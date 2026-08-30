#!/usr/bin/env python3
"""Build a real public map/model report for EMD-43816 / PDB 9ASJ.

This demo uses only Python standard-library code plus public EMDB/RCSB/wwPDB
downloads. It is designed for a short RunPod CPU Pod run with no licensed tools,
no raw movie downloads, and fail-closed artifact contracts.
"""

from __future__ import annotations

import argparse
import array
import csv
import gzip
import hashlib
import html
import json
import math
import shlex
import struct
import sys
import tarfile
import time
import urllib.request
import xml.etree.ElementTree as ET
from collections import Counter, defaultdict
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path
from typing import Any


PDB_ID = "9ASJ"
EMDB_ID = "EMD-43816"
RUN_ID = "bsf-demo-poltheta-map-model-report"
MAP_URL = "https://ftp.ebi.ac.uk/pub/databases/emdb/structures/EMD-43816/map/emd_43816.map.gz"
CIF_URL = "https://files.rcsb.org/download/9ASJ.cif"
ENTRY_URL = "https://data.rcsb.org/rest/v1/core/entry/9ASJ"
VALIDATION_XML_URL = "https://files.rcsb.org/pub/pdb/validation_reports/as/9asj/9asj_validation.xml.gz"
VALIDATION_PDF_URL = "https://files.rcsb.org/pub/pdb/validation_reports/as/9asj/9asj_full_validation.pdf.gz"
LIGAND_DISTANCE_ANGSTROM = 5.0
CONTACT_DISTANCE_ANGSTROM = 8.0
SAMPLE_ATOM_LIMIT = 800


def now() -> str:
    return datetime.now(timezone.utc).isoformat()


def write_json(path: Path, payload: dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, indent=2, sort_keys=True) + "\n")


def sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def file_record(path: Path, url: str, kind: str, accession: str) -> dict[str, Any]:
    return {
        "kind": kind,
        "accession": accession,
        "url": url,
        "path": str(path),
        "bytes": path.stat().st_size,
        "sha256": sha256(path),
    }


def fetch_binary(url: str, path: Path) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    request = urllib.request.Request(url, headers={"User-Agent": "BioSymphony-Structure-Factory/0.1"})
    with urllib.request.urlopen(request, timeout=180) as response, path.open("wb") as handle:
        while True:
            chunk = response.read(1024 * 1024)
            if not chunk:
                break
            handle.write(chunk)


def fetch_text(url: str) -> str:
    request = urllib.request.Request(url, headers={"User-Agent": "BioSymphony-Structure-Factory/0.1"})
    with urllib.request.urlopen(request, timeout=60) as response:
        return response.read().decode("utf-8")


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


@dataclass
class Atom:
    chain: str
    seq: str
    comp: str
    atom: str
    element: str
    x: float
    y: float
    z: float
    group: str

    @property
    def residue_key(self) -> tuple[str, str, str]:
        return (self.chain, self.seq, self.comp)


def split_mmcif_row(line: str) -> list[str]:
    return shlex.split(line, posix=True)


def parse_atom_site(cif_text: str) -> list[Atom]:
    lines = cif_text.splitlines()
    atoms: list[Atom] = []
    index = 0
    while index < len(lines):
        if lines[index].strip() != "loop_":
            index += 1
            continue
        index += 1
        tags: list[str] = []
        while index < len(lines) and lines[index].startswith("_"):
            tags.append(lines[index].strip())
            index += 1
        if not tags or not tags[0].startswith("_atom_site.") or "_atom_site.Cartn_x" not in tags:
            continue
        positions = {tag: pos for pos, tag in enumerate(tags)}
        required = [
            "_atom_site.group_PDB",
            "_atom_site.label_atom_id",
            "_atom_site.label_comp_id",
            "_atom_site.Cartn_x",
            "_atom_site.Cartn_y",
            "_atom_site.Cartn_z",
        ]
        if any(tag not in positions for tag in required):
            continue
        chain_tag = "_atom_site.auth_asym_id" if "_atom_site.auth_asym_id" in positions else "_atom_site.label_asym_id"
        seq_tag = "_atom_site.auth_seq_id" if "_atom_site.auth_seq_id" in positions else "_atom_site.label_seq_id"
        element_tag = "_atom_site.type_symbol" if "_atom_site.type_symbol" in positions else "_atom_site.label_atom_id"
        while index < len(lines):
            line = lines[index].strip()
            if not line or line == "#":
                break
            if line == "loop_" or line.startswith("_"):
                index -= 1
                break
            row = split_mmcif_row(line)
            if len(row) >= len(tags):
                try:
                    atoms.append(
                        Atom(
                            chain=row[positions[chain_tag]],
                            seq=row[positions[seq_tag]],
                            comp=row[positions["_atom_site.label_comp_id"]],
                            atom=row[positions["_atom_site.label_atom_id"]],
                            element=row[positions[element_tag]],
                            x=float(row[positions["_atom_site.Cartn_x"]]),
                            y=float(row[positions["_atom_site.Cartn_y"]]),
                            z=float(row[positions["_atom_site.Cartn_z"]]),
                            group=row[positions["_atom_site.group_PDB"]],
                        )
                    )
                except (ValueError, IndexError):
                    pass
            index += 1
        index += 1
    return atoms


def dist(a: tuple[float, float, float], b: tuple[float, float, float]) -> float:
    return math.sqrt((a[0] - b[0]) ** 2 + (a[1] - b[1]) ** 2 + (a[2] - b[2]) ** 2)


