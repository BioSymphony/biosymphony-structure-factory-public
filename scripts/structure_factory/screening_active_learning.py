#!/usr/bin/env python3
"""Build active-learning and evidence artifacts from screening results.

This is a no-download, stdlib-only post-processing pass. It works with the
fixture outputs today, and gives future real lanes a stable artifact shape for
method disagreement, scaffold diversity, rescue queues, and evidence graphs.
"""

from __future__ import annotations

import argparse
import csv
import json
from pathlib import Path
from typing import Any


def load_json(path: Path) -> dict[str, Any]:
    return json.loads(path.read_text())


def write_json(path: Path, data: Any) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(data, indent=2, sort_keys=True) + "\n")


def write_jsonl(path: Path, records: list[dict[str, Any]]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text("".join(json.dumps(record, sort_keys=True) + "\n" for record in records))


def read_jsonl(path: Path) -> list[dict[str, Any]]:
    records: list[dict[str, Any]] = []
    if not path.is_file():
        return records
    for line in path.read_text().splitlines():
        if line.strip():
            records.append(json.loads(line))
    return records


def read_ranking(path: Path) -> list[dict[str, Any]]:
    if not path.is_file():
        return []
    with path.open(newline="") as handle:
        rows = list(csv.DictReader(handle))
    for row in rows:
        for key in (
            "rank",
            "consensus_score",
            "best_vina_score_proxy",
            "boltz_affinity_probability_proxy",
            "method_disagreement_proxy",
        ):
            if key in row and row[key] not in {"", None}:
                row[key] = int(row[key]) if key == "rank" else float(row[key])
    return rows


def scaffold_key(prep: dict[str, Any]) -> str:
    if prep.get("prep_status") != "prepared":
        return "invalid_or_unprepared"
    smiles = str(prep.get("smiles", ""))
    hetero = int(prep.get("hetero_atom_proxy") or 0)
    heavy = int(prep.get("heavy_atom_proxy") or 0)
    if "c" in smiles and hetero >= 2:
        return "aromatic_hetero_rich"
    if "c" in smiles:
        return "aromatic_fragment"
    if heavy >= 8 and hetero == 0:
        return "aliphatic_decoy_like"
    return "other_prepared"


def disagreement_band(value: float) -> str:
    if value >= 0.55:
        return "high"
    if value >= 0.30:
        return "medium"
    return "low"


def select_unique(items: list[str], limit: int) -> list[str]:
    selected: list[str] = []
    for item in items:
        if item and item not in selected:
            selected.append(item)
        if len(selected) >= limit:
            break
    return selected


def build_active_learning(root: Path) -> dict[str, Any]:
    manifest = load_json(root / "screening_manifest.json")
    prep_records = read_jsonl(root / "ligand_prep.jsonl")
    affinity_records = read_jsonl(root / "affinity_predictions.jsonl")
    ranking_rows = read_ranking(root / "consensus_ranking.csv")
    failure_report = load_json(root / "failure_report.json") if (root / "failure_report.json").is_file() else {}
    validation_ledger = load_json(root / "validation_ledger.json") if (root / "validation_ledger.json").is_file() else {}

    prep_by_id = {str(record.get("ligand_id")): record for record in prep_records}
    affinity_by_id = {str(record.get("ligand_id")): record for record in affinity_records}

    clusters: dict[str, list[str]] = {}
    for prep in prep_records:
        clusters.setdefault(scaffold_key(prep), []).append(str(prep.get("ligand_id")))
    scaffold_atlas = {
        "schema_version": 1,
        "artifact_type": "scaffold_atlas",
        "mode": "fixture_or_demo",
        "cluster_method": "stdlib_smiles_proxy",
        "clusters": [
            {
                "scaffold_key": key,
                "ligand_ids": ligand_ids,
                "size": len(ligand_ids),
                "claim_level": "candidate" if key != "invalid_or_unprepared" else "blocked",
            }
            for key, ligand_ids in sorted(clusters.items())
        ],
    }

    disagreement_records: list[dict[str, Any]] = []
    for ligand_id, affinity in affinity_by_id.items():
        if affinity.get("status") != "completed":
            continue
        value = float(affinity.get("method_disagreement_proxy") or 0.0)
        prep = prep_by_id.get(ligand_id, {})
        disagreement_records.append({
            "schema_version": 1,
            "ligand_id": ligand_id,
            "scaffold_key": scaffold_key(prep),
            "method_disagreement_proxy": round(value, 4),
            "disagreement_band": disagreement_band(value),
            "consensus_score": affinity.get("consensus_score"),
            "drivers": [
                "boltz_vs_similarity_proxy",
                "molecular_weight_vs_clogp_baseline",
            ],
            "recommended_action": "promote_to_report_or_next_tranche" if value >= 0.30 else "keep_in_background_ledger",
            "claim_level": "candidate",
            "evidence_mode": affinity.get("evidence_mode", "fixture_or_demo"),
        })
    disagreement_records.sort(
        key=lambda record: (
            float(record.get("method_disagreement_proxy") or 0.0),
            float(record.get("consensus_score") or 0.0),
        ),
        reverse=True,
    )

    ranked_ids = [str(row.get("ligand_id")) for row in ranking_rows]
    top_ids = select_unique(ranked_ids, 2)
    control_ids = select_unique(
        [
            str(record.get("ligand_id"))
            for record in prep_records
            if record.get("known_class") in {"active_control", "decoy_control", "fragment_control"}
        ],
        3,
    )
    disagreement_ids = select_unique([str(record.get("ligand_id")) for record in disagreement_records], 2)
    failed_ids = select_unique(
        [
            str(item.get("ligand_id"))
            for item in failure_report.get("failed_ligands", [])
            if isinstance(item, dict)
        ],
        3,
    )

    tranches = {
        "schema_version": 1,
        "artifact_type": "active_learning_tranches",
        "campaign_id": manifest.get("campaign_id"),
        "run_id": manifest.get("run_id"),
        "evidence_mode": "fixture_or_demo",
        "claim_level": "candidate",
        "tranches": [
            {
                "tranche_id": "top_ranked_candidates",
                "ligand_ids": top_ids,
                "selection_axis": "consensus_score",
                "recommended_next_action": "focused Boltz/GNINA tranche after real-method and license gates",
            },
            {
                "tranche_id": "controls_and_scaffold_representatives",
                "ligand_ids": control_ids,
                "selection_axis": "control_balance_and_scaffold_diversity",
                "recommended_next_action": "keep in every calibration slice",
            },
            {
                "tranche_id": "method_disagreement_cases",
                "ligand_ids": disagreement_ids,
                "selection_axis": "method_disagreement_proxy",
                "recommended_next_action": "promote to review reports and run alternate methods",
            },
            {
                "tranche_id": "failure_rescue_cases",
                "ligand_ids": failed_ids,
                "selection_axis": "clean_degradation",
                "recommended_next_action": "repair input or keep as negative-control failure",
            },
        ],
    }

    rescue_items = []
    for item in failure_report.get("failed_ligands", []):
        if isinstance(item, dict):
            rescue_items.append({
                "schema_version": 1,
                "ligand_id": item.get("ligand_id"),
                "failure_stage": item.get("stage"),
                "failure_reason": item.get("reason"),
                "recommended_action": "fix_or_exclude_from_real_screen",
                "claim_level": "blocked",
                "evidence_mode": "fixture_or_demo",
            })
    for record in disagreement_records:
        if record["disagreement_band"] == "high":
            rescue_items.append({
                "schema_version": 1,
                "ligand_id": record["ligand_id"],
                "failure_stage": "method_comparison",
                "failure_reason": "high_method_disagreement",
                "recommended_action": "route_to_alternate_scoring_or_manual_review",
                "claim_level": "candidate",
                "evidence_mode": "fixture_or_demo",
            })
    rescue_queue = {
        "schema_version": 1,
        "artifact_type": "rescue_queue",
        "items": rescue_items,
        "count": len(rescue_items),
    }

    evidence_graph = {
        "schema_version": 1,
        "artifact_type": "evidence_graph",
        "nodes": [
            {"id": "screening_manifest", "path": "screening_manifest.json", "type": "manifest"},
            {"id": "ligand_prep", "path": "ligand_prep.jsonl", "type": "ledger"},
            {"id": "pose_predictions", "path": "pose_predictions.jsonl", "type": "ledger"},
            {"id": "affinity_predictions", "path": "affinity_predictions.jsonl", "type": "ledger"},
            {"id": "consensus_ranking", "path": "consensus_ranking.csv", "type": "ranking"},
            {"id": "failure_report", "path": "failure_report.json", "type": "failure_ledger"},
            {"id": "validation_ledger", "path": "validation_ledger.json", "type": "validation_ledger"},
            {"id": "active_learning_tranches", "path": "active_learning_tranches.json", "type": "selection_plan"},
            {"id": "method_disagreement", "path": "method_disagreement.jsonl", "type": "disagreement_ledger"},
        ],
        "edges": [
            {"from": "screening_manifest", "to": "ligand_prep", "relation": "declares_inputs"},
            {"from": "ligand_prep", "to": "pose_predictions", "relation": "feeds"},
            {"from": "pose_predictions", "to": "affinity_predictions", "relation": "feeds_method_comparison"},
            {"from": "affinity_predictions", "to": "consensus_ranking", "relation": "ranked_by"},
            {"from": "consensus_ranking", "to": "active_learning_tranches", "relation": "selects"},
            {"from": "failure_report", "to": "active_learning_tranches", "relation": "adds_rescue_cases"},
            {"from": "validation_ledger", "to": "consensus_ranking", "relation": "limits_claims"},
        ],
        "claim_ceiling": validation_ledger.get("overall_claim_level", "candidate"),
        "evidence_mode": validation_ledger.get("evidence_mode", "fixture_or_demo"),
    }

    write_json(root / "scaffold_atlas.json", scaffold_atlas)
    write_jsonl(root / "method_disagreement.jsonl", disagreement_records)
    write_json(root / "active_learning_tranches.json", tranches)
    write_json(root / "rescue_queue.json", rescue_queue)
    write_json(root / "evidence_graph.json", evidence_graph)
    (root / "selection_rationale.md").write_text(
        "# Screening Selection Rationale\n\n"
        "- Evidence mode: `fixture_or_demo`.\n"
        "- Claim ceiling: `candidate`.\n"
        "- Top candidates are chosen by the consensus ranking ledger.\n"
        "- Controls and scaffold representatives stay in every calibration slice.\n"
        "- Method-disagreement cases are promoted because they are informative, not because they are validated hits.\n"
        "- Failure-rescue cases are tracked so invalid inputs and brittle preprocessing do not disappear from the campaign ledger.\n"
    )

    return {
        "ok": True,
        "artifact_root": str(root.resolve()),
        "method_disagreement_cases": len(disagreement_records),
        "scaffold_clusters": len(scaffold_atlas["clusters"]),
        "active_learning_tranches": len(tranches["tranches"]),
        "rescue_items": len(rescue_items),
    }


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--artifact-root", type=Path, required=True)
    parser.add_argument("--out", type=Path)
    parser.add_argument("--json", action="store_true")
    args = parser.parse_args()

    summary = build_active_learning(args.artifact_root)
    if args.out:
        write_json(args.out, summary)
        summary["report_path"] = str(args.out.resolve())
    if args.json:
        print(json.dumps(summary, indent=2, sort_keys=True))
    else:
        print(f"ok: {summary['ok']}")
        print(f"artifact_root: {summary['artifact_root']}")
    return 0 if summary["ok"] else 1


if __name__ == "__main__":
    raise SystemExit(main())
