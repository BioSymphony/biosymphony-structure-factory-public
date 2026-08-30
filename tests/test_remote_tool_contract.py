from __future__ import annotations

import io
import json
import tempfile
import unittest
from contextlib import redirect_stdout
from pathlib import Path

from biosymphony_structure_factory.cli import main
from biosymphony_structure_factory.remote_tool_contract import (
    CONTRACT_ID,
    RemoteToolContractError,
    build_stage_request,
    validate_receipt,
    validate_request,
)


ROOT = Path(__file__).resolve().parents[1]


def request_fixture() -> dict:
    return {
        "schema_version": 1,
        "contract_id": CONTRACT_ID,
        "provider_id": "modal",
        "tool_id": "esmfold2-fast",
        "operation": "predict",
        "request_id": "cofold-0123456789abcdef0123456789abcdef",
        "input_payload": {
            "input_manifest": "inputs/candidates.jsonl",
            "output_format": "pdb",
        },
        "artifact_prefix": "runs/cofold-0123456789abcdef0123456789abcdef",
        "source_identity": "source-archive-sha256:synthetic-fixture",
        "model_identity": "model-release:reviewed-runtime-pin",
        "environment_identity": "container-digest:reviewed-runtime-pin",
        "credential_environment_keys": ["PROVIDER_CREDENTIAL"],
        "budget": {"max_spend_usd": 5.0, "max_runtime_seconds": 900},
    }


def receipt_fixture(request: dict) -> dict:
    return {
        "schema_version": 1,
        "contract_id": CONTRACT_ID,
        "provider_id": request["provider_id"],
        "tool_id": request["tool_id"],
        "operation": request["operation"],
        "request_id": request["request_id"],
        "source_identity": request["source_identity"],
        "model_identity": request["model_identity"],
        "environment_identity": request["environment_identity"],
        "status": "completed",
        "artifacts": [
            {
                "path": "predictions/candidate-001.pdb",
                "sha256": "a" * 64,
                "byte_count": 128,
            }
        ],
        "cleanup": {"verified": True},
    }


