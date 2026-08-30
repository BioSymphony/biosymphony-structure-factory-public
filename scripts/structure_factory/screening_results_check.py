#!/usr/bin/env python3
"""Validate no-download screening fixture outputs."""

from __future__ import annotations

import argparse
import csv
import json
from pathlib import Path
from typing import Any


REQUIRED_FILES = [
    "screening_manifest.json",
    "validation/input-audit.json",
    "validation/contract-self-check.json",
    "ligand_prep.jsonl",
    "pose_predictions.jsonl",
    "affinity_predictions.jsonl",
    "consensus_ranking.csv",
    "metrics.json",
    "method_summary.json",
    "method_disagreement.jsonl",
    "scaffold_atlas.json",
    "active_learning_tranches.json",
    "rescue_queue.json",
    "evidence_graph.json",
    "selection_rationale.md",
    "failure_report.json",
    "validation_ledger.json",
    "stage-progress.jsonl",
    "executed-commands.jsonl",
    "provenance.md",
]


def load_json(path: Path) -> dict[str, Any]:
    return json.loads(path.read_text())


def jsonl_records(path: Path) -> list[dict[str, Any]]:
    records: list[dict[str, Any]] = []
    for line in path.read_text().splitlines():
        if line.strip():
            records.append(json.loads(line))
    return records


def validate(root: Path) -> dict[str, Any]:
    errors: list[str] = []
    for rel in REQUIRED_FILES:
        path = root / rel
        if not path.is_file() or path.stat().st_size == 0:
            errors.append(f"missing or empty required output: {rel}")

    ranking_rows: list[dict[str, str]] = []
    ranking_path = root / "consensus_ranking.csv"
    if ranking_path.is_file():
        with ranking_path.open(newline="") as handle:
            ranking_rows = list(csv.DictReader(handle))
        if not ranking_rows:
            errors.append("consensus_ranking.csv has no ranked candidates")
        ranks = [int(row["rank"]) for row in ranking_rows if row.get("rank", "").isdigit()]
        if ranks != sorted(ranks) or ranks[:1] != [1]:
            errors.append("consensus_ranking.csv ranks must start at 1 and be sorted")

    failure_report = load_json(root / "failure_report.json") if (root / "failure_report.json").is_file() else {}
    failures = failure_report.get("failed_ligands", [])
    if not isinstance(failures, list) or not failures:
        errors.append("failure_report.json must include at least one failed ligand control")
    elif not any(item.get("ligand_id") == "FIX-BAD-001" for item in failures if isinstance(item, dict)):
        errors.append("failure_report.json must include FIX-BAD-001 invalid control")

    method_summary = load_json(root / "method_summary.json") if (root / "method_summary.json").is_file() else {}
    calibration = method_summary.get("openbind_style_calibration", {})
    if not calibration.get("simple_baselines_included"):
        errors.append("method_summary.json must record simple baselines for OpenBind-style calibration")

    validation_ledger = load_json(root / "validation_ledger.json") if (root / "validation_ledger.json").is_file() else {}
    if validation_ledger.get("overall_claim_level") != "candidate":
        errors.append("validation_ledger.json overall_claim_level must remain candidate for fixture evidence")
    if validation_ledger.get("evidence_mode") != "fixture_or_demo":
        errors.append("validation_ledger.json evidence_mode must be fixture_or_demo")

    reports = sorted((root / "candidate_reports").glob("*.json")) if (root / "candidate_reports").is_dir() else []
    if len(reports) < 1:
        errors.append("candidate_reports must contain at least one promoted candidate")

    prep_records = jsonl_records(root / "ligand_prep.jsonl") if (root / "ligand_prep.jsonl").is_file() else []
    prepared = [record for record in prep_records if record.get("prep_status") == "prepared"]
    failed = [record for record in prep_records if record.get("prep_status") == "failed"]
    if len(prepared) < 1 or len(failed) < 1:
        errors.append("ligand_prep.jsonl must include prepared and failed records")

    tranches = load_json(root / "active_learning_tranches.json") if (root / "active_learning_tranches.json").is_file() else {}
    if len(tranches.get("tranches", [])) < 4:
        errors.append("active_learning_tranches.json must include top, control, disagreement, and rescue tranches")

    disagreement = jsonl_records(root / "method_disagreement.jsonl") if (root / "method_disagreement.jsonl").is_file() else []
    if not disagreement:
        errors.append("method_disagreement.jsonl must include at least one disagreement record")

    evidence_graph = load_json(root / "evidence_graph.json") if (root / "evidence_graph.json").is_file() else {}
    graph_nodes = {node.get("id") for node in evidence_graph.get("nodes", []) if isinstance(node, dict)}
    if "validation_ledger" not in graph_nodes or "consensus_ranking" not in graph_nodes:
        errors.append("evidence_graph.json must link claims to ranking evidence")

    return {
        "ok": not errors,
        "check_type": "screening_results_check",
        "artifact_root": str(root.resolve()),
        "ranked_candidates": len(ranking_rows),
        "failed_ligands": len(failures) if isinstance(failures, list) else 0,
        "candidate_reports": len(reports),
        "method_disagreement_cases": len(disagreement),
        "active_learning_tranches": len(tranches.get("tranches", [])) if isinstance(tranches, dict) else 0,
        "errors": errors,
        "warnings": [],
    }


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--artifact-root", type=Path, required=True)
    parser.add_argument("--out", type=Path)
    parser.add_argument("--json", action="store_true")
    args = parser.parse_args()

    summary = validate(args.artifact_root)
    if args.out:
        args.out.parent.mkdir(parents=True, exist_ok=True)
        args.out.write_text(json.dumps(summary, indent=2, sort_keys=True) + "\n")
        summary["report_path"] = str(args.out.resolve())
    if args.json:
        print(json.dumps(summary, indent=2, sort_keys=True))
    else:
        print(f"ok: {summary['ok']}")
        for error in summary["errors"]:
            print(f"error: {error}")
    return 0 if summary["ok"] else 1


if __name__ == "__main__":
    raise SystemExit(main())
