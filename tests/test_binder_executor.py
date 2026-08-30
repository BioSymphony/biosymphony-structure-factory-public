from __future__ import annotations

import json
import os
import tempfile
import unittest
from pathlib import Path

from biosymphony_structure_factory import binder_executor

ROOT = Path(__file__).resolve().parents[1]


def adapter_registry(
    *,
    program: str = "truncate",
    readiness_argv: list[str] | None = None,
    command_argv: list[str] | None = None,
    placeholders: dict | None = None,
    required_environment_names: list[str] | None = None,
    execution_kind: str = "local_argv",
    implementation_status: str = "ready",
    expected_outputs: list | None = None,
) -> dict:
    return {
        "schema_version": binder_executor.REGISTRY_SCHEMA_VERSION,
        "boundary": {
            "execution": "Run a validated local argument-array adapter after authorization.",
            "readiness": "Check whether a declared local program starts.",
            "extensions": ["Declare fixed arguments and expected outputs."],
        },
        "adapters": [
            {
                "id": "fixture-adapter",
                "tool_id": "fixture-tool",
                "supported_selections": [{"tool_id": "fixture-tool", "variant_id": None}],
                "roles": ["predictor"],
                "supported_routes": [{"backend": "local", "execution_method": "self_hosted"}],
                "license_gate": "review_required",
                "implementation_status": implementation_status,
                "execution_kind": execution_kind,
                "program": program if execution_kind == "local_argv" else None,
                "readiness_argv": [program, *(readiness_argv or [])] if execution_kind == "local_argv" else [],
                "command_argv": [
                    program,
                    *(command_argv if command_argv is not None else ["-s", "1", "output.txt"]),
                ]
                if execution_kind == "local_argv"
                else [],
                "placeholders": placeholders or {},
                "required_environment_names": required_environment_names or [],
                "network_policy": "forbidden",
                "expected_outputs": expected_outputs
                if expected_outputs is not None
                else [
                    {
                        "id": "result",
                        "path_template": "output.txt",
                        "kind": "file",
                        "minimum_count": 1,
                        "maximum_count": 1,
                    }
                ],
                "public_evidence": [],
            }
        ],
    }


