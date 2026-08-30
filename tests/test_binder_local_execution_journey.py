from __future__ import annotations

import hashlib
import io
import json
import os
import stat
import sys
import tempfile
import unittest
from contextlib import redirect_stdout
from pathlib import Path

from biosymphony_structure_factory import binder_lane
from biosymphony_structure_factory.cli import main


ROOT = Path(__file__).resolve().parents[1]
LEDGER_REF = "references/binder-lane-capability-ledger.json"
REGISTRY_REF = "references/binder-execution-adapters.json"
LOCAL_PROFILE_REF = "modules/provider-profiles/local/workstation-no-download.v1.json"


def _sha256(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def _atom(serial: int, residue: str, number: int) -> str:
    return (
        f"ATOM  {serial:5d}  CA  {residue:>3s} A{number:4d}    "
        f"{float(serial):8.3f}{0.0:8.3f}{0.0:8.3f}  1.00 80.00           C"
    )


def _synthetic_pdb() -> str:
    residues = (
        "ALA",
        "CYS",
        "ASP",
        "GLU",
        "PHE",
        "GLY",
        "HIS",
        "ILE",
        "LYS",
        "LEU",
    )
    return "\n".join(
        [
            "SEQRES   1 A   10  ALA CYS ASP GLU PHE GLY HIS ILE LYS LEU",
            *[_atom(index, residue, index) for index, residue in enumerate(residues, 1)],
            "END",
            "",
        ]
    )


def _write_json(path: Path, payload: object) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, indent=2, sort_keys=True) + "\n", encoding="utf-8")


