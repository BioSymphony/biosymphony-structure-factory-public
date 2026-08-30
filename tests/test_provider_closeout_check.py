from __future__ import annotations

import json
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]


class ProviderCloseoutCheckTests(unittest.TestCase):
    def run_json(self, *args: str, check: bool = True) -> tuple[int, dict]:
        result = subprocess.run(
            [sys.executable, *args],
            cwd=ROOT,
            check=check,
            text=True,
            capture_output=True,
        )
        return result.returncode, json.loads(result.stdout)

    def write_provider_native_closeout(self, root: Path) -> Path:
        validation = root / "validation"
        validation.mkdir(parents=True)
        (root / "results.json").write_text(json.dumps({"ok": True, "result": "fixture"}))
        (root / "stage-progress.jsonl").write_text(
            json.dumps(
                {
                    "schema_version": 1,
                    "timestamp": "2026-05-08T00:00:00+00:00",
                    "run_id": "provider-closeout-fixture",
                    "stage_id": "artifact_verifying",
                    "status": "completed",
                }
            )
            + "\n"
        )
        (root / "executed-commands.jsonl").write_text(
            json.dumps(
                {
                    "schema_version": 1,
                    "timestamp": "2026-05-08T00:00:00+00:00",
                    "stage_id": "screening",
                    "command": "fixture command recorded by test",
                    "exit_code": 0,
                }
            )
            + "\n"
        )
        (validation / "input-audit.json").write_text(json.dumps({"ok": True, "missing_operator_items": []}))
        (validation / "contract-self-check.json").write_text(
            json.dumps({"ok": True, "claim_level": "processed", "evidence_mode": "provider_native"})
        )
        (validation / "artifact-pull-report.json").write_text(
            json.dumps(
                {
                    "schema_version": 1,
                    "provider": "runpod",
                    "run_id": "provider-closeout-fixture",
                    "overall_status": "OK",
                    "artifacts": [
                        {
                            "declared_path": "results.json",
                            "local_path": str(root / "results.json"),
                            "required": True,
                            "bytes": (root / "results.json").stat().st_size,
                            "sha256": "recorded-in-fixture",
                            "hash_status": "matched",
                            "format": "json",
                            "format_ok": True,
                            "proxy_error_body": False,
                            "accepted": True,
                        }
                    ],
                }
            )
        )
        (root / "cost_report.json").write_text(
            json.dumps(
                {
                    "schema_version": 1,
                    "provider": "runpod",
                    "run_id": "provider-closeout-fixture",
                    "total_cost_usd": 0.25,
                    "max_authorized_spend_usd": 1.0,
                    "budget_status": "within_budget",
                }
            )
        )
        (root / "cleanup_proof.json").write_text(
            json.dumps(
                {
                    "schema_version": 1,
                    "provider": "runpod",
                    "run_id": "provider-closeout-fixture",
                    "cleanup": {"requested": True, "verified": True, "policy": "delete_pod"},
                    "overall_status": "verified",
                }
            )
        )
        (root / "validation_ledger.json").write_text(
            json.dumps({"schema_version": 1, "overall_claim_level": "processed", "evidence_mode": "provider_native"})
        )
        (root / "provenance.md").write_text("# provenance\n")
        provider_run = root / "provider-run.json"
        provider_run.write_text(
            json.dumps(
                {
                    "schema_version": 1,
                    "provider": "runpod",
                    "run_id": "provider-closeout-fixture",
                    "status": "cleanup_verified",
                    "desired_status": "COMPLETED",
                    "actual_status": "COMPLETED",
                    "runtime_uptime_seconds": 120,
                    "claim_level": "processed",
                    "evidence_mode": "provider_native",
                    "errors": [],
                }
            )
        )
        return provider_run

    def test_provider_native_closeout_fixture_passes(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            provider_run = self.write_provider_native_closeout(root)
            _code, summary = self.run_json(
                "scripts/structure_factory/provider_closeout_check.py",
                "--provider-run",
                str(provider_run),
                "--artifact-root",
                str(root),
                "--execution-mode",
                "real",
                "--json",
            )
        self.assertTrue(summary["ok"], summary)
        self.assertTrue(summary["closeout_ready"], summary)
        self.assertEqual(summary["closeout_status"], "closeout_ready")

    def test_intent_only_provider_state_blocks_real_closeout(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            provider_run = Path(tmp) / "provider-run.json"
            provider_run.write_text(
                json.dumps(
                    {
                        "schema_version": 1,
                        "provider": "runpod",
                        "run_id": "intent-only-fixture",
                        "status": "running",
                        "desired_status": "RUNNING",
                        "actual_status": None,
                        "runtime_uptime_seconds": 0,
                        "claim_level": "validated",
                        "evidence_mode": "provider_native",
                    }
                )
            )
            code, summary = self.run_json(
                "scripts/structure_factory/provider_closeout_check.py",
                "--provider-run",
                str(provider_run),
                "--execution-mode",
                "real",
                "--json",
                check=False,
            )
        self.assertNotEqual(code, 0)
        self.assertFalse(summary["ok"], summary)
        self.assertTrue(any("intent-only" in error for error in summary["errors"]), summary)
        self.assertFalse(summary["closeout_ready"], summary)

    def test_cloud_shard_ledger_example_validates_as_prep_contract(self) -> None:
        _code, summary = self.run_json(
            "scripts/structure_factory/provider_closeout_check.py",
            "--shard-ledger",
            "examples/screening-superpowers/cloud-shard-ledger.example.json",
            "--execution-mode",
            "prep",
            "--json",
        )
        self.assertTrue(summary["ok"], summary)
        self.assertFalse(summary["closeout_ready"], summary)
        self.assertEqual(summary["shard_ledger"]["shard_count"], 3)
        self.assertEqual(summary["shard_ledger"]["blocked_or_planned_shards"], 3)


if __name__ == "__main__":
    unittest.main()
