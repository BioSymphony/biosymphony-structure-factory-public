#!/usr/bin/env python3
"""Boltz cofold (RFdiffusion backbone + MPNN sequence) -> candidate_ranking.json."""

from __future__ import annotations

import argparse
import datetime as _dt
import hashlib
import json
import os
import re
import subprocess
import sys
import time
from pathlib import Path
from typing import Any

BOLTZ_PINNED_VERSION = "2.2.1"
DEFAULT_BOLTZ_CACHE = "/workspace/structure-factory/weights/boltz"
DESIGNER = "rfdiffusion"
CAMPAIGN_ID = "pd-l1-pd1-binder-design"
TARGET_WINDOW_ID = "pd-l1-pd1-interface-window"

THREE_TO_ONE = {
    "ALA": "A", "ARG": "R", "ASN": "N", "ASP": "D", "CYS": "C", "GLU": "E", "GLN": "Q",
    "GLY": "G", "HIS": "H", "ILE": "I", "LEU": "L", "LYS": "K", "MET": "M", "PHE": "F",
    "PRO": "P", "SER": "S", "THR": "T", "TRP": "W", "TYR": "Y", "VAL": "V",
}


def utc_iso() -> str:
    return _dt.datetime.now(_dt.timezone.utc).isoformat(timespec="seconds").replace("+00:00", "Z")


def sha256_of_file(path: Path) -> str:
    h = hashlib.sha256()
    with path.open("rb") as fh:
        for chunk in iter(lambda: fh.read(1024 * 1024), b""):
            h.update(chunk)
    return h.hexdigest()


def load_json(path: Path) -> Any:
    return json.loads(path.read_text())


def write_json(path: Path, data: Any) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(data, indent=2, sort_keys=True) + "\n")


def run_command(cmd: list[str], timeout: int = 2400) -> tuple[int, str, str, float]:
    start = time.time()
    try:
        proc = subprocess.run(cmd, capture_output=True, text=True, timeout=timeout, check=False)
        return proc.returncode, proc.stdout, proc.stderr, time.time() - start
    except subprocess.TimeoutExpired as exc:
        return 124, exc.stdout or "", exc.stderr or f"timeout after {timeout}s", time.time() - start
    except FileNotFoundError as exc:
        return 127, "", f"FileNotFoundError: {exc}", time.time() - start


def extract_sequence_from_pdb(pdb_path: Path, chain_filter: str = "A") -> str:
    """Read CA atoms from one chain in the first PDB model."""
    if not pdb_path.is_file():
        return ""
    seq: list[str] = []
    last: tuple[str, int, str] | None = None
    in_ensemble = False
    for ln in pdb_path.read_text().splitlines():
        if ln.startswith("MODEL "):
            if in_ensemble:
                break
            in_ensemble = True
            continue
        if ln.startswith("ENDMDL") and in_ensemble:
            break
        if not ln.startswith("ATOM") or ln[12:16].strip() != "CA":
            continue
        cid = ln[21]
        if chain_filter and cid != chain_filter:
            continue
        try:
            rn = int(ln[22:26].strip())
        except ValueError:
            continue
        insertion_code = ln[26:27].strip()
        residue = (cid, rn, insertion_code)
        if residue == last:
            continue
        seq.append(THREE_TO_ONE.get(ln[17:20].strip(), "X"))
        last = residue
    return "".join(seq)


def yaml_quote(value: str) -> str:
    if re.search(r"[:\s\"'\[\]{},&*?#]", value):
        return '"' + value.replace("\\", "\\\\").replace('"', '\\"') + '"'
    return value


def write_boltz_yaml(path: Path, target_seq: str, binder_seq: str, use_msa_server: bool) -> None:
    """Boltz 2.x YAML: two protein chains (A=target, B=binder)."""
    lines = [
        "version: 1",
        "sequences:",
        "  - protein:",
        "      id: A",
        f"      sequence: {yaml_quote(target_seq)}",
    ]
    if not use_msa_server:
        lines.append("      msa: empty")
    lines += [
        "  - protein:",
        "      id: B",
        f"      sequence: {yaml_quote(binder_seq)}",
    ]
    if not use_msa_server:
        lines.append("      msa: empty")
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text("\n".join(lines) + "\n")


