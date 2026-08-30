"""Verify a binder target chain before a design stage starts."""

from __future__ import annotations

import hashlib
import re
from dataclasses import dataclass
from pathlib import Path
from typing import Any

from . import binder_target


REPORT_SCHEMA = "structure-factory-target-verification-v2"
RESIDUE_SELECTION_RE = re.compile(r"^(-?\d+)([A-Za-z]?)(?:-(-?\d+)([A-Za-z]?))?$")
SEQUENCE_RE = re.compile(r"^[ACDEFGHIKLMNPQRSTVWY]+$")
ABSENT_CIF_VALUES = frozenset({".", "?"})

THREE_TO_ONE = {
    "ALA": "A",
    "ARG": "R",
    "ASN": "N",
    "ASP": "D",
    "CYS": "C",
    "GLN": "Q",
    "GLU": "E",
    "GLY": "G",
    "HIS": "H",
    "ILE": "I",
    "LEU": "L",
    "LYS": "K",
    "MET": "M",
    "MSE": "M",
    "PHE": "F",
    "PRO": "P",
    "SER": "S",
    "THR": "T",
    "TRP": "W",
    "TYR": "Y",
    "VAL": "V",
}


class TargetVerificationError(ValueError):
    """The structure cannot establish the requested target identity."""


@dataclass(frozen=True)
class Residue:
    number: int
    insertion_code: str
    name: str
    entity_position: int | None = None

    @property
    def key(self) -> tuple[int, str]:
        return self.number, self.insertion_code

    @property
    def label(self) -> str:
        return f"{self.number}{self.insertion_code}"

    @property
    def letter(self) -> str:
        return THREE_TO_ONE[self.name]


