#!/usr/bin/env python3
"""Final evidence join check for Structure Factory runs.

This script is the "no false success" gate. It validates that declared inputs,
execution profile, runtime artifacts, mock labels, and claim evidence line up.
"""

from __future__ import annotations

import argparse
import json
from pathlib import Path
from typing import Any


def find_repo_root(start: Path) -> Path:
    for parent in [start.resolve().parent, *start.resolve().parents]:
        if (parent / "modules" / "artifact-contracts" / "structure-report.v1.json").exists():
            return parent
    return start.resolve().parents[2]


ROOT = find_repo_root(Path(__file__))
CONTRACT_PATH = ROOT / "modules" / "artifact-contracts" / "structure-report.v1.json"

PROFILE_REQUIREMENTS = {
    "no-download-smoke": "required_for_smoke",
    "raw-subset-open": "required_for_raw_subset_demo",
    "raw-subset-gated": "required_for_raw_subset_demo",
    "map-model-report": "required_for_map_model_report",
}

VALID_CLAIM_LEVELS = {
    "candidate",
    "processed",
    "validated",
    "publishable",
    "insufficient_evidence",
    "blocked",
}

DISALLOWED_REAL_EVIDENCE_MARKERS = {
    "mock",
    "fixture",
    "dry_run",
    "provider_search",
    "reference_only",
    "metadata_only",
    "target_placeholder",
    "target_species_placeholder",
    "planned_not_downloaded_by_scaffold",
}

MISSING_EVIDENCE_VALUES = {
    "",
    "not_available",
    "not_computed",
    "not_computed_without map download",
    "screenshot_only",
}


def load_json(path: Path) -> dict[str, Any]:
    return json.loads(path.read_text())


def maybe_load_json(path: Path) -> dict[str, Any]:
    if not path.exists():
        return {}
    try:
        return load_json(path)
    except json.JSONDecodeError:
        return {}


def load_jsonl(path: Path) -> list[dict[str, Any]]:
    rows: list[dict[str, Any]] = []
    if not path.exists():
        return rows
    for line in path.read_text().splitlines():
        if not line.strip():
            continue
        try:
            rows.append(json.loads(line))
        except json.JSONDecodeError:
            rows.append({"_parse_error": True})
    return rows


def has_true_marker(value: Any, markers: set[str]) -> bool:
    if isinstance(value, dict):
        for key, child in value.items():
            if key in markers and child is True:
                return True
            if has_true_marker(child, markers):
                return True
    elif isinstance(value, list):
        return any(has_true_marker(child, markers) for child in value)
    return False


def has_disallowed_real_evidence(value: Any) -> bool:
    if isinstance(value, dict):
        for key, child in value.items():
            key_text = str(key).lower()
            if key_text in DISALLOWED_REAL_EVIDENCE_MARKERS and child in {True, "true", "yes", "1"}:
                return True
            if isinstance(child, str) and child.lower() in DISALLOWED_REAL_EVIDENCE_MARKERS:
                return True
            if has_disallowed_real_evidence(child):
                return True
    elif isinstance(value, list):
        return any(has_disallowed_real_evidence(child) for child in value)
    elif isinstance(value, str):
        return value.lower() in DISALLOWED_REAL_EVIDENCE_MARKERS
    return False


def is_missing_evidence(value: Any) -> bool:
    if value is None:
        return True
    if isinstance(value, str):
        return value.strip().lower() in MISSING_EVIDENCE_VALUES
    if isinstance(value, dict):
        return not value
    if isinstance(value, list):
        return not value
    return False


def required_key_for_profile(execution_profile: str) -> str:
    return PROFILE_REQUIREMENTS.get(execution_profile, "required_for_full_report")


def artifact_path(root: Path, rel: str) -> Path:
    return root / rel.rstrip("/")


