from __future__ import annotations

import json
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
CHECKER = ROOT / "scripts" / "structure_factory" / "screening_schema_check.py"
FIXTURE = ROOT / "examples" / "orchestration-fixtures" / "calibration-summary.json"


class CalibrationSummaryTests(unittest.TestCase):
    def run_check(self, payload: dict) -> tuple[int, dict]:
        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp) / "calibration-summary.json"
            path.write_text(json.dumps(payload))
            result = subprocess.run(
                [
                    sys.executable,
                    str(CHECKER),
                    "--file",
                    str(path),
                    "--schema",
                    "calibration-summary",
                    "--json",
                ],
                cwd=ROOT,
                text=True,
                capture_output=True,
            )
        return result.returncode, json.loads(result.stdout)

    def test_public_fixture_is_non_authoritative_and_valid(self) -> None:
        code, summary = self.run_check(json.loads(FIXTURE.read_text()))
        self.assertEqual(0, code, summary)
        self.assertTrue(summary["ok"], summary)

    def test_borrowed_record_cannot_authorize_ranking(self) -> None:
        payload = json.loads(FIXTURE.read_text())
        payload.update(
            {
                "source_target_id": "different-public-target",
                "calibration_state": "borrowed",
                "ranking_authority": True,
            }
        )
        code, summary = self.run_check(payload)
        self.assertNotEqual(0, code)
        self.assertFalse(summary["ok"])
        self.assertTrue(
            any("ranking_authority" in error for error in summary["errors"]),
            summary,
        )


if __name__ == "__main__":
    unittest.main()
