from __future__ import annotations

import hashlib
import importlib.util
import re
import shutil
import tempfile
import unittest
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
WRAPPER = ROOT / "scripts" / "structure_factory" / "compute_ipsae.py"
VENDOR = ROOT / "scripts" / "structure_factory" / "vendor" / "ipsae" / "ipsae.py"


def load_wrapper(name: str, path: Path = WRAPPER):
    spec = importlib.util.spec_from_file_location(name, path)
    if spec is None or spec.loader is None:
        raise RuntimeError(f"cannot import {path}")
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


class ComputeIpsaeTests(unittest.TestCase):
    def test_vendored_scorer_matches_its_pin(self) -> None:
        wrapper = load_wrapper("ipsae_pin")
        measured = hashlib.sha256(VENDOR.read_bytes()).hexdigest()
        self.assertEqual(wrapper.VENDOR_IPSAE_SHA256, measured)
        self.assertEqual(wrapper.IMPLEMENTATION_REVISION, "ipsae@4")

    def test_modified_scorer_is_rejected(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            staged_vendor = root / "vendor" / "ipsae"
            staged_vendor.mkdir(parents=True)
            source = VENDOR.read_text(encoding="utf-8")
            self.assertEqual(len(re.findall(r"d0\s*=\s*1\.24", source)), 1)
            staged_vendor.joinpath("ipsae.py").write_text(
                re.sub(r"d0\s*=\s*1\.24", "d0 = 9.99", source, count=1),
                encoding="utf-8",
            )
            staged_wrapper = root / "compute_ipsae.py"
            shutil.copyfile(WRAPPER, staged_wrapper)
            with self.assertRaisesRegex(RuntimeError, "does not match its pin"):
                load_wrapper("ipsae_tampered", staged_wrapper)

    def test_directional_pair_selection_prefers_requested_order(self) -> None:
        wrapper = load_wrapper("ipsae_direction")
        rows = [
            {"Chn1": "A", "Chn2": "B", "ipSAE": 0.2},
            {"Chn1": "B", "Chn2": "A", "ipSAE": 0.8},
        ]
        self.assertEqual(wrapper.select_pair(rows, "B", "A")["ipSAE"], 0.8)
        self.assertEqual(wrapper.select_pair(rows, "A", "B")["ipSAE"], 0.2)

    def test_reverse_pair_is_used_only_when_requested_order_is_absent(self) -> None:
        wrapper = load_wrapper("ipsae_reverse")
        row = {"Chn1": "A", "Chn2": "B", "ipSAE": 0.2}
        self.assertIs(wrapper.select_pair([row], "B", "A"), row)


if __name__ == "__main__":
    unittest.main()