def parse_mpnn_fasta(fasta_path: Path) -> dict[str, list[dict[str, Any]]]:
    """Bucket ProteinMPNN T=... samples under last design_N; skip natives; take binder chain."""
    if not fasta_path.is_file():
        return {}
    out: dict[str, list[dict[str, Any]]] = {}
    last_did: str | None = None
    cur_header: str | None = None
    cur_seq: list[str] = []

    def flush() -> None:
        nonlocal cur_header, cur_seq, last_did
        if cur_header is None:
            return
        token = re.split(r"[\s/|,]", cur_header.lstrip(">"), maxsplit=1)[0]
        if token.startswith("design_"):
            last_did = token
            cur_header, cur_seq = None, []
            return
        did = last_did or (token if token.startswith("design_") else f"design_{token}")
        seq_full = "".join(cur_seq).strip().replace("*", "")
        seq = seq_full.split("/", 1)[1] if "/" in seq_full else seq_full
        bucket = out.setdefault(did, [])
        bucket.append({"header": cur_header, "sequence": seq, "seq_index": len(bucket)})
        cur_header, cur_seq = None, []

    for raw in fasta_path.read_text().splitlines():
        ln = raw.strip()
        if not ln:
            continue
        if ln.startswith(">"):
            flush()
            cur_header = ln
            cur_seq = []
        else:
            cur_seq.append(ln)
    flush()
    return out


def discover_rfdiffusion_designs(rfdiff_dir: Path) -> list[tuple[str, Path]]:
    """Return [(design_id, pdb_path), ...] sorted by integer index."""
    if not rfdiff_dir.is_dir():
        return []
    pat = re.compile(r"^design_(\d+)\.pdb$")
    pairs: list[tuple[int, str, Path]] = []
    for p in rfdiff_dir.iterdir():
        m = pat.match(p.name)
        if not m:
            continue
        pairs.append((int(m.group(1)), f"design_{m.group(1)}", p))
    pairs.sort(key=lambda t: t[0])
    return [(name, path) for _, name, path in pairs]


