#!/usr/bin/env python3
"""Estimate Structure Factory lane fanout before expensive execution.

The estimator is intentionally metadata-only. It reads launch/data manifests and
answers "how big will this route get?" before raw downloads, picking,
refinement, context annotation, or figure lanes are allowed to run.
"""

from __future__ import annotations

import argparse
import json
from pathlib import Path
from typing import Any


DEFAULT_RAW_FANOUT_POLICY = {
    "max_raw_movie_files": 100,
    "max_download_bytes": 11_000_000_000,
    "max_motion_frames": 5_000,
    "max_context_micrographs": 100,
}

RAW_SHARD_CLOSEOUT_ARTIFACTS = [
    "stage-progress.jsonl",
    "validation/input-audit.json",
    "validation/fanout-estimate.json",
    "validation/contract-self-check.json",
    "validation/artifact-pull-report.json",
    "cost_report.json",
    "cleanup_proof.json",
]


def find_repo_root(start: Path) -> Path:
    for parent in [start.resolve().parent, *start.resolve().parents]:
        if (parent / "modules").is_dir() and (parent / "runpod").is_dir():
            return parent
    cwd = Path.cwd()
    if (cwd / "modules").is_dir() and (cwd / "runpod").is_dir():
        return cwd
    return start.resolve().parent


def load_json(path: Path) -> dict[str, Any]:
    return json.loads(path.read_text())


def resolve_path(repo_root: Path, manifest_path: Path, rel: str) -> Path:
    candidate = Path(rel)
    if candidate.is_absolute():
        return candidate
    for base in [manifest_path.resolve().parent, repo_root]:
        path = base / candidate
        if path.exists():
            return path
    return repo_root / candidate


def subset_profile(data_module: dict[str, Any], profile_id: str) -> dict[str, Any]:
    for profile in data_module.get("subset_profiles", []):
        if profile.get("id") == profile_id:
            return profile
    return {}


def policy_value(policy: dict[str, Any], key: str) -> int:
    value = policy.get(key, DEFAULT_RAW_FANOUT_POLICY[key])
    return int(value) if isinstance(value, (int, float, str)) and str(value).isdigit() else DEFAULT_RAW_FANOUT_POLICY[key]


