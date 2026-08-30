from __future__ import annotations

import copy
import io
import json
import os
import tempfile
import unittest
from contextlib import redirect_stdout
from pathlib import Path

from biosymphony_structure_factory import (
    binder_controller,
    binder_execution_prep,
    binder_lane,
    binder_target,
    target_verifier,
)
from biosymphony_structure_factory.cli import main


ROOT = Path(__file__).resolve().parents[1]
REQUEST_REF = "examples/pd-l1-binder-design-public/binder-round-request.json"
LEDGER_REF = "references/binder-lane-capability-ledger.json"
REGISTRY_REF = "references/binder-execution-adapters.json"


def plan() -> dict:
    return binder_lane.plan_request(
        json.loads((ROOT / REQUEST_REF).read_text(encoding="utf-8")),
        json.loads((ROOT / LEDGER_REF).read_text(encoding="utf-8")),
        ROOT,
        request_ref=REQUEST_REF,
        ledger_ref=LEDGER_REF,
    )


def local_cofold_plan() -> dict:
    request = json.loads((ROOT / REQUEST_REF).read_text(encoding="utf-8"))
    route = next(row for row in request["execution_policy"]["routes"] if row["backend"] == "api")
    route.update(
        {
            "id": "cofold-locally",
            "backend": "local",
            "execution_method": "self_hosted",
            "profile_ref": "modules/provider-profiles/local/workstation-no-download.v1.json",
            "operator_adapter_required": False,
        }
    )
    del route["adapter_contract_ref"]
    del route["api_policy"]
    return binder_lane.plan_request(
        request,
        json.loads((ROOT / LEDGER_REF).read_text(encoding="utf-8")),
        ROOT,
        request_ref=REQUEST_REF,
        ledger_ref=LEDGER_REF,
    )


def target_report(
    plan_payload: dict | None = None,
    plan_sha256: str = "c" * 64,
) -> dict:
    target = (plan_payload or plan())["target"]
    site_count = binder_target.required_residue_count(
        target["site"]["required_residues"], "test target site"
    )
    return {
        "ok": True,
        "schema_version": target_verifier.REPORT_SCHEMA,
        "plan_sha256": plan_sha256,
        "target_contract_sha256": binder_target.target_contract_sha256(target),
        "target_contract": target,
        "format": "pdb",
        "structure_sha256": "a" * 64,
        "chain_id": "A",
        "coordinate_residue_count": site_count,
        "first_coordinate_residue": "19",
        "last_coordinate_residue": "127" if site_count > 3 else "21",
        "required_residue_count": site_count,
        "required_residues_verified": True,
        "sequence_basis": "coordinates",
        "sequence_length": site_count,
        "sequence_sha256": "b" * 64,
        "sequence_verified": True,
        "provider_calls": 0,
    }


def filter_settings() -> dict:
    result = {}
    for toolchain_id in ("diffusion-mpnn", "all-atom-mpnn", "integrated-design"):
        result[f"{toolchain_id}.filter.status-preserving-filter"] = {
            "bindings": {
                "run_root": ".",
                "input_path": "inputs/candidates.jsonl",
                "output_path": "outputs/status.jsonl",
                "metric": "metrics.cofold_confidence_proxy",
                "minimum": 0,
                "maximum": 1,
            }
        }
        result[f"{toolchain_id}.filter.diversity-filter"] = {
            "bindings": {
                "run_root": ".",
                "input_path": "inputs/status.jsonl",
                "output_path": "outputs/diverse.jsonl",
                "sequence_field": "sequence",
                "maximum_similarity": 0.8,
            }
        }
    return result


