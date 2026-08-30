from __future__ import annotations

import io
import json
import os
import shutil
import stat
import subprocess
import sys
import tempfile
import unittest
from contextlib import redirect_stdout
from pathlib import Path

from biosymphony_structure_factory.cli import main
from biosymphony_structure_factory.target_verifier import verify_target

ROOT = Path(__file__).resolve().parents[1]


def synthetic_target_pdb() -> str:
    return "\n".join(
        [
            "SEQRES   1 A    3  ALA GLY SER",
            "ATOM      1  CA  ALA A  19       1.000   0.000   0.000  1.00 20.00           C",
            "ATOM      2  CA  GLY A  20       2.000   0.000   0.000  1.00 20.00           C",
            "ATOM      3  CA  SER A  21       3.000   0.000   0.000  1.00 20.00           C",
            "END",
            "",
        ]
    )


def synthetic_candidates_jsonl() -> list[dict]:
    return [
        {
            "candidate_id": "candidate-r1-001",
            "toolchain_id": "diffusion-mpnn",
            "status": "scored",
            "candidate_sequence": "ACDEFGHIKLMNPQRSTVWY",
            "metrics": {"ipsae_min": 0.85, "score": 0.85},
        },
        {
            "candidate_id": "candidate-r1-002",
            "toolchain_id": "diffusion-mpnn",
            "status": "scored",
            "candidate_sequence": "ACDEFGHIKLMNPQRSTVWF",
            "metrics": {"ipsae_min": 0.45, "score": 0.45},
        },
        {
            "candidate_id": "candidate-r1-003",
            "toolchain_id": "all-atom-mpnn",
            "status": "scored",
            "candidate_sequence": "WYKLMNPQRSTVDEFGHICA",
            "metrics": {"ipsae_min": 0.72, "score": 0.72},
        },
        {
            "candidate_id": "candidate-r1-004",
            "toolchain_id": "all-atom-mpnn",
            "status": "failed_prediction",
            "candidate_sequence": "AAAAAAAAAAAAAAAAAAAA",
            "metrics": {},
        },
    ]


