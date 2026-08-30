#!/usr/bin/env python3
"""Build a command-line summary bundle from screening fixture artifacts.

This helper gives CI and demo operators a stdlib-only way to prove the
screening artifact set is parseable, and to write a compact JSON bundle for
agent review or release checks.
"""

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

OPTIONAL_FILES = [
    "receptor_ensemble_manifest.json",
    "validation/screening-manifest-check.json",
    "validation/screening-results-check.json",
    "validation/active-learning-check.json",
    "validation/fanout-estimate.json",
]

TEXT_FILES = {".md", ".txt", ".log"}
JSONL_FILES = {".jsonl"}
CSV_FILES = {".csv"}


def read_json(path: Path) -> Any:
    return json.loads(path.read_text())


def read_jsonl(path: Path) -> list[dict[str, Any]]:
    records: list[dict[str, Any]] = []
    for line in path.read_text().splitlines():
        if line.strip():
            records.append(json.loads(line))
    return records


def read_csv(path: Path) -> list[dict[str, str]]:
    with path.open(newline="") as handle:
        return list(csv.DictReader(handle))


def artifact_kind(rel_path: str) -> str:
    suffix = Path(rel_path).suffix
    if suffix == ".json":
        return "json"
    if suffix in JSONL_FILES:
        return "jsonl"
    if suffix in CSV_FILES:
        return "csv"
    if suffix in TEXT_FILES:
        return "text"
    return "artifact"


def parse_artifact(path: Path, rel_path: str) -> Any:
    kind = artifact_kind(rel_path)
    if kind == "json":
        return read_json(path)
    if kind == "jsonl":
        return read_jsonl(path)
    if kind == "csv":
        return read_csv(path)
    if kind == "text":
        text = path.read_text()
        return text[:6000]
    return None


def artifact_inventory(root: Path) -> tuple[list[dict[str, Any]], list[str]]:
    expected = list(dict.fromkeys(REQUIRED_FILES + OPTIONAL_FILES))
    candidate_files = sorted(root.glob("candidate_reports/*.json"))
    for path in candidate_files:
        expected.append(path.relative_to(root).as_posix())

    seen: set[str] = set()
    artifacts: list[dict[str, Any]] = []
    missing_required: list[str] = []
    for rel_path in expected:
        if rel_path in seen:
            continue
        seen.add(rel_path)
        path = root / rel_path
        required = rel_path in REQUIRED_FILES
        present = path.is_file() and path.stat().st_size > 0
        if required and not present:
            missing_required.append(rel_path)
        artifacts.append(
            {
                "path": rel_path,
                "kind": artifact_kind(rel_path),
                "required": required,
                "status": "present" if present else "missing",
                "size_bytes": path.stat().st_size if present else 0,
            }
        )
    return artifacts, missing_required


def safe_parse(root: Path, rel_path: str, errors: list[str]) -> Any:
    path = root / rel_path
    if not path.is_file():
        return [] if artifact_kind(rel_path) in {"jsonl", "csv"} else {}
    try:
        return parse_artifact(path, rel_path)
    except (OSError, json.JSONDecodeError, csv.Error) as exc:
        errors.append(f"failed to parse {rel_path}: {exc}")
        return [] if artifact_kind(rel_path) in {"jsonl", "csv"} else {}


def build_bundle(root: Path) -> dict[str, Any]:
    root = root.resolve()
    artifacts, missing_required = artifact_inventory(root)
    errors = [f"missing required artifact: {rel_path}" for rel_path in missing_required]

    candidate_reports = []
    for path in sorted(root.glob("candidate_reports/*.json")):
        rel_path = path.relative_to(root).as_posix()
        parsed = safe_parse(root, rel_path, errors)
        if isinstance(parsed, dict):
            candidate_reports.append(parsed)

    manifest = safe_parse(root, "screening_manifest.json", errors)
    metrics = safe_parse(root, "metrics.json", errors)
    validation_ledger = safe_parse(root, "validation_ledger.json", errors)

    bundle = {
        "schema_version": 1,
        "bundle_type": "screening_summary_bundle",
        "artifact_root": str(root),
        "ok": not errors,
        "errors": errors,
        "artifacts": artifacts,
        "manifest": manifest,
        "metrics": metrics,
        "ranking": safe_parse(root, "consensus_ranking.csv", errors),
        "method_summary": safe_parse(root, "method_summary.json", errors),
        "validation_ledger": validation_ledger,
        "failure_report": safe_parse(root, "failure_report.json", errors),
        "active_learning_tranches": safe_parse(root, "active_learning_tranches.json", errors),
        "rescue_queue": safe_parse(root, "rescue_queue.json", errors),
        "method_disagreement": safe_parse(root, "method_disagreement.jsonl", errors),
        "scaffold_atlas": safe_parse(root, "scaffold_atlas.json", errors),
        "evidence_graph": safe_parse(root, "evidence_graph.json", errors),
        "ligand_prep": safe_parse(root, "ligand_prep.jsonl", errors),
        "affinity_predictions": safe_parse(root, "affinity_predictions.jsonl", errors),
        "stage_progress": safe_parse(root, "stage-progress.jsonl", errors),
        "candidate_reports": candidate_reports,
        "selection_rationale": safe_parse(root, "selection_rationale.md", errors),
        "provenance": safe_parse(root, "provenance.md", errors),
        "summary": {
            "run_id": (
                manifest.get("run_id")
                if isinstance(manifest, dict)
                else metrics.get("run_id")
                if isinstance(metrics, dict)
                else None
            ),
            "top_ligand_id": metrics.get("top_ligand_id") if isinstance(metrics, dict) else None,
            "claim_level": validation_ledger.get("overall_claim_level") if isinstance(validation_ledger, dict) else None,
            "evidence_mode": validation_ledger.get("evidence_mode") if isinstance(validation_ledger, dict) else None,
            "candidate_reports": len(candidate_reports),
            "artifact_count": sum(1 for item in artifacts if item["status"] == "present"),
        },
    }
    bundle["ok"] = not bundle["errors"]
    return bundle


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument(
        "--artifact-root",
        type=Path,
        default=Path(".runtime/screening-superpowers-fixture"),
        help="Directory containing screening fixture artifacts.",
    )
    parser.add_argument("--out", type=Path, help="Optional path for a summary JSON bundle.")
    parser.add_argument("--json", action="store_true", help="Print the full bundle as JSON.")
    args = parser.parse_args()

    bundle = build_bundle(args.artifact_root)
    if args.out:
        args.out.parent.mkdir(parents=True, exist_ok=True)
        args.out.write_text(json.dumps(bundle, indent=2, sort_keys=True) + "\n")

    if args.json:
        print(json.dumps(bundle, indent=2, sort_keys=True))
    else:
        print(f"ok: {bundle['ok']}")
        print(f"artifact_root: {bundle['artifact_root']}")
        print(f"artifact_count: {bundle['summary']['artifact_count']}")
        for error in bundle["errors"]:
            print(f"error: {error}")
    return 0 if bundle["ok"] else 1


if __name__ == "__main__":
    raise SystemExit(main())
