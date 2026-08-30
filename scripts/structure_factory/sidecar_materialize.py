#!/usr/bin/env python3
"""Materialize provider-neutral Structure Factory modules into a RunPod launch manifest."""

from __future__ import annotations

import argparse
import json
from pathlib import Path
from typing import Any


def load(path: Path) -> dict[str, Any]:
    return json.loads(path.read_text())


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--campaign", type=Path, required=True)
    parser.add_argument("--provider-profile", type=Path, required=True)
    parser.add_argument("--repo-url", default="https://github.com/BioSymphony/structure-factory.git")
    parser.add_argument("--git-ref", default="structure-factory-prep-v0")
    parser.add_argument("--out", type=Path, required=True)
    args = parser.parse_args()

    campaign = load(args.campaign)
    provider = load(args.provider_profile)
    if provider.get("provider") != "runpod":
        raise SystemExit(
            "sidecar_materialize currently emits RunPod launch manifests only; "
            "use provider_profile_check.py for non-RunPod adapter contracts"
        )
    image_modules = [load(args.campaign.resolve().parents[2] / rel) for rel in campaign.get("image_modules", [])]
    primary_family = image_modules[0]["family"] if image_modules else "cryo-core"
    image_name = provider.get("image_map", {}).get(primary_family)
    if not image_name:
        raise SystemExit(f"provider profile has no image for family {primary_family}")

    manifest = {
        "schema_version": 1,
        "manifest_id": f"{campaign['campaign_id']}-{campaign['run_profile']}-{provider['provider']}",
        "execution_profile": "no-download-smoke" if campaign["run_profile"] == "no_download_smoke" else campaign["run_profile"].replace("_", "-"),
        "provider": provider["provider"],
        "provider_class": provider["provider_class"],
        "run_id": f"{campaign['campaign_id']}-{campaign['run_profile']}",
        "campaign_id": campaign["campaign_id"],
        "repo": {
            "url": args.repo_url,
            "git_ref": args.git_ref,
            "delivery": "public_git_clone",
        },
        "data_policy": {
            "allow_large_downloads": campaign["policies"]["allow_large_downloads"],
            "allow_raw_cryoem_downloads": campaign["policies"]["allow_raw_cryoem_downloads"],
            "allow_private_data": campaign["policies"]["allow_private_data"],
            "expected_download_bytes": campaign["policies"]["expected_download_bytes"],
        },
        "scratch_policy": {
            "scratch_only": bool(provider.get("scratch_only", False)),
            "delete_after_export": bool(provider.get("scratch_only", False)),
        },
        "runpod": {
            "mode": provider["provider_class"],
            "recommended_gpu": provider["recommended_gpu"],
            "fallback_gpu": provider.get("fallback_gpu"),
            "gpu_count": provider["gpu_count"],
            "container_disk_gb": provider["container_disk_gb"],
            "volume_mount": provider["volume_mount"],
            "network_volume_required": provider["network_volume_required"],
            "template_family": primary_family,
            "image_name": image_name,
            "ports": [],
        },
        "environment": {
            "STRUCTURE_FACTORY_RUN_ID": f"{campaign['campaign_id']}-{campaign['run_profile']}",
            "STRUCTURE_FACTORY_REPO_URL": args.repo_url,
            "STRUCTURE_FACTORY_GIT_REF": args.git_ref,
            "STRUCTURE_FACTORY_VOLUME_ROOT": "/workspace/structure-factory",
            "STRUCTURE_FACTORY_EXECUTION_PROFILE": "no-download-smoke" if campaign["run_profile"] == "no_download_smoke" else campaign["run_profile"].replace("_", "-"),
            "STRUCTURE_FACTORY_NO_DOWNLOAD": "1",
        },
        "smoke_checks": [
            "repo_clone_manifest",
            "python_tooling",
            "gpu_visibility",
            "network_volume_write_read",
            "image_version_manifest",
            "no_large_download_policy",
            "input_audit",
            "artifact_manifest",
            "contract_self_check",
        ],
        "expected_artifacts": [
            f"/workspace/structure-factory/runs/{campaign['campaign_id']}-{campaign['run_profile']}/run-manifest.json",
            f"/workspace/structure-factory/runs/{campaign['campaign_id']}-{campaign['run_profile']}/validation/input-audit.json",
            f"/workspace/structure-factory/runs/{campaign['campaign_id']}-{campaign['run_profile']}/validation/toolcheck.json",
            f"/workspace/structure-factory/runs/{campaign['campaign_id']}-{campaign['run_profile']}/validation/gpu.json",
            f"/workspace/structure-factory/runs/{campaign['campaign_id']}-{campaign['run_profile']}/validation/storage.json",
            f"/workspace/structure-factory/runs/{campaign['campaign_id']}-{campaign['run_profile']}/validation/contract-self-check.json",
            f"/workspace/structure-factory/runs/{campaign['campaign_id']}-{campaign['run_profile']}/provenance.md",
        ],
        "license_gates": [
            "cryosparc",
            "phenix",
            "chimerax",
            "motioncor",
            "rosetta_pyrosetta",
            "alphafold3",
        ],
        "module_sources": {
            "campaign": str(args.campaign),
            "provider_profile": str(args.provider_profile),
            "image_modules": campaign.get("image_modules", []),
            "lane_modules": campaign.get("lane_modules", []),
            "smoke_suites": campaign.get("smoke_suites", []),
        },
    }

    args.out.parent.mkdir(parents=True, exist_ok=True)
    args.out.write_text(json.dumps(manifest, indent=2, sort_keys=True) + "\n")
    print(json.dumps({"ok": True, "out": str(args.out.resolve())}, indent=2, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
