from __future__ import annotations

import json
import re
import unittest
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
REGISTRY = ROOT / "references" / "software-registry.yaml"
LEDGER = ROOT / "references" / "binder-lane-capability-ledger.json"
ADAPTERS = ROOT / "references" / "binder-execution-adapters.json"


def registry_block(tool_id: str) -> str:
    text = REGISTRY.read_text(encoding="utf-8")
    match = re.search(
        rf"(?ms)^  {re.escape(tool_id)}:\n(.*?)(?=^  [a-zA-Z0-9_-]+:\n|\Z)",
        text,
    )
    if match is None:
        raise AssertionError(f"missing software registry tool: {tool_id}")
    return match.group(0)


class BinderToolFreshnessTests(unittest.TestCase):
    def test_exact_published_cohort_has_a_public_operator_card(self) -> None:
        card = (ROOT / "tools" / "published-binder-cohort.md").read_text(
            encoding="utf-8"
        )
        for name in (
            "BoltzDesign1",
            "BoltzGen",
            "FoldCraft",
            "FreeBindCraft",
            "Genie3",
            "PXDesign",
            "Protein Hunter",
            "Proteina-Complexa",
            "RFdiffusion",
            "RFdiffusion3",
            "ESMFold2-Fast",
            "ESMFold2-full",
            "Protenix-v2",
        ):
            self.assertIn(name, card)
        self.assertIn("adapter_required", card)
        self.assertIn("is not a policy prohibition", card)

    def test_pinned_local_routes_do_not_inherit_api_license_gate(self) -> None:
        for tool_id in ("esmfold2", "esmfold2-fast"):
            block = registry_block(tool_id)
            self.assertIn("license_gate: none", block)
            self.assertIn('route_terms: "biohub_api=biohub_api_terms_and_aup"', block)

    def test_replay_predictor_records_match_current_primary_sources(self) -> None:
        protenix = registry_block("protenix")
        self.assertIn("license_gate: none", protenix)
        self.assertIn("open_source_apache_2_code_and_model_parameters", protenix)
        self.assertIn("Protenix-v2", protenix)

        proteinmpnn = registry_block("proteinmpnn")
        self.assertIn(
            'upstream_commit_sha: "8907e6671bfbfc92303b5f79c4b5e6ce47cdef57"',
            proteinmpnn,
        )
        self.assertIn("weights_checkpoint_sha256", proteinmpnn)
        self.assertIn("status: pinned", proteinmpnn)

    def test_custom_complexa_targets_are_not_artificially_blocked(self) -> None:
        block = registry_block("proteina-complexa")
        self.assertIn("NVIDIA-BioNeMo/Proteina-Complexa", block)
        self.assertIn("custom protein or ligand target records", block)
        card = (ROOT / "tools" / "proteina-complexa.md").read_text(
            encoding="utf-8"
        )
        self.assertIn("custom protein and ligand target records", card)

    def test_machine_records_use_the_same_route_specific_gates(self) -> None:
        ledger = json.loads(LEDGER.read_text(encoding="utf-8"))
        adapters = json.loads(ADAPTERS.read_text(encoding="utf-8"))
        tool_gates = {row["id"]: row["license_gate"] for row in ledger["tools"]}
        adapter_gates = {
            row["tool_id"]: row["license_gate"] for row in adapters["adapters"]
        }
        for tool_id in ("esmfold2", "esmfold2-fast", "protenix"):
            self.assertEqual(tool_gates[tool_id], adapter_gates[tool_id])
        self.assertEqual("none", tool_gates["esmfold2"])
        self.assertEqual("none", tool_gates["protenix"])

    def test_simplefold_is_documented_without_claiming_bundled_execution(self) -> None:
        block = registry_block("simplefold")
        self.assertIn("apple/ml-simplefold", block)
        self.assertIn(
            "mit_code_apple_research_only_model_assets",
            block,
        )
        self.assertIn(
            "noncommercial_scientific_research_model_terms",
            block,
        )

        card = (ROOT / "tools" / "simplefold.md").read_text(encoding="utf-8")
        self.assertIn("simplefold_100M", card)
        self.assertIn("simplefold_3B", card)
        self.assertIn("adapter_required", card)
        self.assertIn("single-protein lane", card)

        ledger = json.loads(LEDGER.read_text(encoding="utf-8"))
        tool = next(row for row in ledger["tools"] if row["id"] == "simplefold")
        self.assertEqual(["predictor"], tool["roles"])
        self.assertFalse(tool["execution_available"])

        adapters = json.loads(ADAPTERS.read_text(encoding="utf-8"))
        adapter = next(
            row for row in adapters["adapters"] if row["tool_id"] == "simplefold"
        )
        self.assertEqual("adapter_required", adapter["implementation_status"])
        self.assertEqual("external_adapter", adapter["execution_kind"])
        self.assertEqual(
            {
                None,
                "simplefold-100m",
                "simplefold-360m",
                "simplefold-700m",
                "simplefold-1.1b",
                "simplefold-1.6b",
                "simplefold-3b",
            },
            {row["variant_id"] for row in adapter["supported_selections"]},
        )


if __name__ == "__main__":
    unittest.main()
