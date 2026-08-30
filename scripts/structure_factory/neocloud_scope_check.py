#!/usr/bin/env python3
"""Validate neocloud provider profile scope and launch gates."""

from __future__ import annotations

import argparse
import json
from pathlib import Path
from typing import Any


REQUIRED_NEO_KEYS = {
    "project_ref",
    "volume_ref",
    "artifact_export_ref",
    "log_stream_ref",
    "scope_check_required",
    "launch_preflight_required",
    "cleanup_proof_required",
}
REQUIRED_GATES = {
    "public_or_operator_repo_access",
    "pinned_git_ref",
    "public_or_operator_image_or_bootstrap",
    "scratch_or_volume_mount",
    "input_audit",
    "contract_self_check",
    "explicit_operator_launch",
}


def load_json(path: Path) -> dict[str, Any]:
    return json.loads(path.read_text())


def profile_paths(path: Path) -> list[Path]:
    if path.is_dir():
        return sorted(path.rglob("*.json"))
    return [path]


def validate(path: Path) -> dict[str, Any]:
    data = load_json(path)
    errors: list[str] = []
    if data.get("provider") != "neocloud":
        errors.append("provider must be neocloud")
    if data.get("provider_class") != "gpu_pod":
        errors.append("neocloud provider_class must be gpu_pod")
    if data.get("operator_gate_required") is not True:
        errors.append("neocloud profiles must require an operator gate")
    if data.get("blessed_path") is True:
        errors.append("neocloud gpu pod profile must stay adapter-ready/preferred, not blessed_path=true")
    neocloud = data.get("neocloud")
    if not isinstance(neocloud, dict):
        errors.append("neocloud block is required")
        neocloud = {}
    for key in sorted(REQUIRED_NEO_KEYS - set(neocloud)):
        errors.append(f"neocloud profile missing {key}")
    for key in ["scope_check_required", "launch_preflight_required", "cleanup_proof_required"]:
        if key in neocloud and neocloud.get(key) is not True:
            errors.append(f"neocloud.{key} must be true")
    ready = set(data.get("execution_ready_requires", []))
    for gate in sorted(REQUIRED_GATES - ready):
        errors.append(f"execution_ready_requires missing {gate}")
    return {
        "ok": not errors,
        "path": str(path),
        "profile_id": data.get("profile_id"),
        "errors": errors,
        "warnings": [],
    }


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("path", type=Path, nargs="?", default=Path("modules/provider-profiles/neocloud"))
    parser.add_argument("--json", action="store_true")
    args = parser.parse_args()

    results = [validate(path) for path in profile_paths(args.path)]
    ok = bool(results) and all(item["ok"] for item in results)
    summary = {
        "ok": ok,
        "checked": len(results),
        "failures": [item for item in results if not item["ok"]],
        "profiles": results,
    }
    if args.json:
        print(json.dumps(summary, indent=2, sort_keys=True))
    else:
        print(f"ok: {ok}")
        print(f"checked: {len(results)}")
        for failure in summary["failures"]:
            print(f"failed: {failure['path']}")
            for error in failure["errors"]:
                print(f"  {error}")
    return 0 if ok else 1


if __name__ == "__main__":
    raise SystemExit(main())
