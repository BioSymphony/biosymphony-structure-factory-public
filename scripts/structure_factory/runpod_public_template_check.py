#!/usr/bin/env python3
"""Validate tracked RunPod manifests omit live execution state."""

from __future__ import annotations

import argparse
import json
from pathlib import Path
from typing import Any


ALLOWED_NETWORK_VOLUME_IDS = {"", "STRUCTURE_FACTORY_RUNPOD_NETWORK_VOLUME_ID"}
BLOCKED_TEXT_MARKERS = [
    "base64 -d",
    "gunzip",
    "xz -d",
    "--yes-create-paid-runpod",
    '"approved_at": "20',
]


def load_json(path: Path) -> Any:
    with path.open("r", encoding="utf-8") as handle:
        return json.load(handle)


def check_manifest(path: Path) -> list[dict[str, str]]:
    findings: list[dict[str, str]] = []
    rel = path.as_posix()
    text = path.read_text(encoding="utf-8")
    for marker in BLOCKED_TEXT_MARKERS:
        if marker in text:
            findings.append({"path": rel, "check_id": "blocked-public-template-marker", "message": marker})

    try:
        manifest = load_json(path)
    except json.JSONDecodeError as exc:
        return [{"path": rel, "check_id": "invalid-json", "message": str(exc)}]

    if manifest.get("remote_launch_allowed") is not False:
        findings.append({"path": rel, "check_id": "remote-launch-allowed", "message": "remote_launch_allowed must be false"})
    if manifest.get("public_template_status") != "tracked_public_template":
        findings.append({"path": rel, "check_id": "public-template-status", "message": "public_template_status must be tracked_public_template"})

    auth = manifest.get("launch_authorization", {})
    if auth.get("approved_at") != "PENDING":
        findings.append({"path": rel, "check_id": "approval-timestamp", "message": "launch_authorization.approved_at must be PENDING"})
    if auth.get("approved_by") not in {"PENDING", "PENDING-OPERATOR-GATE", ""}:
        findings.append({"path": rel, "check_id": "approval-identity", "message": "approved_by must be a public placeholder"})

    runpod = manifest.get("runpod", {})
    if runpod.get("dataCenterIds") not in ([], None):
        findings.append({"path": rel, "check_id": "concrete-placement", "message": "dataCenterIds must be empty in public templates"})
    network_volume_id = runpod.get("networkVolumeId", "")
    if network_volume_id not in ALLOWED_NETWORK_VOLUME_IDS:
        findings.append({"path": rel, "check_id": "network-volume-id", "message": "networkVolumeId must be empty or STRUCTURE_FACTORY_RUNPOD_NETWORK_VOLUME_ID"})

    commands = manifest.get("startup", {}).get("commands", [])
    if "startup" in manifest:
        if not isinstance(commands, list) or not commands:
            findings.append({"path": rel, "check_id": "startup-commands", "message": "startup.commands must be a non-empty list"})
        else:
            joined = "\n".join(str(command) for command in commands)
            if "exit 64" not in joined and "exit 2" not in joined and "exit 1" not in joined:
                findings.append({"path": rel, "check_id": "nonzero-exit", "message": "public startup command must exit nonzero"})
            if "Tracked template has no runtime payload" not in joined:
                findings.append({"path": rel, "check_id": "public-template-message", "message": "startup should state that the tracked template has no runtime payload"})

    if manifest.get("data_policy", {}).get("allow_raw_cryoem_downloads") is True:
        env = manifest.get("environment", {})
        if env.get("STRUCTURE_FACTORY_ALLOW_RAW_DOWNLOADS") == "1" or env.get("STRUCTURE_FACTORY_OPERATOR_AUTHORIZED") == "1":
            findings.append({
                "path": rel,
                "check_id": "raw-download-enabled",
                "message": "public raw-download launch manifests must use pending operator authorization values",
            })
    if manifest.get("active_gated_lanes"):
        env_text = json.dumps(manifest.get("environment", {}))
        if '"1"' in env_text:
            findings.append({
                "path": rel,
                "check_id": "gated-lane-enabled",
                "message": "public gated-lane launch manifests must not enable license-gated lanes by default",
            })

    repo = manifest.get("repo", {})
    commit = str(repo.get("commit_or_snapshot", ""))
    if (
        len(commit) == 40
        and all(char in "0123456789abcdefABCDEF" for char in commit)
        and set(commit) != {"0"}
    ):
        findings.append({"path": rel, "check_id": "launchable-git-ref", "message": "public RunPod manifests should not carry launch-ready commit SHAs"})

    return findings


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("manifest_dir", nargs="?", default="runpod/bridge-manifests")
    parser.add_argument("--json", action="store_true")
    args = parser.parse_args()

    manifest_path = Path(args.manifest_dir)
    findings: list[dict[str, str]] = []
    if manifest_path.is_file():
        paths = [manifest_path]
    else:
        paths = sorted(manifest_path.glob("*.json"))
    for path in paths:
        findings.extend(check_manifest(path))
    result = {"ok": not findings, "manifest_count": len(paths), "finding_count": len(findings), "findings": findings}
    if args.json:
        print(json.dumps(result, indent=2, sort_keys=True))
    else:
        print(json.dumps(result, indent=2, sort_keys=True))
    return 0 if result["ok"] else 1


if __name__ == "__main__":
    raise SystemExit(main())