def check_required_artifacts(root: Path, required: list[str]) -> list[str]:
    errors: list[str] = []
    for rel in required:
        path = artifact_path(root, rel)
        if rel.endswith("/"):
            if not path.is_dir():
                errors.append(f"required artifact directory missing: {rel}")
        elif not path.is_file():
            errors.append(f"required artifact file missing: {rel}")
    return errors


def check_expected_artifacts(manifest: dict[str, Any], root: Path) -> list[str]:
    errors: list[str] = []
    run_id = manifest.get("run_id")
    run_prefix = f"/workspace/structure-factory/runs/{run_id}/"
    for expected in manifest.get("expected_artifacts", []):
        expected_str = str(expected)
        if expected_str.endswith("/validation/contract-self-check.json") or expected_str.endswith("/validation/stage-contract-check.json"):
            # These reports are emitted by closeout checks after artifact checks run.
            continue
        if expected_str.startswith(run_prefix):
            local = root / expected_str.removeprefix(run_prefix)
        else:
            # Nonstandard paths must still be visible under the artifact root by basename.
            local = root / Path(expected_str).name
        if not local.exists():
            errors.append(f"manifest expected_artifact missing from artifact_root: {expected_str}")
    return errors


def check_raw_join(manifest: dict[str, Any], root: Path) -> list[str]:
    errors: list[str] = []
    plan = manifest.get("download_plan", {})
    ledger = maybe_load_json(root / "data-intake-ledger.json")
    if not ledger:
        return errors
    required_fields = [
        "accession",
        "source_url",
        "subset_profile",
        "deterministic_rule",
        "download_method",
        "storage_path",
        "file_count",
        "checksum_policy",
        "allow_processed_inputs",
    ]
    for field in required_fields:
        if field not in ledger:
            errors.append(f"data-intake-ledger missing {field}")
    expected_subset = plan.get("subset_profile")
    if expected_subset and ledger.get("subset_profile") != expected_subset:
        errors.append(f"data-intake-ledger subset_profile does not match manifest: {ledger.get('subset_profile')} != {expected_subset}")
    if plan.get("deterministic_rule") and ledger.get("deterministic_rule") != plan.get("deterministic_rule"):
        errors.append("data-intake-ledger deterministic_rule does not match manifest")
    file_count = ledger.get("file_count")
    max_files = plan.get("max_files")
    if isinstance(max_files, int) and isinstance(file_count, int) and file_count > max_files:
        errors.append(f"data-intake-ledger file_count exceeds manifest max_files: {file_count} > {max_files}")
    if ledger.get("allow_processed_inputs") is not False:
        errors.append("data-intake-ledger must record allow_processed_inputs false")
    return errors


def check_validation_ledger(root: Path, required: bool) -> list[str]:
    errors: list[str] = []
    md_path = root / "validation_ledger.md"
    json_path = root / "validation_ledger.json"
    if not md_path.exists() and not json_path.exists():
        if required:
            errors.append("validation ledger missing")
        return errors
    if json_path.exists():
        payload = maybe_load_json(json_path)
        claims = payload.get("claims", [])
        if not isinstance(claims, list) or not claims:
            errors.append("validation_ledger.json must contain non-empty claims list")
        for index, claim in enumerate(claims):
            level = claim.get("claim_level")
            if level not in VALID_CLAIM_LEVELS:
                errors.append(f"claim {index} has invalid claim_level: {level}")
            if not claim.get("evidence_artifact"):
                errors.append(f"claim {index} missing evidence_artifact")
    else:
        text = md_path.read_text().lower()
        if not any(level in text for level in VALID_CLAIM_LEVELS):
            errors.append("validation_ledger.md must include explicit result boundarys")
    return errors


