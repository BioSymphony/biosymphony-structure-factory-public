#!/usr/bin/env python3
"""Validate Structure Factory provider profiles."""

from __future__ import annotations

import argparse
import json
from pathlib import Path
from typing import Any


from provider_policy import ALLOWED_PROVIDERS, BLESSED_PROVIDERS
from provider_policy import ALLOWED_PROVIDER_CLASSES as ALLOWED_CLASSES
REQUIRED_COMMON = {
    "schema_version",
    "module_type",
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
REQUIRED_READY_GATES = {"input_audit", "contract_self_check"}
RUNPOD_REQUIRED = {
    "volume_mount",
    "network_volume_required",
    "recommended_gpu",
    "gpu_count",
    "container_disk_gb",
    "image_map",
}


def load(path: Path) -> dict[str, Any]:
    return json.loads(path.read_text())


def validate_profile(data: dict[str, Any], path: Path) -> dict[str, Any]:
    errors: list[str] = []
    warnings: list[str] = []

    missing = sorted(REQUIRED_COMMON - set(data))
    errors.extend(f"missing key: {key}" for key in missing)
    if data.get("module_type") != "provider_profile":
        errors.append("module_type must be provider_profile")
    if data.get("provider") not in ALLOWED_PROVIDERS:
        errors.append(f"unsupported provider: {data.get('provider')}")
    if data.get("provider_class") not in ALLOWED_CLASSES:
        errors.append(f"unsupported provider_class: {data.get('provider_class')}")
    ready = data.get("execution_ready_requires", [])
    if not isinstance(ready, list) or not ready:
        errors.append("execution_ready_requires must be non-empty list")
    else:
        ready_set = set(ready)
        for gate in sorted(REQUIRED_READY_GATES - ready_set):
            errors.append(f"execution_ready_requires missing {gate}")

    if data.get("operator_gate_required") is not False and "explicit_operator_launch" not in ready:
        errors.append("operator-gated profiles must require explicit_operator_launch")

    if data.get("provider") == "runpod":
        missing_runpod = sorted(RUNPOD_REQUIRED - set(data))
        errors.extend(f"missing RunPod key: {key}" for key in missing_runpod)
        if data.get("blessed_path") is not True:
            warnings.append("RunPod profiles should mark the reviewed path with blessed_path=true")
        if data.get("workspace_root") != "/workspace/structure-factory":
            errors.append("RunPod workspace_root must be /workspace/structure-factory")
        if not str(data.get("artifact_root", "")).startswith("/workspace/structure-factory/runs/"):
            errors.append("RunPod artifact_root must be under /workspace/structure-factory/runs/")
    else:
        if data.get("blessed_path") is True and data.get("provider") not in BLESSED_PROVIDERS:
            errors.append(f"only reviewed providers {sorted(BLESSED_PROVIDERS)} may set blessed_path=true")
        if data.get("provider") == "aws" and not isinstance(data.get("aws"), dict):
            errors.append("AWS profiles must include an aws block")
        if data.get("provider") == "aws" and data.get("blessed_path") is True:
            service = data.get("aws", {}).get("service") if isinstance(data.get("aws"), dict) else None
            if service != "batch":
                errors.append("only AWS Batch profiles may set blessed_path=true")
        if data.get("provider") == "neocloud" and not isinstance(data.get("neocloud"), dict):
            errors.append("neocloud profiles must include a neocloud block")
        if data.get("provider") == "modal" and not isinstance(data.get("modal"), dict):
            errors.append("modal profiles must include a modal block")
        if data.get("provider") == "lambda" and not isinstance(data.get("lambda"), dict):
            errors.append("lambda profiles must include a lambda block")
        if data.get("provider") == "fal" and not isinstance(data.get("fal"), dict):
            errors.append("fal profiles must include a fal block")

    return {
        "ok": not errors,
        "path": str(path),
        "profile_id": data.get("profile_id"),
        "provider": data.get("provider"),
        "provider_class": data.get("provider_class"),
        "errors": errors,
        "warnings": warnings,
    }


def profile_paths(path: Path) -> list[Path]:
    if path.is_dir():
        return sorted(path.rglob("*.json"))
    return [path]


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("path", type=Path, help="Provider profile JSON file or directory")
    parser.add_argument("--json", action="store_true")
    args = parser.parse_args()

    results = [validate_profile(load(path), path) for path in profile_paths(args.path)]
    ok = bool(results) and all(result["ok"] for result in results)
    summary = {
        "ok": ok,
        "checked": len(results),
        "failures": [result for result in results if not result["ok"]],
        "warnings": [result for result in results if result["warnings"]],
        "profiles": results,
    }

    if args.json:
        print(json.dumps(summary, indent=2, sort_keys=True))
    else:
        print(f"ok: {ok}")
        print(f"checked: {len(results)}")
        for result in summary["failures"]:
            print(f"failed: {result['path']}")
            for error in result["errors"]:
                print(f"  {error}")
        for result in summary["warnings"]:
            print(f"warning: {result['path']}")
            for warning in result["warnings"]:
                print(f"  {warning}")
    return 0 if ok else 1


if __name__ == "__main__":
    raise SystemExit(main())
