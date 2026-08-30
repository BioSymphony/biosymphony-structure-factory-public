#!/usr/bin/env python3
"""Estimate target x ligand x method fanout for screening manifests."""

from __future__ import annotations

import argparse
import json
from pathlib import Path
from typing import Any

from screening_manifest_check import load_json, rel_path, repo_root_for, validate_manifest


METHOD_COST_WEIGHTS = {
    "stdlib_descriptor_proxy": 0.01,
    "simple_affinity_baselines": 0.01,
    "rdkit": 0.02,
    "autodock_vina": 0.15,
    "boltz": 1.0,
    "gnina": 0.35,
    "diffdock": 0.6,
    "alphafold3": 2.0,
    "chai": 1.2,
    "phenix": 0.5,
    "chimerax": 0.2,
}

CLOUD_SHARD_CLOSEOUT_ARTIFACTS = [
    "stage-progress.jsonl",
    "validation/input-audit.json",
    "validation/contract-self-check.json",
    "validation/artifact-pull-report.json",
    "cost_report.json",
    "cleanup_proof.json",
]


def cloud_shard_ledger_policy(manifest: dict[str, Any], run_id: str) -> dict[str, Any]:
    providers = manifest.get("provider_plan", {}).get("priority", [])
    if not isinstance(providers, list) or not providers:
        providers = ["runpod", "aws_batch", "neocloud_gpu_pod"]
    providers = [str(provider) for provider in providers]
    return {
        "ledger_type": "structure_factory_cloud_shard_ledger",
        "example_path": "examples/screening-superpowers/cloud-shard-ledger.example.json",
        "expected_runtime_path": f".runtime/{run_id}/validation/cloud-shard-ledger.json",
        "provider_order": providers,
        "canary_provider": providers[0],
        "canary_required_before_paid_fanout": True,
        "provider_success_is_not_scientific_success": True,
        "per_shard_closeout_requires": CLOUD_SHARD_CLOSEOUT_ARTIFACTS,
        "validator": "scripts/structure_factory/provider_closeout_check.py --shard-ledger <ledger> --execution-mode prep --json",
    }


def estimate(manifest_path: Path) -> dict[str, Any]:
    check = validate_manifest(manifest_path)
    root = repo_root_for(manifest_path)
    manifest = load_json(manifest_path)
    run_id = str(manifest.get("run_id", "structure-factory-screening"))
    ligand_ref = manifest.get("ligand_library", {}).get("path")
    receptor_ref = manifest.get("receptor_ensemble", {}).get("path")
    ligands = load_json(rel_path(root, ligand_ref)).get("ligands", []) if ligand_ref else []
    receptors = load_json(rel_path(root, receptor_ref)).get("members", []) if receptor_ref else []
    budget = manifest.get("budget", {})
    max_ligands = min(len(ligands), int(budget.get("max_ligands", len(ligands))))

    methods = manifest.get("methods", {})
    wide_methods = list(methods.get("always", [])) + list(methods.get("wide_pass", []))
    focused_methods = list(methods.get("focused", []))
    gated_methods = list(methods.get("gated", []))
    wide_pairs = max_ligands * max(1, len(receptors)) * max(1, len(wide_methods))
    focused_pairs = min(max_ligands, int(manifest.get("outputs", {}).get("promote_top_n", 1)) * 2) * max(1, len(focused_methods))
    gated_pairs = 0
    method_cost_units = sum(METHOD_COST_WEIGHTS.get(method, 0.1) for method in wide_methods) * max_ligands
    method_cost_units += sum(METHOD_COST_WEIGHTS.get(method, 1.0) for method in focused_methods) * max(1, focused_pairs)

    return {
        "ok": check["ok"],
        "check_type": "screening_fanout_estimate",
        "manifest": str(manifest_path.resolve()),
        "ligands_considered": max_ligands,
        "receptor_members": len(receptors),
        "wide_methods": wide_methods,
        "focused_methods": focused_methods,
        "gated_methods_declared": gated_methods,
        "wide_pairs": wide_pairs,
        "focused_pairs": focused_pairs,
        "gated_pairs_without_operator_gate": gated_pairs,
        "estimated_relative_cost_units": round(method_cost_units, 3),
        "canary_policy": {
            "run_wide_fixture_first": True,
            "paid_compute_requires_operator_gate": True,
            "fanout_after_canary": True
        },
        "cloud_shard_ledger": cloud_shard_ledger_policy(manifest, run_id),
        "errors": check["errors"],
        "warnings": check["warnings"],
    }


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--manifest", type=Path, required=True)
    parser.add_argument("--out", type=Path)
    parser.add_argument("--json", action="store_true")
    args = parser.parse_args()

    summary = estimate(args.manifest)
    if args.out:
        args.out.parent.mkdir(parents=True, exist_ok=True)
        args.out.write_text(json.dumps(summary, indent=2, sort_keys=True) + "\n")
        summary["report_path"] = str(args.out.resolve())
    if args.json:
        print(json.dumps(summary, indent=2, sort_keys=True))
    else:
        print(f"ok: {summary['ok']}")
        print(f"wide_pairs: {summary['wide_pairs']}")
        print(f"focused_pairs: {summary['focused_pairs']}")
    return 0 if summary["ok"] else 1


if __name__ == "__main__":
    raise SystemExit(main())