class RemoteToolContractTests(unittest.TestCase):
    def test_valid_request_and_receipt(self) -> None:
        request = request_fixture()
        self.assertEqual(request, validate_request(request))
        receipt = receipt_fixture(request)
        self.assertEqual(receipt, validate_receipt(receipt, request))

    def test_request_recursively_refuses_commands_secrets_and_controller_paths(self) -> None:
        for payload in (
            {"nested": {"argv": ["python", "tool.py"]}},
            {"nested": {"api_key": "credential-value"}},
            {"input_manifest": "/" + "Users/example/campaign/input.json"},
        ):
            with self.subTest(payload=payload):
                request = request_fixture()
                request["input_payload"] = payload
                with self.assertRaises(RemoteToolContractError):
                    validate_request(request)

    def test_completed_receipt_requires_artifacts_cleanup_and_exact_join(self) -> None:
        request = request_fixture()
        receipt = receipt_fixture(request)
        receipt["artifacts"] = []
        with self.assertRaises(RemoteToolContractError):
            validate_receipt(receipt, request)

        receipt = receipt_fixture(request)
        receipt["cleanup"] = {"verified": False}
        with self.assertRaises(RemoteToolContractError):
            validate_receipt(receipt, request)

        receipt = receipt_fixture(request)
        receipt["model_identity"] = "different-model"
        with self.assertRaises(RemoteToolContractError):
            validate_receipt(receipt, request)

    def test_stage_request_derives_attempt_identity_and_rejects_unsafe_fields(self) -> None:
        contract = {
            "provider_id": "runpod",
            "tool_id": "proteinmpnn",
            "operation": "design",
            "input_payload": {"input_manifest": "inputs/backbones.jsonl"},
            "credential_environment_keys": ["PROVIDER_CREDENTIAL"],
            "budget": {"max_spend_usd": 3, "max_runtime_seconds": 600},
            "receipt_path_template": "{{attempt_dir}}/remote-tool-receipt.json",
        }
        request = build_stage_request(
            contract,
            stage_id="sequence-design",
            attempt_id="0123456789abcdef0123456789abcdef",
            source_identity="source-sha256:reviewed",
            model_identity="model-release:reviewed",
            environment_identity="container-digest:reviewed",
        )
        self.assertEqual(
            "sequence-design-0123456789abcdef0123456789abcdef",
            request["request_id"],
        )
        self.assertEqual(f"runs/{request['request_id']}", request["artifact_prefix"])

        contract["command"] = "python arbitrary.py"
        with self.assertRaises(RemoteToolContractError):
            build_stage_request(
                contract,
                stage_id="sequence-design",
                attempt_id="0123456789abcdef0123456789abcdef",
                source_identity="source-sha256:reviewed",
                model_identity="model-release:reviewed",
                environment_identity="container-digest:reviewed",
            )

    def test_custom_registry_allows_a_reviewed_tool_without_relaxing_request_shape(self) -> None:
        request = request_fixture()
        request["tool_id"] = "user-selected-tool"
        request["operation"] = "predict"
        operations = {"user-selected-tool": ["predict", "toolcheck"]}
        self.assertEqual(request, validate_request(request, tool_operations=operations))

    def test_local_provider_id_is_a_registered_route(self) -> None:
        request = request_fixture()
        request["provider_id"] = "local"
        self.assertEqual(request, validate_request(request))

    def test_receipt_accepts_joined_artifact_count_and_cost_and_rejects_drift(self) -> None:
        request = request_fixture()
        receipt = receipt_fixture(request)
        receipt["artifact_count"] = 1
        receipt["cost"] = {"max_spend_usd": 5.0, "reported_spend_usd": 1.25}
        self.assertEqual(receipt, validate_receipt(receipt, request))

        drifted = dict(receipt)
        drifted["artifact_count"] = 2
        with self.assertRaises(RemoteToolContractError):
            validate_receipt(drifted, request)

        drifted = dict(receipt)
        drifted["cost"] = {"max_spend_usd": 4.0, "reported_spend_usd": 1.25}
        with self.assertRaises(RemoteToolContractError):
            validate_receipt(drifted, request)

        drifted = dict(receipt)
        drifted["cost"] = {"max_spend_usd": 5.0, "reported_spend_usd": 6.0}
        drifted["status"] = "failed"
        self.assertEqual(drifted, validate_receipt(drifted, request))


class RemoteToolContractCliTests(unittest.TestCase):
    def call(self, argv: list[str]) -> tuple[int, dict]:
        output = io.StringIO()
        with redirect_stdout(output):
            status = main(argv)
        return status, json.loads(output.getvalue())

    def test_cli_validates_request_and_joined_receipt_without_provider_calls(self) -> None:
        (ROOT / ".runtime").mkdir(exist_ok=True)
        with tempfile.TemporaryDirectory(dir=ROOT / ".runtime") as temporary:
            runtime = Path(temporary)
            request = request_fixture()
            receipt = receipt_fixture(request)
            request_path = runtime / "request.json"
            receipt_path = runtime / "receipt.json"
            request_path.write_text(json.dumps(request) + "\n", encoding="utf-8")
            receipt_path.write_text(json.dumps(receipt) + "\n", encoding="utf-8")

            status, payload = self.call(
                [
                    "binder-lane",
                    "remote-request",
                    request_path.relative_to(ROOT).as_posix(),
                    "--workspace",
                    str(ROOT),
                ]
            )
            self.assertEqual(0, status)
            self.assertEqual(0, payload["provider_calls"])
            self.assertEqual(request["request_id"], payload["request_id"])

            status, payload = self.call(
                [
                    "binder-lane",
                    "remote-receipt",
                    receipt_path.relative_to(ROOT).as_posix(),
                    "--request",
                    request_path.relative_to(ROOT).as_posix(),
                    "--workspace",
                    str(ROOT),
                ]
            )
            self.assertEqual(0, status)
            self.assertEqual(1, payload["artifact_count"])
            self.assertTrue(payload["cleanup_verified"])
            self.assertEqual(0, payload["provider_calls"])


if __name__ == "__main__":
    unittest.main()
