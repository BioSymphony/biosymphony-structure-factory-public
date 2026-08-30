#!/usr/bin/env python3
"""Validate provider closeout evidence without touching provider APIs.

This checker is intentionally stdlib-only and file-based. It validates local
provider-run records, pulled artifacts, cleanup/cost reports, and cloud shard
ledgers. It never calls RunPod, AWS, neocloud, SSH/HPC, or generic cloud CLIs.
"""

from __future__ import annotations

import argparse
import hashlib
import json
from collections import Counter
from pathlib import Path
from typing import Any


REPO_ROOT = Path(__file__).resolve().parents[2]

BASE_REQUIRED_ARTIFACTS = [
    "stage-progress.jsonl",
    "validation/input-audit.json",
    "validation/contract-self-check.json",
    "executed-commands.jsonl",
    "validation_ledger.json",
    "provenance.md",
]

PROVIDER_CLOSEOUT_ARTIFACTS = [
    "validation/artifact-pull-report.json",
    "cost_report.json",
    "cleanup_proof.json",
]

HASH_LEDGER_CANDIDATES = [
    "artifact_hashes.json",
    "artifact-hashes.json",
    "validation/artifact_hashes.json",
    "validation/artifact-hashes.json",
]

ARTIFACT_ALIASES = {
    "validation/artifact-pull-report.json": [
        "validation/artifact-pull-report.json",
        "artifact-pull-report.json",
        "artifact_pull_report.json",
    ],
    "cost_report.json": ["cost_report.json", "cost-report.json"],
    "cleanup_proof.json": [
        "cleanup_proof.json",
        "cleanup-proof.json",
        "validation/cleanup-proof.json",
    ],
}

INTENT_ONLY_STATES = {
    "pending",
    "planned",
    "queued",
    "submitted",
    "starting",
    "running",
    "provider_starting",
    "provider_running",
    "in_queue",
    "running",
}

READY_STATUSES = {"completed", "cleanup_verified", "closeout_ready"}
DOWNGRADED_STATUSES = {
    "blocked",
    "closed_blocked",
    "failed",
    "closed_failed",
    "partial",
    "closed_partial",
    "provider_start_plateau",
    "insufficient_evidence",
    "deleted",
}
TERMINAL_STAGE_STATUSES = {"completed", "failed", "blocked", "skipped", "partial"}
BAD_ARTIFACT_MARKERS = [
    b"<" + bytes.fromhex("68746d6c"),
    b"<!" + b"doctype " + bytes.fromhex("68746d6c"),
    b"404 not found",
    b"502 bad gateway",
    b"503 service unavailable",
]

PAID_PROVIDER_NAMES = {
    "runpod",
    "aws",
    "aws_batch",
    "aws-batch",
    "batch_job",
    "generic_cloud",
    "generic-cloud",
    "cloud_vm",
    "cloud-vm",
    "neocloud",
    "neocloud_gpu_pod",
    "neocloud-gpu-pod",
    "ssh_hpc",
    "ssh-hpc",
}

CLAIM_LEVELS_REQUIRING_REAL_EVIDENCE = {"validated", "publishable"}
DOWNGRADED_CLAIM_LEVELS = {"candidate", "processed", "insufficient_evidence", "blocked"}


def repo_relative(path: Path) -> str:
    try:
        return str(path.resolve().relative_to(REPO_ROOT))
    except ValueError:
        return str(path.resolve())


def resolve_path(path: Path) -> Path:
    return path if path.is_absolute() else REPO_ROOT / path


def load_json(path: Path) -> Any:
    return json.loads(path.read_text())


def write_json(path: Path, payload: dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, indent=2, sort_keys=True) + "\n")


def sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def normalize_status(value: Any) -> str:
    return str(value or "").strip().lower().replace("-", "_")


def normalize_provider(value: Any) -> str:
    return str(value or "").strip().lower().replace("-", "_")


def is_paid_provider(provider: str) -> bool:
    normalized = normalize_provider(provider)
    return normalized in {item.replace("-", "_") for item in PAID_PROVIDER_NAMES}


