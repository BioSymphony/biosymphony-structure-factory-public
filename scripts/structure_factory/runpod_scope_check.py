#!/usr/bin/env python3
"""Validate RunPod provider templates or packets are scoped to Structure Factory resources."""

from __future__ import annotations

import argparse
import json
import subprocess
import tempfile
from pathlib import Path
from typing import Any


ALLOWED_RESOURCE_PREFIXES = ("bsf-", "structure-factory-")
FORBIDDEN_CROSS_CAMPAIGN_MARKERS = ("GENECLUSTER", "BIOPROSPECTOR", "DOE_", "OBS_", "PARAMETER_GOLF")
STRUCTURE_FACTORY_VOLUME_REF = "STRUCTURE_FACTORY_RUNPOD_NETWORK_VOLUME_ID"
ALLOWED_SOFTWARE_ROOTS = ("/workspace/structure-factory/", "/workspace/software")
ALLOWED_REPO_SOURCES = {"git_remote_or_snapshot", "inline_commands"}


def load_json(path: Path) -> dict[str, Any]:
    return json.loads(path.read_text())


def bridge_paths(path: Path) -> list[Path]:
    if path.is_dir():
        return sorted(path.glob("*.json"))
    return [path]


def string_contains_forbidden_marker(value: Any) -> str | None:
    text = json.dumps(value, sort_keys=True) if not isinstance(value, str) else value
    upper = text.upper()
    for marker in FORBIDDEN_CROSS_CAMPAIGN_MARKERS:
        if marker in upper:
            return marker
    return None


def is_hex_commit(value: str) -> bool:
    return len(value) == 40 and all(char in "0123456789abcdef" for char in value.lower())


def remote_commit_visible(url: str, commit: str, timeout_seconds: int = 30) -> tuple[bool, str]:
    """Return whether the declared remote can satisfy a checkout of the pinned commit."""
    if not url or not is_hex_commit(commit):
        return False, "repo url or commit pin is invalid"
    try:
        ls_remote = subprocess.run(
            ["git", "ls-remote", url],
            check=False,
            text=True,
            capture_output=True,
            timeout=timeout_seconds,
        )
    except (OSError, subprocess.TimeoutExpired) as exc:
        return False, f"git ls-remote failed: {exc}"
    if ls_remote.returncode == 0 and any(line.startswith(f"{commit}\t") for line in ls_remote.stdout.splitlines()):
        return True, "commit is advertised by a remote ref"

    with tempfile.TemporaryDirectory() as tmp:
        subprocess.run(["git", "init", "-q", tmp], check=True, text=True, capture_output=True)
        fetch = subprocess.run(
            ["git", "-C", tmp, "fetch", "--depth=1", "--filter=blob:none", url, commit],
            check=False,
            text=True,
            capture_output=True,
            timeout=timeout_seconds,
        )
    if fetch.returncode == 0:
        return True, "commit is fetchable by SHA"
    stderr = fetch.stderr.strip().splitlines()
    detail = stderr[-1] if stderr else "git fetch by SHA failed"
    return False, detail


