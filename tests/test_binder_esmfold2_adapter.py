from __future__ import annotations

import ast
import gzip
import hashlib
import json
import tempfile
import unittest
from pathlib import Path
from unittest import mock

from biosymphony_structure_factory import binder_esmfold2_adapter as adapter


ROOT = Path(__file__).resolve().parents[1]


def _sha256(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def _cif() -> str:
    return """data_fixture
loop_
_atom_site.group_PDB
_atom_site.id
_atom_site.type_symbol
_atom_site.label_atom_id
_atom_site.label_comp_id
_atom_site.label_asym_id
_atom_site.label_seq_id
_atom_site.Cartn_x
_atom_site.Cartn_y
_atom_site.Cartn_z
ATOM 1 C CA ALA A 1 0.0 0.0 0.0
ATOM 2 C CA CYS A 2 1.0 0.0 0.0
ATOM 3 C CA ASP B 1 2.0 0.0 0.0
ATOM 4 C CA GLU B 2 3.0 0.0 0.0
#
"""


class FakeRuntime:
    identity = {
        "esm_distribution_version": "fixture",
        "model_revision": "fixture-revision",
        "device_class": "fixture",
    }

    def predict(
        self,
        chains: list[dict[str, str]],
        *,
        candidate_id: str,
        seed: int,
    ) -> adapter.PredictionResult:
        self.last_call = (chains, candidate_id, seed)
        return adapter.PredictionResult(
            structure_cif=_cif(),
            pae=[
                [0.0, 1.0, 2.0, 3.0],
                [1.0, 0.0, 3.0, 4.0],
                [2.0, 3.0, 0.0, 1.0],
                [3.0, 4.0, 1.0, 0.0],
            ],
            plddt=[91.0, 92.0, 81.0, 82.0],
            ptm=0.7,
            iptm=0.6,
        )


class FailingRuntime:
    identity = {"device_class": "fixture"}

    def predict(
        self,
        chains: list[dict[str, str]],
        *,
        candidate_id: str,
        seed: int,
    ) -> adapter.PredictionResult:
        raise RuntimeError("private runtime path and secret detail")


def _eligible_row(candidate_id: str = "candidate-001") -> dict:
    chains = [
        {"chain_id": "A", "type": "protein", "sequence": "AC"},
        {"chain_id": "B", "type": "protein", "sequence": "DE"},
    ]
    return {
        "candidate_id": candidate_id,
        "status": "eligible",
        "chains": chains,
        "complex_sequence_sha256": adapter.complex_sequence_sha256(chains),
    }


class ESMFold2AdapterTests(unittest.TestCase):
    def setUp(self) -> None:
        self.temporary = tempfile.TemporaryDirectory()
        self.root = Path(self.temporary.name)
        self.input_path = self.root / "inputs" / "candidates.jsonl"
        self.output_path = self.root / "outputs" / "predictions.jsonl"
        self.artifact_dir = self.root / "outputs" / "predictions"
        self.input_path.parent.mkdir(parents=True)

    def tearDown(self) -> None:
        self.temporary.cleanup()

    def _write_rows(self, rows: list[dict]) -> None:
        self.input_path.write_text(
            "".join(json.dumps(row, sort_keys=True) + "\n" for row in rows),
            encoding="utf-8",
        )

    def _run(self, rows: list[dict], runtime: object | None = None) -> dict:
        self._write_rows(rows)
        selected = runtime or FakeRuntime()
        return adapter.run_predictions(
            run_root=self.root,
            input_path=self.input_path,
            output_path=self.output_path,
            artifact_dir=self.artifact_dir,
            variant="fast",
            seed=7,
            expected_count=len(rows),
            runtime_factory=lambda _: selected,
        )

    def test_prediction_preserves_rows_and_hashes_every_sidecar(self) -> None:
        failed = {
            "candidate_id": "candidate-002",
            "status": "failed_generation",
            "failure_code": "upstream_failed",
        }
        summary = self._run([_eligible_row(), failed])
        self.assertEqual(
            {
                "input_count": 2,
                "output_count": 2,
                "predicted_count": 1,
                "failed_count": 0,
                "not_evaluable_count": 1,
                "output_sha256": _sha256(self.output_path),
            },
            summary,
        )
        rows = [json.loads(line) for line in self.output_path.read_text().splitlines()]
        self.assertEqual(["candidate-001", "candidate-002"], [row["candidate_id"] for row in rows])
        self.assertEqual("predicted", rows[0]["status"])
        self.assertEqual("predicted", rows[0]["prediction"]["state"])
        self.assertEqual("failed_generation", rows[1]["status"])
        self.assertEqual("not_evaluable", rows[1]["prediction"]["state"])
        self.assertEqual("upstream_failed", rows[1]["failure_code"])

        prediction = rows[0]["prediction"]
        for path_field, hash_field in (
            ("structure_path", "structure_sha256"),
            ("confidence_path", "confidence_sha256"),
            ("confidence_summary_path", "confidence_summary_sha256"),
        ):
            path = self.root / prediction[path_field]
            self.assertTrue(path.is_file())
            self.assertEqual(_sha256(path), prediction[hash_field])
        confidence = json.loads(
            gzip.decompress((self.root / prediction["confidence_path"]).read_bytes())
        )
        self.assertEqual(["A", "B"], confidence["chain_ids"])
        self.assertEqual([2, 2], confidence["chain_lengths"])
        self.assertEqual(4, len(confidence["pae"]))
        self.assertEqual(4, len(confidence["plddt"]))

    def test_prediction_outputs_are_deterministic(self) -> None:
        self._run([_eligible_row()])
        first_manifest = self.output_path.read_bytes()
        first_files = {
            path.relative_to(self.root).as_posix(): path.read_bytes()
            for path in sorted(self.artifact_dir.rglob("*"))
            if path.is_file()
        }
        self._run([_eligible_row()])
        self.assertEqual(first_manifest, self.output_path.read_bytes())
        self.assertEqual(
            first_files,
            {
                path.relative_to(self.root).as_posix(): path.read_bytes()
                for path in sorted(self.artifact_dir.rglob("*"))
                if path.is_file()
            },
        )

    def test_runtime_failure_writes_a_sanitized_failure_row_and_fails_closed(self) -> None:
        self._write_rows([_eligible_row()])
        with self.assertRaisesRegex(adapter.ESMFold2AdapterError, "failure rows were written"):
            adapter.run_predictions(
                run_root=self.root,
                input_path=self.input_path,
                output_path=self.output_path,
                artifact_dir=self.artifact_dir,
                variant="full",
                seed=0,
                expected_count=1,
                runtime_factory=lambda _: FailingRuntime(),
            )
        row = json.loads(self.output_path.read_text())
        self.assertEqual("failed_prediction", row["status"])
        self.assertEqual("runtime_prediction_failed", row["prediction"]["failure_code"])
        self.assertNotIn("private runtime path", self.output_path.read_text())
        self.assertFalse(self.artifact_dir.exists())

    def test_output_count_is_checked_before_the_runtime_loads(self) -> None:
        self._write_rows([_eligible_row()])
        factory = mock.Mock(side_effect=AssertionError("runtime must not load"))
        with self.assertRaisesRegex(adapter.ESMFold2AdapterError, "expected 2"):
            adapter.run_predictions(
                run_root=self.root,
                input_path=self.input_path,
                output_path=self.output_path,
                artifact_dir=self.artifact_dir,
                variant="fast",
                seed=0,
                expected_count=2,
                runtime_factory=factory,
            )
        factory.assert_not_called()

    def test_invalid_confidence_dimensions_cannot_report_success(self) -> None:
        class InvalidConfidence(FakeRuntime):
            def predict(self, chains, *, candidate_id, seed):
                result = super().predict(chains, candidate_id=candidate_id, seed=seed)
                return adapter.PredictionResult(
                    structure_cif=result.structure_cif,
                    pae=[[0.0]],
                    plddt=result.plddt,
                    ptm=result.ptm,
                    iptm=result.iptm,
                )

        self._write_rows([_eligible_row()])
        with self.assertRaisesRegex(adapter.ESMFold2AdapterError, "failure rows were written"):
            adapter.run_predictions(
                run_root=self.root,
                input_path=self.input_path,
                output_path=self.output_path,
                artifact_dir=self.artifact_dir,
                variant="fast",
                seed=0,
                expected_count=1,
                runtime_factory=lambda _: InvalidConfidence(),
            )
        row = json.loads(self.output_path.read_text())
        self.assertEqual(
            "prediction_or_sidecar_validation_failed",
            row["prediction"]["failure_code"],
        )

    def test_readiness_separates_the_wrapper_from_a_missing_optional_package(self) -> None:
        missing = ModuleNotFoundError("No module named esm")
        missing.name = "esm"
        with mock.patch.object(adapter, "_runtime_imports", side_effect=missing):
            report = adapter.runtime_readiness("fast")
        self.assertTrue(report["wrapper_ready"])
        self.assertFalse(report["package_ready"])
        self.assertFalse(report["ready"])
        self.assertIn("cannot import esm", report["next_actions"][0])

    def test_direct_run_turns_a_missing_package_into_an_actionable_adapter_error(self) -> None:
        missing = ModuleNotFoundError("No module named esm")
        missing.name = "esm"
        with mock.patch.object(adapter, "_runtime_imports", side_effect=missing):
            with self.assertRaisesRegex(
                adapter.ESMFold2AdapterError,
                "cannot import esm; run readiness",
            ):
                adapter._BiohubRuntime("fast", allow_download=False, require_cuda=True)

    def test_module_imports_only_the_standard_library(self) -> None:
        path = ROOT / "src" / "biosymphony_structure_factory" / "binder_esmfold2_adapter.py"
        tree = ast.parse(path.read_text(encoding="utf-8"))
        module_imports = []
        for node in tree.body:
            if isinstance(node, ast.Import):
                module_imports.extend(alias.name.split(".")[0] for alias in node.names)
            if isinstance(node, ast.ImportFrom) and node.module:
                module_imports.append(node.module.split(".")[0])
        self.assertTrue(
            set(module_imports).issubset(
                {
                    "__future__",
                    "argparse",
                    "dataclasses",
                    "gzip",
                    "hashlib",
                    "importlib",
                    "json",
                    "math",
                    "os",
                    "pathlib",
                    "re",
                    "sys",
                    "tempfile",
                    "typing",
                }
            )
        )

    def test_registry_pins_distinct_local_only_full_and_fast_commands(self) -> None:
        registry = json.loads(
            (ROOT / "references" / "binder-execution-adapters.json").read_text(
                encoding="utf-8"
            )
        )
        records = {
            row["tool_id"]: row
            for row in registry["adapters"]
            if row["tool_id"] in {"esmfold2", "esmfold2-fast"}
        }
        self.assertEqual({"esmfold2", "esmfold2-fast"}, set(records))
        for tool_id, variant in (("esmfold2", "full"), ("esmfold2-fast", "fast")):
            row = records[tool_id]
            self.assertEqual("ready", row["implementation_status"])
            self.assertEqual("local_argv", row["execution_kind"])
            self.assertEqual("bsf-esmfold2-predict", row["program"])
            self.assertEqual(["predictor"], row["roles"])
            self.assertEqual("forbidden", row["network_policy"])
            self.assertEqual(
                ["HF_HOME", "ESMFOLD2_CCD_PATH"],
                row["required_environment_names"],
            )
            self.assertIn(variant, row["readiness_argv"])
            self.assertIn(variant, row["command_argv"])
            self.assertNotIn("--allow-weight-download", row["command_argv"])


if __name__ == "__main__":
    unittest.main()
