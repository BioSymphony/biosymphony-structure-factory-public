"""Publish operator-supplied PDB backbones as count-preserving binder rows.

The adapter runs no design model. It verifies each input file hash, copies one
polymer chain into an adapter-owned pose, and records the pose hash. Failed or
filtered upstream rows remain in the output as ``not_evaluable`` rows.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import os
import re
import sys
import tempfile
from pathlib import Path
from typing import Any, Mapping


BACKBONE_SCHEMA = "structure-factory-supplied-backbone-v1"
READINESS_SCHEMA = "structure-factory-supplied-backbone-readiness-v1"
ELIGIBLE_STATUSES = frozenset({"completed", "eligible", "generated", "passed", "scored"})
CANDIDATE_ID_RE = re.compile(r"^[a-z0-9][a-z0-9._-]{0,127}$")
CHAIN_ID_RE = re.compile(r"^[A-Za-z0-9]$")
SHA256_RE = re.compile(r"^[0-9a-f]{64}$")
READ_BLOCK_BYTES = 1024 * 1024


class SuppliedBackboneError(ValueError):
    """A supplied row cannot satisfy the backbone contract."""


def sha256_file(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for block in iter(lambda: handle.read(READ_BLOCK_BYTES), b""):
            digest.update(block)
    return digest.hexdigest()


def _atomic_write(path: Path, payload: bytes) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with tempfile.NamedTemporaryFile("wb", dir=path.parent, delete=False) as handle:
        handle.write(payload)
        temporary = Path(handle.name)
    os.replace(temporary, path)


def _write_jsonl(path: Path, rows: list[dict[str, Any]]) -> None:
    payload = "".join(
        json.dumps(row, sort_keys=True, separators=(",", ":"), allow_nan=False) + "\n"
        for row in rows
    ).encode("utf-8")
    _atomic_write(path, payload)


def _contained_path(root: Path, raw: Path, label: str, *, output: bool = False) -> Path:
    resolved_root = root.resolve()
    candidate = raw if raw.is_absolute() else resolved_root / raw
    resolved = candidate.resolve()
    if resolved == resolved_root or resolved_root not in resolved.parents:
        raise SuppliedBackboneError(f"{label} must name a path below the run root")
    if not output and (not resolved.is_file() or resolved.is_symlink()):
        raise SuppliedBackboneError(f"{label} must name a regular file below the run root")
    return resolved


def _relative(root: Path, path: Path) -> str:
    return path.resolve().relative_to(root.resolve()).as_posix()


def _read_rows(path: Path) -> list[dict[str, Any]]:
    rows: list[dict[str, Any]] = []
    seen: set[str] = set()
    for line_number, line in enumerate(path.read_text(encoding="utf-8").splitlines(), start=1):
        if not line.strip():
            continue
        try:
            row = json.loads(line)
        except json.JSONDecodeError as exc:
            raise SuppliedBackboneError(f"backbone JSONL line {line_number} is invalid") from exc
        if not isinstance(row, dict):
            raise SuppliedBackboneError(f"backbone JSONL line {line_number} must be an object")
        candidate_id = row.get("candidate_id")
        if not isinstance(candidate_id, str) or CANDIDATE_ID_RE.fullmatch(candidate_id) is None:
            raise SuppliedBackboneError(
                f"backbone JSONL line {line_number} has an invalid candidate_id"
            )
        if candidate_id in seen:
            raise SuppliedBackboneError("backbone candidate IDs must be unique")
        seen.add(candidate_id)
        if not isinstance(row.get("status"), str) or not row["status"]:
            raise SuppliedBackboneError(
                f"backbone JSONL line {line_number} must carry a status"
            )
        filter_results = row.get("filter_results", [])
        if not isinstance(filter_results, list) or any(
            not isinstance(item, dict) for item in filter_results
        ):
            raise SuppliedBackboneError(
                f"backbone JSONL line {line_number} filter_results must be a list of objects"
            )
        rows.append(dict(row))
    if not rows:
        raise SuppliedBackboneError("backbone JSONL contains no rows")
    return rows


def _eligible(row: Mapping[str, Any]) -> bool:
    return row["status"] in ELIGIBLE_STATUSES and not any(
        result.get("state") in {"filtered", "not_evaluable"}
        for result in row.get("filter_results", [])
    )


def _first_model_atom_records(path: Path) -> list[str]:
    atoms: list[str] = []
    in_model = False
    model_closed = False
    for line in path.read_text(encoding="utf-8", errors="replace").splitlines():
        if line.startswith("MODEL "):
            in_model = True
            continue
        if line.startswith("ENDMDL"):
            if in_model:
                model_closed = True
            continue
        if model_closed:
            continue
        if line.startswith(("ATOM  ", "HETATM")):
            atoms.append(line)
    if not atoms:
        raise SuppliedBackboneError("supplied structure contains no coordinate records")
    return atoms


def _chain_atoms(atoms: list[str], source_chain: str) -> tuple[list[str], int]:
    selected: list[str] = []
    residue_keys: set[tuple[int, str]] = set()
    available: set[str] = set()
    for line in atoms:
        if not line.startswith("ATOM  "):
            continue
        chain_id = line[21:22]
        if chain_id.strip():
            available.add(chain_id)
        if chain_id != source_chain:
            continue
        raw_number = line[22:26].strip()
        if not raw_number:
            continue
        try:
            residue_number = int(raw_number)
        except ValueError:
            continue
        residue_keys.add((residue_number, line[26:27].strip()))
        selected.append(line)
    if not selected:
        names = ", ".join(sorted(available)) if available else "none"
        raise SuppliedBackboneError(
            f"supplied structure has no polymer chain {source_chain}; available chains: {names}"
        )
    return selected, len(residue_keys)


def _pose_bytes(
    *,
    candidate_id: str,
    source_path: str,
    source_sha256: str,
    source_chain: str,
    binder_chain: str,
    atoms: list[str],
) -> bytes:
    relabelled = [line[:21] + binder_chain + line[22:] for line in atoms]
    lines = [
        f"REMARK 900 CANDIDATE {candidate_id}",
        f"REMARK 900 SUPPLIED STRUCTURE {source_path}",
        f"REMARK 900 SUPPLIED SHA256 {source_sha256}",
        f"REMARK 900 SOURCE CHAIN {source_chain} BINDER CHAIN {binder_chain}",
        "REMARK 900 COPIED BACKBONE; NO DESIGN MODEL RAN",
        *relabelled,
        "TER",
        "END",
    ]
    return ("\n".join(lines) + "\n").encode("utf-8")


def run_backbones(
    *,
    run_root: Path,
    input_path: Path,
    output_path: Path,
    pose_dir: Path,
    source_chain: str,
    binder_chain: str,
    minimum_length: int,
    maximum_length: int,
    expected_count: int,
) -> dict[str, Any]:
    """Copy eligible structures and preserve every input row."""
    if CHAIN_ID_RE.fullmatch(source_chain) is None or CHAIN_ID_RE.fullmatch(binder_chain) is None:
        raise SuppliedBackboneError("source and binder chain IDs must be one alphanumeric character")
    if minimum_length < 1 or maximum_length < minimum_length:
        raise SuppliedBackboneError("length bounds must be positive and ordered")
    if expected_count < 1:
        raise SuppliedBackboneError("expected_count must be a positive integer")
    root = run_root.resolve()
    source = _contained_path(root, input_path, "input")
    destination = _contained_path(root, output_path, "output", output=True)
    poses = _contained_path(root, pose_dir, "pose directory", output=True)
    if destination == source:
        raise SuppliedBackboneError("output must differ from input")
    rows = _read_rows(source)
    if len(rows) != expected_count:
        raise SuppliedBackboneError(
            f"backbone input has {len(rows)} rows; expected {expected_count}"
        )
    prepared: dict[str, tuple[str, str, list[str], int]] = {}
    for row in rows:
        if not _eligible(row):
            continue
        raw_path = row.get("structure_path")
        recorded_hash = row.get("structure_sha256")
        if not isinstance(raw_path, str) or not raw_path or Path(raw_path).is_absolute():
            raise SuppliedBackboneError(
                f"candidate {row['candidate_id']} structure_path must be run-root-relative"
            )
        if not isinstance(recorded_hash, str) or SHA256_RE.fullmatch(recorded_hash) is None:
            raise SuppliedBackboneError(
                f"candidate {row['candidate_id']} must carry a lowercase structure_sha256"
            )
        path = _contained_path(root, Path(raw_path), "supplied structure")
        observed_hash = sha256_file(path)
        if observed_hash != recorded_hash:
            raise SuppliedBackboneError(
                f"candidate {row['candidate_id']} structure_sha256 does not match its file"
            )
        atoms, residue_count = _chain_atoms(_first_model_atom_records(path), source_chain)
        if not minimum_length <= residue_count <= maximum_length:
            raise SuppliedBackboneError(
                f"candidate {row['candidate_id']} chain length {residue_count} is outside "
                f"{minimum_length}..{maximum_length}"
            )
        prepared[row["candidate_id"]] = (raw_path, observed_hash, atoms, residue_count)
    output_rows: list[dict[str, Any]] = []
    generated = 0
    not_evaluable = 0
    for source_row in rows:
        row = dict(source_row)
        row["upstream_status"] = source_row["status"]
        if not _eligible(source_row):
            row["backbone"] = {
                "schema_version": BACKBONE_SCHEMA,
                "state": "not_evaluable",
                "origin_source": "supplied_structure",
                "reason": "upstream_status_or_filter",
                "design_pose_path": None,
                "design_pose_sha256": None,
            }
            not_evaluable += 1
            output_rows.append(row)
            continue
        raw_path, source_hash, atoms, residue_count = prepared[source_row["candidate_id"]]
        pose_path = poses / f"{source_row['candidate_id']}.pdb"
        _atomic_write(
            pose_path,
            _pose_bytes(
                candidate_id=source_row["candidate_id"],
                source_path=raw_path,
                source_sha256=source_hash,
                source_chain=source_chain,
                binder_chain=binder_chain,
                atoms=atoms,
            ),
        )
        row["status"] = "generated"
        row["backbone_only"] = True
        row["origin_source"] = "supplied_structure"
        row["design_pose_path"] = _relative(root, pose_path)
        row["design_pose_sha256"] = sha256_file(pose_path)
        row["backbone"] = {
            "schema_version": BACKBONE_SCHEMA,
            "state": "generated",
            "origin_source": "supplied_structure",
            "source_structure_path": raw_path,
            "source_structure_sha256": source_hash,
            "source_chain": source_chain,
            "binder_chain": binder_chain,
            "binder_residue_count": residue_count,
            "design_pose_path": row["design_pose_path"],
            "design_pose_sha256": row["design_pose_sha256"],
        }
        generated += 1
        output_rows.append(row)
    if len(output_rows) != len(rows):
        raise SuppliedBackboneError("backbone output count differs from input count")
    _write_jsonl(destination, output_rows)
    summary = {
        "input_count": len(rows),
        "output_count": len(output_rows),
        "generated_count": generated,
        "not_evaluable_count": not_evaluable,
        "output_sha256": sha256_file(destination),
    }
    if generated == 0:
        raise SuppliedBackboneError(
            "no eligible row produced a backbone; not-evaluable rows were written"
        )
    return summary


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description=__doc__)
    subparsers = parser.add_subparsers(dest="command", required=True)
    subparsers.add_parser("readiness", help="Report the dependency-free wrapper state.")
    run = subparsers.add_parser("run", help="Publish one pose for every eligible row.")
    run.add_argument("--run-root", type=Path, required=True)
    run.add_argument("--input", type=Path, required=True)
    run.add_argument("--output", type=Path, required=True)
    run.add_argument("--pose-dir", type=Path, required=True)
    run.add_argument("--source-chain", required=True)
    run.add_argument("--binder-chain", required=True)
    run.add_argument("--minimum-length", type=int, required=True)
    run.add_argument("--maximum-length", type=int, required=True)
    run.add_argument("--expected-count", type=int, required=True)
    return parser


def main(argv: list[str] | None = None) -> int:
    args = build_parser().parse_args(argv)
    if args.command == "readiness":
        print(
            json.dumps(
                {
                    "schema_version": READINESS_SCHEMA,
                    "wrapper_ready": True,
                    "runtime_dependencies": [],
                    "ready": True,
                },
                sort_keys=True,
            )
        )
        return 0
    try:
        summary = run_backbones(
            run_root=args.run_root,
            input_path=args.input,
            output_path=args.output,
            pose_dir=args.pose_dir,
            source_chain=args.source_chain,
            binder_chain=args.binder_chain,
            minimum_length=args.minimum_length,
            maximum_length=args.maximum_length,
            expected_count=args.expected_count,
        )
    except (SuppliedBackboneError, OSError, UnicodeError) as exc:
        print(f"supplied backbone adapter: {exc}", file=sys.stderr)
        return 1
    print(json.dumps(summary, sort_keys=True, allow_nan=False))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
