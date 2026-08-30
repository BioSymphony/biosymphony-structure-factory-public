#!/usr/bin/env python3
"""Validate a Structure Factory RunPod launch manifest."""

from __future__ import annotations

import argparse
import json
from pathlib import Path
from typing import Any


REQUIRED_TOP_LEVEL = {
    "schema_version",
    "manifest_id",
    "provider",
    "provider_class",
    "run_id",
    "campaign_id",
    "repo",
    "data_policy",
    "stage_contract",
    "progress_ledger",
    "runpod",
    "environment",
    "smoke_checks",
    "expected_artifacts",
    "license_gates",
}

REQUIRED_REPO = {"url", "git_ref", "delivery"}
REQUIRED_RUNPOD = {
    "mode",
    "recommended_gpu",
    "gpu_count",
    "container_disk_gb",
    "volume_mount",
    "network_volume_required",
    "template_family",
    "image_name",
    "image_visibility",
    "image_digest_required_for_real",
    "registry_auth",
    "monitoring",
}
REQUIRED_ENV = {
    "STRUCTURE_FACTORY_RUN_ID",
    "STRUCTURE_FACTORY_VOLUME_ROOT",
    "STRUCTURE_FACTORY_EXECUTION_PROFILE",
}
FORBIDDEN_SECRET_KEYS = {
    "TOKEN",
    "SECRET",
    "PASSWORD",
    "LICENSE",
    "API_KEY",
    "PRIVATE_KEY",
}
REQUIRED_RAW_FANOUT_POLICY = {
    "max_raw_movie_files",
    "max_download_bytes",
    "max_motion_frames",
    "max_context_micrographs",
}


def load_json(path: Path) -> dict[str, Any]:
    return json.loads(path.read_text())


def missing_keys(obj: dict[str, Any], required: set[str]) -> list[str]:
    return sorted(required - set(obj))


def is_digest_pinned(image_name: str) -> bool:
    return "@sha256:" in image_name


def image_registry(image_name: str) -> str:
    return image_name.split("/", 1)[0] if "/" in image_name else ""


