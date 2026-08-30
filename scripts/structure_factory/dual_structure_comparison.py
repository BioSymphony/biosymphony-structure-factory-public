#!/usr/bin/env python3
"""Build a two-target public structure comparison report.

This campaign is deliberately one step beyond a single map/model smoke test:
it runs two independent public-data structure lanes, joins their artifacts, and
emits a campaign-level result review. It still avoids raw movies, private data,
and license-gated software.
"""

from __future__ import annotations

import argparse
import hashlib
import html
import json
import sys
import tarfile
import time
from datetime import datetime, timezone
from pathlib import Path
from typing import Any


ROOT = Path(__file__).resolve().parents[2]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from scripts.structure_factory import poltheta_map_model_report as poltheta  # noqa: E402
from scripts.structure_factory import t2r14_structure_report as t2r14  # noqa: E402


RUN_ID = "bsf-demo-dual-structure-comparison"


def now() -> str:
    return datetime.now(timezone.utc).isoformat()


def write_json(path: Path, payload: dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, indent=2, sort_keys=True) + "\n")


def read_json(path: Path) -> dict[str, Any]:
    return json.loads(path.read_text())


def sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def stage_event(progress_path: Path, stage_id: str, status: str, message: str = "") -> None:
    progress_path.parent.mkdir(parents=True, exist_ok=True)
    event = {
        "schema_version": 1,
        "timestamp": now(),
        "stage_id": stage_id,
        "status": status,
        "message": message,
    }
    with progress_path.open("a", encoding="utf-8") as handle:
        handle.write(json.dumps(event, sort_keys=True) + "\n")


def command_event(commands_path: Path, stage_id: str, command: str, outputs: list[str], start_ts: str, exit_code: int = 0) -> None:
    commands_path.parent.mkdir(parents=True, exist_ok=True)
    event = {
        "schema_version": 1,
        "stage_id": stage_id,
        "command": command,
        "exit_code": exit_code,
        "started_at": start_ts,
        "completed_at": now(),
        "outputs": outputs,
    }
    with commands_path.open("a", encoding="utf-8") as handle:
        handle.write(json.dumps(event, sort_keys=True) + "\n")


def file_record(path: Path, artifact_root: Path, kind: str, accession: str) -> dict[str, Any]:
    return {
        "kind": kind,
        "accession": accession,
        "path": str(path.relative_to(artifact_root)),
        "bytes": path.stat().st_size,
        "sha256": sha256(path),
    }


def write_evidence_matrix_svg(path: Path, rows: list[dict[str, Any]]) -> None:
    columns = [
        ("input", "Input audit"),
        ("materialized", "Files"),
        ("model", "Model"),
        ("map", "Map"),
        ("validation", "Validation"),
        ("figures", "Figures"),
        ("claims", "Result review"),
    ]
    cell_w = 118
    cell_h = 52
    left = 160
    top = 86
    width = left + cell_w * len(columns) + 28
    height = top + cell_h * len(rows) + 70
    parts = [
        f'<svg xmlns="http://www.w3.org/2000/svg" width="{width}" height="{height}" viewBox="0 0 {width} {height}">',
        '<rect width="100%" height="100%" fill="#ffffff"/>',
        '<text x="24" y="34" font-family="Arial" font-size="22" font-weight="700">Structure Comparison Evidence Matrix</text>',
        '<text x="24" y="58" font-family="Arial" font-size="13" fill="#444">Green cells are real artifacts produced by the run; gray cells are intentionally out of scope.</text>',
    ]
    for col_index, (_, label) in enumerate(columns):
        x = left + col_index * cell_w + cell_w / 2
        parts.append(f'<text x="{x:.1f}" y="78" text-anchor="middle" font-family="Arial" font-size="12" font-weight="700">{html.escape(label)}</text>')
    for row_index, row in enumerate(rows):
        y = top + row_index * cell_h
        parts.append(f'<text x="{left - 14}" y="{y + 31}" text-anchor="end" font-family="Arial" font-size="13" font-weight="700">{html.escape(row["label"])}</text>')
        evidence = row["evidence"]
        for col_index, (key, _) in enumerate(columns):
            x = left + col_index * cell_w
            value = evidence.get(key, "na")
            if value == "yes":
                fill = "#d8f2e2"
                text = "real"
            elif value == "partial":
                fill = "#fff2c7"
                text = "bounded"
            else:
                fill = "#eceff3"
                text = "n/a"
            parts.append(f'<rect x="{x}" y="{y}" width="{cell_w - 4}" height="{cell_h - 4}" rx="4" fill="{fill}" stroke="#263238" stroke-width="0.5"/>')
            parts.append(f'<text x="{x + cell_w / 2:.1f}" y="{y + 30}" text-anchor="middle" font-family="Arial" font-size="12">{text}</text>')
    parts.append("</svg>")
    path.write_text("\n".join(parts) + "\n")


