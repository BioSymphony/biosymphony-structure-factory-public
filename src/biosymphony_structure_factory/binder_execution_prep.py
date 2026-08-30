"""Derive a local controller request from a validated binder plan."""

from __future__ import annotations

import math
from pathlib import Path
from typing import Any, Mapping, Sequence

from . import binder_controller, binder_executor, binder_lane, binder_target, target_verifier


PREPARATION_SCHEMA = "structure-factory-binder-execution-preparation-v1"
STAGE_ROLES = {
    "generation": "generator",
    "sequence_design": "sequence_designer",
    "cofold": "predictor",
    "scoring": "scorer",
    "filter": "filter",
}


class BinderExecutionPreparationError(ValueError):
    """The execution-preparation input is structurally invalid."""


def _target_report(report: Any) -> dict[str, Any]:
    if (
        isinstance(report, dict)
        and report.get("schema_version") == "structure-factory-target-verification-v1"
    ):
        raise BinderExecutionPreparationError(
            "target verification v1 is not plan-bound; rerun target-check with --plan to create a v2 report"
        )
    required = {
        "ok",
        "schema_version",
        "plan_sha256",
        "target_contract_sha256",
        "target_contract",
        "format",
        "structure_sha256",
        "chain_id",
        "coordinate_residue_count",
        "first_coordinate_residue",
        "last_coordinate_residue",
        "required_residue_count",
        "required_residues_verified",
        "sequence_basis",
        "sequence_length",
        "sequence_sha256",
        "sequence_verified",
        "provider_calls",
    }
    if not isinstance(report, dict) or set(report) != required:
        raise BinderExecutionPreparationError(
            "target verification report fields do not match the public report contract"
        )
    if (
        report.get("ok") is not True
        or report.get("schema_version") != target_verifier.REPORT_SCHEMA
        or report.get("required_residues_verified") is not True
        or report.get("provider_calls") != 0
        or report.get("format") not in {"pdb", "mmcif"}
        or report.get("sequence_basis") not in {"coordinates", "entity"}
        or not isinstance(report.get("sequence_verified"), bool)
    ):
        raise BinderExecutionPreparationError(
            "target verification report does not establish the requested site"
        )
    for field in (
        "plan_sha256",
        "target_contract_sha256",
        "structure_sha256",
        "sequence_sha256",
    ):
        digest = report.get(field)
        if not isinstance(digest, str) or binder_lane.SHA256_RE.fullmatch(digest) is None:
            raise BinderExecutionPreparationError(f"target verification {field} is invalid")
    try:
        target_contract = binder_target.normalize_target_contract(
            report.get("target_contract"), "target verification target_contract"
        )
    except binder_target.BinderTargetError as exc:
        raise BinderExecutionPreparationError(str(exc)) from exc
    if report.get("target_contract") != target_contract:
        raise BinderExecutionPreparationError(
            "target verification target_contract must use normalized residue labels"
        )
    if report["target_contract_sha256"] != binder_target.target_contract_sha256(
        target_contract
    ):
        raise BinderExecutionPreparationError(
            "target verification target_contract_sha256 does not match target_contract"
        )
    if (
        report.get("chain_id") != target_contract["site"]["chain_id"]
        or report.get("required_residue_count")
        != binder_target.required_residue_count(
            target_contract["site"]["required_residues"],
            "target verification target_contract site.required_residues",
        )
    ):
        raise BinderExecutionPreparationError(
            "target verification chain or residue count differs from target_contract.site"
        )
    for field in ("coordinate_residue_count", "required_residue_count", "sequence_length"):
        value = report.get(field)
        if isinstance(value, bool) or not isinstance(value, int) or value < 1:
            raise BinderExecutionPreparationError(f"target verification {field} must be positive")
    return dict(report)


