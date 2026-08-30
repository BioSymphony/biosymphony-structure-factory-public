"""Execute a hash-bound sequence of local binder adapters."""

from __future__ import annotations

import json
import math
import os
import shutil
import tempfile
from pathlib import Path
from typing import Any, Mapping

from . import binder_executor, binder_lane, remediation, target_verifier


CONTROLLER_SCHEMA = "structure-factory-binder-controller-v1"
RECEIPT_SCHEMA = "structure-factory-binder-controller-receipt-v1"
RESULT_BOUNDARIES = frozenset(
    {"planning", "public_demo", "public_synthetic_demo", "computational_candidate"}
)
AUTHORIZATION = "authorize_local_execution"


class BinderControllerError(ValueError):
    """A binder controller request does not satisfy its execution contract."""


def _exact_keys(
    value: Mapping[str, Any],
    required: set[str],
    label: str,
    optional: set[str] | None = None,
) -> None:
    missing = sorted(required - set(value))
    unknown = sorted(set(value) - required - (optional or set()))
    if missing:
        raise BinderControllerError(f"{label} is missing required fields: {', '.join(missing)}")
    if unknown:
        raise BinderControllerError(f"{label} has unknown fields: {', '.join(unknown)}")


def _money(value: Any, label: str) -> float:
    if isinstance(value, bool) or not isinstance(value, (int, float)) or not math.isfinite(float(value)):
        raise BinderControllerError(f"{label} must be a finite number")
    if value < 0:
        raise BinderControllerError(f"{label} must be non-negative")
    return float(value)


def _validate_workflow_strategy(
    strategy: Mapping[str, Any],
    toolchain_ids: set[str],
) -> dict[str, Any]:
    """Validate controller arm classifications against the prepared stages."""
    mode = strategy.get("mode")
    if not isinstance(mode, str) or mode not in binder_lane.WORKFLOW_STRATEGY_MODES:
        raise BinderControllerError("workflow_strategy mode is not supported")

    reference_scope = strategy.get("reference_scope")
    if reference_scope is not None and (
        not isinstance(reference_scope, str)
        or reference_scope not in binder_lane.WORKFLOW_REFERENCE_SCOPES
    ):
        raise BinderControllerError("workflow_strategy reference_scope is not supported")

    classifications: dict[str, list[Any]] = {}
    for field in ("replay_toolchain_ids", "swap_toolchain_ids"):
        values = strategy.get(field)
        if not isinstance(values, list) or any(
            not isinstance(value, str) or binder_lane.SAFE_ID_RE.fullmatch(value) is None
            for value in values
        ):
            raise BinderControllerError(f"workflow_strategy {field} must contain public IDs")
        if len(values) != len(set(values)) or not set(values).issubset(toolchain_ids):
            raise BinderControllerError(
                f"workflow_strategy {field} must contain unique declared toolchain IDs"
            )
        classifications[field] = values

    replay_set = set(classifications["replay_toolchain_ids"])
    swap_set = set(classifications["swap_toolchain_ids"])
    if replay_set.intersection(swap_set):
        raise BinderControllerError("workflow_strategy replay and swap toolchains must be disjoint")
    if mode == "independent":
        if reference_scope is not None or replay_set or swap_set:
            raise BinderControllerError(
                "independent workflow_strategy must not classify reference toolchains"
            )
    else:
        if reference_scope not in binder_lane.WORKFLOW_REFERENCE_SCOPES:
            raise BinderControllerError(
                "reference workflow strategies must use published_workflow_shape or published_tool_identities"
            )
        if replay_set.union(swap_set) != toolchain_ids:
            raise BinderControllerError("workflow_strategy must classify every toolchain")
        if mode == "published_shape_replay" and (replay_set != toolchain_ids or swap_set):
            raise BinderControllerError(
                "published_shape_replay must classify every toolchain as replay"
            )
        if mode == "deliberate_tool_swap" and (swap_set != toolchain_ids or replay_set):
            raise BinderControllerError(
                "deliberate_tool_swap must classify every toolchain as a swap"
            )
        if mode == "replay_and_swap" and (not replay_set or not swap_set):
            raise BinderControllerError(
                "replay_and_swap requires at least one replay and one swap toolchain"
            )
    return {
        "mode": mode,
        "reference_scope": reference_scope,
        "replay_toolchain_ids": list(classifications["replay_toolchain_ids"]),
        "swap_toolchain_ids": list(classifications["swap_toolchain_ids"]),
    }