def _sha256_path(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for block in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(block)
    return digest.hexdigest()


def _sha256_text(value: str) -> str:
    return hashlib.sha256(value.encode("ascii")).hexdigest()


def normalize_sequence(value: str) -> str:
    sequence = "".join(value.split()).upper()
    if not sequence or SEQUENCE_RE.fullmatch(sequence) is None:
        raise TargetVerificationError("expected sequence must use the 20 canonical one-letter residue codes")
    return sequence


def parse_residue_selections(value: str) -> set[tuple[int, str]]:
    """Parse comma-separated residue numbers and inclusive numeric ranges."""
    if not isinstance(value, str) or not value.strip():
        raise TargetVerificationError("required residues must be a non-empty selection")
    selected: set[tuple[int, str]] = set()
    for raw_segment in value.split(","):
        segment = raw_segment.strip()
        match = RESIDUE_SELECTION_RE.fullmatch(segment)
        if match is None:
            raise TargetVerificationError(f"invalid residue selection: {segment!r}")
        first, first_insertion, last, last_insertion = match.groups()
        first_number = int(first)
        if last is None:
            selected.add((first_number, first_insertion.upper()))
            continue
        if first_insertion or last_insertion:
            raise TargetVerificationError("insertion codes are allowed on single residues, not ranges")
        last_number = int(last)
        if last_number < first_number or last_number - first_number > 100000:
            raise TargetVerificationError("residue range must be ascending and bounded")
        selected.update((number, "") for number in range(first_number, last_number + 1))
    return selected


def _pdb_residues(text: str, chain_id: str) -> tuple[Residue, ...]:
    residues: list[Residue] = []
    seen: set[tuple[int, str]] = set()
    model_seen = False
    later_model = False
    for line in text.splitlines():
        if line.startswith("MODEL "):
            if model_seen:
                later_model = True
            else:
                model_seen = True
            continue
        if later_model or len(line) < 27 or not line.startswith(("ATOM  ", "HETATM")):
            continue
        if line[21:22].strip() != chain_id:
            continue
        try:
            number = int(line[22:26])
        except ValueError as exc:
            raise TargetVerificationError(f"chain {chain_id} has a non-integer residue number") from exc
        insertion = line[26:27].strip().upper()
        key = (number, insertion)
        if key in seen:
            continue
        name = line[17:20].strip().upper()
        if name not in THREE_TO_ONE:
            if line.startswith("HETATM"):
                continue
            raise TargetVerificationError(f"chain {chain_id} has unsupported residue {name} at {number}{insertion}")
        seen.add(key)
        residues.append(Residue(number, insertion, name))
    if not residues:
        raise TargetVerificationError(f"structure has no readable coordinate residues on chain {chain_id}")
    return tuple(residues)


def _pdb_entity_sequence(text: str, chain_id: str) -> str:
    letters: list[str] = []
    for line in text.splitlines():
        if not line.startswith("SEQRES") or line[11:12].strip() != chain_id:
            continue
        for name in line[19:70].split():
            if name.upper() not in THREE_TO_ONE:
                raise TargetVerificationError(f"SEQRES chain {chain_id} has unsupported residue {name}")
            letters.append(THREE_TO_ONE[name.upper()])
    if not letters:
        raise TargetVerificationError(f"structure has no entity sequence for chain {chain_id}")
    return "".join(letters)


def _cif_tokens(line: str) -> list[str]:
    tokens: list[str] = []
    index = 0
    while index < len(line):
        if line[index].isspace():
            index += 1
            continue
        if line[index] in "'\"":
            quote = line[index]
            end = line.find(quote, index + 1)
            if end < 0:
                raise TargetVerificationError("mmCIF row has an unterminated quoted value")
            tokens.append(line[index + 1 : end])
            index = end + 1
            continue
        end = index
        while end < len(line) and not line[end].isspace():
            end += 1
        tokens.append(line[index:end])
        index = end
    return tokens


def _cif_loop_boundary(line: str) -> bool:
    return (
        line.startswith("#")
        or line == "loop_"
        or line.startswith("_")
        or line.startswith("data_")
        or line.startswith("save_")
        or line == "stop_"
    )


def _cif_multiline(lines: list[str], start: int) -> tuple[str, int]:
    values = [lines[start][1:]] if lines[start][1:] else []
    cursor = start + 1
    while cursor < len(lines) and not lines[cursor].startswith(";"):
        values.append(lines[cursor])
        cursor += 1
    if cursor >= len(lines):
        raise TargetVerificationError("mmCIF has an unterminated multiline value")
    return "\n".join(values), cursor + 1


def _read_cif_loop(lines: list[str], start: int, prefix: str) -> tuple[list[str], list[list[str]], int] | None:
    if lines[start].strip() != "loop_":
        return None
    columns: list[str] = []
    cursor = start + 1
    while cursor < len(lines) and lines[cursor].lstrip().startswith(prefix):
        columns.append(lines[cursor].strip().split(".", 1)[1])
        cursor += 1
    if not columns:
        return None
    rows: list[list[str]] = []
    pending: list[str] = []
    while cursor < len(lines):
        stripped = lines[cursor].strip()
        if not stripped:
            cursor += 1
            continue
        if _cif_loop_boundary(stripped):
            break
        if lines[cursor].startswith(";"):
            value, cursor = _cif_multiline(lines, cursor)
            pending.append(value)
        else:
            pending.extend(_cif_tokens(stripped))
            cursor += 1
        while len(pending) >= len(columns):
            rows.append(pending[: len(columns)])
            pending = pending[len(columns) :]
    if pending:
        raise TargetVerificationError(f"{prefix} loop has an incomplete row")
    return columns, rows, cursor


def _cif_value(row: list[str], columns: dict[str, int], *names: str) -> str:
    for name in names:
        index = columns.get(name)
        if index is not None and index < len(row) and row[index] not in ABSENT_CIF_VALUES:
            return row[index]
    return ""


def _cif_residues(text: str, chain_id: str) -> tuple[Residue, ...]:
    lines = text.splitlines()
    cursor = 0
    while cursor < len(lines):
        parsed = _read_cif_loop(lines, cursor, "_atom_site.")
        if parsed is None:
            cursor += 1
            continue
        names, rows, _ = parsed
        columns = {name: index for index, name in enumerate(names)}
        residues: list[Residue] = []
        seen: set[tuple[int, str]] = set()
        first_model: str | None = None
        for row in rows:
            group = _cif_value(row, columns, "group_PDB")
            if group not in {"ATOM", "HETATM"}:
                continue
            model = _cif_value(row, columns, "pdbx_PDB_model_num") or "1"
            if first_model is None:
                first_model = model
            if model != first_model or _cif_value(row, columns, "auth_asym_id", "label_asym_id") != chain_id:
                continue
            raw_number = _cif_value(row, columns, "auth_seq_id", "label_seq_id")
            try:
                number = int(raw_number)
            except ValueError as exc:
                raise TargetVerificationError(f"chain {chain_id} has a non-integer residue number") from exc
            insertion = _cif_value(row, columns, "pdbx_PDB_ins_code").upper()
            key = (number, insertion)
            if key in seen:
                continue
            name = _cif_value(row, columns, "auth_comp_id", "label_comp_id").upper()
            if name not in THREE_TO_ONE:
                if group == "HETATM":
                    continue
                raise TargetVerificationError(f"chain {chain_id} has unsupported residue {name} at {number}{insertion}")
            raw_entity = _cif_value(row, columns, "label_seq_id")
            entity_position = int(raw_entity) if raw_entity else None
            seen.add(key)
            residues.append(Residue(number, insertion, name, entity_position))
        if not residues:
            raise TargetVerificationError(f"structure has no readable coordinate residues on chain {chain_id}")
        return tuple(residues)
    raise TargetVerificationError("mmCIF structure has no _atom_site loop")


def _cif_entity_sequence(text: str, chain_id: str) -> str:
    lines = text.splitlines()
    entity_sequences: dict[str, str] = {}
    chain_entities: dict[str, str] = {}
    author_chain_entities: dict[str, str] = {}
    cursor = 0
    while cursor < len(lines):
        parsed = _read_cif_loop(lines, cursor, "_entity_poly.")
        if parsed is not None:
            names, rows, cursor = parsed
            columns = {name: index for index, name in enumerate(names)}
            if "entity_id" not in columns or "pdbx_seq_one_letter_code_can" not in columns:
                raise TargetVerificationError("_entity_poly loop lacks sequence columns")
            for row in rows:
                entity_id = row[columns["entity_id"]]
                entity_sequences[entity_id] = "".join(
                    row[columns["pdbx_seq_one_letter_code_can"]].split()
                ).upper()
                strand_index = columns.get("pdbx_strand_id")
                if strand_index is not None:
                    for strand in row[strand_index].replace(",", " ").split():
                        author_chain_entities[strand] = entity_id
            continue
        parsed = _read_cif_loop(lines, cursor, "_struct_asym.")
        if parsed is not None:
            names, rows, cursor = parsed
            columns = {name: index for index, name in enumerate(names)}
            if "id" in columns and "entity_id" in columns:
                for row in rows:
                    chain_entities[row[columns["id"]]] = row[columns["entity_id"]]
            continue
        cursor += 1
    entity_id = chain_entities.get(chain_id) or author_chain_entities.get(chain_id)
    sequence = entity_sequences.get(entity_id or "", "")
    if not sequence or SEQUENCE_RE.fullmatch(sequence) is None:
        raise TargetVerificationError(f"mmCIF has no canonical entity sequence for chain {chain_id}")
    return sequence


def verify_target(
    structure_path: Path,
    *,
    target_contract: dict[str, Any],
    plan_sha256: str,
    expected_sequence: str | None = None,
    sequence_basis: str = "coordinates",
) -> dict[str, Any]:
    """Verify one structure against the exact plan target and site contract."""
    if not structure_path.is_file():
        raise TargetVerificationError("target structure does not name a file")
    try:
        target = binder_target.normalize_target_contract(target_contract)
        bound_plan_sha256 = binder_target.validate_plan_sha256(plan_sha256)
    except binder_target.BinderTargetError as exc:
        raise TargetVerificationError(str(exc)) from exc
    chain_id = target["site"]["chain_id"]
    required_residue_labels = target["site"]["required_residues"]
    if sequence_basis not in {"coordinates", "entity"}:
        raise TargetVerificationError("sequence basis must be coordinates or entity")
    suffix = structure_path.suffix.lower()
    if suffix not in {".pdb", ".cif", ".mmcif"}:
        raise TargetVerificationError("target structure must be PDB or mmCIF")
    text = structure_path.read_text(encoding="utf-8", errors="replace")
    if suffix == ".pdb":
        residues = _pdb_residues(text, chain_id)
        entity_sequence = _pdb_entity_sequence(text, chain_id) if sequence_basis == "entity" else None
        source_format = "pdb"
    else:
        residues = _cif_residues(text, chain_id)
        entity_sequence = _cif_entity_sequence(text, chain_id) if sequence_basis == "entity" else None
        source_format = "mmcif"
    observed_keys = {residue.key for residue in residues}
    required_keys = parse_residue_selections(",".join(required_residue_labels))
    missing = sorted(required_keys - observed_keys)
    if missing:
        rendered = ", ".join(f"{number}{insertion}" for number, insertion in missing[:20])
        if len(missing) > 20:
            rendered += f", and {len(missing) - 20} more"
        raise TargetVerificationError(f"chain {chain_id} lacks required coordinate residues: {rendered}")
    coordinate_sequence = "".join(residue.letter for residue in residues)
    selected_sequence = coordinate_sequence if sequence_basis == "coordinates" else entity_sequence
    assert selected_sequence is not None
    sequence_verified = expected_sequence is not None
    if expected_sequence is not None:
        expected = normalize_sequence(expected_sequence)
        if selected_sequence != expected:
            first = next(
                (index for index, pair in enumerate(zip(selected_sequence, expected), start=1) if pair[0] != pair[1]),
                min(len(selected_sequence), len(expected)) + 1,
            )
            raise TargetVerificationError(
                f"{sequence_basis} sequence differs from the expected sequence at position {first}; "
                f"observed length {len(selected_sequence)}, expected length {len(expected)}"
            )
    return {
        "ok": True,
        "schema_version": REPORT_SCHEMA,
        "plan_sha256": bound_plan_sha256,
        "target_contract_sha256": binder_target.target_contract_sha256(target),
        "target_contract": target,
        "format": source_format,
        "structure_sha256": _sha256_path(structure_path),
        "chain_id": chain_id,
        "coordinate_residue_count": len(residues),
        "first_coordinate_residue": residues[0].label,
        "last_coordinate_residue": residues[-1].label,
        "required_residue_count": len(required_keys),
        "required_residues_verified": True,
        "sequence_basis": sequence_basis,
        "sequence_length": len(selected_sequence),
        "sequence_sha256": _sha256_text(selected_sequence),
        "sequence_verified": sequence_verified,
        "provider_calls": 0,
    }