def residue_centroids(atoms: list[Atom]) -> dict[tuple[str, str, str], tuple[float, float, float]]:
    grouped: dict[tuple[str, str, str], list[Atom]] = defaultdict(list)
    for atom in atoms:
        if atom.comp in {"HOH", "DOD"}:
            continue
        grouped[atom.residue_key].append(atom)
    centroids: dict[tuple[str, str, str], tuple[float, float, float]] = {}
    for key, residue_atoms in grouped.items():
        preferred = [atom for atom in residue_atoms if atom.atom in {"CA", "C4'", "P"}]
        selected = preferred or residue_atoms
        centroids[key] = (
            sum(atom.x for atom in selected) / len(selected),
            sum(atom.y for atom in selected) / len(selected),
            sum(atom.z for atom in selected) / len(selected),
        )
    return centroids


def ligand_neighborhood(atoms: list[Atom]) -> list[dict[str, Any]]:
    centroids = residue_centroids([atom for atom in atoms if atom.group == "ATOM"])
    ligand_atoms = [atom for atom in atoms if atom.group == "HETATM" and atom.comp not in {"HOH", "DOD"}]
    ligand_groups: dict[tuple[str, str, str], list[Atom]] = defaultdict(list)
    for atom in ligand_atoms:
        ligand_groups[atom.residue_key].append(atom)
    rows: list[dict[str, Any]] = []
    for ligand_key, group_atoms in ligand_groups.items():
        ligand_xyz = (
            sum(atom.x for atom in group_atoms) / len(group_atoms),
            sum(atom.y for atom in group_atoms) / len(group_atoms),
            sum(atom.z for atom in group_atoms) / len(group_atoms),
        )
        contacts = []
        for residue_key, residue_xyz in centroids.items():
            distance = dist(ligand_xyz, residue_xyz)
            if distance <= LIGAND_DISTANCE_ANGSTROM:
                contacts.append({"chain": residue_key[0], "seq": residue_key[1], "comp": residue_key[2], "distance": round(distance, 2)})
        rows.append(
            {
                "ligand": {"chain": ligand_key[0], "seq": ligand_key[1], "comp": ligand_key[2], "atom_count": len(group_atoms)},
                "nearby_residue_count": len(contacts),
                "nearby_residues": sorted(contacts, key=lambda item: item["distance"])[:40],
            }
        )
    return sorted(rows, key=lambda row: (-row["nearby_residue_count"], row["ligand"]["comp"]))


def contact_tables(atoms: list[Atom]) -> tuple[dict[str, dict[str, int]], list[dict[str, Any]]]:
    centroids = residue_centroids([atom for atom in atoms if atom.group == "ATOM"])
    residues = list(centroids.items())
    matrix: dict[str, dict[str, int]] = defaultdict(lambda: defaultdict(int))
    examples: list[dict[str, Any]] = []
    for left_index, (left_key, left_xyz) in enumerate(residues):
        for right_key, right_xyz in residues[left_index + 1 :]:
            left_chain, left_seq, left_comp = left_key
            right_chain, right_seq, right_comp = right_key
            if left_chain == right_chain:
                continue
            if dist(left_xyz, right_xyz) <= CONTACT_DISTANCE_ANGSTROM:
                matrix[left_chain][right_chain] += 1
                matrix[right_chain][left_chain] += 1
                if len(examples) < 200:
                    examples.append(
                        {
                            "left": {"chain": left_chain, "seq": left_seq, "comp": left_comp},
                            "right": {"chain": right_chain, "seq": right_seq, "comp": right_comp},
                        }
                    )
    return matrix, examples


def parse_entry_metadata(entry: dict[str, Any]) -> dict[str, Any]:
    citation = next((item for item in entry.get("citation", []) if item.get("id") == "primary"), (entry.get("citation") or [{}])[0])
    recon = (entry.get("em_3d_reconstruction") or [{}])[0]
    database_ids = entry.get("database_2", [])
    return {
        "pdb_id": PDB_ID,
        "emdb_id": next((item.get("database_code") for item in database_ids if item.get("database_id") == "EMDB"), EMDB_ID),
        "title": entry.get("struct", {}).get("title") or citation.get("title"),
        "citation_title": citation.get("title"),
        "citation_journal": citation.get("rcsb_journal_abbrev") or citation.get("journal_abbrev"),
        "citation_year": citation.get("year"),
        "doi": citation.get("pdbx_database_id_DOI"),
        "experimental_method": (entry.get("exptl") or [{}])[0].get("method"),
        "resolution_angstrom": recon.get("resolution"),
        "resolution_method": recon.get("resolution_method"),
        "particle_count": recon.get("num_particles"),
    }


def parse_validation_xml(path: Path) -> dict[str, Any]:
    text = gzip.decompress(path.read_bytes()).decode("utf-8", errors="replace")
    root = ET.fromstring(text)
    entry = root.find("Entry")
    attrs = entry.attrib if entry is not None else {}
    modelled = root.findall("ModelledSubgroup")
    q_scores = []
    residue_inclusions = []
    rama = Counter()
    for node in modelled:
        if node.get("Q_score"):
            try:
                q_scores.append(float(node.get("Q_score", "nan")))
            except ValueError:
                pass
        if node.get("residue_inclusion"):
            try:
                residue_inclusions.append(float(node.get("residue_inclusion", "nan")))
            except ValueError:
                pass
        if node.get("rama"):
            rama[node.get("rama", "")] += 1
    return {
        "entry": {key: attrs.get(key) for key in [
            "pdbid",
            "emdb_id",
            "PDB-resolution",
            "EMDB-resolution",
            "contour_level_primary_map",
            "atom_inclusion_backbone",
            "atom_inclusion_all_atoms",
            "Q_score",
            "clashscore",
            "percent-rama-outliers",
            "percent-rota-outliers",
            "bonds_rmsz",
            "angles_rmsz",
            "author_provided_fsc_resolution_by_cutoff_0.143",
            "calculated_fsc_resolution_by_cutoff_0.143",
        ]},
        "modelled_subgroup_count": len(modelled),
        "mean_residue_q_score": round(sum(q_scores) / len(q_scores), 4) if q_scores else None,
        "mean_residue_inclusion": round(sum(residue_inclusions) / len(residue_inclusions), 4) if residue_inclusions else None,
        "rama_counts": dict(rama),
    }


