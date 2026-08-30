from __future__ import annotations

import contextlib
import hashlib
import io
import json
import tempfile
import unittest
from pathlib import Path

from biosymphony_structure_factory import binder_supplied_backbone_adapter as adapter


def _sha256(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def _atom(serial: int, residue: str, chain: str, number: int, x: float) -> str:
    return (
        f"ATOM  {serial:5d}  CA  {residue:>3s} {chain}{number:4d}    "
        f"{x:8.3f}{0.0:8.3f}{0.0:8.3f}  1.00 80.00           C"
    )


def _pdb() -> str:
    return "\n".join(
        [
            "MODEL        1",
            _atom(1, "ALA", "A", 1, 0.0),
            _atom(2, "CYS", "A", 2, 1.0),
            "HETATM    3  O   HOH A 101       4.000   0.000   0.000  1.00 20.00           O",
            "ENDMDL",
            "MODEL        2",
            _atom(4, "ASP", "A", 3, 2.0),
            "ENDMDL",
            "END",
            "",
        ]
    )


class SuppliedBackboneAdapterTests(unittest.TestCase):
    def setUp(self) -> None:
        self.temporary = tempfile.TemporaryDirectory()
        self.root = Path(self.temporary.name)
        self.structure = self.root / "inputs" / "backbone.pdb"
        self.input_path = self.root / "inputs" / "rows.jsonl"
        self.output_path = self.root / "outputs" / "backbones.jsonl"
        self.pose_dir = self.root / "outputs" / "poses"
        self.structure.parent.mkdir(parents=True)
        self.structure.write_text(_pdb(), encoding="utf-8")

    def tearDown(self) -> None:
        self.temporary.cleanup()

    def _eligible(self) -> dict:
        return {
            "candidate_id": "candidate-001",
            "status": "eligible",
            "structure_path": "inputs/backbone.pdb",
            "structure_sha256": _sha256(self.structure),
            "target_id": "synthetic-target",
        }

    def _write(self, rows: list[dict]) -> None:
        self.input_path.write_text(
            "".join(json.dumps(row, sort_keys=True) + "\n" for row in rows),
            encoding="utf-8",
        )

    def _run(self, rows: list[dict]) -> dict:
        self._write(rows)
        return adapter.run_backbones(
            run_root=self.root,
            input_path=self.input_path,
            output_path=self.output_path,
            pose_dir=self.pose_dir,
            source_chain="A",
            binder_chain="B",
            minimum_length=2,
            maximum_length=2,
            expected_count=len(rows),
        )

    def test_adapter_copies_one_chain_and_preserves_failed_rows(self) -> None:
        failed = {
            "candidate_id": "candidate-002",
            "status": "failed_generation",
            "failure_code": "upstream_failed",
        }
        summary = self._run([self._eligible(), failed])
        self.assertEqual(2, summary["input_count"])
        self.assertEqual(2, summary["output_count"])
        self.assertEqual(1, summary["generated_count"])
        self.assertEqual(1, summary["not_evaluable_count"])
        self.assertEqual(_sha256(self.output_path), summary["output_sha256"])
        rows = [json.loads(line) for line in self.output_path.read_text().splitlines()]
        self.assertEqual(["candidate-001", "candidate-002"], [row["candidate_id"] for row in rows])
        self.assertEqual("generated", rows[0]["status"])
        self.assertEqual("failed_generation", rows[1]["status"])
        self.assertEqual("not_evaluable", rows[1]["backbone"]["state"])
        pose = self.root / rows[0]["design_pose_path"]
        self.assertEqual(_sha256(pose), rows[0]["design_pose_sha256"])
        text = pose.read_text(encoding="utf-8")
        atoms = [line for line in text.splitlines() if line.startswith("ATOM  ")]
        self.assertEqual(2, len(atoms))
        self.assertTrue(all(line[21:22] == "B" for line in atoms))
        self.assertNotIn("HETATM", text)
        self.assertNotIn("ASP", text)
        self.assertIn("NO DESIGN MODEL RAN", text)

    def test_outputs_are_deterministic(self) -> None:
        self._run([self._eligible()])
        first_manifest = self.output_path.read_bytes()
        first_pose = next(self.pose_dir.iterdir()).read_bytes()
        self._run([self._eligible()])
        self.assertEqual(first_manifest, self.output_path.read_bytes())
        self.assertEqual(first_pose, next(self.pose_dir.iterdir()).read_bytes())

    def test_hash_mismatch_fails_before_any_output_is_written(self) -> None:
        row = self._eligible()
        row["structure_sha256"] = "0" * 64
        self._write([row])
        with self.assertRaisesRegex(adapter.SuppliedBackboneError, "does not match"):
            adapter.run_backbones(
                run_root=self.root,
                input_path=self.input_path,
                output_path=self.output_path,
                pose_dir=self.pose_dir,
                source_chain="A",
                binder_chain="B",
                minimum_length=2,
                maximum_length=2,
                expected_count=1,
            )
        self.assertFalse(self.output_path.exists())
        self.assertFalse(self.pose_dir.exists())

    def test_output_count_is_checked(self) -> None:
        self._write([self._eligible()])
        with self.assertRaisesRegex(adapter.SuppliedBackboneError, "expected 2"):
            adapter.run_backbones(
                run_root=self.root,
                input_path=self.input_path,
                output_path=self.output_path,
                pose_dir=self.pose_dir,
                source_chain="A",
                binder_chain="B",
                minimum_length=2,
                maximum_length=2,
                expected_count=2,
            )

    def test_all_failed_input_is_preserved_but_cannot_report_success(self) -> None:
        self._write([{"candidate_id": "candidate-002", "status": "failed_generation"}])
        with self.assertRaisesRegex(adapter.SuppliedBackboneError, "not-evaluable rows were written"):
            adapter.run_backbones(
                run_root=self.root,
                input_path=self.input_path,
                output_path=self.output_path,
                pose_dir=self.pose_dir,
                source_chain="A",
                binder_chain="B",
                minimum_length=2,
                maximum_length=2,
                expected_count=1,
            )
        row = json.loads(self.output_path.read_text())
        self.assertEqual("failed_generation", row["status"])
        self.assertEqual("not_evaluable", row["backbone"]["state"])
        self.assertFalse(self.pose_dir.exists())

    def test_readiness_reports_no_optional_runtime_dependency(self) -> None:
        output = io.StringIO()
        with contextlib.redirect_stdout(output):
            self.assertEqual(0, adapter.main(["readiness"]))
        report = json.loads(output.getvalue())
        self.assertTrue(report["wrapper_ready"])
        self.assertTrue(report["ready"])
        self.assertEqual([], report["runtime_dependencies"])

    def test_registry_exposes_the_tested_fixed_argument_wrapper(self) -> None:
        root = Path(__file__).resolve().parents[1]
        registry = json.loads(
            (root / "references" / "binder-execution-adapters.json").read_text(
                encoding="utf-8"
            )
        )
        row = next(
            item for item in registry["adapters"] if item["id"] == "supplied-backbone-v1"
        )
        self.assertEqual("supplied-backbone", row["tool_id"])
        self.assertEqual(["generator"], row["roles"])
        self.assertEqual("ready", row["implementation_status"])
        self.assertEqual("local_argv", row["execution_kind"])
        self.assertEqual("bsf-supplied-backbone", row["program"])
        self.assertEqual("forbidden", row["network_policy"])
        self.assertEqual([], row["required_environment_names"])


if __name__ == "__main__":
    unittest.main()