def validate_bridge(
    data: dict[str, Any],
    path: Path,
    *,
    source_ready: bool = False,
    probe_remote: bool = False,
) -> dict[str, Any]:
    errors: list[str] = []
    warnings: list[str] = []
    runpod = data.get("runpod", {})
    repo = data.get("repo", {})
    worker = data.get("worker_coordination", {})
    closeout = data.get("closeout", {})
    artifact_egress = data.get("artifact_egress", {})
    tool_setup = runpod.get("toolSetup", {}) if isinstance(runpod, dict) else {}
    env = runpod.get("env", {}) if isinstance(runpod, dict) else {}
    public_template = data.get("public_template_status") == "tracked_public_template"

    if data.get("manifest_kind") != "symphony_runpod_launch":
        errors.append("manifest_kind must be symphony_runpod_launch")
    provider = data.get("provider", {})
    if provider.get("name") != "runpod" or provider.get("adapter") != "runpod_pod_v1":
        errors.append("provider must be runpod_pod_v1")

    if not isinstance(repo, dict):
        errors.append("repo must be an object")
    else:
        repo_source = str(repo.get("source", ""))
        repo_url = str(repo.get("url_or_path", ""))
        commit_or_snapshot = str(repo.get("commit_or_snapshot", ""))
        if repo_source not in ALLOWED_REPO_SOURCES:
            errors.append("repo.source must be git_remote_or_snapshot or inline_commands")
        if repo_source == "git_remote_or_snapshot":
            if not repo_url or repo_url == "inline":
                errors.append("git_remote_or_snapshot requires repo.url_or_path")
            if not is_hex_commit(commit_or_snapshot) and not public_template:
                errors.append("git_remote_or_snapshot requires repo.commit_or_snapshot to be a 40-character commit SHA")
            elif source_ready and probe_remote:
                visible, detail = remote_commit_visible(repo_url, commit_or_snapshot)
                if not visible:
                    errors.append(
                        "git_remote_or_snapshot commit is not fetchable from repo.url_or_path: "
                        f"{commit_or_snapshot} ({detail})"
                    )
        elif repo_source == "inline_commands":
            startup_commands = data.get("startup", {}).get("commands", [])
            if not isinstance(startup_commands, list) or not startup_commands:
                errors.append("inline_commands requires startup.commands")
            if source_ready and str(repo.get("workdir", "")) in {"", "/workspace/repo"}:
                warnings.append(
                    "inline_commands does not clone the repo; ensure commands are fully inline or repo.workdir is pre-synced"
                )

    resource_prefix = str(worker.get("resource_name_prefix", ""))
    if not resource_prefix:
        errors.append("worker_coordination.resource_name_prefix is required")
    elif not resource_prefix.startswith(ALLOWED_RESOURCE_PREFIXES):
        errors.append(
            "worker_coordination.resource_name_prefix must start with one of: "
            + ", ".join(ALLOWED_RESOURCE_PREFIXES)
        )
    if worker.get("single_mutating_worker") is not True:
        errors.append("worker_coordination.single_mutating_worker must be true")
    if worker.get("read_only_monitors_allowed") is not True:
        errors.append("worker_coordination.read_only_monitors_allowed must be true")

    pod_name = str(runpod.get("name", ""))
    if not pod_name:
        errors.append("runpod.name is required")
    elif not pod_name.startswith(ALLOWED_RESOURCE_PREFIXES):
        errors.append("runpod.name must start with a Structure Factory prefix")

    network_volume_id = str(runpod.get("networkVolumeId", ""))
    if network_volume_id:
        marker = string_contains_forbidden_marker(network_volume_id)
        if marker:
            errors.append(f"runpod.networkVolumeId appears to reference another campaign: {marker}")
        if (
            "PENDING-set-at-launch-from-" in network_volume_id
            and STRUCTURE_FACTORY_VOLUME_REF not in network_volume_id
        ):
            errors.append(
                "pending networkVolumeId must use "
                f"{STRUCTURE_FACTORY_VOLUME_REF}, not a generic or sibling-campaign env var"
            )
        repo_source = env.get("STRUCTURE_FACTORY_REPO_SOURCE") if isinstance(env, dict) else None
        if artifact_egress.get("requires_network_volume") is not True and repo_source != "network_volume":
            warnings.append("networkVolumeId is set but artifact_egress.requires_network_volume is not true")

    if isinstance(env, dict):
        volume_root = env.get("STRUCTURE_FACTORY_VOLUME_ROOT")
        if network_volume_id and volume_root != "/workspace/structure-factory":
            errors.append("network-volume runs must set STRUCTURE_FACTORY_VOLUME_ROOT=/workspace/structure-factory")
    else:
        errors.append("runpod.env must be an object")

    marker = string_contains_forbidden_marker(data)
    if marker:
        errors.append(f"manifest contains forbidden cross-campaign marker: {marker}")

    if isinstance(tool_setup, dict) and tool_setup:
        tool_setup_env_ref = tool_setup.get("network_volume_env_var")
        tool_setup_volume_id = tool_setup.get("network_volume_id")
        if tool_setup_env_ref != STRUCTURE_FACTORY_VOLUME_REF and tool_setup_volume_id != network_volume_id:
            errors.append(
                "runpod.toolSetup must declare either "
                f"network_volume_env_var={STRUCTURE_FACTORY_VOLUME_REF} or a network_volume_id matching runpod.networkVolumeId"
            )
        software_root = str(tool_setup.get("software_root", ""))
        if software_root and not software_root.startswith(ALLOWED_SOFTWARE_ROOTS):
            errors.append(
                "runpod.toolSetup.software_root must live under /workspace/structure-factory "
                "or /workspace/software on a dedicated Structure Factory volume"
            )
        weights_root = str(tool_setup.get("weights_root", ""))
        if weights_root and not weights_root.startswith(ALLOWED_SOFTWARE_ROOTS):
            errors.append(
                "runpod.toolSetup.weights_root must live under /workspace/structure-factory "
                "or /workspace/software on a dedicated Structure Factory volume"
            )
    elif network_volume_id and not (
        isinstance(env, dict) and env.get("STRUCTURE_FACTORY_REPO_SOURCE") == "network_volume"
    ):
        warnings.append("networkVolumeId is set but runpod.toolSetup is not declared")

    if closeout.get("stop_or_delete_pod") is not True:
        errors.append("closeout.stop_or_delete_pod must be true")
    if closeout.get("retain_pod") is not False:
        errors.append("closeout.retain_pod must be false unless an issue explicitly authorizes retention")

    return {
        "ok": not errors,
        "path": str(path),
        "run_id": data.get("run_id"),
        "pod_name": pod_name,
        "resource_name_prefix": resource_prefix,
        "network_volume_id": network_volume_id,
        "errors": errors,
        "warnings": warnings,
    }


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("path", type=Path, help="Bridge manifest JSON file or directory")
    parser.add_argument("--source-ready", action="store_true", help="Require repo delivery to be ready for paid launch")
    parser.add_argument("--no-remote-probe", action="store_true", help="Skip git remote fetchability probe")
    parser.add_argument("--json", action="store_true")
    args = parser.parse_args()

    results = [
        validate_bridge(
            load_json(path),
            path,
            source_ready=args.source_ready,
            probe_remote=not args.no_remote_probe,
        )
        for path in bridge_paths(args.path)
    ]
    ok = bool(results) and all(result["ok"] for result in results)
    summary = {
        "ok": ok,
        "checked": len(results),
        "failures": [result for result in results if not result["ok"]],
        "warnings": [
            {"path": result["path"], "warning": warning}
            for result in results
            for warning in result["warnings"]
        ],
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
        for warning in summary["warnings"]:
            print(f"warning: {warning['path']}: {warning['warning']}")
    return 0 if ok else 1


if __name__ == "__main__":
    raise SystemExit(main())