def _validate_input_handoffs(
    value: Any,
    *,
    label: str,
    stage: Mapping[str, Any],
    stage_adapter: Mapping[str, Any],
    prior_stages: Mapping[str, Mapping[str, Any]],
    adapters: Mapping[str, Mapping[str, Any]],
) -> list[dict[str, str]]:
    if not isinstance(value, list):
        raise BinderControllerError(f"{label} must be a list")
    normalized: list[dict[str, str]] = []
    destination_bindings: set[str] = set()
    destination_paths: list[Path] = []
    for index, handoff in enumerate(value):
        item_label = f"{label}[{index}]"
        if not isinstance(handoff, dict):
            raise BinderControllerError(f"{item_label} must be an object")
        _exact_keys(
            handoff,
            {"source_stage_id", "source_output_id", "destination_binding"},
            item_label,
        )
        source_stage_id = handoff.get("source_stage_id")
        source_output_id = handoff.get("source_output_id")
        destination_binding = handoff.get("destination_binding")
        if (
            not isinstance(source_stage_id, str)
            or binder_lane.SAFE_ID_RE.fullmatch(source_stage_id) is None
        ):
            raise BinderControllerError(f"{item_label}.source_stage_id is invalid")
        if source_stage_id not in prior_stages or source_stage_id not in stage["depends_on"]:
            raise BinderControllerError(
                f"{item_label}.source_stage_id must name an earlier dependency"
            )
        for field, value_item in (
            ("source_output_id", source_output_id),
            ("destination_binding", destination_binding),
        ):
            if (
                not isinstance(value_item, str)
                or binder_lane.SAFE_ID_RE.fullmatch(value_item) is None
            ):
                raise BinderControllerError(f"{item_label}.{field} is invalid")
        source_adapter = adapters[prior_stages[source_stage_id]["adapter_id"]]
        source_outputs = [
            output
            for output in source_adapter["expected_outputs"]
            if output["id"] == source_output_id
        ]
        if len(source_outputs) != 1:
            raise BinderControllerError(
                f"{item_label}.source_output_id must name one output contract"
            )
        source_output = source_outputs[0]
        destination_spec = stage_adapter["placeholders"].get(destination_binding)
        if destination_spec is None or destination_spec["type"] != "path":
            raise BinderControllerError(
                f"{item_label}.destination_binding must name a path binding"
            )
        if destination_binding in destination_bindings:
            raise BinderControllerError(f"{label} repeats a destination binding")
        destination_value = stage["bindings"].get(destination_binding)
        try:
            destination_path = binder_lane.safe_relative_path(
                destination_value, f"{item_label} destination"
            )
        except binder_lane.BinderLaneError as exc:
            raise BinderControllerError(
                f"{item_label}.destination_binding must resolve to a relative input path"
            ) from exc
        if any(
            destination_path == existing
            or destination_path in existing.parents
            or existing in destination_path.parents
            for existing in destination_paths
        ):
            raise BinderControllerError(f"{label} has overlapping destination paths")
        marker = "{{" + destination_binding + "}}"
        if any(marker in output["path_template"] for output in stage_adapter["expected_outputs"]):
            raise BinderControllerError(
                f"{item_label}.destination_binding must not name a declared output"
            )
        destination_bindings.add(destination_binding)
        destination_paths.append(destination_path)
        normalized.append(
            {
                "source_stage_id": source_stage_id,
                "source_output_id": source_output_id,
                "destination_binding": destination_binding,
                "artifact_kind": source_output["kind"],
            }
        )
    return normalized


