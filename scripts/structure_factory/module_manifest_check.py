#!/usr/bin/env python3
"""Validate Structure Factory provider-neutral module manifests."""

from __future__ import annotations

import argparse
import json
from pathlib import Path
from typing import Any


REQUIRED_CAMPAIGN_KEYS = {
    "schema_version",
    "campaign_id",
    "campaign_family",
    "run_profile",
    "data_modules",
    "image_modules",
    "lane_modules",
    "smoke_suites",
    "artifact_contract",
    "policies",
}

REQUIRED_MODULE_KEYS = {
    "schema_version",
    "module_type",
}

VALID_MODULE_TYPES = {
    "campaign_manifest",
    "data_module",
    "image_module",
    "lane_module",
    "smoke_check",
    "artifact_contract",
    "provider_profile",
    "schema_contract",
}
from provider_policy import ALLOWED_PROVIDERS, ALLOWED_PROVIDER_CLASSES, BLESSED_PROVIDERS


def load(path: Path) -> dict[str, Any]:
    return json.loads(path.read_text())


def check_referenced_module(root: Path, rel: str) -> dict[str, Any]:
    path = root / rel
    if not path.exists():
        return {"ok": False, "path": rel, "errors": ["missing referenced module"]}
    try:
        data = load(path)
    except Exception as exc:
        return {"ok": False, "path": rel, "errors": [f"invalid json: {type(exc).__name__}: {exc}"]}
    missing = sorted(REQUIRED_MODULE_KEYS - set(data))
    errors = [f"missing key: {key}" for key in missing]
    module_type = data.get("module_type")
    if module_type and module_type not in VALID_MODULE_TYPES:
        errors.append(f"invalid module_type: {module_type}")
    if module_type == "data_module":
        errors.extend(validate_data_module(data))
    if module_type == "artifact_contract":
        errors.extend(validate_artifact_contract(data))
    if module_type == "provider_profile":
        errors.extend(validate_provider_profile(data))
    return {"ok": not errors, "path": rel, "errors": errors}


def validate_data_module(data: dict[str, Any]) -> list[str]:
    errors: list[str] = []
    policy = data.get("download_policy", {})
    if not isinstance(policy, dict):
        return ["download_policy must be object"]
    if data.get("git_policy") and "never_commit" not in str(data.get("git_policy")):
        errors.append("git_policy must forbid committing raw/generated data")
    if policy.get("enabled") is True:
        if policy.get("requires_explicit_execution_issue") is not True:
            errors.append("enabled download_policy requires explicit execution issue")
        max_bytes = policy.get("expected_download_bytes_max", policy.get("expected_download_bytes"))
        if not isinstance(max_bytes, int) or max_bytes <= 0:
            errors.append("enabled download_policy requires positive expected_download_bytes_max")
    if "raw_cryoem_movies" in data.get("data_classes", []):
        for subset in data.get("subset_profiles", []):
            if str(subset.get("id", "")).startswith("raw_movies_"):
                if not subset.get("deterministic_rule"):
                    errors.append(f"subset {subset.get('id')} missing deterministic_rule")
                max_files = subset.get("max_files")
                if not isinstance(max_files, int) or max_files <= 0:
                    errors.append(f"subset {subset.get('id')} missing positive max_files")
                if subset.get("allow_processed_inputs") is not False:
                    errors.append(f"subset {subset.get('id')} must set allow_processed_inputs false")
    return errors


def validate_artifact_contract(data: dict[str, Any]) -> list[str]:
    errors: list[str] = []
    if "required_for_raw_subset_demo" in data:
        required = set(data["required_for_raw_subset_demo"])
        for artifact in ["data-intake-ledger.json", "validation/versions.json", "provenance.md"]:
            if artifact not in required:
                errors.append(f"required_for_raw_subset_demo missing {artifact}")
    closeout = set(data.get("required_at_closeout", []))
    for artifact in ["validation/input-audit.json", "validation/contract-self-check.json"]:
        if artifact not in closeout:
            errors.append(f"required_at_closeout missing {artifact}")
    ladder = data.get("maturity_ladder", {})
    for level in ["L0", "L1", "L2", "L3", "L4", "L5"]:
        if level not in ladder:
            errors.append(f"maturity_ladder missing {level}")
    claim_levels = set(data.get("claim_levels", []))
    for level in ["candidate", "processed", "validated", "publishable", "insufficient_evidence", "blocked"]:
        if level not in claim_levels:
            errors.append(f"claim_levels missing {level}")
    if "export_policy" in data:
        policy = data["export_policy"]
        if policy.get("raw_cryoem_movies") != "do_not_export":
            errors.append("export_policy.raw_cryoem_movies must be do_not_export")
    return errors


