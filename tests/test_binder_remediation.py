from __future__ import annotations

import io
import json
import tempfile
import unittest
from contextlib import redirect_stdout
from pathlib import Path

from biosymphony_structure_factory.cli import main
from biosymphony_structure_factory.remediation import failure_record
from biosymphony_structure_factory.target_verifier import TargetVerificationError


ROOT = Path(__file__).resolve().parents[1]


class BinderRemediationTests(unittest.TestCase):
    def test_records_stable_actions_for_target_calibration_and_authorization(self) -> None:
        target = failure_record(TargetVerificationError("chain A lacks required coordinate residues"))
        self.assertEqual("target-verification", target["check_id"])
        self.assertTrue(any(action["id"] == "select-coordinates" for action in target["next_actions"]))

        calibration = failure_record(ValueError("target threshold needs calibration provenance"))
        self.assertEqual("metric-provenance", calibration["check_id"])
        self.assertTrue(any(action["id"] == "change-stopping-rule" for action in calibration["next_actions"]))

        authorization = failure_record(ValueError("explicit authorization is required"))
        self.assertEqual("execution-authorization", authorization["check_id"])
        self.assertTrue(any(action["id"] == "change-route" for action in authorization["next_actions"]))

    def test_cli_refusal_includes_actions_without_echoing_binding_values(self) -> None:
        (ROOT / ".runtime").mkdir(exist_ok=True)
        with tempfile.TemporaryDirectory(dir=ROOT / ".runtime") as temporary:
            relative = Path(temporary).relative_to(ROOT).as_posix()
            output = io.StringIO()
            with redirect_stdout(output):
                status = main(
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
            payload = json.loads(output.getvalue())
            self.assertEqual(2, status)
            self.assertEqual("execution-authorization", payload["failure"]["check_id"])
            self.assertGreaterEqual(len(payload["failure"]["next_actions"]), 2)
            self.assertEqual(0, payload["provider_calls"])


if __name__ == "__main__":
    unittest.main()