def cofold_one(
    work_dir: Path,
    target_seq: str,
    binder_seq: str,
    boltz_cache: str,
    timeout: int,
) -> dict[str, Any]:
    """Run a single boltz cofold and parse outputs into a flat record."""
    work_dir.mkdir(parents=True, exist_ok=True)
    yaml_path = work_dir / "boltz_config.yaml"
    write_boltz_yaml(yaml_path, target_seq, binder_seq, use_msa_server=True)

    # FASTA copy (operator-friendly; not consumed by boltz).
    (work_dir / "input.fasta").write_text(
        f">A|protein\n{target_seq}\n>B|protein\n{binder_seq}\n"
    )

    cmd = [
        "boltz", "predict", str(yaml_path),
        "--out_dir", str(work_dir),
        "--cache", boltz_cache,
        "--use_msa_server",
        "--no_kernels",
        "--write_full_pae",
    ]
    rc, stdout, stderr, dur = run_command(cmd, timeout=timeout)

    rec: dict[str, Any] = {
        "boltz_status": "not_run",
        "boltz_version": BOLTZ_PINNED_VERSION,
        "boltz_invocation": cmd,
        "boltz_exit_code": rc,
        "boltz_duration_seconds": round(dur, 3),
        "boltz_stdout_head": stdout[:1024],
        "boltz_stderr_head": stderr[:1024],
        "interface_confidence": None,
        "confidence_summary": None,
        "clash_flag": "unknown",
        "contact_plausibility": "unknown",
        "failure_reason": None,
    }

    stem = yaml_path.stem  # boltz_config
    nested_root = work_dir / f"boltz_results_{stem}" / "predictions" / stem
    nested_cif = nested_root / f"{stem}_model_0.cif"
    nested_pae = nested_root / f"pae_{stem}_model_0.npz"
    nested_plddt = nested_root / f"plddt_{stem}_model_0.npz"
    nested_conf = nested_root / f"confidence_{stem}_model_0.json"

    flat_cif = work_dir / "prediction.cif"
    flat_pae = work_dir / "prediction.pae.npz"
    flat_plddt = work_dir / "prediction.plddt.npz"
    flat_conf = work_dir / "confidence.json"

    # Promote nested → flat for downstream consumers.
    if nested_cif.exists():
        flat_cif.write_bytes(nested_cif.read_bytes())
    if nested_pae.exists():
        flat_pae.write_bytes(nested_pae.read_bytes())
    if nested_plddt.exists():
        flat_plddt.write_bytes(nested_plddt.read_bytes())
    if nested_conf.exists():
        flat_conf.write_bytes(nested_conf.read_bytes())

    if rc == 0 and flat_cif.exists() and flat_cif.stat().st_size > 0:
        rec["boltz_status"] = "run"
        rec["prediction_cif_path"] = str(flat_cif)
        rec["prediction_cif_sha256"] = sha256_of_file(flat_cif)
        if flat_pae.exists():
            rec["prediction_pae_npz_path"] = str(flat_pae)
            rec["prediction_pae_npz_sha256"] = sha256_of_file(flat_pae)
        if flat_plddt.exists():
            rec["prediction_plddt_npz_path"] = str(flat_plddt)
        if flat_conf.is_file():
            rec["confidence_json_path"] = str(flat_conf)
            try:
                conf = load_json(flat_conf)
                rec["interface_confidence"] = conf.get("iptm")
                rec["confidence_summary"] = {
                    k: conf.get(k)
                    for k in ("iptm", "ptm", "complex_plddt", "complex_iplddt")
                    if k in conf
                }
            except Exception as exc:
                rec["failure_reason"] = f"confidence_json parse: {exc}"
    elif rc == 0:
        rec["boltz_status"] = "failed"
        rec["failure_reason"] = f"boltz exit 0 but no model_0.cif at {nested_cif}"
    else:
        rec["boltz_status"] = "failed"
        rec["failure_reason"] = f"boltz exit {rc}: {stderr[:256]}"

    return rec


