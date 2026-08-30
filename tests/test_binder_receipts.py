from __future__ import annotations

import copy
import inspect
import json
import os
import tempfile
import unittest
from pathlib import Path

from biosymphony_structure_factory import binder_receipts


class BinderReceiptTests(unittest.TestCase):
    def make_run(self) -> tuple[tempfile.TemporaryDirectory[str], Path, list[dict[str, str]]]:
        temporary = tempfile.TemporaryDirectory()
        root = Path(temporary.name)
        outputs = root / "stages" / "score"
        outputs.mkdir(parents=True)
        (outputs / "ranking.json").write_text('{"rank": 1}\n', encoding="utf-8")
        declarations = [{"artifact_id": "ranking", "path": "stages/score/ranking.json"}]
        return temporary, root, declarations

    def test_completed_receipt_has_relative_hashes_and_no_payload(self) -> None:
        temporary, root, declarations = self.make_run()
        with temporary:
            ledger = binder_receipts.create_artifact_ledger(root, "score", "stages/score", declarations)
            receipt = binder_receipts.create_stage_receipt(
                root, "score", "computational_candidate", 0, ledger, validation_notes=["The ranking file passed validation."]
            )
            self.assertEqual("completed", receipt["execution_state"])
            self.assertEqual(1, receipt["expected_output_count"])
            self.assertEqual(1, receipt["found_output_count"])
            self.assertEqual("stages/score/ranking.json", receipt["artifact_hashes"][0]["path"])
            self.assertNotIn('{"rank": 1}', json.dumps(receipt))
            binder_receipts.validate_stage_receipt(receipt)

    def test_missing_output_turns_exit_zero_into_failed_receipt(self) -> None:
        temporary, root, declarations = self.make_run()
        with temporary:
            declarations.append({"artifact_id": "summary", "path": "stages/score/summary.json"})
            ledger = binder_receipts.create_artifact_ledger(root, "score", "stages/score", declarations)
            receipt = binder_receipts.create_stage_receipt(root, "score", "blocked", 0, ledger)
            self.assertEqual("failed", receipt["execution_state"])
            self.assertIn("Exit code 0 did not satisfy the declared output count.", receipt["validation_notes"])
            with self.assertRaises(binder_receipts.BinderReceiptError):
                forged = copy.deepcopy(receipt)
                forged["execution_state"] = "completed"
                binder_receipts.validate_stage_receipt(forged)

    def test_extra_output_prevents_success(self) -> None:
        temporary, root, declarations = self.make_run()
        with temporary:
            (root / "stages" / "score" / "undeclared.json").write_text("{}\n", encoding="utf-8")
            ledger = binder_receipts.create_artifact_ledger(root, "score", "stages/score", declarations)
            receipt = binder_receipts.create_stage_receipt(root, "score", "blocked", 0, ledger)
            self.assertEqual(2, ledger["found_output_count"])
            self.assertEqual("failed", receipt["execution_state"])

    def test_partial_receipt_records_declared_artifact_hashes_only(self) -> None:
        temporary, root, declarations = self.make_run()
        with temporary:
            declarations.append({"artifact_id": "summary", "path": "stages/score/summary.json"})
            ledger = binder_receipts.create_artifact_ledger(root, "score", "stages/score", declarations)
            receipt = binder_receipts.create_stage_receipt(
                root, "score", "insufficient_support", 1, ledger, requested_state="partial"
            )
            self.assertEqual("partial", receipt["execution_state"])
            self.assertEqual(["stages/score/ranking.json"], [row["path"] for row in receipt["artifact_hashes"]])

    def test_ledger_verification_detects_hash_tampering(self) -> None:
        temporary, root, declarations = self.make_run()
        with temporary:
            ledger = binder_receipts.create_artifact_ledger(root, "score", "stages/score", declarations)
            binder_receipts.write_artifact_ledger(root, "ledgers/score.json", ledger)
            (root / "stages" / "score" / "ranking.json").write_text('{"rank": 2}\n', encoding="utf-8")
            result = binder_receipts.verify_artifact_ledger(root, "ledgers/score.json", declarations)
            self.assertFalse(result["ok"])
            self.assertIn("an artifact hash differs from the ledger", result["findings"])

    def test_traversal_and_unknown_declaration_fields_fail_closed(self) -> None:
        temporary, root, declarations = self.make_run()
        with temporary:
            for invalid in (
                [{"artifact_id": "bad", "path": "../outside"}],
                [{"artifact_id": "bad", "path": "/tmp/outside"}],
                [{"artifact_id": "ranking", "path": declarations[0]["path"], "private_note": "x"}],
            ):
                with self.subTest(invalid=invalid):
                    with self.assertRaises(binder_receipts.BinderReceiptError):
                        binder_receipts.create_artifact_ledger(root, "score", "stages/score", invalid)

    @unittest.skipUnless(hasattr(os, "symlink"), "symlinks are unavailable")
    def test_symlinked_output_fails_closed(self) -> None:
        temporary, root, declarations = self.make_run()
        with temporary, tempfile.TemporaryDirectory() as outside:
            external = Path(outside) / "external.json"
            external.write_text("{}\n", encoding="utf-8")
            target = root / "stages" / "score" / "ranking.json"
            target.unlink()
            target.symlink_to(external)
            with self.assertRaises(binder_receipts.BinderReceiptError):
                binder_receipts.create_artifact_ledger(root, "score", "stages/score", declarations)

    def test_receipt_rejects_unknown_fields_and_nonpublic_notes(self) -> None:
        temporary, root, declarations = self.make_run()
        with temporary:
            ledger = binder_receipts.create_artifact_ledger(root, "score", "stages/score", declarations)
            with self.assertRaises(binder_receipts.BinderReceiptError):
                binder_receipts.create_stage_receipt(
                    root, "score", "blocked", 1, ledger, validation_notes=["pri" + "vate operator note"]
                )
            receipt = binder_receipts.create_stage_receipt(root, "score", "computational_candidate", 0, ledger)
            receipt["api_key"] = "sk" + "-proj-abcdefghijklmnop"
            with self.assertRaises(binder_receipts.BinderReceiptError):
                binder_receipts.validate_stage_receipt(receipt)

    def test_notes_reject_secrets_paths_and_sequence_payloads(self) -> None:
        temporary, root, declarations = self.make_run()
        with temporary:
            ledger = binder_receipts.create_artifact_ledger(root, "score", "stages/score", declarations)
            for note in (
                "Bear" + "er abcdefghijklmnopqrstuvwxyz",
                "/" + "Users/example/pri" + "vate",
                "ACDEFGHIKL" + "MNPQRSTVWY",
            ):
                with self.subTest(note=note):
                    with self.assertRaises(binder_receipts.BinderReceiptError):
                        binder_receipts.create_stage_receipt(root, "score", "blocked", 1, ledger, validation_notes=[note])

    def test_module_does_not_launch_processes_or_read_environment(self) -> None:
        source = inspect.getsource(binder_receipts)
        for forbidden in ("import subprocess", "import socket", "import requests", "import urllib", "os.environ"):
            self.assertNotIn(forbidden, source)

    def test_stage_receipt_write_is_contained_and_round_trips(self) -> None:
        temporary, root, declarations = self.make_run()
        with temporary:
            ledger = binder_receipts.create_artifact_ledger(root, "score", "stages/score", declarations)
            receipt = binder_receipts.create_stage_receipt(root, "score", "computational_candidate", 0, ledger)
            path = binder_receipts.write_stage_receipt(root, "receipts/score.json", receipt)
            self.assertEqual(root.resolve() / "receipts" / "score.json", path)
            self.assertEqual(receipt, json.loads(path.read_text(encoding="utf-8")))
            with self.assertRaises(binder_receipts.BinderReceiptError):
                binder_receipts.write_stage_receipt(root, "../score.json", receipt)