def check_map_model_validation(root: Path, real_required: bool) -> list[str]:
    errors: list[str] = []
    path = root / "validation" / "map_model_fit.json"
    if not path.exists():
        return errors
    payload = maybe_load_json(path)
    required_keys = [
        "pixel_size_angstrom",
        "map_model_correlation",
        "local_resolution",
        "mask_provenance",
        "handedness_check",
        "geometry_validation",
    ]
    for key in required_keys:
        if key not in payload:
            errors.append(f"map_model_fit.json missing {key}")
    if real_required and has_disallowed_real_evidence(payload):
        errors.append("real map/model validation cannot pass with mock/fixture/dry-run/reference-only/metadata-only evidence markers")
    if real_required:
        fsc = payload.get("fsc_provenance")
        if is_missing_evidence(fsc):
            errors.append("real map/model validation requires fsc_provenance, not screenshot-only evidence")
        elif isinstance(fsc, dict):
            if is_missing_evidence(fsc.get("source")):
                errors.append("fsc_provenance must include a source")
            fsc_values = [
                fsc.get("author_fsc_0_143"),
                fsc.get("calculated_fsc_0_143"),
                fsc.get("reported_resolution"),
            ]
            if all(is_missing_evidence(value) for value in fsc_values):
                errors.append("fsc_provenance must include an FSC or resolution value")
        for key in ["map_model_correlation", "geometry_validation"]:
            value = payload.get(key)
            if is_missing_evidence(value):
                errors.append(f"real map/model validation requires computed {key}")
        correlation = payload.get("map_model_correlation")
        if isinstance(correlation, dict):
            if is_missing_evidence(correlation.get("value")):
                errors.append("map_model_correlation must include a computed value")
            try:
                sampled_atoms = int(correlation.get("sampled_atom_count", 0))
            except (TypeError, ValueError):
                sampled_atoms = 0
            if sampled_atoms <= 0:
                errors.append("map_model_correlation must include sampled_atom_count > 0")
    return errors


def expected_accessions(manifest: dict[str, Any]) -> dict[str, str]:
    accessions: dict[str, str] = {}
    for key in ["pdb", "pdb_id", "pdb_accession"]:
        if manifest.get(key):
            accessions["pdb"] = str(manifest[key]).upper()
    for key in ["emdb", "emdb_id", "emdb_accession"]:
        if manifest.get(key):
            accessions["emdb"] = str(manifest[key]).upper()
    nested = manifest.get("accessions", {})
    if isinstance(nested, dict):
        if nested.get("pdb"):
            accessions["pdb"] = str(nested["pdb"]).upper()
        if nested.get("emdb"):
            accessions["emdb"] = str(nested["emdb"]).upper()
    data_module = manifest.get("data_module", {})
    if isinstance(data_module, dict):
        nested = data_module.get("accessions", {})
        if isinstance(nested, dict):
            if nested.get("pdb"):
                accessions["pdb"] = str(nested["pdb"]).upper()
            if nested.get("emdb"):
                accessions["emdb"] = str(nested["emdb"]).upper()
    return accessions


def check_input_audit_join(manifest: dict[str, Any], root: Path, real_required: bool) -> list[str]:
    errors: list[str] = []
    if not real_required:
        return errors
    audit = maybe_load_json(root / "validation" / "input-audit.json")
    if not audit:
        errors.append("validation/input-audit.json missing")
        return errors
    if audit.get("ok") is not True:
        errors.append("validation/input-audit.json does not report ok true")
    if audit.get("missing_operator_items"):
        errors.append("real execution cannot close with missing_operator_items in input audit")
    accessions = expected_accessions(manifest)
    known_text = json.dumps(audit.get("known_inputs", audit), sort_keys=True).upper()
    for label, accession in accessions.items():
        if accession and accession not in known_text:
            errors.append(f"input audit does not include declared {label} accession {accession}")
    return errors