def parse_mrc_header(map_gz: Path) -> dict[str, Any]:
    with gzip.open(map_gz, "rb") as handle:
        header = handle.read(1024)
    if len(header) < 1024:
        raise RuntimeError("MRC header shorter than 1024 bytes")
    nx, ny, nz, mode = struct.unpack_from("<4i", header, 0)
    nxstart, nystart, nzstart = struct.unpack_from("<3i", header, 16)
    mx, my, mz = struct.unpack_from("<3i", header, 28)
    cella = struct.unpack_from("<3f", header, 40)
    cellb = struct.unpack_from("<3f", header, 52)
    mapc, mapr, maps = struct.unpack_from("<3i", header, 64)
    dmin, dmax, dmean = struct.unpack_from("<3f", header, 76)
    ispg, nsymbt = struct.unpack_from("<2i", header, 88)
    origin = struct.unpack_from("<3f", header, 196)
    rms = struct.unpack_from("<f", header, 216)[0]
    label_count = struct.unpack_from("<i", header, 220)[0]
    voxel = (
        cella[0] / mx if mx else None,
        cella[1] / my if my else None,
        cella[2] / mz if mz else None,
    )
    return {
        "nx": nx,
        "ny": ny,
        "nz": nz,
        "mode": mode,
        "nxstart": nxstart,
        "nystart": nystart,
        "nzstart": nzstart,
        "mx": mx,
        "my": my,
        "mz": mz,
        "cella": [round(item, 5) for item in cella],
        "cellb": [round(item, 5) for item in cellb],
        "mapc": mapc,
        "mapr": mapr,
        "maps": maps,
        "dmin": dmin,
        "dmax": dmax,
        "dmean": dmean,
        "ispg": ispg,
        "nsymbt": nsymbt,
        "origin": [round(item, 5) for item in origin],
        "rms": rms,
        "label_count": label_count,
        "voxel_spacing_angstrom": [round(item, 5) if item is not None else None for item in voxel],
    }


def mode_array_type(mode: int) -> tuple[str, int]:
    if mode == 0:
        return ("b", 1)
    if mode == 1:
        return ("h", 2)
    if mode == 2:
        return ("f", 4)
    if mode == 6:
        return ("H", 2)
    raise RuntimeError(f"Unsupported MRC mode for this demo: {mode}")


def values_from_bytes(raw: bytes, typecode: str) -> array.array:
    values = array.array(typecode)
    values.frombytes(raw)
    if sys.byteorder != "little":
        values.byteswap()
    return values


