#!/usr/bin/env python3
"""Validate Structure Factory screening manifests and fixture inputs."""

from __future__ import annotations

import argparse
import json
from pathlib import Path
from typing import Any


REQUIRED_TOP_LEVEL = {
    "schema_version",
    "manifest_type",
    "campaign_id",
    "run_id",
    "intent",
    "target",
    "ligand_library",
    "receptor_ensemble",
    "methods",
    "provider_plan",
    "budget",
    "outputs",
    "policies",
}
VALID_CLAIM_LEVELS = {"candidate", "processed", "validated", "publishable", "insufficient_evidence", "blocked"}
GATED_METHODS = {"gnina", "diffdock", "alphafold3", "chai", "phenix", "chimerax", "cryosparc"}


def load_json(path: Path) -> dict[str, Any]:
    return json.loads(path.read_text())


def repo_root_for(path: Path) -> Path:
    resolved = path.resolve()
    for parent in [resolved.parent, *resolved.parents]:
        if (parent / "modules").is_dir() and (parent / "scripts").is_dir():
            return parent
    return resolved.parents[2]


def rel_path(root: Path, value: str) -> Path:
    path = Path(value)
    return path if path.is_absolute() else root / path


def validate_ligand_library(path: Path) -> tuple[list[str], dict[str, Any]]:
    errors: list[str] = []
    try:
        data = load_json(path)
    except Exception as exc:
        return [f"could not read ligand library: {type(exc).__name__}: {exc}"], {}
    ligands = data.get("ligands")
    if not isinstance(ligands, list) or not ligands:
        errors.append("ligand library must contain a non-empty ligands list")
        return errors, data
    seen: set[str] = set()
    for index, ligand in enumerate(ligands):
        if not isinstance(ligand, dict):
            errors.append(f"ligand {index} must be object")
            continue
        ligand_id = ligand.get("ligand_id")
        smiles = ligand.get("smiles")
        if not isinstance(ligand_id, str) or not ligand_id:
            errors.append(f"ligand {index} missing ligand_id")
        elif ligand_id in seen:
            errors.append(f"duplicate ligand_id: {ligand_id}")
        seen.add(str(ligand_id))
        if not isinstance(smiles, str) or not smiles:
            errors.append(f"ligand {ligand_id or index} missing smiles")
    return errors, data


def validate_receptor_ensemble(path: Path) -> tuple[list[str], dict[str, Any]]:
    errors: list[str] = []
    try:
        data = load_json(path)
    except Exception as exc:
        return [f"could not read receptor ensemble: {type(exc).__name__}: {exc}"], {}
    members = data.get("members")
    if not isinstance(members, list) or not members:
        errors.append("receptor ensemble must contain a non-empty members list")
    site = data.get("site_definition")
    if not isinstance(site, dict) or not site.get("mode"):
        errors.append("receptor ensemble must define site_definition.mode")
    return errors, data


def validate_manifest(path: Path) -> dict[str, Any]:
    root = repo_root_for(path)
    errors: list[str] = []
    warnings: list[str] = []
    try:
        manifest = load_json(path)
    except Exception as exc:
        return {
            "ok": False,
            "manifest": str(path.resolve()),
            "errors": [f"invalid json: {type(exc).__name__}: {exc}"],
            "warnings": [],
        }

    for key in sorted(REQUIRED_TOP_LEVEL - set(manifest)):
        errors.append(f"missing top-level key: {key}")
    if manifest.get("schema_version") != 1:
        errors.append("schema_version must be 1")
    if manifest.get("manifest_type") != "screening_manifest":
        errors.append("manifest_type must be screening_manifest")
    if manifest.get("campaign_id") != "screening-superpowers":
        warnings.append("campaign_id is not screening-superpowers; treating as custom screening manifest")

    policies = manifest.get("policies", {})
    if policies.get("allow_private_data") is not False:
        errors.append("policies.allow_private_data must be false by default")
    if policies.get("allow_raw_cryoem_downloads") is not False:
        errors.append("policies.allow_raw_cryoem_downloads must be false for screening fixture")
    if policies.get("expected_download_bytes") != 0:
        errors.append("policies.expected_download_bytes must be 0 for no-download fixture")

    claim = manifest.get("intent", {}).get("claim_ceiling")
    if claim not in VALID_CLAIM_LEVELS:
        errors.append(f"intent.claim_ceiling must be one of {sorted(VALID_CLAIM_LEVELS)}")
    elif claim in {"validated", "publishable"} and manifest.get("provider_plan", {}).get("current_run_is_no_download_fixture") is True:
        errors.append("no-download fixture cannot request validated or publishable claim ceiling")

    ligand_ref = manifest.get("ligand_library", {}).get("path")
    receptor_ref = manifest.get("receptor_ensemble", {}).get("path")
    ligand_count = 0
    receptor_count = 0
    if isinstance(ligand_ref, str):
        ligand_path = rel_path(root, ligand_ref)
        if not ligand_path.exists():
            errors.append(f"ligand_library.path does not exist: {ligand_ref}")
        else:
            ligand_errors, ligand_data = validate_ligand_library(ligand_path)
            errors.extend(ligand_errors)
            ligand_count = len(ligand_data.get("ligands", [])) if isinstance(ligand_data.get("ligands"), list) else 0
    else:
        errors.append("ligand_library.path is required")

    if isinstance(receptor_ref, str):
        receptor_path = rel_path(root, receptor_ref)
        if not receptor_path.exists():
            errors.append(f"receptor_ensemble.path does not exist: {receptor_ref}")
        else:
            receptor_errors, receptor_data = validate_receptor_ensemble(receptor_path)
            errors.extend(receptor_errors)
            receptor_count = len(receptor_data.get("members", [])) if isinstance(receptor_data.get("members"), list) else 0
    else:
        errors.append("receptor_ensemble.path is required")

    methods = manifest.get("methods", {})
    always = set(methods.get("always", [])) if isinstance(methods.get("always"), list) else set()
    if "simple_affinity_baselines" not in always:
        errors.append("methods.always must include simple_affinity_baselines")
    gated_enabled = set(methods.get("enabled", [])) & GATED_METHODS if isinstance(methods.get("enabled"), list) else set()
    if gated_enabled and not manifest.get("provider_plan", {}).get("operator_gate_for_gated_tools"):
        errors.append(f"gated methods enabled without operator gate: {sorted(gated_enabled)}")

    budget = manifest.get("budget", {})
    max_ligands = budget.get("max_ligands")
    if not isinstance(max_ligands, int) or max_ligands <= 0:
        errors.append("budget.max_ligands must be a positive integer")
    elif ligand_count and max_ligands < ligand_count:
        warnings.append("budget.max_ligands is lower than ligand library size; fixture runner will truncate")
    if budget.get("max_spend_usd") != 0 and manifest.get("provider_plan", {}).get("current_run_is_no_download_fixture") is True:
        errors.append("no-download fixture max_spend_usd must be 0")

    return {
        "ok": not errors,
        "check_type": "screening_manifest_check",
        "manifest": str(path.resolve()),
        "ligand_count": ligand_count,
        "receptor_count": receptor_count,
        "errors": errors,
        "warnings": warnings,
    }


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("manifest", type=Path)
    parser.add_argument("--out", type=Path)
    parser.add_argument("--json", action="store_true")
    args = parser.parse_args()

    summary = validate_manifest(args.manifest)
    if args.out:
        args.out.parent.mkdir(parents=True, exist_ok=True)
        args.out.write_text(json.dumps(summary, indent=2, sort_keys=True) + "\n")
        summary["report_path"] = str(args.out.resolve())
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
