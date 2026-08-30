from __future__ import annotations

import copy
import json
import tempfile
import unittest
from pathlib import Path

from biosymphony_structure_factory.remediation import failure_record
from biosymphony_structure_factory.remote_tool_contract import (
    CONTRACT_ID,
    RemoteToolContractError,
    validate_receipt,
    validate_request,
)
from biosymphony_structure_factory.target_verifier import TargetVerificationError, verify_target


ROOT = Path(__file__).resolve().parents[1]
SCHEMA_NAMES = (
    "binder-remote-tool-request.schema.json",
    "binder-remote-tool-receipt.schema.json",
    "binder-target-verification-report.schema.json",
    "binder-metric-provenance.schema.json",
    "binder-failure-record.schema.json",
)
MIRROR_DIRECTORIES = (
    ROOT / "skills" / "binder-lane-round" / "references" / "schemas",
    ROOT / "skills" / "biosymphony-structure-factory" / "references" / "schemas",
)


def request_fixture() -> dict:
    return {
        "schema_version": 1,
        "contract_id": CONTRACT_ID,
        "provider_id": "modal",
        "tool_id": "esmfold2-fast",
        "operation": "predict",
        "request_id": "cofold-0123456789abcdef0123456789abcdef",
        "input_payload": {"input_manifest": "inputs/synthetic-candidates.jsonl"},
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
                "path": "predictions/synthetic-candidate.pdb",
                "sha256": "a" * 64,
                "byte_count": 128,
            }
        ],
        "cleanup": {"verified": True},
    }


def pdb_atom(serial: int, residue: str, chain: str, number: int) -> str:
    return (
        f"ATOM  {serial:>5d}  CA  {residue:>3s} {chain}{number:>4d}    "
        f"{float(serial):>8.3f}{0.0:>8.3f}{0.0:>8.3f}  1.00 20.00           C"
    )


def target_report_fixture() -> dict:
    with tempfile.TemporaryDirectory() as temporary:
        path = Path(temporary) / "synthetic-target.pdb"
        path.write_text(
            "\n".join(
                [
                    pdb_atom(1, "ALA", "A", 19),
                    pdb_atom(2, "GLY", "A", 20),
                    pdb_atom(3, "SER", "A", 21),
                    "END",
                    "",
                ]
            ),
            encoding="utf-8",
        )
        return verify_target(
            path,
            target_contract={
                "input_posture": "synthetic",
                "label": "Synthetic target",
                "public_accession": "SYNTHETIC:schema-fixture",
                "window": "chain A residues 19-21",
                "site": {
                    "chain_id": "A",
                    "required_residues": ["19-21"],
                },
            },
            plan_sha256="c" * 64,
            expected_sequence="AGS",
        )


class BinderContractSchemaTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        cls.schemas = {
            name: json.loads((ROOT / "schemas" / name).read_text(encoding="utf-8"))
            for name in SCHEMA_NAMES
        }

    def validator(self, name: str):
        try:
            from jsonschema import Draft202012Validator
        except ImportError:
            self.skipTest("jsonschema is optional")
        return Draft202012Validator(self.schemas[name])

    def assert_invalid(self, name: str, value: object) -> None:
        validator = self.validator(name)
        self.assertFalse(validator.is_valid(value), list(validator.iter_errors(value)))

    def test_schema_files_fail_closed_and_portable_mirrors_match(self) -> None:
        for name, schema in self.schemas.items():
            with self.subTest(name=name):
                self.assertIs(False, schema["additionalProperties"])
                canonical = (ROOT / "schemas" / name).read_bytes()
                for mirror_directory in MIRROR_DIRECTORIES:
                    self.assertEqual(canonical, (mirror_directory / name).read_bytes())

    def test_schemas_are_valid_draft_2020_12(self) -> None:
        try:
            from jsonschema import Draft202012Validator
        except ImportError:
            self.skipTest("jsonschema is optional")
        for name, schema in self.schemas.items():
            with self.subTest(name=name):
                Draft202012Validator.check_schema(schema)

    def test_runtime_records_validate_against_their_public_schemas(self) -> None:
        request = validate_request(request_fixture())
        receipt = validate_receipt(receipt_fixture(request), request)
        local_request_payload = request_fixture()
        local_request_payload["provider_id"] = "local"
        local_request_payload["credential_environment_keys"] = []
        local_request = validate_request(local_request_payload)
        dispatch_receipt_payload = receipt_fixture(local_request)
        dispatch_receipt_payload["artifact_count"] = 1
        dispatch_receipt_payload["cost"] = {
            "max_spend_usd": local_request["budget"]["max_spend_usd"],
            "reported_spend_usd": 0.0,
        }
        dispatch_receipt = validate_receipt(dispatch_receipt_payload, local_request)
        metric_provenance = {
            "metric_id": "cofold-confidence-proxy",
            "metric_source": "stage_closeout",
            "source_artifact_sha256": "b" * 64,
            "calibration_state": "calibrated",
            "calibration_scope_id": "public-calibration",
            "calibration_artifact_sha256": "c" * 64,
        }
        failure_errors = (
            ValueError("metric provenance is incomplete"),
            TargetVerificationError("chain A lacks required coordinate residues"),
            ValueError("explicit authorization is required"),
            ValueError("budget ceiling reached"),
            ValueError("artifact output sha-256 mismatch"),
            ValueError("program readiness is incomplete"),
            ValueError("license terms require review"),
            ValueError("secret value is not allowed"),
            RemoteToolContractError("request does not match the remote contract"),
            ValueError("invalid declared field"),
        )

        self.validator("binder-remote-tool-request.schema.json").validate(request)
        self.validator("binder-remote-tool-receipt.schema.json").validate(receipt)
        self.validator("binder-remote-tool-request.schema.json").validate(local_request)
        self.validator("binder-remote-tool-receipt.schema.json").validate(dispatch_receipt)
        self.validator("binder-target-verification-report.schema.json").validate(target_report_fixture())
        self.validator("binder-metric-provenance.schema.json").validate(metric_provenance)
        failure_validator = self.validator("binder-failure-record.schema.json")
        for error in failure_errors:
            with self.subTest(error=type(error).__name__):
                failure_validator.validate(failure_record(error))

    def test_contract_schemas_reject_missing_or_inconsistent_records(self) -> None:
        request = request_fixture()
        unsafe_request = copy.deepcopy(request)
        unsafe_request["command"] = "synthetic-placeholder"
        self.assert_invalid("binder-remote-tool-request.schema.json", unsafe_request)

        nested_unsafe_request = copy.deepcopy(request)
        nested_unsafe_request["input_payload"] = {"nested": {"command": "synthetic-placeholder"}}
        self.assert_invalid("binder-remote-tool-request.schema.json", nested_unsafe_request)

        traversal_request = copy.deepcopy(request)
        traversal_request["artifact_prefix"] = "runs/../outside"
        self.assert_invalid("binder-remote-tool-request.schema.json", traversal_request)

        receipt = receipt_fixture(request)
        receipt["artifacts"] = []
        self.assert_invalid("binder-remote-tool-receipt.schema.json", receipt)

        traversal_receipt = receipt_fixture(request)
        traversal_receipt["artifacts"][0]["path"] = "../outside"
        self.assert_invalid("binder-remote-tool-receipt.schema.json", traversal_receipt)

        target_report = target_report_fixture()
        target_report["sequence"] = "AGS"
        self.assert_invalid("binder-target-verification-report.schema.json", target_report)

        synthetic_metric = {
            "metric_id": "cofold-confidence-proxy",
            "metric_source": "synthetic_fixture",
            "source_artifact_sha256": "d" * 64,
            "calibration_state": "not_applicable",
            "calibration_scope_id": "synthetic-demo",
            "calibration_artifact_sha256": None,
        }
        self.assert_invalid("binder-metric-provenance.schema.json", synthetic_metric)

        failure = failure_record(TargetVerificationError("target chain mismatch"))
        failure["category"] = "budget"
        self.assert_invalid("binder-failure-record.schema.json", failure)


if __name__ == "__main__":
    unittest.main()