def validate_controller(request: Any, registry: Any) -> tuple[dict[str, Any], dict[str, Any]]:
    """Validate a controller request and its adapter registry."""
    if not isinstance(request, dict):
        raise BinderControllerError("controller request must be an object")
    _exact_keys(
        request,
        {
            "schema_version",
            "controller_id",
            "plan_sha256",
            "result_boundary",
            "target_verification",
            "budget",
            "stages",
        },
        "controller request",
        {"target_verification_sha256", "workflow_strategy", "round_context"},
    )
    if request.get("schema_version") != CONTROLLER_SCHEMA:
        raise BinderControllerError(f"controller schema_version must be {CONTROLLER_SCHEMA}")
    controller_id = request.get("controller_id")
    if not isinstance(controller_id, str) or binder_lane.SAFE_ID_RE.fullmatch(controller_id) is None:
        raise BinderControllerError("controller_id must be a lowercase public slug")
    plan_sha256 = request.get("plan_sha256")
    if not isinstance(plan_sha256, str) or binder_lane.SHA256_RE.fullmatch(plan_sha256) is None:
        raise BinderControllerError("plan_sha256 must be a lowercase SHA-256 digest")
    if request.get("result_boundary") not in RESULT_BOUNDARIES:
        raise BinderControllerError("result_boundary is not supported")

    target_verification_sha256 = request.get("target_verification_sha256")
    if target_verification_sha256 is not None and (
        not isinstance(target_verification_sha256, str)
        or binder_lane.SHA256_RE.fullmatch(target_verification_sha256) is None
    ):
        raise BinderControllerError(
            "target_verification_sha256 must be a lowercase SHA-256 digest"
        )

    workflow_strategy = request.get("workflow_strategy")
    if workflow_strategy is not None:
        if not isinstance(workflow_strategy, dict):
            raise BinderControllerError("workflow_strategy must be an object")
        _exact_keys(
            workflow_strategy,
            {"mode", "reference_scope", "replay_toolchain_ids", "swap_toolchain_ids"},
            "workflow_strategy",
        )

    round_context = request.get("round_context")
    if round_context is not None:
        if not isinstance(round_context, dict):
            raise BinderControllerError("round_context must be an object")
        _exact_keys(
            round_context,
            {
                "current_round_index",
                "maximum_round_count",
                "primary_metric_id",
                "direction",
                "selected_stages",
            },
            "round_context",
        )
        current = round_context.get("current_round_index")
        maximum = round_context.get("maximum_round_count")
        if (
            isinstance(current, bool)
            or not isinstance(current, int)
            or isinstance(maximum, bool)
            or not isinstance(maximum, int)
            or not 1 <= current <= maximum
        ):
            raise BinderControllerError("round_context indexes are invalid")
        metric = round_context.get("primary_metric_id")
        if not isinstance(metric, str) or binder_lane.SAFE_ID_RE.fullmatch(metric) is None:
            raise BinderControllerError("round_context primary_metric_id is invalid")
        if round_context.get("direction") not in {"maximize", "minimize"}:
            raise BinderControllerError("round_context direction is not supported")
        selected = round_context.get("selected_stages")
        if (
            not isinstance(selected, list)
            or not selected
            or len(selected) != len(set(selected))
            or any(stage not in binder_lane.ROUTABLE_STAGES for stage in selected)
        ):
            raise BinderControllerError("round_context selected_stages is invalid")

    target = request.get("target_verification")
    if not isinstance(target, dict):
        raise BinderControllerError("target_verification must be an object")
    if (
        target.get("ok") is not True
        or target.get("schema_version") != target_verifier.REPORT_SCHEMA
        or target.get("required_residues_verified") is not True
        or not isinstance(target.get("structure_sha256"), str)
        or binder_lane.SHA256_RE.fullmatch(target["structure_sha256"]) is None
    ):
        raise BinderControllerError("target verification does not establish the requested site")

    budget = request.get("budget")
    if not isinstance(budget, dict):
        raise BinderControllerError("budget must be an object")
    _exact_keys(budget, {"currency", "spend_ceiling_usd"}, "budget")
    if budget.get("currency") != "USD":
        raise BinderControllerError("budget currency must be USD")
    ceiling = _money(budget.get("spend_ceiling_usd"), "budget spend_ceiling_usd")

    validated_registry = binder_executor.validate_registry(registry)
    adapters = {row["id"]: row for row in validated_registry["adapters"]}
    stages = request.get("stages")
    if not isinstance(stages, list) or not stages:
        raise BinderControllerError("stages must be a non-empty list")
    normalized_stages: list[dict[str, Any]] = []
    stages_by_id: dict[str, dict[str, Any]] = {}
    seen: set[str] = set()
    mapped_stage_count = 0
    stage_toolchain_ids: set[str] = set()
    total = 0.0
    for index, stage in enumerate(stages):
        label = f"stages[{index}]"
        if not isinstance(stage, dict):
            raise BinderControllerError(f"{label} must be an object")
        _exact_keys(
            stage,
            {"stage_id", "adapter_id", "depends_on", "bindings", "estimated_cost_usd", "timeout_seconds"},
            label,
            {"toolchain_id", "stage", "tool_id", "variant_id", "route", "input_handoffs"},
        )
        stage_id = stage.get("stage_id")
        if not isinstance(stage_id, str) or binder_lane.SAFE_ID_RE.fullmatch(stage_id) is None or stage_id in seen:
            raise BinderControllerError(f"{label}.stage_id is invalid or duplicated")
        depends_on = stage.get("depends_on")
        if (
            not isinstance(depends_on, list)
            or any(not isinstance(item, str) or item not in seen for item in depends_on)
            or len(depends_on) != len(set(depends_on))
        ):
            raise BinderControllerError(f"{label}.depends_on must name earlier stages")
        adapter_id = stage.get("adapter_id")
        if adapter_id not in adapters:
            raise BinderControllerError(f"{label}.adapter_id is not in the registry")
        mapping_fields = {"toolchain_id", "stage", "tool_id", "variant_id", "route"}
        present_mapping_fields = set(stage).intersection(mapping_fields)
        if present_mapping_fields and present_mapping_fields != mapping_fields:
            raise BinderControllerError(f"{label} plan mapping is incomplete")
        if present_mapping_fields:
            mapped_stage_count += 1
            toolchain_id = stage.get("toolchain_id")
            stage_name = stage.get("stage")
            tool_id = stage.get("tool_id")
            variant_id = stage.get("variant_id")
            route = stage.get("route")
            if (
                not isinstance(toolchain_id, str)
                or binder_lane.SAFE_ID_RE.fullmatch(toolchain_id) is None
                or stage_name not in binder_lane.ROUTABLE_STAGES
                or not isinstance(tool_id, str)
                or binder_lane.SAFE_ID_RE.fullmatch(tool_id) is None
                or (variant_id is not None and (
                    not isinstance(variant_id, str)
                    or binder_lane.SAFE_ID_RE.fullmatch(variant_id) is None
                ))
                or not isinstance(route, dict)
            ):
                raise BinderControllerError(f"{label} plan mapping is invalid")
            _exact_keys(route, {"id", "backend", "execution_method"}, f"{label}.route")
            if (
                not isinstance(route.get("id"), str)
                or binder_lane.SAFE_ID_RE.fullmatch(route["id"]) is None
                or route.get("backend") not in binder_lane.BACKENDS
                or route.get("execution_method") not in {"platform_skill", "hosted_api", "self_hosted"}
                or not binder_executor.adapter_supports_selection(
                    adapters[adapter_id], tool_id, variant_id
                )
                or not binder_executor.adapter_supports_route(adapters[adapter_id], route)
            ):
                raise BinderControllerError(f"{label} route or tool mapping is invalid")
            stage_toolchain_ids.add(toolchain_id)
        if not isinstance(stage.get("bindings"), dict):
            raise BinderControllerError(f"{label}.bindings must be an object")
        handoffs = _validate_input_handoffs(
            stage.get("input_handoffs", []),
            label=f"{label}.input_handoffs",
            stage=stage,
            stage_adapter=adapters[adapter_id],
            prior_stages=stages_by_id,
            adapters=adapters,
        )
        timeout = stage.get("timeout_seconds")
        if isinstance(timeout, bool) or not isinstance(timeout, int) or timeout < 1:
            raise BinderControllerError(f"{label}.timeout_seconds must be a positive integer")
        cost = _money(stage.get("estimated_cost_usd"), f"{label}.estimated_cost_usd")
        total += cost
        seen.add(stage_id)
        normalized_stage = {
            **stage,
            "input_handoffs": handoffs,
            "estimated_cost_usd": cost,
        }
        normalized_stages.append(normalized_stage)
        stages_by_id[stage_id] = normalized_stage
    if workflow_strategy is not None:
        if mapped_stage_count not in {0, len(stages)}:
            raise BinderControllerError(
                "workflow_strategy requires complete toolchain mappings for every stage"
            )
        if workflow_strategy.get("mode") != "independent" and mapped_stage_count != len(stages):
            raise BinderControllerError(
                "reference workflow strategies require toolchain mappings for every stage"
            )
        workflow_strategy = _validate_workflow_strategy(workflow_strategy, stage_toolchain_ids)
    if total > ceiling + 1e-9:
        raise BinderControllerError("stage cost estimates exceed the spend ceiling")
    return (
        {
            **request,
            "budget": {"currency": "USD", "spend_ceiling_usd": ceiling},
            "stages": normalized_stages,
            **({"workflow_strategy": workflow_strategy} if workflow_strategy is not None else {}),
        },
        validated_registry,
    )


