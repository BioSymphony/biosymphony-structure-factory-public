from __future__ import annotations

import importlib.util
import tempfile
import unittest
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
SCRIPT = ROOT / "scripts" / "structure_factory" / "boltz_cofold_rfdiffusion.py"


def load_script():
    spec = importlib.util.spec_from_file_location("boltz_cofold_rfdiffusion_test", SCRIPT)
    if spec is None or spec.loader is None:
        raise RuntimeError(f"cannot import {SCRIPT}")
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def ca_line(number: int, insertion_code: str = " ", residue: str = "GLY") -> str:
    return (
        f"ATOM      1  CA  {residue:>3s} A{number:4d}{insertion_code:1s}"
        "   0.000   0.000   0.000  1.00  0.00           C"
    )


class PdbSequenceTests(unittest.TestCase):
    def setUp(self) -> None:
        self.module = load_script()

    def write_pdb(self, lines: list[str]) -> Path:
        tmp = tempfile.NamedTemporaryFile("w", suffix=".pdb", delete=False)
        self.addCleanup(Path(tmp.name).unlink, missing_ok=True)
        with tmp:
            tmp.write("\n".join(lines) + "\n")
        return Path(tmp.name)

    def test_insertion_codes_are_distinct_residues(self) -> None:
        path = self.write_pdb(
            [
                ca_line(51, residue="ALA"),
                ca_line(52, residue="GLY"),
                ca_line(52, "A", residue="SER"),
                ca_line(52, "B", residue="TYR"),
            ]
        )
        self.assertEqual(self.module.extract_sequence_from_pdb(path), "AGSY")

    def test_only_first_model_is_read(self) -> None:
        path = self.write_pdb(
            [
                "MODEL        1",
                ca_line(1, residue="ALA"),
                ca_line(2, residue="GLY"),
                "ENDMDL",
                "MODEL        2",
                ca_line(1, residue="SER"),
                ca_line(2, residue="TYR"),
                "ENDMDL",
            ]
        )
        self.assertEqual(self.module.extract_sequence_from_pdb(path), "AG")


if __name__ == "__main__":
    unittest.main()
