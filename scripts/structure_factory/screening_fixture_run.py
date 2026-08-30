#!/usr/bin/env python3
"""Run the no-download Screening Superpowers fixture.

This runner deliberately uses only the Python standard library. It proves the
contract, ledger, ranking, failure, and selective-report behavior without
claiming real docking, affinity, or structure prediction.
"""

from __future__ import annotations

import argparse
import csv
import hashlib
import json
import re
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from screening_manifest_check import load_json, rel_path, repo_root_for, validate_manifest


RANKING_FORMULA_VERSION = "screening_fixture_rank_v1"
VALID_SMILES_CHARS = re.compile(r"^[A-Za-z0-9@+\-\[\]\(\)=#$\\/%.]+$")
ELEMENT_WEIGHTS = {
    "C": 12.011,
    "N": 14.007,
    "O": 15.999,
    "S": 32.06,
    "P": 30.974,
    "F": 18.998,
    "Cl": 35.45,
    "Br": 79.904,
    "I": 126.904,
}


def utc_now() -> str:
    return datetime.now(timezone.utc).isoformat()


def write_json(path: Path, data: Any) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(data, indent=2, sort_keys=True) + "\n")


def append_jsonl(path: Path, records: list[dict[str, Any]]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text("".join(json.dumps(record, sort_keys=True) + "\n" for record in records))


def stable_float(*parts: str, low: float = 0.0, high: float = 1.0) -> float:
    digest = hashlib.sha256("|".join(parts).encode()).hexdigest()
    integer = int(digest[:12], 16)
    value = integer / float(0xFFFFFFFFFFFF)
    return round(low + value * (high - low), 4)


def smiles_tokens(smiles: str) -> list[str]:
    tokens: list[str] = []
    i = 0
    while i < len(smiles):
        if smiles[i : i + 2] in {"Cl", "Br"}:
            tokens.append(smiles[i : i + 2])
            i += 2
            continue
        char = smiles[i]
        if char.isalpha():
            tokens.append(char.upper())
        i += 1
    return tokens


def validate_smiles(smiles: str) -> tuple[bool, str]:
    if not smiles:
        return False, "empty_smiles"
    if "INVALID" in smiles.upper():
        return False, "contains_invalid_marker"
    if not VALID_SMILES_CHARS.match(smiles):
        return False, "unsupported_character"
    if smiles.count("(") != smiles.count(")"):
        return False, "unbalanced_parentheses"
    if smiles.count("[") != smiles.count("]"):
        return False, "unbalanced_brackets"
    return True, ""


def descriptor_record(ligand: dict[str, Any]) -> dict[str, Any]:
    smiles = str(ligand.get("smiles", ""))
    ok, reason = validate_smiles(smiles)
    tokens = smiles_tokens(smiles) if ok else []
    estimated_mw = round(sum(ELEMENT_WEIGHTS.get(token, 0.0) for token in tokens), 3)
    hetero = sum(1 for token in tokens if token in {"N", "O", "S", "P"})
    aromatic_proxy = smiles.count("c")
    clogp_proxy = round((smiles.count("C") + smiles.count("c") * 0.6 - hetero * 0.8) / 5.0, 3) if ok else None
    return {
        "schema_version": 1,
        "ligand_id": ligand.get("ligand_id"),
        "name": ligand.get("name"),
        "smiles": smiles,
        "known_class": ligand.get("known_class", "unknown"),
        "prep_status": "prepared" if ok else "failed",
        "failure_reason": reason,
        "estimated_mw": estimated_mw if ok else None,
        "heavy_atom_proxy": len(tokens) if ok else None,
        "hetero_atom_proxy": hetero if ok else None,
        "aromatic_proxy": aromatic_proxy if ok else None,
        "clogp_proxy": clogp_proxy,
        "descriptor_mode": "stdlib_fixture_proxy",
    }


def score_ligand(prep: dict[str, Any], receptors: list[dict[str, Any]], reference_smiles: str) -> tuple[list[dict[str, Any]], dict[str, Any]]:
    ligand_id = str(prep["ligand_id"])
    if prep["prep_status"] != "prepared":
        return [], {
            "schema_version": 1,
            "ligand_id": ligand_id,
            "method": "screening_fixture_ranker",
            "status": "failed",
            "reason": prep["failure_reason"],
        }

    smiles = str(prep["smiles"])
    ref_chars = set(reference_smiles)
    chars = set(smiles)
    tanimoto_proxy = round(len(chars & ref_chars) / max(1, len(chars | ref_chars)), 4)
    mw = float(prep["estimated_mw"] or 0.0)
    clogp = float(prep["clogp_proxy"] or 0.0)
    poses: list[dict[str, Any]] = []
    best_vina = 99.0
    best_pose_validity = 0.0
    for receptor in receptors:
        receptor_id = str(receptor.get("receptor_id", "unknown-receptor"))
        base = stable_float(ligand_id, receptor_id, "vina", low=-9.5, high=-4.0)
        ligand_efficiency = round(abs(base) / max(1.0, mw / 100.0), 4)
        pose_validity = stable_float(ligand_id, receptor_id, "posebusters", low=0.62, high=0.99)
        contact_iou = stable_float(ligand_id, receptor_id, "contacts", low=0.2, high=0.9)
        best_vina = min(best_vina, base)
        best_pose_validity = max(best_pose_validity, pose_validity)
        poses.append({
            "schema_version": 1,
            "ligand_id": ligand_id,
            "receptor_id": receptor_id,
            "method": "autodock_vina_fixture_proxy",
            "status": "completed",
            "vina_score_proxy": base,
            "ligand_efficiency_proxy": ligand_efficiency,
            "pose_validity_proxy": pose_validity,
            "pocket_contact_iou_proxy": contact_iou,
            "evidence_mode": "fixture_or_demo",
        })

    boltz_probability_proxy = stable_float(ligand_id, "boltz", "affinity_probability_binary", low=0.05, high=0.92)
    mw_baseline = round(max(0.0, min(1.0, 1.0 - abs(mw - 180.0) / 250.0)), 4)
    clogp_baseline = round(max(0.0, min(1.0, 1.0 - abs(clogp - 2.0) / 5.0)), 4)
    consensus = round(
        0.30 * tanimoto_proxy
        + 0.20 * mw_baseline
        + 0.15 * clogp_baseline
        + 0.20 * ((-best_vina - 4.0) / 5.5)
        + 0.15 * boltz_probability_proxy,
        4,
    )
    disagreement = round(max(abs(boltz_probability_proxy - tanimoto_proxy), abs(mw_baseline - clogp_baseline)), 4)
    affinity = {
        "schema_version": 1,
        "ligand_id": ligand_id,
        "method": "screening_fixture_method_comparison",
        "status": "completed",
        "molecular_weight_baseline": mw_baseline,
        "clogp_baseline": clogp_baseline,
        "similarity_to_reference_proxy": tanimoto_proxy,
        "best_vina_score_proxy": best_vina,
        "boltz_affinity_probability_proxy": boltz_probability_proxy,
        "method_disagreement_proxy": disagreement,
        "consensus_score": consensus,
        "claim_level": "candidate",
        "evidence_mode": "fixture_or_demo",
    }
    return poses, affinity


def stage_events(status: str = "completed") -> list[dict[str, Any]]:
    stages = [
        "manifest_preflight",
        "input_audit",
        "ligand_prep",
        "method_comparison",
        "ranking_and_validation_review",
    ]
    return [
        {
            "schema_version": 1,
            "timestamp": utc_now(),
            "stage_id": stage,
            "status": status,
            "message": f"{stage} {status} for no-download screening fixture",
        }
        for stage in stages
    ]


def run_fixture(manifest_path: Path, out: Path) -> dict[str, Any]:
    root = repo_root_for(manifest_path)
    check = validate_manifest(manifest_path)
    out.mkdir(parents=True, exist_ok=True)
    validation_dir = out / "validation"
    write_json(validation_dir / "screening-manifest-check.json", check)
    if not check["ok"]:
        write_json(out / "partial-summary.json", {
            "claim_level": "blocked",
            "failed_stage": "manifest_preflight",
            "artifact_status": "manifest_invalid",
            "completed_stages": [],
            "resume_command": f"python3 scripts/structure_factory/screening_fixture_run.py --manifest {manifest_path} --out {out} --json",
        })
        return {"ok": False, "out": str(out.resolve()), "errors": check["errors"]}

    manifest = load_json(manifest_path)
    ligand_data = load_json(rel_path(root, manifest["ligand_library"]["path"]))
    receptor_data = load_json(rel_path(root, manifest["receptor_ensemble"]["path"]))
    ligands = ligand_data["ligands"][: int(manifest["budget"]["max_ligands"])]
    receptors = receptor_data["members"]
    reference_id = receptor_data.get("site_definition", {}).get("reference_ligand_id")
    reference_smiles = next((ligand.get("smiles", "") for ligand in ligands if ligand.get("ligand_id") == reference_id), ligands[0]["smiles"])

    input_audit = {
        "schema_version": 1,
        "ok": True,
        "campaign_id": manifest["campaign_id"],
        "run_id": manifest["run_id"],
        "private_data_allowed": False,
        "raw_downloads_allowed": False,
        "expected_download_bytes": 0,
        "ligand_count": len(ligands),
        "receptor_member_count": len(receptors),
        "evidence_mode": "fixture_or_demo",
    }
    write_json(validation_dir / "input-audit.json", input_audit)
    write_json(out / "screening_manifest.json", manifest)
    write_json(out / "receptor_ensemble_manifest.json", receptor_data)

    prep_records = [descriptor_record(ligand) for ligand in ligands]
    append_jsonl(out / "ligand_prep.jsonl", prep_records)

    pose_records: list[dict[str, Any]] = []
    affinity_records: list[dict[str, Any]] = []
    failures: list[dict[str, Any]] = []
    for prep in prep_records:
        poses, affinity = score_ligand(prep, receptors, reference_smiles)
        if prep["prep_status"] != "prepared":
            failures.append({
                "ligand_id": prep["ligand_id"],
                "stage": "ligand_prep",
                "reason": prep["failure_reason"],
                "claim_level": "blocked",
            })
        pose_records.extend(poses)
        affinity_records.append(affinity)
    append_jsonl(out / "pose_predictions.jsonl", pose_records)
    append_jsonl(out / "affinity_predictions.jsonl", affinity_records)

    successful = [record for record in affinity_records if record["status"] == "completed"]
    successful.sort(key=lambda record: record["consensus_score"], reverse=True)
    with (out / "consensus_ranking.csv").open("w", newline="") as handle:
        writer = csv.DictWriter(
            handle,
            fieldnames=[
                "rank",
                "ligand_id",
                "consensus_score",
                "best_vina_score_proxy",
                "boltz_affinity_probability_proxy",
                "molecular_weight_baseline",
                "clogp_baseline",
                "similarity_to_reference_proxy",
                "method_disagreement_proxy",
                "claim_level",
                "evidence_mode",
            ],
        )
        writer.writeheader()
        for rank, record in enumerate(successful, start=1):
            row = {"rank": rank, **{key: record[key] for key in writer.fieldnames if key in record}}
            writer.writerow(row)

    promote_top_n = int(manifest.get("outputs", {}).get("promote_top_n", 2))
    report_dir = out / "candidate_reports"
    report_dir.mkdir(exist_ok=True)
    promoted = []
    for rank, record in enumerate(successful[:promote_top_n], start=1):
        report = {
            "schema_version": 1,
            "candidate_report_id": f"{manifest['run_id']}-{record['ligand_id']}",
            "candidate_report_id": f"{manifest['run_id']}-{record['ligand_id']}",
            "rank": rank,
            "ligand_id": record["ligand_id"],
            "selection_reason": "top_ranked_fixture_candidate",
            "source_screening_manifest": "screening_manifest.json",
            "candidate_evidence": record,
            "claim_level": "candidate",
            "evidence_mode": "fixture_or_demo",
            "caveat": "Deterministic fixture report; not real docking, affinity, or biological support.",
        }
        path = report_dir / f"{record['ligand_id']}.json"
        write_json(path, report)
        promoted.append(str(path.relative_to(out)))

    method_summary = {
        "schema_version": 1,
        "ranking_formula_version": RANKING_FORMULA_VERSION,
        "methods": {
            "stdlib_descriptor_proxy": {"status": "completed", "claim_role": "simple_baseline"},
            "autodock_vina_fixture_proxy": {"status": "completed", "claim_role": "wide_screen_proxy"},
            "boltz_affinity_probability_proxy": {"status": "completed", "claim_role": "focused_lane_proxy"},
            "gnina": {"status": "gated", "claim_role": "optional_review_required"},
            "diffdock": {"status": "gated", "claim_role": "optional_review_required"},
            "alphafold3": {"status": "runtime_gated", "claim_role": "optional_comparison"},
            "chimerax": {"status": "runtime_gated", "claim_role": "optional_visual_review"}
        },
        "openbind_style_calibration": {
            "separate_tasks": ["redocking_proxy", "cross_docking_proxy", "cofolding_proxy", "affinity_baselines"],
            "simple_baselines_included": ["molecular_weight", "clogp", "similarity_to_reference"],
            "note": "Fixture mirrors OpenBind-style evaluation shape without using OpenBind data or making scientific claims."
        },
    }
    write_json(out / "method_summary.json", method_summary)
    write_json(out / "failure_report.json", {
        "schema_version": 1,
        "failed_ligands": failures,
        "failure_count": len(failures),
        "invalid_smiles_degrades_cleanly": any(item["reason"] for item in failures),
    })
    write_json(out / "metrics.json", {
        "schema_version": 1,
        "ligands_total": len(ligands),
        "ligands_prepared": len(successful),
        "ligands_failed": len(failures),
        "receptor_members": len(receptors),
        "pose_records": len(pose_records),
        "top_ligand_id": successful[0]["ligand_id"] if successful else None,
        "top_consensus_score": successful[0]["consensus_score"] if successful else None,
        "claim_level": "candidate",
        "evidence_mode": "fixture_or_demo",
    })
    write_json(out / "validation_ledger.json", {
        "schema_version": 1,
        "overall_claim_level": "candidate",
        "evidence_mode": "fixture_or_demo",
        "claims": [
            {
                "claim": "No-download fixture produced a compact screening ranking.",
                "level": "processed",
                "evidence": ["consensus_ranking.csv", "method_summary.json", "failure_report.json"]
            },
            {
                "claim": "Top fixture candidates were promoted to selective reports.",
                "level": "candidate",
                "evidence": promoted
            },
            {
                "claim": "Scores indicate biological affinity or validated binding.",
                "level": "insufficient_evidence",
                "evidence": ["fixture_or_demo only"]
            }
        ],
    })
    append_jsonl(out / "stage-progress.jsonl", stage_events())
    append_jsonl(out / "executed-commands.jsonl", [
        {
            "schema_version": 1,
            "timestamp": utc_now(),
            "stage_id": "screening_fixture_run",
            "command": f"python3 scripts/structure_factory/screening_fixture_run.py --manifest {manifest_path} --out {out} --json",
            "exit_code": 0,
            "mode": "fixture_or_demo",
        }
    ])
    (out / "provenance.md").write_text(
        "# Screening Superpowers Fixture Provenance\n\n"
        f"- Generated at: {utc_now()}\n"
        f"- Manifest: `{manifest_path}`\n"
        f"- Ranking formula: `{RANKING_FORMULA_VERSION}`\n"
        "- Evidence mode: `fixture_or_demo`\n"
        "- Claim ceiling: `candidate`\n"
        "- No paid compute, raw downloads, private data, secrets, or model weights were used.\n"
    )
    write_json(validation_dir / "contract-self-check.json", {
        "schema_version": 1,
        "ok": True,
        "required_outputs_present": [
            "consensus_ranking.csv",
            "failure_report.json",
            "method_summary.json",
            "validation_ledger.json",
            "stage-progress.jsonl",
            "executed-commands.jsonl"
        ],
        "claim_level": "candidate",
        "evidence_mode": "fixture_or_demo",
    })
    return {
        "ok": True,
        "out": str(out.resolve()),
        "ligands_total": len(ligands),
        "ligands_prepared": len(successful),
        "ligands_failed": len(failures),
        "candidate_reports": promoted,
    }


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--manifest", type=Path, required=True)
    parser.add_argument("--out", type=Path, required=True)
    parser.add_argument("--json", action="store_true")
    args = parser.parse_args()

    summary = run_fixture(args.manifest, args.out)
    if args.json:
        print(json.dumps(summary, indent=2, sort_keys=True))
    else:
        print(f"ok: {summary['ok']}")
        print(f"out: {summary['out']}")
    return 0 if summary["ok"] else 1


if __name__ == "__main__":
    raise SystemExit(main())