class BinderExecutorTests(unittest.TestCase):
    def setUp(self) -> None:
        self.temporary = tempfile.TemporaryDirectory()
        self.workspace = Path(self.temporary.name)
        self.runtime = self.workspace / ".runtime" / "binder-round"

    def tearDown(self) -> None:
        self.temporary.cleanup()

    def test_real_execution_requires_explicit_authorization(self) -> None:
        with self.assertRaisesRegex(binder_executor.BinderExecutorError, "explicit authorization"):
            binder_executor.run_adapter(
                adapter_registry(),
                "fixture-adapter",
                workspace_root=self.workspace,
                runtime_root=self.runtime,
            )

    def test_shipped_registry_validates_and_boltz_readiness_needs_no_run_bindings(self) -> None:
        registry = json.loads((ROOT / "references" / "binder-execution-adapters.json").read_text())
        validated = binder_executor.validate_registry(registry)
        self.assertEqual(len(validated["adapters"]), len(registry["adapters"]))
        result = binder_executor.run_adapter(
            registry,
            "boltz-local-v1",
            workspace_root=self.workspace,
            runtime_root=self.runtime,
            operation="readiness",
            dry_run=True,
        )
        self.assertEqual(result["operation"], "readiness")
        self.assertIn(result["status"], {"planned"})

    def test_dry_run_starts_no_process_and_writes_a_sanitized_receipt(self) -> None:
        result = binder_executor.run_adapter(
            adapter_registry(program="missing-fixture-program", required_environment_names=["FIXTURE_TOKEN"]),
            "fixture-adapter",
            workspace_root=self.workspace,
            runtime_root=self.runtime,
            dry_run=True,
            source_environment={"FIXTURE_TOKEN": "secret-value", "UNDECLARED_SECRET": "other-secret"},
        )
        self.assertFalse(result["ok"])
        self.assertEqual(result["status"], "planned")
        receipt = (self.workspace / result["receipt_path"]).read_text()
        self.assertNotIn("secret-value", receipt)
        self.assertNotIn("other-secret", receipt)
        self.assertEqual(json.loads(receipt)["environment_names"], ["FIXTURE_TOKEN"])

    def test_local_adapter_runs_with_shell_false_and_records_success(self) -> None:
        result = binder_executor.run_adapter(
            adapter_registry(),
            "fixture-adapter",
            workspace_root=self.workspace,
            runtime_root=self.runtime,
            authorization=binder_executor.LOCAL_EXECUTION_AUTHORIZATION,
        )
        self.assertTrue(result["ok"], result)
        self.assertEqual(result["returncode"], 0)
        self.assertEqual(result["status"], "completed")
        self.assertTrue((self.workspace / result["receipt_path"]).is_file())
        self.assertTrue((self.runtime / result["log_path"]).is_file())

    def test_registry_rejects_shell_programs_and_inline_code(self) -> None:
        with self.assertRaisesRegex(binder_executor.BinderExecutorError, "shell program"):
            binder_executor.validate_registry(adapter_registry(program="sh"))
        with self.assertRaisesRegex(binder_executor.BinderExecutorError, "inline-code"):
            binder_executor.validate_registry(adapter_registry(program="python3", command_argv=["-c", "pass"]))

    def test_registry_rejects_a_placeholder_in_the_program(self) -> None:
        with self.assertRaisesRegex(binder_executor.BinderExecutorError, "static program name"):
            binder_executor.validate_registry(adapter_registry(program="{{program}}"))

    def test_registry_requires_a_real_output_contract(self) -> None:
        with self.assertRaisesRegex(binder_executor.BinderExecutorError, "non-empty list"):
            binder_executor.validate_registry(adapter_registry(expected_outputs=[]))
        with self.assertRaisesRegex(binder_executor.BinderExecutorError, "positive integer"):
            binder_executor.validate_registry(
                adapter_registry(
                    expected_outputs=[
                        {
                            "id": "result",
                            "path_template": "output.txt",
                            "kind": "file",
                            "minimum_count": 0,
                        }
                    ]
                )
            )

    def test_legacy_registry_requires_explicit_capability_migration(self) -> None:
        registry = adapter_registry()
        adapter = registry["adapters"][0]
        del adapter["supported_selections"]
        del adapter["supported_routes"]
        with self.assertRaisesRegex(
            binder_executor.BinderExecutorError,
            "must declare supported_routes, supported_selections; add explicit selection and route capabilities",
        ):
            binder_executor.validate_registry(registry)

    def test_runtime_bindings_are_typed_and_cannot_escape_runtime(self) -> None:
        registry = adapter_registry(
            command_argv=["--count", "{{count}}", "--out", "{{output_path}}"],
            placeholders={
                "count": {"type": "integer", "minimum": 1},
                "output_path": {"type": "path"},
            },
        )
        with self.assertRaisesRegex(binder_executor.BinderExecutorError, "must be an integer"):
            binder_executor.run_adapter(
                registry,
                "fixture-adapter",
                workspace_root=self.workspace,
                runtime_root=self.runtime,
                bindings={"count": "1", "output_path": "output.json"},
                dry_run=True,
            )
        with self.assertRaisesRegex(binder_executor.BinderExecutorError, "outside the runtime root"):
            binder_executor.run_adapter(
                registry,
                "fixture-adapter",
                workspace_root=self.workspace,
                runtime_root=self.runtime,
                bindings={"count": 1, "output_path": "../../output.json"},
                dry_run=True,
            )

    def test_runtime_root_must_stay_below_dot_runtime(self) -> None:
        with self.assertRaisesRegex(binder_executor.BinderExecutorError, "below .runtime"):
            binder_executor.run_adapter(
                adapter_registry(),
                "fixture-adapter",
                workspace_root=self.workspace,
                runtime_root=self.workspace / "outside",
                dry_run=True,
            )

    def test_missing_program_and_environment_are_readiness_facts(self) -> None:
        result = binder_executor.run_adapter(
            adapter_registry(program="missing-fixture-program", required_environment_names=["MISSING_NAME"]),
            "fixture-adapter",
            workspace_root=self.workspace,
            runtime_root=self.runtime,
            operation="readiness",
            authorization=binder_executor.LOCAL_EXECUTION_AUTHORIZATION,
            source_environment={},
        )
        self.assertFalse(result["ok"])
        self.assertEqual(result["status"], "blocked")
        self.assertEqual(result["missing_environment_names"], ["MISSING_NAME"])
        self.assertIn("program was not found", result["findings"])

    def test_adapter_required_can_run_when_registry_supplies_a_safe_command(self) -> None:
        result = binder_executor.run_adapter(
            adapter_registry(implementation_status="adapter_required"),
            "fixture-adapter",
            workspace_root=self.workspace,
            runtime_root=self.runtime,
            authorization=binder_executor.LOCAL_EXECUTION_AUTHORIZATION,
        )
        self.assertTrue(result["ok"], result)

    def test_built_in_without_an_argv_contract_is_reported_cleanly(self) -> None:
        with self.assertRaisesRegex(binder_executor.BinderExecutorError, "no local argv execution contract"):
            binder_executor.run_adapter(
                adapter_registry(execution_kind="built_in"),
                "fixture-adapter",
                workspace_root=self.workspace,
                runtime_root=self.runtime,
                authorization=binder_executor.LOCAL_EXECUTION_AUTHORIZATION,
            )

    def test_timeout_and_nonzero_exit_cannot_report_success(self) -> None:
        timed = binder_executor.run_adapter(
            adapter_registry(program="sleep", command_argv=["2"]),
            "fixture-adapter",
            workspace_root=self.workspace,
            runtime_root=self.runtime,
            authorization=binder_executor.LOCAL_EXECUTION_AUTHORIZATION,
            timeout_seconds=1,
        )
        self.assertFalse(timed["ok"])
        self.assertTrue(timed["timed_out"])
        failed = binder_executor.run_adapter(
            adapter_registry(program="false"),
            "fixture-adapter",
            workspace_root=self.workspace,
            runtime_root=self.runtime,
            authorization=binder_executor.LOCAL_EXECUTION_AUTHORIZATION,
        )
        self.assertFalse(failed["ok"])
        self.assertNotEqual(failed["returncode"], 0)

    def test_output_count_content_and_hash_are_validated(self) -> None:
        output = self.runtime / "outputs" / "rows.jsonl"
        output.parent.mkdir(parents=True)
        output.write_text('{"candidate_id":"one"}\n', encoding="utf-8")
        result = binder_executor.run_adapter(
            adapter_registry(
                expected_outputs=[
                    {"id": "rows", "path_template": "outputs/*.jsonl", "kind": "jsonl", "minimum_count": 1, "maximum_count": 1}
                ]
            ),
            "fixture-adapter",
            workspace_root=self.workspace,
            runtime_root=self.runtime,
            authorization=binder_executor.LOCAL_EXECUTION_AUTHORIZATION,
        )
        self.assertTrue(result["ok"], result)
        file_record = result["outputs"][0]["files"][0]
        self.assertEqual(file_record["records"], 1)
        self.assertRegex(file_record["sha256"], r"^[0-9a-f]{64}$")
        output.unlink()
        missing = binder_executor.run_adapter(
            adapter_registry(
                expected_outputs=[
                    {"id": "rows", "path_template": "outputs/*.jsonl", "kind": "jsonl", "minimum_count": 1, "maximum_count": 1}
                ]
            ),
            "fixture-adapter",
            workspace_root=self.workspace,
            runtime_root=self.runtime,
            authorization=binder_executor.LOCAL_EXECUTION_AUTHORIZATION,
        )
        self.assertFalse(missing["ok"])
        self.assertIn("declared output count is below minimum_count", missing["findings"])

    def test_directory_output_receipt_hashes_each_bundle_member(self) -> None:
        bundle = self.runtime / "outputs" / "bundle"
        (bundle / "structures").mkdir(parents=True)
        (bundle / "manifest.json").write_text('{"bundle_id":"synthetic"}\n', encoding="utf-8")
        (bundle / "structures" / "candidate.pdb").write_text(
            "ATOM      1  CA  ALA A   1       0.000   0.000   0.000  1.00 20.00           C\n",
            encoding="utf-8",
        )
        result = binder_executor.run_adapter(
            adapter_registry(
                expected_outputs=[
                    {
                        "id": "bundle",
                        "path_template": "outputs/bundle",
                        "kind": "directory",
                        "minimum_count": 1,
                        "maximum_count": 1,
                    }
                ]
            ),
            "fixture-adapter",
            workspace_root=self.workspace,
            runtime_root=self.runtime,
            authorization=binder_executor.LOCAL_EXECUTION_AUTHORIZATION,
        )
        self.assertTrue(result["ok"], result)
        artifact = result["outputs"][0]["files"][0]
        self.assertEqual(2, artifact["records"])
        self.assertEqual(
            ["manifest.json", "structures/candidate.pdb"],
            [member["path"] for member in artifact["members"]],
        )
        self.assertEqual(
            sum(member["bytes"] for member in artifact["members"]),
            artifact["bytes"],
        )
        self.assertTrue(all(member["records"] == 1 for member in artifact["members"]))
        self.assertTrue(all(len(member["sha256"]) == 64 for member in artifact["members"]))

    def test_subprocess_receipt_does_not_echo_secret_values(self) -> None:
        value = "private-secret-value"
        result = binder_executor.run_adapter(
            adapter_registry(program="false", required_environment_names=["FIXTURE_TOKEN"]),
            "fixture-adapter",
            workspace_root=self.workspace,
            runtime_root=self.runtime,
            authorization=binder_executor.LOCAL_EXECUTION_AUTHORIZATION,
            source_environment={"FIXTURE_TOKEN": value},
        )
        receipt = (self.workspace / result["receipt_path"]).read_text()
        self.assertNotIn(value, receipt)


if __name__ == "__main__":
    unittest.main()
