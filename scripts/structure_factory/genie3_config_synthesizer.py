#!/usr/bin/env python3
"""Synthesize a Genie 3 binder-design dataset + config from a target window report.

Matches the canonical schema observed in the upstream `aqlaboratory/genie3` at
`examples/binder_design/experiment.yaml` and
`data/design/binder_design/binderbench/problems/01_bhrf1.json`.

Produces under <out>:
  binderbench/problems/<sel>.json
  binderbench/targets/{pdb,fasta}/<sel>{,-chain_<X>}.{pdb,fasta}
  <sel>.config.yaml

Genie 3 reads `paths.dataset` as a binderbench-shaped dir, then resolves the
problem JSON's filepaths relative to that dir. When invoking, set
cwd=<weights_dir> because Genie 3 reads `pretrained/v1/config.yaml` from cwd.
Stdlib only.
"""
from __future__ import annotations
import argparse
import json
import shutil
import sys
from pathlib import Path
from typing import Any

DEFAULT_BINDER_MIN_LEN = 60
DEFAULT_BINDER_MAX_LEN = 100
HOTSPOT_CUTOFF_A = 3.5

THREE_TO_ONE = {
    "ALA": "A", "ARG": "R", "ASN": "N", "ASP": "D", "CYS": "C",
    "GLU": "E", "GLN": "Q", "GLY": "G", "HIS": "H", "ILE": "I",
    "LEU": "L", "LYS": "K", "MET": "M", "PHE": "F", "PRO": "P",
    "SER": "S", "THR": "T", "TRP": "W", "TYR": "Y", "VAL": "V",
}


def parse_cif_chain(cif_path: Path, chain_id: str) -> list[dict[str, Any]]:
    rows: list[dict[str, Any]] = []
    in_atom_site = False
    headers: list[str] = []
    for raw in cif_path.read_text(errors="replace").splitlines():
        s = raw.strip()
        if s == "loop_":
            in_atom_site = False
            headers = []
            continue
        if s.startswith("_atom_site."):
            headers.append(s[len("_atom_site."):])
            in_atom_site = True
            continue
        if in_atom_site and headers:
            if s.startswith(("_", "#")) or not s:
                if s.startswith(("_", "#")):
                    in_atom_site = False
                    headers = []
                continue
            cols = s.split()
            if len(cols) < len(headers):
                continue
            row = dict(zip(headers, cols[:len(headers)]))
            if row.get("auth_asym_id") != chain_id and row.get("label_asym_id") != chain_id:
                continue
            rows.append(row)
    return rows


def write_pdb(rows: list[dict[str, Any]], out_pdb: Path, chain: str) -> int:
    lines: list[str] = []
    serial = 0
    for row in rows:
        group = row.get("group_PDB", "ATOM")
        if group not in ("ATOM", "HETATM"):
            continue
        try:
            atom = (row.get("label_atom_id") or "").strip().strip('"')
            alt = row.get("label_alt_id") or " "
            if alt == ".":
                alt = " "
            comp = (row.get("label_comp_id") or "UNK").strip().upper()
            resnum = int(row.get("label_seq_id") or row.get("auth_seq_id") or "0")
            x = float(row.get("Cartn_x", "0"))
            y = float(row.get("Cartn_y", "0"))
            z = float(row.get("Cartn_z", "0"))
            occ = float(row.get("occupancy", "1.00") or "1.00")
            bfac = float(row.get("B_iso_or_equiv", "0.00") or "0.00")
            elem = (row.get("type_symbol") or atom[:1]).strip().rjust(2)
        except Exception:
            continue
        serial += 1
        atom_field = atom[:4] if len(atom) >= 4 else " " + atom.ljust(3)
        lines.append(
            f"{group:<6}{serial:>5} {atom_field:<4}{alt:1}{comp:>3} {chain:1}{resnum:>4}    "
            f"{x:>8.3f}{y:>8.3f}{z:>8.3f}{occ:>6.2f}{bfac:>6.2f}          {elem:>2}"
        )
    lines += ["TER", "END"]
    out_pdb.write_text("\n".join(lines) + "\n")
    return serial


