#!/usr/bin/env python3
"""Emit inert provider launch packets for Structure Factory dry-runs.

This adapter spine is intentionally stdlib-only and side-effect-light: it reads
a screening manifest or provider run spec, writes JSON packets, and never calls
provider APIs, shells out to cloud CLIs, reads secrets, or launches compute.
"""

from __future__ import annotations

import argparse
import hashlib
import json
from datetime import datetime, timezone
from pathlib import Path
from typing import Any


REPO_ROOT = Path(__file__).resolve().parents[2]

ADAPTER_PROFILE_PATHS = {
    "local_workstation_v1": "modules/provider-profiles/local/workstation-no-download.v1.json",
    "runpod_pod_v1": "modules/provider-profiles/runpod/pod-no-download.v1.json",
    "aws_batch_v1": "modules/provider-profiles/aws/aws-batch-gpu-no-download.v1.json",
    "neocloud_gpu_pod_v1": "modules/provider-profiles/neocloud/gpu-pod-no-download.v1.json",
}

DEFAULT_ADAPTERS = list(ADAPTER_PROFILE_PATHS)

CANONICAL_LIFECYCLE_STATES = [
    {
        "state": "packet_created",
        "terminal": False,
        "meaning": "Dry-run launch packet exists; no provider action has been taken.",
    },
    {
        "state": "preflight_pending",
        "terminal": False,
        "meaning": "Input, repo, provider scope, license, and budget checks still need to run.",
    },
    {
        "state": "preflight_passed",
        "terminal": False,
        "meaning": "All declared preflight checks passed for the selected provider profile.",
    },
    {
        "state": "operator_gate_pending",
        "terminal": False,
        "meaning": "Human approval is required before paid or provider-mutating execution.",
    },
    {
        "state": "launch_authorized",
        "terminal": False,
        "meaning": "Operator approved a bounded provider launch with budget and cleanup policy.",
    },
    {
        "state": "submitted",
        "terminal": False,
        "meaning": "Provider accepted a job or pod request; this is intent only, not success.",
    },
    {
        "state": "provider_starting",
        "terminal": False,
        "meaning": "Provider is allocating runtime; uptime and workload heartbeat are not yet proof.",
    },
    {
        "state": "provider_running",
        "terminal": False,
        "meaning": "Runtime appears active; scientific success still requires artifacts and checks.",
    },
    {
        "state": "artifact_exporting",
        "terminal": False,
        "meaning": "Artifacts are being exported or pulled from provider storage.",
    },
    {
        "state": "artifact_verifying",
        "terminal": False,
        "meaning": "Required artifacts are parsed, hashed, and joined to manifest/provenance.",
    },
    {
        "state": "cleanup_pending",
        "terminal": False,
        "meaning": "Provider job, pod, scratch, or temporary storage cleanup still needs proof.",
    },
    {
        "state": "cleanup_verified",
        "terminal": False,
        "meaning": "Provider cleanup proof exists and is linked to the run.",
    },
    {
        "state": "closeout_ready",
        "terminal": True,
        "meaning": "Artifacts, checks, cost report, cleanup proof, and validation ledger are sufficient.",
    },
    {
        "state": "closed_partial",
        "terminal": True,
        "meaning": "Run closed with explicit partial/degraded evidence and downgraded claims.",
    },
    {
        "state": "closed_blocked",
        "terminal": True,
        "meaning": "Run cannot proceed until missing authorization, capability, input, or license gate is resolved.",
    },
    {
        "state": "closed_failed",
        "terminal": True,
        "meaning": "Required run evidence failed validation and cannot support the requested claim.",
    },
]

INTENT_ONLY_STATES = [
    "submitted",
    "provider_starting",
    "provider_running",
]

COMMON_REQUIRED_ARTIFACTS = [
    "screening_manifest.json",
    "validation/input-audit.json",
    "validation/contract-self-check.json",
    "stage-progress.jsonl",
    "executed-commands.jsonl",
    "validation_ledger.json",
    "provenance.md",
]

PROVIDER_CLOSEOUT_ARTIFACTS = [
    "validation/artifact-pull-report.json",
    "cost_report.json",
    "cleanup_proof.json",
]

CLOUD_SHARD_LEDGER_EXAMPLE = "examples/screening-superpowers/cloud-shard-ledger.example.json"
CLOUD_SHARD_LEDGER_VALIDATOR = (
    "python3 scripts/structure_factory/provider_closeout_check.py "
    "--shard-ledger <ledger> --execution-mode prep --json"
)