def as_number(value: Any) -> float | None:
    if isinstance(value, bool):
        return None
    if isinstance(value, (int, float)):
        return float(value)
    if isinstance(value, str):
        try:
            return float(value)
        except ValueError:
            return None
    return None


def unique(items: list[str]) -> list[str]:
    seen: set[str] = set()
    result: list[str] = []
    for item in items:
        if item not in seen:
            result.append(item)
            seen.add(item)
    return result


def artifact_candidates(root: Path, rel: str) -> list[Path]:
    candidates = ARTIFACT_ALIASES.get(rel, [rel])
    return [root / candidate for candidate in candidates]


def first_existing_artifact(root: Path, rel: str) -> Path:
    for candidate in artifact_candidates(root, rel):
        if candidate.exists():
            return candidate
    return root / rel


def artifact_has_bad_proxy_body(path: Path) -> bool:
    try:
        sample = path.read_bytes()[:2048].lower()
    except OSError:
        return False
    return any(marker in sample for marker in BAD_ARTIFACT_MARKERS)


def parse_jsonl(path: Path) -> tuple[list[dict[str, Any]], list[str]]:
    events: list[dict[str, Any]] = []
    errors: list[str] = []
    for index, raw_line in enumerate(path.read_text().splitlines(), start=1):
        line = raw_line.strip()
        if not line:
            continue
        try:
            payload = json.loads(line)
        except json.JSONDecodeError as exc:
            errors.append(f"{repo_relative(path)} line {index} is malformed JSON: {exc.msg}")
            continue
        if not isinstance(payload, dict):
            errors.append(f"{repo_relative(path)} line {index} must be a JSON object")
            continue
        events.append(payload)
    return events, errors


def load_launch_packet(path: Path | None) -> dict[str, Any]:
    if path is None:
        return {}
    return load_json(resolve_path(path))


def closeout_required_artifacts(
    launch_packet: dict[str, Any],
    user_required: list[str],
    provider: str,
    execution_mode: str,
) -> list[str]:
    packet_artifacts = launch_packet.get("required_artifacts", {}) if launch_packet else {}
    required: list[str] = []
    if isinstance(packet_artifacts, dict):
        for key in ["required_at_closeout", "required"]:
            values = packet_artifacts.get(key)
            if isinstance(values, list) and all(isinstance(item, str) for item in values):
                required.extend(values)
                break
    required.extend(user_required)
    if not required:
        required.extend(BASE_REQUIRED_ARTIFACTS)
        if execution_mode == "real" and is_paid_provider(provider):
            required.extend(PROVIDER_CLOSEOUT_ARTIFACTS)
    return unique(required)


def check_structured_json(path: Path, payload: Any) -> list[str]:
    errors: list[str] = []
    rel = repo_relative(path)
    if isinstance(payload, dict) and payload.get("ok") is False:
        errors.append(f"{rel} reports ok false")
    if path.name in {"input-audit.json", "contract-self-check.json"} and not isinstance(payload, dict):
        errors.append(f"{rel} must be a JSON object")
    return errors


def check_artifacts(root: Path, required: list[str]) -> tuple[list[dict[str, Any]], list[str], list[str]]:
    checks: list[dict[str, Any]] = []
    errors: list[str] = []
    warnings: list[str] = []
    for rel in required:
        path = first_existing_artifact(root, rel)
        check: dict[str, Any] = {
            "declared_path": rel,
            "path": repo_relative(path),
            "present": path.exists(),
            "bytes": 0,
            "sha256": None,
            "format_ok": None,
        }
        if not path.exists():
            errors.append(f"required artifact missing: {rel}")
            checks.append(check)
            continue
        try:
            size = path.stat().st_size
        except OSError as exc:
            errors.append(f"required artifact unreadable: {rel}: {exc}")
            checks.append(check)
            continue
        check["bytes"] = size
        if size <= 0:
            errors.append(f"required artifact is empty: {rel}")
        if artifact_has_bad_proxy_body(path):
            errors.append(f"required artifact looks like provider/proxy error body: {rel}")
        if path.suffix == ".json":
            try:
                payload = load_json(path)
            except json.JSONDecodeError as exc:
                check["format_ok"] = False
                errors.append(f"required JSON artifact malformed: {rel}: {exc.msg}")
            else:
                check["format_ok"] = True
                errors.extend(check_structured_json(path, payload))
        elif path.suffix == ".jsonl":
            _events, jsonl_errors = parse_jsonl(path)
            check["format_ok"] = not jsonl_errors
            errors.extend(jsonl_errors)
        if size > 0 and path.is_file():
            check["sha256"] = sha256(path)
        checks.append(check)
    if not required:
        warnings.append("no required artifacts declared")
    return checks, errors, warnings


