from __future__ import annotations

import json
import os
import sys
import tempfile
import unittest
from pathlib import Path
from unittest import mock

from biosymphony_structure_factory import binder_controller, binder_executor, target_verifier


def registry(
    *,
    second_program: str = "fixture-writer",
    second_execution_kind: str = "local_argv",
    network_policy: str = "forbidden",
    license_gate: str = "none",
) -> dict:
    def adapter(adapter_id: str, program: str, execution_kind: str = "local_argv") -> dict:
        local = execution_kind == "local_argv"
        return {
            "id": adapter_id,
            "tool_id": adapter_id.removesuffix("-adapter"),
            "supported_selections": [
                {"tool_id": adapter_id.removesuffix("-adapter"), "variant_id": None}
            ],
            "roles": ["filter"],
            "supported_routes": [{"backend": "local", "execution_method": "self_hosted"}],
            "license_gate": license_gate,
            "implementation_status": "ready" if local else "adapter_required",
            "execution_kind": execution_kind,
            "program": program if local else None,
            "readiness_argv": [program] if local else [],
            "command_argv": [program, "output.jsonl"] if local else [],
            "placeholders": {},
            "required_environment_names": [],
            "network_policy": network_policy,
            "expected_outputs": [
                {
                    "id": "candidate-rows",
                    "path_template": "output.jsonl",
                    "kind": "jsonl",
                    "minimum_count": 1,
                    "maximum_count": 1,
                }
            ],
            "public_evidence": [],
        }

    return {
        "schema_version": binder_executor.REGISTRY_SCHEMA_VERSION,
        "boundary": {
            "execution": "Run fixed local argument arrays.",
            "readiness": "Check each declared program and environment name.",
            "extensions": ["Add reviewed local argument-array adapters."],
        },
        "adapters": [
            adapter("first-adapter", "fixture-writer"),
            adapter("second-adapter", second_program, second_execution_kind),
        ],
    }


def request() -> dict:
    return {
        "schema_version": binder_controller.CONTROLLER_SCHEMA,
        "controller_id": "public-round-1",
        "plan_sha256": "a" * 64,
        "result_boundary": "computational_candidate",
        "target_verification": {
            "ok": True,
            "schema_version": target_verifier.REPORT_SCHEMA,
            "structure_sha256": "b" * 64,
            "required_residues_verified": True,
        },
        "budget": {"currency": "USD", "spend_ceiling_usd": 1.0},
        "stages": [
            {
                "stage_id": "filter-status",
                "adapter_id": "first-adapter",
                "depends_on": [],
                "bindings": {},
                "estimated_cost_usd": 0.0,
                "timeout_seconds": 10,
            },
            {
                "stage_id": "filter-diversity",
                "adapter_id": "second-adapter",
                "depends_on": ["filter-status"],
                "bindings": {},
                "estimated_cost_usd": 0.0,
                "timeout_seconds": 10,
            },
        ],
    }


def handoff_registry() -> dict:
    def adapter(
        adapter_id: str,
        program: str,
        command_argv: list[str],
        placeholders: dict,
        output_id: str,
        output_path: str,
    ) -> dict:
        tool_id = adapter_id.removesuffix("-adapter")
        return {
            "id": adapter_id,
            "tool_id": tool_id,
            "supported_selections": [{"tool_id": tool_id, "variant_id": None}],
            "roles": ["filter"],
            "supported_routes": [
                {"backend": "local", "execution_method": "self_hosted"}
            ],
            "license_gate": "none",
            "implementation_status": "ready",
            "execution_kind": "local_argv",
            "program": program,
            "readiness_argv": [program, "--ready"],
            "command_argv": [program, *command_argv],
            "placeholders": placeholders,
            "required_environment_names": [],
            "network_policy": "forbidden",
            "expected_outputs": [
                {
                    "id": output_id,
                    "path_template": output_path,
                    "kind": "jsonl",
                    "minimum_count": 1,
                    "maximum_count": 1,
                }
            ],
            "public_evidence": [],
        }

    path_placeholder = {"type": "path"}
    return {
        "schema_version": binder_executor.REGISTRY_SCHEMA_VERSION,
        "boundary": {
            "execution": "Run fixed local argument arrays.",
            "readiness": "Check each declared program.",
            "extensions": ["Add reviewed local argument-array adapters."],
        },
        "adapters": [
            adapter(
                "handoff-source-adapter",
                "fixture-source",
                ["{{output_path}}"],
                {"output_path": path_placeholder},
                "source-rows",
                "{{output_path}}",
            ),
            adapter(
                "handoff-sink-adapter",
                "fixture-sink",
                ["{{input_path}}", "{{output_path}}"],
                {
                    "input_path": path_placeholder,
                    "output_path": path_placeholder,
                },
                "sink-rows",
                "{{output_path}}",
            ),
        ],
    }