LOCAL_PREP_ARTIFACTS = [
    "ligand_prep.jsonl",
    "pose_predictions.jsonl",
    "affinity_predictions.jsonl",
    "consensus_ranking.csv",
    "metrics.json",
    "method_summary.json",
    "failure_report.json",
]

CLOSEOUT_REQUIREMENTS = [
    {
        "id": "manifest_and_inputs_hashed",
        "required": True,
        "description": "Source manifest, ligand library, receptor ensemble, stage contract, and code ref are hash-joined.",
    },
    {
        "id": "input_audit_passed",
        "required": True,
        "description": "Input audit proves no private data, no secrets, and no unauthorized raw or large downloads.",
    },
    {
        "id": "required_artifacts_present",
        "required": True,
        "description": "Every required artifact is present, non-empty when applicable, parsed when structured, and recorded in a hash ledger.",
    },
    {
        "id": "stage_progress_terminal",
        "required": True,
        "description": "Progress ledger has terminal events for required stages; timeouts write partial-summary.json.",
    },
    {
        "id": "contract_self_check_passed",
        "required": True,
        "description": "Contract self-check passes for the declared source posture and result boundary.",
    },
    {
        "id": "cost_report_checked",
        "required_for_paid_provider": True,
        "description": "Actual provider rate, runtime, GPU allocation, and total spend are checked against budget.",
    },
    {
        "id": "cleanup_proof_checked",
        "required_for_paid_provider": True,
        "description": "Provider job/pod termination and scratch or temporary storage cleanup are proven.",
    },
    {
        "id": "claim_level_downgraded_when_needed",
        "required": True,
        "description": "Fixture, dry-run, fallback, or partial evidence cannot be closed as validated or publishable.",
    },
]

PROVIDER_GATE_CATALOG = {
    "local_workstation_v1": {
        "cost_gates": [
            "max_spend_usd must be 0 for this no-paid dry-run",
            "no raw cryo-EM or large external downloads",
            "local high-resource execution needs a separate operator issue before use",
        ],
        "cleanup_gates": [
            "record local artifact root before execution",
            "write cleanup_proof.json for any retained .runtime artifacts",
            "do not delete user data outside the declared artifact root",
        ],
        "operator_gates": [
            "not required for packet generation",
            "required before local heavy compute or raw data materialization",
        ],
    },
    "runpod_pod_v1": {
        "cost_gates": [
            "explicit operator launch approval",
            "max_spend_usd and max_runtime_minutes declared before pod create",
            "post-create provider rate and GPU allocation must match budget",
            "provider_start_plateau must trigger delete/retry/escalate, not success",
        ],
        "cleanup_gates": [
            "delete pod or prove intended stopped terminal state",
            "verify Structure Factory-scoped Network Volume only",
            "export and hash small artifacts before closeout",
            "write cleanup_proof.json with provider object identifiers",
        ],
        "operator_gates": [
            "RunPod API key and Network Volume are not required for dry-run",
            "real pod launch requires human/operator gate issue",
        ],
    },
    "aws_batch_v1": {
        "cost_gates": [
            "explicit operator launch approval",
            "AWS account and region allowlist",
            "AWS Budget or equivalent alarm configured",
            "Batch GPU quota and requested instance family checked before submit",
            "actual job runtime and EC2/GPU class reconciled in cost_report.json",
        ],
        "cleanup_gates": [
            "Batch job reaches terminal state",
            "temporary EBS/EFS/scratch cleanup or lifecycle policy recorded",
            "S3 artifacts exported with checksums and retention policy",
            "CloudWatch log group retention declared",
        ],
        "operator_gates": [
            "AWS credentials are not required for dry-run",
            "real submit requires operator-approved AWS profile and budget",
        ],
    },
    "neocloud_gpu_pod_v1": {
        "cost_gates": [
            "explicit operator launch approval",
            "provider project and quota scope checked",
            "max_spend_usd and max_runtime_minutes declared before pod create",
            "actual pod rate, GPU type, and volume charge reconciled in cost_report.json",
        ],
        "cleanup_gates": [
            "pod deletion or terminal stopped proof",
            "scratch or volume cleanup proof",
            "artifact export proof from provider storage",
            "provider log stream captured or retention declared",
        ],
        "operator_gates": [
            "neocloud credentials are not required for dry-run",
            "real launch requires provider scope check and operator gate",
        ],
    },
}


def load_json(path: Path) -> dict[str, Any]:
    return json.loads(path.read_text())


