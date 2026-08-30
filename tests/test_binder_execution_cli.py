from __future__ import annotations

import io
import json
import tempfile
import unittest
from contextlib import redirect_stdout
from pathlib import Path

from biosymphony_structure_factory.cli import main


ROOT = Path(__file__).resolve().parents[1]


class BinderExecutionCliTests(unittest.TestCase):
    def call(self, argv: list[str]) -> tuple[int, dict]:
        output = io.StringIO()
        with redirect_stdout(output):
            status = main(argv)
        return status, json.loads(output.getvalue())

    def test_adapters_lists_the_validated_registry(self) -> None:
        status, payload = self.call(["binder-lane", "adapters", "--workspace", str(ROOT)])
        self.assertEqual(0, status)
        registry = json.loads((ROOT / "references/binder-execution-adapters.json").read_text(encoding="utf-8"))
        self.assertEqual(len(registry["adapters"]), payload["adapter_count"])
        self.assertTrue(any(row["id"] == "boltz-local-v1" for row in payload["adapters"]))
        self.assertEqual(0, payload["provider_calls"])

    def test_adapter_dry_run_starts_no_process_and_real_check_needs_authorization(self) -> None:
        (ROOT / ".runtime").mkdir(exist_ok=True)
        with tempfile.TemporaryDirectory(dir=ROOT / ".runtime") as temporary:
            relative = Path(temporary).relative_to(ROOT).as_posix()
            status, payload = self.call(
                [
                    "binder-lane",
                    "adapter",
                    "boltz-local-v1",
                    "--workspace",
                    str(ROOT),
                    "--run-root",
                    relative,
                    "--operation",
                    "readiness",
                    "--dry-run",
                ]
            )
            self.assertIn(status, {0, 1})
            self.assertTrue(payload["dry_run"])
            self.assertIsNone(payload["returncode"])

            status, payload = self.call(
                [
                    "binder-lane",
                    "adapter",
                    "boltz-local-v1",
                    "--workspace",
                    str(ROOT),
                    "--run-root",
                    relative,
                    "--operation",
                    "readiness",
                ]
            )
            self.assertEqual(2, status)
            self.assertIn("explicit authorization", payload["error"])

    def test_round_decision_evaluates_closed_round_without_provider_calls(self) -> None:
        (ROOT / ".runtime").mkdir(exist_ok=True)
        with tempfile.TemporaryDirectory(dir=ROOT / ".runtime") as temporary:
            runtime_root = Path(temporary)
            relative_root = runtime_root.relative_to(ROOT)
            plan_path = relative_root / "plan.json"
            status, _ = self.call(
                [
                    "binder-lane",
                    "plan-request",
                    "examples/pd-l1-binder-design-public/binder-round-request.json",
                    "--workspace",
                    str(ROOT),
                    "--out",
                    plan_path.as_posix(),
                ]
            )
            self.assertEqual(0, status)
            history_path = runtime_root / "round-history.json"
            history_path.write_text(
                json.dumps(
                    [
                        {
                            "round_index": 1,
                            "primary_metric_value": 0.8,
                            "actual_spend_usd": 60,
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
                    ]
                )
                + "\n",
                encoding="utf-8",
            )
            decision_path = relative_root / "round-decision.json"
            status, payload = self.call(
                [
                    "binder-lane",
                    "round-decision",
                    plan_path.as_posix(),
                    "--workspace",
                    str(ROOT),
                    "--history",
                    history_path.relative_to(ROOT).as_posix(),
                    "--out",
                    decision_path.as_posix(),
                ]
            )
            self.assertEqual(0, status)
            self.assertEqual("stop", payload["decision"])
            self.assertEqual("budget_ceiling_reached", payload["reason"])
            self.assertEqual(0, payload["provider_calls"])
            self.assertTrue((ROOT / decision_path).is_file())

    def test_closeout_refuses_false_success(self) -> None:
        (ROOT / ".runtime").mkdir(exist_ok=True)
        with tempfile.TemporaryDirectory(dir=ROOT / ".runtime") as temporary:
            run_root = Path(temporary)
            output_root = run_root / "outputs"
            output_root.mkdir()
            (output_root / "ranking.json").write_text("{}\n", encoding="utf-8")
            declarations = run_root / "declarations.json"
            declarations.write_text(
                json.dumps(
                    [
                        {"artifact_id": "ranking", "path": "outputs/ranking.json"},
                        {"artifact_id": "summary", "path": "outputs/summary.json"},
                    ]
                )
                + "\n",
                encoding="utf-8",
            )
            relative = run_root.relative_to(ROOT).as_posix()
            status, payload = self.call(
                [
                    "binder-lane",
                    "closeout",
                    "--workspace",
                    str(ROOT),
                    relative,
                    "--stage-id",
                    "score",
                    "--artifact-root",
                    "outputs",
                    "--declarations",
                    declarations.relative_to(ROOT).as_posix(),
                    "--exit-code",
                    "0",
                ]
            )
            self.assertEqual(1, status)
            self.assertFalse(payload["ok"])
            self.assertEqual("failed", payload["execution_state"])
            self.assertEqual(2, payload["expected_output_count"])
            self.assertEqual(1, payload["found_output_count"])


if __name__ == "__main__":
    unittest.main()