def _write_jsonl(path: Path, rows: list[dict]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(
        "".join(json.dumps(row, sort_keys=True) + "\n" for row in rows),
        encoding="utf-8",
    )


def _synthetic_fixture() -> dict:
    return {
        "schema_version": "structure-factory-candidate-ranking-v1",
        "campaign_id": "local-adapter-journey",
        "result_boundary": "public_synthetic_demo",
        "source_posture": "synthetic_demo",
        "ranking_policy": {
            "primary": "cofold_confidence_proxy",
            "secondary": ["interface_confidence_proxy", "failure_status"],
            "note": "Constructed rows define count and boundary checks.",
        },
        "candidates": [
            {
                "rank": rank,
                "id": f"candidate-{rank:03d}",
                "toolchain_id": "local-supplied",
                "source_posture": "synthetic_demo",
                "result_boundary": "public_synthetic_demo",
                "cofold_status": "not_executed",
                "scores": {
                    "cofold_confidence_proxy": None,
                    "interface_confidence_proxy": None,
                },
                "artifact_refs": [],
            }
            for rank in range(1, 4)
        ],
        "boundaries": [
            "Rows are synthetic workflow records.",
            "The fixture does not establish binding, function, or safety.",
        ],
    }


def _request(fixture_ref: str) -> dict:
    request = json.loads(
        (ROOT / "examples/pd-l1-binder-design-public/binder-round-request.json").read_text(
            encoding="utf-8"
        )
    )
    request.update(
        {
            "round_id": "local-adapter-journey",
            "study_template": "custom",
            "published_workflow": None,
            "workflow_strategy": {
                "mode": "independent",
                "reference_scope": None,
                "replay_toolchain_ids": [],
                "swap_toolchain_ids": [],
            },
            "source_posture": "synthetic_demo",
            "result_boundary": "public_synthetic_demo",
            "target": {
                "input_posture": "synthetic",
                "label": "Synthetic local adapter target",
                "public_accession": "SYNTHETIC:LOCAL-ADAPTER-JOURNEY",
                "window": "chain A residues 1-10",
                "site": {
                    "chain_id": "A",
                    "required_residues": ["1-10"],
                },
            },
            "toolchains": [
                {
                    "id": "local-supplied",
                    "label": "Supplied backbone and local filters",
                    "candidate_count": 3,
                    "generator": "supplied-backbone",
                    "sequence_designer": "proteinmpnn",
                    "predictors": ["boltz"],
                    "scorers": ["ipsae"],
                    "filters": ["status-preserving-filter", "diversity-filter"],
                }
            ],
            "synthetic_fixture": fixture_ref,
        }
    )
    request["optimization_policy"] = {
        "round_count": 1,
        "current_round_index": 1,
        "primary_metric_id": "cofold_confidence_proxy",
        "direction": "maximize",
        "candidate_policy": {
            "mode": "fixed_per_toolchain",
            "candidate_count_per_toolchain": 3,
        },
        "stopping_rule": {"type": "fixed_round_count"},
        "round_budget_usd": [0],
    }
    request["constraints"] = {
        "objective": "Exercise dependency-free local execution with synthetic rows.",
        "target_selection_method": "Use the verified synthetic coordinate chain.",
        "binder_length": {"minimum": 10, "maximum": 10},
        "required_controls": ["synthetic-reference"],
        "inclusion_rules": ["Preserve every declared candidate row."],
        "exclusion_rules": ["Mark rows outside the score bounds as filtered."],
        "interpretation_limit": "Adapter outputs are workflow records without biological claims.",
        "preserve_failure_rows": True,
        "top_per_arm": 1,
    }
    request["license_policy"] = {
        "allowed_gates": ["none"],
        "blocked_tools": [],
        "require_operator_review_for_gated": True,
        "review_dimensions": {
            "code": "not_applicable",
            "weights": "not_applicable",
            "dependencies": "not_applicable",
            "api_terms": "not_applicable",
            "redistribution": "not_applicable",
        },
        "use_context": "research_evaluation",
    }
    request["execution_policy"] = {
        "topology": "local",
        "authorization": "plan_then_explicit_runtime_authorization",
        "max_spend_usd": 0,
        "max_wall_clock_minutes": 5,
        "routes": [
            {
                "id": "dependency-free-local",
                "toolchain_ids": ["local-supplied"],
                "stages": [
                    "generation",
                    "sequence_design",
                    "cofold",
                    "scoring",
                    "filter",
                    "report",
                ],
                "backend": "local",
                "execution_method": "self_hosted",
                "profile_ref": LOCAL_PROFILE_REF,
                "operator_adapter_required": False,
            }
        ],
    }
    return request


class BinderLocalExecutionJourneyTests(unittest.TestCase):
    def setUp(self) -> None:
        (ROOT / ".runtime").mkdir(exist_ok=True)
        self.temporary = tempfile.TemporaryDirectory(
            dir=ROOT / ".runtime", prefix="local-execution-journey-"
        )
        self.runtime = Path(self.temporary.name)
        self.bin_dir = self.runtime / "bin"
        self.bin_dir.mkdir()
        self._install_entry_point(
            "bsf-supplied-backbone",
            "biosymphony_structure_factory.binder_supplied_backbone_adapter",
            "main",
        )
        self._install_entry_point(
            "bsf-status-filter",
            "biosymphony_structure_factory.candidate_filters",
            "status_main",
        )
        self._install_entry_point(
            "bsf-diversity-filter",
            "biosymphony_structure_factory.candidate_filters",
            "diversity_main",
        )
        self.original_path = os.environ.get("PATH", "")
        self.original_sentinel = os.environ.get("BSF_TEST_SENTINEL")
        os.environ["PATH"] = f"{self.bin_dir}{os.pathsep}{self.original_path}"
        os.environ["BSF_TEST_SENTINEL"] = "runtime-only-marker"

    def tearDown(self) -> None:
        os.environ["PATH"] = self.original_path
        if self.original_sentinel is None:
            os.environ.pop("BSF_TEST_SENTINEL", None)
        else:
            os.environ["BSF_TEST_SENTINEL"] = self.original_sentinel
        self.temporary.cleanup()

    def _install_entry_point(self, name: str, module: str, function: str) -> None:
        path = self.bin_dir / name
        path.write_text(
            "\n".join(
                [
                    f"#!{sys.executable}",
                    "import sys",
                    f"sys.path.insert(0, {(ROOT / 'src').as_posix()!r})",
                    f"from {module} import {function}",
                    f"raise SystemExit({function}())",
                    "",
                ]
            ),
            encoding="utf-8",
        )
        path.chmod(path.stat().st_mode | stat.S_IXUSR | stat.S_IXGRP | stat.S_IXOTH)

    def _relative(self, path: Path) -> str:
        return path.relative_to(ROOT).as_posix()

    def _call(self, argv: list[str]) -> tuple[int, dict]:
        output = io.StringIO()
        with redirect_stdout(output):
            status = main(argv)
        return status, json.loads(output.getvalue())

    def test_verified_target_runs_through_hash_bound_local_adapters_and_closeout(self) -> None:
        target_path = self.runtime / "target" / "synthetic-target.pdb"
        target_path.parent.mkdir()
        target_path.write_text(_synthetic_pdb(), encoding="utf-8")
        sequence_path = target_path.with_name("expected-sequence.txt")
        sequence_path.write_text("ACDEFGHIKL\n", encoding="utf-8")
        target_report_path = target_path.with_name("verification.json")

        fixture_path = self.runtime / "candidate-ranking.synthetic.json"
        request_path = self.runtime / "binder-round-request.json"
        plan_path = self.runtime / "planned.json"
        _write_json(fixture_path, _synthetic_fixture())
        _write_json(request_path, _request(self._relative(fixture_path)))
        status, planned = self._call(
            [
                "binder-lane",
                "plan-request",
                self._relative(request_path),
                "--workspace",
                str(ROOT),
                "--ledger",
                LEDGER_REF,
                "--out",
                self._relative(plan_path),
            ]
        )
        self.assertEqual(0, status, planned)
        self.assertEqual("public_synthetic_demo", planned["result_boundary"])
        self.assertEqual(0, planned["execution"]["provider_calls"])

        contract_root = self.runtime / "contract"
        status, materialized = self._call(
            [
                "binder-lane",
                "plan",
                self._relative(plan_path),
                "--workspace",
                str(ROOT),
                "--out",
                self._relative(contract_root),
            ]
        )
        self.assertEqual(0, status, materialized)
        materialized_plan = contract_root / "plan.json"
        plan_sha256 = _sha256(materialized_plan)

        status, target = self._call(
            [
                "binder-lane",
                "target-check",
                self._relative(target_path),
                "--workspace",
                str(ROOT),
                "--plan",
                self._relative(materialized_plan),
                "--expected-sequence-file",
                self._relative(sequence_path),
                "--sequence-basis",
                "entity",
                "--out",
                self._relative(target_report_path),
            ]
        )
        self.assertEqual(0, status, target)
        self.assertEqual(plan_sha256, target["plan_sha256"])
        self.assertTrue(target["sequence_verified"])
        self.assertEqual(0, target["provider_calls"])

        for name in ("round-contract.json", "execution-handoff.json"):
            payload = json.loads((contract_root / name).read_text(encoding="utf-8"))
            self.assertEqual(plan_sha256, payload["plan_sha256"])
            self.assertEqual(0, payload["provider_calls"])
        status, preflight = self._call(
            [
                "binder-lane",
                "preflight",
                "--workspace",
                str(ROOT),
                self._relative(contract_root),
            ]
        )
        self.assertEqual(0, status, preflight)
        self.assertTrue(preflight["ok"], preflight)
        self.assertEqual(0, preflight["provider_calls"])

        generation_selector = "local-supplied.generation.supplied-backbone"
        status_selector = "local-supplied.filter.status-preserving-filter"
        diversity_selector = "local-supplied.filter.diversity-filter"
        settings = {
            generation_selector: {
                "bindings": {
                    "run_root": ".",
                    "input_path": "inputs/backbones.jsonl",
                    "output_path": "outputs/backbones.jsonl",
                    "pose_dir": "outputs/poses",
                    "source_chain": "A",
                    "binder_chain": "B",
                    "minimum_length": 10,
                    "maximum_length": 10,
                    "expected_count": 3,
                },
                "estimated_cost_usd": 0,
                "timeout_seconds": 30,
            },
            status_selector: {
                "bindings": {
                    "run_root": ".",
                    "input_path": "inputs/backbones.jsonl",
                    "output_path": "outputs/status.jsonl",
                    "metric": "metrics.score",
                    "minimum": 0.5,
                    "maximum": 1.0,
                },
                "input_handoffs": [
                    {
                        "source_selector": generation_selector,
                        "source_output_id": "backbone-manifest",
                        "destination_binding": "input_path",
                    }
                ],
                "estimated_cost_usd": 0,
                "timeout_seconds": 30,
            },
            diversity_selector: {
                "bindings": {
                    "run_root": ".",
                    "input_path": "inputs/status.jsonl",
                    "output_path": "outputs/diverse.jsonl",
                    "sequence_field": "candidate_sequence",
                    "maximum_similarity": 0.8,
                },
                "input_handoffs": [
                    {
                        "source_selector": status_selector,
                        "source_output_id": "status-filtered-candidates",
                        "destination_binding": "input_path",
                    }
                ],
                "estimated_cost_usd": 0,
                "timeout_seconds": 30,
            },
        }
        settings_path = self.runtime / "stage-settings.json"
        controller_request_path = self.runtime / "controller-request.json"
        readiness_path = self.runtime / "execution-readiness.json"
        _write_json(settings_path, settings)
        status, preparation = self._call(
            [
                "binder-lane",
                "prepare-execution",
                self._relative(materialized_plan),
                "--workspace",
                str(ROOT),
                "--target-report",
                self._relative(target_report_path),
                "--registry",
                REGISTRY_REF,
                "--stage-settings",
                self._relative(settings_path),
                "--stages",
                "generation,filter",
                "--out",
                self._relative(controller_request_path),
                "--readiness-out",
                self._relative(readiness_path),
            ]
        )
        self.assertEqual(0, status, preparation)
        self.assertEqual("ready", preparation["status"])
        self.assertEqual(3, preparation["controller_stage_count"])
        self.assertEqual(0, preparation["provider_calls"])
        controller_request = json.loads(controller_request_path.read_text(encoding="utf-8"))
        self.assertEqual(plan_sha256, controller_request["plan_sha256"])
        self.assertEqual(_sha256(target_report_path), controller_request["target_verification_sha256"])
        stages_by_tool = {stage["tool_id"]: stage for stage in controller_request["stages"]}
        generation_stage = stages_by_tool["supplied-backbone"]
        status_stage = stages_by_tool["status-preserving-filter"]
        diversity_stage = stages_by_tool["diversity-filter"]
        self.assertEqual([], generation_stage["input_handoffs"])
        self.assertEqual(
            generation_stage["stage_id"],
            status_stage["input_handoffs"][0]["source_stage_id"],
        )
        self.assertEqual(
            status_stage["stage_id"],
            diversity_stage["input_handoffs"][0]["source_stage_id"],
        )

        dry_root = self.runtime / "controller-dry-run"
        status, dry_run = self._call(
            [
                "binder-lane",
                "execute",
                self._relative(controller_request_path),
                "--workspace",
                str(ROOT),
                "--registry",
                REGISTRY_REF,
                "--plan",
                self._relative(materialized_plan),
                "--run-root",
                self._relative(dry_root),
                "--dry-run",
            ]
        )
        self.assertEqual(0, status, dry_run)
        self.assertEqual("planned", dry_run["status"])
        self.assertFalse(dry_run["authorized"])
        self.assertEqual(0, dry_run["provider_calls"])
        self.assertEqual(
            ["planned", "planned"],
            [
                handoff["state"]
                for stage in dry_run["stages"]
                for handoff in stage["input_handoffs"]
            ],
        )

        execution_root = self.runtime / "controller-execution"
        generator_root = execution_root / "stages" / generation_stage["stage_id"]
        generator_input = generator_root / "inputs" / "synthetic-target.pdb"
        generator_input.parent.mkdir(parents=True)
        generator_input.write_bytes(target_path.read_bytes())
        candidate_rows = [
            {
                "candidate_id": "candidate-001",
                "status": "eligible",
                "candidate_sequence": "ACDEFGHIKL",
                "metrics": {"score": 0.8},
                "result_boundary": "public_synthetic_demo",
                "source_posture": "synthetic_demo",
                "structure_path": "inputs/synthetic-target.pdb",
                "structure_sha256": target["structure_sha256"],
                "target_id": "synthetic-local-target",
            },
            {
                "candidate_id": "candidate-002",
                "status": "eligible",
                "candidate_sequence": "WYVTSRQPNM",
                "metrics": {"score": 0.4},
                "result_boundary": "public_synthetic_demo",
                "source_posture": "synthetic_demo",
                "structure_path": "inputs/synthetic-target.pdb",
                "structure_sha256": target["structure_sha256"],
                "target_id": "synthetic-local-target",
            },
            {
                "candidate_id": "candidate-003",
                "status": "eligible",
                "candidate_sequence": "ACDEFGHIKL",
                "metrics": {"score": 0.7},
                "result_boundary": "public_synthetic_demo",
                "source_posture": "synthetic_demo",
                "structure_path": "inputs/synthetic-target.pdb",
                "structure_sha256": target["structure_sha256"],
                "target_id": "synthetic-local-target",
            },
        ]
        _write_jsonl(generator_root / "inputs" / "backbones.jsonl", candidate_rows)
        status_input = (
            execution_root / "stages" / status_stage["stage_id"] / status_stage["bindings"]["input_path"]
        )
        diversity_input = (
            execution_root
            / "stages"
            / diversity_stage["stage_id"]
            / diversity_stage["bindings"]["input_path"]
        )
        self.assertFalse(status_input.exists())
        self.assertFalse(diversity_input.exists())

        status, executed = self._call(
            [
                "binder-lane",
                "execute",
                self._relative(controller_request_path),
                "--workspace",
                str(ROOT),
                "--registry",
                REGISTRY_REF,
                "--plan",
                self._relative(materialized_plan),
                "--run-root",
                self._relative(execution_root),
                "--authorize-local-execution",
            ]
        )
        self.assertEqual(0, status, executed)
        self.assertEqual("completed", executed["status"])
        self.assertEqual(3, executed["completed_stage_count"])
        self.assertTrue(executed["authorized"])
        self.assertFalse(executed["network_authorized"])
        self.assertFalse(executed["license_gates_authorized"])
        self.assertEqual(0, executed["provider_calls"])
        self.assertEqual(plan_sha256, executed["plan_sha256"])
        self.assertEqual(_sha256(target_report_path), executed["target_verification_sha256"])
        self.assertEqual(target["structure_sha256"], executed["target_structure_sha256"])
        self.assertTrue(status_input.is_file())
        self.assertTrue(diversity_input.is_file())
        self.assertFalse(status_input.is_symlink())
        self.assertFalse(diversity_input.is_symlink())

        execution_rows = {stage["adapter_id"]: stage for stage in executed["stages"]}
        generation_receipt = json.loads(
            (execution_root / execution_rows["supplied-backbone-v1"]["receipt_path"]).read_text(
                encoding="utf-8"
            )
        )
        status_receipt = json.loads(
            (execution_root / execution_rows["status-preserving-filter-v1"]["receipt_path"]).read_text(
                encoding="utf-8"
            )
        )
        diversity_receipt = json.loads(
            (execution_root / execution_rows["diversity-filter-v1"]["receipt_path"]).read_text(
                encoding="utf-8"
            )
        )
        receipts = {
            "supplied-backbone-v1": generation_receipt,
            "status-preserving-filter-v1": status_receipt,
            "diversity-filter-v1": diversity_receipt,
        }
        for adapter_id, receipt in receipts.items():
            controller_stage = execution_rows[adapter_id]
            receipt_path = execution_root / controller_stage["receipt_path"]
            self.assertEqual("completed", receipt["status"])
            self.assertEqual([], receipt["environment_names"])
            self.assertEqual(_sha256(receipt_path), controller_stage["receipt_sha256"])
        generation_outputs = {row["id"]: row for row in generation_receipt["outputs"]}
        self.assertEqual(3, generation_outputs["backbone-manifest"]["files"][0]["records"])
        self.assertEqual(3, generation_outputs["design-poses"]["files"][0]["records"])
        status_output = status_receipt["outputs"][0]["files"][0]
        diversity_output = diversity_receipt["outputs"][0]["files"][0]
        self.assertEqual(3, status_output["records"])
        self.assertEqual(3, diversity_output["records"])

        generated_manifest = generator_root / generation_stage["bindings"]["output_path"]
        status_output_path = (
            execution_root / "stages" / status_stage["stage_id"] / status_stage["bindings"]["output_path"]
        )
        diversity_output_path = (
            execution_root
            / "stages"
            / diversity_stage["stage_id"]
            / diversity_stage["bindings"]["output_path"]
        )
        self.assertEqual(generated_manifest.read_bytes(), status_input.read_bytes())
        self.assertEqual(status_output_path.read_bytes(), diversity_input.read_bytes())
        self.assertEqual(_sha256(status_output_path), status_output["sha256"])
        self.assertEqual(_sha256(diversity_output_path), diversity_output["sha256"])
        handoffs = [
            handoff
            for stage in executed["stages"]
            for handoff in stage["input_handoffs"]
        ]
        self.assertEqual(["materialized", "materialized"], [row["state"] for row in handoffs])
        self.assertTrue(
            all(
                set(row)
                == {
                    "source_stage_id",
                    "source_output_id",
                    "destination_binding",
                    "artifact_kind",
                    "state",
                    "source_receipt_sha256",
                    "source_artifact_sha256",
                    "destination_artifact_sha256",
                    "file_count",
                    "byte_count",
                    "record_count",
                }
                for row in handoffs
            )
        )
        receipt_hashes = {
            stage["stage_id"]: stage["receipt_sha256"] for stage in executed["stages"]
        }
        self.assertTrue(
            all(
                row["source_artifact_sha256"] == row["destination_artifact_sha256"]
                and row["source_receipt_sha256"]
                == receipt_hashes[row["source_stage_id"]]
                and row["record_count"] == 3
                for row in handoffs
            )
        )

        status_rows = [json.loads(line) for line in status_output_path.read_text().splitlines()]
        diversity_rows = [json.loads(line) for line in diversity_output_path.read_text().splitlines()]
        self.assertEqual(3, len(status_rows))
        self.assertEqual(3, len(diversity_rows))
        self.assertTrue(
            all(
                row["result_boundary"] == "public_synthetic_demo"
                and row["source_posture"] == "synthetic_demo"
                for row in diversity_rows
            )
        )
        self.assertEqual(
            ["passed", "filtered", "passed"],
            [row["filter_results"][-1]["state"] for row in status_rows],
        )
        self.assertEqual(
            ["passed", "not_evaluable", "filtered"],
            [row["filter_results"][-1]["state"] for row in diversity_rows],
        )
        generated_rows = [json.loads(line) for line in generated_manifest.read_text().splitlines()]
        for row in generated_rows:
            pose = generator_root / row["design_pose_path"]
            self.assertEqual(row["design_pose_sha256"], _sha256(pose))
            self.assertIn("NO DESIGN MODEL RAN", pose.read_text(encoding="utf-8"))

        declarations_by_stage = {
            generation_stage["stage_id"]: [
                {"artifact_id": "backbone-manifest", "path": "outputs/backbones.jsonl"},
                *[
                    {
                        "artifact_id": f"pose-{index:03d}",
                        "path": f"outputs/poses/candidate-{index:03d}.pdb",
                    }
                    for index in range(1, 4)
                ],
            ],
            status_stage["stage_id"]: [
                {"artifact_id": "status-candidates", "path": "outputs/status.jsonl"}
            ],
            diversity_stage["stage_id"]: [
                {"artifact_id": "diverse-candidates", "path": "outputs/diverse.jsonl"}
            ],
        }
        closeouts = []
        for stage in controller_request["stages"]:
            stage_root = execution_root / "stages" / stage["stage_id"]
            declarations_path = stage_root / "output-declarations.json"
            declarations = declarations_by_stage[stage["stage_id"]]
            _write_json(declarations_path, declarations)
            status, closeout = self._call(
                [
                    "binder-lane",
                    "closeout",
                    "--workspace",
                    str(ROOT),
                    self._relative(stage_root),
                    "--stage-id",
                    stage["stage_id"],
                    "--artifact-root",
                    "outputs",
                    "--declarations",
                    self._relative(declarations_path),
                    "--exit-code",
                    "0",
                    "--result-boundary",
                    "public_synthetic_demo",
                ]
            )
            self.assertEqual(0, status, closeout)
            self.assertEqual("completed", closeout["execution_state"])
            self.assertEqual(len(declarations), closeout["expected_output_count"])
            self.assertEqual(len(declarations), closeout["found_output_count"])
            self.assertEqual("public_synthetic_demo", closeout["result_boundary"])
            self.assertEqual(0, closeout["provider_calls"])
            receipt = json.loads((ROOT / closeout["receipt"]).read_text(encoding="utf-8"))
            for artifact in receipt["artifact_hashes"]:
                self.assertEqual(
                    artifact["sha256"],
                    _sha256(stage_root / artifact["path"]),
                )
            closeouts.append(closeout)

        for path in self.runtime.rglob("*"):
            if not path.is_file() or self.bin_dir in path.parents:
                continue
            text = path.read_text(encoding="utf-8", errors="replace")
            self.assertNotIn(ROOT.as_posix(), text, path)
            self.assertNotIn("/" + "Users" + "/", text, path)
            self.assertNotIn("runtime-only-marker", text, path)
        self.assertEqual(3, len(closeouts))


if __name__ == "__main__":
    unittest.main()
