from __future__ import annotations

import io
import json
import tempfile
import unittest
from contextlib import redirect_stdout
from pathlib import Path

from biosymphony_structure_factory import binder_lane
from biosymphony_structure_factory.cli import main


ROOT = Path(__file__).resolve().parents[1]
FIXTURE = ROOT / "examples" / "binder-controls-synthetic"


class BinderControlsCliTests(unittest.TestCase):
    def call(self, argv: list[str]) -> tuple[int, dict]:
        output = io.StringIO()
        with redirect_stdout(output):
            status = main(argv)
        return status, json.loads(output.getvalue())

    def test_calibrate_controls_writes_a_ready_record(self) -> None:
        (ROOT / ".runtime").mkdir(exist_ok=True)
        with tempfile.TemporaryDirectory(dir=ROOT / ".runtime") as temporary:
            out = Path(temporary).relative_to(ROOT) / "calibration.json"

            status, payload = self.call(
                [
                    "binder-lane",
                    "calibrate-controls",
                    "examples/binder-controls-synthetic/control-panel.json",
                    "--workspace",
                    str(ROOT),
                    "--observations",
                    "examples/binder-controls-synthetic/control-observations.jsonl",
                    "--out",
                    out.as_posix(),
                ]
            )

            self.assertEqual(0, status)
            self.assertTrue(payload["ok"])
            self.assertEqual("ready_with_optional_gaps", payload["status"])
            self.assertEqual(0, payload["provider_calls"])
            record = json.loads((ROOT / out).read_text(encoding="utf-8"))
            self.assertTrue(record["round_decision_ready"])

    def test_calibrate_controls_returns_one_for_a_required_gap(self) -> None:
        (ROOT / ".runtime").mkdir(exist_ok=True)
        with tempfile.TemporaryDirectory(dir=ROOT / ".runtime") as temporary:
            runtime_root = Path(temporary)
            relative_root = runtime_root.relative_to(ROOT)
            source_rows = (FIXTURE / "control-observations.jsonl").read_text(encoding="utf-8")
            incomplete = runtime_root / "incomplete.jsonl"
            incomplete.write_text(
                "\n".join(line for line in source_rows.splitlines() if '"positive-1"' not in line)
                + "\n",
                encoding="utf-8",
            )
            out = relative_root / "blocked-calibration.json"

            status, payload = self.call(
                [
                    "binder-lane",
                    "calibrate-controls",
                    "examples/binder-controls-synthetic/control-panel.json",
                    "--workspace",
                    str(ROOT),
                    "--observations",
                    incomplete.relative_to(ROOT).as_posix(),
                    "--out",
                    out.as_posix(),
                ]
            )

            self.assertEqual(1, status)
            self.assertFalse(payload["ok"])
            self.assertEqual("blocked", payload["status"])
            self.assertTrue(payload["readiness"]["blocking_reasons"])
            self.assertTrue((ROOT / out).is_file())

    def test_round_decision_can_bind_a_control_calibration(self) -> None:
        (ROOT / ".runtime").mkdir(exist_ok=True)
        with tempfile.TemporaryDirectory(dir=ROOT / ".runtime") as temporary:
            runtime_root = Path(temporary)
            relative_root = runtime_root.relative_to(ROOT)
            request = json.loads(
                (
                    ROOT
                    / "examples"
                    / "pd-l1-binder-design-public"
                    / "binder-round-request.json"
                ).read_text(encoding="utf-8")
            )
            request["comparison_policy"]["metrics"] = [
                {
                    "id": "interface_score",
                    "direction": "higher_is_better",
                    "unit": "unitless_proxy",
                    "missing_value_policy": "preserve_as_failure",
                }
            ]
            request["comparison_policy"]["tie_break"] = ["interface_score", "candidate_id"]
            request["optimization_policy"]["primary_metric_id"] = "interface_score"
            request["optimization_policy"]["direction"] = "maximize"
            ledger = json.loads(
                (ROOT / "references" / "binder-lane-capability-ledger.json").read_text(
                    encoding="utf-8"
                )
            )
            plan = binder_lane.plan_request(request, ledger, ROOT)
            plan_path = runtime_root / "plan.json"
            binder_lane.write_json(plan_path, plan)
            history_path = runtime_root / "history.json"
            binder_lane.write_json(
                history_path,
                [
                    {
                        "round_index": 1,
                        "primary_metric_value": 0.6,
                        "actual_spend_usd": 60,
                        "closeout_complete": True,
                        "metric_provenance": {
                            "metric_id": "interface_score",
                            "metric_source": "stage_closeout",
                            "source_artifact_sha256": "2" * 64,
                            "calibration_state": "uncalibrated",
                            "calibration_scope_id": "pending",
                            "calibration_artifact_sha256": None,
                        },
                    }
                ],
            )
            calibration_path = relative_root / "calibration.json"
            status, _ = self.call(
                [
                    "binder-lane",
                    "calibrate-controls",
                    "examples/binder-controls-synthetic/control-panel.json",
                    "--workspace",
                    str(ROOT),
                    "--observations",
                    "examples/binder-controls-synthetic/control-observations.jsonl",
                    "--out",
                    calibration_path.as_posix(),
                ]
            )
            self.assertEqual(0, status)

            status, payload = self.call(
                [
                    "binder-lane",
                    "round-decision",
                    plan_path.relative_to(ROOT).as_posix(),
                    "--workspace",
                    str(ROOT),
                    "--history",
                    history_path.relative_to(ROOT).as_posix(),
                    "--calibration",
                    calibration_path.as_posix(),
                ]
            )

            self.assertEqual(0, status)
            self.assertEqual("calibrated", payload["calibration_state"])
            self.assertEqual("synthetic-two-predictor-panel", payload["calibration_scope_id"])
            self.assertEqual(64, len(payload["calibration_artifact_sha256"]))


if __name__ == "__main__":
    unittest.main()
