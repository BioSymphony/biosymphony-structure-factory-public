from __future__ import annotations

import hashlib
import json
import tempfile
import time
import unittest
from pathlib import Path

from biosymphony_structure_factory.remote_dispatch import (
    DISPATCH_AUTHORIZATION,
    PROVIDER_ROUTES,
    RemoteDispatchError,
    dispatch_remote_tool,
    resolve_provider_route,
)
from biosymphony_structure_factory.remote_tool_contract import (
    CONTRACT_ID,
    RemoteToolContractError,
    validate_receipt,
)


ARTIFACT_PATH = "predictions/candidate-001.pdb"
ARTIFACT_BYTES = b"ATOM      1  CA  ALA A   1\n"
ARTIFACT_SHA256 = hashlib.sha256(ARTIFACT_BYTES).hexdigest()


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


def staging_adapter(status: str = "completed", *, sha256: str | None = ARTIFACT_SHA256):
    def adapter(request, context):
        staged = Path(context["attempt_dir"]) / ARTIFACT_PATH
        staged.parent.mkdir(parents=True, exist_ok=True)
        staged.write_bytes(ARTIFACT_BYTES)
        return {
            "status": status,
            "artifacts": [
                {"path": ARTIFACT_PATH, "sha256": sha256, "byte_count": len(ARTIFACT_BYTES)}
            ],
            "cost": {"reported_spend_usd": 1.25},
            "cleanup_verified": True,
        }

    return adapter