def _write_receipt(run_root: Path, receipt: Mapping[str, Any]) -> Path:
    path = run_root / "controller-receipt.json"
    encoded = json.dumps(receipt, indent=2, sort_keys=True, allow_nan=False) + "\n"
    with tempfile.NamedTemporaryFile("w", encoding="utf-8", dir=run_root, delete=False) as handle:
        handle.write(encoded)
        temporary = Path(handle.name)
    os.replace(temporary, path)
    return path


def _planned_input_handoffs(stage: Mapping[str, Any]) -> list[dict[str, Any]]:
    return [
        {
            **handoff,
            "state": "planned",
            "source_receipt_sha256": None,
            "source_artifact_sha256": None,
            "destination_artifact_sha256": None,
            "file_count": None,
            "byte_count": None,
            "record_count": None,
        }
        for handoff in stage["input_handoffs"]
    ]


def _contained_path(root: Path, relative: str, label: str) -> Path:
    try:
        safe = binder_lane.safe_relative_path(relative, label)
    except binder_lane.BinderLaneError as exc:
        raise BinderControllerError(f"{label} is not a safe relative path") from exc
    current = root
    for part in safe.parts:
        current = current / part
        if current.is_symlink():
            raise BinderControllerError(f"{label} must not use a symbolic link")
    resolved = (root / safe).resolve()
    if resolved == root or root not in resolved.parents:
        raise BinderControllerError(f"{label} resolves outside its stage root")
    return resolved