class BinderExecutionPreparationTests(unittest.TestCase):
    def setUp(self) -> None:
        self.plan = plan()
        self.registry = json.loads((ROOT / REGISTRY_REF).read_text(encoding="utf-8"))

    def test_partial_filter_subset_builds_hash_bound_controller_request(self) -> None:
        result, request = binder_execution_prep.prepare_execution(
            self.plan,
            target_report(),
            self.registry,
            plan_sha256="c" * 64,
            target_report_sha256="d" * 64,
            selected_stages=["filter"],
            stage_settings=filter_settings(),
        )
        self.assertEqual("ready", result["status"])
        self.assertEqual([], result["readiness_gaps"])
        self.assertIsNotNone(request)
        assert request is not None
        self.assertEqual("d" * 64, request["target_verification_sha256"])
        self.assertEqual(self.plan["workflow_strategy"], request["workflow_strategy"])
        self.assertEqual("cofold_confidence_proxy", request["round_context"]["primary_metric_id"])
        self.assertEqual(6, len(request["stages"]))
        self.assertTrue(all(row["route"]["backend"] == "local" for row in request["stages"]))
        binder_controller.validate_controller(request, self.registry)
        try:
            from jsonschema import Draft202012Validator
        except ImportError:
            return
        schema = json.loads(
            (ROOT / "schemas" / "binder-controller-request.schema.json").read_text(
                encoding="utf-8"
            )
        )
        Draft202012Validator.check_schema(schema)
        Draft202012Validator(schema).validate(request)

    def test_rejects_target_report_from_another_plan_or_site(self) -> None:
        wrong_plan = target_report(self.plan, "e" * 64)
        with self.assertRaisesRegex(
            binder_execution_prep.BinderExecutionPreparationError,
            "belongs to another plan",
        ):
            binder_execution_prep.prepare_execution(
                self.plan,
                wrong_plan,
                self.registry,
                plan_sha256="c" * 64,
                target_report_sha256="d" * 64,
                selected_stages=["filter"],
                stage_settings=filter_settings(),
            )

        wrong_site = target_report(self.plan)
        wrong_site["target_contract"] = copy.deepcopy(self.plan["target"])
        wrong_site["target_contract"]["site"]["required_residues"] = ["20-128"]
        wrong_site["target_contract_sha256"] = binder_target.target_contract_sha256(
            wrong_site["target_contract"]
        )
        with self.assertRaisesRegex(
            binder_execution_prep.BinderExecutionPreparationError,
            "belongs to another target or site",
        ):
            binder_execution_prep.prepare_execution(
                self.plan,
                wrong_site,
                self.registry,
                plan_sha256="c" * 64,
                target_report_sha256="d" * 64,
                selected_stages=["filter"],
                stage_settings=filter_settings(),
            )

    def test_v1_target_report_has_an_actionable_migration_error(self) -> None:
        legacy = target_report(self.plan)
        legacy["schema_version"] = "structure-factory-target-verification-v1"
        with self.assertRaisesRegex(
            binder_execution_prep.BinderExecutionPreparationError,
            "rerun target-check with --plan",
        ):
            binder_execution_prep.prepare_execution(
                self.plan,
                legacy,
                self.registry,
                plan_sha256="c" * 64,
                target_report_sha256="d" * 64,
                selected_stages=["filter"],
                stage_settings=filter_settings(),
            )

    def test_canonical_workflow_strategy_modes_prepare_and_validate(self) -> None:
        toolchain_ids = [row["id"] for row in self.plan["toolchains"]]
        strategies = {
            "published_shape_replay": {
                "mode": "published_shape_replay",
                "reference_scope": "published_workflow_shape",
                "replay_toolchain_ids": toolchain_ids,
                "swap_toolchain_ids": [],
            },
            "deliberate_tool_swap": {
                "mode": "deliberate_tool_swap",
                "reference_scope": "published_workflow_shape",
                "replay_toolchain_ids": [],
                "swap_toolchain_ids": toolchain_ids,
            },
            "replay_and_swap": {
                "mode": "replay_and_swap",
                "reference_scope": "published_workflow_shape",
                "replay_toolchain_ids": toolchain_ids[:1],
                "swap_toolchain_ids": toolchain_ids[1:],
            },
            "independent": {
                "mode": "independent",
                "reference_scope": None,
                "replay_toolchain_ids": [],
                "swap_toolchain_ids": [],
            },
        }
        schema = json.loads(
            (ROOT / "schemas" / "binder-controller-request.schema.json").read_text(
                encoding="utf-8"
            )
        )
        try:
            from jsonschema import Draft202012Validator
        except ImportError:
            Draft202012Validator = None
        if Draft202012Validator is not None:
            Draft202012Validator.check_schema(schema)
            schema_validator = Draft202012Validator(schema)

        for mode, strategy in strategies.items():
            with self.subTest(mode=mode):
                changed_plan = copy.deepcopy(self.plan)
                changed_plan["workflow_strategy"] = strategy
                result, request = binder_execution_prep.prepare_execution(
                    changed_plan,
                    target_report(),
                    self.registry,
                    plan_sha256="c" * 64,
                    target_report_sha256="d" * 64,
                    selected_stages=["filter"],
                    stage_settings=filter_settings(),
                )
                self.assertEqual("ready", result["status"])
                self.assertIsNotNone(request)
                assert request is not None
                self.assertEqual(strategy, request["workflow_strategy"])
                binder_controller.validate_controller(request, self.registry)
                if Draft202012Validator is not None:
                    schema_validator.validate(request)

    def test_controller_rejects_inconsistent_workflow_strategy_classifications(self) -> None:
        _, request = binder_execution_prep.prepare_execution(
            self.plan,
            target_report(),
            self.registry,
            plan_sha256="c" * 64,
            target_report_sha256="d" * 64,
            selected_stages=["filter"],
            stage_settings=filter_settings(),
        )
        assert request is not None
        toolchain_ids = [row["id"] for row in self.plan["toolchains"]]
        invalid_strategies = {
            "obsolete_mode": {
                "mode": "replay",
                "reference_scope": "published_workflow_shape",
                "replay_toolchain_ids": toolchain_ids[:1],
                "swap_toolchain_ids": toolchain_ids[1:],
            },
            "partial_shape_replay": {
                "mode": "published_shape_replay",
                "reference_scope": "published_workflow_shape",
                "replay_toolchain_ids": toolchain_ids[:1],
                "swap_toolchain_ids": [],
            },
            "partial_tool_swap": {
                "mode": "deliberate_tool_swap",
                "reference_scope": "published_workflow_shape",
                "replay_toolchain_ids": [],
                "swap_toolchain_ids": toolchain_ids[:1],
            },
            "replay_without_swap": {
                "mode": "replay_and_swap",
                "reference_scope": "published_workflow_shape",
                "replay_toolchain_ids": toolchain_ids,
                "swap_toolchain_ids": [],
            },
            "independent_with_reference": {
                "mode": "independent",
                "reference_scope": "published_workflow_shape",
                "replay_toolchain_ids": [],
                "swap_toolchain_ids": [],
            },
            "independent_with_classification": {
                "mode": "independent",
                "reference_scope": None,
                "replay_toolchain_ids": toolchain_ids[:1],
                "swap_toolchain_ids": [],
            },
        }
        for name, strategy in invalid_strategies.items():
            with self.subTest(name=name):
                invalid_request = copy.deepcopy(request)
                invalid_request["workflow_strategy"] = strategy
                with self.assertRaises(binder_controller.BinderControllerError):
                    binder_controller.validate_controller(invalid_request, self.registry)

    def test_prepared_request_writes_schema_valid_controller_receipt(self) -> None:
        _, request = binder_execution_prep.prepare_execution(
            self.plan,
            target_report(),
            self.registry,
            plan_sha256="c" * 64,
            target_report_sha256="d" * 64,
            selected_stages=["filter"],
            stage_settings=filter_settings(),
        )
        assert request is not None
        with tempfile.TemporaryDirectory() as temporary:
            workspace = Path(temporary)
            bin_dir = workspace / "bin"
            bin_dir.mkdir()
            for program in ("bsf-status-filter", "bsf-diversity-filter"):
                path = bin_dir / program
                path.write_text("#!/bin/sh\nexit 0\n", encoding="utf-8")
                path.chmod(0o755)
            original_path = os.environ.get("PATH", "")
            os.environ["PATH"] = f"{bin_dir}{os.pathsep}{original_path}"
            try:
                result = binder_controller.run_controller(
                    request,
                    self.registry,
                    workspace_root=workspace,
                    runtime_root=workspace / ".runtime" / "controller",
                    plan_sha256="c" * 64,
                    authorization=None,
                    dry_run=True,
                )
            finally:
                os.environ["PATH"] = original_path
            self.assertEqual("planned", result["status"])
            receipt = json.loads((workspace / result["receipt_path"]).read_text(encoding="utf-8"))
            try:
                from jsonschema import Draft202012Validator
            except ImportError:
                return
            schema = json.loads(
                (ROOT / "schemas" / "binder-controller-receipt.schema.json").read_text(
                    encoding="utf-8"
                )
            )
            Draft202012Validator.check_schema(schema)
            Draft202012Validator(schema).validate(receipt)

    def test_missing_bindings_are_planning_gaps_not_global_failure(self) -> None:
        result, request = binder_execution_prep.prepare_execution(
            self.plan,
            target_report(),
            self.registry,
            plan_sha256="c" * 64,
            target_report_sha256="d" * 64,
            selected_stages=["filter"],
        )
        self.assertTrue(result["ok"])
        self.assertEqual("planning_with_readiness_gaps", result["status"])
        self.assertIsNone(request)
        self.assertEqual(
            {"adapter-bindings-required"},
            {gap["gap_id"] for gap in result["readiness_gaps"]},
        )
        self.assertTrue(all(len(gap["next_actions"]) >= 2 for gap in result["readiness_gaps"]))

    def test_remote_route_requires_explicit_client_and_preserves_route(self) -> None:
        changed = json.loads(json.dumps(self.plan))
        for toolchain in changed["toolchains"]:
            toolchain["predictors"] = [{"tool_id": "boltz"}]
        settings = {
            f"{toolchain}.cofold.boltz": {
                "adapter_id": "boltz-local-v1",
                "bindings": {"input_path": "inputs/complex.yaml", "output_dir": "outputs"},
            }
            for toolchain in ("diffusion-mpnn", "all-atom-mpnn", "integrated-design")
        }
        result, request = binder_execution_prep.prepare_execution(
            changed,
            target_report(),
            self.registry,
            plan_sha256="c" * 64,
            target_report_sha256="d" * 64,
            selected_stages=["cofold"],
            stage_settings=settings,
        )
        self.assertIsNone(request)
        boltz = [row for row in result["stage_mappings"] if row["tool_id"] == "boltz"]
        self.assertTrue(boltz)
        self.assertTrue(all(row["backend"] == "api" for row in boltz))
        self.assertEqual({"adapter-route-mismatch"}, {gap["gap_id"] for gap in result["readiness_gaps"]})

    def test_runtime_api_client_can_match_an_api_route(self) -> None:
        changed = json.loads(json.dumps(self.plan))
        for toolchain in changed["toolchains"]:
            toolchain["predictors"] = [{"tool_id": "boltz"}]
        registry = json.loads(json.dumps(self.registry))
        adapter = next(row for row in registry["adapters"] if row["id"] == "boltz-local-v1")
        adapter["id"] = "boltz-api-client-v1"
        adapter["program"] = "boltz-api-client"
        adapter["readiness_argv"] = ["boltz-api-client", "--help"]
        adapter["command_argv"] = [
            "boltz-api-client",
            "predict",
            "{{input_path}}",
            "--out-dir",
            "{{output_dir}}",
        ]
        adapter["supported_routes"] = [{"backend": "api", "execution_method": "hosted_api"}]
        settings = {
            f"{toolchain}.cofold.boltz": {
                "adapter_id": "boltz-api-client-v1",
                "bindings": {"input_path": "inputs/complex.yaml", "output_dir": "outputs"},
            }
            for toolchain in ("diffusion-mpnn", "all-atom-mpnn", "integrated-design")
        }
        result, request = binder_execution_prep.prepare_execution(
            changed,
            target_report(),
            registry,
            plan_sha256="c" * 64,
            target_report_sha256="d" * 64,
            selected_stages=["cofold"],
            stage_settings=settings,
        )
        self.assertEqual("ready", result["status"])
        self.assertIsNotNone(request)
        assert request is not None
        self.assertTrue(
            all(stage["adapter_id"] == "boltz-api-client-v1" for stage in request["stages"])
        )

    def test_local_esmfold2_adapter_reports_a_route_gap_for_api_execution(self) -> None:
        changed = json.loads(json.dumps(self.plan))
        for toolchain in changed["toolchains"]:
            toolchain["predictors"] = [{"tool_id": "esmfold2"}]
        settings = {
            f"{toolchain}.cofold.esmfold2": {
                "adapter_id": "esmfold2-local-adapter-v1",
                "bindings": {
                    "run_root": "run",
                    "input_path": "inputs/complex.yaml",
                    "output_path": "outputs/predictions.jsonl",
                    "artifact_dir": "outputs/artifacts",
                    "seed": 0,
                    "expected_count": 1,
                },
            }
            for toolchain in ("diffusion-mpnn", "all-atom-mpnn", "integrated-design")
        }
        result, request = binder_execution_prep.prepare_execution(
            changed,
            target_report(),
            self.registry,
            plan_sha256="c" * 64,
            target_report_sha256="d" * 64,
            selected_stages=["cofold"],
            stage_settings=settings,
        )
        self.assertIsNone(request)
        self.assertEqual({"adapter-route-mismatch"}, {gap["gap_id"] for gap in result["readiness_gaps"]})

    def test_esmfold2_full_and_fast_variants_select_their_matching_local_adapters(self) -> None:
        changed = local_cofold_plan()
        for toolchain in changed["toolchains"]:
            toolchain["predictors"] = [
                {"tool_id": "esmfold2", "variant_id": "esmfold2-full"},
                {"tool_id": "esmfold2", "variant_id": "esmfold2-fast"},
            ]
        bindings = {
            "run_root": "run",
            "input_path": "inputs/complex.yaml",
            "output_path": "outputs/predictions.jsonl",
            "artifact_dir": "outputs/artifacts",
            "seed": 0,
            "expected_count": 1,
        }
        settings = {
            f"{toolchain}.cofold.esmfold2@{variant_id}": {
                "adapter_id": adapter_id,
                "bindings": bindings,
            }
            for toolchain in ("diffusion-mpnn", "all-atom-mpnn", "integrated-design")
            for variant_id, adapter_id in (
                ("esmfold2-full", "esmfold2-local-adapter-v1"),
                ("esmfold2-fast", "esmfold2-fast-adapter-v1"),
            )
        }
        result, request = binder_execution_prep.prepare_execution(
            changed,
            target_report(),
            self.registry,
            plan_sha256="c" * 64,
            target_report_sha256="d" * 64,
            selected_stages=["cofold"],
            stage_settings=settings,
        )
        self.assertEqual("ready", result["status"])
        self.assertIsNotNone(request)
        assert request is not None
        adapters_by_variant = {
            stage["variant_id"]: stage["adapter_id"] for stage in request["stages"]
        }
        self.assertEqual("esmfold2-local-adapter-v1", adapters_by_variant["esmfold2-full"])
        self.assertEqual("esmfold2-fast-adapter-v1", adapters_by_variant["esmfold2-fast"])

    def test_esmfold2_without_a_variant_selects_the_full_local_adapter(self) -> None:
        changed = local_cofold_plan()
        for toolchain in changed["toolchains"]:
            toolchain["predictors"] = [{"tool_id": "esmfold2"}]
        settings = {
            f"{toolchain}.cofold.esmfold2": {
                "adapter_id": "esmfold2-local-adapter-v1",
                "bindings": {
                    "run_root": "run",
                    "input_path": "inputs/complex.yaml",
                    "output_path": "outputs/predictions.jsonl",
                    "artifact_dir": "outputs/artifacts",
                    "seed": 0,
                    "expected_count": 1,
                },
            }
            for toolchain in ("diffusion-mpnn", "all-atom-mpnn", "integrated-design")
        }
        result, request = binder_execution_prep.prepare_execution(
            changed,
            target_report(),
            self.registry,
            plan_sha256="c" * 64,
            target_report_sha256="d" * 64,
            selected_stages=["cofold"],
            stage_settings=settings,
        )
        self.assertEqual("ready", result["status"])
        self.assertIsNotNone(request)
        assert request is not None
        self.assertTrue(
            all(stage["adapter_id"] == "esmfold2-local-adapter-v1" for stage in request["stages"])
        )

    def test_platform_skill_route_needs_no_local_adapter(self) -> None:
        changed = json.loads(json.dumps(self.plan))
        local_route = next(
            route
            for route in changed["execution_policy"]["routes"]
            if route["backend"] == "local"
        )
        local_route["execution_method"] = "platform_skill"
        local_route["platform_skill_id"] = "local-binder-skill"
        result, request = binder_execution_prep.prepare_execution(
            changed,
            target_report(),
            self.registry,
            plan_sha256="c" * 64,
            target_report_sha256="d" * 64,
            selected_stages=["filter"],
        )
        self.assertIsNone(request)
        self.assertEqual("ready_without_controller", result["status"])
        self.assertEqual([], result["readiness_gaps"])
        self.assertEqual(6, result["platform_skill_stage_count"])