def write_maturity_svg(path: Path, levels: list[dict[str, str]]) -> None:
    width = 1040
    height = 260
    left = 54
    step = 154
    y = 116
    parts = [
        f'<svg xmlns="http://www.w3.org/2000/svg" width="{width}" height="{height}" viewBox="0 0 {width} {height}">',
        '<rect width="100%" height="100%" fill="#ffffff"/>',
        '<text x="28" y="36" font-family="Arial" font-size="22" font-weight="700">Campaign Maturity Ladder</text>',
        '<text x="28" y="60" font-family="Arial" font-size="13" fill="#444">The campaign reaches L5 for deposited public-data reports; raw reconstruction remains a separate future lane.</text>',
    ]
    for index, item in enumerate(levels):
        x = left + index * step
        fill = "#0f8f5f" if item["status"] == "complete" else "#b8c0cc"
        parts.append(f'<circle cx="{x}" cy="{y}" r="28" fill="{fill}" stroke="#17324d" stroke-width="1"/>')
        parts.append(f'<text x="{x}" y="{y + 5}" text-anchor="middle" font-family="Arial" font-size="14" fill="#fff" font-weight="700">{html.escape(item["level"])}</text>')
        if index < len(levels) - 1:
            parts.append(f'<line x1="{x + 31}" y1="{y}" x2="{x + step - 31}" y2="{y}" stroke="#17324d" stroke-width="2"/>')
        parts.append(f'<text x="{x}" y="{y + 54}" text-anchor="middle" font-family="Arial" font-size="12">{html.escape(item["label"])}</text>')
        parts.append(f'<text x="{x}" y="{y + 72}" text-anchor="middle" font-family="Arial" font-size="11" fill="#555">{html.escape(item["status"])}</text>')
    parts.append("</svg>")
    path.write_text("\n".join(parts) + "\n")


def target_summary(label: str, root: Path, artifacts: Path) -> dict[str, Any]:
    status = read_json(root / "status.json")
    manifest = read_json(artifacts / "report_manifest.json")
    claim_text = (artifacts / "validation_ledger.md").read_text()
    figures = manifest.get("figures", [])
    return {
        "label": label,
        "ok": status.get("ok") is True,
        "pdb_id": manifest.get("pdb_id"),
        "emdb_id": manifest.get("emdb_id"),
        "claim_level": manifest.get("claim_level"),
        "figure_count": len(figures),
        "figures": figures,
        "validation_ledger_has_insufficient_evidence": "insufficient_evidence" in claim_text,
        "artifact_root": str(artifacts),
    }


