"""Normalize the public target and site contract for a binder round."""

from __future__ import annotations

import hashlib
import json
import re
from typing import Any, Mapping


CHAIN_RE = re.compile(r"^[A-Za-z0-9]+$")
RESIDUE_SELECTION_RE = re.compile(
    r"^(-?\d+)([A-Za-z]?)(?:-(-?\d+)([A-Za-z]?))?$"
)
SHA256_RE = re.compile(r"^[0-9a-f]{64}$")


class BinderTargetError(ValueError):
    """The binder target or site contract is invalid."""


def _exact_keys(value: Mapping[str, Any], expected: set[str], label: str) -> None:
    missing = expected - set(value)
    extra = set(value) - expected
    if missing or extra:
        if label.endswith("target") and "site" in missing:
            raise BinderTargetError(
                f"{label} is missing site; add site.chain_id and site.required_residues"
            )
        raise BinderTargetError(f"{label} has missing or undeclared fields")


def normalize_required_residues(value: Any, label: str) -> list[str]:
    """Return unique residue selections in numeric order."""
    if not isinstance(value, list) or not value:
        raise BinderTargetError(f"{label} must be a non-empty residue-selection list")
    parsed: list[tuple[int, str, int | None, str]] = []
    covered: set[tuple[int, str]] = set()
    for item in value:
        if not isinstance(item, str):
            raise BinderTargetError(f"{label} must contain residue selections")
        match = RESIDUE_SELECTION_RE.fullmatch(item)
        if match is None:
            raise BinderTargetError(
                f"{label} entries must be residue numbers or inclusive numeric ranges"
            )
        first = int(match.group(1))
        first_insertion = match.group(2).upper()
        last_raw = match.group(3)
        last_insertion = (match.group(4) or "").upper()
        if last_raw is None:
            keys = {(first, first_insertion)}
            last = None
        else:
            last = int(last_raw)
            if first_insertion or last_insertion:
                raise BinderTargetError(
                    f"{label} allows insertion codes on single residues, not ranges"
                )
            if last < first or last - first > 100000:
                raise BinderTargetError(f"{label} ranges must be ascending and bounded")
            keys = {(number, "") for number in range(first, last + 1)}
        if covered.intersection(keys):
            raise BinderTargetError(f"{label} must not contain overlapping residues")
        covered.update(keys)
        parsed.append((first, first_insertion, last, last_insertion))
    parsed.sort(key=lambda row: (row[0], row[1], row[2] if row[2] is not None else row[0]))
    return [
        f"{first}{first_insertion}"
        + (f"-{last}{last_insertion}" if last is not None else "")
        for first, first_insertion, last, last_insertion in parsed
    ]


def required_residue_count(value: Any, label: str) -> int:
    normalized = normalize_required_residues(value, label)
    count = 0
    for selection in normalized:
        match = RESIDUE_SELECTION_RE.fullmatch(selection)
        assert match is not None
        first = int(match.group(1))
        last = int(match.group(3)) if match.group(3) is not None else first
        count += last - first + 1
    return count


def normalize_target_contract(value: Any, label: str = "target") -> dict[str, Any]:
    """Validate and normalize the structural fields of a public target contract."""
    if not isinstance(value, dict):
        raise BinderTargetError(f"{label} must be an object")
    _exact_keys(
        value,
        {"input_posture", "label", "public_accession", "window", "site"},
        label,
    )
    site = value.get("site")
    if not isinstance(site, dict):
        raise BinderTargetError(f"{label} site must be an object")
    _exact_keys(site, {"chain_id", "required_residues"}, f"{label} site")
    chain_id = site.get("chain_id")
    if not isinstance(chain_id, str) or CHAIN_RE.fullmatch(chain_id) is None:
        raise BinderTargetError(f"{label} site.chain_id must contain letters and digits only")
    residues = normalize_required_residues(
        site.get("required_residues"), f"{label} site.required_residues"
    )
    return {
        "input_posture": value.get("input_posture"),
        "label": value.get("label"),
        "public_accession": value.get("public_accession"),
        "window": value.get("window"),
        "site": {
            "chain_id": chain_id,
            "required_residues": residues,
        },
    }


def target_contract_sha256(target: Any) -> str:
    normalized = normalize_target_contract(target)
    encoded = json.dumps(
        normalized,
        sort_keys=True,
        separators=(",", ":"),
        ensure_ascii=True,
    ).encode("utf-8")
    return hashlib.sha256(encoded).hexdigest()


def validate_plan_sha256(value: Any) -> str:
    if not isinstance(value, str) or SHA256_RE.fullmatch(value) is None:
        raise BinderTargetError("plan_sha256 must be a lowercase SHA-256 digest")
    return value