def write_json(path: Path, data: dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(data, indent=2, sort_keys=True) + "\n")


def sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def repo_relative(path: Path) -> str:
    try:
        return str(path.resolve().relative_to(REPO_ROOT))
    except ValueError:
        return str(path.resolve())


def resolve_repo_path(value: str | Path) -> Path:
    path = Path(value)
    return path if path.is_absolute() else REPO_ROOT / path


def unique(items: list[str]) -> list[str]:
    seen: set[str] = set()
    result: list[str] = []
    for item in items:
        if item not in seen:
            result.append(item)
            seen.add(item)
    return result


def load_artifact_contract(manifest: dict[str, Any]) -> dict[str, Any]:
    contract_path = manifest.get("outputs", {}).get("artifact_contract")
    if not isinstance(contract_path, str) or not contract_path:
        return {}
    path = resolve_repo_path(contract_path)
    if not path.exists():
        return {}
    return load_json(path)


def artifact_roots(adapter: str, profile: dict[str, Any], run_id: str) -> dict[str, str]:
    root = str(profile.get("artifact_root", "runs/<run-id>")).replace("<run-id>", run_id)
    if adapter == "local_workstation_v1" and root.startswith(".runtime/"):
        return {
            "provider_artifact_root": root,
            "operator_pull_root": root,
            "hash_root": root,
        }
    if adapter == "aws_batch_v1":
        return {
            "provider_artifact_root": root,
            "operator_pull_root": f".runtime/provider-artifacts/{run_id}/aws_batch_v1",
            "hash_root": f".runtime/provider-artifacts/{run_id}/aws_batch_v1",
        }
    return {
        "provider_artifact_root": root,
        "operator_pull_root": f".runtime/provider-artifacts/{run_id}/{adapter}",
        "hash_root": f".runtime/provider-artifacts/{run_id}/{adapter}",
    }


def required_artifacts_for(adapter: str, manifest: dict[str, Any]) -> dict[str, list[str]]:
    contract = load_artifact_contract(manifest)
    smoke = contract.get("required_for_screening_smoke") if isinstance(contract, dict) else None
    scale = contract.get("required_for_scale_canary") if isinstance(contract, dict) else None
    if isinstance(smoke, list) and all(isinstance(item, str) for item in smoke):
        base = list(smoke)
    else:
        base = COMMON_REQUIRED_ARTIFACTS + LOCAL_PREP_ARTIFACTS

    if adapter == "local_workstation_v1":
        required = unique(base + ["validation/contract-self-check.json"])
    elif isinstance(scale, list) and all(isinstance(item, str) for item in scale):
        required = unique(scale)
    else:
        required = unique(base + PROVIDER_CLOSEOUT_ARTIFACTS)

    return {
        "required": required,
        "required_at_closeout": unique(COMMON_REQUIRED_ARTIFACTS + (PROVIDER_CLOSEOUT_ARTIFACTS if adapter != "local_workstation_v1" else [])),
        "promoted_when_selected": ["candidate_reports/"],
    }


def normalize_adapters(value: Any) -> list[str]:
    if value is None:
        return DEFAULT_ADAPTERS
    if not isinstance(value, list) or not value:
        raise ValueError("providers/adapters must be a non-empty list")
    adapters: list[str] = []
    for item in value:
        if isinstance(item, str):
            adapter = item
        elif isinstance(item, dict):
            adapter = str(item.get("adapter", ""))
        else:
            raise ValueError("provider entries must be adapter strings or objects")
        if adapter not in ADAPTER_PROFILE_PATHS:
            raise ValueError(f"unsupported adapter: {adapter}")
        adapters.append(adapter)
    return unique(adapters)


def read_input(path: Path) -> tuple[dict[str, Any], dict[str, Any], str, list[str]]:
    data = load_json(path)
    warnings: list[str] = []

    if data.get("manifest_type") == "screening_manifest":
        manifest = data
        run_spec = {
            "schema_version": 1,
            "spec_type": "provider_run_spec",
            "campaign_id": manifest.get("campaign_id"),
            "run_id": manifest.get("run_id"),
            "source_manifest": repo_relative(path),
            "execution_profile": manifest.get("provider_plan", {}).get("execution_profile"),
            "adapters": DEFAULT_ADAPTERS,
            "dry_run": {
                "no_provider_launch": True,
                "no_secrets_required": True,
                "no_paid_compute": True,
            },
        }
        input_kind = "screening_manifest"
    elif data.get("spec_type") == "provider_run_spec":
        run_spec = data
        source_manifest = data.get("source_manifest")
        if not isinstance(source_manifest, str) or not source_manifest:
            raise ValueError("provider_run_spec.source_manifest is required")
        manifest_path = resolve_repo_path(source_manifest)
        manifest = load_json(manifest_path)
        if manifest.get("manifest_type") != "screening_manifest":
            raise ValueError("provider_run_spec.source_manifest must point to a screening_manifest")
        input_kind = "provider_run_spec"
        spec_run_id = run_spec.get("run_id")
        if spec_run_id and spec_run_id != manifest.get("run_id"):
            warnings.append("run_spec.run_id differs from source manifest run_id; manifest run_id is used in packets")
    else:
        raise ValueError("input must be a screening_manifest or provider_run_spec JSON")

    return manifest, run_spec, input_kind, warnings