def check_stage_progress(root: Path, execution_mode: str, closeout_ready_requested: bool) -> tuple[dict[str, Any], list[str], list[str]]:
    path = root / "stage-progress.jsonl"
    errors: list[str] = []
    warnings: list[str] = []
    summary: dict[str, Any] = {
        "path": repo_relative(path),
        "present": path.exists(),
        "event_count": 0,
        "terminal_by_stage": {},
        "failed_or_partial_stages": [],
    }
    if not path.exists():
        if execution_mode == "real":
            errors.append("stage-progress.jsonl missing")
        return summary, errors, warnings
    events, jsonl_errors = parse_jsonl(path)
    errors.extend(jsonl_errors)
    summary["event_count"] = len(events)
    terminal_by_stage: dict[str, str] = {}
    failed_or_partial: list[dict[str, str]] = []
    for event in events:
        status = normalize_status(event.get("status"))
        stage_id = str(event.get("stage_id", ""))
        if status in TERMINAL_STAGE_STATUSES and stage_id:
            terminal_by_stage[stage_id] = status
            if status in {"failed", "blocked", "partial"}:
                failed_or_partial.append({"stage_id": stage_id, "status": status})
    summary["terminal_by_stage"] = terminal_by_stage
    summary["failed_or_partial_stages"] = failed_or_partial
    if execution_mode == "real" and not terminal_by_stage:
        errors.append("stage-progress.jsonl has no terminal stage events")
    if closeout_ready_requested and failed_or_partial:
        errors.append("closeout_ready requested with failed, blocked, or partial stage events")
    if not events:
        warnings.append("stage-progress.jsonl contains no events")
    return summary, errors, warnings


def check_artifact_pull_report(root: Path, execution_mode: str) -> tuple[dict[str, Any], list[str], list[str]]:
    path = first_existing_artifact(root, "validation/artifact-pull-report.json")
    errors: list[str] = []
    warnings: list[str] = []
    summary: dict[str, Any] = {
        "path": repo_relative(path),
        "present": path.exists(),
        "overall_status": None,
        "artifact_count": 0,
        "accepted_required_count": 0,
    }
    if not path.exists():
        return summary, errors, warnings
    try:
        report = load_json(path)
    except json.JSONDecodeError as exc:
        errors.append(f"artifact pull report malformed: {exc.msg}")
        return summary, errors, warnings
    if not isinstance(report, dict):
        errors.append("artifact pull report must be a JSON object")
        return summary, errors, warnings
    status = str(report.get("overall_status", "")).upper()
    artifacts = report.get("artifacts", [])
    summary["overall_status"] = status
    summary["artifact_count"] = len(artifacts) if isinstance(artifacts, list) else 0
    if execution_mode == "real" and status != "OK":
        errors.append(f"artifact pull report overall_status is not OK: {status or 'missing'}")
    if not isinstance(artifacts, list):
        errors.append("artifact pull report artifacts must be a list")
        return summary, errors, warnings
    accepted_required_count = 0
    for index, artifact in enumerate(artifacts):
        if not isinstance(artifact, dict):
            errors.append(f"artifact pull report artifact[{index}] must be an object")
            continue
        required = artifact.get("required") is True
        accepted = artifact.get("accepted") is True
        bytes_value = as_number(artifact.get("bytes"))
        http_status = as_number(artifact.get("http_status"))
        declared = artifact.get("declared_path") or f"artifact[{index}]"
        if required and accepted:
            accepted_required_count += 1
        if required and not accepted:
            errors.append(f"required pulled artifact was not accepted: {declared}")
        if required and (bytes_value is None or bytes_value <= 0):
            errors.append(f"required pulled artifact has no bytes: {declared}")
        if http_status is not None and http_status >= 400:
            errors.append(f"pulled artifact has failing HTTP status {int(http_status)}: {declared}")
        if artifact.get("proxy_error_body") is True:
            errors.append(f"pulled artifact recorded proxy_error_body: {declared}")
        if artifact.get("hash_status") in {"mismatch", "missing", "failed"}:
            errors.append(f"pulled artifact hash_status is {artifact.get('hash_status')}: {declared}")
        if artifact.get("format_ok") is False:
            errors.append(f"pulled artifact format_ok false: {declared}")
    summary["accepted_required_count"] = accepted_required_count
    if execution_mode == "real" and accepted_required_count == 0:
        warnings.append("artifact pull report has no accepted required artifacts")
    return summary, errors, warnings