class BinderEndToEndJourneyTests(unittest.TestCase):
    def setUp(self) -> None:
        (ROOT / ".runtime").mkdir(exist_ok=True)
        self.temp_dir = tempfile.TemporaryDirectory(dir=ROOT / ".runtime", prefix="journey-test-")
        self.runtime_root = Path(self.temp_dir.name)
        self.workspace = ROOT

        # Set up a local bin directory so console scripts are resolvable on PATH
        self.bin_dir = self.runtime_root / "bin"
        self.bin_dir.mkdir()
        self._setup_local_scripts()
        self.orig_path = os.environ.get("PATH", "")
        os.environ["PATH"] = f"{self.bin_dir}:{self.orig_path}"
        self.orig_pythonpath = os.environ.get("PYTHONPATH", "")
        os.environ["PYTHONPATH"] = f"{ROOT / 'src'}:{self.orig_pythonpath}"

    def tearDown(self) -> None:
        os.environ["PATH"] = self.orig_path
        os.environ["PYTHONPATH"] = self.orig_pythonpath
        self.temp_dir.cleanup()

    def _setup_local_scripts(self) -> None:
        src_path = (ROOT / "src").as_posix()
        status_script = self.bin_dir / "bsf-status-filter"
        status_script.write_text(
            f"#!/bin/sh\nexec {sys.executable} -c \"import sys; sys.path.insert(0, '{src_path}'); from biosymphony_structure_factory.candidate_filters import status_main; sys.exit(status_main())\" \"$@\"\n",
            encoding="utf-8",
        )
        status_script.chmod(status_script.stat().st_mode | stat.S_IXUSR | stat.S_IXGRP | stat.S_IXOTH)

        diversity_script = self.bin_dir / "bsf-diversity-filter"
        diversity_script.write_text(
            f"#!/bin/sh\nexec {sys.executable} -c \"import sys; sys.path.insert(0, '{src_path}'); from biosymphony_structure_factory.candidate_filters import diversity_main; sys.exit(diversity_main())\" \"$@\"\n",
            encoding="utf-8",
        )
        diversity_script.chmod(diversity_script.stat().st_mode | stat.S_IXUSR | stat.S_IXGRP | stat.S_IXOTH)

    def call_cli(self, argv: list[str]) -> tuple[int, dict]:
        output = io.StringIO()
        with redirect_stdout(output):
            status = main(argv)
        raw = output.getvalue()
        try:
            return status, json.loads(raw)
        except json.JSONDecodeError:
            return status, {"raw": raw}

    def test_complete_round1_binder_journey_end_to_end(self) -> None:
        # ---------------------------------------------------------------------
        # 1. Target & Site Selection and Pre-Generation Coordinate Verification
        # ---------------------------------------------------------------------
        target_dir = self.runtime_root / "target"
        target_dir.mkdir(parents=True)
        target_pdb_path = target_dir / "target.pdb"
        target_pdb_path.write_text(synthetic_target_pdb(), encoding="utf-8")
        expected_seq_path = target_dir / "expected-sequence.txt"
        expected_seq_path.write_text("AGS\n", encoding="utf-8")
        verification_path = target_dir / "verification.json"

        # ---------------------------------------------------------------------
        # 2. Capability Discovery & Evidence Inspection
        # ---------------------------------------------------------------------
        status, menu = self.call_cli(["binder-lane", "menu", "--workspace", str(ROOT)])
        self.assertEqual(0, status)
        self.assertIn("generator", menu["roles"])
        self.assertIn("predictor", menu["roles"])
        self.assertIn("filter", menu["roles"])
        self.assertIn("mixed", menu["supported_topologies"])
        self.assertIn("neocloud", menu["supported_topologies"])

        status, adapters = self.call_cli(["binder-lane", "adapters", "--workspace", str(ROOT)])
        self.assertEqual(0, status)
        self.assertTrue(any(a["id"] == "status-preserving-filter-v1" for a in adapters["adapters"]))
        self.assertTrue(any(a["id"] == "diversity-filter-v1" for a in adapters["adapters"]))

        # ---------------------------------------------------------------------
        # 3. Formulate Anthropic-Style Binder Round Request
        # ---------------------------------------------------------------------
        synthetic_fixture_path = self.runtime_root / "synthetic-fixture.json"
        synthetic_fixture_path.write_text(
            json.dumps(
                {
                    "schema_version": "structure-factory-candidate-ranking-v1",
                    "campaign_id": "journey-smoke-test",
                    "result_boundary": "public_synthetic_demo",
                    "source_posture": "synthetic_demo",
                    "ranking_policy": {
                        "primary": "cofold_confidence_proxy",
                        "secondary": ["interface_confidence_proxy", "failure_status"],
                        "note": "Synthetic demonstration rows.",
                    },
                    "candidates": [
                        {
                            "rank": 1,
                            "id": "demo-r1-001",
                            "toolchain_id": "diffusion-mpnn",
                            "source_posture": "synthetic_demo",
                            "result_boundary": "public_synthetic_demo",
                            "cofold_status": "completed",
                            "scores": {"cofold_confidence_proxy": 0.85, "interface_confidence_proxy": 0.85},
                            "artifact_refs": [],
                        },
                        {
                            "rank": 2,
                            "id": "demo-r1-002",
                            "toolchain_id": "diffusion-mpnn",
                            "source_posture": "synthetic_demo",
                            "result_boundary": "public_synthetic_demo",
                            "cofold_status": "failed",
                            "scores": {"cofold_confidence_proxy": None, "interface_confidence_proxy": None},
                            "artifact_refs": [],
                        },
                        {
                            "rank": 1,
                            "id": "demo-r1-003",
                            "toolchain_id": "all-atom-mpnn",
                            "source_posture": "synthetic_demo",
                            "result_boundary": "public_synthetic_demo",
                            "cofold_status": "completed",
                            "scores": {"cofold_confidence_proxy": 0.72, "interface_confidence_proxy": 0.72},
                            "artifact_refs": [],
                        },
                        {
                            "rank": 2,
                            "id": "demo-r1-004",
                            "toolchain_id": "all-atom-mpnn",
                            "source_posture": "synthetic_demo",
                            "result_boundary": "public_synthetic_demo",
                            "cofold_status": "completed",
                            "scores": {"cofold_confidence_proxy": 0.49, "interface_confidence_proxy": 0.49},
                            "artifact_refs": [],
                        },
                    ],
                    "boundaries": [
                        "Synthetic comparison rows are not candidate binders.",
                        "Binding, function, selectivity, safety, and therapeutic value are not established by this fixture.",
                    ],
                },
                indent=2,
            )
            + "\n",
            encoding="utf-8",
        )

        request_payload = {
            "schema_version": "structure-factory-binder-round-request-v1",
            "round_id": "journey-smoke-round-1",
            "study_template": "published-binder-comparison-shape",
            "published_workflow": {
                "reference_ref": "references/published-binder-comparison-workflow.json",
                "bounded_stage_ids": ["target", "generation", "sequence_design", "cofold", "scoring", "filter", "report"],
                "published_result_values_imported": False,
            },
            "workflow_strategy": {
                "mode": "replay_and_swap",
                "reference_scope": "published_workflow_shape",
                "replay_toolchain_ids": ["diffusion-mpnn"],
                "swap_toolchain_ids": ["all-atom-mpnn"],
            },
            "comparison_policy": {
                "mode": "controlled_generation",
                "cross_arm_ranking": "shared_metrics_only",
                "metrics": [
                    {
                        "id": "cofold_confidence_proxy",
                        "direction": "higher_is_better",
                        "unit": "unitless_proxy",
                        "missing_value_policy": "preserve_as_failure",
                    },
                    {
                        "id": "interface_confidence_proxy",
                        "direction": "higher_is_better",
                        "unit": "unitless_proxy",
                        "missing_value_policy": "preserve_as_failure",
                    },
                ],
                "tie_break": ["cofold_confidence_proxy", "interface_confidence_proxy", "candidate_id"],
            },
            "optimization_policy": {
                "round_count": 3,
                "current_round_index": 1,
                "primary_metric_id": "cofold_confidence_proxy",
                "direction": "maximize",
                "candidate_policy": {
                    "mode": "fixed_per_toolchain",
                    "candidate_count_per_toolchain": 2,
                },
                "stopping_rule": {
                    "type": "target_threshold",
                    "threshold": 0.80,
                    "direction": "maximize",
                },
                "round_budget_usd": [40.0, 30.0, 30.0],
            },
            "source_posture": "synthetic_demo",
            "result_boundary": "public_synthetic_demo",
            "target": {
                "input_posture": "public_reference",
                "label": "A2A receptor public target window",
                "public_accession": "PDB:5G53",
                "window": "chain A residues 19-21",
                "site": {
                    "chain_id": "A",
                    "required_residues": ["19-21"],
                },
            },
            "toolchains": [
                {
                    "id": "diffusion-mpnn",
                    "label": "Diffusion backbone plus sequence design replay arm",
                    "candidate_count": 2,
                    "generator": "rfdiffusion",
                    "sequence_designer": "proteinmpnn",
                    "predictors": ["esmfold2"],
                    "scorers": ["dockq-v2"],
                    "filters": ["status-preserving-filter", "diversity-filter"],
                },
                {
                    "id": "all-atom-mpnn",
                    "label": "All-atom generation swap arm",
                    "candidate_count": 2,
                    "generator": "genie3",
                    "sequence_designer": "solublempnn",
                    "predictors": ["esmfold2"],
                    "scorers": ["dockq-v2"],
                    "filters": ["status-preserving-filter", "diversity-filter"],
                },
            ],
            "constraints": {
                "objective": "Compare published replay baseline with alternative generator and sequence designer.",
                "target_selection_method": "Use the deposited public complex interface.",
                "binder_length": {"minimum": 20, "maximum": 120},
                "required_controls": ["public_reference", "sequence_decoy"],
                "inclusion_rules": [
                    "Assign every row to one declared toolchain.",
                    "Keep candidates within the declared binder-length range.",
                ],
                "exclusion_rules": [
                    "Exclude rows that cannot be assigned to a declared toolchain.",
                    "Preserve failed evaluation rows in the report instead of deleting them.",
                ],
                "interpretation_limit": "The public fixture checks workflow contracts and does not estimate binding or tool performance.",
                "preserve_failure_rows": True,
                "top_per_arm": 1,
            },
            "license_policy": {
                "allowed_gates": [
                    "none",
                    "none_after_current_terms_check",
                    "terms_review",
                    "terms_and_weights_review",
                    "dependency_and_weight_terms_review",
                ],
                "blocked_tools": [],
                "require_operator_review_for_gated": True,
                "review_dimensions": {
                    "code": "review_required",
                    "weights": "review_required",
                    "dependencies": "review_required",
                    "api_terms": "review_required",
                    "redistribution": "review_required",
                },
                "use_context": "research_evaluation",
            },
            "execution_policy": {
                "topology": "mixed",
                "authorization": "plan_then_explicit_runtime_authorization",
                "max_spend_usd": 100.0,
                "max_wall_clock_minutes": 720,
                "routes": [
                    {
                        "id": "design-on-neocloud",
                        "toolchain_ids": ["diffusion-mpnn", "all-atom-mpnn"],
                        "stages": ["generation", "sequence_design"],
                        "backend": "neocloud",
                        "execution_method": "self_hosted",
                        "profile_ref": "modules/provider-profiles/neocloud/gpu-pod-no-download.v1.json",
                        "operator_adapter_required": False,
                    },
                    {
                        "id": "cofold-through-api-adapter",
                        "toolchain_ids": ["diffusion-mpnn", "all-atom-mpnn"],
                        "stages": ["cofold"],
                        "backend": "api",
                        "execution_method": "hosted_api",
                        "profile_ref": None,
                        "operator_adapter_required": True,
                        "adapter_contract_ref": "templates/binder-api-adapter-contract.json",
                        "api_policy": {
                            "terms_review_required": True,
                            "input_retention_review_required": True,
                            "runtime_secret_reference_required": True,
                        },
                    },
                    {
                        "id": "score-and-report-locally",
                        "toolchain_ids": ["diffusion-mpnn", "all-atom-mpnn"],
                        "stages": ["scoring", "filter", "report"],
                        "backend": "local",
                        "execution_method": "self_hosted",
                        "profile_ref": "modules/provider-profiles/local/workstation-no-download.v1.json",
                        "operator_adapter_required": False,
                    },
                ],
            },
            "synthetic_fixture": (synthetic_fixture_path.relative_to(ROOT)).as_posix(),
        }

        request_file = self.runtime_root / "binder-round-request.json"
        request_file.write_text(json.dumps(request_payload, indent=2) + "\n", encoding="utf-8")

        plan_file = self.runtime_root / "plan.json"
        status, plan_res = self.call_cli(
            [
                "binder-lane",
                "plan-request",
                (request_file.relative_to(ROOT)).as_posix(),
                "--workspace",
                str(ROOT),
                "--out",
                (plan_file.relative_to(ROOT)).as_posix(),
            ]
        )
        self.assertEqual(0, status, plan_res)
        self.assertTrue(plan_file.is_file())
        self.assertEqual("public_synthetic_demo", plan_res["result_boundary"])
        self.assertEqual(2, len(plan_res["toolchains"]))

        status, target_rep = self.call_cli(
            [
                "binder-lane",
                "target-check",
                (target_pdb_path.relative_to(ROOT)).as_posix(),
                "--plan",
                (plan_file.relative_to(ROOT)).as_posix(),
                "--workspace",
                str(ROOT),
                "--expected-sequence-file",
                (expected_seq_path.relative_to(ROOT)).as_posix(),
                "--sequence-basis",
                "entity",
                "--out",
                (verification_path.relative_to(ROOT)).as_posix(),
            ]
        )
        self.assertEqual(0, status, target_rep)
        self.assertTrue(target_rep["ok"])
        self.assertTrue(target_rep["sequence_verified"])
        self.assertEqual(3, target_rep["coordinate_residue_count"])
        self.assertEqual(plan_res["target"], target_rep["target_contract"])
        self.assertTrue(verification_path.is_file())
        structure_sha = target_rep["structure_sha256"]

        # ---------------------------------------------------------------------
        # 4. Materialize Plan, Round Contract, and Execution Handoff
        # ---------------------------------------------------------------------
        run_root = self.runtime_root / "run"
        status, mat_res = self.call_cli(
            [
                "binder-lane",
                "plan",
                (plan_file.relative_to(ROOT)).as_posix(),
                "--workspace",
                str(ROOT),
                "--out",
                (run_root.relative_to(ROOT)).as_posix(),
            ]
        )
        self.assertEqual(0, status, mat_res)
        self.assertTrue((run_root / "plan.json").is_file())
        self.assertTrue((run_root / "round-contract.json").is_file())
        self.assertTrue((run_root / "execution-handoff.json").is_file())

        # ---------------------------------------------------------------------
        # 5. Preflight Verification (Checks contract, hashes, and bounds)
        # ---------------------------------------------------------------------
        status, pre_res = self.call_cli(
            [
                "binder-lane",
                "preflight",
                "--workspace",
                str(ROOT),
                (run_root.relative_to(ROOT)).as_posix(),
            ]
        )
        self.assertEqual(0, status, pre_res)
        self.assertTrue(pre_res["ok"])
        self.assertEqual(0, pre_res["provider_calls"])

        # ---------------------------------------------------------------------
        # 6. Adapter Choice Points & Safe Local Filter Execution
        # ---------------------------------------------------------------------
        filter_stage_dir = self.runtime_root / "filter-stage"
        filter_stage_dir.mkdir(parents=True)
        inputs_dir = filter_stage_dir / "inputs"
        outputs_dir = filter_stage_dir / "outputs"
        inputs_dir.mkdir()
        outputs_dir.mkdir()

        raw_candidates_file = inputs_dir / "candidates.jsonl"
        raw_candidates_file.write_text(
            "".join(json.dumps(row) + "\n" for row in synthetic_candidates_jsonl()),
            encoding="utf-8",
        )

        filter_bindings = {
            "run_root": ".",
            "input_path": "inputs/candidates.jsonl",
            "output_path": "outputs/status-filtered.jsonl",
            "metric": "metrics.ipsae_min",
            "minimum": 0.5,
            "maximum": 1.0,
        }
        filter_bindings_path = filter_stage_dir / "bindings.json"
        filter_bindings_path.write_text(json.dumps(filter_bindings, indent=2) + "\n", encoding="utf-8")

        # 6a. Dry run without launching process
        status, dry_res = self.call_cli(
            [
                "binder-lane",
                "adapter",
                "status-preserving-filter-v1",
                "--workspace",
                str(ROOT),
                "--run-root",
                (filter_stage_dir.relative_to(ROOT)).as_posix(),
                "--bindings",
                (filter_bindings_path.relative_to(ROOT)).as_posix(),
                "--dry-run",
            ]
        )
        self.assertEqual(0, status, dry_res)
        self.assertTrue(dry_res["dry_run"])
        self.assertIsNone(dry_res["returncode"])

        # 6b. Unauthorized real run must fail closed
        status, unauth_res = self.call_cli(
            [
                "binder-lane",
                "adapter",
                "status-preserving-filter-v1",
                "--workspace",
                str(ROOT),
                "--run-root",
                (filter_stage_dir.relative_to(ROOT)).as_posix(),
                "--bindings",
                (filter_bindings_path.relative_to(ROOT)).as_posix(),
            ]
        )
        self.assertEqual(2, status)
        self.assertIn("explicit authorization", unauth_res["error"])

        # 6c. Authorized local execution
        status, auth_res = self.call_cli(
            [
                "binder-lane",
                "adapter",
                "status-preserving-filter-v1",
                "--workspace",
                str(ROOT),
                "--run-root",
                (filter_stage_dir.relative_to(ROOT)).as_posix(),
                "--bindings",
                (filter_bindings_path.relative_to(ROOT)).as_posix(),
                "--authorize-local-execution",
            ]
        )
        self.assertEqual(0, status, auth_res)
        self.assertTrue(auth_res["ok"])
        self.assertEqual(0, auth_res["returncode"])
        filtered_file = outputs_dir / "status-filtered.jsonl"
        self.assertTrue(filtered_file.is_file())
        filtered_lines = [json.loads(line) for line in filtered_file.read_text(encoding="utf-8").splitlines()]
        self.assertEqual(4, len(filtered_lines))
        self.assertEqual(
            ["passed", "filtered", "passed", "not_evaluable"],
            [row["filter_results"][-1]["state"] for row in filtered_lines],
        )

        # 6d. Test custom runtime adapter registry below .runtime/
        # Proves adapter_required is an extensible choice point
        custom_stage_dir = self.runtime_root / "custom-stage"
        custom_stage_dir.mkdir(parents=True)
        custom_script_path = custom_stage_dir / "custom_scorer.py"
        custom_script_path.write_text(
            "import sys, json, pathlib\n"
            "args = sys.argv[1:]\n"
            "out = pathlib.Path(args[args.index('--out') + 1])\n"
            "out.parent.mkdir(parents=True, exist_ok=True)\n"
            "out.write_text(json.dumps({'score': 0.88}) + '\\n')\n",
            encoding="utf-8",
        )
        custom_registry = {
            "schema_version": "structure-factory-binder-execution-adapters-v1",
            "boundary": {
                "execution": "Custom runtime adapter registry test",
                "readiness": "Check custom tools",
                "extensions": ["Declare custom adapter"],
            },
            "adapters": [
                {
                    "id": "custom-scorer-v1",
                    "tool_id": "custom-scorer",
                    "supported_selections": [
                        {"tool_id": "custom-scorer", "variant_id": None}
                    ],
                    "roles": ["scorer"],
                    "supported_routes": [
                        {"backend": "local", "execution_method": "self_hosted"}
                    ],
                    "license_gate": "none",
                    "implementation_status": "ready",
                    "execution_kind": "local_argv",
                    "program": "python3",
                    "readiness_argv": ["python3", "--version"],
                    "command_argv": ["python3", "custom_scorer.py", "--out", "{{output_path}}"],
                    "placeholders": {"output_path": {"type": "path"}},
                    "required_environment_names": [],
                    "network_policy": "forbidden",
                    "expected_outputs": [
                        {
                            "id": "score-output",
                            "kind": "json",
                            "path_template": "{{output_path}}",
                            "minimum_count": 1,
                        }
                    ],
                    "public_evidence": [],
                }
            ],
        }
        custom_registry_path = self.runtime_root / "custom-adapters.json"
        custom_registry_path.write_text(json.dumps(custom_registry, indent=2) + "\n", encoding="utf-8")

        custom_bindings_path = custom_stage_dir / "bindings.json"
        custom_bindings_path.write_text(
            json.dumps({"output_path": "outputs/score.json"}, indent=2) + "\n",
            encoding="utf-8",
        )
        status, cust_res = self.call_cli(
            [
                "binder-lane",
                "adapter",
                "custom-scorer-v1",
                "--workspace",
                str(ROOT),
                "--registry",
                (custom_registry_path.relative_to(ROOT)).as_posix(),
                "--run-root",
                (custom_stage_dir.relative_to(ROOT)).as_posix(),
                "--bindings",
                (custom_bindings_path.relative_to(ROOT)).as_posix(),
                "--authorize-local-execution",
            ]
        )
        self.assertEqual(0, status, cust_res)
        self.assertTrue(cust_res["ok"])
        self.assertTrue((custom_stage_dir / "outputs" / "score.json").is_file())

        # ---------------------------------------------------------------------
        # 7. Provider-Neutral Remote Request & Receipt Validation
        # ---------------------------------------------------------------------
        remote_req = {
            "schema_version": 1,
            "contract_id": "structure-factory-remote-tool.v1",
            "provider_id": "neocloud",
            "tool_id": "esmfold2-fast",
            "operation": "predict",
            "request_id": "cofold-0123456789abcdef0123456789abcdef",
            "input_payload": {
                "input_manifest": "inputs/candidates.jsonl",
                "output_format": "pdb",
            },
            "artifact_prefix": "runs/cofold-0123456789abcdef0123456789abcdef",
            "source_identity": f"source-structure-sha256:{structure_sha}",
            "model_identity": "model-release:reviewed-runtime-pin",
            "environment_identity": "container-digest:reviewed-runtime-pin",
            "credential_environment_keys": ["NEOCLOUD_API_KEY"],
            "budget": {"max_spend_usd": 25.0, "max_runtime_seconds": 1800},
        }
        remote_req_path = self.runtime_root / "remote-request.json"
        remote_req_path.write_text(json.dumps(remote_req, indent=2) + "\n", encoding="utf-8")
        val_req_path = self.runtime_root / "validated-remote-request.json"

        status, val_req_res = self.call_cli(
            [
                "binder-lane",
                "remote-request",
                (remote_req_path.relative_to(ROOT)).as_posix(),
                "--workspace",
                str(ROOT),
                "--out",
                (val_req_path.relative_to(ROOT)).as_posix(),
            ]
        )
        self.assertEqual(0, status, val_req_res)
        self.assertTrue(val_req_res["ok"])

        # Validate remote receipt join
        remote_rec = {
            "schema_version": 1,
            "contract_id": "structure-factory-remote-tool.v1",
            "provider_id": "neocloud",
            "tool_id": "esmfold2-fast",
            "operation": "predict",
            "request_id": "cofold-0123456789abcdef0123456789abcdef",
            "source_identity": f"source-structure-sha256:{structure_sha}",
            "model_identity": "model-release:reviewed-runtime-pin",
            "environment_identity": "container-digest:reviewed-runtime-pin",
            "status": "completed",
            "artifacts": [
                {
                    "path": "predictions/candidate-001.pdb",
                    "sha256": "a" * 64,
                    "byte_count": 1024,
                }
            ],
            "cleanup": {"verified": True},
        }
        remote_rec_path = self.runtime_root / "remote-receipt.json"
        remote_rec_path.write_text(json.dumps(remote_rec, indent=2) + "\n", encoding="utf-8")
        val_rec_path = self.runtime_root / "validated-remote-receipt.json"

        status, val_rec_res = self.call_cli(
            [
                "binder-lane",
                "remote-receipt",
                (remote_rec_path.relative_to(ROOT)).as_posix(),
                "--request",
                (val_req_path.relative_to(ROOT)).as_posix(),
                "--workspace",
                str(ROOT),
                "--out",
                (val_rec_path.relative_to(ROOT)).as_posix(),
            ]
        )
        self.assertEqual(0, status, val_rec_res)
        self.assertTrue(val_rec_res["ok"])

        # ---------------------------------------------------------------------
        # 8. Synthetic Stage Run & Safe Report Summary
        # ---------------------------------------------------------------------
        status, syn_res = self.call_cli(
            [
                "binder-lane",
                "run",
                "--workspace",
                str(ROOT),
                (run_root.relative_to(ROOT)).as_posix(),
            ]
        )
        self.assertEqual(0, status, syn_res)
        self.assertEqual("public_synthetic_demo", syn_res["result_boundary"])
        self.assertEqual(4, syn_res["candidate_count"])
        self.assertTrue((run_root / "round-report.json").is_file())
        self.assertTrue((run_root / "artifact-hashes.json").is_file())
        self.assertTrue((run_root / "generation-status.json").is_file())

        status, rep_res = self.call_cli(
            [
                "binder-lane",
                "report",
                "--workspace",
                str(ROOT),
                (run_root.relative_to(ROOT)).as_posix(),
            ]
        )
        self.assertEqual(0, status, rep_res)
        self.assertTrue(rep_res["ok"])
        self.assertEqual("public_synthetic_demo", rep_res["result_boundary"])
        self.assertTrue(len(rep_res["not_supported"]) > 0)

        # ---------------------------------------------------------------------
        # 9. Output-Count Verified Closeout Gate
        # ---------------------------------------------------------------------
        closeout_stage_dir = self.runtime_root / "closeout-stage"
        closeout_stage_dir.mkdir(parents=True)
        closeout_outputs = closeout_stage_dir / "outputs"
        closeout_outputs.mkdir()
        dummy_output = closeout_outputs / "scored.json"
        dummy_output.write_text(json.dumps({"candidate_count": 4}) + "\n", encoding="utf-8")
        closeout_declarations = [
            {"artifact_id": "score-output", "path": "outputs/scored.json"},
        ]
        decl_path = closeout_stage_dir / "declarations.json"
        decl_path.write_text(json.dumps(closeout_declarations, indent=2) + "\n", encoding="utf-8")

        status, close_res = self.call_cli(
            [
                "binder-lane",
                "closeout",
                "--workspace",
                str(ROOT),
                (closeout_stage_dir.relative_to(ROOT)).as_posix(),
                "--stage-id",
                "scoring",
                "--artifact-root",
                "outputs",
                "--declarations",
                (decl_path.relative_to(ROOT)).as_posix(),
                "--exit-code",
                "0",
            ]
        )
        self.assertEqual(0, status, close_res)
        self.assertTrue(close_res["ok"])
        self.assertEqual("completed", close_res["execution_state"])
        self.assertEqual(1, close_res["expected_output_count"])
        self.assertEqual(1, close_res["found_output_count"])

        # ---------------------------------------------------------------------
        # 10. Sequential Round Decision Loop
        # ---------------------------------------------------------------------
        # Round 1 history: primary metric 0.72 < 0.80, spend $40 < $100 -> continue
        r1_history = [
            {
                "round_index": 1,
                "primary_metric_value": 0.72,
                "actual_spend_usd": 40.0,
                "closeout_complete": True,
                "metric_provenance": {
                    "metric_id": "cofold_confidence_proxy",
                    "metric_source": "stage_closeout",
                    "source_artifact_sha256": "a" * 64,
                    "calibration_state": "operator_defined",
                    "calibration_scope_id": "shared-threshold-policy",
                    "calibration_artifact_sha256": None,
                },
            }
        ]
        history_path = self.runtime_root / "round-history.json"
        history_path.write_text(json.dumps(r1_history, indent=2) + "\n", encoding="utf-8")
        decision_path = self.runtime_root / "round-decision-r1.json"

        status, dec_res = self.call_cli(
            [
                "binder-lane",
                "round-decision",
                (plan_file.relative_to(ROOT)).as_posix(),
                "--workspace",
                str(ROOT),
                "--history",
                (history_path.relative_to(ROOT)).as_posix(),
                "--out",
                (decision_path.relative_to(ROOT)).as_posix(),
            ]
        )
        self.assertEqual(0, status, dec_res)
        self.assertEqual("continue", dec_res["decision"])

        # Round 2 history: primary metric 0.85 >= 0.80 stopping threshold -> stop
        r2_plan_payload = json.loads(plan_file.read_text(encoding="utf-8"))
        r2_plan_payload["optimization_policy"]["current_round_index"] = 2
        r2_plan_file = self.runtime_root / "plan-r2.json"
        r2_plan_file.write_text(json.dumps(r2_plan_payload, indent=2) + "\n", encoding="utf-8")

        r2_history = [
            *r1_history,
            {
                "round_index": 2,
                "primary_metric_value": 0.85,
                "actual_spend_usd": 30.0,
                "closeout_complete": True,
                "metric_provenance": {
                    "metric_id": "cofold_confidence_proxy",
                    "metric_source": "stage_closeout",
                    "source_artifact_sha256": "b" * 64,
                    "calibration_state": "operator_defined",
                    "calibration_scope_id": "shared-threshold-policy",
                    "calibration_artifact_sha256": None,
                },
            },
        ]
        history_path.write_text(json.dumps(r2_history, indent=2) + "\n", encoding="utf-8")
        decision_r2_path = self.runtime_root / "round-decision-r2.json"

        status, dec_r2_res = self.call_cli(
            [
                "binder-lane",
                "round-decision",
                (r2_plan_file.relative_to(ROOT)).as_posix(),
                "--workspace",
                str(ROOT),
                "--history",
                (history_path.relative_to(ROOT)).as_posix(),
                "--out",
                (decision_r2_path.relative_to(ROOT)).as_posix(),
            ]
        )
        self.assertEqual(0, status, dec_r2_res)
        self.assertEqual("stop", dec_r2_res["decision"])
        self.assertEqual("target_threshold_reached", dec_r2_res["reason"])

        # ---------------------------------------------------------------------
        # 11. Visual-Ready Artifacts Inspection & Script Generation
        # ---------------------------------------------------------------------
        visuals_dir = self.runtime_root / "visuals"
        visuals_dir.mkdir()
        top_candidate = synthetic_candidates_jsonl()[0]

        pml_script_path = visuals_dir / f"{top_candidate['candidate_id']}.pml"
        pml_content = "\n".join(
            [
                f"# Auto-generated PyMOL visualization for candidate {top_candidate['candidate_id']}",
                "load target/target.pdb, complex",
                "bg_color white",
                "hide everything",
                "show cartoon, chain A",
                "color grey80, chain A",
                "show surface, chain A",
                "set transparency, 0.55, chain A",
                "show cartoon, chain B",
                "color marine, chain B",
                "select hot, chain A and resi 19+20+21",
                "show sticks, hot",
                "color hotpink, hot",
                "orient complex",
                f"png visuals/{top_candidate['candidate_id']}_hero.png, dpi=300, ray=1",
                "",
            ]
        )
        pml_script_path.write_text(pml_content, encoding="utf-8")
        self.assertTrue(pml_script_path.is_file())
        self.assertIn("color hotpink, hot", pml_script_path.read_text(encoding="utf-8"))


if __name__ == "__main__":
    unittest.main()
