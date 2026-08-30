from __future__ import annotations

import json
import re
import unittest
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
REGISTRY_PATH = ROOT / "references" / "binder-execution-adapters.json"
SCHEMA_PATH = ROOT / "schemas" / "binder-execution-adapters.schema.json"
LEDGER_PATH = ROOT / "references" / "binder-lane-capability-ledger.json"
PUBLISHED_WORKFLOW_PATH = ROOT / "references" / "published-binder-comparison-workflow.json"

ADAPTER_FIELDS = {
    "id",
    "tool_id",
    "supported_selections",
    "roles",
    "supported_routes",
    "license_gate",
    "execution_kind",
    "program",
    "readiness_argv",
    "command_argv",
    "placeholders",
    "required_environment_names",
    "network_policy",
    "expected_outputs",
    "implementation_status",
    "public_evidence",
}
TOKEN_RE = re.compile(r"\{\{([a-z][a-z0-9_]*)\}\}")
SHELL_PROGRAMS = {"bash", "csh", "dash", "env", "fish", "ksh", "sh", "tcsh", "zsh"}
INLINE_PROGRAMS = {"bun", "deno", "node", "perl", "python", "python2", "python3", "ruby", "Rscript"}
INLINE_FLAGS = {"-c", "-e", "-E", "--eval", "--command", "--exec"}


class BinderExecutionRegistryTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        cls.registry = json.loads(REGISTRY_PATH.read_text())
        cls.schema = json.loads(SCHEMA_PATH.read_text())
        cls.ledger = json.loads(LEDGER_PATH.read_text())
        cls.published_workflow = json.loads(PUBLISHED_WORKFLOW_PATH.read_text())

    def test_registry_validates_against_schema_when_jsonschema_is_available(self) -> None:
        try:
            import jsonschema
        except ImportError:
            self.skipTest("jsonschema is optional")
        jsonschema.Draft202012Validator.check_schema(self.schema)
        jsonschema.Draft202012Validator(self.schema).validate(self.registry)

    def test_registry_and_adapter_fields_are_exact(self) -> None:
        self.assertEqual({"schema_version", "boundary", "adapters"}, set(self.registry))
        self.assertEqual(
            "structure-factory-binder-execution-adapters-v1",
            self.registry["schema_version"],
        )
        for adapter in self.registry["adapters"]:
            self.assertEqual(ADAPTER_FIELDS, set(adapter), adapter["id"])

    def test_core_tool_records_are_unique_and_join_to_the_capability_ledger(self) -> None:
        adapters = self.registry["adapters"]
        ids = [row["id"] for row in adapters]
        self.assertEqual(len(ids), len(set(ids)))
        ledger = {row["id"]: row for row in self.ledger["tools"]}
        adapter_tool_ids = {row["tool_id"] for row in adapters}
        self.assertEqual(set(ledger), adapter_tool_ids)
        self.assertTrue(
            {
                "bindcraft",
                "boltzgen",
                "promera",
                "switchcraft",
                "esmfold2",
                "protenix",
                "decaf",
                "opendde",
                "dockq-v2",
                "posebusters",
                "helixdiff",
                "pepglad",
                "evobind",
                "rfpeptides",
                "cosine",
                "rfdiffusion3",
                "solublempnn",
                "caliby",
                "solublecaliby",
                "freebindcraft",
                "foldcraft",
                "boltzdesign1",
                "protein-hunter",
                "pxdesign",
                "proteina-complexa",
                "esmfold2-fast",
                "ipsae",
                "rfantibody",
                "alphafold-multimer-v3",
                "openfold3",
                "rosettafold3",
                "status-preserving-filter",
                "diversity-filter",
            }.issubset(adapter_tool_ids)
        )
        for adapter in adapters:
            tool = ledger[adapter["tool_id"]]
            self.assertEqual(tool["license_gate"], adapter["license_gate"])
            self.assertTrue(set(adapter["roles"]).issubset(tool["roles"]))

    def test_execution_available_means_a_bundled_ready_command_exists(self) -> None:
        ready_tool_ids = {
            row["tool_id"]
            for row in self.registry["adapters"]
            if row["implementation_status"] == "ready"
        }
        self.assertEqual(
            {
                "boltz",
                "diversity-filter",
                "esmfold2",
                "esmfold2-fast",
                "status-preserving-filter",
                "supplied-backbone",
            },
            ready_tool_ids,
        )
        for tool in self.ledger["tools"]:
            self.assertEqual(tool["id"] in ready_tool_ids, tool["execution_available"])

    def test_documented_inventory_extensions_are_adapter_required(self) -> None:
        expected = {
            "helixdiff",
            "pepglad",
            "evobind",
            "rfpeptides",
            "cosine",
            "rfdiffusion3",
            "solublempnn",
            "caliby",
            "solublecaliby",
            "freebindcraft",
            "foldcraft",
            "boltzdesign1",
            "protein-hunter",
            "pxdesign",
            "proteina-complexa",
            "ipsae",
            "rfantibody",
            "alphafold-multimer-v3",
            "openfold3",
            "rosettafold3",
        }
        adapters = {
            row["tool_id"]: row
            for row in self.registry["adapters"]
            if row["tool_id"] in expected
        }
        self.assertEqual(expected, set(adapters))
        for adapter in adapters.values():
            self.assertEqual("adapter_required", adapter["implementation_status"])
            self.assertEqual("external_adapter", adapter["execution_kind"])
            self.assertIsNone(adapter["program"])

    def test_published_cohort_is_machine_readable_and_selectable(self) -> None:
        cohort = self.published_workflow["published_tool_cohort"]
        generator_ids = {row["tool_id"] for row in cohort["generators"]}
        self.assertEqual(
            {
                "boltzdesign1",
                "boltzgen",
                "foldcraft",
                "freebindcraft",
                "genie3",
                "pxdesign",
                "protein-hunter",
                "proteina-complexa",
                "rfdiffusion",
                "rfdiffusion3",
            },
            generator_ids,
        )
        sequence_designer_ids = {row["tool_id"] for row in cohort["sequence_designers"]}
        self.assertEqual(
            {"proteinmpnn", "solublempnn", "caliby", "solublecaliby"},
            sequence_designer_ids,
        )
        source_predictors = {
            (row["source_id"], row["tool_id"], row["variant_id"])
            for row in cohort["published_score_predictors"]
        }
        self.assertEqual(
            {
                ("ef2fast", "esmfold2", "esmfold2-fast"),
                ("ef2full", "esmfold2", "esmfold2-full"),
                ("ptxv2", "protenix", "protenix-v2"),
            },
            source_predictors,
        )
        scorer_ids = {row["tool_id"] for row in cohort["published_interface_scorers"]}
        self.assertEqual({"ipsae", "dockq-v2"}, scorer_ids)
        self.assertEqual(
            {"Mosaic", "HalluDesign"},
            {row["source_label"] for row in cohort["named_without_ordered_designs"]},
        )
        self.assertTrue(
            all(not row["ordered_designs_contributed"] for row in cohort["named_without_ordered_designs"])
        )
        substitutes = cohort["permitted_predictor_substitutes"]
        self.assertEqual(
            {
                "AlphaFold-Multimer v3 / ColabFold",
                "AlphaFold 3 architecture with OpenFold3 weights",
                "Chai-1",
                "Boltz-1",
                "Boltz-2",
                "AF_unmasked",
            },
            {row["source_label"] for row in substitutes},
        )
        af_unmasked = next(row for row in substitutes if row["source_label"] == "AF_unmasked")
        self.assertIsNone(af_unmasked["tool_id"])
        self.assertEqual("source_identity_not_mapped", af_unmasked["mapping_status"])
        post_hoc = {row["tool_id"] for row in cohort["post_hoc_predictors"]}
        self.assertEqual({"openfold3", "rosettafold3", "opendde"}, post_hoc)

        selectable = {row["id"] for row in self.ledger["tools"]}
        adapter_tools = {row["tool_id"] for row in self.registry["adapters"]}
        exact_replay_tools = generator_ids | sequence_designer_ids | {"esmfold2", "protenix"} | scorer_ids
        self.assertTrue(exact_replay_tools.issubset(selectable))
        self.assertTrue(exact_replay_tools.issubset(adapter_tools))
        self.assertIn("esmfold2-fast", selectable)
        self.assertIn("esmfold2-fast", adapter_tools)
        mapped_substitutes = {row["tool_id"] for row in substitutes if row["tool_id"] is not None}
        self.assertTrue((mapped_substitutes | post_hoc).issubset(selectable))
        self.assertTrue((mapped_substitutes | post_hoc).issubset(adapter_tools))
        self.assertNotIn("rfantibody", generator_ids)
        self.assertIn("outside the published cohort", self.published_workflow["replay_policy"]["inventory_scope"])

    def test_every_mapped_published_selection_has_an_exact_adapter_identity(self) -> None:
        cohort = self.published_workflow["published_tool_cohort"]
        mapped_rows = []
        for group in (
            "generators",
            "sequence_designers",
            "published_score_predictors",
            "published_interface_scorers",
            "permitted_predictor_substitutes",
            "post_hoc_predictors",
        ):
            mapped_rows.extend(cohort[group])
        expected = {
            (row["tool_id"], row.get("variant_id"))
            for row in mapped_rows
            if row.get("tool_id") is not None
        }
        declared = {
            (selection["tool_id"], selection["variant_id"])
            for adapter in self.registry["adapters"]
            for selection in adapter["supported_selections"]
        }
        self.assertTrue(expected.issubset(declared), sorted(expected - declared))

    def test_boltz_versioned_selections_do_not_use_the_unversioned_ready_command(self) -> None:
        adapters = {row["id"]: row for row in self.registry["adapters"]}
        unversioned = adapters["boltz-local-v1"]
        self.assertEqual(
            [{"tool_id": "boltz", "variant_id": None}],
            unversioned["supported_selections"],
        )
        for adapter_id, variant_id in (
            ("boltz-1-local-adapter-v1", "boltz-1"),
            ("boltz-2-local-adapter-v1", "boltz-2"),
        ):
            adapter = adapters[adapter_id]
            self.assertEqual("adapter_required", adapter["implementation_status"])
            self.assertEqual("external_adapter", adapter["execution_kind"])
            self.assertEqual(
                [{"tool_id": "boltz", "variant_id": variant_id}],
                adapter["supported_selections"],
            )

    def test_execution_boundary_matches_executor_behavior(self) -> None:
        execution = self.registry["boundary"]["execution"]
        self.assertIn("any validated local_argv record", execution)
        self.assertIn("bundled or runtime registry", execution)
        self.assertIn("explicit local authorization", execution)
        self.assertNotIn("only records marked ready or built_in", execution)

    def test_ready_argv_uses_a_literal_program_without_shell_syntax(self) -> None:
        ready = [row for row in self.registry["adapters"] if row["implementation_status"] == "ready"]
        self.assertGreaterEqual(len(ready), 1)
        for adapter in ready:
            program = adapter["program"]
            self.assertIsInstance(program, str)
            self.assertNotIn(program, SHELL_PROGRAMS)
            self.assertNotIn("{{", program)
            for field in ("readiness_argv", "command_argv"):
                argv = adapter[field]
                self.assertEqual(program, argv[0])
                self.assertFalse(any(char in item for item in argv for char in ";|`\n\r"))
                if program in INLINE_PROGRAMS:
                    self.assertTrue(INLINE_FLAGS.isdisjoint(argv[1:]))
            command_tokens = {
                token
                for item in adapter["command_argv"]
                for token in TOKEN_RE.findall(item)
            }
            self.assertEqual(set(adapter["placeholders"]), command_tokens)

    def test_all_adapters_have_typed_inputs_and_outputs(self) -> None:
        for adapter in self.registry["adapters"]:
            self.assertTrue(adapter["placeholders"], adapter["id"])
            for spec in adapter["placeholders"].values():
                self.assertIn(spec["type"], {"string", "integer", "number", "boolean", "path"})
            self.assertTrue(adapter["expected_outputs"], adapter["id"])

    def test_adapters_declare_unique_route_capabilities(self) -> None:
        for adapter in self.registry["adapters"]:
            routes = adapter["supported_routes"]
            self.assertTrue(routes, adapter["id"])
            identities = {(route["backend"], route["execution_method"]) for route in routes}
            self.assertEqual(len(routes), len(identities), adapter["id"])

    def test_esmfold2_adapters_preserve_full_and_fast_selection_identity(self) -> None:
        adapters = {row["id"]: row for row in self.registry["adapters"]}
        full = adapters["esmfold2-local-adapter-v1"]
        fast = adapters["esmfold2-fast-adapter-v1"]
        self.assertIn({"tool_id": "esmfold2", "variant_id": "esmfold2-full"}, full["supported_selections"])
        self.assertNotIn({"tool_id": "esmfold2", "variant_id": "esmfold2-fast"}, full["supported_selections"])
        self.assertIn({"tool_id": "esmfold2", "variant_id": "esmfold2-fast"}, fast["supported_selections"])

    def test_unimplemented_adapters_do_not_guess_commands(self) -> None:
        for adapter in self.registry["adapters"]:
            status = adapter["implementation_status"]
            if status == "adapter_required":
                self.assertIsNone(adapter["program"])
                self.assertEqual([], adapter["readiness_argv"])
                self.assertEqual([], adapter["command_argv"])
            if status == "built_in":
                self.assertEqual("built_in", adapter["execution_kind"])
                self.assertIsNone(adapter["program"])
                self.assertEqual([], adapter["readiness_argv"])
                self.assertEqual([], adapter["command_argv"])
                self.assertEqual("forbidden", adapter["network_policy"])

    def test_expected_outputs_use_declared_placeholders_and_positive_counts(self) -> None:
        for adapter in self.registry["adapters"]:
            declared = set(adapter["placeholders"])
            output_ids = []
            for output in adapter["expected_outputs"]:
                output_ids.append(output["id"])
                self.assertGreaterEqual(output["minimum_count"], 1)
                self.assertTrue(set(TOKEN_RE.findall(output["path_template"])).issubset(declared))
                self.assertFalse(any(char in output["path_template"] for char in ";|`\n\r"))
            self.assertEqual(len(output_ids), len(set(output_ids)))

    def test_public_evidence_is_repo_relative_and_exists(self) -> None:
        for adapter in self.registry["adapters"]:
            for relative in adapter["public_evidence"]:
                path = Path(relative)
                self.assertFalse(path.is_absolute())
                self.assertNotIn("..", path.parts)
                resolved = (ROOT / path).resolve()
                self.assertIn(ROOT.resolve(), resolved.parents)
                self.assertTrue(resolved.is_file(), f"missing evidence for {adapter['id']}: {relative}")

    def test_registry_contains_no_private_or_provider_specific_values(self) -> None:
        text = REGISTRY_PATH.read_text()
        forbidden = (
            "/" + "Users/",
            "/" + "Volumes/",
            "github" + "_2",
            "fal" + ".run/",
            "api" + "_key",
            "access" + "_token",
            "private" + "_key",
            "provider" + "_account_id",
        )
        for marker in forbidden:
            self.assertNotIn(marker, text.lower() if marker == marker.lower() else text)
        self.assertNotRegex(text, r"https?://(?!biosymphony\.org/schemas/)")

    def test_registry_json_has_no_duplicate_object_keys(self) -> None:
        def reject_duplicates(pairs: list[tuple[str, object]]) -> dict[str, object]:
            result: dict[str, object] = {}
            for key, value in pairs:
                self.assertNotIn(key, result, f"duplicate JSON key: {key}")
                result[key] = value
            return result

        json.loads(REGISTRY_PATH.read_text(), object_pairs_hook=reject_duplicates)

    def test_extension_rules_keep_added_adapters_inside_the_executor_contract(self) -> None:
        rules = " ".join(self.registry["boundary"]["extensions"])
        for phrase in (
            "unique ID",
            "literal program name",
            "argument arrays",
            "environment-variable name",
            "expected output",
            "path containment",
        ):
            self.assertIn(phrase, rules)

    def test_portable_skill_copies_match_the_canonical_files(self) -> None:
        mirrors = (
            ROOT / "skills" / "binder-lane-round" / "references" / "references" / REGISTRY_PATH.name,
            ROOT / "skills" / "biosymphony-structure-factory" / "references" / REGISTRY_PATH.name,
            ROOT / "skills" / "biosymphony-structure-factory" / "references" / "references" / REGISTRY_PATH.name,
            ROOT / "skills" / "binder-lane-round" / "references" / "schemas" / SCHEMA_PATH.name,
            ROOT / "skills" / "biosymphony-structure-factory" / "references" / "schemas" / SCHEMA_PATH.name,
            ROOT / "skills" / "binder-lane-round" / "references" / "references" / LEDGER_PATH.name,
            ROOT / "skills" / "biosymphony-structure-factory" / "references" / LEDGER_PATH.name,
            ROOT / "skills" / "biosymphony-structure-factory" / "references" / "references" / LEDGER_PATH.name,
            ROOT / "skills" / "binder-lane-round" / "references" / "references" / PUBLISHED_WORKFLOW_PATH.name,
            ROOT / "skills" / "biosymphony-structure-factory" / "references" / PUBLISHED_WORKFLOW_PATH.name,
            ROOT / "skills" / "biosymphony-structure-factory" / "references" / "references" / PUBLISHED_WORKFLOW_PATH.name,
        )
        canonical_by_name = {
            REGISTRY_PATH.name: REGISTRY_PATH.read_bytes(),
            SCHEMA_PATH.name: SCHEMA_PATH.read_bytes(),
            LEDGER_PATH.name: LEDGER_PATH.read_bytes(),
            PUBLISHED_WORKFLOW_PATH.name: PUBLISHED_WORKFLOW_PATH.read_bytes(),
        }
        for mirror in mirrors:
            self.assertEqual(canonical_by_name[mirror.name], mirror.read_bytes(), str(mirror))


if __name__ == "__main__":
    unittest.main()
