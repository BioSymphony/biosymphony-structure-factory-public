#!/usr/bin/env python3
"""Generate an operator-gated RunPod provider packet for the two-target demo."""

from __future__ import annotations

import argparse
import base64
import io
import json
import tarfile
from pathlib import Path

from public_bridge_template import make_public_bridge_template


ROOT = Path(__file__).resolve().parents[2]
RUN_ID = "bsf-demo-dual-structure-comparison"
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


def build_manifest(files: dict[str, str]) -> dict:
    bundle_b64 = encoded_source_bundle(files)
    workload_command = f"""mkdir -p scripts/structure_factory runpod-execution/artifacts
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
python3 scripts/structure_factory/dual_structure_comparison.py --out runpod-execution --json | tee runpod-execution/artifacts/campaign-summary.stdout.json
"""
    return {
        "schema_version": 1,
        "manifest_kind": "symphony_runpod_launch",
        "provider": {"name": "runpod", "adapter": "runpod_pod_v1"},
        "run_id": RUN_ID,
        "compute_profile": "cpu-public-structure-ranking-under-2h",
        "workload": {
            "scale": "small",
            "description": "Two-target public deposited-structure comparison for T2R14 and pol theta",
            "shards": [{"shard_id": "dual-public-report"}],
            "checkpoint_policy": {"mode": "stage-progress-jsonl"},
            "stage_contract": {
                "inputs": [
                    "PDB 9W0Q public mmCIF and RCSB metadata",
                    "PDB 9ASJ public mmCIF",
                    "EMDB EMD-43816 public deposited map",
                    "wwPDB public validation XML for 9ASJ",
                ],
                "exact_commands": [
                    "python3 scripts/structure_factory/dual_structure_comparison.py --out runpod-execution --json",
                ],
                "expected_outputs": [
                    "runpod-execution/status.json",
                    "runpod-execution/artifacts/campaign-summary.json",
                    "runpod-execution/artifacts/report.md",
                    "runpod-execution/artifacts/report_manifest.json",
                    "runpod-execution/artifacts/validation/contract-self-check.json",
                    "runpod-execution/artifacts/validation/map_model_fit.json",
                    "runpod-execution/artifacts/validation/stage-contract-check.json",
                    "runpod-execution/artifacts/figures/evidence-matrix.svg",
                    "runpod-execution/artifacts/figures/maturity-ladder.svg",
                    "runpod-execution/artifacts/targets/t2r14/artifacts/report.md",
                    "runpod-execution/artifacts/targets/t2r14/artifacts/figures/ligand-neighborhoods.svg",
                    "runpod-execution/artifacts/targets/poltheta/artifacts/report.md",
                    "runpod-execution/artifacts/targets/poltheta/artifacts/figures/density-support.svg",
                    "runpod-execution/artifacts/validation_ledger.md",
                    "runpod-execution/artifacts/methods.md",
                    "runpod-execution/artifacts/provenance.md",
                    "runpod-execution/artifacts/runpod-execution.tar.gz",
                ],
                "done_markers": [
                    "runpod-execution/status.json reports completed",
                    "runpod-execution/artifacts/validation/contract-self-check.json reports ok true",
                    "runpod-execution/artifacts/runpod-execution.tar.gz exists",
                ],
                "timeout_minutes": 120,
                "resume_policy": "Disposable demo pod. If interrupted, delete pod and relaunch the same manifest; public-data outputs are deterministic enough for demo comparison.",
                "fail_closed": True,
                "claim_level": "candidate",
                "route_proof": {
                    "input_materialization": [
                        "runpod-execution/artifacts/data-intake-ledger.json joins PDB 9W0Q, PDB 9ASJ, EMDB EMD-43816, and wwPDB validation XML materialized files with bytes and sha256",
                        "runpod-execution/artifacts/validation/input-audit.json records no missing operator items before target report execution",
                    ],
                    "tool_invocation": [
                        "python3 scripts/structure_factory/dual_structure_comparison.py --out runpod-execution --json",
                        "runpod-execution/artifacts/executed-commands.jsonl records campaign_input_audit, t2r14_report, poltheta_report, campaign_join, validation_review, and archive stages",
                    ],
                    "artifact_validation": [
                        "validation command reads runpod-execution/status.json, runpod-execution/artifacts/campaign-summary.json, runpod-execution/artifacts/validation/contract-self-check.json, runpod-execution/artifacts/report_manifest.json, and runpod-execution/artifacts/data-intake-ledger.json",
                        "expected artifacts include runpod-execution/artifacts/report.md, runpod-execution/artifacts/figures/evidence-matrix.svg, runpod-execution/artifacts/targets/poltheta/artifacts/validation/map_model_fit.json, and runpod-execution/artifacts/runpod-execution.tar.gz",
                    ],
                    "claim_boundaries": [
                        "runpod-execution/artifacts/validation_ledger.md must include insufficient_evidence boundaries for final mechanism and publication-ready validation",
                        "campaign result boundary remains candidate for deposited public-data report evidence; raw reconstruction and licensed-tool refinement are out of scope",
                    ],
                },
            },
        },
        "remote_launch_allowed": True,
        "launch_authorization": {
            "source": "operator-chat",
            "approved_by": "PENDING-OPERATOR-GATE",
            "approved_at": "PENDING",
            "linear_issue_url": LINEAR_ISSUE_URL,
            "scope": "CPU-only dual public PDB/EMDB structure comparison, no licensed tools, no raw movies, target under two hours",
        },
        "budget": {"max_runtime_minutes": 120, "max_estimated_cost_usd": 1.5},
        "repo": {
            "source": "inline_commands",
            "url_or_path": "inline",
            "commit_or_snapshot": "inline:dual-structure-comparison-v1",
            "workdir": "/workspace/repo",
        },
        "runpod": {
            "cloudType": "SECURE",
            "imageName": "python:3.12-slim",
            "templateId": "",
            "name": "bsf-demo-structure-ranking",
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
            "max_silent_minutes": 10,
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
            "python3 - <<'PY'\nimport json\nfrom pathlib import Path\nroot = Path('runpod-execution')\nbase = root / 'artifacts'\nstatus = json.loads((root / 'status.json').read_text())\nsummary = json.loads((base / 'campaign-summary.json').read_text())\ncontract = json.loads((base / 'validation' / 'contract-self-check.json').read_text())\nmanifest = json.loads((base / 'report_manifest.json').read_text())\nledger = json.loads((base / 'data-intake-ledger.json').read_text())\nassert status['ok'] is True\nassert summary['ok'] is True\nassert summary['target_count'] == 2\nassert contract['ok'] is True, contract['errors']\nassert manifest['raw_data_downloaded'] is False\nassert manifest['license_gated_tools_used'] == []\nassert ledger['raw_movies_downloaded'] is False\nfor rel in ['report.md', 'figures/evidence-matrix.svg', 'figures/maturity-ladder.svg', 'targets/t2r14/artifacts/report.md', 'targets/poltheta/artifacts/report.md', 'targets/poltheta/artifacts/validation/map_model_fit.json', 'runpod-execution.tar.gz']:\n    assert (base / rel).is_file(), rel\nPY",
        ],
        "expected_artifacts": [
            {"artifact_id": "status", "path": "runpod-execution/status.json", "required": True, "sha256_required": True},
            {"artifact_id": "campaign_summary", "path": "runpod-execution/artifacts/campaign-summary.json", "required": True, "sha256_required": True},
            {"artifact_id": "report_md", "path": "runpod-execution/artifacts/report.md", "required": True, "sha256_required": True},
            {"artifact_id": "report_manifest", "path": "runpod-execution/artifacts/report_manifest.json", "required": True, "sha256_required": True},
            {"artifact_id": "data_intake", "path": "runpod-execution/artifacts/data-intake-ledger.json", "required": True, "sha256_required": True},
            {"artifact_id": "executed_commands", "path": "runpod-execution/artifacts/executed-commands.jsonl", "required": True, "sha256_required": True},
            {"artifact_id": "contract_self_check", "path": "runpod-execution/artifacts/validation/contract-self-check.json", "required": True, "sha256_required": True},
            {"artifact_id": "map_model_fit", "path": "runpod-execution/artifacts/validation/map_model_fit.json", "required": True, "sha256_required": True},
            {"artifact_id": "stage_contract_check", "path": "runpod-execution/artifacts/validation/stage-contract-check.json", "required": True, "sha256_required": True},
            {"artifact_id": "figure_evidence_matrix", "path": "runpod-execution/artifacts/figures/evidence-matrix.svg", "required": True, "sha256_required": True},
            {"artifact_id": "figure_maturity_ladder", "path": "runpod-execution/artifacts/figures/maturity-ladder.svg", "required": True, "sha256_required": True},
            {"artifact_id": "t2r14_report", "path": "runpod-execution/artifacts/targets/t2r14/artifacts/report.md", "required": True, "sha256_required": True},
            {"artifact_id": "t2r14_ligand_figure", "path": "runpod-execution/artifacts/targets/t2r14/artifacts/figures/ligand-neighborhoods.svg", "required": True, "sha256_required": True},
            {"artifact_id": "poltheta_report", "path": "runpod-execution/artifacts/targets/poltheta/artifacts/report.md", "required": True, "sha256_required": True},
            {"artifact_id": "poltheta_density_figure", "path": "runpod-execution/artifacts/targets/poltheta/artifacts/figures/density-support.svg", "required": True, "sha256_required": True},
            {"artifact_id": "validation_ledger", "path": "runpod-execution/artifacts/validation_ledger.md", "required": True, "sha256_required": True},
            {"artifact_id": "methods", "path": "runpod-execution/artifacts/methods.md", "required": True, "sha256_required": True},
            {"artifact_id": "provenance", "path": "runpod-execution/artifacts/provenance.md", "required": True, "sha256_required": True},
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
            "resource_name_prefix": "bsf-demo-structure-ranking",
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
            "raw_data_policy": "no raw movies or particle stacks",
        },
    }


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--out", type=Path, default=ROOT / ".runtime" / "bridge-manifests" / "dual-structure-comparison.json")
    args = parser.parse_args()
    files = {
        "scripts/structure_factory/dual_structure_comparison.py": (ROOT / "scripts" / "structure_factory" / "dual_structure_comparison.py").read_text(),
        "scripts/structure_factory/t2r14_structure_report.py": (ROOT / "scripts" / "structure_factory" / "t2r14_structure_report.py").read_text(),
        "scripts/structure_factory/poltheta_map_model_report.py": (ROOT / "scripts" / "structure_factory" / "poltheta_map_model_report.py").read_text(),
    }
    manifest = make_public_bridge_template(build_manifest(files))
    args.out.parent.mkdir(parents=True, exist_ok=True)
    args.out.write_text(json.dumps(manifest, indent=2, sort_keys=True) + "\n")
    print(json.dumps({"ok": True, "out": str(args.out.resolve())}, indent=2, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