def _path_exists(path: Path) -> bool:
    return os.path.lexists(path)


def _copy_file_atomically(
    source: Path,
    destination: Path,
    *,
    source_sha256: str,
    source_records: int,
    kind: str,
) -> None:
    if _path_exists(destination):
        raise BinderControllerError("input handoff destination already exists")
    destination.parent.mkdir(parents=True, exist_ok=True)
    with source.open("rb") as source_handle, tempfile.NamedTemporaryFile(
        "wb", dir=destination.parent, delete=False
    ) as destination_handle:
        shutil.copyfileobj(source_handle, destination_handle)
        temporary = Path(destination_handle.name)
    try:
        copied_sha256 = binder_lane.sha256_path(temporary)
        copied_records = binder_executor._record_count(temporary, kind)
        if copied_sha256 != source_sha256 or copied_records != source_records:
            raise BinderControllerError("input handoff copy differs from its verified source")
        try:
            os.link(temporary, destination)
        except FileExistsError as exc:
            raise BinderControllerError("input handoff destination already exists") from exc
    finally:
        temporary.unlink(missing_ok=True)


def _copy_directory_atomically(
    source: Path,
    destination: Path,
    *,
    source_sha256: str,
    source_bytes: int,
    source_members: list[dict[str, Any]],
) -> None:
    if _path_exists(destination):
        raise BinderControllerError("input handoff destination already exists")
    destination.parent.mkdir(parents=True, exist_ok=True)
    temporary = Path(tempfile.mkdtemp(prefix=".bsf-handoff-", dir=destination.parent))
    try:
        for member in source_members:
            source_member = _contained_path(
                source,
                member.get("path"),
                "input handoff source bundle member",
            )
            if not source_member.is_file() or source_member.is_symlink():
                raise BinderControllerError("input handoff source bundle member is missing")
            destination_member = _contained_path(
                temporary,
                member["path"],
                "input handoff destination bundle member",
            )
            if _path_exists(destination_member):
                raise BinderControllerError("input handoff bundle repeats a destination member")
            destination_member.parent.mkdir(parents=True, exist_ok=True)
            shutil.copyfile(source_member, destination_member)

        copied_sha256, copied_bytes, copied_members = binder_executor._directory_manifest(
            temporary
        )
        if (
            copied_sha256 != source_sha256
            or copied_bytes != source_bytes
            or copied_members != source_members
        ):
            raise BinderControllerError("input handoff bundle copy differs from its verified source")
        if _path_exists(destination):
            raise BinderControllerError("input handoff destination already exists")
        os.rename(temporary, destination)
    finally:
        if temporary.exists():
            shutil.rmtree(temporary)


