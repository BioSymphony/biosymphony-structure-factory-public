from __future__ import annotations

import unittest
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
GUIDE = ROOT / "docs" / "binder-study-decision-loop.md"


class BinderDecisionLoopDocTests(unittest.TestCase):
    def test_portable_guide_copies_match_the_public_guide(self) -> None:
        expected = GUIDE.read_bytes()
        mirrors = (
            ROOT
            / "skills"
            / "binder-lane-round"
            / "references"
            / "docs"
            / GUIDE.name,
            ROOT
            / "skills"
            / "biosymphony-structure-factory"
            / "references"
            / "docs"
            / GUIDE.name,
        )
        for mirror in mirrors:
            self.assertEqual(expected, mirror.read_bytes(), str(mirror))

    def test_guide_covers_every_round_decision_and_gate(self) -> None:
        text = GUIDE.read_text(encoding="utf-8")
        required = (
            "Target and site",
            "Study mode",
            "Tool mix",
            "Execution mix",
            "Use constraints",
            "Budget",
            "Rounds",
            "primary metric",
            "stopping rule",
            "--dry-run",
            "explicit approval",
            "bsf binder-lane closeout",
            "adapter_required",
            "validated adapter registry below `.runtime/`",
        )
        for phrase in required:
            self.assertIn(phrase, text)

    def test_guide_contains_no_private_location_or_release_marker(self) -> None:
        text = GUIDE.read_text(encoding="utf-8")
        forbidden_values = (
            "/" + "Users/",
            "github_" + "2",
            "BSF-" + "PRIVATE",
            "PRIVATE-" + "NEVER-PUBLISH",
        )
        for forbidden in forbidden_values:
            self.assertNotIn(forbidden, text)


if __name__ == "__main__":
    unittest.main()