def extract_fasta(rows: list[dict[str, Any]]) -> str:
    seen: dict[int, str] = {}
    for row in rows:
        try:
            seq_id = int(row.get("label_seq_id") or row.get("auth_seq_id") or "0")
        except ValueError:
            continue
        if seq_id and seq_id not in seen:
            comp = (row.get("label_comp_id") or "UNK").strip().upper()
            seen[seq_id] = THREE_TO_ONE.get(comp, "X")
    return "".join(seen[i] for i in sorted(seen))


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--report", required=True, type=Path)
    ap.add_argument("--target-cif", required=True, type=Path)
    ap.add_argument("--out", required=True, type=Path)
    ap.add_argument("--problem-id", default="telo-recruit-w1")
    ap.add_argument("--binder-min-len", type=int, default=DEFAULT_BINDER_MIN_LEN)
    ap.add_argument("--binder-max-len", type=int, default=DEFAULT_BINDER_MAX_LEN)
    ap.add_argument("--n-sample", type=int, default=1)
    ap.add_argument("--direction-scale", type=float, default=0.0,
                    help="Genie 3 sampler.direction_scale; non-zero values steer toward the binder hotspots")
    ap.add_argument("--hotspot-cutoff-a", type=float, default=HOTSPOT_CUTOFF_A)
    ap.add_argument("--msa-a3m", type=Path, help="optional precomputed ColabFold MSA")
    ap.add_argument("--json", action="store_true")
    args = ap.parse_args(argv)

    report = json.loads(args.report.read_text())
    iface = report.get("interface", {}).get("interface_residues", [])
    if not iface:
        raise SystemExit("report has no interface.interface_residues")
    chain_id = (report.get("target_chain_summary") or {}).get("chain_ids_auth", ["A"])[0]
    pdb_id = report.get("source_pdb") or "?"

    hotspot: list[str] = []
    extended: list[str] = []
    for r in iface:
        c, n, d = r.get("chain", "?"), r.get("resnum"), r.get("min_distance_angstrom")
        if n is None:
            continue
        token = f"{c}{n}"
        if d is not None and d <= args.hotspot_cutoff_a:
            hotspot.append(token)
        else:
            extended.append(token)
    nums = [r["resnum"] for r in iface if r.get("chain") == chain_id and r.get("resnum") is not None]
    chain_range = f"{chain_id}{min(nums)}-{max(nums)}" if nums else f"{chain_id}1-1"

    sel = args.problem_id
    ds_root = args.out / "binderbench"
    problems = ds_root / "problems"
    pdb_d = ds_root / "targets" / "pdb"
    fasta_d = ds_root / "targets" / "fasta"
    msa_d = ds_root / "targets" / "msa"
    for d in (problems, pdb_d, fasta_d, msa_d):
        d.mkdir(parents=True, exist_ok=True)

    rows = parse_cif_chain(args.target_cif, chain_id)
    if not rows:
        raise SystemExit(f"no atoms for chain {chain_id} in {args.target_cif}")
    chain_pdb = pdb_d / f"{sel}-chain_{chain_id}.pdb"
    full_pdb = pdb_d / f"{sel}.pdb"
    n_atoms = write_pdb(rows, chain_pdb, chain_id)
    shutil.copyfile(chain_pdb, full_pdb)

    seq = extract_fasta(rows)
    chain_fasta = fasta_d / f"{sel}-chain_{chain_id}.fasta"
    full_fasta = fasta_d / f"{sel}.fasta"
    chain_fasta.write_text(f">target_chain_{chain_id}\n{seq}\n")
    shutil.copyfile(chain_fasta, full_fasta)

    target_msa = None
    target_msa_chain = None
    if args.msa_a3m and args.msa_a3m.is_file():
        full_msa = msa_d / f"{sel}.a3m"
        chain_msa = msa_d / f"{sel}-chain_{chain_id}.a3m"
        shutil.copyfile(args.msa_a3m, full_msa)
        shutil.copyfile(args.msa_a3m, chain_msa)
        target_msa = str(full_msa.resolve())
        target_msa_chain = str(chain_msa.resolve())

    # Genie 3 reads target_*_filepath from the problem JSON via Python `open()`,
    # which resolves RELATIVE paths from cwd (= weights_dir, where pretrained/
    # config.yaml lives). Our dataset is NOT under weights_dir, so use absolute
    # paths instead. Python `open(abs_path)` is cwd-independent.
    problem: dict[str, Any] = {
        "key": sel,
        "name": sel,
        "target_pdb_filepath": str(full_pdb.resolve()),
        "target_fasta_filepath": str(full_fasta.resolve()),
        "target_pdb_filepath_by_chain": [str(chain_pdb.resolve())],
        "target_fasta_filepath_by_chain": [str(chain_fasta.resolve())],
        "target_chain_and_residues": [chain_range],
        "target_interface_residues": {
            "hotspot": hotspot,
            "extended": extended,
            "common": list(hotspot),
        },
        "binder_min_length": args.binder_min_len,
        "binder_max_length": args.binder_max_len,
        "tag": [],
        "pdb_id": pdb_id,
    }
    if target_msa:
        problem["target_msa_filepath"] = target_msa
        problem["target_msa_filepath_by_chain"] = [target_msa_chain]
    problem_path = problems / f"{sel}.json"
    problem_path.write_text(json.dumps(problem, indent=4) + "\n")

    rootdir = args.out / "genie3-runs"
    rootdir.mkdir(parents=True, exist_ok=True)
    config_yaml = (
        "# Genie 3 binder-design config (synthesized).\n"
        f"experiment:\n  name: {sel}\n\n"
        f"paths:\n  rootdir: {rootdir.resolve()}\n  dataset: {ds_root.resolve()}\n\n"
        "generation:\n"
        "  dataset:\n    source: target\n"
        f"    selections: {sel}\n    n_sample: {args.n_sample}\n"
        f"  sampler:\n    sampler:\n      direction_scale: {args.direction_scale}\n\n"
        "evaluation:\n  version: binder\n"
        "  inverse_folding:\n    num_seq: 1\n"
        "  folding:\n    model_name: colabfold\n    mode: template\n"
    )
    config_path = args.out / f"{sel}.config.yaml"
    config_path.write_text(config_yaml)

    summary = {
        "problem_id": sel,
        "source_pdb": pdb_id,
        "target_chain": chain_id,
        "interface_residue_count": len(iface),
        "hotspot_count": len(hotspot),
        "extended_count": len(extended),
        "common_count": len(hotspot),
        "fasta_length": len(seq),
        "pdb_atoms_written": n_atoms,
        "binder_min_length": args.binder_min_len,
        "binder_max_length": args.binder_max_len,
        "msa_provided": target_msa is not None,
        "outputs": {
            "dataset_root": str(ds_root),
            "problem_json": str(problem_path),
            "config_yaml": str(config_path),
            "rootdir": str(rootdir),
        },
    }
    if args.json:
        print(json.dumps(summary, indent=2))
    else:
        print(f"wrote: {config_path}")
        print(f"wrote: {problem_path}")
        print(f"dataset root: {ds_root}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