def validate_provider_profile(data: dict[str, Any]) -> list[str]:
    errors: list[str] = []
    common = {
        "provider",
        "provider_class",
        "profile_id",
        "maps_campaign_profile",
        "workspace_root",
        "artifact_root",
        "secret_mode",
        "operator_gate_required",
        "execution_ready_requires",
    }
    for key in sorted(common - set(data)):
        errors.append(f"provider_profile missing {key}")
    if data.get("provider") not in ALLOWED_PROVIDERS:
        errors.append(f"provider_profile unsupported provider: {data.get('provider')}")
    if data.get("provider_class") not in ALLOWED_PROVIDER_CLASSES:
        errors.append(f"provider_profile unsupported provider_class: {data.get('provider_class')}")
    ready = data.get("execution_ready_requires", [])
    if not isinstance(ready, list) or not ready:
        errors.append("provider_profile execution_ready_requires must be non-empty list")
    else:
        for gate in ["input_audit", "contract_self_check"]:
            if gate not in ready:
                errors.append(f"provider_profile execution_ready_requires missing {gate}")
    if data.get("operator_gate_required") is not False and "explicit_operator_launch" not in ready:
        errors.append("operator-gated provider_profile must require explicit_operator_launch")
    if data.get("provider") == "runpod":
        for key in ["volume_mount", "network_volume_required", "recommended_gpu", "gpu_count", "container_disk_gb", "image_map"]:
            if key not in data:
                errors.append(f"RunPod provider_profile missing {key}")
        if data.get("blessed_path") is not True:
            errors.append("RunPod provider_profile must mark the reviewed path with blessed_path=true")
    elif data.get("blessed_path") is True and data.get("provider") not in BLESSED_PROVIDERS:
        errors.append(f"only reviewed providers {sorted(BLESSED_PROVIDERS)} may set blessed_path=true")
    if data.get("provider") == "aws":
        if "aws" not in data or not isinstance(data.get("aws"), dict):
            errors.append("AWS provider_profile missing aws block")
    if data.get("provider") == "neocloud":
        if "neocloud" not in data or not isinstance(data.get("neocloud"), dict):
            errors.append("neocloud provider_profile missing neocloud block")
    if data.get("provider") == "modal":
        if "modal" not in data or not isinstance(data.get("modal"), dict):
            errors.append("modal provider_profile missing modal block")
    if data.get("provider") == "lambda":
        if "lambda" not in data or not isinstance(data.get("lambda"), dict):
            errors.append("lambda provider_profile missing lambda block")
    if data.get("provider") == "fal":
        if "fal" not in data or not isinstance(data.get("fal"), dict):
            errors.append("fal provider_profile missing fal block")
    return errors


def validate_campaign(path: Path, check_all: bool = False) -> dict[str, Any]:
    path = path.resolve()
    root = path.parents[2]
    data = load(path)
    errors: list[str] = []
    missing = sorted(REQUIRED_CAMPAIGN_KEYS - set(data))
    errors.extend(f"missing campaign key: {key}" for key in missing)

    policies = data.get("policies", {})
    run_profile = data.get("run_profile")
    if policies.get("allow_private_data") is not False:
        errors.append("policies.allow_private_data must be false")
    expected_download_bytes = policies.get("expected_download_bytes")
    if not isinstance(expected_download_bytes, int) or expected_download_bytes < 0:
        errors.append("policies.expected_download_bytes must be a non-negative integer")
    if run_profile == "no_download_smoke":
        if policies.get("allow_large_downloads") is not False:
            errors.append("policies.allow_large_downloads must be false for no-download profile")
        if policies.get("allow_raw_cryoem_downloads") is not False:
            errors.append("policies.allow_raw_cryoem_downloads must be false for no-download profile")
        if expected_download_bytes != 0:
            errors.append("policies.expected_download_bytes must be 0 for no-download profile")
    else:
        if expected_download_bytes == 0:
            errors.append("non no-download campaigns must declare expected_download_bytes > 0")
        if policies.get("allow_raw_cryoem_downloads") is True:
            subset = data.get("raw_subset_plan", {})
            if not subset:
                errors.append("raw campaign requires raw_subset_plan")
            elif subset.get("allow_processed_inputs") is not False:
                errors.append("raw_subset_plan.allow_processed_inputs must be false")

    referenced = []
    for key in ["data_modules", "image_modules", "lane_modules", "smoke_suites"]:
        for rel in data.get(key, []):
            referenced.append(check_referenced_module(root, rel))
    if data.get("artifact_contract"):
        referenced.append(check_referenced_module(root, data["artifact_contract"]))

    if check_all:
        referenced_paths = {result["path"] for result in referenced}
        referenced_paths.add(str(path.relative_to(root)))
        for module_path in sorted((root / "modules").rglob("*.json")):
            rel = str(module_path.relative_to(root))
            if rel in referenced_paths:
                continue
            referenced.append(check_referenced_module(root, rel))

    for result in referenced:
        if not result["ok"]:
            errors.extend(f"{result['path']}: {error}" for error in result["errors"])

    return {
        "ok": not errors,
        "campaign_manifest": str(path.resolve()),
        "errors": errors,
        "referenced_modules_checked": len(referenced),
    }


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("campaign_manifest", type=Path)
    parser.add_argument("--check-all", action="store_true", help="Validate all modules/**/*.json, not only campaign references")
    parser.add_argument("--json", action="store_true")
    args = parser.parse_args()

    summary = validate_campaign(args.campaign_manifest, check_all=args.check_all)
    if args.json:
        print(json.dumps(summary, indent=2, sort_keys=True))
    else:
        print(f"ok: {summary['ok']}")
        for error in summary["errors"]:
            print(f"error: {error}")
    return 0 if summary["ok"] else 1


if __name__ == "__main__":
    raise SystemExit(main())
