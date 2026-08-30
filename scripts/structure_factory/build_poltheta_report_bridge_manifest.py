#!/usr/bin/env python3
"""Generate an operator-gated RunPod provider packet for the Pol theta demo."""

from __future__ import annotations

import argparse
import base64
import io
import json
import tarfile
from pathlib import Path

from public_bridge_template import make_public_bridge_template


ROOT = Path(__file__).resolve().parents[2]
RUN_ID = "bsf-demo-poltheta-map-model-report"
LINEAR_ISSUE_URL = ""


def encoded_source_bundle(files: dict[str, str]) -> str:
    buffer = io.BytesIO()
    with tarfile.open(fileobj=buffer, mode="w:gz") as archive:
        for name, text in sorted(files.items()):
            data = text.encode("utf-8")
            info = tarfile.TarInfo(name)
            info.mode = 0o644
            info.size = len(data)
            archive.addfile(info, io.BytesIO(data))
    return base64.b64encode(buffer.getvalue()).decode("ascii")


def build_manifest(runner_text: str, self_check_text: str, artifact_contract_text: str) -> dict:
    bundle_b64 = encoded_source_bundle(
        {
            "scripts/structure_factory/poltheta_map_model_report.py": runner_text,
            "scripts/structure_factory/contract_self_check.py": self_check_text,
            "modules/artifact-contracts/structure-report.v1.json": artifact_contract_text,
        }
    )
    workload_command = f"""mkdir -p scripts/structure_factory modules/artifact-contracts runpod-execution/artifacts
python3 - <<'PY'
import base64
import io
import tarfile
from pathlib import Path

root = Path(".").resolve()
payload = {bundle_b64!r}
with tarfile.open(fileobj=io.BytesIO(base64.b64decode(payload)), mode="r:gz") as archive:
    for member in archive.getmembers():
        target = (root / member.name).resolve()
        if not str(target).startswith(str(root)):
            raise RuntimeError(f"Unsafe bundle member: {{member.name}}")
    archive.extractall(root)
PY
python3 scripts/structure_factory/poltheta_map_model_report.py --out runpod-execution/artifacts --json | tee runpod-execution/artifacts/demo-summary.json
python3 scripts/structure_factory/contract_self_check.py --manifest runpod-execution/artifacts/contract-manifest.json --artifact-root runpod-execution/artifacts --execution-mode real --json | tee runpod-execution/artifacts/validation/contract-self-check.stdout.json
python3 - <<'PY'
import tarfile
from pathlib import Path
artifacts = Path('runpod-execution/artifacts')
include = [
    'demo-summary.json',
    'report.md',
    'report_manifest.json',
    'data-intake-ledger.json',
    'executed-commands.jsonl',
    'stage-progress.jsonl',
    'contract-manifest.json',
    'validation/contract-self-check.json',
    'validation/contract-self-check.stdout.json',
    'validation/map_model_fit.json',
    'map-summary.json',
    'coordinate-summary.json',
    'ligand-neighborhoods.json',
    'validation_ledger.md',
    'methods.md',
    'provenance.md',
    'figures/emd-43816-mid-slice.svg',
    'figures/model-inventory.svg',
    'figures/ampnp-neighborhood.svg',
    'figures/density-support.svg',
]
with tarfile.open(artifacts / 'runpod-execution.tar.gz', 'w:gz') as archive:
    for rel in include:
        path = artifacts / rel
        if path.is_file():
            archive.add(path, arcname=path.relative_to(artifacts))
PY
if [ -s runpod-execution/live-status.pid ]; then
  kill "$(cat runpod-execution/live-status.pid)" >/dev/null 2>&1 || true
  sleep 1
fi
"""
    return {
        "schema_version": 1,
        "manifest_kind": "symphony_runpod_launch",
        "provider": {"name": "runpod", "adapter": "runpod_pod_v1"},
        "run_id": RUN_ID,
        "compute_profile": "cpu-public-map-model-under-2h",
        "workload": {
            "scale": "small",
            "description": "Public EMDB/PDB map-model report for Pol theta helicase domain EMD-43816 / PDB 9ASJ",
            "shards": [{"shard_id": "single-map-model-report"}],
            "checkpoint_policy": {"mode": "stage-progress-jsonl"},
            "stage_contract": {
                "inputs": [
                    "EMDB EMD-43816 public map: https://ftp.ebi.ac.uk/pub/databases/emdb/structures/EMD-43816/map/emd_43816.map.gz",
                    "PDB 9ASJ public mmCIF: https://files.rcsb.org/download/9ASJ.cif",
                    "wwPDB 9ASJ validation XML/PDF from public validation report endpoints",
                ],
                "exact_commands": [
                    "python3 scripts/structure_factory/poltheta_map_model_report.py --out runpod-execution/artifacts --json",
                    "python3 scripts/structure_factory/contract_self_check.py --manifest runpod-execution/artifacts/contract-manifest.json --artifact-root runpod-execution/artifacts --execution-mode real --json",
                    "python3 inline archive rebuild for runpod-execution/artifacts/runpod-execution.tar.gz",
                ],
                "expected_outputs": [
                    "runpod-execution/status.json",
                    "runpod-execution/artifacts/demo-summary.json",
                    "runpod-execution/artifacts/report.md",
                    "runpod-execution/artifacts/report_manifest.json",
                    "runpod-execution/artifacts/data-intake-ledger.json",
                    "runpod-execution/artifacts/executed-commands.jsonl",
                    "runpod-execution/artifacts/validation/contract-self-check.json",
                    "runpod-execution/artifacts/validation/map_model_fit.json",
                    "runpod-execution/artifacts/map-summary.json",
                    "runpod-execution/artifacts/coordinate-summary.json",
                    "runpod-execution/artifacts/ligand-neighborhoods.json",
                    "runpod-execution/artifacts/validation_ledger.md",
                    "runpod-execution/artifacts/methods.md",
                    "runpod-execution/artifacts/provenance.md",
                    "runpod-execution/artifacts/figures/emd-43816-mid-slice.svg",
                    "runpod-execution/artifacts/figures/model-inventory.svg",
                    "runpod-execution/artifacts/figures/ampnp-neighborhood.svg",
                    "runpod-execution/artifacts/figures/density-support.svg",
                    "runpod-execution/artifacts/runpod-execution.tar.gz",
                ],
                "done_markers": [
                    "runpod-execution/status.json reports succeeded",
                    "runpod-execution/artifacts/validation/contract-self-check.json reports ok true",
                    "runpod-execution/artifacts/runpod-execution.tar.gz exists",
                ],
                "timeout_minutes": 120,
                "resume_policy": "Disposable demo pod. If interrupted, delete pod and relaunch the same manifest; outputs are deterministic public-data artifacts.",
                "fail_closed": True,
                "claim_level": "candidate",
            },
        },
        "remote_launch_allowed": True,
        "launch_authorization": {
            "source": "operator-chat",
            "approved_by": "PENDING-OPERATOR-GATE",
            "approved_at": "PENDING",
            "linear_issue_url": LINEAR_ISSUE_URL,
            "scope": "CPU-only public EMDB/PDB map-model demo, no licensed tools, no raw movies, target under two hours",
        },
        "budget": {"max_runtime_minutes": 120, "max_estimated_cost_usd": 1.0},
        "repo": {
            "source": "inline_commands",
            "url_or_path": "inline",
            "commit_or_snapshot": "inline:poltheta-map-model-report-v1",
            "workdir": "/workspace/repo",
        },
        "runpod": {
            "cloudType": "SECURE",
            "imageName": "python:3.12-slim",
            "templateId": "",
            "name": "bsf-demo-poltheta-map-model",
            "gpuCount": 0,
            "gpuTypeIds": [],
            "dataCenterIds": [],
            "networkVolumeId": "",
            "containerDiskInGb": 20,
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
            "commands": [
                "set -euo pipefail",
                "cd /workspace/repo",
                workload_command,
            ],
        },
        "monitoring": {
            "poll_interval_seconds": 15,
            "max_silent_minutes": 8,
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
            "python3 - <<'PY'\nimport json\nfrom pathlib import Path\nroot = Path('runpod-execution')\nbase = root / 'artifacts'\nsummary = json.loads((base / 'demo-summary.json').read_text())\ncontract = json.loads((base / 'validation' / 'contract-self-check.json').read_text())\nmanifest = json.loads((base / 'report_manifest.json').read_text())\nfit = json.loads((base / 'validation' / 'map_model_fit.json').read_text())\nledger = json.loads((base / 'data-intake-ledger.json').read_text())\nassert summary['ok'] is True\nassert contract['ok'] is True, contract['errors']\nassert manifest['pdb_id'] == '9ASJ'\nassert manifest['emdb_id'] == 'EMD-43816'\nassert ledger['raw_movies_downloaded'] is False\nassert ledger['status'] == 'downloaded'\nassert fit['ok'] is True\nassert fit['map_model_correlation']['sampled_atom_count'] > 0\nfor rel in ['report.md', 'figures/emd-43816-mid-slice.svg', 'figures/model-inventory.svg', 'figures/ampnp-neighborhood.svg', 'figures/density-support.svg', 'validation_ledger.md', 'provenance.md', 'executed-commands.jsonl', 'runpod-execution.tar.gz']:\n    assert (base / rel).is_file(), rel\nPY",
        ],
        "expected_artifacts": [
            {"artifact_id": "status", "path": "runpod-execution/status.json", "required": True, "sha256_required": True},
            {"artifact_id": "summary", "path": "runpod-execution/artifacts/demo-summary.json", "required": True, "sha256_required": True},
            {"artifact_id": "report_md", "path": "runpod-execution/artifacts/report.md", "required": True, "sha256_required": True},
            {"artifact_id": "report_manifest", "path": "runpod-execution/artifacts/report_manifest.json", "required": True, "sha256_required": True},
            {"artifact_id": "data_intake", "path": "runpod-execution/artifacts/data-intake-ledger.json", "required": True, "sha256_required": True},
            {"artifact_id": "executed_commands", "path": "runpod-execution/artifacts/executed-commands.jsonl", "required": True, "sha256_required": True},
            {"artifact_id": "contract_self_check", "path": "runpod-execution/artifacts/validation/contract-self-check.json", "required": True, "sha256_required": True},
            {"artifact_id": "map_model_fit", "path": "runpod-execution/artifacts/validation/map_model_fit.json", "required": True, "sha256_required": True},
            {"artifact_id": "map_summary", "path": "runpod-execution/artifacts/map-summary.json", "required": True, "sha256_required": True},
            {"artifact_id": "coordinate_summary", "path": "runpod-execution/artifacts/coordinate-summary.json", "required": True, "sha256_required": True},
            {"artifact_id": "ligand_neighborhoods", "path": "runpod-execution/artifacts/ligand-neighborhoods.json", "required": True, "sha256_required": True},
            {"artifact_id": "validation_ledger", "path": "runpod-execution/artifacts/validation_ledger.md", "required": True, "sha256_required": True},
            {"artifact_id": "methods", "path": "runpod-execution/artifacts/methods.md", "required": True, "sha256_required": True},
            {"artifact_id": "provenance", "path": "runpod-execution/artifacts/provenance.md", "required": True, "sha256_required": True},
            {"artifact_id": "figure_map_slice", "path": "runpod-execution/artifacts/figures/emd-43816-mid-slice.svg", "required": True, "sha256_required": True},
            {"artifact_id": "figure_inventory", "path": "runpod-execution/artifacts/figures/model-inventory.svg", "required": True, "sha256_required": True},
            {"artifact_id": "figure_ligand", "path": "runpod-execution/artifacts/figures/ampnp-neighborhood.svg", "required": True, "sha256_required": True},
            {"artifact_id": "figure_density_support", "path": "runpod-execution/artifacts/figures/density-support.svg", "required": True, "sha256_required": True},
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
            "resource_name_prefix": "bsf-demo-poltheta",
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
            "private_data_policy": "public EMDB/PDB/wwPDB validation only; no private data",
            "license_policy": "open tooling only; no CryoSPARC/Phenix/ChimeraX/MotionCor/Rosetta/AlphaFold3",
        },
    }


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--linear-issue-url", default=LINEAR_ISSUE_URL)
    parser.add_argument("--out", type=Path, default=ROOT / ".runtime" / "bridge-manifests" / "poltheta-map-model-report.json")
    args = parser.parse_args()
    runner = (ROOT / "scripts" / "structure_factory" / "poltheta_map_model_report.py").read_text()
    self_check = (ROOT / "scripts" / "structure_factory" / "contract_self_check.py").read_text()
    artifact_contract = (ROOT / "modules" / "artifact-contracts" / "structure-report.v1.json").read_text()
    manifest = make_public_bridge_template(build_manifest(runner, self_check, artifact_contract))
    if args.linear_issue_url:
        manifest["launch_authorization"]["linear_issue_url"] = args.linear_issue_url
    args.out.parent.mkdir(parents=True, exist_ok=True)
    args.out.write_text(json.dumps(manifest, indent=2, sort_keys=True) + "\n")
    print(json.dumps({"ok": True, "out": str(args.out.resolve())}, indent=2, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
