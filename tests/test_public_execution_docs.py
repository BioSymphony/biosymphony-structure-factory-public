from __future__ import annotations

import re
import unittest
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
PUBLIC_PROSE_ROOTS = (
    Path("campaigns"),
    Path("demos"),
    Path("docs"),
    Path("packs"),
    Path("recipes"),
    Path("runpod"),
    Path("skills"),
    Path("templates"),
    Path("tools"),
)
TOP_LEVEL_PROSE = (
    Path("AGENTS.md"),
    Path("CONTRIBUTING.md"),
    Path("PUBLIC_RELEASE.md"),
    Path("README.md"),
    Path("SECURITY.md"),
    Path("SUPPORT.md"),
)
OWNED_DOCS = (
    Path("README.md"),
    Path("docs/quickstart-tour.md"),
    Path("docs/workflow-map.md"),
    Path("docs/faq.md"),
    Path("docs/runpod-stack.md"),
    Path("docs/ai-design-runtime-readiness.md"),
    Path("docs/use-cases.md"),
)


class PublicExecutionDocTests(unittest.TestCase):
    def public_prose_paths(self) -> list[Path]:
        paths = [ROOT / relative for relative in TOP_LEVEL_PROSE]
        for relative in PUBLIC_PROSE_ROOTS:
            paths.extend((ROOT / relative).rglob("*.md"))
        return sorted(path for path in paths if path.is_file())

    def test_docs_describe_runtime_execution_without_false_blockers(self) -> None:
        forbidden = (
            "non-launchable",
            "non-launching",
            "private/operator-gated",
            "private launcher",
        )
        for relative in OWNED_DOCS:
            text = (ROOT / relative).read_text(encoding="utf-8")
            for phrase in forbidden:
                self.assertNotIn(phrase, text.lower(), f"{relative}: {phrase}")

    def test_docs_state_the_shared_execution_boundary(self) -> None:
        combined = "\n".join(
            (ROOT / relative).read_text(encoding="utf-8") for relative in OWNED_DOCS
        )
        required = (
            "ignored `.runtime/`",
            "explicit human authorization",
            "validated adapter",
            "tracked template",
        )
        for phrase in required:
            self.assertIn(phrase, combined)

    def test_binder_docs_name_shipped_execution_paths(self) -> None:
        guide = (ROOT / "docs" / "binder-lane-round.md").read_text(encoding="utf-8")
        cli = (ROOT / "docs" / "cli-reference.md").read_text(encoding="utf-8")
        controls = (ROOT / "docs" / "binder-controls.md").read_text(encoding="utf-8")

        for phrase in (
            "`target-check`",
            "`execute`",
            "`remote-request`",
            "`remote-receipt`",
            "`closeout`",
            "`round-decision`",
        ):
            self.assertIn(phrase, guide)
            self.assertIn(phrase, cli)
        self.assertIn("calibrate-controls", controls)
        self.assertIn("not a `bsf binder-lane dispatch` command", guide)
        self.assertIn("not a CLI subcommand", cli)

    def test_public_prose_has_no_private_paths_or_false_execution_labels(self) -> None:
        forbidden = (
            "/" + "users/",
            "/" + "home/",
            "github" + "_2",
            "non-launchable",
            "non-launching",
            "private/operator-gated",
            "private launcher",
            "there is no headless download path",
        )
        for path in self.public_prose_paths():
            text = path.read_text(encoding="utf-8").lower()
            relative = path.relative_to(ROOT)
            for phrase in forbidden:
                self.assertNotIn(phrase, text, f"{relative}: {phrase}")

    def test_public_cli_entry_points_use_the_bsf_namespace(self) -> None:
        pyproject = (ROOT / "pyproject.toml").read_text(encoding="utf-8")
        scripts_block = pyproject.split("[project.scripts]", 1)[1].split("\n[", 1)[0]
        entry_points = {
            match.group(1)
            for line in scripts_block.splitlines()
            if (match := re.fullmatch(r"([a-z0-9-]+)\s*=\s*.+", line.strip()))
        }

        self.assertTrue(entry_points)
        for entry_point in entry_points:
            self.assertTrue(
                entry_point == "bsf" or entry_point.startswith("bsf-"),
                f"public CLI entry point must use the bsf namespace: {entry_point}",
            )

    def test_portable_copies_match_canonical_docs(self) -> None:
        mirrors = {
            Path("README.md"): (
                Path("skills/biosymphony-structure-factory/references/README.md"),
            ),
            Path("docs/workflow-map.md"): (
                Path("skills/binder-lane-round/references/docs/workflow-map.md"),
                Path("skills/biosymphony-structure-factory/references/docs/workflow-map.md"),
            ),
        }
        for canonical in OWNED_DOCS[1:]:
            if canonical not in mirrors:
                mirrors[canonical] = (
                    Path("skills/biosymphony-structure-factory/references")
                    / canonical,
                )

        for canonical, copies in mirrors.items():
            expected = (ROOT / canonical).read_bytes()
            for copy in copies:
                self.assertEqual(expected, (ROOT / copy).read_bytes(), str(copy))


if __name__ == "__main__":
    unittest.main()
