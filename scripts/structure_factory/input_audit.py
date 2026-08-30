#!/usr/bin/env python3
"""Audit declared Structure Factory inputs before asking for operator input.

The audit is intentionally read-only. It summarizes what the repo already knows
from manifests and ledgers, then emits only explicit missing_operator_items.
"""

from __future__ import annotations

import argparse
import json
import os
from pathlib import Path
from typing import Any


TRUTHY = {"1", "true", "yes", "y", "on"}


def find_repo_root(start: Path) -> Path:
    for parent in [start.resolve().parent, *start.resolve().parents]:
        if (parent / "modules").is_dir() and (parent / "runpod").is_dir():
            return parent
        if (parent / "modules").is_dir() and (parent / "launch-manifest.json").exists():
            return parent
    return start.resolve().parents[2]


ROOT = find_repo_root(Path(__file__))


def load_json(path: Path) -> dict[str, Any]:
    return json.loads(path.read_text())


def truthy_env(name: str) -> bool:
    return os.environ.get(name, "").strip().lower() in TRUTHY


def add_known(known: list[dict[str, Any]], kind: str, identifier: str, **extra: Any) -> None:
    item: dict[str, Any] = {"kind": kind, "id": identifier}
    item.update({key: value for key, value in extra.items() if value is not None})
    known.append(item)


def audit_launch_manifest(path: Path) -> dict[str, Any]:
    manifest = load_json(path)
    known_inputs: list[dict[str, Any]] = []
    missing_operator_items: list[dict[str, str]] = []
    errors: list[str] = []
    warnings: list[str] = []

    execution_profile = manifest.get("execution_profile") or manifest.get("environment", {}).get("STRUCTURE_FACTORY_EXECUTION_PROFILE")
    data_policy = manifest.get("data_policy", {})
    repo = manifest.get("repo", {})

    add_known(known_inputs, "launch_manifest", manifest.get("manifest_id", path.name), path=str(path.resolve()))
    add_known(known_inputs, "repo", repo.get("url", "unknown"), git_ref=repo.get("git_ref"), delivery=repo.get("delivery"))
    add_known(
        known_inputs,
        "data_policy",
        str(execution_profile),
        allow_raw_cryoem_downloads=data_policy.get("allow_raw_cryoem_downloads"),
        expected_download_bytes=data_policy.get("expected_download_bytes"),
    )

    if data_policy.get("allow_private_data") is not False:
        errors.append("data_policy.allow_private_data must be false")

    download_plan = manifest.get("download_plan")
    if isinstance(download_plan, dict) and download_plan:
        module_rel = download_plan.get("data_module")
        data_module: dict[str, Any] = {}
        if module_rel:
            module_path = ROOT / str(module_rel)
            if module_path.exists():
                data_module = load_json(module_path)
            else:
                errors.append(f"download_plan.data_module does not exist: {module_rel}")
        subset_id = download_plan.get("subset_profile")
        subset = next((item for item in data_module.get("subset_profiles", []) if item.get("id") == subset_id), {})
        add_known(
            known_inputs,
            "raw_subset",
            str(subset_id),
            data_module=module_rel,
            accession=data_module.get("id"),
            source=data_module.get("source"),
            deterministic_rule=download_plan.get("deterministic_rule") or subset.get("deterministic_rule"),
            max_files=download_plan.get("max_files") or subset.get("max_files"),
            expected_download_bytes=download_plan.get("expected_download_bytes") or subset.get("expected_download_bytes"),
            destination_root=download_plan.get("destination_root"),
            allow_processed_inputs=download_plan.get("allow_processed_inputs"),
        )
        if download_plan.get("allow_processed_inputs") is not False:
            errors.append("download_plan.allow_processed_inputs must be false")
        if not truthy_env("STRUCTURE_FACTORY_OPERATOR_AUTHORIZED"):
            missing_operator_items.append(
                {
                    "id": "operator_authorization_for_raw_download",
                    "why": "raw-download profiles require an explicit cost/data authorization gate before execution",
                    "env_or_artifact": "STRUCTURE_FACTORY_OPERATOR_AUTHORIZED=1",
                }
            )

    artifact_plan = manifest.get("artifact_plan")
    if isinstance(artifact_plan, dict) and artifact_plan:
        add_known(
            known_inputs,
            "map_model_artifact_plan",
            str(manifest.get("campaign_id")),
            allow_raw_cryoem_downloads=artifact_plan.get("allow_raw_cryoem_downloads"),
            expected_outputs=artifact_plan.get("expected_outputs"),
        )

    if execution_profile == "no-download-smoke" and data_policy.get("expected_download_bytes") != 0:
        errors.append("no-download-smoke must declare expected_download_bytes 0")
    if manifest.get("repo", {}).get("git_ref") in {"main", "master"}:
        warnings.append("repo.git_ref is branch-like; pin to a commit before real RunPod execution")

    return {
        "ok": not errors,
        "audit_type": "structure_factory_input_audit",
        "manifest_path": str(path.resolve()),
        "manifest_id": manifest.get("manifest_id"),
        "execution_profile": execution_profile,
        "known_inputs": known_inputs,
        "missing_operator_items": missing_operator_items,
        "errors": errors,
        "warnings": warnings,
    }


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--manifest", type=Path, required=True, help="RunPod launch manifest to audit")
    parser.add_argument("--out", type=Path, help="Optional output JSON path")
    parser.add_argument("--json", action="store_true")
    args = parser.parse_args()

    summary = audit_launch_manifest(args.manifest)
    payload = json.dumps(summary, indent=2, sort_keys=True) + "\n"
    if args.out:
        args.out.parent.mkdir(parents=True, exist_ok=True)
        args.out.write_text(payload)
    if args.json or not args.out:
        print(payload, end="")
    return 0 if summary["ok"] else 1


if __name__ == "__main__":
    raise SystemExit(main())
