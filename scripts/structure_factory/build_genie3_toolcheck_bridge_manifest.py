#!/usr/bin/env python3
"""Build the Genie 3 no-download toolcheck bridge manifest.

Default output is a tracked template without live execution state. Materialized
manifests with inline payloads must be written below ignored ``.runtime/`` space
with ``--execution-ready --out .runtime/...`` after explicit human approval.
"""

from __future__ import annotations

import argparse
import base64
import gzip
import json
import os
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[2]
TOOLCHECK_SCRIPT = REPO_ROOT / "scripts" / "structure_factory" / "genie3_toolcheck.py"
OUTPUT = REPO_ROOT / ".runtime" / "bridge-manifests" / "genie3-no-download-toolcheck.json"
STAGE_CONTRACT = "runpod/stage-contracts/genie3-no-download-toolcheck.stage-contract.json"

RUN_ID = "structure-factory-genie3-no-download-toolcheck"
RESOURCE_PREFIX = "structure-factory-genie3-toolcheck"
POD_NAME = "structure-factory-genie3-toolcheck"
WORKDIR = "/workspace"
ARTIFACT_ROOT = "/workspace/runpod-execution/artifacts"
LOG_FILE = "/workspace/runpod-execution/logs/startup.log"
PUBLIC_TEMPLATE_NOTE = (
    "Public template only. This file documents the expected RunPod bridge-manifest "
    "shape. It is not execution-ready until a human/operator gate records current "
    "license/use context, budget, placement, a pushed public commit SHA, "
    "provider credentials by reference, and cleanup policy."
)


def gz_b64(payload: bytes) -> str:
    return base64.b64encode(gzip.compress(payload, compresslevel=9)).decode("ascii")


def build_startup_commands(encoded_script: str) -> list[str]:
    decode_pipe = f"echo '{encoded_script}' | base64 -d | gunzip > /workspace/genie3_toolcheck.py"
    return [
        "set -euo pipefail",
        "echo '[genie3-toolcheck] start' && date -u",
        "mkdir -p /workspace/runpod-execution/logs /workspace/runpod-execution/artifacts/validation /workspace/runpod-execution/artifacts/logs /workspace/runpod-execution/artifacts/source",
        "cd /workspace",
        decode_pipe,
        f"echo \"[$(date -u +%H:%M:%S)] decoded toolcheck script\" >> {LOG_FILE}",
        f"ls -la /workspace/genie3_toolcheck.py >> {LOG_FILE}",
        f"echo \"[$(date -u +%H:%M:%S)] launching toolcheck\" >> {LOG_FILE}",
        (
            "python3 /workspace/genie3_toolcheck.py "
            f"--out {ARTIFACT_ROOT} "
            f"--run-id {RUN_ID} --json "
            f">> {LOG_FILE} 2>&1 || echo 'TOOLCHECK_RUNNER_RETURNED_NONZERO' >> {LOG_FILE}"
        ),
        f"echo \"[$(date -u +%H:%M:%S)] toolcheck runner exited\" >> {LOG_FILE}",
        f"ls -la {ARTIFACT_ROOT} >> {LOG_FILE} 2>&1 || true",
        (
            "cd /workspace && tar czf "
            f"{ARTIFACT_ROOT}/runpod-execution.tar.gz "
            "runpod-execution/status.json runpod-execution/artifacts/ "
            f"2>>{LOG_FILE} || true"
        ),
        f"echo \"[$(date -u +%H:%M:%S)] archive written; sleeping 600s for pull\" >> {LOG_FILE}",
        "sleep 600",
    ]


def public_template_startup_commands() -> list[str]:
    return [
        "set -euo pipefail",
        "echo 'Tracked template has no runtime payload. Materialize an ignored runtime packet and obtain explicit human authorization before execution.'",
        "exit 64",
    ]