def _materialize_input_handoffs(
    stage: Mapping[str, Any],
    *,
    workspace: Path,
    run_root: Path,
    stage_root: Path,
    completed_rows: Mapping[str, Mapping[str, Any]],
) -> list[dict[str, Any]]:
    materialized: list[dict[str, Any]] = []
    for handoff in stage["input_handoffs"]:
        source_stage_id = handoff["source_stage_id"]
        source_row = completed_rows.get(source_stage_id)
        if source_row is None:
            raise BinderControllerError("input handoff source stage has no completed receipt")
        receipt_path = _contained_path(
            run_root,
            source_row["receipt_path"],
            "input handoff source receipt",
        )
        if not receipt_path.is_file() or receipt_path.is_symlink():
            raise BinderControllerError("input handoff source receipt is missing")
        receipt_sha256 = binder_lane.sha256_path(receipt_path)
        if receipt_sha256 != source_row["receipt_sha256"]:
            raise BinderControllerError("input handoff source receipt hash changed")
        try:
            receipt = binder_lane.read_json(receipt_path)
        except (binder_lane.BinderLaneError, OSError) as exc:
            raise BinderControllerError("input handoff source receipt is unreadable") from exc
        source_stage_root = (run_root / "stages" / source_stage_id).resolve()
        if (
            receipt.get("schema_version")
            != "structure-factory-binder-execution-receipt-v1"
            or receipt.get("adapter_id") != source_row["adapter_id"]
            or receipt.get("operation") != "run"
            or receipt.get("dry_run") is not False
            or receipt.get("authorized") is not True
            or receipt.get("status") != "completed"
            or receipt.get("ok") is not True
            or receipt.get("runtime_root")
            != source_stage_root.relative_to(workspace).as_posix()
            or not isinstance(receipt.get("outputs"), list)
        ):
            raise BinderControllerError("input handoff source receipt is not a completed local run")
        output_rows = [
            output
            for output in receipt["outputs"]
            if isinstance(output, dict)
            and output.get("id") == handoff["source_output_id"]
        ]
        if len(output_rows) != 1:
            raise BinderControllerError("input handoff source output is absent or duplicated")
        output = output_rows[0]
        files = output.get("files")
        source_kind = handoff["artifact_kind"]
        if (
            output.get("kind") != source_kind
            or output.get("matched_count") != 1
            or not isinstance(files, list)
            or len(files) != 1
            or not isinstance(files[0], dict)
        ):
            raise BinderControllerError("input handoff source output must resolve to one artifact")
        artifact = files[0]
        source_path = _contained_path(
            source_stage_root,
            artifact.get("path"),
            "input handoff source artifact",
        )
        try:
            if source_kind == "directory":
                if not source_path.is_dir() or source_path.is_symlink():
                    raise BinderControllerError("input handoff source bundle is missing")
                source_sha256, source_bytes, source_members = (
                    binder_executor._directory_manifest(source_path)
                )
                source_records = len(source_members)
                if (
                    source_sha256 != artifact.get("sha256")
                    or source_bytes != artifact.get("bytes")
                    or source_records != artifact.get("records")
                    or source_members != artifact.get("members")
                ):
                    raise BinderControllerError(
                        "input handoff source bundle manifest changed"
                    )
            else:
                if not source_path.is_file() or source_path.is_symlink():
                    raise BinderControllerError("input handoff source artifact is missing")
                source_sha256 = binder_lane.sha256_path(source_path)
                source_bytes = source_path.stat().st_size
                source_records = binder_executor._record_count(source_path, source_kind)
                source_members = []
                if (
                    source_sha256 != artifact.get("sha256")
                    or source_bytes != artifact.get("bytes")
                    or source_records != artifact.get("records")
                    or "members" in artifact
                ):
                    raise BinderControllerError(
                        "input handoff source artifact hash, size, or record count changed"
                    )
        except (
            binder_executor.BinderExecutorError,
            OSError,
            UnicodeError,
            json.JSONDecodeError,
        ) as exc:
            raise BinderControllerError("input handoff source artifact content is invalid") from exc

        destination_value = stage["bindings"][handoff["destination_binding"]]
        destination = _contained_path(
            stage_root,
            destination_value,
            "input handoff destination",
        )
        if source_kind == "directory":
            _copy_directory_atomically(
                source_path,
                destination,
                source_sha256=source_sha256,
                source_bytes=source_bytes,
                source_members=source_members,
            )
        else:
            _copy_file_atomically(
                source_path,
                destination,
                source_sha256=source_sha256,
                source_records=source_records,
                kind=source_kind,
            )
        destination_sha256 = source_sha256
        destination_bytes = source_bytes
        destination_records = source_records
        materialized.append(
            {
                **handoff,
                "state": "materialized",
                "source_receipt_sha256": receipt_sha256,
                "source_artifact_sha256": source_sha256,
                "destination_artifact_sha256": destination_sha256,
                "file_count": source_records if source_kind == "directory" else 1,
                "byte_count": destination_bytes,
                "record_count": source_records,
            }
        )
    return materialized


