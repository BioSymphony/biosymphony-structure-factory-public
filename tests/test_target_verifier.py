from __future__ import annotations

import io
import json
import tempfile
import unittest
from contextlib import redirect_stdout
from pathlib import Path

from biosymphony_structure_factory import binder_lane
from biosymphony_structure_factory.cli import main
from biosymphony_structure_factory.target_verifier import TargetVerificationError, verify_target


ROOT = Path(__file__).resolve().parents[1]
PLAN_SHA256 = "c" * 64


def target_contract(required_residues: list[str] | None = None) -> dict:
    return {
        "input_posture": "synthetic",
        "label": "Synthetic target",
        "public_accession": "SYNTHETIC:target-verifier",
        "window": "chain A residues 19-21",
        "site": {
            "chain_id": "A",
            "required_residues": required_residues or ["19-21"],
        },
    }


def pdb_atom(serial: int, residue: str, chain: str, number: int) -> str:
    return (
        f"ATOM  {serial:>5d}  CA  {residue:>3s} {chain}{number:>4d}    "
        f"{float(serial):>8.3f}{0.0:>8.3f}{0.0:>8.3f}  1.00 20.00           C"
    )


def pdb_fixture() -> str:
    return "\n".join(
        [
            "SEQRES   1 A    3  ALA GLY SER",
            pdb_atom(1, "ALA", "A", 19),
            pdb_atom(2, "GLY", "A", 20),
            pdb_atom(3, "SER", "A", 21),
            "END",
            "",
        ]
    )


def mmcif_fixture() -> str:
    return """data_target
#
loop_
_entity_poly.entity_id
_entity_poly.pdbx_seq_one_letter_code_can
_entity_poly.pdbx_strand_id
1 AGS A
#
loop_
_struct_asym.id
_struct_asym.entity_id
X 1
#
loop_
_atom_site.group_PDB
_atom_site.auth_asym_id
_atom_site.label_asym_id
_atom_site.auth_seq_id
_atom_site.label_seq_id
_atom_site.pdbx_PDB_ins_code
_atom_site.auth_comp_id
_atom_site.label_comp_id
_atom_site.pdbx_PDB_model_num
ATOM A X 19 1 ? ALA ALA 1
ATOM A X 20 2 ? GLY GLY 1
ATOM A X 21 3 ? SER SER 1
#
"""


class TargetVerifierTests(unittest.TestCase):
    def test_pdb_verifies_coordinates_entity_sequence_and_site(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            path = Path(temporary) / "target.pdb"
            path.write_text(pdb_fixture(), encoding="utf-8")
            coordinates = verify_target(
                path,
                target_contract=target_contract(),
                plan_sha256=PLAN_SHA256,
                expected_sequence="AGS",
            )
            self.assertTrue(coordinates["sequence_verified"])
            self.assertEqual(3, coordinates["coordinate_residue_count"])
            self.assertNotIn("sequence", coordinates)
            self.assertNotIn("path", coordinates)

            entity = verify_target(
                path,
                target_contract=target_contract(["19", "21"]),
                plan_sha256=PLAN_SHA256,
                expected_sequence="AGS",
                sequence_basis="entity",
            )
            self.assertEqual("entity", entity["sequence_basis"])

    def test_mmcif_verifies_first_model_chain_and_entity_sequence(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            path = Path(temporary) / "target.cif"
            path.write_text(mmcif_fixture(), encoding="utf-8")
            report = verify_target(
                path,
                target_contract=target_contract(),
                plan_sha256=PLAN_SHA256,
                expected_sequence="AGS",
                sequence_basis="entity",
            )
            self.assertEqual("mmcif", report["format"])
            self.assertEqual(3, report["required_residue_count"])

    def test_refuses_missing_site_residue_and_sequence_mismatch(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            path = Path(temporary) / "target.pdb"
            path.write_text(pdb_fixture(), encoding="utf-8")
            with self.assertRaises(TargetVerificationError):
                verify_target(
                    path,
                    target_contract=target_contract(["19-22"]),
                    plan_sha256=PLAN_SHA256,
                )
            with self.assertRaises(TargetVerificationError):
                verify_target(
                    path,
                    target_contract=target_contract(),
                    plan_sha256=PLAN_SHA256,
                    expected_sequence="AAA",
                )


class TargetVerifierCliTests(unittest.TestCase):
    def test_cli_writes_sanitized_report_without_provider_calls(self) -> None:
        (ROOT / ".runtime").mkdir(exist_ok=True)
        with tempfile.TemporaryDirectory(dir=ROOT / ".runtime") as temporary:
            runtime = Path(temporary)
            structure = runtime / "target.pdb"
            sequence = runtime / "expected.fasta"
            structure.write_text(pdb_fixture(), encoding="utf-8")
            sequence.write_text("AGS\n", encoding="utf-8")
            request = json.loads(
                (
                    ROOT
                    / "examples"
                    / "pd-l1-binder-design-public"
                    / "binder-round-request.json"
                ).read_text(encoding="utf-8")
            )
            request["target"] = target_contract()
            plan_payload = binder_lane.plan_request(
                request,
                json.loads(
                    (ROOT / "references" / "binder-lane-capability-ledger.json").read_text(
                        encoding="utf-8"
                    )
                ),
                ROOT,
            )
            plan = runtime / "plan.json"
            binder_lane.write_json(plan, plan_payload)
            report = runtime / "target-report.json"
            output = io.StringIO()
            with redirect_stdout(output):
                status = main(
                    [
                        "binder-lane",
                        "target-check",
                        structure.relative_to(ROOT).as_posix(),
                        "--plan",
                        plan.relative_to(ROOT).as_posix(),
                        "--workspace",
                        str(ROOT),
                        "--expected-sequence-file",
                        sequence.relative_to(ROOT).as_posix(),
                        "--out",
                        report.relative_to(ROOT).as_posix(),
                    ]
                )
            payload = json.loads(output.getvalue())
            self.assertEqual(0, status)
            self.assertEqual(0, payload["provider_calls"])
            self.assertTrue(payload["required_residues_verified"])
            self.assertEqual(report.relative_to(ROOT).as_posix(), payload["report"])
            stored = json.loads(report.read_text(encoding="utf-8"))
            self.assertEqual(binder_lane.sha256_path(plan), stored["plan_sha256"])
            self.assertEqual(target_contract(), stored["target_contract"])
            self.assertNotIn("path", stored)
            self.assertNotIn("sequence", stored)


if __name__ == "__main__":
    unittest.main()
