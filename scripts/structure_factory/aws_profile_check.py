#!/usr/bin/env python3
"""Validate AWS provider profile readiness gates for Structure Factory."""

from __future__ import annotations

import argparse
import json
from pathlib import Path
from typing import Any


REQUIRED_BATCH_REFS = {
    "compute_environment_ref",
    "job_queue_ref",
    "job_definition_ref",
    "artifact_bucket_ref",
    "log_group_ref",
    "budget_name_ref",
}
REQUIRED_BATCH_GATES = {
    "aws_account_region_allowlist",
    "ec2_gpu_quota_check",
    "batch_compute_environment",
    "batch_job_queue",
    "batch_job_definition",
    "ecr_auth_or_public_image",
    "s3_artifact_bucket",
    "cloudwatch_log_group",
    "aws_budget_alert",
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
    warnings: list[str] = []
    if data.get("provider") != "aws":
        errors.append("provider must be aws")
    if data.get("operator_gate_required") is not True:
        errors.append("AWS provider profiles must require an operator gate")
    aws = data.get("aws")
    if not isinstance(aws, dict):
        errors.append("aws block is required")
        aws = {}
    ready = set(data.get("execution_ready_requires", []))
    if data.get("profile_id") == "aws-batch-gpu-no-download":
        for key in sorted(REQUIRED_BATCH_REFS - set(aws)):
            errors.append(f"aws batch profile missing {key}")
        for gate in sorted(REQUIRED_BATCH_GATES - ready):
            errors.append(f"aws batch execution_ready_requires missing {gate}")
        if data.get("blessed_path") is not True:
            errors.append("aws-batch-gpu-no-download must set blessed_path=true")
    elif data.get("blessed_path") is True:
        errors.append("only aws-batch-gpu-no-download may set blessed_path=true")
    if aws.get("artifact_egress") != "s3_checksum_required":
        warnings.append("aws.artifact_egress should require S3 checksums")
    return {
        "ok": not errors,
        "path": str(path),
        "profile_id": data.get("profile_id"),
        "errors": errors,
        "warnings": warnings,
    }


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("path", type=Path, nargs="?", default=Path("modules/provider-profiles/aws"))
    parser.add_argument("--json", action="store_true")
    args = parser.parse_args()

    results = [validate(path) for path in profile_paths(args.path)]
    ok = bool(results) and all(item["ok"] for item in results)
    summary = {
        "ok": ok,
        "checked": len(results),
        "failures": [item for item in results if not item["ok"]],
        "warnings": [{"path": item["path"], "warnings": item["warnings"]} for item in results if item["warnings"]],
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