class RemoteDispatchTests(unittest.TestCase):
    def dispatch(self, tmp: Path, adapter=staging_adapter(), **overrides) -> dict:
        kwargs = {
            "attempt_dir": tmp / "attempt",
            "route": "serverless_gpu",
            "environment": {"PROVIDER_CREDENTIAL": "example-credential-value"},
            "authorization": DISPATCH_AUTHORIZATION,
        }
        kwargs.update(overrides)
        return dispatch_remote_tool(request_fixture(), adapter, **kwargs)

    def test_completed_dispatch_writes_joined_verified_receipt(self) -> None:
        with tempfile.TemporaryDirectory() as raw:
            tmp = Path(raw)
            outcome = self.dispatch(tmp)
            self.assertEqual("completed", outcome["status"])
            self.assertTrue(outcome["adapter_invoked"])
            self.assertEqual("serverless_gpu", outcome["provider_route"])
            self.assertEqual(1, outcome["artifact_count"])
            self.assertEqual(1.25, outcome["reported_spend_usd"])
            self.assertEqual([], outcome["findings"])
            receipt_path = tmp / "attempt" / "remote-tool-receipt.json"
            self.assertTrue(receipt_path.is_file())
            receipt = json.loads(receipt_path.read_text(encoding="utf-8"))
            self.assertEqual(ARTIFACT_SHA256, receipt["artifacts"][0]["sha256"])
            self.assertEqual(len(receipt["artifacts"]), receipt["artifact_count"])
            self.assertEqual(
                {
                    "max_spend_usd": 5.0,
                    "reported_spend_usd": 1.25,
                },
                receipt["cost"],
            )
            self.assertEqual(receipt, validate_receipt(receipt, request_fixture()))

    def test_receipt_joins_request_identity_without_leaking_credentials(self) -> None:
        with tempfile.TemporaryDirectory() as raw:
            tmp = Path(raw)
            outcome = self.dispatch(tmp)
            receipt = json.loads(
                (tmp / "attempt" / "remote-tool-receipt.json").read_text(encoding="utf-8")
            )
            request = request_fixture()
            for field in (
                "provider_id",
                "tool_id",
                "operation",
                "request_id",
                "source_identity",
                "model_identity",
                "environment_identity",
            ):
                self.assertEqual(request[field], receipt[field])
            self.assertNotIn("example-credential-value", json.dumps(outcome))
            receipt_text = (tmp / "attempt" / "remote-tool-receipt.json").read_text(encoding="utf-8")
            self.assertNotIn("example-credential-value", receipt_text)

    def test_missing_adapter_and_credentials_are_actionable_blocked_states(self) -> None:
        def fail_adapter(request, context):
            raise AssertionError("adapter must not be invoked for a blocked dispatch")

        with tempfile.TemporaryDirectory() as raw:
            tmp = Path(raw)
            outcome = dispatch_remote_tool(
                request_fixture(),
                None,
                attempt_dir=tmp / "attempt",
                route="serverless_gpu",
                environment={},
                authorization=DISPATCH_AUTHORIZATION,
            )
            self.assertEqual("blocked", outcome["status"])
            self.assertFalse(outcome["adapter_invoked"])
            self.assertTrue(any("adapter callable" in finding for finding in outcome["findings"]))
            self.assertFalse((tmp / "attempt" / "remote-tool-receipt.json").exists())

            outcome = self.dispatch(
                tmp,
                adapter=fail_adapter,
                environment={},
            )
            self.assertEqual("blocked", outcome["status"])
            self.assertFalse(outcome["adapter_invoked"])
            self.assertTrue(
                any("PROVIDER_CREDENTIAL" in finding for finding in outcome["findings"])
            )
            self.assertFalse((tmp / "attempt" / "remote-tool-receipt.json").exists())

    def test_dry_run_and_unauthorized_dispatch_never_invoke_the_adapter(self) -> None:
        def fail_adapter(request, context):
            raise AssertionError("adapter must not be invoked without authorization")

        with tempfile.TemporaryDirectory() as raw:
            tmp = Path(raw)
            outcome = self.dispatch(tmp, adapter=fail_adapter, dry_run=True)
            self.assertEqual("planned", outcome["status"])
            self.assertFalse(outcome["adapter_invoked"])
            self.assertFalse((tmp / "attempt" / "remote-tool-receipt.json").exists())

            with self.assertRaises(RemoteDispatchError):
                self.dispatch(tmp, adapter=fail_adapter, authorization=None)

    def test_route_identities_cover_every_provider_and_are_enforced(self) -> None:
        self.assertEqual(
            {
                "local",
                "api",
                "aws",
                "cloud_vm",
                "fal",
                "lambda",
                "modal",
                "neocloud",
                "runpod",
                "ssh_hpc",
            },
            set(PROVIDER_ROUTES),
        )
        self.assertEqual("workstation", resolve_provider_route("local", None))
        self.assertEqual("hosted_api", resolve_provider_route("api", None))
        self.assertEqual("slurm", resolve_provider_route("ssh_hpc", "slurm"))
        self.assertEqual("gpu_pod", resolve_provider_route("runpod", "gpu_pod"))
        self.assertEqual("serverless_gpu", resolve_provider_route("runpod", "serverless_gpu"))
        with self.assertRaises(RemoteDispatchError):
            resolve_provider_route("runpod", None)
        with self.assertRaises(RemoteDispatchError):
            resolve_provider_route("runpod", "batch")
        with self.assertRaises(RemoteDispatchError):
            resolve_provider_route("unknown-provider", "gpu_pod")

        with tempfile.TemporaryDirectory() as raw:
            tmp = Path(raw)
            request = request_fixture()
            request["provider_id"] = "local"
            request["credential_environment_keys"] = []
            outcome = dispatch_remote_tool(
                request,
                staging_adapter(),
                attempt_dir=tmp / "attempt",
                environment={},
                authorization=DISPATCH_AUTHORIZATION,
            )
            self.assertEqual("completed", outcome["status"])
            self.assertEqual("workstation", outcome["provider_route"])

    def test_budget_and_runtime_overruns_fail_the_receipt(self) -> None:
        def slow_adapter(request, context):
            time.sleep(0.02)
            return {
                "status": "completed",
                "artifacts": [],
                "cost": {"reported_spend_usd": 0},
                "cleanup_verified": True,
            }

        def overspending_adapter(request, context):
            return {
                "status": "completed",
                "artifacts": [],
                "cost": {"reported_spend_usd": 9.0},
                "cleanup_verified": True,
            }

        with tempfile.TemporaryDirectory() as raw:
            tmp = Path(raw)
            request = request_fixture()
            request["budget"] = {"max_spend_usd": 5.0, "max_runtime_seconds": 0.001}
            request["credential_environment_keys"] = []
            outcome = dispatch_remote_tool(
                request,
                slow_adapter,
                attempt_dir=tmp / "attempt",
                route="serverless_gpu",
                environment={},
                authorization=DISPATCH_AUTHORIZATION,
            )
            self.assertEqual("failed", outcome["status"])
            self.assertTrue(
                any("max_runtime_seconds" in finding for finding in outcome["findings"])
            )

            request = request_fixture()
            request["credential_environment_keys"] = []
            outcome = dispatch_remote_tool(
                request,
                overspending_adapter,
                attempt_dir=tmp / "attempt",
                route="serverless_gpu",
                environment={},
                authorization=DISPATCH_AUTHORIZATION,
            )
            self.assertEqual("failed", outcome["status"])
            self.assertTrue(any("max_spend_usd" in finding for finding in outcome["findings"]))
            receipt = json.loads(
                (tmp / "attempt" / "remote-tool-receipt.json").read_text(encoding="utf-8")
            )
            self.assertEqual("failed", receipt["status"])

    def test_hash_and_byte_count_mismatches_fail_the_receipt(self) -> None:
        with tempfile.TemporaryDirectory() as raw:
            tmp = Path(raw)
            outcome = self.dispatch(tmp, adapter=staging_adapter(sha256="b" * 64))
            self.assertEqual("failed", outcome["status"])
            self.assertTrue(any("hash does not match" in finding for finding in outcome["findings"]))

            # The attempt directory already stages the artifact; claim the wrong size.
            outcome = self.dispatch(
                tmp,
                adapter=lambda request, context: {
                    "status": "completed",
                    "artifacts": [
                        {"path": ARTIFACT_PATH, "sha256": ARTIFACT_SHA256, "byte_count": 999}
                    ],
                    "cost": {"reported_spend_usd": 0},
                    "cleanup_verified": True,
                },
            )
            self.assertEqual("failed", outcome["status"])
            self.assertTrue(any("byte count" in finding for finding in outcome["findings"]))

    def test_missing_and_escaping_artifacts_fail_the_receipt(self) -> None:
        with tempfile.TemporaryDirectory() as raw:
            tmp = Path(raw)
            outcome = self.dispatch(
                tmp,
                adapter=lambda request, context: {
                    "status": "completed",
                    "artifacts": [
                        {"path": "predictions/missing.pdb", "sha256": ARTIFACT_SHA256, "byte_count": 10}
                    ],
                    "cost": {"reported_spend_usd": 0},
                    "cleanup_verified": True,
                },
            )
            self.assertEqual("failed", outcome["status"])
            self.assertTrue(any("is missing" in finding for finding in outcome["findings"]))

            outcome = self.dispatch(
                tmp,
                adapter=lambda request, context: {
                    "status": "completed",
                    "artifacts": [
                        {"path": "../escape.pdb", "sha256": ARTIFACT_SHA256, "byte_count": 10}
                    ],
                    "cost": {"reported_spend_usd": 0},
                    "cleanup_verified": True,
                },
            )
            self.assertEqual("failed", outcome["status"])
            self.assertTrue(any("attempt directory" in finding for finding in outcome["findings"]))
            self.assertFalse((tmp / "remote-tool-receipt.json").exists())

    def test_invalid_adapter_results_are_rejected_without_shell_or_secrets(self) -> None:
        bad_results = [
            {"status": "completed", "artifacts": [], "cost": {"reported_spend_usd": 0}},
            {
                "status": "completed",
                "artifacts": [],
                "cost": {"reported_spend_usd": 0},
                "cleanup_verified": True,
                "command": "python tool.py",
            },
            {
                "status": "scheduled",
                "artifacts": [],
                "cost": {"reported_spend_usd": 0},
                "cleanup_verified": True,
            },
            {
                "status": "completed",
                "artifacts": [],
                "cost": {"reported_spend_usd": -1},
                "cleanup_verified": True,
            },
        ]
        with tempfile.TemporaryDirectory() as raw:
            tmp = Path(raw)
            for result in bad_results:
                with self.assertRaises(RemoteDispatchError):
                    self.dispatch(tmp, adapter=lambda request, context: result)

    def test_adapter_exception_fails_without_writing_a_receipt(self) -> None:
        def raising_adapter(request, context):
            raise RuntimeError("provider transport unavailable")

        with tempfile.TemporaryDirectory() as raw:
            tmp = Path(raw)
            outcome = self.dispatch(tmp, adapter=raising_adapter)
            self.assertEqual("failed", outcome["status"])
            self.assertTrue(outcome["adapter_invoked"])
            self.assertIsNone(outcome["receipt_path"])
            self.assertTrue(any("RuntimeError" in finding for finding in outcome["findings"]))
            self.assertFalse((tmp / "attempt" / "remote-tool-receipt.json").exists())

    def test_unverified_cleanup_blocks_the_receipt(self) -> None:
        def unclean_adapter(request, context):
            return {
                "status": "completed",
                "artifacts": [
                    {"path": ARTIFACT_PATH, "sha256": ARTIFACT_SHA256, "byte_count": len(ARTIFACT_BYTES)}
                ],
                "cost": {"reported_spend_usd": 0.5},
                "cleanup_verified": False,
            }

        with tempfile.TemporaryDirectory() as raw:
            tmp = Path(raw)
            outcome = self.dispatch(tmp, adapter=unclean_adapter)
            self.assertEqual("blocked", outcome["status"])
            self.assertIsNone(outcome["receipt_path"])
            self.assertTrue(any("cleanup" in finding for finding in outcome["findings"]))

    def test_adapter_receives_a_request_copy_and_readonly_contract_error_propagates(self) -> None:
        seen = {}

        def recording_adapter(request, context):
            seen["request"] = request
            seen["context"] = context
            return {
                "status": "completed",
                "artifacts": [
                    {"path": ARTIFACT_PATH, "sha256": ARTIFACT_SHA256, "byte_count": len(ARTIFACT_BYTES)}
                ],
                "cost": {"reported_spend_usd": 0},
                "cleanup_verified": True,
            }

        request = request_fixture()
        with tempfile.TemporaryDirectory() as raw:
            tmp = Path(raw)
            self.dispatch(tmp, adapter=recording_adapter)
        self.assertIsNot(request["input_payload"], seen["request"]["input_payload"])
        request["input_payload"]["output_format"] = "mutated"
        self.assertEqual("pdb", seen["request"]["input_payload"]["output_format"])
        self.assertEqual({"PROVIDER_CREDENTIAL": "example-credential-value"}, seen["context"]["credential_environment"])
        self.assertEqual(5.0, seen["context"]["budget"]["max_spend_usd"])

        with self.assertRaises(RemoteToolContractError):
            dispatch_remote_tool(
                {"schema_version": 1},
                staging_adapter(),
                attempt_dir="unused",
                route="serverless_gpu",
                environment={},
                authorization=DISPATCH_AUTHORIZATION,
            )


if __name__ == "__main__":
    unittest.main()