def validate_no_paid_posture(manifest: dict[str, Any], run_spec: dict[str, Any]) -> tuple[list[str], list[str]]:
    errors: list[str] = []
    warnings: list[str] = []

    dry_run = run_spec.get("dry_run", {})
    if not isinstance(dry_run, dict):
        errors.append("dry_run block must be an object")
        dry_run = {}
    if dry_run.get("no_provider_launch") is not True:
        errors.append("dry_run.no_provider_launch must be true")
    if dry_run.get("no_secrets_required") is not True:
        errors.append("dry_run.no_secrets_required must be true")
    if dry_run.get("no_paid_compute") is not True:
        errors.append("dry_run.no_paid_compute must be true")

    policies = manifest.get("policies", {})
    if policies.get("allow_private_data") is not False:
        errors.append("screening manifest must keep policies.allow_private_data false for this dry-run")
    if policies.get("allow_raw_cryoem_downloads") is not False:
        errors.append("screening manifest must keep policies.allow_raw_cryoem_downloads false for this dry-run")
    if policies.get("expected_download_bytes") != 0:
        errors.append("screening manifest expected_download_bytes must be 0 for this dry-run")

    budget = manifest.get("budget", {})
    max_spend = budget.get("max_spend_usd")
    if max_spend != 0:
        warnings.append(f"manifest budget.max_spend_usd is {max_spend}; dry-run packets still perform no paid action")
    if manifest.get("provider_plan", {}).get("operator_gate_required_for_paid_compute") is not True:
        warnings.append("provider_plan.operator_gate_required_for_paid_compute should be true for remote providers")

    claim = manifest.get("intent", {}).get("claim_ceiling")
    if claim in {"validated", "publishable"}:
        errors.append("dry-run screening packets cannot request validated or publishable claim ceilings")

    return errors, warnings


def provider_profile_for(adapter: str, run_spec: dict[str, Any]) -> tuple[Path, dict[str, Any]]:
    configured = {}
    for item in run_spec.get("providers", []) if isinstance(run_spec.get("providers"), list) else []:
        if isinstance(item, dict) and item.get("adapter") == adapter and isinstance(item.get("profile"), str):
            configured[adapter] = item["profile"]
    path = resolve_repo_path(configured.get(adapter, ADAPTER_PROFILE_PATHS[adapter]))
    return path, load_json(path)