def check_cost_report(root: Path, paid_provider: bool, execution_mode: str) -> tuple[dict[str, Any], list[str], list[str]]:
    path = first_existing_artifact(root, "cost_report.json")
    errors: list[str] = []
    warnings: list[str] = []
    summary: dict[str, Any] = {"path": repo_relative(path), "present": path.exists()}
    if not path.exists():
        if paid_provider and execution_mode == "real":
            errors.append("cost_report.json missing for paid/provider closeout")
        return summary, errors, warnings
    try:
        report = load_json(path)
    except json.JSONDecodeError as exc:
        errors.append(f"cost report malformed: {exc.msg}")
        return summary, errors, warnings
    if not isinstance(report, dict):
        errors.append("cost report must be a JSON object")
        return summary, errors, warnings
    total = as_number(report.get("total_cost_usd") or report.get("cost_usd"))
    max_authorized = as_number(report.get("max_authorized_spend_usd") or report.get("max_spend_usd"))
    budget_status = report.get("budget_status")
    summary.update(
        {
            "total_cost_usd": total,
            "max_authorized_spend_usd": max_authorized,
            "budget_status": budget_status,
        }
    )
    if budget_status == "over_budget":
        errors.append("cost report budget_status is over_budget")
    if total is not None and max_authorized is not None and total > max_authorized:
        errors.append(f"cost report exceeds authorized spend: {total} > {max_authorized}")
    if paid_provider and execution_mode == "real" and total is None:
        warnings.append("cost report does not include total_cost_usd")
    if paid_provider and execution_mode == "real" and max_authorized is None:
        warnings.append("cost report does not include max_authorized_spend_usd")
    return summary, errors, warnings


def check_cleanup_proof(root: Path, paid_provider: bool, execution_mode: str) -> tuple[dict[str, Any], list[str], list[str]]:
    path = first_existing_artifact(root, "cleanup_proof.json")
    errors: list[str] = []
    warnings: list[str] = []
    summary: dict[str, Any] = {"path": repo_relative(path), "present": path.exists()}
    if not path.exists():
        if paid_provider and execution_mode == "real":
            errors.append("cleanup_proof.json missing for paid/provider closeout")
        return summary, errors, warnings
    try:
        report = load_json(path)
    except json.JSONDecodeError as exc:
        errors.append(f"cleanup proof malformed: {exc.msg}")
        return summary, errors, warnings
    if not isinstance(report, dict):
        errors.append("cleanup proof must be a JSON object")
        return summary, errors, warnings
    cleanup = report.get("cleanup", {}) if isinstance(report.get("cleanup", {}), dict) else {}
    verified = cleanup.get("verified")
    status = report.get("overall_status")
    summary.update({"verified": verified, "overall_status": status})
    if paid_provider and execution_mode == "real" and verified is not True and status not in {"verified", "not_applicable"}:
        errors.append("cleanup proof is not verified")
    return summary, errors, warnings