class BinderExecutionPreparationCliTests(unittest.TestCase):
    def test_cli_writes_ready_request_and_readiness_result_below_runtime(self) -> None:
        (ROOT / ".runtime").mkdir(exist_ok=True)
        with tempfile.TemporaryDirectory(dir=ROOT / ".runtime") as temporary:
            runtime = Path(temporary)
            plan_path = runtime / "plan.json"
            target_path = runtime / "target.json"
            settings_path = runtime / "settings.json"
            request_path = runtime / "controller-request.json"
            readiness_path = runtime / "readiness.json"
            plan_payload = plan()
            binder_lane.write_json(plan_path, plan_payload)
            binder_lane.write_json(
                target_path,
                target_report(plan_payload, binder_lane.sha256_path(plan_path)),
            )
            binder_lane.write_json(settings_path, filter_settings())
            output = io.StringIO()
            with redirect_stdout(output):
                status = main(
                    [
                        "binder-lane",
                        "prepare-execution",
                        plan_path.relative_to(ROOT).as_posix(),
                        "--workspace",
                        str(ROOT),
                        "--target-report",
                        target_path.relative_to(ROOT).as_posix(),
                        "--stage-settings",
                        settings_path.relative_to(ROOT).as_posix(),
                        "--stages",
                        "filter",
                        "--out",
                        request_path.relative_to(ROOT).as_posix(),
                        "--readiness-out",
                        readiness_path.relative_to(ROOT).as_posix(),
                    ]
                )
            payload = json.loads(output.getvalue())
            self.assertEqual(0, status, payload)
            self.assertEqual("ready", payload["status"])
            self.assertTrue(request_path.is_file())
            self.assertTrue(readiness_path.is_file())
            stored = json.loads(request_path.read_text(encoding="utf-8"))
            self.assertEqual(binder_lane.sha256_path(plan_path), stored["plan_sha256"])
            self.assertEqual(
                binder_lane.sha256_path(target_path),
                stored["target_verification_sha256"],
            )

    def test_controller_schema_mirrors_match(self) -> None:
        for name in (
            "binder-controller-request.schema.json",
            "binder-controller-receipt.schema.json",
        ):
            canonical = (ROOT / "schemas" / name).read_bytes()
            for mirror in (
                ROOT / "skills" / "binder-lane-round" / "references" / "schemas" / name,
                ROOT
                / "skills"
                / "biosymphony-structure-factory"
                / "references"
                / "schemas"
                / name,
            ):
                self.assertEqual(canonical, mirror.read_bytes(), str(mirror))


if __name__ == "__main__":
    unittest.main()