def packet_for(
    adapter: str,
    profile_path: Path,
    profile: dict[str, Any],
    manifest_path: Path,
    run_spec_path: Path,
    manifest: dict[str, Any],
    run_spec: dict[str, Any],
    created_at: str,
) -> dict[str, Any]:
    run_id = str(manifest.get("run_id", run_spec.get("run_id", "structure-factory-run")))
    campaign_id = str(manifest.get("campaign_id", run_spec.get("campaign_id", "structure-factory")))
    execution_profile = str(
        run_spec.get("execution_profile")
        or manifest.get("provider_plan", {}).get("execution_profile")
        or profile.get("maps_campaign_profile")
        or "screening-no-download-smoke"
    )
    roots = artifact_roots(adapter, profile, run_id)
    artifacts = required_artifacts_for(adapter, manifest)
    gates = PROVIDER_GATE_CATALOG[adapter]
    operator_gate_required = bool(profile.get("operator_gate_required"))
    max_runtime = manifest.get("budget", {}).get("max_runtime_minutes")
    max_spend = manifest.get("budget", {}).get("max_spend_usd")

    packet_id = f"{run_id}-{adapter}"
    env_preview = {
        "STRUCTURE_FACTORY_RUN_ID": run_id,
        "STRUCTURE_FACTORY_CAMPAIGN_ID": campaign_id,
        "STRUCTURE_FACTORY_EXECUTION_PROFILE": execution_profile,
        "STRUCTURE_FACTORY_DRY_RUN": "1",
        "STRUCTURE_FACTORY_NO_PROVIDER_LAUNCH": "1",
    }

    return {
        "schema_version": 1,
        "packet_type": "structure_factory_provider_launch_packet",
        "packet_id": packet_id,
        "created_at": created_at,
        "adapter": adapter,
        "provider": profile.get("provider"),
        "provider_class": profile.get("provider_class"),
        "profile_id": profile.get("profile_id"),
        "profile_path": repo_relative(profile_path),
        "dry_run": {
            "enabled": True,
            "no_provider_launch": True,
            "no_paid_compute": True,
            "no_secrets_required": True,
            "launch_command": None,
            "provider_api_calls": [],
            "secret_env_reads": [],
        },
        "source": {
            "input_kind": "provider_run_spec" if run_spec_path != manifest_path else "screening_manifest",
            "run_spec_path": repo_relative(run_spec_path),
            "run_spec_sha256": sha256(run_spec_path),
            "screening_manifest_path": repo_relative(manifest_path),
            "screening_manifest_sha256": sha256(manifest_path),
        },
        "run": {
            "campaign_id": campaign_id,
            "run_id": run_id,
            "execution_profile": execution_profile,
            "intent_mode": manifest.get("intent", {}).get("mode"),
            "claim_ceiling": manifest.get("intent", {}).get("claim_ceiling"),
            "evidence_mode": "fixture_or_demo",
            "current_run_is_no_download_fixture": manifest.get("provider_plan", {}).get("current_run_is_no_download_fixture"),
        },
        "budget": {
            "max_spend_usd": max_spend,
            "max_runtime_minutes": max_runtime,
            "cost_incurred_by_packet": 0,
            "paid_mutation_allowed": False,
        },
        "workspace": {
            "workspace_root": profile.get("workspace_root"),
            **roots,
        },
        "lifecycle": {
            "canonical_states": CANONICAL_LIFECYCLE_STATES,
            "initial_state": "packet_created",
            "dry_run_terminal_state": "packet_created",
            "states_that_do_not_prove_success": INTENT_ONLY_STATES,
            "success_state": "closeout_ready",
            "failure_states": ["closed_partial", "closed_blocked", "closed_failed"],
        },
        "required_artifacts": artifacts,
        "shard_ledger": {
            "ledger_type": "structure_factory_cloud_shard_ledger",
            "example_path": CLOUD_SHARD_LEDGER_EXAMPLE,
            "expected_runtime_path": f"{roots['operator_pull_root']}/validation/cloud-shard-ledger.json",
            "per_shard_closeout_requires": artifacts["required_at_closeout"],
            "canary_required_before_paid_fanout": True,
            "provider_success_is_not_scientific_success": True,
            "validator": CLOUD_SHARD_LEDGER_VALIDATOR,
        },
        "gates": {
            "operator_gate_required_for_real_launch": operator_gate_required,
            "execution_ready_requires": profile.get("execution_ready_requires", []),
            "cost": gates["cost_gates"],
            "cleanup": gates["cleanup_gates"],
            "operator": gates["operator_gates"],
        },
        "closeout_requirements": CLOSEOUT_REQUIREMENTS,
        "command_preview": {
            "dry_run_packet_generation": (
                "python3 scripts/structure_factory/provider_adapter_dry_run.py "
                f"--run-spec {repo_relative(run_spec_path)} --out .runtime/provider-adapter-dry-run --json"
            ),
            "local_fixture_command": (
                "python3 scripts/structure_factory/screening_fixture_run.py "
                f"--manifest {repo_relative(manifest_path)} --out .runtime/{run_id} --json"
            ),
            "real_provider_launch": "blocked: requires explicit operator gate and provider-specific launcher outside this dry-run adapter",
        },
        "environment_preview": env_preview,
        "notes": [
            "This packet is inert and provider-neutral; it is not an authorization to launch.",
            "Provider scheduler state, pod RUNNING, or process exit alone cannot close scientific success.",
            "Dry-run or fixture evidence must stay at fixture_or_demo/candidate result boundary unless replaced by provider-native evidence.",
        ],
    }