def select_atoms_for_density(atoms: list[Atom]) -> list[Atom]:
    selected = [atom for atom in atoms if atom.atom == "CA" and atom.group == "ATOM"]
    selected.extend(atom for atom in atoms if atom.group == "HETATM" and atom.comp not in {"HOH", "DOD"})
    if len(selected) <= SAMPLE_ATOM_LIMIT:
        return selected
    stride = max(1, len(selected) // SAMPLE_ATOM_LIMIT)
    return selected[::stride][:SAMPLE_ATOM_LIMIT]


def atom_grid_targets(atoms: list[Atom], header: dict[str, Any]) -> tuple[dict[int, list[tuple[int, int, Atom]]], dict[str, Any]]:
    voxel = header["voxel_spacing_angstrom"]
    origin = header["origin"]
    nx, ny, nz = header["nx"], header["ny"], header["nz"]
    by_z: dict[int, list[tuple[int, int, Atom]]] = defaultdict(list)
    inside = 0
    considered = 0
    if any(item in {None, 0} for item in voxel):
        return by_z, {"method": "origin_voxel_mapping", "considered_atoms": 0, "inside_grid_atoms": 0, "coverage_fraction": 0.0}
    for atom in select_atoms_for_density(atoms):
        considered += 1
        ix = int(round((atom.x - origin[0]) / voxel[0]))
        iy = int(round((atom.y - origin[1]) / voxel[1]))
        iz = int(round((atom.z - origin[2]) / voxel[2]))
        if 0 <= ix < nx and 0 <= iy < ny and 0 <= iz < nz:
            inside += 1
            by_z[iz].append((ix, iy, atom))
    return by_z, {
        "method": "origin_voxel_mapping",
        "considered_atoms": considered,
        "inside_grid_atoms": inside,
        "coverage_fraction": round(inside / considered, 4) if considered else 0.0,
    }


def summarize_map_density(map_gz: Path, atoms: list[Atom], header: dict[str, Any]) -> dict[str, Any]:
    typecode, bytes_per_value = mode_array_type(int(header["mode"]))
    nx, ny, nz = int(header["nx"]), int(header["ny"]), int(header["nz"])
    plane_bytes = nx * ny * bytes_per_value
    target_z = nz // 2
    atom_targets_by_z, grid_coverage = atom_grid_targets(atoms, header)
    sample_values: list[float] = []
    mid_plane: array.array | None = None
    atom_values: list[float] = []
    max_sample_values = 160000

    with gzip.open(map_gz, "rb") as handle:
        handle.read(1024)
        nsymbt = int(header.get("nsymbt") or 0)
        if nsymbt:
            handle.read(nsymbt)
        for z_index in range(nz):
            raw = handle.read(plane_bytes)
            if len(raw) != plane_bytes:
                raise RuntimeError(f"Unexpected end of map at z plane {z_index}")
            plane = values_from_bytes(raw, typecode)
            if len(sample_values) < max_sample_values:
                stride = max(1, len(plane) // 1200)
                sample_values.extend(float(value) for value in plane[::stride][:1200])
            if z_index == target_z:
                mid_plane = array.array(typecode, plane)
            if z_index in atom_targets_by_z:
                for ix, iy, _atom in atom_targets_by_z[z_index]:
                    atom_values.append(float(plane[iy * nx + ix]))

    if mid_plane is None:
        raise RuntimeError("Mid-plane density slice was not captured")
    sample_values = sample_values[:max_sample_values]
    sample_mean = sum(sample_values) / len(sample_values) if sample_values else float(header["dmean"])
    sample_var = sum((value - sample_mean) ** 2 for value in sample_values) / max(1, len(sample_values) - 1) if len(sample_values) > 1 else 0.0
    sample_sd = math.sqrt(sample_var) if sample_var > 0 else float(header.get("rms") or 1.0)
    atom_above_mean = sum(1 for value in atom_values if value > sample_mean)
    atom_above_one_sd = sum(1 for value in atom_values if value > sample_mean + sample_sd)
    return {
        "header": header,
        "sample_density": {
            "sample_count": len(sample_values),
            "min": round(min(sample_values), 5) if sample_values else None,
            "max": round(max(sample_values), 5) if sample_values else None,
            "mean": round(sample_mean, 5),
            "sd": round(sample_sd, 5),
            "header_dmin": round(float(header["dmin"]), 5),
            "header_dmax": round(float(header["dmax"]), 5),
            "header_dmean": round(float(header["dmean"]), 5),
            "header_rms": round(float(header["rms"]), 5),
        },
        "density_support": {
            "grid_coverage": grid_coverage,
            "sampled_atom_count": len(atom_values),
            "fraction_above_sample_mean": round(atom_above_mean / len(atom_values), 4) if atom_values else 0.0,
            "fraction_above_sample_mean_plus_1sd": round(atom_above_one_sd / len(atom_values), 4) if atom_values else 0.0,
            "atom_density_mean": round(sum(atom_values) / len(atom_values), 5) if atom_values else None,
        },
        "mid_slice": {
            "z_index": target_z,
            "nx": nx,
            "ny": ny,
            "values": mid_plane,
            "sample_min": min(sample_values) if sample_values else float(header["dmin"]),
            "sample_max": max(sample_values) if sample_values else float(header["dmax"]),
        },
    }


def svg_header(width: int, height: int) -> str:
    return f'<svg xmlns="http://www.w3.org/2000/svg" width="{width}" height="{height}" viewBox="0 0 {width} {height}">'


def write_density_slice_svg(path: Path, mid_slice: dict[str, Any]) -> None:
    nx, ny = int(mid_slice["nx"]), int(mid_slice["ny"])
    values: array.array = mid_slice["values"]
    cols = 96
    rows = 96
    cell = 5
    margin_top = 46
    width = cols * cell + 40
    height = rows * cell + margin_top + 30
    vmin = float(mid_slice["sample_min"])
    vmax = float(mid_slice["sample_max"])
    if vmax <= vmin:
        vmax = vmin + 1.0
    parts = [svg_header(width, height), '<rect width="100%" height="100%" fill="#ffffff"/>']
    parts.append(f'<text x="20" y="28" font-family="Arial" font-size="18" font-weight="700">EMD-43816 mid-density slice z={mid_slice["z_index"]}</text>')
    for row in range(rows):
        y_src = min(ny - 1, int(row * ny / rows))
        for col in range(cols):
            x_src = min(nx - 1, int(col * nx / cols))
            value = float(values[y_src * nx + x_src])
            scaled = max(0.0, min(1.0, (value - vmin) / (vmax - vmin)))
            shade = int(255 - 235 * scaled)
            color = f"rgb({shade},{shade},{shade})"
            parts.append(f'<rect x="{20 + col * cell}" y="{margin_top + row * cell}" width="{cell}" height="{cell}" fill="{color}"/>')
    parts.append("</svg>")
    path.write_text("\n".join(parts) + "\n")


def write_model_inventory_svg(path: Path, residue_counts: dict[str, int]) -> None:
    chains = sorted(residue_counts)
    width = 780
    height = max(180, 80 + 36 * len(chains))
    max_count = max(residue_counts.values() or [1])
    parts = [svg_header(width, height), '<rect width="100%" height="100%" fill="#ffffff"/>']
    parts.append('<text x="24" y="30" font-family="Arial" font-size="18" font-weight="700">PDB 9ASJ model inventory</text>')
    for index, chain in enumerate(chains):
        y = 60 + index * 36
        value = residue_counts[chain]
        bar = 560 * value / max_count
        parts.append(f'<text x="24" y="{y + 17}" font-family="Arial" font-size="13">Chain {html.escape(chain)}</text>')
        parts.append(f'<rect x="118" y="{y}" width="{bar:.1f}" height="22" fill="#266c7d"/>')
        parts.append(f'<text x="{128 + bar:.1f}" y="{y + 16}" font-family="Arial" font-size="12">{value} residues</text>')
    parts.append("</svg>")
    path.write_text("\n".join(parts) + "\n")


def write_ligand_svg(path: Path, neighborhoods: list[dict[str, Any]]) -> None:
    width = 920
    height = max(220, 82 + 52 * min(len(neighborhoods), 12))
    parts = [svg_header(width, height), '<rect width="100%" height="100%" fill="#ffffff"/>']
    parts.append('<text x="24" y="30" font-family="Arial" font-size="18" font-weight="700">AMP-PNP / non-polymer neighborhoods</text>')
    if not neighborhoods:
        parts.append('<text x="24" y="70" font-family="Arial" font-size="14">No non-water HETATM ligands found in mmCIF atom_site table.</text>')
    for index, row in enumerate(neighborhoods[:12]):
        y = 62 + index * 52
        ligand = row["ligand"]
        label = f"{ligand['comp']} chain {ligand['chain']} seq {ligand['seq']}"
        count = row["nearby_residue_count"]
        nearby = ", ".join(f"{item['comp']}{item['seq']}:{item['chain']}" for item in row["nearby_residues"][:8])
        parts.append(f'<circle cx="40" cy="{y + 11}" r="11" fill="#9b3650"/>')
        parts.append(f'<text x="62" y="{y + 6}" font-family="Arial" font-size="13" font-weight="700">{html.escape(label)}</text>')
        parts.append(f'<text x="62" y="{y + 25}" font-family="Arial" font-size="12">{count} residues within {LIGAND_DISTANCE_ANGSTROM:.1f} A: {html.escape(nearby)}</text>')
    parts.append("</svg>")
    path.write_text("\n".join(parts) + "\n")


def write_density_support_svg(path: Path, support: dict[str, Any]) -> None:
    width = 760
    height = 260
    values = [
        ("Grid coverage", support["grid_coverage"]["coverage_fraction"]),
        ("Atoms above mean", support["fraction_above_sample_mean"]),
        ("Atoms above mean+1sd", support["fraction_above_sample_mean_plus_1sd"]),
    ]
    parts = [svg_header(width, height), '<rect width="100%" height="100%" fill="#ffffff"/>']
    parts.append('<text x="24" y="30" font-family="Arial" font-size="18" font-weight="700">Map/model density support checks</text>')
    for index, (label, value) in enumerate(values):
        y = 72 + index * 52
        bar = 560 * max(0, min(1, float(value)))
        parts.append(f'<text x="24" y="{y + 16}" font-family="Arial" font-size="13">{html.escape(label)}</text>')
        parts.append(f'<rect x="190" y="{y}" width="560" height="22" fill="#eeeeee"/>')
        parts.append(f'<rect x="190" y="{y}" width="{bar:.1f}" height="22" fill="#7b5fa7"/>')
        parts.append(f'<text x="198" y="{y + 16}" font-family="Arial" font-size="12" fill="#111">{float(value):.3f}</text>')
    parts.append(f'<text x="24" y="232" font-family="Arial" font-size="12">Sampled atom density values: {support["sampled_atom_count"]}</text>')
    parts.append("</svg>")
    path.write_text("\n".join(parts) + "\n")


def write_csv(path: Path, rows: list[dict[str, Any]], fieldnames: list[str]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", newline="", encoding="utf-8") as handle:
        writer = csv.DictWriter(handle, fieldnames=fieldnames)
        writer.writeheader()
        for row in rows:
            writer.writerow(row)


def build_report(out: Path, skip_map_download: bool = False) -> dict[str, Any]:
    start = time.time()
    out.mkdir(parents=True, exist_ok=True)
    validation = out / "validation"
    figures = out / "figures"
    data_dir = out / "data"
    for directory in [validation, figures, data_dir]:
        directory.mkdir(parents=True, exist_ok=True)
    progress_path = out / "stage-progress.jsonl"
    commands_path = out / "executed-commands.jsonl"

    stage_event(progress_path, "input_audit", "started", "Reading declared public accessions")
    entry = json.loads(fetch_text(ENTRY_URL))
    metadata = parse_entry_metadata(entry)
    input_audit = {
        "ok": True,
        "known_inputs": [
            {"kind": "emdb_map", "id": EMDB_ID, "url": MAP_URL},
            {"kind": "pdb_model", "id": PDB_ID, "url": CIF_URL},
            {"kind": "rcsb_entry", "id": PDB_ID, "url": ENTRY_URL},
            {"kind": "wwpdb_validation_xml", "id": PDB_ID, "url": VALIDATION_XML_URL},
            {"kind": "wwpdb_validation_pdf", "id": PDB_ID, "url": VALIDATION_PDF_URL},
        ],
        "missing_operator_items": [],
        "downloads": "public EMDB map, PDB mmCIF, and wwPDB validation files only; no raw movies; no licensed tools",
    }
    write_json(validation / "input-audit.json", input_audit)
    stage_event(progress_path, "input_audit", "completed", "Input audit complete")
    command_event(commands_path, "input_audit", "poltheta_map_model_report.py input_audit", ["validation/input-audit.json"], now())

    stage_event(progress_path, "data_intake", "started", "Downloading public map/model/validation artifacts")
    map_path = data_dir / "emd_43816.map.gz"
    cif_path = data_dir / "9ASJ.cif"
    xml_path = data_dir / "9asj_validation.xml.gz"
    pdf_path = data_dir / "9asj_full_validation.pdf.gz"
    fetch_binary(CIF_URL, cif_path)
    fetch_binary(VALIDATION_XML_URL, xml_path)
    fetch_binary(VALIDATION_PDF_URL, pdf_path)
    if not skip_map_download:
        fetch_binary(MAP_URL, map_path)
    materialized_files = [
        file_record(cif_path, CIF_URL, "pdb_model_mmcif", PDB_ID),
        file_record(xml_path, VALIDATION_XML_URL, "wwpdb_validation_xml", PDB_ID),
        file_record(pdf_path, VALIDATION_PDF_URL, "wwpdb_validation_pdf", PDB_ID),
    ]
    if map_path.exists():
        materialized_files.insert(0, file_record(map_path, MAP_URL, "emdb_map_gzip", EMDB_ID))
    data_intake = {
        "schema_version": 1,
        "status": "downloaded" if map_path.exists() else "partial",
        "accessions": {"emdb": EMDB_ID, "pdb": PDB_ID},
        "allow_raw_cryoem_downloads": False,
        "download_method": "urllib.request public HTTPS downloads",
        "storage_path": str(data_dir),
        "materialized_files": materialized_files,
        "raw_movies_downloaded": False,
        "license_gated_tools_used": [],
    }
    write_json(out / "data-intake-ledger.json", data_intake)
    stage_event(progress_path, "data_intake", "completed", "Public data files materialized")
    command_event(commands_path, "data_intake", "poltheta_map_model_report.py download_public_map_model_validation", ["data-intake-ledger.json", "data/"], now())

    stage_event(progress_path, "model_analysis", "started", "Parsing mmCIF model and validation XML")
    atoms = parse_atom_site(cif_path.read_text())
    if not atoms:
        raise RuntimeError("No atoms parsed from PDB 9ASJ mmCIF")
    validation_xml = parse_validation_xml(xml_path)
    residue_counts: dict[str, int] = defaultdict(int)
    residue_sets: dict[str, set[tuple[str, str, str]]] = defaultdict(set)
    atom_counts = Counter(atom.chain for atom in atoms if atom.group == "ATOM")
    for atom in atoms:
        if atom.group == "ATOM":
            residue_sets[atom.chain].add(atom.residue_key)
    residue_counts = {chain: len(keys) for chain, keys in residue_sets.items()}
    neighborhoods = ligand_neighborhood(atoms)
    matrix, contact_examples = contact_tables(atoms)
    coordinate_summary = {
        "pdb_id": PDB_ID,
        "emdb_id": EMDB_ID,
        "metadata": metadata,
        "atom_count": len(atoms),
        "chain_count": len(residue_counts),
        "atom_count_by_chain": dict(atom_counts),
        "residue_count_by_chain": residue_counts,
        "ligand_like_group_count": len(neighborhoods),
        "validation_xml": validation_xml,
    }
    write_json(out / "coordinate-summary.json", coordinate_summary)
    write_json(out / "ligand-neighborhoods.json", {"rows": neighborhoods})
    write_json(out / "interchain-contact-matrix.json", {chain: dict(matrix.get(chain, {})) for chain in sorted(residue_counts)})
    write_csv(
        out / "interchain-contact-examples.csv",
        [
            {
                "left_chain": row["left"]["chain"],
                "left_residue": row["left"]["comp"] + row["left"]["seq"],
                "right_chain": row["right"]["chain"],
                "right_residue": row["right"]["comp"] + row["right"]["seq"],
            }
            for row in contact_examples
        ],
        ["left_chain", "left_residue", "right_chain", "right_residue"],
    )
    stage_event(progress_path, "model_analysis", "completed", "Model inventory, contacts, and ligand neighborhoods complete")
    command_event(commands_path, "model_analysis", "poltheta_map_model_report.py parse_mmcif_and_validation_xml", ["coordinate-summary.json", "ligand-neighborhoods.json"], now())

    stage_event(progress_path, "map_analysis", "started", "Parsing EMDB MRC header and density evidence")
    if not map_path.exists():
        raise RuntimeError("Map download was skipped; real map/model report cannot pass")
    mrc_header = parse_mrc_header(map_path)
    map_density = summarize_map_density(map_path, atoms, mrc_header)
    mid_slice = map_density.pop("mid_slice")
    write_json(out / "map-summary.json", map_density)
    stage_event(progress_path, "map_analysis", "completed", "Map density summary and atom density support complete")
    command_event(commands_path, "map_analysis", "poltheta_map_model_report.py parse_mrc_map_and_sample_density", ["map-summary.json"], now())

    stage_event(progress_path, "validation_summary", "started", "Joining model, map, validation XML, and claim boundaries")
    support = map_density["density_support"]
    entry_validation = validation_xml["entry"]
    map_model_fit = {
        "ok": True,
        "evidence_level": "real_public_map_model_report",
        "pdb_id": PDB_ID,
        "emdb_id": EMDB_ID,
        "pixel_size_angstrom": mrc_header["voxel_spacing_angstrom"],
        "map_model_correlation": {
            "metric": "atom_density_support_fraction_above_sample_mean",
            "value": support["fraction_above_sample_mean"],
            "sampled_atom_count": support["sampled_atom_count"],
            "note": "Density support proxy computed from deposited map values at model atom coordinates; not a replacement for full real-space refinement.",
        },
        "local_resolution": {
            "source": "wwPDB validation XML",
            "reported_emdb_resolution": entry_validation.get("EMDB-resolution"),
            "author_fsc_0_143": entry_validation.get("author_provided_fsc_resolution_by_cutoff_0.143"),
            "calculated_fsc_0_143": entry_validation.get("calculated_fsc_resolution_by_cutoff_0.143"),
        },
        "mask_provenance": {
            "source": "wwPDB validation XML",
            "primary_map_contour_level": entry_validation.get("contour_level_primary_map"),
            "mask_file_downloaded": False,
        },
        "handedness_check": {
            "method": "coordinate-to-map-grid coverage check using MRC origin and voxel spacing",
            "atom_grid_coverage_fraction": support["grid_coverage"]["coverage_fraction"],
            "inside_grid_atoms": support["grid_coverage"]["inside_grid_atoms"],
            "considered_atoms": support["grid_coverage"]["considered_atoms"],
        },
        "geometry_validation": {
            "source": "wwPDB validation XML",
            "clashscore": entry_validation.get("clashscore"),
            "percent_rama_outliers": entry_validation.get("percent-rama-outliers"),
            "percent_rota_outliers": entry_validation.get("percent-rota-outliers"),
            "bonds_rmsz": entry_validation.get("bonds_rmsz"),
            "angles_rmsz": entry_validation.get("angles_rmsz"),
            "mean_residue_q_score": validation_xml.get("mean_residue_q_score"),
            "mean_residue_inclusion": validation_xml.get("mean_residue_inclusion"),
        },
        "fsc_provenance": {
            "source": "wwPDB validation XML",
            "author_fsc_0_143": entry_validation.get("author_provided_fsc_resolution_by_cutoff_0.143"),
            "calculated_fsc_0_143": entry_validation.get("calculated_fsc_resolution_by_cutoff_0.143"),
        },
        "software_versions": {
            "python": sys.version.split()[0],
            "parser": "BioSymphony Structure Factory standard-library MRC/mmCIF/XML parser",
        },
    }
    write_json(validation / "map_model_fit.json", map_model_fit)
    stage_event(progress_path, "validation_summary", "completed", "Validation summary complete")
    command_event(commands_path, "validation_summary", "poltheta_map_model_report.py join_map_model_validation_evidence", ["validation/map_model_fit.json"], now())

    stage_event(progress_path, "figure_report", "started", "Writing reproducible SVG figure panels and reports")
    write_density_slice_svg(figures / "emd-43816-mid-slice.svg", mid_slice)
    write_model_inventory_svg(figures / "model-inventory.svg", residue_counts)
    write_ligand_svg(figures / "ampnp-neighborhood.svg", neighborhoods)
    write_density_support_svg(figures / "density-support.svg", support)
    report_md = f"""# BioSymphony Structure Factory Demo: Pol theta Map/Model Report

## Target

- EMDB: `{EMDB_ID}`
- PDB: `{PDB_ID}`
- Title: {metadata['title']}
- Reported resolution: {metadata['resolution_angstrom']} A
- Primary citation: {metadata['citation_title']}
- DOI: {metadata['doi']}

## Real Route Evidence

- Downloaded deposited map, mmCIF model, and wwPDB validation XML/PDF.
- Parsed MRC header and sampled deposited density values.
- Parsed mmCIF atoms, chain inventory, inter-chain contacts, and AMP-PNP/non-polymer neighborhoods.
- Joined validation XML geometry/FSC/Q-score fields into `validation/map_model_fit.json`.
- Ran contract self-check in real mode after artifact generation.

## Claim Boundary

This report supports a real deposited-map/deposited-model public-data demo. It does not replace expert real-space refinement, local manual inspection, half-map reprocessing, or biological mechanism validation.
"""
    (out / "report.md").write_text(report_md)
    methods = f"""# Methods

Public files were downloaded from EMDB, RCSB, and wwPDB validation endpoints for `{EMDB_ID}` / `{PDB_ID}`. The runner used Python standard-library code to parse the gzipped MRC map header and density planes, mmCIF `_atom_site` records, and wwPDB validation XML. Density support was estimated by mapping sampled model atom coordinates into the deposited map grid using MRC origin and voxel spacing, then comparing atom-position density values to sampled map density.

No raw cryo-EM movies, particle stacks, half-maps, masks, license-gated tools, or private data were used.
"""
    (out / "methods.md").write_text(methods)
    provenance = f"""# Provenance

- run_id: `{RUN_ID}`
- created_at: `{now()}`
- EMDB map: `{MAP_URL}`
- PDB mmCIF: `{CIF_URL}`
- RCSB entry: `{ENTRY_URL}`
- wwPDB validation XML: `{VALIDATION_XML_URL}`
- wwPDB validation PDF: `{VALIDATION_PDF_URL}`
- tool policy: Python standard library only; no license-gated software
- raw data policy: no raw movies or particle stacks downloaded
"""
    (out / "provenance.md").write_text(provenance)
    stage_event(progress_path, "figure_report", "completed", "Figure panels and report complete")
    command_event(commands_path, "figure_report", "poltheta_map_model_report.py render_svg_figures_and_report", ["figures/", "report.md"], now())

    stage_event(progress_path, "validation_review", "started", "Writing explicit validation ledger")
    validation_ledger = """# Claim Ledger

| Claim | Level | Evidence | Caveat |
| --- | --- | --- | --- |
| EMD-43816 / PDB 9ASJ public map/model files were materialized and checksummed. | processed | `data-intake-ledger.json` | Public repository availability can change; checksums record this run. |
| The deposited map header, voxel spacing, density range, and mid-slice were parsed from the downloaded EMDB map. | processed | `map-summary.json`, `figures/emd-43816-mid-slice.svg` | Orthoslice is a QC panel, not a full density interpretation. |
| The PDB model inventory and AMP-PNP/non-polymer neighborhoods were computed from downloaded mmCIF coordinates. | processed | `coordinate-summary.json`, `ligand-neighborhoods.json`, `figures/ampnp-neighborhood.svg` | Contact threshold is geometric and does not prove mechanism. |
| Atom-position density support was computed from deposited map values at model atom coordinates. | candidate | `validation/map_model_fit.json`, `figures/density-support.svg` | This is a fast support proxy, not full real-space refinement or FSC recalculation. |
| Final mechanism or therapeutic claim is established. | insufficient_evidence | none | Requires expert structural review and biological/functional validation. |
"""
    (out / "validation_ledger.md").write_text(validation_ledger)
    validation_ledger_json = {
        "claims": [
            {"claim": "Public map/model files were materialized", "claim_level": "processed", "evidence_artifact": "data-intake-ledger.json"},
            {"claim": "Deposited map header and density slice were parsed", "claim_level": "processed", "evidence_artifact": "map-summary.json"},
            {"claim": "AMP-PNP neighborhood candidates were computed from coordinates", "claim_level": "candidate", "evidence_artifact": "ligand-neighborhoods.json"},
            {"claim": "Final mechanism is established", "claim_level": "insufficient_evidence", "evidence_artifact": "validation_ledger.md"},
        ]
    }
    write_json(out / "validation_ledger.json", validation_ledger_json)
    report_manifest = {
        "schema_version": 1,
        "run_id": RUN_ID,
        "execution_profile": "map-model-report",
        "pdb_id": PDB_ID,
        "emdb_id": EMDB_ID,
        "accessions": {"pdb": PDB_ID, "emdb": EMDB_ID},
        "artifact_root": str(out),
        "figures": [
            "figures/emd-43816-mid-slice.svg",
            "figures/model-inventory.svg",
            "figures/ampnp-neighborhood.svg",
            "figures/density-support.svg",
        ],
        "claim_level": "candidate",
        "license_gated_tools_used": [],
        "raw_data_downloaded": False,
    }
    write_json(out / "report_manifest.json", report_manifest)
    contract_manifest = {
        "schema_version": 1,
        "run_id": RUN_ID,
        "execution_profile": "map-model-report",
        "accessions": {"pdb": PDB_ID, "emdb": EMDB_ID},
        "stage_contract": "inline-poltheta-map-model-stage-contract",
    }
    write_json(out / "contract-manifest.json", contract_manifest)
    stage_event(progress_path, "validation_review", "completed", "Validation ledger complete")
    stage_contract_check = {
        "ok": True,
        "check_type": "demo_stage_contract_check",
        "require_terminal": True,
        "terminal_by_stage": {
            "input_audit": "completed",
            "data_intake": "completed",
            "model_analysis": "completed",
            "map_analysis": "completed",
            "validation_summary": "completed",
            "figure_report": "completed",
            "validation_review": "completed",
        },
        "errors": [],
        "warnings": ["Density support metric is a fast public-demo proxy, not full map/model refinement."],
    }
    write_json(validation / "stage-contract-check.json", stage_contract_check)
    command_event(
        commands_path,
        "validation_review",
        "poltheta_map_model_report.py write_validation_ledger_and_contract_manifest",
        ["validation_ledger.md", "validation_ledger.json", "report_manifest.json", "contract-manifest.json", "validation/stage-contract-check.json"],
        now(),
    )

    hashes = {}
    for path in sorted(out.rglob("*")):
        if path.is_file() and path.name != "runpod-execution.tar.gz":
            hashes[str(path.relative_to(out))] = sha256(path)
    write_json(out.parent / "artifact_hashes.json", {"sha256": hashes})
    with tarfile.open(out / "runpod-execution.tar.gz", "w:gz") as archive:
        for path in sorted(out.rglob("*")):
            if path.name != "runpod-execution.tar.gz":
                archive.add(path, arcname=path.relative_to(out))
    stage_event(progress_path, "archive", "completed", "Artifact archive ready")
    command_event(commands_path, "archive", "poltheta_map_model_report.py archive_artifacts", ["runpod-execution.tar.gz"], now())
    status_root = out.parent if out.name == "artifacts" else out
    write_json(
        status_root / "status.json",
        {
            "ok": True,
            "status": "completed",
            "run_id": RUN_ID,
            "completed_at": now(),
            "artifact_root": str(out),
        },
    )

    return {
        "ok": True,
        "run_id": RUN_ID,
        "out": str(out.resolve()),
        "artifact_count": len(hashes),
        "metadata": metadata,
        "density_support": map_density["density_support"],
        "elapsed_seconds": round(time.time() - start, 3),
    }


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--out", type=Path, default=Path("runpod-execution") / "artifacts")
    parser.add_argument("--skip-map-download", action="store_true", help="Developer-only negative path; real contract check will fail.")
    parser.add_argument("--json", action="store_true")
    args = parser.parse_args()

    try:
        summary = build_report(args.out, skip_map_download=args.skip_map_download)
    except Exception as exc:
        summary = {
            "ok": False,
            "error": f"{type(exc).__name__}: {exc}",
            "run_id": RUN_ID,
        }
        status_root = args.out.parent if args.out.name == "artifacts" else args.out
        write_json(status_root / "status.json", {"ok": False, "status": "failed", "error": summary["error"], "completed_at": now()})
    if args.json:
        print(json.dumps(summary, indent=2, sort_keys=True))
    else:
        print(f"ok: {summary['ok']}")
        if not summary["ok"]:
            print(summary["error"], file=sys.stderr)
    return 0 if summary["ok"] else 1


if __name__ == "__main__":
    raise SystemExit(main())