def check_hash_evidence(root: Path, artifact_checks: list[dict[str, Any]]) -> dict[str, Any]:
    ledger_paths = [root / candidate for candidate in HASH_LEDGER_CANDIDATES]
    existing = next((path for path in ledger_paths if path.exists()), None)
    computed_hashes = {
        check["declared_path"]: check["sha256"]
        for check in artifact_checks
        if isinstance(check.get("sha256"), str) and check.get("present")
    }
    return {
        "hash_ledger_present": existing is not None,
        "hash_ledger_path": repo_relative(existing) if existing else None,
        "computed_artifact_hash_count": len(computed_hashes),
        "computed_hashes": computed_hashes,
    }


def check_provider_run(provider_run: dict[str, Any], execution_mode: str) -> tuple[dict[str, Any], list[str], list[str]]:
    errors: list[str] = []
    warnings: list[str] = []
    provider = normalize_provider(provider_run.get("provider"))
    status = normalize_status(provider_run.get("status"))
    desired_status = normalize_status(provider_run.get("desired_status"))
    actual_status = normalize_status(provider_run.get("actual_status"))
    evidence_mode = str(provider_run.get("evidence_mode") or "")
    claim_level = str(provider_run.get("claim_level") or "")
    uptime = as_number(provider_run.get("runtime_uptime_seconds"))
    closeout_ready_requested = status in READY_STATUSES or normalize_status(provider_run.get("closeout_status")) == "closeout_ready"

    summary = {
        "provider": provider,
        "run_id": provider_run.get("run_id"),
        "status": status,
        "desired_status": desired_status,
        "actual_status": actual_status,
        "runtime_uptime_seconds": uptime,
        "claim_level": claim_level,
        "evidence_mode": evidence_mode,
        "closeout_ready_requested": closeout_ready_requested,
    }

    if status in INTENT_ONLY_STATES and claim_level not in {"blocked", "insufficient_evidence"}:
        message = f"provider status is intent-only and cannot support closeout: {status}"
        if execution_mode == "real":
            errors.append(message)
        else:
            warnings.append(message)
    if desired_status in INTENT_ONLY_STATES and not actual_status and (uptime is None or uptime <= 0):
        message = "desired_status is provider intent only; actual runtime/progress evidence is missing"
        if execution_mode == "real":
            errors.append(message)
        else:
            warnings.append(message)
    if closeout_ready_requested and is_paid_provider(provider) and (uptime is None or uptime <= 0):
        errors.append("paid/provider closeout_ready requires runtime_uptime_seconds > 0")
    if claim_level in CLAIM_LEVELS_REQUIRING_REAL_EVIDENCE and evidence_mode != "provider_native":
        errors.append(f"{claim_level} claim requires provider_native evidence, not {evidence_mode or 'missing'}")
    if evidence_mode == "fixture_or_demo" and claim_level not in DOWNGRADED_CLAIM_LEVELS:
        errors.append(f"fixture_or_demo evidence cannot support result boundary {claim_level}")
    if status in DOWNGRADED_STATUSES and claim_level in CLAIM_LEVELS_REQUIRING_REAL_EVIDENCE:
        errors.append(f"downgraded provider status cannot carry {claim_level} claim")
    run_errors = provider_run.get("errors")
    if isinstance(run_errors, list) and run_errors and closeout_ready_requested:
        errors.append("provider run records errors but closeout_ready was requested")
    return summary, errors, warnings


def load_shard_ledger(path: Path) -> dict[str, Any]:
    if path.suffix == ".jsonl":
        shards, errors = parse_jsonl(path)
        return {
            "schema_version": 1,
            "ledger_type": "structure_factory_cloud_shard_ledger",
            "ledger_format": "jsonl",
            "shards": shards,
            "_parse_errors": errors,
        }
    ledger = load_json(path)
    if not isinstance(ledger, dict):
        raise ValueError("shard ledger JSON must be an object")
    return ledger