def check_data_intake_join(manifest: dict[str, Any], root: Path, real_required: bool) -> list[str]:
    errors: list[str] = []
    ledger = maybe_load_json(root / "data-intake-ledger.json")
    if not ledger:
        if real_required:
            errors.append("data-intake-ledger.json missing")
        return errors
    accessions = expected_accessions(manifest)
    ledger_text = json.dumps(ledger, sort_keys=True).upper()
    for label, accession in accessions.items():
        if accession and accession not in ledger_text:
            errors.append(f"data-intake-ledger does not join declared {label} accession {accession}")
    if real_required:
        if ledger.get("status") not in {"downloaded", "materialized", "completed"}:
            errors.append(f"real execution requires materialized/downloaded data-intake-ledger status, got {ledger.get('status')}")
        if has_disallowed_real_evidence(ledger):
            errors.append("real execution cannot pass with mock/fixture/dry-run/reference-only data-intake-ledger evidence")
        materialized = ledger.get("materialized_files") or ledger.get("files") or []
        if not isinstance(materialized, list) or not materialized:
            errors.append("data-intake-ledger must list materialized files")
        for index, item in enumerate(materialized if isinstance(materialized, list) else []):
            if not isinstance(item, dict):
                errors.append(f"data-intake-ledger materialized_files[{index}] must be an object")
                continue
            for key in ["path", "sha256", "bytes"]:
                if item.get(key) in {None, ""}:
                    errors.append(f"data-intake-ledger materialized_files[{index}] missing {key}")
    return errors


def check_executed_commands(root: Path, real_required: bool) -> list[str]:
    errors: list[str] = []
    path = root / "executed-commands.jsonl"
    if not path.exists():
        if real_required:
            errors.append("executed-commands.jsonl missing")
        return errors
    rows: list[dict[str, Any]] = []
    for line_number, line in enumerate(path.read_text().splitlines(), start=1):
        if not line.strip():
            continue
        try:
            row = json.loads(line)
        except json.JSONDecodeError:
            errors.append(f"executed-commands.jsonl line {line_number} is not valid JSON")
            continue
        rows.append(row)
    if real_required and not rows:
        errors.append("executed-commands.jsonl has no command records")
    for index, row in enumerate(rows):
        if not row.get("stage_id"):
            errors.append(f"executed command {index} missing stage_id")
        if not row.get("command"):
            errors.append(f"executed command {index} missing command")
        if row.get("exit_code") != 0:
            errors.append(f"executed command {index} did not exit 0")
        if not row.get("outputs"):
            errors.append(f"executed command {index} missing outputs")
        if real_required and has_disallowed_real_evidence(row):
            errors.append(f"executed command {index} contains mock/fixture/dry-run/reference-only marker")
    return errors


def check_stage_progress(manifest: dict[str, Any], root: Path, real_required: bool) -> list[str]:
    errors: list[str] = []
    if not manifest.get("stage_contract"):
        return errors
    progress_path = root / "stage-progress.jsonl"
    stage_report_path = root / "validation" / "stage-contract-check.json"
    if not progress_path.exists():
        errors.append("stage-progress.jsonl missing")
    if not stage_report_path.exists():
        return errors
    payload = maybe_load_json(stage_report_path)
    if payload.get("ok") is not True:
        errors.append("validation/stage-contract-check.json does not report ok true")
    if real_required:
        if payload.get("require_terminal") is not True:
            errors.append("real execution requires terminal stage-contract check")
        terminal = payload.get("terminal_by_stage", {})
        if not isinstance(terminal, dict) or not terminal:
            errors.append("real execution requires terminal stage progress")
        elif any(status != "completed" for status in terminal.values()):
            errors.append("real execution stage progress contains non-completed terminal status")
    return errors


def check_partial_summary(root: Path) -> list[str]:
    errors: list[str] = []
    events = load_jsonl(root / "stage-progress.jsonl")
    if not events:
        return errors
    partial_or_failed = [
        event for event in events
        if event.get("status") in {"failed", "partial"} or event.get("fallback_used") is True
    ]
    if not partial_or_failed:
        return errors
    summary = maybe_load_json(root / "partial-summary.json")
    if not summary:
        errors.append("partial-summary.json is required when any stage fails, closes partial, or uses fallback")
        return errors
    for key in ["completed_stages", "failed_stage", "resume_command", "artifact_status", "claim_level"]:
        if key not in summary:
            errors.append(f"partial-summary.json missing {key}")
    if str(summary.get("claim_level", "")).lower() not in {"partial", "degraded", "blocked", "failed", "insufficient_evidence"}:
        errors.append("partial-summary.json claim_level must be partial/degraded/blocked/failed/insufficient_evidence")
    return errors