def estimate_raw_subset(manifest: dict[str, Any], manifest_path: Path) -> dict[str, Any]:
    repo_root = find_repo_root(manifest_path)
    plan = manifest.get("download_plan", {})
    policy = {**DEFAULT_RAW_FANOUT_POLICY, **manifest.get("fanout_policy", {})}
    blockers: list[str] = []
    warnings: list[str] = []

    data_module_path = resolve_path(repo_root, manifest_path, str(plan.get("data_module", "")))
    data_module = load_json(data_module_path) if data_module_path.exists() else {}
    if not data_module:
        blockers.append(f"data_module not found: {plan.get('data_module')}")

    profile_id = str(plan.get("subset_profile", ""))
    profile = subset_profile(data_module, profile_id)
    if not profile:
        blockers.append(f"subset_profile not found in data module: {profile_id}")

    image_set = data_module.get("image_set", {}) if isinstance(data_module, dict) else {}
    frames_per_movie = int(image_set.get("frames_per_image") or 1)
    max_files = int(plan.get("max_files") or profile.get("max_files") or 0)
    expected_download_bytes = int(
        plan.get("expected_download_bytes")
        or profile.get("expected_download_bytes")
        or manifest.get("data_policy", {}).get("expected_download_bytes")
        or 0
    )
    motion_frames = max_files * frames_per_movie
    context_micrographs = max_files

    budgets = {
        "max_raw_movie_files": policy_value(policy, "max_raw_movie_files"),
        "max_download_bytes": policy_value(policy, "max_download_bytes"),
        "max_motion_frames": policy_value(policy, "max_motion_frames"),
        "max_context_micrographs": policy_value(policy, "max_context_micrographs"),
    }
    measured = {
        "raw_movie_files": max_files,
        "download_bytes": expected_download_bytes,
        "motion_frames": motion_frames,
        "context_micrographs": context_micrographs,
    }

    comparisons = [
        ("raw_movie_files", "max_raw_movie_files"),
        ("download_bytes", "max_download_bytes"),
        ("motion_frames", "max_motion_frames"),
        ("context_micrographs", "max_context_micrographs"),
    ]
    for estimate_key, budget_key in comparisons:
        estimate = measured[estimate_key]
        budget = budgets[budget_key]
        if estimate > budget:
            blockers.append(f"{estimate_key} exceeds {budget_key}: {estimate} > {budget}")
        elif estimate > 0.75 * budget:
            warnings.append(f"{estimate_key} is above 75% of {budget_key}: {estimate} / {budget}")

    if plan.get("allow_processed_inputs") is not False:
        blockers.append("download_plan.allow_processed_inputs must be false for honest raw-subset fanout")
    if not plan.get("deterministic_rule"):
        blockers.append("download_plan.deterministic_rule is required for bounded fanout")

    lane_estimates = [
        {
            "lane": "primary_raw_intake",
            "success_level": "L2_inputs_materialized",
            "work_units": max_files,
            "unit": "raw_movie_files",
            "classification": "primary_evidence",
        },
        {
            "lane": "motion_correction",
            "success_level": "L3_primary_evidence",
            "work_units": motion_frames,
            "unit": "movie_frames",
            "classification": "primary_evidence",
        },
        {
            "lane": "ctf_qc",
            "success_level": "L3_primary_evidence",
            "work_units": max_files,
            "unit": "micrographs",
            "classification": "primary_evidence",
        },
        {
            "lane": "picking_2d_context",
            "success_level": "L4_context_or_deferred",
            "work_units": context_micrographs,
            "unit": "micrographs",
            "classification": "context_lane",
            "note": "Context lanes may close partial if primary evidence succeeds but this lane exceeds time budget.",
        },
    ]

    max_ratio = 0.0
    for estimate_key, budget_key in comparisons:
        budget = budgets[budget_key]
        if budget:
            max_ratio = max(max_ratio, measured[estimate_key] / budget)
    risk_tier = "low"
    if blockers:
        risk_tier = "blocked"
    elif max_ratio >= 0.75:
        risk_tier = "medium"

    return {
        "ok": not blockers,
        "check_type": "structure_factory_fanout_estimate",
        "execution_profile": manifest.get("execution_profile") or manifest.get("environment", {}).get("STRUCTURE_FACTORY_EXECUTION_PROFILE"),
        "manifest_id": manifest.get("manifest_id"),
        "run_id": manifest.get("run_id"),
        "data_module": str(data_module_path),
        "subset_profile": profile_id,
        "risk_tier": risk_tier,
        "budgets": budgets,
        "estimates": measured,
        "lane_estimates": lane_estimates,
        "success_policy": {
            "primary_evidence_can_close_without_context": True,
            "context_lane_timeout_closes_as": "partial",
            "raw_tool_outputs_must_be_normalized": True,
        },
        "shard_ledger_policy": {
            "ledger_type": "structure_factory_cloud_shard_ledger",
            "expected_runtime_path": f".runtime/{manifest.get('run_id', 'structure-factory-raw-subset')}/validation/cloud-shard-ledger.json",
            "canary_required_before_paid_fanout": True,
            "provider_success_is_not_scientific_success": True,
            "per_shard_closeout_requires": RAW_SHARD_CLOSEOUT_ARTIFACTS,
            "validator": "scripts/structure_factory/provider_closeout_check.py --shard-ledger <ledger> --execution-mode prep --json",
        },
        "blockers": blockers,
        "warnings": warnings,
    }


def estimate(manifest_path: Path) -> dict[str, Any]:
    manifest = load_json(manifest_path)
    execution_profile = manifest.get("execution_profile") or manifest.get("environment", {}).get("STRUCTURE_FACTORY_EXECUTION_PROFILE")
    if execution_profile not in {"raw-subset-open", "raw-subset-gated"}:
        return {
            "ok": True,
            "check_type": "structure_factory_fanout_estimate",
            "execution_profile": execution_profile,
            "manifest_id": manifest.get("manifest_id"),
            "run_id": manifest.get("run_id"),
            "risk_tier": "low",
            "budgets": {},
            "estimates": {},
            "lane_estimates": [],
            "success_policy": {
                "primary_evidence_can_close_without_context": True,
                "context_lane_timeout_closes_as": "partial",
                "raw_tool_outputs_must_be_normalized": True,
            },
            "shard_ledger_policy": {
                "ledger_type": "structure_factory_cloud_shard_ledger",
                "expected_runtime_path": f".runtime/{manifest.get('run_id', 'structure-factory-run')}/validation/cloud-shard-ledger.json",
                "canary_required_before_paid_fanout": True,
                "provider_success_is_not_scientific_success": True,
                "per_shard_closeout_requires": RAW_SHARD_CLOSEOUT_ARTIFACTS,
                "validator": "scripts/structure_factory/provider_closeout_check.py --shard-ledger <ledger> --execution-mode prep --json",
            },
            "blockers": [],
            "warnings": [],
        }
    return estimate_raw_subset(manifest, manifest_path)


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
        print(f"risk_tier: {summary['risk_tier']}")
        for warning in summary["warnings"]:
            print(f"warning: {warning}")
        for blocker in summary["blockers"]:
            print(f"blocker: {blocker}")
    return 0 if summary["ok"] else 1


if __name__ == "__main__":
    raise SystemExit(main())