def build_ranking_row(
    candidate_id: str,
    design_id: str,
    seq_index: int,
    mpnn_header: str,
    binder_seq: str,
    rfdiff_pdb: Path,
    cofold_dir: Path,
    cofold_rec: dict[str, Any],
) -> dict[str, Any]:
    """Single ranking row matching the candidate_ranking.json schema."""
    iptm = cofold_rec.get("interface_confidence")
    summary = cofold_rec.get("confidence_summary") or {}
    return {
        "candidate_id": candidate_id,
        "designer": DESIGNER,
        "generator": DESIGNER,
        "generator_version": "rfdiffusion-inline",
        "design_id": design_id,
        "seq_index": seq_index,
        "mpnn_header": mpnn_header,
        "mpnn_sequence": binder_seq,
        "mpnn_sequence_length": len(binder_seq),
        "status": "generated" if rfdiff_pdb.is_file() else "missing",
        "structure_path": str(rfdiff_pdb),
        "rfdiffusion_backbone_pdb": str(rfdiff_pdb),
        "cofold_dir": str(cofold_dir),
        "boltz_status": cofold_rec.get("boltz_status", "not_run"),
        "boltz_version": cofold_rec.get("boltz_version", BOLTZ_PINNED_VERSION),
        "boltz_prediction_cif": cofold_rec.get("prediction_cif_path"),
        "boltz_pae_npz": cofold_rec.get("prediction_pae_npz_path"),
        "boltz_plddt_npz": cofold_rec.get("prediction_plddt_npz_path"),
        "boltz_confidence_json": cofold_rec.get("confidence_json_path"),
        "interface_confidence": iptm,
        "confidence_summary": summary or None,
        "clash_flag": cofold_rec.get("clash_flag", "unknown"),
        "contact_plausibility": cofold_rec.get("contact_plausibility", "unknown"),
        "diversity_note": None,
        "failure_reason": cofold_rec.get("failure_reason"),
        "claim_ceiling": "computational candidate only; requires experimental validation",
    }


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__.split("\n\n", 1)[0])
    ap.add_argument("--artifact-root", required=True, type=Path,
                    help="Top of the artifacts tree (contains rfdiffusion/, mpnn/).")
    ap.add_argument("--target-pdb", required=True, type=Path,
                    help="PDB file with the target chain (e.g. 4ZQK chain A 19-127).")
    ap.add_argument("--target-chain", default="A",
                    help="Chain ID to extract target sequence from (default A).")
    ap.add_argument("--max-cofolds", type=int, default=16,
                    help="Cap on total (design, seq) cofolds to run (default 16).")
    ap.add_argument("--max-seqs-per-design", type=int, default=2,
                    help="Cap on MPNN sequences per design (default 2).")
    ap.add_argument("--boltz-cache", default=os.environ.get("BOLTZ_CACHE", DEFAULT_BOLTZ_CACHE),
                    help="Path to Boltz weights cache.")
    ap.add_argument("--per-cofold-timeout", type=int, default=900,
                    help="Per-cofold boltz timeout in seconds (default 2400).")
    ap.add_argument("--ranking-output", type=Path, default=None,
                    help="Override candidate_ranking.json output path "
                         "(default: <artifact-root>/candidate_ranking.json).")
    args = ap.parse_args()

    artifact_root: Path = args.artifact_root.resolve()
    rfdiff_dir = artifact_root / "rfdiffusion"
    mpnn_fasta = artifact_root / "mpnn" / "sequences.fasta"
    cofold_root = artifact_root / "cofold"
    cofold_root.mkdir(parents=True, exist_ok=True)
    Path(args.boltz_cache).mkdir(parents=True, exist_ok=True)

    target_seq = extract_sequence_from_pdb(args.target_pdb, chain_filter=args.target_chain)
    if not target_seq:
        print(f"FATAL: could not extract chain {args.target_chain} sequence from "
              f"{args.target_pdb}", file=sys.stderr)
        return 2

    designs = discover_rfdiffusion_designs(rfdiff_dir)
    if not designs:
        print(f"FATAL: no design_*.pdb under {rfdiff_dir}", file=sys.stderr)
        return 3

    mpnn_by_design = parse_mpnn_fasta(mpnn_fasta)
    if not mpnn_by_design:
        print(f"FATAL: no MPNN sequences parsed from {mpnn_fasta}", file=sys.stderr)
        return 4

    rfd_manifest_path = rfdiff_dir / "rfdiffusion_manifest.json"
    rfd_manifest = load_json(rfd_manifest_path) if rfd_manifest_path.is_file() else {}

    ranking_rows: list[dict[str, Any]] = []
    cofolds_run = 0
    skipped_designs: list[str] = []

    print(f"[boltz_cofold_rfdiffusion] target_len={len(target_seq)} "
          f"designs={len(designs)} mpnn_buckets={len(mpnn_by_design)} "
          f"max_cofolds={args.max_cofolds} max_seqs_per_design={args.max_seqs_per_design}",
          flush=True)

    for design_idx, (design_id, rfdiff_pdb) in enumerate(designs):
        if cofolds_run >= args.max_cofolds:
            skipped_designs.append(design_id)
            continue
        seqs = mpnn_by_design.get(design_id, [])[: args.max_seqs_per_design]
        if not seqs:
            ranking_rows.append({
                "candidate_id": f"rfdiff-{design_idx + 1:03d}-s0",
                "designer": DESIGNER,
                "design_id": design_id,
                "seq_index": 0,
                "status": "no_mpnn_sequence",
                "structure_path": str(rfdiff_pdb),
                "rfdiffusion_backbone_pdb": str(rfdiff_pdb),
                "boltz_status": "skipped",
                "boltz_version": BOLTZ_PINNED_VERSION,
                "failure_reason": f"no MPNN sequences for {design_id}",
                "claim_ceiling": "computational candidate only; requires experimental validation",
            })
            continue
        for seq_entry in seqs:
            if cofolds_run >= args.max_cofolds:
                break
            seq_index = seq_entry["seq_index"]
            binder_seq = seq_entry["sequence"]
            if not binder_seq:
                continue
            candidate_id = f"rfdiff-{design_idx + 1:03d}-s{seq_index + 1}"
            cofold_dir = cofold_root / design_id / str(seq_index)
            print(f"[boltz_cofold_rfdiffusion] >>> {candidate_id} "
                  f"design={design_id} seq_index={seq_index} "
                  f"binder_len={len(binder_seq)}", flush=True)
            cofold_rec = cofold_one(
                cofold_dir,
                target_seq=target_seq,
                binder_seq=binder_seq,
                boltz_cache=args.boltz_cache,
                timeout=args.per_cofold_timeout,
            )
            cofold_rec.update({
                "candidate_id": candidate_id,
                "design_id": design_id,
                "seq_index": seq_index,
                "mpnn_header": seq_entry["header"],
                "binder_sequence": binder_seq,
                "rfdiffusion_backbone_pdb": str(rfdiff_pdb),
                "target_pdb": str(args.target_pdb),
                "recorded_at": utc_iso(),
            })
            write_json(cofold_dir / "cofold_record.json", cofold_rec)
            row = build_ranking_row(
                candidate_id=candidate_id,
                design_id=design_id,
                seq_index=seq_index,
                mpnn_header=seq_entry["header"],
                binder_seq=binder_seq,
                rfdiff_pdb=rfdiff_pdb,
                cofold_dir=cofold_dir,
                cofold_rec=cofold_rec,
            )
            ranking_rows.append(row)
            cofolds_run += 1
            iptm_str = (f"{row['interface_confidence']:.4f}"
                        if isinstance(row.get("interface_confidence"), (int, float))
                        else "n/a")
            print(f"[boltz_cofold_rfdiffusion] <<< {candidate_id} "
                  f"status={row['boltz_status']} iptm={iptm_str}", flush=True)

    runs_ok = sum(1 for r in ranking_rows if r.get("boltz_status") == "run")
    runs_fail = sum(1 for r in ranking_rows if r.get("boltz_status") == "failed")
    runs_skip = sum(1 for r in ranking_rows if r.get("boltz_status") == "skipped")

    ranking = {
        "schema_version": 1,
        "campaign_id": CAMPAIGN_ID,
        "target_window": TARGET_WINDOW_ID,
        "designer": DESIGNER,
        "rfdiffusion_manifest_excerpt": {
            "num_designs_produced": rfd_manifest.get("num_designs_produced"),
            "hotspots": rfd_manifest.get("hotspots"),
            "rfdiffusion_version": rfd_manifest.get("rfdiffusion_version"),
        },
        "target_pdb": str(args.target_pdb),
        "target_chain": args.target_chain,
        "target_sequence_length": len(target_seq),
        "boltz_version": BOLTZ_PINNED_VERSION,
        "cofold_caps": {
            "max_cofolds": args.max_cofolds,
            "max_seqs_per_design": args.max_seqs_per_design,
            "per_cofold_timeout_seconds": args.per_cofold_timeout,
        },
        "stats": {
            "total_rows": len(ranking_rows),
            "cofolds_run": cofolds_run,
            "boltz_run": runs_ok,
            "boltz_failed": runs_fail,
            "boltz_skipped": runs_skip,
            "designs_skipped_by_cap": skipped_designs,
        },
        "candidates": ranking_rows,
        "synthesized_at": utc_iso(),
    }
    ranking_path: Path = args.ranking_output or (artifact_root / "candidate_ranking.json")
    write_json(ranking_path, ranking)

    print(f"[boltz_cofold_rfdiffusion] wrote {ranking_path} "
          f"rows={len(ranking_rows)} run={runs_ok} failed={runs_fail} skipped={runs_skip}",
          flush=True)
    # Always exit 0 — per-candidate failures are recorded, not fatal.
    return 0


if __name__ == "__main__":
    sys.exit(main())
