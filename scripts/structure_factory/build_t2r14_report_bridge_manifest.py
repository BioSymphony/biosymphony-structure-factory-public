#!/usr/bin/env python3
"""Generate an operator-gated RunPod provider packet for the T2R14 open demo."""

from __future__ import annotations

import argparse
import json
from pathlib import Path

from public_bridge_template import make_public_bridge_template


ROOT = Path(__file__).resolve().parents[2]
RUN_ID = "bsf-demo-t2r14-structure-report"
LINEAR_ISSUE_URL = "PENDING-TRACKER-ISSUE"


def build_manifest(script_text: str) -> dict:
    workload_command = f"""mkdir -p runpod-execution/artifacts
cat > /tmp/t2r14_structure_report.py <<'PY'
{script_text}
PY
python3 /tmp/t2r14_structure_report.py --out runpod-execution --json | tee runpod-execution/artifacts/demo-summary.json
"""
    return {
        "schema_version": 1,
        "manifest_kind": "symphony_runpod_launch",
        "provider": {"name": "runpod", "adapter": "runpod_pod_v1"},
        "run_id": RUN_ID,
        "compute_profile": "cpu-public-open-tools-under-1h",
        "workload": {
            "scale": "small",
            "description": "Public PDB/EMDB open-tool report for 2026 T2R14 cryo-EM structure",
            "shards": [{"shard_id": "single-report"}],
            "checkpoint_policy": {"mode": "stage-progress-jsonl"},
        },
        "remote_launch_allowed": True,
        "launch_authorization": {
            "source": "operator-chat",
            "approved_by": "PENDING-OPERATOR-GATE",
            "approved_at": "PENDING",
            "linear_issue_url": LINEAR_ISSUE_URL,
            "scope": "CPU-only public data demo, no licensed tools, target under one hour",
        },
        "budget": {"max_runtime_minutes": 45, "max_estimated_cost_usd": 0.5},
        "repo": {
            "source": "inline_commands",
            "url_or_path": "inline",
            "commit_or_snapshot": "inline:t2r14-structure-report-v1",
            "workdir": "/workspace/repo",
        },
        "runpod": {
            "cloudType": "SECURE",
            "imageName": "python:3.12-slim",
            "templateId": "",
            "name": "bsf-demo-t2r14-structure-report",
            "gpuCount": 0,
            "gpuTypeIds": [],
            "dataCenterIds": [],
            "networkVolumeId": "",
            "containerDiskInGb": 10,
            "volumeInGb": 0,
            "volumeMountPath": "/workspace",
            "ports": [],
            "env": {"STRUCTURE_FACTORY_RUN_ID": RUN_ID},
        },
        "access": {
            "ssh_required": False,
            "full_ssh_scp_required": False,
            "http_proxy_required": False,
            "tcp_ports_required": False,
            "ssh_public_key_ref": "",
            "public_services_require_auth": False,
        },
        "startup": {
            "mode": "dockerStartCmd",
            "log_file": "runpod-execution/logs/startup.log",
            "status_file": "runpod-execution/status.json",
            "heartbeat_file": "runpod-execution/monitor_events.ndjson",
            "inspection": {"hold_after_success_seconds": 600},
            "commands": ["set -euo pipefail", "cd /workspace/repo", workload_command],
        },
        "monitoring": {
            "poll_interval_seconds": 15,
            "max_silent_minutes": 5,
            "record_pod_fields": [
                "id",
                "desiredStatus",
                "lastStartedAt",
                "lastStatusChange",
                "costPerHr",
                "adjustedCostPerHr",
                "machine.dataCenterId",
                "portMappings",
            ],
            "requires_workload_heartbeat": True,
            "requires_status_file": True,
            "requires_log_artifact": True,
        },
        "validation_commands": [
            "python3 -m json.tool runpod-execution/status.json >/dev/null",
            "python3 - <<'PY'\nimport json\nfrom pathlib import Path\nbase = Path('runpod-execution/artifacts')\nstatus = json.loads(Path('runpod-execution/status.json').read_text())\nmanifest = json.loads((base / 'report_manifest.json').read_text())\nsummary = json.loads((base / 'coordinate-summary.json').read_text())\nassert status['ok'] is True\nassert manifest['pdb_id'] == '9W0Q'\nassert manifest['raw_data_downloaded'] is False\nassert manifest['license_gated_tools_used'] == []\nassert summary['metadata']['resolution_angstrom'] == 3.2\nfor rel in ['report.md', 'figures/interchain-contact-heatmap.svg', 'figures/chain-residue-inventory.svg', 'figures/ligand-neighborhoods.svg', 'validation_ledger.md', 'provenance.md']:\n    assert (base / rel).is_file(), rel\nPY",
        ],
        "expected_artifacts": [
            {"artifact_id": "status", "path": "runpod-execution/status.json", "required": True, "sha256_required": True},
            {"artifact_id": "summary", "path": "runpod-execution/artifacts/demo-summary.json", "required": True, "sha256_required": True},
            {"artifact_id": "report_md", "path": "runpod-execution/artifacts/report.md", "required": True, "sha256_required": True},
            {"artifact_id": "report_manifest", "path": "runpod-execution/artifacts/report_manifest.json", "required": True, "sha256_required": True},
            {"artifact_id": "coordinate_summary", "path": "runpod-execution/artifacts/coordinate-summary.json", "required": True, "sha256_required": True},
            {"artifact_id": "contact_matrix", "path": "runpod-execution/artifacts/interchain-contact-matrix.json", "required": True, "sha256_required": True},
            {"artifact_id": "ligand_neighborhoods", "path": "runpod-execution/artifacts/ligand-neighborhoods.json", "required": True, "sha256_required": True},
            {"artifact_id": "validation_ledger", "path": "runpod-execution/artifacts/validation_ledger.md", "required": True, "sha256_required": True},
            {"artifact_id": "methods", "path": "runpod-execution/artifacts/methods.md", "required": True, "sha256_required": True},
            {"artifact_id": "provenance", "path": "runpod-execution/artifacts/provenance.md", "required": True, "sha256_required": True},
            {"artifact_id": "figure_contacts", "path": "runpod-execution/artifacts/figures/interchain-contact-heatmap.svg", "required": True, "sha256_required": True},
            {"artifact_id": "figure_inventory", "path": "runpod-execution/artifacts/figures/chain-residue-inventory.svg", "required": True, "sha256_required": True},
            {"artifact_id": "figure_ligands", "path": "runpod-execution/artifacts/figures/ligand-neighborhoods.svg", "required": True, "sha256_required": True},
            {"artifact_id": "artifact_archive", "path": "runpod-execution/artifacts/runpod-execution.tar.gz", "required": True, "sha256_required": True},
        ],
        "artifact_egress": {
            "mode": "workspace_archive",
            "archive_path": "runpod-execution/artifacts/runpod-execution.tar.gz",
            "requires_network_volume": False,
            "requires_scp": False,
            "requires_object_store_upload": False,
        },
        "worker_coordination": {
            "linear_issue_lock_required": True,
            "single_mutating_worker": True,
            "read_only_monitors_allowed": True,
            "resource_name_prefix": "bsf-demo-t2r14",
        },
        "closeout": {
            "record_runtime_minutes": True,
            "record_cost_estimate": True,
            "prefer_billing_api_cost": True,
            "record_artifact_hashes": True,
            "stop_or_delete_pod": True,
            "delete_pod_if_network_volume_attached": True,
            "linear_outcome_required": True,
            "retain_pod": False,
        },
        "safety": {
            "no_literal_secrets": True,
            "private_data_policy": "public PDB/EMDB only; no private data",
            "license_policy": "open tooling only; no CryoSPARC/Phenix/ChimeraX/MotionCor/Rosetta/AlphaFold3",
        },
    }


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--out", type=Path, default=ROOT / ".runtime" / "bridge-manifests" / "t2r14-structure-report.json")
    args = parser.parse_args()
    script = (ROOT / "scripts" / "structure_factory" / "t2r14_structure_report.py").read_text()
    manifest = make_public_bridge_template(build_manifest(script))
    args.out.parent.mkdir(parents=True, exist_ok=True)
    args.out.write_text(json.dumps(manifest, indent=2, sort_keys=True) + "\n")
    print(json.dumps({"ok": True, "out": str(args.out.resolve())}, indent=2, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