def run_controller(
    request: Any,
    registry: Any,
    *,
    workspace_root: Path,
    runtime_root: Path,
    plan_sha256: str,
    authorization: str | None,
    authorize_network: bool = False,
    authorize_license_gates: bool = False,
    dry_run: bool = False,
) -> dict[str, Any]:
    """Run ready stages in dependency order and stop at the first failed receipt."""
    normalized, validated_registry = validate_controller(request, registry)
    if normalized["plan_sha256"] != plan_sha256:
        raise BinderControllerError("controller request does not match the selected plan SHA-256")
    if not dry_run and authorization != AUTHORIZATION:
        raise BinderControllerError("local execution requires explicit authorization")
    adapters = {row["id"]: row for row in validated_registry["adapters"]}
    for stage in normalized["stages"]:
        adapter = adapters[stage["adapter_id"]]
        if adapter["execution_kind"] != binder_executor.SUPPORTED_EXECUTION_KIND:
            raise BinderControllerError(
                f"stage {stage['stage_id']} adapter readiness is {adapter['implementation_status']}: "
                "a local argv adapter contract is required"
            )
        if not dry_run and adapter["network_policy"] == "runtime_review_required" and not authorize_network:
            raise BinderControllerError("network execution requires explicit authorization")
        if not dry_run and adapter["license_gate"] != "none" and not authorize_license_gates:
            raise BinderControllerError("license-gated execution requires explicit authorization")

    workspace = Path(workspace_root).resolve()
    run_root = binder_lane.require_runtime_root(workspace, Path(runtime_root), must_exist=False)
    run_root.mkdir(parents=True, exist_ok=True)
    stage_rows: list[dict[str, Any]] = []
    completed: set[str] = set()
    completed_rows: dict[str, dict[str, Any]] = {}
    status = "planned" if dry_run else "completed"
    halted = False
    for stage in normalized["stages"]:
        if halted or any(dependency not in completed for dependency in stage["depends_on"]):
            status = "planned_with_readiness_gaps" if dry_run else "failed"
            stage_rows.append(
                {
                    "stage_id": stage["stage_id"],
                    "adapter_id": stage["adapter_id"],
                    "state": "not_started",
                    "input_handoffs": _planned_input_handoffs(stage),
                    "failure": remediation.failure_record(BinderControllerError("stage dependency failed")),
                }
            )
            halted = True
            continue
        stage_root = run_root / "stages" / stage["stage_id"]
        input_handoffs = _planned_input_handoffs(stage)
        if not dry_run:
            stage_root.mkdir(parents=True, exist_ok=True)
            try:
                input_handoffs = _materialize_input_handoffs(
                    stage,
                    workspace=workspace,
                    run_root=run_root,
                    stage_root=stage_root,
                    completed_rows=completed_rows,
                )
            except (BinderControllerError, OSError) as exc:
                failure = (
                    exc
                    if isinstance(exc, BinderControllerError)
                    else BinderControllerError("input handoff local file operation failed")
                )
                status = "failed"
                stage_rows.append(
                    {
                        "stage_id": stage["stage_id"],
                        "adapter_id": stage["adapter_id"],
                        "implementation_status": adapters[stage["adapter_id"]][
                            "implementation_status"
                        ],
                        "state": "failed",
                        "estimated_cost_usd": stage["estimated_cost_usd"],
                        "input_handoffs": input_handoffs,
                        "failure": remediation.failure_record(failure),
                    }
                )
                halted = True
                continue
        result = binder_executor.run_adapter(
            validated_registry,
            stage["adapter_id"],
            workspace_root=workspace,
            runtime_root=stage_root,
            bindings=stage["bindings"],
            operation="run",
            authorization=(binder_executor.LOCAL_EXECUTION_AUTHORIZATION if not dry_run else None),
            dry_run=dry_run,
            timeout_seconds=stage["timeout_seconds"],
        )
        adapter_receipt = workspace / result["receipt_path"]
        row = {
            "stage_id": stage["stage_id"],
            "adapter_id": stage["adapter_id"],
            "implementation_status": result["implementation_status"],
            "state": result["status"],
            "estimated_cost_usd": stage["estimated_cost_usd"],
            "receipt_path": adapter_receipt.relative_to(run_root).as_posix(),
            "receipt_sha256": binder_lane.sha256_path(adapter_receipt),
            "output_contract_count": len(result["outputs"]),
            "input_handoffs": input_handoffs,
        }
        if not result["ok"]:
            row["failure"] = remediation.failure_record(
                binder_executor.BinderExecutorError("adapter readiness or output validation failed")
            )
            status = "planned_with_readiness_gaps" if dry_run else "failed"
            stage_rows.append(row)
            halted = True
            continue
        stage_rows.append(row)
        completed.add(stage["stage_id"])
        completed_rows[stage["stage_id"]] = row

    receipt = {
        "schema_version": RECEIPT_SCHEMA,
        "controller_id": normalized["controller_id"],
        "plan_sha256": plan_sha256,
        "target_verification_sha256": normalized.get("target_verification_sha256"),
        "target_structure_sha256": normalized["target_verification"]["structure_sha256"],
        "result_boundary": normalized["result_boundary"],
        "dry_run": dry_run,
        "authorized": authorization == AUTHORIZATION,
        "network_authorized": authorize_network,
        "license_gates_authorized": authorize_license_gates,
        "status": status,
        "planned_stage_count": len(normalized["stages"]),
        "completed_stage_count": len(completed),
        "spend_ceiling_usd": normalized["budget"]["spend_ceiling_usd"],
        "estimated_cost_usd": sum(stage["estimated_cost_usd"] for stage in normalized["stages"]),
        "actual_spend_usd": None,
        "stages": stage_rows,
        "provider_calls": 0,
    }
    receipt_path = _write_receipt(run_root, receipt)
    return {
        "ok": status in {"completed", "planned"},
        **receipt,
        "receipt_path": receipt_path.relative_to(workspace).as_posix(),
    }