def handoff_request() -> dict:
    payload = request()
    payload["controller_id"] = "handoff-rejection-check"
    payload["stages"] = [
        {
            "stage_id": "handoff-source",
            "adapter_id": "handoff-source-adapter",
            "depends_on": [],
            "bindings": {"output_path": "outputs/source.jsonl"},
            "estimated_cost_usd": 0.0,
            "timeout_seconds": 10,
        },
        {
            "stage_id": "handoff-sink",
            "adapter_id": "handoff-sink-adapter",
            "depends_on": ["handoff-source"],
            "bindings": {
                "input_path": "inputs/source.jsonl",
                "output_path": "outputs/sink.jsonl",
            },
            "input_handoffs": [
                {
                    "source_stage_id": "handoff-source",
                    "source_output_id": "source-rows",
                    "destination_binding": "input_path",
                }
            ],
            "estimated_cost_usd": 0.0,
            "timeout_seconds": 10,
        },
    ]
    return payload


def bundle_registry() -> dict:
    path_placeholder = {"type": "path"}

    def adapter(
        adapter_id: str,
        program: str,
        command_argv: list[str],
        placeholders: dict,
        output_id: str,
        output_path: str,
        output_kind: str,
    ) -> dict:
        tool_id = adapter_id.removesuffix("-adapter")
        return {
            "id": adapter_id,
            "tool_id": tool_id,
            "supported_selections": [{"tool_id": tool_id, "variant_id": None}],
            "roles": ["filter"],
            "supported_routes": [
                {"backend": "local", "execution_method": "self_hosted"}
            ],
            "license_gate": "none",
            "implementation_status": "ready",
            "execution_kind": "local_argv",
            "program": program,
            "readiness_argv": [program, "--ready"],
            "command_argv": [program, *command_argv],
            "placeholders": placeholders,
            "required_environment_names": [],
            "network_policy": "forbidden",
            "expected_outputs": [
                {
                    "id": output_id,
                    "path_template": output_path,
                    "kind": output_kind,
                    "minimum_count": 1,
                    "maximum_count": 1,
                }
            ],
            "public_evidence": [],
        }

    return {
        "schema_version": binder_executor.REGISTRY_SCHEMA_VERSION,
        "boundary": {
            "execution": "Run fixed local argument arrays.",
            "readiness": "Check each declared program.",
            "extensions": ["Add reviewed local argument-array adapters."],
        },
        "adapters": [
            adapter(
                "bundle-source-adapter",
                "fixture-bundle-source",
                ["{{output_dir}}"],
                {"output_dir": path_placeholder},
                "candidate-bundle",
                "{{output_dir}}",
                "directory",
            ),
            adapter(
                "bundle-sink-adapter",
                "fixture-bundle-sink",
                ["{{input_dir}}", "{{output_path}}"],
                {"input_dir": path_placeholder, "output_path": path_placeholder},
                "bundle-summary",
                "{{output_path}}",
                "json",
            ),
        ],
    }


def bundle_request() -> dict:
    payload = request()
    payload["controller_id"] = "bundle-handoff-check"
    payload["stages"] = [
        {
            "stage_id": "bundle-source",
            "adapter_id": "bundle-source-adapter",
            "depends_on": [],
            "bindings": {"output_dir": "outputs/candidate-bundle"},
            "estimated_cost_usd": 0.0,
            "timeout_seconds": 10,
        },
        {
            "stage_id": "bundle-sink",
            "adapter_id": "bundle-sink-adapter",
            "depends_on": ["bundle-source"],
            "bindings": {
                "input_dir": "inputs/candidate-bundle",
                "output_path": "outputs/summary.json",
            },
            "input_handoffs": [
                {
                    "source_stage_id": "bundle-source",
                    "source_output_id": "candidate-bundle",
                    "destination_binding": "input_dir",
                }
            ],
            "estimated_cost_usd": 0.0,
            "timeout_seconds": 10,
        },
    ]
    return payload