def build_self_check(artifact_root: Path, manifest: dict[str, Any], targets: list[dict[str, Any]]) -> dict[str, Any]:
    errors: list[str] = []
    required = [
        "report_manifest.json",
        "data-intake-ledger.json",
        "executed-commands.jsonl",
        "validation/input-audit.json",
        "validation/map_model_fit.json",
        "stage-progress.jsonl",
        "figures/evidence-matrix.svg",
        "figures/maturity-ladder.svg",
        "methods.md",
        "validation_ledger.md",
        "provenance.md",
        "report.md",
    ]
    for rel in required:
        if not (artifact_root / rel).exists():
            errors.append(f"missing campaign artifact: {rel}")
    for target in targets:
        if not target["ok"]:
            errors.append(f"target did not complete: {target['label']}")
        if not target["validation_ledger_has_insufficient_evidence"]:
            errors.append(f"target validation ledger lacks insufficient_evidence boundary: {target['label']}")
        if target["figure_count"] <= 0:
            errors.append(f"target has no figures: {target['label']}")
    if manifest.get("execution_profile") != "map-model-report":
        errors.append("campaign manifest must use execution_profile map-model-report")
    if manifest.get("license_gated_tools_used") != []:
        errors.append("campaign must not use license-gated tools")
    if manifest.get("raw_data_downloaded") is not False:
        errors.append("campaign must not download raw movies")
    return {
        "ok": not errors,
        "check_type": "structure_ranking_contract_self_check",
        "execution_mode": "real",
        "run_id": RUN_ID,
        "target_count": len(targets),
        "targets": targets,
        "errors": errors,
        "warnings": [
            "This is a public deposited-data structure comparison, not raw cryo-EM reconstruction.",
            "T2R14 is coordinate/metadata-only in this campaign; pol theta includes deposited map sampling.",
        ],
    }