def validate_shard_ledger(path: Path, execution_mode: str) -> tuple[dict[str, Any], list[str], list[str]]:
    errors: list[str] = []
    warnings: list[str] = []
    ledger = load_shard_ledger(path)
    errors.extend(ledger.pop("_parse_errors", []))
    shards = ledger.get("shards")
    summary: dict[str, Any] = {
        "path": repo_relative(path),
        "ledger_type": ledger.get("ledger_type"),
        "ledger_mode": ledger.get("ledger_mode"),
        "campaign_id": ledger.get("campaign_id"),
        "run_id": ledger.get("run_id"),
        "shard_total_declared": ledger.get("shard_total"),
        "shard_count": 0,
        "providers": {},
        "statuses": {},
        "closeout_ready_shards": 0,
        "blocked_or_planned_shards": 0,
    }
    if ledger.get("schema_version") != 1:
        errors.append("shard ledger schema_version must be 1")
    if ledger.get("ledger_type") not in {None, "structure_factory_cloud_shard_ledger"}:
        errors.append(f"unsupported shard ledger_type: {ledger.get('ledger_type')}")
    if not isinstance(shards, list) or not shards:
        errors.append("shard ledger must contain a non-empty shards list")
        return summary, errors, warnings

    summary["shard_count"] = len(shards)
    declared_total = ledger.get("shard_total")
    if declared_total is not None and declared_total != len(shards):
        errors.append(f"shard_total does not match shards length: {declared_total} != {len(shards)}")

    ids: set[str] = set()
    indexes: set[int] = set()
    provider_counts: Counter[str] = Counter()
    status_counts: Counter[str] = Counter()
    closeout_ready_count = 0
    blocked_or_planned_count = 0

    for position, shard in enumerate(shards):
        if not isinstance(shard, dict):
            errors.append(f"shards[{position}] must be an object")
            continue
        shard_id = str(shard.get("shard_id") or "")
        provider = normalize_provider(shard.get("provider"))
        status = normalize_status(shard.get("status"))
        closeout_status = normalize_status(shard.get("closeout_status"))
        evidence_mode = str(shard.get("evidence_mode") or "")
        claim_level = str(shard.get("claim_level") or "")
        no_provider_launch = shard.get("no_provider_launch") is True
        operator_gate = shard.get("operator_gate", {}) if isinstance(shard.get("operator_gate"), dict) else {}
        gate_required = operator_gate.get("required") is True
        gate_authorized = operator_gate.get("authorized") is True
        budget = shard.get("budget", {}) if isinstance(shard.get("budget"), dict) else {}
        max_spend = as_number(budget.get("max_spend_usd"))

        if not shard_id:
            errors.append(f"shards[{position}] missing shard_id")
        elif shard_id in ids:
            errors.append(f"duplicate shard_id in ledger: {shard_id}")
        else:
            ids.add(shard_id)
        shard_index = shard.get("shard_index")
        if isinstance(shard_index, int):
            if shard_index in indexes:
                errors.append(f"duplicate shard_index in ledger: {shard_index}")
            indexes.add(shard_index)
        if not provider:
            errors.append(f"shard {shard_id or position} missing provider")
        provider_counts[provider or "missing"] += 1
        status_counts[status or "missing"] += 1

        if closeout_status == "closeout_ready":
            closeout_ready_count += 1
        if closeout_status in {"blocked", "closed_blocked", "planned", "operator_gate_pending"} or status in {"planned", "blocked"}:
            blocked_or_planned_count += 1

        if no_provider_launch and closeout_status == "closeout_ready":
            errors.append(f"shard {shard_id} cannot be closeout_ready with no_provider_launch true")
        if no_provider_launch and status not in {"planned", "blocked", "closed_blocked", "skipped", "dry_run"}:
            warnings.append(f"shard {shard_id} is no_provider_launch but status is {status or 'missing'}")
        if no_provider_launch and max_spend not in {None, 0.0}:
            warnings.append(f"shard {shard_id} dry-run budget max_spend_usd is {max_spend}")
        mutating_or_paid = not no_provider_launch or status in READY_STATUSES or closeout_status == "closeout_ready"
        if mutating_or_paid and is_paid_provider(provider) and not gate_required:
            errors.append(f"shard {shard_id} paid/provider route must declare operator_gate.required true")
        if mutating_or_paid and gate_required and not gate_authorized:
            errors.append(f"shard {shard_id} requires operator gate before provider-mutating closeout")
        if closeout_status == "closeout_ready" and not (
            shard.get("artifact_root") or shard.get("artifact_pull_report") or shard.get("provider_run_path")
        ):
            errors.append(f"shard {shard_id} closeout_ready lacks artifact/provider evidence pointer")
        if normalize_status(shard.get("desired_status")) in INTENT_ONLY_STATES and not shard.get("actual_status"):
            errors.append(f"shard {shard_id} records desired_status intent without actual_status")
        if claim_level in CLAIM_LEVELS_REQUIRING_REAL_EVIDENCE and evidence_mode != "provider_native":
            errors.append(f"shard {shard_id} {claim_level} claim requires provider_native evidence")
        if execution_mode == "real" and closeout_status in {"", "planned", "operator_gate_pending"}:
            warnings.append(f"shard {shard_id} is not closed in real closeout mode")

    summary["providers"] = dict(sorted(provider_counts.items()))
    summary["statuses"] = dict(sorted(status_counts.items()))
    summary["closeout_ready_shards"] = closeout_ready_count
    summary["blocked_or_planned_shards"] = blocked_or_planned_count

    aggregation_policy = ledger.get("aggregation_policy", {})
    if isinstance(aggregation_policy, dict):
        if aggregation_policy.get("provider_success_is_not_scientific_success") is not True:
            errors.append("aggregation_policy.provider_success_is_not_scientific_success must be true")
        if aggregation_policy.get("canary_required_before_fanout") is not True:
            warnings.append("aggregation_policy.canary_required_before_fanout should be true")
    else:
        warnings.append("shard ledger missing aggregation_policy")

    return summary, errors, warnings


