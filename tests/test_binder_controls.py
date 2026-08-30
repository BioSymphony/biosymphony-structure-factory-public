from __future__ import annotations

import copy
import json
import unittest
from pathlib import Path

from biosymphony_structure_factory import binder_controls, binder_lane


ROOT = Path(__file__).resolve().parents[1]
FIXTURE = ROOT / "examples" / "binder-controls-synthetic"


def load_panel() -> dict:
    return json.loads((FIXTURE / "control-panel.json").read_text(encoding="utf-8"))


def load_rows() -> list[dict]:
    return [
        json.loads(line)
        for line in (FIXTURE / "control-observations.jsonl").read_text(encoding="utf-8").splitlines()
        if line.strip()
    ]


class BinderControlTests(unittest.TestCase):
    def test_derives_predictor_separated_gates_with_optional_gaps(self) -> None:
        result = binder_controls.derive_calibration(load_panel(), load_rows())

        self.assertTrue(result["round_decision_ready"])
        self.assertEqual("ready_with_optional_gaps", result["status"])
        self.assertEqual("calibrated", result["calibration_state"])
        self.assertEqual(2, len(result["gates"]))
        self.assertEqual(
            {"predictor-a": 0.5, "predictor-b": 0.5},
            {gate["predictor_id"]: gate["threshold"] for gate in result["gates"]},
        )
        self.assertEqual(2, len(result["readiness"]["optional_gaps"]))
        self.assertEqual("predictor_separated", result["diagnostic"]["aggregation"])
        self.assertIn("does not establish experimental binding", result["interpretation_limit"])

    def test_selected_metric_can_require_an_optional_control(self) -> None:
        panel = load_panel()
        panel["metrics"][0]["required_control_ids"] = ["positive-optional"]

        result = binder_controls.derive_calibration(panel, load_rows())

        self.assertFalse(result["round_decision_ready"])
        self.assertEqual("blocked", result["status"])
        self.assertTrue(
            any("positive-optional" in reason for reason in result["readiness"]["blocking_reasons"])
        )

    def test_missing_required_control_blocks_derivation(self) -> None:
        rows = [row for row in load_rows() if row["control_id"] != "positive-1"]

        result = binder_controls.derive_calibration(load_panel(), rows)

        self.assertFalse(result["round_decision_ready"])
        self.assertTrue(
            any("positive-1" in reason for reason in result["readiness"]["blocking_reasons"])
        )

    def test_nonseparating_selected_metric_has_no_gate(self) -> None:
        rows = load_rows()
        for row in rows:
            if row["control_id"] == "negative-3":
                row["metrics"]["interface_score"] = 0.9

        result = binder_controls.derive_calibration(load_panel(), rows)

        self.assertFalse(result["round_decision_ready"])
        self.assertEqual([], result["gates"])
        self.assertTrue(
            all(
                not report["metrics"]["interface_score"]["strictly_separating"]
                for report in result["diagnostic"]["predictors"].values()
            )
        )

    def test_lower_is_better_metric_uses_an_upper_gate(self) -> None:
        panel = load_panel()
        panel["selected_metric_id"] = "target_alignment_rmsd"

        result = binder_controls.derive_calibration(panel, load_rows())

        self.assertTrue(result["round_decision_ready"])
        self.assertEqual({"<="}, {gate["operator"] for gate in result["gates"]})
        self.assertEqual(
            {"predictor-a": 2.7, "predictor-b": 2.8},
            {gate["predictor_id"]: gate["threshold"] for gate in result["gates"]},
        )

    def test_seed_reduction_uses_selected_direction_then_lowest_seed(self) -> None:
        panel = load_panel()
        panel["required_seeds"] = [0, 1]
        rows = load_rows()
        rows.extend({**copy.deepcopy(row), "seed": 1} for row in load_rows())

        result = binder_controls.derive_calibration(panel, rows)

        self.assertTrue(result["round_decision_ready"])
        self.assertEqual({0}, {row["selected_seed"] for row in result["selected_rows"]})

    def test_adopts_a_complete_gate_set(self) -> None:
        adopted = {
            "schema_version": binder_controls.ADOPTION_SCHEMA,
            "source_scope_id": "reviewed-source-panel",
            "selected_metric_id": "interface_score",
            "source_artifact_sha256": "1" * 64,
            "gates": [
                {"predictor_id": "predictor-a", "metric_id": "interface_score", "operator": ">=", "threshold": 0.5},
                {"predictor_id": "predictor-b", "metric_id": "interface_score", "operator": ">=", "threshold": 0.5},
            ],
            "adoption_reason": "The source and destination records use the same metric and predictor revisions.",
        }

        result = binder_controls.adopt_calibration(load_panel(), adopted)

        self.assertTrue(result["round_decision_ready"])
        self.assertEqual("borrowed", result["calibration_state"])
        self.assertEqual("reviewed-source-panel", result["source_calibration"]["scope_id"])

    def test_adoption_requires_every_predictor(self) -> None:
        adopted = {
            "schema_version": binder_controls.ADOPTION_SCHEMA,
            "source_scope_id": "reviewed-source-panel",
            "selected_metric_id": "interface_score",
            "source_artifact_sha256": "1" * 64,
            "gates": [
                {"predictor_id": "predictor-a", "metric_id": "interface_score", "operator": ">=", "threshold": 0.5}
            ],
            "adoption_reason": "The metric identity matches.",
        }

        with self.assertRaisesRegex(binder_controls.BinderControlError, "cover every required predictor"):
            binder_controls.adopt_calibration(load_panel(), adopted)

    def test_ready_calibration_binds_round_decision_provenance(self) -> None:
        request = json.loads(
            (ROOT / "examples" / "pd-l1-binder-design-public" / "binder-round-request.json").read_text(
                encoding="utf-8"
            )
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
        ledger = json.loads((ROOT / "references" / "binder-lane-capability-ledger.json").read_text(encoding="utf-8"))
        plan = binder_lane.plan_request(request, ledger, ROOT)
        history = [
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
        ]
        calibration = binder_controls.derive_calibration(load_panel(), load_rows())

        bound = binder_controls.bind_round_history(plan, history, calibration, "3" * 64)
        decision = binder_lane.round_decision(plan, bound)

        self.assertEqual("calibrated", decision["calibration_state"])
        self.assertEqual("synthetic-two-predictor-panel", decision["calibration_scope_id"])
        self.assertEqual("3" * 64, decision["calibration_artifact_sha256"])

    def test_public_schemas_accept_the_fixture_and_results(self) -> None:
        try:
            from jsonschema import Draft202012Validator
        except ImportError:
            return
        panel_schema = json.loads((ROOT / "schemas" / "binder-control-panel.schema.json").read_text())
        calibration_schema = json.loads(
            (ROOT / "schemas" / "binder-control-calibration.schema.json").read_text()
        )
        self.assertTrue(Draft202012Validator(panel_schema).is_valid(load_panel()))
        self.assertTrue(
            Draft202012Validator(calibration_schema).is_valid(
                binder_controls.derive_calibration(load_panel(), load_rows())
            )
        )


if __name__ == "__main__":
    unittest.main()