def build_manifest(*, execution_ready: bool = False) -> dict:
    encoded = gz_b64(TOOLCHECK_SCRIPT.read_bytes())
    startup_commands = build_startup_commands(encoded) if execution_ready else public_template_startup_commands()
    manifest = {
        "schema_version": 1,
        "manifest_kind": "symphony_runpod_launch",
        "campaign_id": "genie3-toolcheck",
        "campaign_manifest_ref": "modules/lane-modules/genie3.toolcheck.v1.json",
        "stage_contract_ref": STAGE_CONTRACT,
        "launch_manifest_ref": ".runtime/bridge-manifests/genie3-no-download-toolcheck.json",
        "wave": "T0",
        "run_id": RUN_ID,
        "shard": {"lane": "genie3", "mode": "no-download-toolcheck"},
        "remote_launch_allowed": execution_ready,
        "public_template_status": "execution_ready_runtime_packet" if execution_ready else "tracked_public_template",
        "public_template_note": PUBLIC_TEMPLATE_NOTE,
        "provider": {"name": "runpod", "adapter": "runpod_pod_v1"},
        "repo": {
            "source": "inline_commands",
            "url_or_path": "inline",
            "commit_or_snapshot": (
                "inline:genie3-no-download-toolcheck-v1"
                if execution_ready
                else "inline:public-template-no-payload"
            ),
            "commit_or_snapshot_pin_policy": (
                "Inline payloads are not published in bridge manifests. Rebuild from tracked source scripts after operator gates pass."
            ),
            "workdir": WORKDIR,
        },
        "runpod": {
            "name": POD_NAME,
            "computeType": "GPU",
            "cloudType": "SECURE",
            "gpuCount": 1,
            "gpuTypeIds": ["NVIDIA GeForce RTX 4090"],
            "vcpuCount": 4,
            "containerDiskInGb": 40,
            "volumeInGb": 0,
            "volumeMountPath": "/workspace",
            "imageName": "pytorch/pytorch:2.4.0-cuda12.4-cudnn9-runtime",
            "imageDigestRequiredForReal": True,
            "templateId": "",
            "ports": [],
            "registryAuth": {
                "required": False,
                "provider": "dockerhub",
                "policy_note": "stock_pytorch_image",
            },
            "env": {
                "STRUCTURE_FACTORY_RUN_ID": RUN_ID,
                "STRUCTURE_FACTORY_LANE": "genie3",
                "STRUCTURE_FACTORY_EXECUTION_PROFILE": "genie3-no-download-toolcheck",
                "STRUCTURE_FACTORY_GENIE3_PINNED_SHA": "5214459c42e69b01fadfc7d7ebda09d8e5082115",
            },
        },
        "compute_profile": "gpu-genie3-toolcheck-under-1h",
        "expected_artifacts": [
            {"artifact_id": "status", "path": "runpod-execution/status.json", "required": True, "sha256_required": True},
            {"artifact_id": "stage_progress", "path": "runpod-execution/artifacts/stage-progress.jsonl", "required": True, "sha256_required": True},
            {"artifact_id": "executed_commands", "path": "runpod-execution/artifacts/executed-commands.jsonl", "required": True, "sha256_required": True},
            {"artifact_id": "host_probe", "path": "runpod-execution/artifacts/validation/host_probe.json", "required": True, "sha256_required": True},
            {"artifact_id": "source_download", "path": "runpod-execution/artifacts/validation/source_download.json", "required": True, "sha256_required": True},
            {"artifact_id": "dependency_review", "path": "runpod-execution/artifacts/validation/dependency_review.json", "required": True, "sha256_required": True},
            {"artifact_id": "pip_install", "path": "runpod-execution/artifacts/validation/pip_install.json", "required": True, "sha256_required": True},
            {"artifact_id": "smoke_commands", "path": "runpod-execution/artifacts/validation/smoke_commands.json", "required": True, "sha256_required": True},
            {"artifact_id": "hf_weights_probe", "path": "runpod-execution/artifacts/validation/hf_weights_probe.json", "required": True, "sha256_required": True},
            {"artifact_id": "versions", "path": "runpod-execution/artifacts/versions.json", "required": True, "sha256_required": True},
            {"artifact_id": "validation_ledger", "path": "runpod-execution/artifacts/validation_ledger.json", "required": True, "sha256_required": True},
            {"artifact_id": "report_md", "path": "runpod-execution/artifacts/genie3_toolcheck_report.md", "required": True, "sha256_required": True},
            {"artifact_id": "artifact_index", "path": "runpod-execution/artifacts/artifact_index.json", "required": True, "sha256_required": True},
            {"artifact_id": "artifact_archive", "path": "runpod-execution/artifacts/runpod-execution.tar.gz", "required": True, "sha256_required": True},
        ],
        "validation_commands": [
            "python3 -m json.tool /workspace/runpod-execution/status.json >/dev/null",
            "test -f /workspace/runpod-execution/artifacts/validation_ledger.json",
            "test -f /workspace/runpod-execution/artifacts/genie3_toolcheck_report.md",
            "test -f /workspace/runpod-execution/artifacts/validation/host_probe.json",
            "test -f /workspace/runpod-execution/artifacts/validation/source_download.json",
            "test -f /workspace/runpod-execution/artifacts/validation/smoke_commands.json",
        ],
        "license_gates": [],
        "launch_authorization": {
            "approved_at": "PENDING",
            "approved_by": "PENDING-OPERATOR-GATE",
            "linear_issue_url": "PENDING-TRACKER-ISSUE",
            "scope": PUBLIC_TEMPLATE_NOTE
            if not execution_ready
            else "Genie 3 no-download toolcheck. Source archive at pinned SHA, pip install attempt, smoke commands, HF weights revision HEAD probe. No weights download, no inference, no design output.",
            "source": "templates/operator-wave-runbook.md",
        },
        "safety": {
            "license_policy": "Genie 3 source review only; pip install of public source; no weights, no inference, no design output. ColabFold/AlphaFold2/IPSAE/etc are dependency-review evidence only.",
            "no_literal_secrets": True,
            "private_data_policy": "no private data; toolcheck targets public source and HF revision",
            "public_template_policy": "No secrets, concrete provider resources, private volume assumptions, prior-run artifacts, or accepted-license state are encoded in this public manifest.",
        },
        "access": {
            "ssh_required": False,
            "ssh_public_key_ref": "",
            "tcp_ports_required": False,
            "http_proxy_required": False,
            "public_services_require_auth": False,
            "full_ssh_scp_required": False,
        },
        "artifact_egress": {
            "mode": "workspace_archive",
            "archive_path": "runpod-execution/artifacts/runpod-execution.tar.gz",
            "requires_network_volume": False,
            "requires_object_store_upload": False,
            "requires_scp": False,
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
            "required_signals": [
                "provider_actual_status",
                "runtime_uptime_seconds",
                "image_pull_success_or_failure",
                "stage_progress_heartbeat",
            ],
            "requires_log_artifact": True,
            "requires_status_file": True,
            "requires_workload_heartbeat": True,
        },
        "budget": {
            "max_estimated_cost_usd": 2.0,
            "max_runtime_minutes": 50,
            "terminate_after_minutes": 60,
        },
        "closeout": {
            "stop_or_delete_pod": True,
            "retain_pod": False,
            "delete_pod_if_network_volume_attached": False,
            "linear_outcome_required": True,
            "prefer_billing_api_cost": True,
            "record_artifact_hashes": True,
            "record_cost_estimate": True,
            "record_runtime_minutes": True,
        },
        "worker_coordination": {
            "resource_name_prefix": RESOURCE_PREFIX,
            "single_mutating_worker": True,
            "read_only_monitors_allowed": True,
            "linear_issue_lock_required": True,
        },
        "workload": {
            "scale": "small",
            "description": "Genie 3 no-download toolcheck on stock pytorch GPU pod (RTX 4090). Tests source download, pip install, smoke commands, HF revision resolution.",
            "shards": [{"shard_id": "genie3-toolcheck-shard-1"}],
            "checkpoint_policy": {"mode": "stage-progress-jsonl"},
            "stage_contract": {
                "claim_level": "candidate",
                "fail_closed": True,
                "timeout_minutes": 60,
                "exact_commands": [
                    f"python3 /workspace/genie3_toolcheck.py --out {ARTIFACT_ROOT} --run-id {RUN_ID} --json"
                ],
                "expected_outputs": [
                    "runpod-execution/status.json",
                    "runpod-execution/artifacts/stage-progress.jsonl",
                    "runpod-execution/artifacts/executed-commands.jsonl",
                    "runpod-execution/artifacts/validation/host_probe.json",
                    "runpod-execution/artifacts/validation/source_download.json",
                    "runpod-execution/artifacts/validation/dependency_review.json",
                    "runpod-execution/artifacts/validation/pip_install.json",
                    "runpod-execution/artifacts/validation/smoke_commands.json",
                    "runpod-execution/artifacts/validation/hf_weights_probe.json",
                    "runpod-execution/artifacts/versions.json",
                    "runpod-execution/artifacts/validation_ledger.json",
                    "runpod-execution/artifacts/genie3_toolcheck_report.md",
                    "runpod-execution/artifacts/artifact_index.json",
                    "runpod-execution/artifacts/runpod-execution.tar.gz",
                ],
                "done_markers": [
                    "runpod-execution/status.json reports completed or completed_partial",
                    "runpod-execution/artifacts/validation_ledger.json exists",
                    "runpod-execution/artifacts/genie3_toolcheck_report.md exists",
                    "runpod-execution/artifacts/runpod-execution.tar.gz exists",
                ],
                "inputs": [
                    "Toolcheck Python script embedded inline (gzip+base64) — no fetch required",
                    "Genie 3 source archive fetched at runtime from GitHub at the lane-pinned SHA",
                    "HuggingFace API HEAD-equivalent probe of the lane-pinned weights revision",
                ],
                "resume_policy": "Disposable toolcheck pod. If interrupted, just relaunch; no persistent state, no NV. Re-run is idempotent: a fresh archive fetch and pip install attempt.",
                "route_proof": {
                    "tool_invocation": [
                        f"python3 /workspace/genie3_toolcheck.py --out {ARTIFACT_ROOT} --run-id {RUN_ID} --json"
                    ],
                    "input_materialization": [
                        "Genie 3 source archive at pinned SHA fetched via urllib.request and hashed (sha256)",
                    ],
                    "artifact_validation": [
                        "validation_commands check status.json + validation_ledger.json + report.md + per-stage validation/*.json"
                    ],
                    "claim_boundaries": [
                        "claim_level cap is candidate; downgrades to insufficient_evidence on smoke failure or source/install failure"
                    ],
                },
            },
        },
        "startup": {
            "mode": "dockerStartCmd",
            "log_file": "runpod-execution/logs/startup.log",
            "status_file": "runpod-execution/status.json",
            "heartbeat_file": "runpod-execution/logs/startup.log",
            "inspection": {
                "hold_after_success_seconds": 600 if execution_ready else 0,
            },
            "commands": startup_commands,
        },
    }
    if not execution_ready:
        manifest["validation_commands"] = [
            "python3 scripts/structure_factory/runpod_public_template_check.py runpod/bridge-manifests --json",
        ]
        manifest["workload"]["stage_contract"]["claim_level"] = "planning"
        manifest["workload"]["stage_contract"]["exact_commands"] = []
        manifest["workload"]["stage_contract"]["expected_outputs"] = []
        manifest["workload"]["stage_contract"]["inputs"] = [
            "Public template only; no inline payload is published.",
        ]
        manifest["workload"]["stage_contract"]["route_proof"]["tool_invocation"] = []
        manifest["workload"]["stage_contract"]["route_proof"]["input_materialization"] = [
            "Execution-ready payload materialization must happen outside public git after operator authorization.",
        ]
        manifest["workload"]["stage_contract"]["route_proof"]["claim_boundaries"] = [
            "Public template result boundary is planning; provider execution evidence is unavailable.",
        ]
    return manifest