def check_fanout_estimate(manifest: dict[str, Any], root: Path, real_required: bool) -> list[str]:
    errors: list[str] = []
    execution_profile = manifest.get("execution_profile") or manifest.get("environment", {}).get("STRUCTURE_FACTORY_EXECUTION_PROFILE")
    if execution_profile not in {"raw-subset-open", "raw-subset-gated"}:
        return errors
    path = root / "validation" / "fanout-estimate.json"
    if not path.exists():
        if real_required:
            errors.append("validation/fanout-estimate.json missing")
        return errors
    payload = maybe_load_json(path)
    if payload.get("ok") is not True:
        errors.append("validation/fanout-estimate.json does not report ok true")
    if payload.get("blockers"):
        errors.append("fanout estimate contains blockers")
    if payload.get("execution_profile") != execution_profile:
        errors.append(f"fanout execution_profile mismatch: {payload.get('execution_profile')} != {execution_profile}")
    estimates = payload.get("estimates", {})
    max_files = manifest.get("download_plan", {}).get("max_files")
    if isinstance(estimates, dict) and isinstance(max_files, int):
        raw_files = estimates.get("raw_movie_files")
        if isinstance(raw_files, int) and raw_files > max_files:
            errors.append(f"fanout raw_movie_files exceeds manifest max_files: {raw_files} > {max_files}")
    success_policy = payload.get("success_policy", {})
    if success_policy.get("raw_tool_outputs_must_be_normalized") is not True:
        errors.append("fanout success_policy must require normalized deliverables, not raw tool output only")
    return errors


def check_no_silent_fallback(root: Path, payloads: list[dict[str, Any]]) -> list[str]:
    errors: list[str] = []
    fallback_markers = {
        "fallback_used",
        "provider_fallback",
        "teammate_fallback",
        "subagent_fallback",
        "route_fallback",
        "rescue_route",
    }
    silent_markers = {"silent_fallback", "unreported_fallback"}
    accepted_statuses = {"partial", "degraded", "blocked", "failed"}

    fallback_ledger = maybe_load_json(root / "validation" / "fallback-ledger.json")
    if fallback_ledger:
        payloads = [*payloads, fallback_ledger]

    fallback_detected = any(has_true_marker(payload, fallback_markers) for payload in payloads)
    silent_detected = any(has_true_marker(payload, silent_markers) for payload in payloads)
    if silent_detected:
        errors.append("silent fallback marker detected; final status must be explicit and degraded")
    if fallback_detected:
        statuses = {
            str(payload.get(key, "")).lower()
            for payload in payloads
            for key in ["final_status", "outcome_status", "closeout_status", "claim_status"]
            if payload.get(key)
        }
        if not statuses.intersection(accepted_statuses):
            errors.append("fallback was used but final status was not partial/degraded/blocked/failed")
    return errors