def build_packets(input_path: Path, out: Path) -> dict[str, Any]:
    manifest, run_spec, input_kind, input_warnings = read_input(input_path)
    errors, posture_warnings = validate_no_paid_posture(manifest, run_spec)
    warnings = input_warnings + posture_warnings

    source_manifest_path = input_path
    if input_kind == "provider_run_spec":
        source_manifest_path = resolve_repo_path(str(run_spec["source_manifest"]))

    adapters = normalize_adapters(run_spec.get("adapters", run_spec.get("providers")))
    created_at = datetime.now(timezone.utc).isoformat()
    packet_dir = out / "packets"
    packets: list[dict[str, Any]] = []

    for adapter in adapters:
        profile_path, profile = provider_profile_for(adapter, run_spec)
        packet = packet_for(
            adapter=adapter,
            profile_path=profile_path,
            profile=profile,
            manifest_path=source_manifest_path,
            run_spec_path=input_path,
            manifest=manifest,
            run_spec=run_spec,
            created_at=created_at,
        )
        packets.append(packet)
        write_json(packet_dir / f"{adapter}.launch-packet.json", packet)

    summary = {
        "ok": not errors,
        "check_type": "provider_adapter_dry_run",
        "created_at": created_at,
        "input": {
            "path": repo_relative(input_path),
            "kind": input_kind,
            "sha256": sha256(input_path),
        },
        "screening_manifest": {
            "path": repo_relative(source_manifest_path),
            "sha256": sha256(source_manifest_path),
            "campaign_id": manifest.get("campaign_id"),
            "run_id": manifest.get("run_id"),
            "execution_profile": manifest.get("provider_plan", {}).get("execution_profile"),
        },
        "dry_run_guarantees": {
            "provider_api_calls": 0,
            "paid_compute_launched": False,
            "secrets_required": False,
            "files_written_under": repo_relative(out),
        },
        "adapters": [
            {
                "adapter": packet["adapter"],
                "provider": packet["provider"],
                "provider_class": packet["provider_class"],
                "packet_path": repo_relative(packet_dir / f"{packet['adapter']}.launch-packet.json"),
                "operator_gate_required_for_real_launch": packet["gates"]["operator_gate_required_for_real_launch"],
            }
            for packet in packets
        ],
        "canonical_lifecycle_states": CANONICAL_LIFECYCLE_STATES,
        "states_that_do_not_prove_success": INTENT_ONLY_STATES,
        "required_artifacts_by_adapter": {packet["adapter"]: packet["required_artifacts"] for packet in packets},
        "cloud_shard_ledger": {
            "example_path": CLOUD_SHARD_LEDGER_EXAMPLE,
            "validator": CLOUD_SHARD_LEDGER_VALIDATOR,
            "packet_fields": {packet["adapter"]: packet["shard_ledger"] for packet in packets},
        },
        "closeout_requirements": CLOSEOUT_REQUIREMENTS,
        "errors": errors,
        "warnings": warnings,
    }
    write_json(out / "summary.json", summary)
    return summary


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument(
        "input",
        type=Path,
        nargs="?",
        help="Screening manifest or provider run spec JSON. Defaults to the screening-superpowers provider run spec.",
    )
    parser.add_argument("--manifest", type=Path, help="Read a screening manifest directly")
    parser.add_argument("--run-spec", type=Path, help="Read a provider run spec that references a screening manifest")
    parser.add_argument(
        "--out",
        type=Path,
        default=Path(".runtime/provider-adapter-dry-run"),
        help="Output directory for summary and packet JSON files",
    )
    parser.add_argument("--json", action="store_true")
    args = parser.parse_args()

    selected = [value for value in [args.input, args.manifest, args.run_spec] if value is not None]
    if len(selected) > 1:
        raise SystemExit("choose only one of positional input, --manifest, or --run-spec")
    input_path = selected[0] if selected else Path("examples/screening-superpowers/provider-run-spec.json")
    input_path = resolve_repo_path(input_path)

    try:
        summary = build_packets(input_path=input_path, out=args.out)
    except Exception as exc:
        summary = {
            "ok": False,
            "check_type": "provider_adapter_dry_run",
            "input": str(input_path),
            "errors": [f"{type(exc).__name__}: {exc}"],
            "warnings": [],
        }

    if args.json:
        print(json.dumps(summary, indent=2, sort_keys=True))
    else:
        print(f"ok: {summary['ok']}")
        if summary.get("dry_run_guarantees"):
            print(f"out: {summary['dry_run_guarantees']['files_written_under']}")
        for warning in summary.get("warnings", []):
            print(f"warning: {warning}")
        for error in summary.get("errors", []):
            print(f"error: {error}")
    return 0 if summary["ok"] else 1


if __name__ == "__main__":
    raise SystemExit(main())