def assert_execution_ready_output(path: Path) -> None:
    resolved = path.resolve()
    try:
        resolved.relative_to(REPO_ROOT.resolve())
    except ValueError:
        return
    try:
        resolved.relative_to((REPO_ROOT / ".runtime").resolve())
    except ValueError as exc:
        raise SystemExit("--execution-ready output must be outside public git or under .runtime/") from exc

    gate = os.environ.get("STRUCTURE_FACTORY_OPERATOR_GATE_ACK")
    if gate != "I_UNDERSTAND_THIS_WRITES_RUNTIME_EXECUTION_STATE":
        raise SystemExit(
            "Set STRUCTURE_FACTORY_OPERATOR_GATE_ACK=I_UNDERSTAND_THIS_WRITES_RUNTIME_EXECUTION_STATE "
            "before writing an execution-ready packet."
        )


def main() -> int:
    ap = argparse.ArgumentParser(description="Build the Genie 3 no-download toolcheck bridge manifest")
    ap.add_argument("--out", type=Path, default=OUTPUT)
    ap.add_argument(
        "--execution-ready",
        action="store_true",
        help="write a runtime execution packet with inline startup payload; output must be under .runtime/ or outside the repo",
    )
    ap.add_argument("--json", action="store_true")
    args = ap.parse_args()

    if args.execution_ready:
        assert_execution_ready_output(args.out)

    manifest = build_manifest(execution_ready=args.execution_ready)
    args.out.parent.mkdir(parents=True, exist_ok=True)
    args.out.write_text(json.dumps(manifest, indent=2, sort_keys=True) + "\n")

    summary = {
        "ok": True,
        "manifest_path": str(args.out),
        "run_id": manifest["run_id"],
        "campaign_id": manifest["campaign_id"],
        "image": manifest["runpod"]["imageName"],
        "gpu": manifest["runpod"]["gpuTypeIds"],
        "max_estimated_cost_usd": manifest["budget"]["max_estimated_cost_usd"],
        "expected_artifact_count": len(manifest["expected_artifacts"]),
        "startup_command_count": len(manifest["startup"]["commands"]),
        "remote_launch_allowed": manifest["remote_launch_allowed"],
        "public_template_status": manifest["public_template_status"],
    }
    if args.json:
        print(json.dumps(summary, indent=2, sort_keys=True))
    else:
        print(f"wrote {args.out}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