def self_check(manifest_path: Path, artifact_root: Path, execution_mode: str) -> dict[str, Any]:
    manifest = load_json(manifest_path)
    contract = load_json(CONTRACT_PATH)
    execution_profile = manifest.get("execution_profile") or manifest.get("environment", {}).get("STRUCTURE_FACTORY_EXECUTION_PROFILE")
    requirement_key = required_key_for_profile(str(execution_profile))
    required = contract.get(requirement_key, [])
    errors: list[str] = []
    warnings: list[str] = []

    errors.extend(check_required_artifacts(artifact_root, required))
    errors.extend(check_expected_artifacts(manifest, artifact_root))

    run_manifest = maybe_load_json(artifact_root / "run-manifest.json")
    toolcheck = maybe_load_json(artifact_root / "validation" / "toolcheck.json")
    gpu = maybe_load_json(artifact_root / "validation" / "gpu.json")
    storage = maybe_load_json(artifact_root / "validation" / "storage.json")
    stage_report = maybe_load_json(artifact_root / "validation" / "stage-contract-check.json")

    if run_manifest and run_manifest.get("run_id") != manifest.get("run_id"):
        errors.append(f"run-manifest run_id does not match launch manifest: {run_manifest.get('run_id')} != {manifest.get('run_id')}")
    if toolcheck and toolcheck.get("ok") is not True:
        errors.append("validation/toolcheck.json does not report ok true")
    if gpu and gpu.get("ok") is not True:
        errors.append("validation/gpu.json does not report ok true")
    if storage and storage.get("ok") is not True:
        errors.append("validation/storage.json does not report ok true")

    mock_markers = {"mock_gpu", "mock_tools", "dry_run"}
    mock_detected = any(has_true_marker(payload, mock_markers) for payload in [run_manifest, toolcheck, gpu, storage])
    if mock_detected and execution_mode == "real":
        errors.append("real execution cannot pass with mock_gpu/mock_tools/dry_run markers")
    elif mock_detected:
        warnings.append("mock or dry-run markers are present; this can only satisfy prep evidence")

    errors.extend(check_stage_progress(manifest, artifact_root, real_required=execution_mode == "real"))
    errors.extend(check_partial_summary(artifact_root))
    errors.extend(check_no_silent_fallback(artifact_root, [run_manifest, toolcheck, gpu, storage, stage_report]))

    if execution_profile in {"raw-subset-open", "raw-subset-gated"}:
        errors.extend(check_fanout_estimate(manifest, artifact_root, real_required=execution_mode == "real"))
        errors.extend(check_raw_join(manifest, artifact_root))
        ledger = maybe_load_json(artifact_root / "data-intake-ledger.json")
        if execution_mode == "real" and ledger.get("status") in {"planned_not_downloaded_by_scaffold", "dry_run", "mock"}:
            errors.append("real raw-subset execution cannot pass with planned/mock data-intake-ledger status")
    if execution_profile == "map-model-report":
        errors.extend(check_input_audit_join(manifest, artifact_root, real_required=execution_mode == "real"))
        errors.extend(check_data_intake_join(manifest, artifact_root, real_required=execution_mode == "real"))
        errors.extend(check_executed_commands(artifact_root, real_required=execution_mode == "real"))
        errors.extend(check_validation_ledger(artifact_root, required=True))
        errors.extend(check_map_model_validation(artifact_root, real_required=execution_mode == "real"))
    if execution_profile not in {"no-download-smoke", "raw-subset-open", "raw-subset-gated", "map-model-report"}:
        errors.extend(check_validation_ledger(artifact_root, required=True))
        errors.extend(check_map_model_validation(artifact_root, real_required=execution_mode == "real"))

    return {
        "ok": not errors,
        "check_type": "structure_factory_contract_self_check",
        "execution_mode": execution_mode,
        "execution_profile": execution_profile,
        "manifest_path": str(manifest_path.resolve()),
        "artifact_root": str(artifact_root.resolve()),
        "requirement_key": requirement_key,
        "required_artifacts_checked": required,
        "errors": errors,
        "warnings": warnings,
    }


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--manifest", type=Path, required=True)
    parser.add_argument("--artifact-root", type=Path, required=True)
    parser.add_argument("--execution-mode", choices=["prep", "real"], default="prep")
    parser.add_argument("--out", type=Path, help="Defaults to <artifact-root>/validation/contract-self-check.json")
    parser.add_argument("--json", action="store_true")
    args = parser.parse_args()

    summary = self_check(args.manifest, args.artifact_root, args.execution_mode)
    out = args.out or args.artifact_root / "validation" / "contract-self-check.json"
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text(json.dumps(summary, indent=2, sort_keys=True) + "\n")
    summary["report_path"] = str(out.resolve())

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