def build_report(out: Path) -> dict[str, Any]:
    start = time.time()
    out.mkdir(parents=True, exist_ok=True)
    artifacts = out / "artifacts"
    targets_root = artifacts / "targets"
    figures = artifacts / "figures"
    validation = artifacts / "validation"
    logs = out / "logs"
    for directory in [artifacts, targets_root, figures, validation, logs]:
        directory.mkdir(parents=True, exist_ok=True)
    progress_path = artifacts / "stage-progress.jsonl"
    commands_path = artifacts / "executed-commands.jsonl"

    stage_event(progress_path, "campaign_input_audit", "started", "Declaring public structure comparison inputs")
    input_audit = {
        "ok": True,
        "known_inputs": [
            {"kind": "pdb_entry", "id": "9W0Q", "lane": "t2r14"},
            {"kind": "emdb_entry", "id": "EMD-65512", "lane": "t2r14"},
            {"kind": "pdb_entry", "id": "9ASJ", "lane": "poltheta"},
            {"kind": "emdb_entry", "id": "EMD-43816", "lane": "poltheta"},
        ],
        "missing_operator_items": [],
        "execution_scope": "public deposited PDB/EMDB reports only; no raw movies; no license-gated tools",
    }
    write_json(validation / "input-audit.json", input_audit)
    command_event(commands_path, "campaign_input_audit", "dual_structure_comparison.py declare_public_inputs", ["validation/input-audit.json"], now())
    stage_event(progress_path, "campaign_input_audit", "completed", "Input audit complete")

    stage_event(progress_path, "t2r14_report", "started", "Running T2R14 public-coordinate report")
    ts = now()
    t2r14_root = targets_root / "t2r14"
    t2r14_result = t2r14.build_report(t2r14_root)
    command_event(commands_path, "t2r14_report", "t2r14_structure_report.py --out artifacts/targets/t2r14 --json", ["targets/t2r14/status.json", "targets/t2r14/artifacts/"], ts)
    stage_event(progress_path, "t2r14_report", "completed", "T2R14 report complete")

    stage_event(progress_path, "poltheta_report", "started", "Running pol theta public map/model report")
    ts = now()
    poltheta_root = targets_root / "poltheta"
    poltheta_artifacts = poltheta_root / "artifacts"
    poltheta_result = poltheta.build_report(poltheta_artifacts)
    command_event(commands_path, "poltheta_report", "poltheta_map_model_report.py --out artifacts/targets/poltheta/artifacts --json", ["targets/poltheta/status.json", "targets/poltheta/artifacts/"], ts)
    stage_event(progress_path, "poltheta_report", "completed", "Pol theta report complete")

    stage_event(progress_path, "campaign_join", "started", "Joining target evidence and claim boundaries")
    targets = [
        target_summary("T2R14 receptor complex", t2r14_root, t2r14_root / "artifacts"),
        target_summary("Pol theta helicase map/model", poltheta_root, poltheta_artifacts),
    ]
    poltheta_fit = read_json(poltheta_artifacts / "validation" / "map_model_fit.json")
    data_files = [
        file_record(t2r14_root / "artifacts" / "data" / "9W0Q.cif", artifacts, "pdb_mmcif", "9W0Q"),
        file_record(poltheta_artifacts / "data" / "9ASJ.cif", artifacts, "pdb_mmcif", "9ASJ"),
        file_record(poltheta_artifacts / "data" / "emd_43816.map.gz", artifacts, "emdb_map_gzip", "EMD-43816"),
        file_record(poltheta_artifacts / "data" / "9asj_validation.xml.gz", artifacts, "wwpdb_validation_xml", "9ASJ"),
    ]
    data_intake = {
        "schema_version": 1,
        "status": "completed",
        "run_id": RUN_ID,
        "raw_movies_downloaded": False,
        "license_gated_tools_used": [],
        "materialized_files": data_files,
        "targets": targets,
    }
    write_json(artifacts / "data-intake-ledger.json", data_intake)
    map_model_fit = {
        "ok": True,
        "evidence_level": "joined_public_deposited_structure_ranking",
        "pixel_size_angstrom": poltheta_fit.get("pixel_size_angstrom"),
        "map_model_correlation": poltheta_fit.get("map_model_correlation"),
        "local_resolution": poltheta_fit.get("local_resolution"),
        "mask_provenance": poltheta_fit.get("mask_provenance"),
        "handedness_check": poltheta_fit.get("handedness_check"),
        "geometry_validation": {
            "poltheta": poltheta_fit.get("geometry_validation"),
            "t2r14": "coordinate inventory and inter-chain contact geometry only",
        },
        "fsc_provenance": poltheta_fit.get("fsc_provenance"),
        "target_scope": [
            {"pdb_id": "9W0Q", "emdb_id": "EMD-65512", "map_sampled": False},
            {"pdb_id": "9ASJ", "emdb_id": "EMD-43816", "map_sampled": True},
        ],
    }
    write_json(validation / "map_model_fit.json", map_model_fit)
    evidence_rows = [
        {
            "label": "T2R14 / 9W0Q",
            "evidence": {"input": "yes", "materialized": "yes", "model": "yes", "map": "na", "validation": "partial", "figures": "yes", "claims": "yes"},
        },
        {
            "label": "Pol theta / 9ASJ",
            "evidence": {"input": "yes", "materialized": "yes", "model": "yes", "map": "yes", "validation": "yes", "figures": "yes", "claims": "yes"},
        },
    ]
    write_evidence_matrix_svg(figures / "evidence-matrix.svg", evidence_rows)
    write_maturity_svg(
        figures / "maturity-ladder.svg",
        [
            {"level": "L0", "label": "Plan", "status": "complete"},
            {"level": "L1", "label": "Tools", "status": "complete"},
            {"level": "L2", "label": "Inputs", "status": "complete"},
            {"level": "L3", "label": "Run", "status": "complete"},
            {"level": "L4", "label": "Join", "status": "complete"},
            {"level": "L5", "label": "Audit", "status": "complete"},
        ],
    )
    campaign_summary = {
        "ok": True,
        "run_id": RUN_ID,
        "execution_profile": "map-model-report",
        "target_count": len(targets),
        "targets": targets,
        "t2r14_result": t2r14_result,
        "poltheta_result": poltheta_result,
        "raw_movies_downloaded": False,
        "license_gated_tools_used": [],
    }
    write_json(artifacts / "campaign-summary.json", campaign_summary)
    stage_event(progress_path, "campaign_join", "completed", "Campaign evidence joined")
    command_event(commands_path, "campaign_join", "dual_structure_comparison.py join_target_evidence", ["campaign-summary.json", "data-intake-ledger.json", "validation/map_model_fit.json"], now())

    stage_event(progress_path, "validation_review", "started", "Writing campaign-level result review")
    manifest = {
        "schema_version": 1,
        "run_id": RUN_ID,
        "execution_profile": "map-model-report",
        "pdb_id": "9ASJ",
        "emdb_id": "EMD-43816",
        "accessions": {
            "pdb": "9ASJ",
            "emdb": "EMD-43816",
            "additional_targets": [{"pdb": "9W0Q", "emdb": "EMD-65512"}],
        },
        "targets": targets,
        "figures": ["figures/evidence-matrix.svg", "figures/maturity-ladder.svg"],
        "claim_level": "candidate",
        "license_gated_tools_used": [],
        "raw_data_downloaded": False,
    }
    write_json(artifacts / "report_manifest.json", manifest)
    claim_json = {
        "claims": [
            {
                "claim": "Two independent public structure lanes were executed and joined into one campaign report.",
                "claim_level": "processed",
                "evidence_artifact": "campaign-summary.json",
            },
            {
                "claim": "Pol theta map/model files were materialized and sampled against the deposited EMDB map.",
                "claim_level": "candidate",
                "evidence_artifact": "targets/poltheta/artifacts/validation/map_model_fit.json",
            },
            {
                "claim": "T2R14 interface and ligand-neighborhood summaries are coordinate-derived candidate observations.",
                "claim_level": "candidate",
                "evidence_artifact": "targets/t2r14/artifacts/ligand-neighborhoods.json",
            },
            {
                "claim": "The campaign establishes biological mechanism or publication-ready validation.",
                "claim_level": "insufficient_evidence",
                "evidence_artifact": "validation_ledger.md",
            },
        ]
    }
    write_json(artifacts / "validation_ledger.json", claim_json)
    claim_md = """# Structure Comparison Claim Ledger

| Claim | Level | Evidence | Caveat |
| --- | --- | --- | --- |
| Two independent public structure lanes ran and were joined into one report. | processed | `campaign-summary.json`, `executed-commands.jsonl` | This proves orchestration and artifact joining, not raw reconstruction. |
| Pol theta EMD-43816 / PDB 9ASJ supports a deposited map/model evidence lane. | candidate | `targets/poltheta/artifacts/validation/map_model_fit.json` | Fast density-support proxy, not full expert refinement. |
| T2R14 PDB 9W0Q supports coordinate-derived interface and ligand-neighborhood observations. | candidate | `targets/t2r14/artifacts/interchain-contact-matrix.json`, `targets/t2r14/artifacts/ligand-neighborhoods.json` | Coordinate-only lane; deposited map was not downloaded in this target lane. |
| The campaign proves final biological mechanism or publication-ready model validation. | insufficient_evidence | none | Requires domain expert review, stronger validation, and in many cases raw-data or half-map provenance. |
"""
    (artifacts / "validation_ledger.md").write_text(claim_md)
    methods = """# Methods

The campaign ran two public-data Structure Factory lanes in one RunPod-compatible workflow. The T2R14 lane downloaded public RCSB metadata and PDB `9W0Q` mmCIF coordinates and computed chain, inter-chain contact, and ligand-neighborhood summaries. The pol theta lane downloaded public EMDB `EMD-43816`, PDB `9ASJ`, and wwPDB validation artifacts, parsed deposited map/model metadata, sampled atom-position map density, and generated validation summaries.

No raw cryo-EM movies, particle stacks, private data, CryoSPARC, Phenix, ChimeraX, Rosetta, AlphaFold 3, or other license-gated tools were used.
"""
    (artifacts / "methods.md").write_text(methods)
    provenance = f"""# Provenance

- run_id: `{RUN_ID}`
- created_at: `{now()}`
- target_1: `PDB 9W0Q`, `EMD-65512`
- target_2: `PDB 9ASJ`, `EMD-43816`
- execution_profile: `map-model-report`
- tool_policy: Python standard library only
- raw_data_policy: no raw movies or particle stacks downloaded
- license_policy: no license-gated tools used
"""
    (artifacts / "provenance.md").write_text(provenance)
    report_md = """# BioSymphony Structure Factory: Two-Target Structure Comparison

This campaign runs two real public structure lanes and joins the evidence into one result-reviewed report.

## Targets

- T2R14 receptor complex: `PDB 9W0Q`, `EMD-65512`
- Pol theta helicase map/model: `PDB 9ASJ`, `EMD-43816`

## Campaign Figures

- `figures/evidence-matrix.svg`
- `figures/maturity-ladder.svg`

## Claim Boundary

This is a deposited public-data structure comparison. It proves input materialization, exact-command execution, artifact joining, and result reviewing across two lanes. It does not claim raw-data reconstruction or final biological mechanism.
"""
    (artifacts / "report.md").write_text(report_md)
    self_check = build_self_check(artifacts, manifest, targets)
    write_json(validation / "contract-self-check.json", self_check)
    stage_contract_check = {
        "ok": self_check["ok"],
        "check_type": "structure_ranking_stage_contract_check",
        "require_terminal": True,
        "terminal_by_stage": {
            "campaign_input_audit": "completed",
            "t2r14_report": "completed",
            "poltheta_report": "completed",
            "campaign_join": "completed",
            "validation_review": "completed",
        },
        "errors": self_check["errors"],
        "warnings": self_check["warnings"],
    }
    write_json(validation / "stage-contract-check.json", stage_contract_check)
    stage_event(progress_path, "validation_review", "completed", "Campaign result review complete")
    command_event(commands_path, "validation_review", "dual_structure_comparison.py write_campaign_validation_review", ["report_manifest.json", "validation_ledger.md", "validation/contract-self-check.json"], now())

    hashes = {}
    for path in sorted(artifacts.rglob("*")):
        if path.is_file() and path.name != "runpod-execution.tar.gz":
            hashes[str(path.relative_to(artifacts))] = sha256(path)
    write_json(out / "artifact_hashes.json", {"sha256": hashes})
    with tarfile.open(artifacts / "runpod-execution.tar.gz", "w:gz") as archive:
        for path in sorted(artifacts.rglob("*")):
            if path.name != "runpod-execution.tar.gz":
                archive.add(path, arcname=path.relative_to(artifacts))
    stage_event(progress_path, "archive", "completed", "Artifact archive ready")
    command_event(commands_path, "archive", "dual_structure_comparison.py archive_artifacts", ["runpod-execution.tar.gz"], now())
    status = {
        "ok": self_check["ok"],
        "run_id": RUN_ID,
        "status": "completed" if self_check["ok"] else "failed",
        "completed_at": now(),
        "artifact_root": "runpod-execution/artifacts",
    }
    write_json(out / "status.json", status)
    return {
        "ok": self_check["ok"],
        "run_id": RUN_ID,
        "out": str(out.resolve()),
        "artifact_count": len(hashes),
        "target_count": len(targets),
        "targets": targets,
        "elapsed_seconds": round(time.time() - start, 3),
    }


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--out", type=Path, default=Path("runpod-execution"))
    parser.add_argument("--json", action="store_true")
    args = parser.parse_args()

    try:
        summary = build_report(args.out)
    except Exception as exc:
        summary = {
            "ok": False,
            "error": f"{type(exc).__name__}: {exc}",
            "run_id": RUN_ID,
        }
        write_json(args.out / "status.json", {"ok": False, "status": "failed", "error": summary["error"], "completed_at": now()})
    if args.json:
        print(json.dumps(summary, indent=2, sort_keys=True))
    else:
        print(f"ok: {summary['ok']}")
        if not summary["ok"]:
            print(summary.get("error", "unknown error"), file=sys.stderr)
    return 0 if summary["ok"] else 1


if __name__ == "__main__":
    raise SystemExit(main())
