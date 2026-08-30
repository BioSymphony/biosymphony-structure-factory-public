from __future__ import annotations

import tempfile
import unittest
from pathlib import Path

from scripts.structure_factory.public_doc_reference_check import check
from scripts.structure_factory.runpod_public_template_check import check_manifest


ROOT = Path(__file__).resolve().parents[1]


class PublicDocReferenceTests(unittest.TestCase):
    def test_public_doc_references_are_current(self) -> None:
        result = check(ROOT)
        self.assertTrue(result["ok"], result)

    def test_doc_reference_check_flags_missing_make_target(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            (root / "Makefile").write_text("release-check:\n\ttrue\n", encoding="utf-8")
            (root / "README.md").write_text("Run `make missing-target`.\n", encoding="utf-8")
            result = check(root)
            self.assertFalse(result["ok"])
            self.assertTrue(any(item["check_id"] == "missing-make-target" for item in result["findings"]))

    def test_doc_reference_check_flags_private_package_url(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            (root / "Makefile").write_text("release-check:\n\ttrue\n", encoding="utf-8")
            (root / "pyproject.toml").write_text(
                'Homepage = "https://github.com/BioSymphony/biosymphony-structure-factory"\n',
                encoding="utf-8",
            )
            result = check(root)
            self.assertFalse(result["ok"])
            self.assertTrue(any(item["check_id"] == "private-package-url" for item in result["findings"]))

    def test_doc_reference_check_flags_private_repo_urls_in_public_metadata(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            (root / "Makefile").write_text("release-check:\n\ttrue\n", encoding="utf-8")
            (root / "schemas").mkdir()
            (root / "schemas" / "campaign-manifest.schema.json").write_text(
                '{"$id": "https://github.com/BioSymphony/biosymphony-structure-factory/schemas/campaign-manifest.schema.json"}\n',
                encoding="utf-8",
            )
            (root / ".github" / "ISSUE_TEMPLATE").mkdir(parents=True)
            (root / ".github" / "ISSUE_TEMPLATE" / "config.yml").write_text(
                "url: https://github.com/BioSymphony/biosymphony-structure-factory/discussions\n",
                encoding="utf-8",
            )
            result = check(root)
            self.assertFalse(result["ok"])
            private_url_findings = [item for item in result["findings"] if item["check_id"] == "private-repo-url"]
            self.assertEqual(len(private_url_findings), 2, result)

    def test_doc_reference_check_flags_stale_skill_copy(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            (root / "Makefile").write_text("release-check:\n\ttrue\n", encoding="utf-8")
            (root / "docs").mkdir()
            (root / "docs" / "guide.md").write_text("canonical\n", encoding="utf-8")
            bundled = root / "skills" / "biosymphony-structure-factory" / "references" / "docs"
            bundled.mkdir(parents=True)
            (bundled / "guide.md").write_text("stale\n", encoding="utf-8")
            result = check(root)
            self.assertFalse(result["ok"])
            self.assertTrue(
                any(item["check_id"] == "stale-skill-reference-copy" for item in result["findings"]),
                result,
            )

    def test_doc_reference_check_flags_missing_bundled_skill_link(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            (root / "Makefile").write_text("release-check:\n\ttrue\n", encoding="utf-8")
            skill = root / "skills" / "binder-lane-round" / "references" / "docs"
            skill.mkdir(parents=True)
            (skill / "guide.md").write_text("See [missing](missing.md).\n", encoding="utf-8")
            result = check(root)
            self.assertFalse(result["ok"])
            self.assertTrue(
                any(item["check_id"] == "missing-bundled-skill-link" for item in result["findings"]),
                result,
            )

    def test_runpod_public_template_check_rejects_launchable_manifest(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp) / "demo.json"
            path.write_text(
                """{
  "remote_launch_allowed": true,
  "public_template_status": "ready",
  "launch_authorization": {"approved_at": "2026-01-01", "approved_by": "operator"},
  "runpod": {"dataCenterIds": ["US-XX-1"], "networkVolumeId": "abc123"},
  "startup": {"commands": ["echo run"]}
}
""",
                encoding="utf-8",
            )
            findings = check_manifest(path)
            self.assertTrue(findings)


if __name__ == "__main__":
    unittest.main()