def validate(manifest: dict[str, Any], *, manifest_path: Path | None = None, execution_ready: bool = False) -> dict[str, Any]:
    errors: list[str] = []
    warnings: list[str] = []

    for key in missing_keys(manifest, REQUIRED_TOP_LEVEL):
        errors.append(f"missing top-level key: {key}")

    repo = manifest.get("repo", {})
    runpod = manifest.get("runpod", {})
    env = manifest.get("environment", {})
    policy = manifest.get("data_policy", {})
    execution_profile = manifest.get("execution_profile") or env.get("STRUCTURE_FACTORY_EXECUTION_PROFILE")
    is_no_download = execution_profile == "no-download-smoke" or env.get("STRUCTURE_FACTORY_NO_DOWNLOAD") in {"1", "true", "yes"}

    if isinstance(repo, dict):
        for key in missing_keys(repo, REQUIRED_REPO):
            errors.append(f"missing repo key: {key}")
    else:
        errors.append("repo must be object")

    if isinstance(runpod, dict):
        for key in missing_keys(runpod, REQUIRED_RUNPOD):
            errors.append(f"missing runpod key: {key}")
    else:
        errors.append("runpod must be object")

    if isinstance(env, dict):
        for key in missing_keys(env, REQUIRED_ENV):
            errors.append(f"missing environment key: {key}")
        for key, value in env.items():
            upper = key.upper()
            if any(marker in upper for marker in FORBIDDEN_SECRET_KEYS):
                errors.append(f"environment contains secret-like key: {key}")
            if isinstance(value, str) and any(marker in value.lower() for marker in ["ghp_", "gho_", "lin_api_", "-----begin"]):
                errors.append(f"environment value looks secret-like: {key}")
    else:
        errors.append("environment must be object")

    if manifest.get("provider") != "runpod":
        errors.append("provider must be runpod")
    if manifest.get("provider_class") != "pod":
        errors.append("provider_class must be pod")
    if runpod.get("mode") != "pod":
        errors.append("runpod.mode must be pod")
    if runpod.get("volume_mount") != "/workspace":
        errors.append("runpod.volume_mount must be /workspace")
    stage_contract = manifest.get("stage_contract")
    if not isinstance(stage_contract, str) or not stage_contract:
        errors.append("stage_contract must be a non-empty path")
    elif stage_contract.startswith("/"):
        errors.append("stage_contract must be repo-relative, not absolute")
    elif manifest_path is not None:
        repo_root = manifest_path.resolve().parents[2] if len(manifest_path.resolve().parents) >= 3 else manifest_path.resolve().parent
        if not (repo_root / stage_contract).exists():
            errors.append(f"stage_contract path does not exist: {stage_contract}")
    progress_ledger = manifest.get("progress_ledger")
    if not isinstance(progress_ledger, str) or not progress_ledger.startswith("/workspace/"):
        errors.append("progress_ledger must be an absolute /workspace path")
    if policy.get("allow_private_data") is not False:
        errors.append("data_policy.allow_private_data must be false for prep")
    if execution_profile not in {
        "no-download-smoke",
        "raw-subset-open",
        "raw-subset-gated",
        "map-model-report",
    }:
        errors.append(f"unknown execution_profile: {execution_profile}")
    if runpod.get("network_volume_required") is not True and not manifest.get("scratch_policy", {}).get("scratch_only"):
        errors.append("runpod.network_volume_required may be false only when scratch_policy.scratch_only is true")
    expected_download_bytes = policy.get("expected_download_bytes")
    if not isinstance(expected_download_bytes, int) or expected_download_bytes < 0:
        errors.append("data_policy.expected_download_bytes must be a non-negative integer")

    image_name = str(runpod.get("image_name", ""))
    if not image_name:
        errors.append("runpod.image_name must be non-empty")
    image_visibility = runpod.get("image_visibility")
    if image_visibility not in {"public", "private"}:
        errors.append("runpod.image_visibility must be public or private")
    registry_auth = runpod.get("registry_auth", {})
    if image_visibility == "private" or image_registry(image_name) in {"ghcr" + ".io"}:
        if not isinstance(registry_auth, dict):
            errors.append("runpod.registry_auth must be object for private registry images")
        else:
            if registry_auth.get("required") is not True:
                errors.append("runpod.registry_auth.required must be true for private registry images")
            refs = registry_auth.get("runtime_secret_refs")
            if not isinstance(refs, list) or not refs:
                errors.append("runpod.registry_auth.runtime_secret_refs must list runtime env refs")
            elif any(not isinstance(ref, str) or not ref for ref in refs):
                errors.append("runpod.registry_auth.runtime_secret_refs must contain non-empty strings")
            if registry_auth.get("credential_policy") != "runtime_reference_only":
                errors.append("runpod.registry_auth.credential_policy must be runtime_reference_only")
            literal_markers = ["ghp_", "gho_", "github_pat_", "password", "token:", "-----BEGIN"]
            if any(marker.lower() in json.dumps(registry_auth).lower() for marker in literal_markers):
                errors.append("runpod.registry_auth appears to contain literal credentials")
    if runpod.get("image_digest_required_for_real") is not True:
        errors.append("runpod.image_digest_required_for_real must be true")
    if not is_digest_pinned(image_name):
        message = "runpod.image_name is not digest-pinned; install-at-boot/tag images are prep-only risk"
        if execution_ready:
            errors.append(message)
        else:
            warnings.append(message)

    monitoring = runpod.get("monitoring", {})
    if not isinstance(monitoring, dict):
        errors.append("runpod.monitoring must be object")
    else:
        required_signals = monitoring.get("required_signals", [])
        for signal in ["provider_actual_status", "runtime_uptime_seconds", "image_pull_success_or_failure", "stage_progress_heartbeat"]:
            if signal not in required_signals:
                errors.append(f"runpod.monitoring.required_signals missing {signal}")
        if monitoring.get("desired_status_only_ok") is not False:
            errors.append("runpod.monitoring.desired_status_only_ok must be false")
        if monitoring.get("progress_ledger") != progress_ledger:
            errors.append("runpod.monitoring.progress_ledger must match top-level progress_ledger")

    if is_no_download:
        if policy.get("allow_large_downloads") is not False:
            errors.append("data_policy.allow_large_downloads must be false for no-download profile")
        if policy.get("allow_raw_cryoem_downloads") is not False:
            errors.append("data_policy.allow_raw_cryoem_downloads must be false for no-download profile")
        if policy.get("expected_download_bytes") != 0:
            errors.append("data_policy.expected_download_bytes must be 0 for no-download profile")
        if env.get("STRUCTURE_FACTORY_NO_DOWNLOAD") not in {"1", "true", "yes"}:
            errors.append("STRUCTURE_FACTORY_NO_DOWNLOAD must be set to a truthy value for no-download profile")
    else:
        if env.get("STRUCTURE_FACTORY_NO_DOWNLOAD") in {"1", "true", "yes"}:
            errors.append("STRUCTURE_FACTORY_NO_DOWNLOAD must not be truthy outside no-download profile")
        if expected_download_bytes == 0:
            errors.append("non no-download profiles must declare expected_download_bytes > 0")

    if policy.get("allow_raw_cryoem_downloads") is True:
        plan = manifest.get("download_plan", {})
        raw_auth = env.get("STRUCTURE_FACTORY_ALLOW_RAW_DOWNLOADS")
        operator_auth = env.get("STRUCTURE_FACTORY_OPERATOR_AUTHORIZED")
        truthy_auth = {"1", "true", "yes"}
        if execution_ready:
            if raw_auth not in truthy_auth or operator_auth not in truthy_auth:
                errors.append("execution-ready raw-download manifests require STRUCTURE_FACTORY_ALLOW_RAW_DOWNLOADS and STRUCTURE_FACTORY_OPERATOR_AUTHORIZED")
        elif raw_auth in truthy_auth or operator_auth in truthy_auth:
            warnings.append("tracked raw-download manifests should keep raw and human authorization pending until runtime packet creation")
        if not isinstance(plan, dict) or not plan:
            errors.append("raw download profile requires download_plan")
        else:
            if not plan.get("data_module"):
                errors.append("download_plan.data_module is required")
            if not plan.get("subset_profile"):
                errors.append("download_plan.subset_profile is required")
            max_files = plan.get("max_files")
            if not isinstance(max_files, int) or max_files <= 0 or max_files > 500:
                errors.append("download_plan.max_files must be between 1 and 500")
            if not plan.get("deterministic_rule"):
                errors.append("download_plan.deterministic_rule is required")
            if plan.get("allow_processed_inputs") is not False:
                errors.append("download_plan.allow_processed_inputs must be false for raw subset demos")
            destination = str(plan.get("destination_root", ""))
            if not destination.startswith("/workspace/"):
                errors.append("download_plan.destination_root must be under /workspace")
        fanout_policy = manifest.get("fanout_policy", {})
        if not isinstance(fanout_policy, dict) or not fanout_policy:
            errors.append("raw download profile requires fanout_policy")
        else:
            for key in sorted(REQUIRED_RAW_FANOUT_POLICY - set(fanout_policy)):
                errors.append(f"fanout_policy missing {key}")
            for key in sorted(REQUIRED_RAW_FANOUT_POLICY.intersection(fanout_policy)):
                value = fanout_policy.get(key)
                if not isinstance(value, int) or value <= 0:
                    errors.append(f"fanout_policy.{key} must be a positive integer")
    elif not is_no_download and execution_profile == "map-model-report":
        artifact_plan = manifest.get("artifact_plan", {})
        if not isinstance(artifact_plan, dict) or not artifact_plan:
            errors.append("map-model-report profile requires artifact_plan")
        elif artifact_plan.get("allow_raw_cryoem_downloads") is not False:
            errors.append("artifact_plan.allow_raw_cryoem_downloads must be false")

    artifacts = manifest.get("expected_artifacts", [])
    if not isinstance(artifacts, list) or not artifacts:
        errors.append("expected_artifacts must be a non-empty list")
    elif not all(str(path).startswith("/workspace/") for path in artifacts):
        errors.append("all expected_artifacts must be under /workspace")

    smoke_checks = manifest.get("smoke_checks", [])
    required_checks = [
        "repo_clone_manifest",
        "artifact_manifest",
        "input_audit",
        "contract_self_check",
        "stage_contract",
        "stage_progress_ledger",
    ]
    if execution_profile in {"no-download-smoke", "raw-subset-open", "raw-subset-gated"}:
        required_checks.append("gpu_visibility")
    if runpod.get("network_volume_required") is True:
        required_checks.append("network_volume_write_read")
    else:
        required_checks.append("scratch_write_read")
    if policy.get("allow_raw_cryoem_downloads") is True:
        required_checks.append("operator_authorization_gate")
        required_checks.append("fanout_estimate")
    for required_check in required_checks:
        if required_check not in smoke_checks:
            errors.append(f"missing smoke check: {required_check}")

    expected_suffixes = [
        "validation/input-audit.json",
        "validation/contract-self-check.json",
        "validation/stage-contract-check.json",
        "stage-progress.jsonl",
    ]
    if policy.get("allow_raw_cryoem_downloads") is True:
        expected_suffixes.append("validation/fanout-estimate.json")
    for suffix in expected_suffixes:
        if not any(str(path).endswith(suffix) for path in artifacts):
            errors.append(f"expected_artifacts missing {suffix}")

    if repo.get("git_ref") in {"main", "master"}:
        warnings.append("repo.git_ref is branch-like; pin to commit before real RunPod execution")
    if execution_ready and not str(repo.get("git_ref", "")).startswith("sha256:"):
        git_ref = str(repo.get("git_ref", ""))
        if not (len(git_ref) == 40 and all(char in "0123456789abcdef" for char in git_ref.lower())):
            errors.append("execution-ready RunPod manifests must pin repo.git_ref to a 40-character commit SHA")

    return {
        "ok": not errors,
        "errors": errors,
        "warnings": warnings,
        "manifest_id": manifest.get("manifest_id"),
        "run_id": manifest.get("run_id"),
    }


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("manifest", type=Path)
    parser.add_argument("--execution-ready", action="store_true", help="Require real launch pins, not prep-only warnings")
    parser.add_argument("--json", action="store_true")
    args = parser.parse_args()

    summary = validate(load_json(args.manifest), manifest_path=args.manifest, execution_ready=args.execution_ready)
    summary["manifest_path"] = str(args.manifest.resolve())

    if args.json:
        print(json.dumps(summary, indent=2, sort_keys=True))
    else:
        print(f"ok: {summary['ok']}")
        for warning in summary["warnings"]:
            print(f"warning: {warning}")
        for error in summary["errors"]:
            print(f"error: {error}")

    return 0 if summary["ok"] else 1


if __name__ == "__main__":
    raise SystemExit(main())