def evaluate_closeout(args: argparse.Namespace) -> dict[str, Any]:
    errors: list[str] = []
    warnings: list[str] = []

    provider_run: dict[str, Any] = {}
    provider_run_summary: dict[str, Any] = {"present": False}
    provider = ""
    closeout_ready_requested = False
    if args.provider_run:
        provider_run_path = resolve_path(args.provider_run)
        provider_run = load_json(provider_run_path)
        if not isinstance(provider_run, dict):
            errors.append("provider-run JSON must be an object")
            provider_run = {}
        else:
            provider_run_summary, provider_errors, provider_warnings = check_provider_run(provider_run, args.execution_mode)
            provider_run_summary["path"] = repo_relative(provider_run_path)
            provider_run_summary["present"] = True
            errors.extend(provider_errors)
            warnings.extend(provider_warnings)
            provider = provider_run_summary.get("provider") or ""
            closeout_ready_requested = bool(provider_run_summary.get("closeout_ready_requested"))

    launch_packet = load_launch_packet(args.launch_packet)
    if not provider and launch_packet:
        provider = str(launch_packet.get("provider") or "")

    artifact_root_summary: dict[str, Any] = {"present": False}
    artifact_checks: list[dict[str, Any]] = []
    stage_summary: dict[str, Any] = {}
    pull_summary: dict[str, Any] = {}
    cost_summary: dict[str, Any] = {}
    cleanup_summary: dict[str, Any] = {}
    hash_summary: dict[str, Any] = {}
    required_artifacts: list[str] = []

    if args.artifact_root:
        artifact_root = resolve_path(args.artifact_root)
        artifact_root_summary = {"path": repo_relative(artifact_root), "present": artifact_root.exists()}
        if not artifact_root.exists():
            errors.append(f"artifact root does not exist: {repo_relative(artifact_root)}")
        else:
            required_artifacts = closeout_required_artifacts(
                launch_packet=launch_packet,
                user_required=args.required_artifact,
                provider=provider,
                execution_mode=args.execution_mode,
            )
            artifact_checks, artifact_errors, artifact_warnings = check_artifacts(artifact_root, required_artifacts)
            errors.extend(artifact_errors)
            warnings.extend(artifact_warnings)
            stage_summary, stage_errors, stage_warnings = check_stage_progress(
                artifact_root,
                args.execution_mode,
                closeout_ready_requested,
            )
            errors.extend(stage_errors)
            warnings.extend(stage_warnings)
            pull_summary, pull_errors, pull_warnings = check_artifact_pull_report(artifact_root, args.execution_mode)
            errors.extend(pull_errors)
            warnings.extend(pull_warnings)
            paid_provider = is_paid_provider(provider)
            cost_summary, cost_errors, cost_warnings = check_cost_report(artifact_root, paid_provider, args.execution_mode)
            errors.extend(cost_errors)
            warnings.extend(cost_warnings)
            cleanup_summary, cleanup_errors, cleanup_warnings = check_cleanup_proof(artifact_root, paid_provider, args.execution_mode)
            errors.extend(cleanup_errors)
            warnings.extend(cleanup_warnings)
            hash_summary = check_hash_evidence(artifact_root, artifact_checks)

    shard_summary: dict[str, Any] = {"present": False}
    if args.shard_ledger:
        ledger_path = resolve_path(args.shard_ledger)
        shard_summary, shard_errors, shard_warnings = validate_shard_ledger(ledger_path, args.execution_mode)
        shard_summary["present"] = True
        errors.extend(shard_errors)
        warnings.extend(shard_warnings)

    if not any([args.provider_run, args.artifact_root, args.shard_ledger]):
        errors.append("provide at least one of --provider-run, --artifact-root, or --shard-ledger")

    closeout_ready = not errors and (
        closeout_ready_requested
        or (bool(args.artifact_root) and args.execution_mode == "real")
        or shard_summary.get("closeout_ready_shards", 0) > 0
    )
    if args.execution_mode == "prep" and not closeout_ready:
        closeout_status = "prep_valid"
    elif closeout_ready:
        closeout_status = "closeout_ready"
    elif errors:
        closeout_status = "blocked"
    else:
        closeout_status = "insufficient_evidence"

    return {
        "ok": not errors,
        "check_type": "provider_closeout_check",
        "execution_mode": args.execution_mode,
        "provider": provider or None,
        "closeout_ready": closeout_ready,
        "closeout_status": closeout_status,
        "provider_run": provider_run_summary,
        "artifact_root": artifact_root_summary,
        "required_artifacts": required_artifacts,
        "artifact_checks": artifact_checks,
        "stage_progress": stage_summary,
        "artifact_pull_report": pull_summary,
        "cost_report": cost_summary,
        "cleanup_proof": cleanup_summary,
        "hash_evidence": hash_summary,
        "shard_ledger": shard_summary,
        "errors": errors,
        "warnings": warnings,
    }


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--provider-run", type=Path, help="Local provider-run JSON record to validate")
    parser.add_argument("--artifact-root", type=Path, help="Local pulled artifact root to validate")
    parser.add_argument("--launch-packet", type=Path, help="Optional provider adapter launch packet for required artifacts")
    parser.add_argument("--shard-ledger", type=Path, help="Cloud shard ledger JSON or JSONL to validate")
    parser.add_argument(
        "--required-artifact",
        action="append",
        default=[],
        help="Additional artifact path required under --artifact-root; may be passed multiple times",
    )
    parser.add_argument("--execution-mode", choices=["prep", "real"], default="real")
    parser.add_argument("--out", type=Path, help="Optional JSON report path")
    parser.add_argument("--json", action="store_true")
    args = parser.parse_args()

    try:
        summary = evaluate_closeout(args)
    except Exception as exc:
        summary = {
            "ok": False,
            "check_type": "provider_closeout_check",
            "execution_mode": args.execution_mode,
            "closeout_ready": False,
            "closeout_status": "blocked",
            "errors": [f"{type(exc).__name__}: {exc}"],
            "warnings": [],
        }

    if args.out:
        write_json(resolve_path(args.out), summary)
    if args.json:
        print(json.dumps(summary, indent=2, sort_keys=True))
    else:
        print(f"ok: {summary['ok']}")
        print(f"closeout_status: {summary.get('closeout_status')}")
        for warning in summary.get("warnings", []):
            print(f"warning: {warning}")
        for error in summary.get("errors", []):
            print(f"error: {error}")
    return 0 if summary["ok"] else 1


if __name__ == "__main__":
    raise SystemExit(main())