def _selected_stages(plan: Mapping[str, Any], selected: Sequence[str] | None) -> list[str]:
    available = [
        stage
        for stage in binder_lane.ROUTABLE_STAGES
        if any(stage in route["stages"] for route in plan["execution_policy"]["routes"])
    ]
    if selected is None:
        return available
    if not selected or any(stage not in available for stage in selected):
        raise BinderExecutionPreparationError(
            "selected stages must be a non-empty subset of the plan stages"
        )
    if len(selected) != len(set(selected)):
        raise BinderExecutionPreparationError("selected stages must not contain duplicates")
    return [stage for stage in available if stage in selected]


def _tools(toolchain: Mapping[str, Any], stage: str) -> list[dict[str, Any]]:
    if stage == "generation":
        return [toolchain["generator"]]
    if stage == "sequence_design":
        return [toolchain["sequence_designer"]]
    if stage == "cofold":
        return list(toolchain["predictors"])
    if stage == "scoring":
        return list(toolchain["scorers"])
    if stage == "filter":
        return list(toolchain["filters"])
    return []


def _route(plan: Mapping[str, Any], toolchain_id: str, stage: str) -> dict[str, Any]:
    matches = [
        route
        for route in plan["execution_policy"]["routes"]
        if toolchain_id in route["toolchain_ids"] and stage in route["stages"]
    ]
    if len(matches) != 1:
        raise BinderExecutionPreparationError(
            "validated plan does not resolve one route for each selected toolchain stage"
        )
    return matches[0]


def _setting(settings: Mapping[str, Any], selector: str) -> dict[str, Any]:
    raw = settings.get(selector, {})
    if not isinstance(raw, dict):
        raise BinderExecutionPreparationError(f"stage setting {selector} must be an object")
    allowed = {
        "adapter_id",
        "bindings",
        "estimated_cost_usd",
        "input_handoffs",
        "timeout_seconds",
    }
    if set(raw) - allowed:
        raise BinderExecutionPreparationError(f"stage setting {selector} has unknown fields")
    bindings = raw.get("bindings", {})
    if not isinstance(bindings, dict):
        raise BinderExecutionPreparationError(f"stage setting {selector} bindings must be an object")
    cost = raw.get("estimated_cost_usd", 0)
    if (
        isinstance(cost, bool)
        or not isinstance(cost, (int, float))
        or not math.isfinite(float(cost))
        or cost < 0
    ):
        raise BinderExecutionPreparationError(
            f"stage setting {selector} estimated_cost_usd must be non-negative"
        )
    timeout = raw.get("timeout_seconds", 300)
    if isinstance(timeout, bool) or not isinstance(timeout, int) or timeout < 1:
        raise BinderExecutionPreparationError(
            f"stage setting {selector} timeout_seconds must be positive"
        )
    adapter_id = raw.get("adapter_id")
    if adapter_id is not None and (
        not isinstance(adapter_id, str) or binder_lane.SAFE_ID_RE.fullmatch(adapter_id) is None
    ):
        raise BinderExecutionPreparationError(f"stage setting {selector} adapter_id is invalid")
    input_handoffs = raw.get("input_handoffs", [])
    if not isinstance(input_handoffs, list):
        raise BinderExecutionPreparationError(
            f"stage setting {selector} input_handoffs must be a list"
        )
    normalized_handoffs: list[dict[str, str]] = []
    destination_bindings: set[str] = set()
    for index, handoff in enumerate(input_handoffs):
        label = f"stage setting {selector} input_handoffs[{index}]"
        if not isinstance(handoff, dict) or set(handoff) != {
            "source_selector",
            "source_output_id",
            "destination_binding",
        }:
            raise BinderExecutionPreparationError(
                f"{label} must name one source selector, output, and destination binding"
            )
        source_selector = handoff.get("source_selector")
        source_output_id = handoff.get("source_output_id")
        destination_binding = handoff.get("destination_binding")
        if (
            not isinstance(source_selector, str)
            or not source_selector
            or len(source_selector) > 290
            or any(
                character not in "abcdefghijklmnopqrstuvwxyz0123456789._-"
                for character in source_selector
            )
        ):
            raise BinderExecutionPreparationError(f"{label} source_selector is invalid")
        for field, value in (
            ("source_output_id", source_output_id),
            ("destination_binding", destination_binding),
        ):
            if not isinstance(value, str) or binder_lane.SAFE_ID_RE.fullmatch(value) is None:
                raise BinderExecutionPreparationError(f"{label} {field} is invalid")
        if destination_binding in destination_bindings:
            raise BinderExecutionPreparationError(
                f"stage setting {selector} repeats an input handoff destination"
            )
        destination_bindings.add(destination_binding)
        normalized_handoffs.append(
            {
                "source_selector": source_selector,
                "source_output_id": source_output_id,
                "destination_binding": destination_binding,
            }
        )
    return {
        "adapter_id": adapter_id,
        "bindings": dict(bindings),
        "estimated_cost_usd": float(cost),
        "input_handoffs": normalized_handoffs,
        "timeout_seconds": timeout,
    }