class BinderControllerTests(unittest.TestCase):
    def setUp(self) -> None:
        self.temporary = tempfile.TemporaryDirectory()
        self.workspace = Path(self.temporary.name)
        self.runtime = self.workspace / ".runtime" / "controller"
        self.bin_dir = self.workspace / "bin"
        self.bin_dir.mkdir()
        writer = self.bin_dir / "fixture-writer"
        writer.write_text("#!/bin/sh\nprintf '{\"candidate_id\":\"fixture\"}\\n' > \"$1\"\n", encoding="utf-8")
        writer.chmod(0o755)
        source = self.bin_dir / "fixture-source"
        source.write_text(
            "\n".join(
                [
                    f"#!{sys.executable}",
                    "import sys",
                    "from pathlib import Path",
                    "if sys.argv[1:] == ['--ready']:",
                    "    raise SystemExit(0)",
                    "output = Path(sys.argv[1])",
                    "output.parent.mkdir(parents=True, exist_ok=True)",
                    "output.write_text('{\"candidate_id\":\"fixture\"}\\n', encoding='utf-8')",
                    "",
                ]
            ),
            encoding="utf-8",
        )
        source.chmod(0o755)
        sink = self.bin_dir / "fixture-sink"
        sink.write_text(
            "\n".join(
                [
                    f"#!{sys.executable}",
                    "import sys",
                    "from pathlib import Path",
                    "if sys.argv[1:] == ['--ready']:",
                    "    raise SystemExit(0)",
                    "source = Path(sys.argv[1])",
                    "output = Path(sys.argv[2])",
                    "output.parent.mkdir(parents=True, exist_ok=True)",
                    "output.write_bytes(source.read_bytes())",
                    "",
                ]
            ),
            encoding="utf-8",
        )
        sink.chmod(0o755)
        bundle_source = self.bin_dir / "fixture-bundle-source"
        bundle_source.write_text(
            "\n".join(
                [
                    f"#!{sys.executable}",
                    "import json",
                    "import sys",
                    "from pathlib import Path",
                    "if sys.argv[1:] == ['--ready']:",
                    "    raise SystemExit(0)",
                    "bundle = Path(sys.argv[1])",
                    "(bundle / 'structures').mkdir(parents=True, exist_ok=True)",
                    "(bundle / 'sidecars').mkdir(parents=True, exist_ok=True)",
                    "(bundle / 'manifest.json').write_text(json.dumps({'bundle_id': 'synthetic-bundle'}) + '\\n', encoding='utf-8')",
                    "(bundle / 'structures' / 'candidate.pdb').write_text('ATOM      1  CA  ALA A   1       0.000   0.000   0.000  1.00 20.00           C\\n', encoding='utf-8')",
                    "(bundle / 'sidecars' / 'metrics.jsonl').write_text(json.dumps({'candidate_id': 'synthetic-1', 'score': 0.5}) + '\\n', encoding='utf-8')",
                    "",
                ]
            ),
            encoding="utf-8",
        )
        bundle_source.chmod(0o755)
        bundle_sink = self.bin_dir / "fixture-bundle-sink"
        bundle_sink.write_text(
            "\n".join(
                [
                    f"#!{sys.executable}",
                    "import json",
                    "import sys",
                    "from pathlib import Path",
                    "if sys.argv[1:] == ['--ready']:",
                    "    raise SystemExit(0)",
                    "bundle = Path(sys.argv[1])",
                    "required = ['manifest.json', 'structures/candidate.pdb', 'sidecars/metrics.jsonl']",
                    "if any(not (bundle / name).is_file() for name in required):",
                    "    raise SystemExit(2)",
                    "output = Path(sys.argv[2])",
                    "output.parent.mkdir(parents=True, exist_ok=True)",
                    "output.write_text(json.dumps({'bundle_id': json.loads((bundle / 'manifest.json').read_text())['bundle_id'], 'file_count': len(required)}) + '\\n', encoding='utf-8')",
                    "",
                ]
            ),
            encoding="utf-8",
        )
        bundle_sink.chmod(0o755)
        self.original_path = os.environ.get("PATH", "")
        os.environ["PATH"] = f"{self.bin_dir}{os.pathsep}{self.original_path}"

    def tearDown(self) -> None:
        os.environ["PATH"] = self.original_path
        self.temporary.cleanup()

    def test_executes_dependencies_and_hashes_adapter_receipts(self) -> None:
        result = binder_controller.run_controller(
            request(),
            registry(),
            workspace_root=self.workspace,
            runtime_root=self.runtime,
            plan_sha256="a" * 64,
            authorization=binder_controller.AUTHORIZATION,
        )
        self.assertTrue(result["ok"], result)
        self.assertEqual(result["status"], "completed")
        self.assertEqual(result["completed_stage_count"], 2)
        self.assertEqual(result["actual_spend_usd"], None)
        self.assertTrue(all(len(row["receipt_sha256"]) == 64 for row in result["stages"]))
        written = json.loads((self.workspace / result["receipt_path"]).read_text())
        self.assertEqual(written["result_boundary"], "computational_candidate")

    def test_stops_after_failed_output_validation(self) -> None:
        result = binder_controller.run_controller(
            request(),
            registry(second_program="false"),
            workspace_root=self.workspace,
            runtime_root=self.runtime,
            plan_sha256="a" * 64,
            authorization=binder_controller.AUTHORIZATION,
        )
        self.assertFalse(result["ok"])
        self.assertEqual(result["status"], "failed")
        self.assertEqual(result["completed_stage_count"], 1)
        self.assertEqual(result["stages"][-1]["failure"]["check_id"], "artifact-closeout")

    def test_reports_missing_adapter_contract_before_execution(self) -> None:
        with self.assertRaisesRegex(binder_controller.BinderControllerError, "adapter readiness is adapter_required"):
            binder_controller.run_controller(
                request(),
                registry(second_execution_kind="external_adapter"),
                workspace_root=self.workspace,
                runtime_root=self.runtime,
                plan_sha256="a" * 64,
                authorization=binder_controller.AUTHORIZATION,
            )
        self.assertFalse(self.runtime.exists())

    def test_rejects_plan_or_budget_changes_before_execution(self) -> None:
        with self.assertRaisesRegex(binder_controller.BinderControllerError, "selected plan"):
            binder_controller.run_controller(
                request(),
                registry(),
                workspace_root=self.workspace,
                runtime_root=self.runtime,
                plan_sha256="c" * 64,
                authorization=binder_controller.AUTHORIZATION,
            )
        over_budget = request()
        over_budget["stages"][0]["estimated_cost_usd"] = 2.0
        with self.assertRaisesRegex(binder_controller.BinderControllerError, "spend ceiling"):
            binder_controller.validate_controller(over_budget, registry())

    def test_real_execution_requires_all_authorizations(self) -> None:
        with self.assertRaisesRegex(binder_controller.BinderControllerError, "explicit authorization"):
            binder_controller.run_controller(
                request(),
                registry(),
                workspace_root=self.workspace,
                runtime_root=self.runtime,
                plan_sha256="a" * 64,
                authorization=None,
            )

        gated = registry(network_policy="runtime_review_required", license_gate="terms_review")
        dry_result = binder_controller.run_controller(
            request(),
            gated,
            workspace_root=self.workspace,
            runtime_root=self.runtime,
            plan_sha256="a" * 64,
            authorization=None,
            dry_run=True,
        )
        self.assertTrue(dry_result["ok"], dry_result)
        with self.assertRaisesRegex(binder_controller.BinderControllerError, "network execution"):
            binder_controller.run_controller(
                request(),
                gated,
                workspace_root=self.workspace,
                runtime_root=self.workspace / ".runtime" / "gated",
                plan_sha256="a" * 64,
                authorization=binder_controller.AUTHORIZATION,
            )

    def test_rejects_tampered_or_unsafe_input_handoffs(self) -> None:
        original_materialize = binder_controller._materialize_input_handoffs

        for scenario in (
            "source-receipt-tamper",
            "source-artifact-tamper",
            "destination-symlink",
            "destination-collision",
        ):
            with self.subTest(scenario=scenario):
                runtime = self.workspace / ".runtime" / scenario
                destination = runtime / "stages" / "handoff-sink" / "inputs" / "source.jsonl"
                if scenario in {"destination-symlink", "destination-collision"}:
                    destination.parent.mkdir(parents=True)
                    if scenario == "destination-symlink":
                        symlink_target = runtime / "existing-source.jsonl"
                        symlink_target.parent.mkdir(parents=True, exist_ok=True)
                        symlink_target.write_text("preserve\n", encoding="utf-8")
                        destination.symlink_to(symlink_target)
                    else:
                        destination.write_text("preserve\n", encoding="utf-8")

                def tamper_then_materialize(stage, **kwargs):
                    if not stage["input_handoffs"]:
                        return original_materialize(stage, **kwargs)
                    source_row = kwargs["completed_rows"]["handoff-source"]
                    receipt_path = kwargs["run_root"] / source_row["receipt_path"]
                    if scenario == "source-receipt-tamper":
                        receipt_path.write_bytes(receipt_path.read_bytes() + b" ")
                    elif scenario == "source-artifact-tamper":
                        receipt = json.loads(receipt_path.read_text(encoding="utf-8"))
                        artifact_path = (
                            kwargs["run_root"]
                            / "stages"
                            / "handoff-source"
                            / receipt["outputs"][0]["files"][0]["path"]
                        )
                        artifact_path.write_bytes(artifact_path.read_bytes() + b"{}\n")
                    return original_materialize(stage, **kwargs)

                patcher = mock.patch.object(
                    binder_controller,
                    "_materialize_input_handoffs",
                    side_effect=tamper_then_materialize,
                )
                if scenario.startswith("source-"):
                    patcher.start()
                try:
                    result = binder_controller.run_controller(
                        handoff_request(),
                        handoff_registry(),
                        workspace_root=self.workspace,
                        runtime_root=runtime,
                        plan_sha256="a" * 64,
                        authorization=binder_controller.AUTHORIZATION,
                    )
                finally:
                    if scenario.startswith("source-"):
                        patcher.stop()

                self.assertFalse(result["ok"], result)
                self.assertEqual("failed", result["status"])
                self.assertEqual(1, result["completed_stage_count"])
                self.assertEqual("failed", result["stages"][-1]["state"])
                self.assertEqual("planned", result["stages"][-1]["input_handoffs"][0]["state"])
                if scenario in {"destination-symlink", "destination-collision"}:
                    self.assertEqual("preserve\n", destination.read_text(encoding="utf-8"))

    def test_materializes_a_verified_directory_bundle_for_a_later_stage(self) -> None:
        dry_runtime = self.workspace / ".runtime" / "bundle-dry-run"
        dry_result = binder_controller.run_controller(
            bundle_request(),
            bundle_registry(),
            workspace_root=self.workspace,
            runtime_root=dry_runtime,
            plan_sha256="a" * 64,
            authorization=None,
            dry_run=True,
        )
        planned = dry_result["stages"][-1]["input_handoffs"][0]
        self.assertEqual("planned", planned["state"])
        self.assertEqual("directory", planned["artifact_kind"])
        self.assertIsNone(planned["file_count"])
        self.assertFalse(
            (dry_runtime / "stages" / "bundle-sink" / "inputs" / "candidate-bundle").exists()
        )

        runtime = self.workspace / ".runtime" / "bundle-run"
        result = binder_controller.run_controller(
            bundle_request(),
            bundle_registry(),
            workspace_root=self.workspace,
            runtime_root=runtime,
            plan_sha256="a" * 64,
            authorization=binder_controller.AUTHORIZATION,
        )
        self.assertTrue(result["ok"], result)
        self.assertEqual("completed", result["status"])
        handoff = result["stages"][-1]["input_handoffs"][0]
        self.assertEqual("materialized", handoff["state"])
        self.assertEqual("directory", handoff["artifact_kind"])
        self.assertEqual(3, handoff["file_count"])
        self.assertEqual(3, handoff["record_count"])
        self.assertGreater(handoff["byte_count"], 0)
        self.assertEqual(
            handoff["source_artifact_sha256"],
            handoff["destination_artifact_sha256"],
        )
        self.assertNotIn("path", json.dumps(handoff))
        copied = runtime / "stages" / "bundle-sink" / "inputs" / "candidate-bundle"
        self.assertEqual(
            [
                "manifest.json",
                "sidecars/metrics.jsonl",
                "structures/candidate.pdb",
            ],
            sorted(path.relative_to(copied).as_posix() for path in copied.rglob("*") if path.is_file()),
        )

    def test_rejects_overlapping_handoff_destinations_before_execution(self) -> None:
        changed_registry = bundle_registry()
        sink = changed_registry["adapters"][1]
        sink["placeholders"]["nested_input_dir"] = {"type": "path"}
        changed_request = bundle_request()
        sink_stage = changed_request["stages"][1]
        sink_stage["bindings"]["nested_input_dir"] = "inputs/candidate-bundle/nested"
        sink_stage["input_handoffs"].append(
            {
                "source_stage_id": "bundle-source",
                "source_output_id": "candidate-bundle",
                "destination_binding": "nested_input_dir",
            }
        )
        with self.assertRaisesRegex(
            binder_controller.BinderControllerError,
            "overlapping destination paths",
        ):
            binder_controller.validate_controller(changed_request, changed_registry)

    def test_rejects_bundle_tampering_symlinks_escapes_and_collisions(self) -> None:
        original_materialize = binder_controller._materialize_input_handoffs

        for scenario in (
            "source-member-tamper",
            "source-unrecorded-symlink",
            "receipt-member-escape",
            "destination-collision",
        ):
            with self.subTest(scenario=scenario):
                runtime = self.workspace / ".runtime" / f"bundle-{scenario}"
                destination = (
                    runtime
                    / "stages"
                    / "bundle-sink"
                    / "inputs"
                    / "candidate-bundle"
                )
                if scenario == "destination-collision":
                    destination.mkdir(parents=True)
                    (destination / "preserve.txt").write_text("preserve\n", encoding="utf-8")

                def tamper_then_materialize(stage, **kwargs):
                    if not stage["input_handoffs"]:
                        return original_materialize(stage, **kwargs)
                    source_row = kwargs["completed_rows"]["bundle-source"]
                    receipt_path = kwargs["run_root"] / source_row["receipt_path"]
                    receipt = json.loads(receipt_path.read_text(encoding="utf-8"))
                    artifact = receipt["outputs"][0]["files"][0]
                    bundle = kwargs["run_root"] / "stages" / "bundle-source" / artifact["path"]
                    if scenario == "source-member-tamper":
                        member = bundle / artifact["members"][0]["path"]
                        member.write_bytes(member.read_bytes() + b" ")
                    elif scenario == "source-unrecorded-symlink":
                        outside = kwargs["run_root"] / "outside.txt"
                        outside.write_text("outside\n", encoding="utf-8")
                        (bundle / "sidecars" / "outside-link").symlink_to(outside)
                    elif scenario == "receipt-member-escape":
                        artifact["members"][0]["path"] = "../outside.txt"
                        receipt_path.write_text(
                            json.dumps(receipt, indent=2, sort_keys=True) + "\n",
                            encoding="utf-8",
                        )
                        source_row["receipt_sha256"] = binder_controller.binder_lane.sha256_path(
                            receipt_path
                        )
                    return original_materialize(stage, **kwargs)

                patcher = mock.patch.object(
                    binder_controller,
                    "_materialize_input_handoffs",
                    side_effect=tamper_then_materialize,
                )
                if scenario != "destination-collision":
                    patcher.start()
                try:
                    result = binder_controller.run_controller(
                        bundle_request(),
                        bundle_registry(),
                        workspace_root=self.workspace,
                        runtime_root=runtime,
                        plan_sha256="a" * 64,
                        authorization=binder_controller.AUTHORIZATION,
                    )
                finally:
                    if scenario != "destination-collision":
                        patcher.stop()

                self.assertFalse(result["ok"], result)
                self.assertEqual("failed", result["status"])
                self.assertEqual(1, result["completed_stage_count"])
                if scenario == "destination-collision":
                    self.assertEqual(
                        "preserve\n",
                        (destination / "preserve.txt").read_text(encoding="utf-8"),
                    )
                else:
                    self.assertFalse(destination.exists())
                self.assertEqual([], list(destination.parent.glob(".bsf-handoff-*")))


if __name__ == "__main__":
    unittest.main()
