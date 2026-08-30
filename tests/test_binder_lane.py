from __future__ import annotations

import copy
import inspect
import json
import os
import tempfile
import unittest
from pathlib import Path

from biosymphony_structure_factory import binder_lane
from biosymphony_structure_factory.cli import main


ROOT = Path(__file__).resolve().parents[1]
LEDGER_PATH = ROOT / "references" / "binder-lane-capability-ledger.json"
REQUEST_PATH = ROOT / "examples" / "pd-l1-binder-design-public" / "binder-round-request.json"
FIXTURE_PATH = ROOT / "examples" / "pd-l1-binder-design-public" / "candidate-ranking.example.json"


class BinderLaneTests(unittest.TestCase):
    def ledger(self) -> dict:
        return json.loads(LEDGER_PATH.read_text(encoding="utf-8"))

    def request(self) -> dict:
        return json.loads(REQUEST_PATH.read_text(encoding="utf-8"))

    def fixture(self) -> dict:
        return json.loads(FIXTURE_PATH.read_text(encoding="utf-8"))

    def plan(self) -> dict:
        return binder_lane.plan_request(
            self.request(),
            self.ledger(),
            ROOT,
            request_ref=REQUEST_PATH.relative_to(ROOT).as_posix(),
            ledger_ref=LEDGER_PATH.relative_to(ROOT).as_posix(),
        )

    def test_menu_separates_public_evidence_from_runtime_availability(self) -> None:
        result = binder_lane.menu(self.ledger(), ROOT)
        self.assertTrue(result["planning_available"])
        self.assertTrue(result["direct_launch_available"])
        boltz = next(item for item in result["roles"]["predictor"] if item["id"] == "boltz")
        self.assertTrue(boltz["bundled_execution_available"])
        rows = [row for tools in result["roles"].values() for row in tools]
        self.assertTrue(rows)
        self.assertTrue(all(row["planning_selectable"] is True for row in rows))
        self.assertTrue(all(row["runtime_status"] == "not_checked" for row in rows))
        self.assertTrue(any(profile["provider"] == "neocloud" for profile in result["provider_profiles"]))
        self.assertTrue(any(profile["provider"] == "api" for profile in result["provider_profiles"]))
        route_identities = {
            (row["backend"], row["execution_method"])
            for row in result["route_contracts"]
        }
        expected_identities = {
            (backend, execution_method)
            for backend, execution_methods in binder_lane.ROUTE_EXECUTION_METHODS_BY_BACKEND.items()
            for execution_method in execution_methods
        }
        self.assertEqual(expected_identities, route_identities)
        self.assertEqual(len(result["route_contracts"]), len(route_identities))
        self.assertIn(("local", "self_hosted"), route_identities)
        self.assertIn(("api", "hosted_api"), route_identities)
        self.assertNotIn(("local", "hosted_api"), route_identities)
        self.assertNotIn(("api", "self_hosted"), route_identities)
        platform_skill = next(
            row
            for row in result["route_contracts"]
            if row["backend"] == "fal" and row["execution_method"] == "platform_skill"
        )
        self.assertTrue(platform_skill["platform_skill_id_required"])
        self.assertFalse(platform_skill["adapter_route_declaration_required"])
        self.assertEqual(
            ["modules/provider-profiles/fal/serverless-gpu-no-download.v1.json"],
            platform_skill["profile_refs"],
        )
        local = next(profile for profile in result["provider_profiles"] if profile["provider"] == "local")
        self.assertFalse(local["operator_gate_required"])
        self.assertTrue(
            all(profile["operator_gate_required"] for profile in result["provider_profiles"] if profile["provider"] != "local")
        )
        self.assertNotIn("served", json.dumps(result).lower())

    def test_full_synthetic_round_has_counts_markers_and_hashes(self) -> None:
        plan = self.plan()
        (ROOT / ".runtime").mkdir(exist_ok=True)
        with tempfile.TemporaryDirectory(dir=ROOT / ".runtime") as tmp:
            workspace = ROOT
            run_root = Path(tmp) / "round"
            binder_lane.materialize_plan(plan, run_root, workspace)
            self.assertTrue(binder_lane.preflight(run_root, workspace)["ok"])
            report = binder_lane.run_synthetic(run_root, workspace)
            summary = binder_lane.report_summary(run_root, workspace)

            self.assertEqual(0, report["execution"]["provider_calls"])
            self.assertEqual("synthetic_fixture", report["construction"]["mode"])
            self.assertTrue(report["construction"]["not_a_measurement"])
            self.assertEqual(len(self.fixture()["candidates"]), report["candidate_count"])
            self.assertEqual(
                [arm["id"] for arm in plan["toolchains"]],
                [arm["id"] for arm in report["toolchains"]],
            )
            self.assertTrue(summary["ok"], summary)
            contract = json.loads((run_root / "round-contract.json").read_text())
            expected = {
                item
                for stage in contract["stages"]
                for item in stage["expected_artifacts"]
            }
            hashes = json.loads((run_root / "artifact-hashes.json").read_text())
            self.assertEqual(expected, {row["path"] for row in hashes["artifacts"]})
            for row in hashes["artifacts"]:
                self.assertFalse(Path(row["path"]).is_absolute())

    def test_report_fails_hash_check_after_tampering(self) -> None:
        plan = self.plan()
        (ROOT / ".runtime").mkdir(exist_ok=True)
        with tempfile.TemporaryDirectory(dir=ROOT / ".runtime") as tmp:
            workspace = ROOT
            run_root = Path(tmp) / "round"
            binder_lane.materialize_plan(plan, run_root, workspace)
            binder_lane.run_synthetic(run_root, workspace)
            report_path = run_root / "round-report.json"
            report_path.write_text(report_path.read_text() + " ", encoding="utf-8")
            summary = binder_lane.report_summary(run_root, workspace)
            self.assertFalse(summary["ok"])
            self.assertIn("round-report.json", summary["hash_mismatches"])

    def test_hash_ledger_must_cover_every_expected_artifact(self) -> None:
        plan = self.plan()
        (ROOT / ".runtime").mkdir(exist_ok=True)
        with tempfile.TemporaryDirectory(dir=ROOT / ".runtime") as tmp:
            workspace = ROOT
            run_root = Path(tmp) / "round"
            binder_lane.materialize_plan(plan, run_root, workspace)
            binder_lane.run_synthetic(run_root, workspace)
            ledger_path = run_root / "artifact-hashes.json"
            ledger = json.loads(ledger_path.read_text())
            ledger["artifacts"].pop()
            ledger_path.write_text(json.dumps(ledger), encoding="utf-8")
            summary = binder_lane.report_summary(run_root, workspace)
            self.assertFalse(summary["ok"])
            self.assertIn("hash_ledger_coverage", summary["hash_mismatches"])

    def test_preflight_rejects_corrupt_artifact_digest(self) -> None:
        plan = self.plan()
        (ROOT / ".runtime").mkdir(exist_ok=True)
        with tempfile.TemporaryDirectory(dir=ROOT / ".runtime") as tmp:
            run_root = Path(tmp) / "round"
            binder_lane.materialize_plan(plan, run_root, ROOT)
            binder_lane.run_synthetic(run_root, ROOT)
            ledger_path = run_root / "artifact-hashes.json"
            ledger = json.loads(ledger_path.read_text())
            ledger["artifacts"][0]["sha256"] = "0" * 64
            ledger_path.write_text(json.dumps(ledger), encoding="utf-8")
            self.assertFalse(binder_lane.preflight(run_root, ROOT)["ok"])

    def test_public_documents_reject_sensitive_and_sequence_fields(self) -> None:
        for key, value in [
            ("sequence", "EXAMPLE"),
            ("api_key", "redacted"),
            ("provider_id", "example"),
            ("internal_note", "example"),
        ]:
            with self.subTest(key=key):
                request = self.request()
                request[key] = value
                with self.assertRaises(binder_lane.BinderLaneError):
                    binder_lane.plan_request(request, self.ledger())

    def test_target_site_is_required_and_normalized(self) -> None:
        missing_site = self.request()
        del missing_site["target"]["site"]
        with self.assertRaisesRegex(
            binder_lane.BinderLaneError,
            "add site.chain_id and site.required_residues",
        ):
            binder_lane.plan_request(missing_site, self.ledger(), ROOT)

        noncontiguous = self.request()
        noncontiguous["target"]["site"]["required_residues"] = ["130a", "19-21"]
        plan = binder_lane.plan_request(noncontiguous, self.ledger(), ROOT)
        self.assertEqual(
            ["19-21", "130A"],
            plan["target"]["site"]["required_residues"],
        )

    def test_paths_reject_escape_absolute_nul_backslash_root_and_file_url(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            for value in ["../escape", "/tmp/escape", "bad\x00path", "bad\\path", ".runtime", "file://example"]:
                with self.subTest(value=value), self.assertRaises(binder_lane.BinderLaneError):
                    binder_lane.runtime_path(root, value, "test path")

    @unittest.skipUnless(hasattr(os, "symlink"), "symlinks unavailable")
    def test_paths_reject_symlink_escape(self) -> None:
        with tempfile.TemporaryDirectory() as tmp, tempfile.TemporaryDirectory() as outside:
            root = Path(tmp)
            (root / ".runtime").mkdir()
            (root / ".runtime" / "link").symlink_to(Path(outside), target_is_directory=True)
            with self.assertRaises(binder_lane.BinderLaneError):
                binder_lane.runtime_path(root, ".runtime/link/result.json", "test path")

    def test_materialization_refuses_nonempty_run_root(self) -> None:
        plan = self.plan()
        (ROOT / ".runtime").mkdir(exist_ok=True)
        with tempfile.TemporaryDirectory(dir=ROOT / ".runtime") as tmp:
            run_root = Path(tmp) / "run"
            run_root.mkdir()
            (run_root / "existing.json").write_text("{}\n", encoding="utf-8")
            with self.assertRaises(binder_lane.BinderLaneError):
                binder_lane.materialize_plan(plan, run_root, ROOT)

    def test_lane_core_has_no_network_subprocess_or_environment_access(self) -> None:
        source = inspect.getsource(binder_lane)
        for forbidden in ["import subprocess", "import socket", "import requests", "import urllib", "os.environ"]:
            self.assertNotIn(forbidden, source)

    def test_cli_refuses_writes_outside_runtime(self) -> None:
        code = main(
            [
                "binder-lane",
                "plan-request",
                "examples/pd-l1-binder-design-public/binder-round-request.json",
                "--out",
                "docs/round-plan.json",
            ]
        )
        self.assertEqual(2, code)

    def test_unknown_role_binding_fails_closed(self) -> None:
        request = copy.deepcopy(self.request())
        request["toolchains"][0]["predictors"] = ["genie3"]
        with self.assertRaises(binder_lane.BinderLaneError):
            binder_lane.plan_request(request, self.ledger())

    def test_comparison_modes_control_full_stack_swaps(self) -> None:
        controlled = copy.deepcopy(self.request())
        controlled["toolchains"][1]["predictors"] = ["chai"]
        controlled["license_policy"]["allowed_gates"].append("verify_current_terms")
        with self.assertRaises(binder_lane.BinderLaneError):
            binder_lane.plan_request(controlled, self.ledger(), ROOT)

        exploratory = copy.deepcopy(controlled)
        exploratory["comparison_policy"]["mode"] = "exploratory_full_stack"
        exploratory["comparison_policy"]["cross_arm_ranking"] = "not_permitted"
        plan = binder_lane.plan_request(exploratory, self.ledger(), ROOT)
        self.assertEqual("exploratory_full_stack", plan["comparison_policy"]["mode"])
        self.assertEqual("chai", plan["toolchains"][1]["predictors"][0]["tool_id"])

    def test_nonpublished_study_templates_use_null_workflow(self) -> None:
        for template in ("toolchain-comparison", "custom"):
            with self.subTest(template=template):
                request = copy.deepcopy(self.request())
                request["study_template"] = template
                request["published_workflow"] = None
                request["workflow_strategy"] = {
                    "mode": "independent",
                    "reference_scope": None,
                    "replay_toolchain_ids": [],
                    "swap_toolchain_ids": [],
                }
                self.assertEqual(template, binder_lane.plan_request(request, self.ledger(), ROOT)["study_template"])

        request = copy.deepcopy(self.request())
        request["study_template"] = "single-arm-replay"
        request["published_workflow"] = None
        request["workflow_strategy"] = {
            "mode": "independent",
            "reference_scope": None,
            "replay_toolchain_ids": [],
            "swap_toolchain_ids": [],
        }
        request["toolchains"] = request["toolchains"][:1]
        for route in request["execution_policy"]["routes"]:
            route["toolchain_ids"] = [request["toolchains"][0]["id"]]
        plan = binder_lane.plan_request(request, self.ledger(), ROOT)
        self.assertEqual(1, len(plan["toolchains"]))

    def test_mixed_routes_preserve_api_contract_and_selected_tools(self) -> None:
        plan = self.plan()
        handoff = binder_lane.execution_handoff(plan, "0" * 64)
        api_packages = [package for package in handoff["packages"] if package["backend"] == "api"]
        self.assertTrue(api_packages)
        for package in api_packages:
            self.assertRegex(package["package_id"], r"^[a-z0-9._-]+$")
            self.assertEqual("templates/binder-api-adapter-contract.json", package["adapter_contract_ref"])
            self.assertRegex(package["adapter_contract_sha256"], r"^[0-9a-f]{64}$")
            self.assertTrue(all(package["tools_by_toolchain"].values()))
            self.assertTrue(package["api_policy"]["input_retention_review_required"])
            self.assertEqual("hosted_api", package["execution_method"])
            self.assertEqual("required_at_execution", package["authorization"])
            self.assertEqual("authorize_external_or_provider_dispatch", package["authorization_action"])
            self.assertEqual("not_executed", package["execution_state"])
            self.assertEqual("public_or_synthetic_only", package["transfer"]["data_class"])
            self.assertFalse(package["transfer"]["credentials_embedded"])
        self.assertTrue(any(not package["operator_gate_required"] for package in handoff["packages"] if package["backend"] == "local"))
        self.assertTrue(all(package["operator_gate_required"] for package in handoff["packages"] if package["backend"] != "local"))

    def test_optimization_policy_requires_a_metric_direction_counts_and_budget(self) -> None:
        plan = self.plan()
        self.assertEqual("cofold_confidence_proxy", plan["optimization_policy"]["primary_metric_id"])
        self.assertEqual("maximize", plan["optimization_policy"]["direction"])
        self.assertEqual([60], plan["optimization_policy"]["round_budget_usd"])
        self.assertEqual(6, sum(binder_lane._candidate_counts_per_round(plan).values()))

    def test_workflow_strategy_classifies_replay_and_swap_arms(self) -> None:
        plan = self.plan()
        self.assertEqual("replay_and_swap", plan["workflow_strategy"]["mode"])
        self.assertEqual(["diffusion-mpnn"], plan["workflow_strategy"]["replay_toolchain_ids"])
        self.assertEqual(
            ["all-atom-mpnn", "integrated-design"],
            plan["workflow_strategy"]["swap_toolchain_ids"],
        )

        request = copy.deepcopy(self.request())
        request["workflow_strategy"]["swap_toolchain_ids"] = ["all-atom-mpnn"]
        with self.assertRaises(binder_lane.BinderLaneError):
            binder_lane.plan_request(request, self.ledger(), ROOT)

    def test_partial_published_identity_scope_verifies_replay_and_swap_generators(self) -> None:
        request = copy.deepcopy(self.request())
        request["published_workflow"]["bounded_stage_ids"] = ["target", "generation"]
        request["workflow_strategy"]["reference_scope"] = "published_tool_identities"
        request["toolchains"][1]["generator"] = "rfantibody"
        request["toolchains"][2]["generator"] = "rfantibody"
        request["license_policy"]["allowed_gates"].append("weight_terms_review")

        plan = binder_lane.plan_request(request, self.ledger(), ROOT)
        self.assertEqual(["target", "generation"], plan["published_stage_ids"])
        self.assertEqual("published_tool_identities", plan["workflow_strategy"]["reference_scope"])

        wrong_replay = copy.deepcopy(request)
        wrong_replay["toolchains"][0]["generator"] = "rfantibody"
        with self.assertRaisesRegex(binder_lane.BinderLaneError, "generation"):
            binder_lane.plan_request(wrong_replay, self.ledger(), ROOT)

        wrong_swap = copy.deepcopy(request)
        wrong_swap["toolchains"][1]["generator"] = "genie3"
        wrong_swap["toolchains"][2]["generator"] = "boltzgen"
        with self.assertRaisesRegex(binder_lane.BinderLaneError, "swap toolchain"):
            binder_lane.plan_request(wrong_swap, self.ledger(), ROOT)

    def test_full_published_identity_replay_requires_recorded_variants(self) -> None:
        request = copy.deepcopy(self.request())
        request["workflow_strategy"] = {
            "mode": "published_shape_replay",
            "reference_scope": "published_tool_identities",
            "replay_toolchain_ids": [row["id"] for row in request["toolchains"]],
            "swap_toolchain_ids": [],
        }
        exact_predictors = [
            {"tool_id": "esmfold2", "variant_id": "esmfold2-fast"},
            {"tool_id": "esmfold2", "variant_id": "esmfold2-full"},
            {"tool_id": "protenix", "variant_id": "protenix-v2"},
        ]
        exact_scorers = [
            {"tool_id": "ipsae", "variant_id": "ipsae-min"},
            {"tool_id": "dockq-v2", "variant_id": "sc-dockq"},
        ]
        for toolchain in request["toolchains"]:
            toolchain["predictors"] = copy.deepcopy(exact_predictors)
            toolchain["scorers"] = copy.deepcopy(exact_scorers)

        plan = binder_lane.plan_request(request, self.ledger(), ROOT)
        self.assertEqual(
            ["esmfold2-fast", "esmfold2-full", "protenix-v2"],
            [row["variant_id"] for row in plan["toolchains"][0]["predictors"]],
        )
        handoff = binder_lane.execution_handoff(plan, "0" * 64)
        cofold = next(
            package
            for package in handoff["packages"]
            if package["stage"] == "cofold" and "diffusion-mpnn" in package["toolchain_ids"]
        )
        self.assertEqual(
            exact_predictors,
            cofold["tools_by_toolchain"]["diffusion-mpnn"],
        )

        for toolchain in request["toolchains"]:
            toolchain["predictors"][0]["variant_id"] = "unrecorded-variant"
        with self.assertRaisesRegex(binder_lane.BinderLaneError, "cofold"):
            binder_lane.plan_request(request, self.ledger(), ROOT)

    def test_execution_method_records_platform_skill_api_and_self_hosted_choices(self) -> None:
        request = copy.deepcopy(self.request())
        request["execution_policy"]["routes"][2]["execution_method"] = "platform_skill"
        request["execution_policy"]["routes"][2]["platform_skill_id"] = "platform-pack:local-binder"
        plan = binder_lane.plan_request(request, self.ledger(), ROOT)
        methods = {route["execution_method"] for route in plan["execution_policy"]["routes"]}
        self.assertEqual({"platform_skill", "hosted_api", "self_hosted"}, methods)
        handoff = binder_lane.execution_handoff(plan, "0" * 64)
        platform_packages = [
            package for package in handoff["packages"] if package["execution_method"] == "platform_skill"
        ]
        self.assertTrue(platform_packages)
        self.assertTrue(
            all(package["platform_skill_id"] == "platform-pack:local-binder" for package in platform_packages)
        )
        try:
            from jsonschema import Draft202012Validator
        except ImportError:
            pass
        else:
            request_schema = json.loads(
                (ROOT / "schemas/binder-round-request.schema.json").read_text(encoding="utf-8")
            )
            handoff_schema = json.loads(
                (ROOT / "modules/schemas/binder-execution-handoff.v1.schema.json").read_text(
                    encoding="utf-8"
                )
            )
            self.assertTrue(Draft202012Validator(request_schema).is_valid(request))
            self.assertTrue(Draft202012Validator(handoff_schema).is_valid(handoff))

        request["execution_policy"]["routes"][2]["execution_method"] = "unknown"
        del request["execution_policy"]["routes"][2]["platform_skill_id"]
        with self.assertRaises(binder_lane.BinderLaneError):
            binder_lane.plan_request(request, self.ledger(), ROOT)

    def test_platform_skill_route_requires_a_public_skill_id(self) -> None:
        request = copy.deepcopy(self.request())
        route = request["execution_policy"]["routes"][0]
        route["execution_method"] = "platform_skill"
        with self.assertRaisesRegex(binder_lane.BinderLaneError, "platform_skill_id"):
            binder_lane.plan_request(request, self.ledger(), ROOT)

    def test_route_matrix_rejects_impossible_local_and_api_pairs(self) -> None:
        local_request = copy.deepcopy(self.request())
        local_route = local_request["execution_policy"]["routes"][0]
        local_route["backend"] = "local"
        local_route["execution_method"] = "hosted_api"
        local_route["profile_ref"] = "modules/provider-profiles/local/workstation-no-download.v1.json"
        with self.assertRaisesRegex(binder_lane.BinderLaneError, "backend and execution_method"):
            binder_lane.plan_request(local_request, self.ledger(), ROOT)

        api_request = copy.deepcopy(self.request())
        api_request["execution_policy"]["routes"][1]["execution_method"] = "self_hosted"
        with self.assertRaisesRegex(binder_lane.BinderLaneError, "backend and execution_method"):
            binder_lane.plan_request(api_request, self.ledger(), ROOT)

    def test_round_horizon_keeps_current_round_output_contract_bounded(self) -> None:
        request = copy.deepcopy(self.request())
        request["optimization_policy"]["round_count"] = 3
        request["optimization_policy"]["round_budget_usd"] = [20, 20, 20]
        plan = binder_lane.plan_request(request, self.ledger(), ROOT)
        contract = binder_lane.round_contract(plan)
        handoff = binder_lane.execution_handoff(plan)
        self.assertEqual(6, contract["planned_candidate_count"])
        self.assertEqual(1, contract["optimization_horizon"]["current_round_index"])
        self.assertEqual(3, contract["optimization_horizon"]["maximum_round_count"])
        self.assertTrue(all(package["round_index"] == 1 for package in handoff["packages"]))
        expected = {
            "diffusion-mpnn": 2,
            "all-atom-mpnn": 2,
            "integrated-design": 2,
        }
        self.assertTrue(
            all(
                stage["expected_record_counts_by_toolchain"] == expected
                for stage in contract["stages"]
                if stage["id"] != "target"
            )
        )

        (ROOT / ".runtime").mkdir(exist_ok=True)
        with tempfile.TemporaryDirectory(dir=ROOT / ".runtime") as tmp:
            temp_root = Path(tmp)
            request_path = temp_root / "request.json"
            request_path.write_text(json.dumps(request), encoding="utf-8")
            bound_plan = binder_lane.plan_request(
                request,
                self.ledger(),
                ROOT,
                request_ref=request_path.relative_to(ROOT).as_posix(),
                ledger_ref=LEDGER_PATH.relative_to(ROOT).as_posix(),
            )
            run_root = temp_root / "round"
            binder_lane.materialize_plan(bound_plan, run_root, ROOT)
            binder_lane.run_synthetic(run_root, ROOT)
            self.assertTrue(binder_lane.report_summary(run_root, ROOT)["ok"])

    def test_round_decision_uses_metric_budget_stopping_rule_and_horizon(self) -> None:
        request = copy.deepcopy(self.request())
        request["optimization_policy"].update(
            {
                "round_count": 3,
                "current_round_index": 1,
                "stopping_rule": {
                    "type": "target_threshold",
                    "threshold": 0.9,
                    "direction": "maximize",
                },
                "round_budget_usd": [20, 20, 20],
            }
        )
        plan = binder_lane.plan_request(request, self.ledger(), ROOT)
        decision = binder_lane.round_decision(
            plan,
            [
                {
                    "round_index": 1,
                    "primary_metric_value": 0.8,
                    "actual_spend_usd": 18,
                    "closeout_complete": True,
                    "metric_provenance": {
                        "metric_id": "cofold_confidence_proxy",
                        "metric_source": "stage_closeout",
                        "source_artifact_sha256": "a" * 64,
                        "calibration_state": "operator_defined",
                        "calibration_scope_id": "shared-threshold-policy",
                        "calibration_artifact_sha256": None,
                    },
                }
            ],
        )
        self.assertEqual("continue", decision["decision"])
        self.assertEqual(2, decision["next_round_index"])
        self.assertEqual(42.0, decision["remaining_budget_usd"])
        self.assertEqual(0, decision["provider_calls"])
        try:
            from jsonschema import Draft202012Validator
        except ImportError:
            pass
        else:
            decision_schema = json.loads(
                (ROOT / "schemas/binder-round-decision.schema.json").read_text(encoding="utf-8")
            )
            self.assertTrue(Draft202012Validator(decision_schema).is_valid(decision))

        threshold = binder_lane.round_decision(
            plan,
            [
                {
                    "round_index": 1,
                    "primary_metric_value": 0.91,
                    "actual_spend_usd": 18,
                    "closeout_complete": True,
                    "metric_provenance": {
                        "metric_id": "cofold_confidence_proxy",
                        "metric_source": "stage_closeout",
                        "source_artifact_sha256": "b" * 64,
                        "calibration_state": "operator_defined",
                        "calibration_scope_id": "shared-threshold-policy",
                        "calibration_artifact_sha256": None,
                    },
                }
            ],
        )
        self.assertEqual("stop", threshold["decision"])
        self.assertEqual("target_threshold_reached", threshold["reason"])

        uncalibrated_history = [
            {
                "round_index": 1,
                "primary_metric_value": 0.91,
                "actual_spend_usd": 18,
                "closeout_complete": True,
                "metric_provenance": {
                    "metric_id": "cofold_confidence_proxy",
                    "metric_source": "stage_closeout",
                    "source_artifact_sha256": "c" * 64,
                    "calibration_state": "uncalibrated",
                    "calibration_scope_id": "uninterpreted-score",
                    "calibration_artifact_sha256": None,
                },
            }
        ]
        with self.assertRaises(binder_lane.BinderLaneError):
            binder_lane.round_decision(plan, uncalibrated_history)

        incomplete = copy.deepcopy(self.request())
        incomplete["optimization_policy"].update(
            {"round_count": 3, "current_round_index": 2, "round_budget_usd": [20, 20, 20]}
        )
        plan_two = binder_lane.plan_request(incomplete, self.ledger(), ROOT)
        with self.assertRaises(binder_lane.BinderLaneError):
            binder_lane.round_decision(
                plan_two,
                [
                    {
                        "round_index": 2,
                        "primary_metric_value": 0.8,
                        "actual_spend_usd": 18,
                        "closeout_complete": True,
                        "metric_provenance": {
                            "metric_id": "cofold_confidence_proxy",
                            "metric_source": "synthetic_fixture",
                            "source_artifact_sha256": None,
                            "calibration_state": "not_applicable",
                            "calibration_scope_id": "synthetic-demo",
                            "calibration_artifact_sha256": None,
                        },
                    }
                ],
            )

        mutations = [
            ("unknown_metric", lambda request: request["optimization_policy"].update({"primary_metric_id": "missing-metric"})),
            ("zero_rounds", lambda request: request["optimization_policy"].update({"round_count": 0, "round_budget_usd": []})),
            ("wrong_direction", lambda request: request["optimization_policy"].update({"direction": "minimize"})),
            (
                "wrong_stopping_direction",
                lambda request: request["optimization_policy"].update(
                    {"stopping_rule": {"type": "target_threshold", "threshold": 0.8, "direction": "minimize"}}
                ),
            ),
            ("budget_mismatch", lambda request: request["optimization_policy"].update({"round_budget_usd": [59]})),
        ]
        for name, mutate in mutations:
            with self.subTest(name=name):
                request = copy.deepcopy(self.request())
                mutate(request)
                with self.assertRaises(binder_lane.BinderLaneError):
                    binder_lane.plan_request(request, self.ledger(), ROOT)

    def test_optimization_policy_allows_custom_tool_comparisons_and_optional_budget_ceiling(self) -> None:
        request = copy.deepcopy(self.request())
        request["study_template"] = "custom"
        request["published_workflow"] = None
        request["workflow_strategy"] = {
            "mode": "independent",
            "reference_scope": None,
            "replay_toolchain_ids": [],
            "swap_toolchain_ids": [],
        }
        request["comparison_policy"]["mode"] = "exploratory_full_stack"
        request["comparison_policy"]["cross_arm_ranking"] = "not_permitted"
        request["toolchains"][1]["predictors"] = ["chai"]
        request["license_policy"]["allowed_gates"].append("verify_current_terms")
        request["optimization_policy"] = {
            "round_count": 2,
            "current_round_index": 1,
            "primary_metric_id": "cofold_confidence_proxy",
            "direction": "maximize",
            "candidate_policy": {"mode": "fixed_per_toolchain", "candidate_count_per_toolchain": 2},
            "stopping_rule": {
                "type": "no_improvement",
                "patience_rounds": 1,
                "minimum_delta": 0.02,
                "direction": "maximize",
            },
            "round_budget_usd": [30, 30],
        }
        plan = binder_lane.plan_request(request, self.ledger(), ROOT)
        self.assertEqual("custom", plan["study_template"])
        self.assertEqual("chai", plan["toolchains"][1]["predictors"][0]["tool_id"])
        self.assertEqual(6, sum(binder_lane._candidate_counts_per_round(plan).values()))

        request["execution_policy"]["max_spend_usd"] = None
        request["optimization_policy"]["round_budget_usd"] = [None, None]
        request["optimization_policy"]["stopping_rule"] = {
            "type": "target_threshold",
            "threshold": 0.8,
            "direction": "maximize",
        }
        plan = binder_lane.plan_request(request, self.ledger(), ROOT)
        self.assertIsNone(plan["execution_policy"]["max_spend_usd"])
        self.assertEqual([None, None], plan["optimization_policy"]["round_budget_usd"])

        request["optimization_policy"]["round_budget_usd"] = [0, 0]
        with self.assertRaises(binder_lane.BinderLaneError):
            binder_lane.plan_request(request, self.ledger(), ROOT)

    def test_unknown_nested_request_fields_fail_closed(self) -> None:
        mutations = [
            ("constraints", "private_comment"),
            ("license_policy", "approval_note"),
            ("execution_policy", "internal_route"),
        ]
        for parent, key in mutations:
            with self.subTest(parent=parent, key=key):
                request = copy.deepcopy(self.request())
                request[parent][key] = "public-looking but undeclared"
                with self.assertRaises(binder_lane.BinderLaneError):
                    binder_lane.plan_request(request, self.ledger(), ROOT)

        request = copy.deepcopy(self.request())
        request["execution_policy"]["routes"][0]["internal_route"] = "undeclared"
        with self.assertRaises(binder_lane.BinderLaneError):
            binder_lane.plan_request(request, self.ledger(), ROOT)

    def test_capability_ledger_rejects_unknown_or_internal_fields(self) -> None:
        ledger = copy.deepcopy(self.ledger())
        ledger["tools"][0]["providerId"] = "fake"
        with self.assertRaises(binder_lane.BinderLaneError):
            binder_lane.validate_ledger(ledger, ROOT)

        ledger = copy.deepcopy(self.ledger())
        ledger["state_definitions"]["listed"] = "Internal " + "process note from private review."
        with self.assertRaises(binder_lane.BinderLaneError):
            binder_lane.validate_ledger(ledger, ROOT)

    def test_route_backend_profile_and_topology_must_match(self) -> None:
        for mutation in ("backend", "topology"):
            with self.subTest(mutation=mutation):
                request = copy.deepcopy(self.request())
                if mutation == "backend":
                    request["execution_policy"]["routes"][0]["backend"] = "aws"
                else:
                    request["execution_policy"]["topology"] = "local"
                with self.assertRaises(binder_lane.BinderLaneError):
                    binder_lane.plan_request(request, self.ledger(), ROOT)

    def test_fal_profile_is_a_valid_planning_route(self) -> None:
        request = copy.deepcopy(self.request())
        route = request["execution_policy"]["routes"][0]
        route["backend"] = "fal"
        route["profile_ref"] = "modules/provider-profiles/fal/serverless-gpu-no-download.v1.json"
        plan = binder_lane.plan_request(request, self.ledger(), ROOT)
        fal_route = next(item for item in plan["execution_policy"]["routes"] if item["backend"] == "fal")
        self.assertTrue(fal_route["operator_gate_required"])
        self.assertEqual("plan_then_explicit_runtime_authorization", plan["execution_policy"]["authorization"])
        try:
            from jsonschema import Draft202012Validator
        except ImportError:
            return
        request_schema = json.loads((ROOT / "schemas/binder-round-request.schema.json").read_text(encoding="utf-8"))
        self.assertTrue(Draft202012Validator(request_schema).is_valid(request))

    def test_api_route_requires_terms_retention_and_secret_review(self) -> None:
        request = copy.deepcopy(self.request())
        del request["execution_policy"]["routes"][1]["api_policy"]
        with self.assertRaises(binder_lane.BinderLaneError):
            binder_lane.plan_request(request, self.ledger(), ROOT)

    def test_api_route_rejects_unapproved_or_invalid_adapter_contract(self) -> None:
        request = copy.deepcopy(self.request())
        request["execution_policy"]["routes"][1]["adapter_contract_ref"] = "internal/README.md"
        with self.assertRaises(binder_lane.BinderLaneError):
            binder_lane.plan_request(request, self.ledger(), ROOT)

        adapter = json.loads((ROOT / "templates/binder-api-adapter-contract.json").read_text())
        adapter["launch_authorization"] = "granted"
        with self.assertRaises(binder_lane.BinderLaneError):
            binder_lane.validate_api_adapter_contract(adapter)

    def test_license_policy_can_block_a_selected_tool_and_never_records_acceptance(self) -> None:
        request = copy.deepcopy(self.request())
        request["license_policy"]["blocked_tools"] = ["rfdiffusion"]
        with self.assertRaises(binder_lane.BinderLaneError):
            binder_lane.plan_request(request, self.ledger(), ROOT)
        plan = self.plan()
        self.assertEqual("not_recorded", plan["license_policy"]["review_status"])
        self.assertTrue(plan["license_policy"]["allowed_gates_are_not_acceptance"])

    def test_secret_shaped_value_is_rejected_without_echoing_it(self) -> None:
        request = copy.deepcopy(self.request())
        request["target"]["label"] = "Bearer abcdefghijklmnopqrstuvwxyz"
        with self.assertRaises(binder_lane.BinderLaneError) as caught:
            binder_lane.plan_request(request, self.ledger(), ROOT)
        self.assertNotIn("abcdefghijklmnopqrstuvwxyz", str(caught.exception))

    def test_private_paths_networks_and_unknown_keys_are_rejected_without_echo(self) -> None:
        sentinels = [
            "sk" + "-proj-" + "abcdefghijklmnop",
            "/root/private/project",
            "/var/folders/example/private",
            "http://[::1]:8000/private",
            "see:/" + "Users/example/private",
            "path=(/" + "Volumes/private/data)",
            "C:\\Temp\\private",
            "/etc/credentials",
            "/mnt/project/private",
        ]
        for sentinel in sentinels:
            with self.subTest(sentinel=sentinel):
                request = copy.deepcopy(self.request())
                request["target"]["label"] = sentinel
                with self.assertRaises(binder_lane.BinderLaneError) as caught:
                    binder_lane.plan_request(request, self.ledger(), ROOT)
                self.assertNotIn(sentinel, str(caught.exception))

        sentinel_key = "sk" + "-proj-" + "unknownfieldsecret"
        request = copy.deepcopy(self.request())
        request[sentinel_key] = "ordinary"
        with self.assertRaises(binder_lane.BinderLaneError) as caught:
            binder_lane.plan_request(request, self.ledger(), ROOT)
        self.assertNotIn(sentinel_key, str(caught.exception))

    def test_synthetic_fixture_rejects_claim_like_or_malformed_rows(self) -> None:
        mutations = [
            ("cofold_status", "binding_confirmed"),
            ("rank", "first"),
            ("scores", {"affinity_nM": 0.01}),
            ("artifact_refs", ["private-result.pdb"]),
        ]
        for key, value in mutations:
            with self.subTest(key=key):
                fixture = copy.deepcopy(self.fixture())
                fixture["candidates"][0][key] = value
                with self.assertRaises(binder_lane.BinderLaneError):
                    binder_lane._synthetic_candidates(fixture)

    def test_published_schemas_reject_weakened_boundaries(self) -> None:
        try:
            from jsonschema import Draft202012Validator
        except ImportError:
            self.skipTest("jsonschema is optional")

        def validator(relative: str) -> Draft202012Validator:
            schema = json.loads((ROOT / relative).read_text(encoding="utf-8"))
            Draft202012Validator.check_schema(schema)
            return Draft202012Validator(schema)

        plan = self.plan()
        plan_validator = validator("schemas/binder-round-plan.schema.json")
        local_plan = copy.deepcopy(plan)
        local_route = next(route for route in local_plan["execution_policy"]["routes"] if route["backend"] == "local")
        self.assertFalse(local_route["operator_gate_required"])
        self.assertTrue(plan_validator.is_valid(local_plan))
        weakened_plan = copy.deepcopy(plan)
        weakened_plan["execution"]["adapter_execution_authorization"] = "not_required"
        self.assertFalse(plan_validator.is_valid(weakened_plan))
        mismatched_plan = copy.deepcopy(plan)
        mismatched_plan["source_posture"] = "public_data"
        self.assertFalse(plan_validator.is_valid(mismatched_plan))
        sequence_plan = copy.deepcopy(plan)
        sequence_plan["target"]["public_accession"] = "MKTAYIAKQRQISFVKSHFS"
        self.assertFalse(plan_validator.is_valid(sequence_plan))

        request_validator = validator("schemas/binder-round-request.schema.json")
        mismatched_request = copy.deepcopy(self.request())
        mismatched_request["source_posture"] = "public_data"
        self.assertFalse(request_validator.is_valid(mismatched_request))
        namespace_request = copy.deepcopy(self.request())
        namespace_request["target"]["public_accession"] = "SYNTHETIC:demo"
        self.assertFalse(request_validator.is_valid(namespace_request))
        sequence_request = copy.deepcopy(self.request())
        sequence_request["target"]["public_accession"] = "MKTAYIAKQRQISFVKSHFS"
        self.assertFalse(request_validator.is_valid(sequence_request))

        counts = {arm["id"]: arm["candidate_count"] for arm in plan["toolchains"]}
        candidates = binder_lane._synthetic_candidates(self.fixture())
        report = binder_lane._synthetic_report(plan, candidates, counts)
        report_validator = validator("schemas/binder-round-report.schema.json")
        claim_report = copy.deepcopy(report)
        claim_report["claims"] = {"supported": ["binding confirmed"], "not_supported": []}
        self.assertFalse(report_validator.is_valid(claim_report))
        status_report = copy.deepcopy(report)
        status_report["candidates"][0]["status"] = "binding_confirmed"
        self.assertFalse(report_validator.is_valid(status_report))
        sequence_report = copy.deepcopy(report)
        sequence_report["target"]["public_accession"] = "MKTAYIAKQRQISFVKSHFS"
        self.assertFalse(report_validator.is_valid(sequence_report))

        contract = binder_lane.round_contract(plan, "0" * 64)
        contract_validator = validator("modules/schemas/binder-round-contract.v1.schema.json")
        wrong_artifact = copy.deepcopy(contract)
        wrong_artifact["stages"][0]["expected_artifacts"] = ["round-report.json"]
        self.assertFalse(contract_validator.is_valid(wrong_artifact))
        duplicate_stages = copy.deepcopy(contract)
        duplicate_stages["stages"] = [copy.deepcopy(contract["stages"][0]) for _ in range(7)]
        self.assertFalse(contract_validator.is_valid(duplicate_stages))

        handoff = binder_lane.execution_handoff(plan, "0" * 64)
        handoff_validator = validator("modules/schemas/binder-execution-handoff.v1.schema.json")
        self.assertTrue(handoff_validator.is_valid(handoff))
        weakened_handoff = copy.deepcopy(handoff)
        weakened_handoff["packages"][0]["authorization"] = "not_required"
        self.assertFalse(handoff_validator.is_valid(weakened_handoff))

    def test_synthetic_boundary_requires_synthetic_source_posture(self) -> None:
        request = copy.deepcopy(self.request())
        request["source_posture"] = "public_data"
        with self.assertRaises(binder_lane.BinderLaneError):
            binder_lane.plan_request(request, self.ledger(), ROOT)

    def test_request_prose_rejects_internal_process_language(self) -> None:
        mutations = [
            ("toolchain_label", "operator scratch" + "pad option alpha"),
            ("objective", "Internal " + "process note from a private source lane."),
            ("inclusion_rule", "Keep the reviewer note with every row."),
        ]
        for mutation, value in mutations:
            with self.subTest(mutation=mutation):
                request = copy.deepcopy(self.request())
                if mutation == "toolchain_label":
                    request["toolchains"][0]["label"] = value
                elif mutation == "objective":
                    request["constraints"]["objective"] = value
                else:
                    request["constraints"]["inclusion_rules"][0] = value
                with self.assertRaises(binder_lane.BinderLaneError):
                    binder_lane.plan_request(request, self.ledger(), ROOT)

    def test_preflight_blocks_plan_tampering(self) -> None:
        plan = self.plan()
        (ROOT / ".runtime").mkdir(exist_ok=True)
        with tempfile.TemporaryDirectory(dir=ROOT / ".runtime") as tmp:
            run_root = Path(tmp) / "round"
            binder_lane.materialize_plan(plan, run_root, ROOT)
            stored = json.loads((run_root / "plan.json").read_text())
            stored["target"]["label"] = "changed public label"
            (run_root / "plan.json").write_text(json.dumps(stored), encoding="utf-8")
            result = binder_lane.preflight(run_root, ROOT)
            self.assertFalse(result["ok"])
            self.assertTrue(any("plan.json" in finding or "plan" in finding for finding in result["findings"]))

    def test_run_refuses_planning_only_handoff(self) -> None:
        request = copy.deepcopy(self.request())
        request["source_posture"] = "public_data"
        request["result_boundary"] = "planning"
        request["synthetic_fixture"] = None
        (ROOT / ".runtime").mkdir(exist_ok=True)
        with tempfile.TemporaryDirectory(dir=ROOT / ".runtime") as tmp:
            request_path = Path(tmp) / "planning-request.json"
            request_path.write_text(json.dumps(request), encoding="utf-8")
            plan = binder_lane.plan_request(
                request,
                self.ledger(),
                ROOT,
                request_ref=request_path.relative_to(ROOT).as_posix(),
                ledger_ref=LEDGER_PATH.relative_to(ROOT).as_posix(),
            )
            run_root = Path(tmp) / "round"
            binder_lane.materialize_plan(plan, run_root, ROOT)
            with self.assertRaises(binder_lane.BinderLaneError):
                binder_lane.run_synthetic(run_root, ROOT)

    def test_library_refuses_materialization_outside_runtime(self) -> None:
        plan = self.plan()
        with tempfile.TemporaryDirectory() as tmp:
            with self.assertRaises(binder_lane.BinderLaneError):
                binder_lane.materialize_plan(plan, Path(tmp) / "run", ROOT)

    def test_materialization_requires_hash_bound_public_inputs(self) -> None:
        plan = binder_lane.plan_request(self.request(), self.ledger(), ROOT)
        (ROOT / ".runtime").mkdir(exist_ok=True)
        with tempfile.TemporaryDirectory(dir=ROOT / ".runtime") as tmp:
            with self.assertRaises(binder_lane.BinderLaneError):
                binder_lane.materialize_plan(plan, Path(tmp) / "run", ROOT)

    def test_preflight_rejects_weakened_handoff_and_round_contract(self) -> None:
        (ROOT / ".runtime").mkdir(exist_ok=True)
        for filename, mutate in [
            (
                "execution-handoff.json",
                lambda payload: payload.update({"launch_boundary": "Authorization granted."}),
            ),
            (
                "round-contract.json",
                lambda payload: payload["stages"][0].update(
                    {"expected_artifacts": ["plan.json"], "minimum_output_count": 0}
                ),
            ),
        ]:
            with self.subTest(filename=filename), tempfile.TemporaryDirectory(dir=ROOT / ".runtime") as tmp:
                run_root = Path(tmp) / "round"
                binder_lane.materialize_plan(self.plan(), run_root, ROOT)
                path = run_root / filename
                payload = json.loads(path.read_text())
                mutate(payload)
                path.write_text(json.dumps(payload), encoding="utf-8")
                self.assertFalse(binder_lane.preflight(run_root, ROOT)["ok"])

    def test_preflight_rejects_undeclared_run_artifacts(self) -> None:
        (ROOT / ".runtime").mkdir(exist_ok=True)
        with tempfile.TemporaryDirectory(dir=ROOT / ".runtime") as tmp:
            run_root = Path(tmp) / "round"
            binder_lane.materialize_plan(self.plan(), run_root, ROOT)
            (run_root / "agent-notes.json").write_text(
                json.dumps({"meta_concern": "public-looking process note"}),
                encoding="utf-8",
            )
            result = binder_lane.preflight(run_root, ROOT)
            self.assertFalse(result["ok"])
            self.assertIn("undeclared run artifact", result["findings"])

    def test_report_rejects_forged_boundary_even_with_recomputed_hash(self) -> None:
        (ROOT / ".runtime").mkdir(exist_ok=True)
        with tempfile.TemporaryDirectory(dir=ROOT / ".runtime") as tmp:
            run_root = Path(tmp) / "round"
            binder_lane.materialize_plan(self.plan(), run_root, ROOT)
            binder_lane.run_synthetic(run_root, ROOT)
            report_path = run_root / "round-report.json"
            report = json.loads(report_path.read_text())
            report["result_boundary"] = "binding_confirmed"
            report_path.write_text(json.dumps(report), encoding="utf-8")
            ledger_path = run_root / "artifact-hashes.json"
            ledger = json.loads(ledger_path.read_text())
            for row in ledger["artifacts"]:
                if row["path"] == "round-report.json":
                    row["sha256"] = binder_lane.sha256_path(report_path)
            ledger_path.write_text(json.dumps(ledger), encoding="utf-8")
            with self.assertRaises(binder_lane.BinderLaneError):
                binder_lane.report_summary(run_root, ROOT)

    def test_preflight_rejects_mutated_stage_even_with_recomputed_hash(self) -> None:
        (ROOT / ".runtime").mkdir(exist_ok=True)
        with tempfile.TemporaryDirectory(dir=ROOT / ".runtime") as tmp:
            run_root = Path(tmp) / "round"
            binder_lane.materialize_plan(self.plan(), run_root, ROOT)
            binder_lane.run_synthetic(run_root, ROOT)
            stage_path = run_root / "generation-status.json"
            stage = json.loads(stage_path.read_text())
            stage["providerId"] = "fake-provider-resource"
            stage_path.write_text(json.dumps(stage), encoding="utf-8")
            ledger_path = run_root / "artifact-hashes.json"
            ledger = json.loads(ledger_path.read_text())
            for row in ledger["artifacts"]:
                if row["path"] == "generation-status.json":
                    row["sha256"] = binder_lane.sha256_path(stage_path)
            ledger_path.write_text(json.dumps(ledger), encoding="utf-8")
            self.assertFalse(binder_lane.preflight(run_root, ROOT)["ok"])
            with self.assertRaises(binder_lane.BinderLaneError):
                binder_lane.report_summary(run_root, ROOT)

    def test_materialization_rejects_fixture_changed_after_planning(self) -> None:
        (ROOT / ".runtime").mkdir(exist_ok=True)
        with tempfile.TemporaryDirectory(dir=ROOT / ".runtime") as tmp:
            temp_root = Path(tmp)
            fixture_path = temp_root / "fixture.json"
            request_path = temp_root / "request.json"
            fixture_path.write_text(json.dumps(self.fixture()), encoding="utf-8")
            request = copy.deepcopy(self.request())
            request["synthetic_fixture"] = fixture_path.relative_to(ROOT).as_posix()
            request_path.write_text(json.dumps(request), encoding="utf-8")
            plan = binder_lane.plan_request(
                request,
                self.ledger(),
                ROOT,
                request_ref=request_path.relative_to(ROOT).as_posix(),
                ledger_ref=LEDGER_PATH.relative_to(ROOT).as_posix(),
            )
            changed = self.fixture()
            changed["candidates"][0]["id"] = "changed-public-fixture-id"
            fixture_path.write_text(json.dumps(changed), encoding="utf-8")
            with self.assertRaises(binder_lane.BinderLaneError):
                binder_lane.materialize_plan(plan, temp_root / "round", ROOT)

    def test_json_reader_rejects_duplicate_keys_and_nonfinite_values(self) -> None:
        (ROOT / ".runtime").mkdir(exist_ok=True)
        with tempfile.TemporaryDirectory(dir=ROOT / ".runtime") as tmp:
            path = Path(tmp) / "ambiguous.json"
            path.write_text('{"authorization":"not_granted","authorization":"granted"}', encoding="utf-8")
            with self.assertRaises(binder_lane.BinderLaneError):
                binder_lane.read_json(path)

        request = copy.deepcopy(self.request())
        request["execution_policy"]["max_spend_usd"] = float("nan")
        with self.assertRaises(binder_lane.BinderLaneError):
            binder_lane.plan_request(request, self.ledger(), ROOT)


if __name__ == "__main__":
    unittest.main()