def _gap(
    gap_id: str,
    selector: str,
    route: Mapping[str, Any],
    reason: str,
    actions: list[dict[str, str]],
) -> dict[str, Any]:
    toolchain_id, stage, selected_tool = selector.split(".", 2)
    tool_id = selected_tool.split("@", 1)[0]
    return {
        "gap_id": gap_id,
        "selector": selector,
        "toolchain_id": toolchain_id,
        "stage": stage,
        "tool_id": tool_id,
        "route_id": route["id"],
        "reason": reason,
        "next_actions": actions,
    }


def _stage_id(index: int, selector: str) -> str:
    suffix = selector.replace("_", "-").replace(".", "-").replace("@", "-")
    return f"s{index:03d}-{suffix}"[:96].rstrip("-.")


def _selector(toolchain_id: str, stage: str, selection: Mapping[str, Any]) -> str:
    tool_id = selection["tool_id"]
    variant_id = selection.get("variant_id")
    return f"{toolchain_id}.{stage}.{tool_id}" + (
        f"@{variant_id}" if variant_id is not None else ""
    )


def prepare_execution(
    plan: Any,
    target_report: Any,
    registry: Any,
    *,
    plan_sha256: str,
    target_report_sha256: str,
    selected_stages: Sequence[str] | None = None,
    stage_settings: Mapping[str, Any] | None = None,
) -> tuple[dict[str, Any], dict[str, Any] | None]:
    """Build a complete controller request or return actionable readiness gaps."""
    normalized_plan = binder_lane.validate_plan(plan)
    target = _target_report(target_report)
    if not isinstance(plan_sha256, str) or binder_lane.SHA256_RE.fullmatch(plan_sha256) is None:
        raise BinderExecutionPreparationError("plan_sha256 must be a lowercase SHA-256 digest")
    if (
        not isinstance(target_report_sha256, str)
        or binder_lane.SHA256_RE.fullmatch(target_report_sha256) is None
    ):
        raise BinderExecutionPreparationError(
            "target_report_sha256 must be a lowercase SHA-256 digest"
        )
    if target["plan_sha256"] != plan_sha256:
        raise BinderExecutionPreparationError(
            "target verification belongs to another plan; rerun target-check with this exact plan"
        )
    expected_target_sha256 = binder_target.target_contract_sha256(
        normalized_plan["target"]
    )
    if (
        target["target_contract"] != normalized_plan["target"]
        or target["target_contract_sha256"] != expected_target_sha256
    ):
        raise BinderExecutionPreparationError(
            "target verification belongs to another target or site; rerun target-check with this exact plan"
        )
    validated_registry = binder_executor.validate_registry(registry)
    settings = {} if stage_settings is None else stage_settings
    if not isinstance(settings, Mapping):
        raise BinderExecutionPreparationError("stage settings must be an object")
    chosen_stages = _selected_stages(normalized_plan, selected_stages)
    adapters = {row["id"]: row for row in validated_registry["adapters"]}
    stage_rows: list[dict[str, Any]] = []
    mappings: list[dict[str, Any]] = []
    gaps: list[dict[str, Any]] = []
    used_settings: set[str] = set()
    prior_by_toolchain: dict[str, str] = {}
    stage_id_by_selector: dict[str, str] = {}
    sequence = 0

    for toolchain in normalized_plan["toolchains"]:
        toolchain_id = toolchain["id"]
        for stage in chosen_stages:
            route = _route(normalized_plan, toolchain_id, stage)
            tools = _tools(toolchain, stage)
            if not tools:
                mappings.append(
                    {
                        "toolchain_id": toolchain_id,
                        "stage": stage,
                        "route_id": route["id"],
                        "backend": route["backend"],
                        "execution_method": route["execution_method"],
                        "readiness": "bsf_closeout",
                    }
                )
                continue
            for selection in tools:
                sequence += 1
                tool_id = selection["tool_id"]
                selector = _selector(toolchain_id, stage, selection)
                if route["execution_method"] == "platform_skill":
                    mappings.append(
                        {
                            "selector": selector,
                            "toolchain_id": toolchain_id,
                            "stage": stage,
                            "tool_id": tool_id,
                            "variant_id": selection.get("variant_id"),
                            "route_id": route["id"],
                            "backend": route["backend"],
                            "execution_method": route["execution_method"],
                            "adapter_id": None,
                            "readiness": "platform_skill_handoff",
                        }
                    )
                    continue
                config = _setting(settings, selector)
                if selector in settings:
                    used_settings.add(selector)
                candidates = [
                    row
                    for row in validated_registry["adapters"]
                    if STAGE_ROLES[stage] in row["roles"]
                    and binder_executor.adapter_supports_selection(
                        row, tool_id, selection.get("variant_id")
                    )
                ]
                route_candidates = [
                    row for row in candidates if binder_executor.adapter_supports_route(row, route)
                ]
                explicit = config["adapter_id"]
                if explicit is not None:
                    adapter = adapters.get(explicit)
                    if adapter not in candidates:
                        gaps.append(
                            _gap(
                                "adapter-selection-mismatch",
                                selector,
                                route,
                                "The selected adapter does not implement this tool and stage role.",
                                [
                                    {
                                        "id": "select-matching-adapter",
                                        "description": "Select an adapter whose tool ID and role match this selector.",
                                    },
                                    {
                                        "id": "add-adapter",
                                        "description": "Add a validated adapter record below .runtime for this tool and role.",
                                    },
                                ],
                            )
                        )
                        adapter = None
                    elif not binder_executor.adapter_supports_route(adapter, route):
                        gaps.append(
                            _gap(
                                "adapter-route-mismatch",
                                selector,
                                route,
                                "The selected adapter does not declare support for this route backend and execution method.",
                                [
                                    {
                                        "id": "select-route-compatible-adapter",
                                        "description": "Select an adapter that declares this route backend and execution method.",
                                    },
                                    {
                                        "id": "add-runtime-client-adapter",
                                        "description": "Add a validated runtime client adapter that declares this route capability.",
                                    },
                                    {
                                        "id": "change-route",
                                        "description": "Choose a route that matches the selected adapter capability.",
                                    },
                                ],
                            )
                        )
                        adapter = None
                else:
                    ready = [
                        row
                        for row in route_candidates
                        if row["implementation_status"] == "ready"
                        and row["execution_kind"] == binder_executor.SUPPORTED_EXECUTION_KIND
                    ]
                    auto_select = (
                        route["backend"] == "local"
                        and route["execution_method"] == "self_hosted"
                        and not route["operator_adapter_required"]
                        and selection.get("variant_id") is None
                    )
                    adapter = ready[0] if auto_select and len(ready) == 1 else None
                    if adapter is None:
                        route_mismatch = bool(candidates) and not route_candidates
                        reason = (
                            "This route requires an explicit adapter choice."
                            if ready
                            else "The registry has matching adapters, but none declares this route backend and execution method."
                            if route_mismatch
                            else "The registry has no runnable adapter for this tool and stage role."
                        )
                        gaps.append(
                            _gap(
                                "adapter-selection-required"
                                if ready
                                else "adapter-route-required"
                                if route_mismatch
                                else "runnable-adapter-required",
                                selector,
                                route,
                                reason,
                                [
                                    {
                                        "id": "select-adapter",
                                        "description": "Set adapter_id for this selector in the stage settings file.",
                                    },
                                    {
                                        "id": "add-adapter",
                                        "description": "Add a validated client or tool adapter below .runtime.",
                                    },
                                    {
                                        "id": "change-route",
                                        "description": "Choose a route that matches an available adapter or platform skill.",
                                    },
                                ],
                            )
                        )
                mapping = {
                    "selector": selector,
                    "toolchain_id": toolchain_id,
                    "stage": stage,
                    "tool_id": tool_id,
                    "variant_id": selection.get("variant_id"),
                    "route_id": route["id"],
                    "backend": route["backend"],
                    "execution_method": route["execution_method"],
                    "adapter_id": adapter["id"] if adapter is not None else explicit,
                    "readiness": "ready" if adapter is not None else "planning_gap",
                }
                mappings.append(mapping)
                if adapter is None:
                    continue
                if (
                    adapter["implementation_status"] != "ready"
                    or adapter["execution_kind"] != binder_executor.SUPPORTED_EXECUTION_KIND
                ):
                    gaps.append(
                        _gap(
                            "runnable-adapter-required",
                            selector,
                            route,
                            "The selected adapter has no runnable local argument-array contract.",
                            [
                                {
                                    "id": "complete-adapter",
                                    "description": "Add the fixed program, arguments, bindings, and output contract.",
                                },
                                {
                                    "id": "select-adapter",
                                    "description": "Select another validated runnable adapter.",
                                },
                            ],
                        )
                    )
                    mapping["readiness"] = "planning_gap"
                    continue
                try:
                    binder_executor.validate_run_bindings(
                        validated_registry,
                        adapter["id"],
                        config["bindings"],
                        runtime_root=Path("/") / "runtime",
                    )
                except binder_executor.BinderExecutorError:
                    gaps.append(
                        _gap(
                            "adapter-bindings-required",
                            selector,
                            route,
                            "The stage settings do not satisfy the adapter binding contract.",
                            [
                                {
                                    "id": "supply-bindings",
                                    "description": "Supply every required typed binding for this selector.",
                                },
                                {
                                    "id": "inspect-adapter",
                                    "description": "Inspect the selected adapter's placeholders and expected outputs.",
                                },
                            ],
                        )
                    )
                    mapping["readiness"] = "planning_gap"
                    continue
                stage_id = _stage_id(sequence, selector)
                dependencies = (
                    [prior_by_toolchain[toolchain_id]]
                    if toolchain_id in prior_by_toolchain
                    else []
                )
                input_handoffs: list[dict[str, str]] = []
                for handoff in config["input_handoffs"]:
                    source_stage_id = stage_id_by_selector.get(handoff["source_selector"])
                    if source_stage_id is None:
                        raise BinderExecutionPreparationError(
                            f"stage setting {selector} input handoff must name an earlier "
                            "runnable selector"
                        )
                    if source_stage_id not in dependencies:
                        dependencies.append(source_stage_id)
                    input_handoffs.append(
                        {
                            "source_stage_id": source_stage_id,
                            "source_output_id": handoff["source_output_id"],
                            "destination_binding": handoff["destination_binding"],
                        }
                    )
                stage_rows.append(
                    {
                        "stage_id": stage_id,
                        "toolchain_id": toolchain_id,
                        "stage": stage,
                        "tool_id": tool_id,
                        "variant_id": selection.get("variant_id"),
                        "route": {
                            "id": route["id"],
                            "backend": route["backend"],
                            "execution_method": route["execution_method"],
                        },
                        "adapter_id": adapter["id"],
                        "depends_on": dependencies,
                        "bindings": config["bindings"],
                        "input_handoffs": input_handoffs,
                        "estimated_cost_usd": config["estimated_cost_usd"],
                        "timeout_seconds": config["timeout_seconds"],
                    }
                )
                prior_by_toolchain[toolchain_id] = stage_id
                stage_id_by_selector[selector] = stage_id

    unknown_settings = sorted(set(settings) - used_settings)
    if unknown_settings:
        raise BinderExecutionPreparationError(
            "stage settings contain selectors outside the selected plan stages"
        )
    policy = normalized_plan["optimization_policy"]
    spend_ceiling = policy["round_budget_usd"][policy["current_round_index"] - 1]
    if spend_ceiling is None:
        gaps.append(
            {
                "gap_id": "round-budget-required",
                "selector": None,
                "toolchain_id": None,
                "stage": None,
                "tool_id": None,
                "route_id": None,
                "reason": "The local controller requires a numeric spend ceiling for this round.",
                "next_actions": [
                    {
                        "id": "set-round-budget",
                        "description": "Set a numeric round budget in the plan before preparing execution.",
                    }
                ],
            }
        )
    estimated_cost = sum(row["estimated_cost_usd"] for row in stage_rows)
    if spend_ceiling is not None and estimated_cost > spend_ceiling + 1e-9:
        gaps.append(
            {
                "gap_id": "stage-estimate-exceeds-budget",
                "selector": None,
                "toolchain_id": None,
                "stage": None,
                "tool_id": None,
                "route_id": None,
                "reason": "The selected stage estimates exceed this round's spend ceiling.",
                "next_actions": [
                    {
                        "id": "reduce-stage-cost",
                        "description": "Reduce selected work or choose routes that fit the existing ceiling.",
                    },
                    {
                        "id": "revise-budget",
                        "description": "Revise the round budget only with the user's bounded approval.",
                    },
                ],
            }
        )

    request: dict[str, Any] | None = None
    if not gaps and stage_rows and spend_ceiling is not None:
        request = {
            "schema_version": binder_controller.CONTROLLER_SCHEMA,
            "controller_id": (
                f"{normalized_plan['round_id']}-r{policy['current_round_index']}"[:96]
                .rstrip("-.")
            ),
            "plan_sha256": plan_sha256,
            "target_verification_sha256": target_report_sha256,
            "result_boundary": normalized_plan["result_boundary"],
            "target_verification": target,
            "workflow_strategy": normalized_plan["workflow_strategy"],
            "round_context": {
                "current_round_index": policy["current_round_index"],
                "maximum_round_count": policy["round_count"],
                "primary_metric_id": policy["primary_metric_id"],
                "direction": policy["direction"],
                "selected_stages": chosen_stages,
            },
            "budget": {"currency": "USD", "spend_ceiling_usd": float(spend_ceiling)},
            "stages": stage_rows,
        }
        binder_controller.validate_controller(request, validated_registry)

    status = (
        "ready"
        if request is not None
        else "ready_without_controller"
        if not gaps
        else "planning_with_readiness_gaps"
    )
    result = {
        "schema_version": PREPARATION_SCHEMA,
        "ok": True,
        "status": status,
        "plan_sha256": plan_sha256,
        "target_verification_sha256": target_report_sha256,
        "selected_stages": chosen_stages,
        "workflow_strategy": normalized_plan["workflow_strategy"],
        "round_context": {
            "current_round_index": policy["current_round_index"],
            "maximum_round_count": policy["round_count"],
            "primary_metric_id": policy["primary_metric_id"],
            "direction": policy["direction"],
            "spend_ceiling_usd": spend_ceiling,
        },
        "stage_mapping_count": len(mappings),
        "controller_stage_count": len(stage_rows),
        "platform_skill_stage_count": sum(
            row.get("readiness") == "platform_skill_handoff" for row in mappings
        ),
        "stage_mappings": mappings,
        "readiness_gaps": gaps,
        "provider_calls": 0,
    }
    return result, request
