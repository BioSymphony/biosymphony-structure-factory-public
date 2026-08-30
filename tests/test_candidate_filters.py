from __future__ import annotations

import json
import tempfile
import unittest
from pathlib import Path

from biosymphony_structure_factory import candidate_filters


def rows_fixture() -> list[dict]:
    return [
        {
            "candidate_id": "candidate-001",
            "status": "scored",
            "candidate_sequence": "ACDEF",
            "metrics": {"score": 0.8},
        },
        {
            "candidate_id": "candidate-002",
            "status": "failed_prediction",
            "candidate_sequence": "ACDEG",
        },
        {
            "candidate_id": "candidate-003",
            "status": "scored",
            "candidate_sequence": "WYKLM",
            "metrics": {"score": 0.2},
        },
        {
            "candidate_id": "candidate-004",
            "status": "scored",
            "candidate_sequence": "ACDEF",
            "metrics": {"score": 0.9},
        },
    ]


class CandidateFilterTests(unittest.TestCase):
    def test_metric_and_diversity_filters_preserve_all_rows(self) -> None:
        metric_rows = candidate_filters.status_filter(
            rows_fixture(),
            metric_path="metrics.score",
            minimum=0.5,
            maximum=1.0,
        )
        self.assertEqual(4, len(metric_rows))
        self.assertEqual(
            ["passed", "not_evaluable", "filtered", "passed"],
            [row["filter_results"][-1]["state"] for row in metric_rows],
        )

        diverse_rows = candidate_filters.diversity_filter(
            metric_rows,
            sequence_field="candidate_sequence",
            maximum_similarity=0.8,
        )
        self.assertEqual(4, len(diverse_rows))
        self.assertEqual(
            ["passed", "not_evaluable", "not_evaluable", "filtered"],
            [row["filter_results"][-1]["state"] for row in diverse_rows],
        )
        self.assertEqual(
            "candidate-001",
            diverse_rows[3]["filter_results"][-1]["nearest_retained_candidate_id"],
        )

    def test_command_entry_points_write_count_preserving_jsonl(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            source = root / "input.jsonl"
            status_output = root / "status.jsonl"
            diversity_output = root / "diversity.jsonl"
            source.write_text(
                "".join(json.dumps(row) + "\n" for row in rows_fixture()),
                encoding="utf-8",
            )
            status = candidate_filters.status_main(
                [
                    "--run-root",
                    str(root),
                    "--input",
                    str(source),
                    "--output",
                    str(status_output),
                    "--metric",
                    "metrics.score",
                    "--minimum",
                    "0.5",
                    "--maximum",
                    "1.0",
                ]
            )
            self.assertEqual(0, status)
            self.assertEqual(4, len(status_output.read_text(encoding="utf-8").splitlines()))

            status = candidate_filters.diversity_main(
                [
                    "--run-root",
                    str(root),
                    "--input",
                    str(status_output),
                    "--output",
                    str(diversity_output),
                    "--sequence-field",
                    "candidate_sequence",
                    "--maximum-similarity",
                    "0.8",
                ]
            )
            self.assertEqual(0, status)
            self.assertEqual(4, len(diversity_output.read_text(encoding="utf-8").splitlines()))


if __name__ == "__main__":
    unittest.main()
