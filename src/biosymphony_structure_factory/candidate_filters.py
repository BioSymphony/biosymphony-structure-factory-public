"""Dependency-free candidate filters for the public binder execution lane."""

from __future__ import annotations

import argparse
import json
import math
import os
import re
import tempfile
from pathlib import Path
from typing import Any


FILTER_SCHEMA = "structure-factory-candidate-filter-result-v1"
ID_RE = re.compile(r"^[a-z0-9][a-z0-9._-]{0,127}$")
METRIC_PATH_RE = re.compile(r"^[a-z][a-z0-9_]*(?:\.[a-z][a-z0-9_]*)*$")
PROTEIN_SEQUENCE_RE = re.compile(r"^[ACDEFGHIKLMNPQRSTVWY]+$")
MAXIMUM_SEQUENCE_LENGTH = 2000
ELIGIBLE_STATUSES = frozenset({"completed", "eligible", "generated", "passed", "scored"})


class CandidateFilterError(ValueError):
    """A candidate table or filter setting is invalid."""


def _reject_constant(_: str) -> None:
    raise CandidateFilterError("candidate JSONL contains a non-finite number")


def read_candidates(path: Path) -> list[dict[str, Any]]:
    if not path.is_file():
        raise CandidateFilterError("candidate input does not name a file")
    rows: list[dict[str, Any]] = []
    seen: set[str] = set()
    for line_number, line in enumerate(path.read_text(encoding="utf-8").splitlines(), start=1):
        if not line.strip():
            continue
        try:
            row = json.loads(line, parse_constant=_reject_constant)
        except json.JSONDecodeError as exc:
            raise CandidateFilterError(f"candidate JSONL line {line_number} is invalid") from exc
        if not isinstance(row, dict):
            raise CandidateFilterError(f"candidate JSONL line {line_number} must be an object")
        candidate_id = row.get("candidate_id")
        if not isinstance(candidate_id, str) or ID_RE.fullmatch(candidate_id) is None:
            raise CandidateFilterError(f"candidate JSONL line {line_number} has an invalid candidate_id")
        if candidate_id in seen:
            raise CandidateFilterError("candidate IDs must be unique")
        seen.add(candidate_id)
        if not isinstance(row.get("status"), str) or not row["status"]:
            raise CandidateFilterError(f"candidate JSONL line {line_number} must carry a status")
        results = row.get("filter_results", [])
        if not isinstance(results, list) or any(not isinstance(item, dict) for item in results):
            raise CandidateFilterError(f"candidate JSONL line {line_number} filter_results must be a list of objects")
        rows.append(dict(row))
    if not rows:
        raise CandidateFilterError("candidate JSONL contains no rows")
    return rows


def _write_candidates(path: Path, rows: list[dict[str, Any]]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    encoded = "".join(json.dumps(row, sort_keys=True, allow_nan=False) + "\n" for row in rows)
    with tempfile.NamedTemporaryFile("w", encoding="utf-8", dir=path.parent, delete=False) as handle:
        handle.write(encoded)
        temporary = Path(handle.name)
    os.replace(temporary, path)


def _metric_value(row: dict[str, Any], metric_path: str) -> Any:
    value: Any = row
    for part in metric_path.split("."):
        if not isinstance(value, dict) or part not in value:
            return None
        value = value[part]
    return value


def status_filter(
    rows: list[dict[str, Any]],
    *,
    metric_path: str,
    minimum: float,
    maximum: float,
) -> list[dict[str, Any]]:
    """Append one metric-filter result while preserving every input row."""
    if METRIC_PATH_RE.fullmatch(metric_path) is None:
        raise CandidateFilterError("metric must be a dotted lowercase field path")
    if not all(isinstance(value, (int, float)) and not isinstance(value, bool) and math.isfinite(value) for value in (minimum, maximum)):
        raise CandidateFilterError("metric bounds must be finite numbers")
    if maximum < minimum:
        raise CandidateFilterError("maximum metric bound must be at least the minimum")
    output: list[dict[str, Any]] = []
    for source in rows:
        row = dict(source)
        prior_results = list(row.get("filter_results", []))
        original_status = row["status"]
        value = _metric_value(row, metric_path)
        if original_status not in ELIGIBLE_STATUSES:
            state = "not_evaluable"
            reason = "upstream_status"
        elif isinstance(value, bool) or not isinstance(value, (int, float)) or not math.isfinite(float(value)):
            state = "not_evaluable"
            reason = "missing_or_invalid_metric"
        elif float(value) < minimum:
            state = "filtered"
            reason = "below_minimum"
        elif float(value) > maximum:
            state = "filtered"
            reason = "above_maximum"
        else:
            state = "passed"
            reason = "within_bounds"
        prior_results.append(
            {
                "schema_version": FILTER_SCHEMA,
                "filter_id": "status-preserving-metric",
                "state": state,
                "reason": reason,
                "metric": metric_path,
                "minimum": minimum,
                "maximum": maximum,
            }
        )
        row["filter_results"] = prior_results
        output.append(row)
    return output


def _edit_similarity(left: str, right: str) -> float:
    """Return one minus normalized Levenshtein distance."""
    if left == right:
        return 1.0
    if not left or not right:
        return 0.0
    if len(left) < len(right):
        left, right = right, left
    previous = list(range(len(right) + 1))
    for left_index, left_letter in enumerate(left, start=1):
        current = [left_index]
        for right_index, right_letter in enumerate(right, start=1):
            current.append(
                min(
                    current[-1] + 1,
                    previous[right_index] + 1,
                    previous[right_index - 1] + (left_letter != right_letter),
                )
            )
        previous = current
    return 1.0 - (previous[-1] / max(len(left), len(right)))


def diversity_filter(
    rows: list[dict[str, Any]],
    *,
    sequence_field: str,
    maximum_similarity: float,
) -> list[dict[str, Any]]:
    """Greedily retain diverse eligible rows in stable input order."""
    if not isinstance(sequence_field, str) or METRIC_PATH_RE.fullmatch(sequence_field) is None:
        raise CandidateFilterError("sequence field must be a dotted lowercase field path")
    if (
        isinstance(maximum_similarity, bool)
        or not isinstance(maximum_similarity, (int, float))
        or not math.isfinite(float(maximum_similarity))
        or not 0 <= float(maximum_similarity) <= 1
    ):
        raise CandidateFilterError("maximum similarity must be between zero and one")
    retained: list[tuple[str, str]] = []
    output: list[dict[str, Any]] = []
    for source in rows:
        row = dict(source)
        prior_results = list(row.get("filter_results", []))
        eligible = row["status"] in ELIGIBLE_STATUSES and not any(
            result.get("state") in {"filtered", "not_evaluable"} for result in prior_results
        )
        raw_sequence = _metric_value(row, sequence_field)
        if not eligible:
            state = "not_evaluable"
            reason = "upstream_status_or_filter"
            nearest_id = None
            nearest_similarity = None
        elif not isinstance(raw_sequence, str):
            state = "not_evaluable"
            reason = "missing_sequence"
            nearest_id = None
            nearest_similarity = None
        else:
            sequence = "".join(raw_sequence.split()).upper()
            if (
                PROTEIN_SEQUENCE_RE.fullmatch(sequence) is None
                or len(sequence) > MAXIMUM_SEQUENCE_LENGTH
            ):
                state = "not_evaluable"
                reason = "invalid_sequence"
                nearest_id = None
                nearest_similarity = None
            else:
                similarities = [
                    (candidate_id, _edit_similarity(sequence, retained_sequence))
                    for candidate_id, retained_sequence in retained
                ]
                nearest_id, nearest_similarity = max(similarities, key=lambda item: item[1]) if similarities else (None, None)
                if nearest_similarity is not None and nearest_similarity > maximum_similarity:
                    state = "filtered"
                    reason = "similar_to_retained_candidate"
                else:
                    state = "passed"
                    reason = "diverse"
                    retained.append((row["candidate_id"], sequence))
        prior_results.append(
            {
                "schema_version": FILTER_SCHEMA,
                "filter_id": "stable-edit-diversity",
                "state": state,
                "reason": reason,
                "maximum_similarity": maximum_similarity,
                "nearest_retained_candidate_id": nearest_id,
                "nearest_similarity": nearest_similarity,
            }
        )
        row["filter_results"] = prior_results
        output.append(row)
    return output


def _contained(root: Path, value: str, label: str) -> Path:
    root = root.resolve()
    path = Path(value).resolve()
    try:
        path.relative_to(root)
    except ValueError as exc:
        raise CandidateFilterError(f"{label} must stay inside the run root") from exc
    if path == root:
        raise CandidateFilterError(f"{label} must name a file below the run root")
    return path


def _base_parser(program: str) -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(prog=program)
    parser.add_argument("--run-root", required=True)
    parser.add_argument("--input", required=True)
    parser.add_argument("--output", required=True)
    return parser


def status_main(argv: list[str] | None = None) -> int:
    parser = _base_parser("bsf-status-filter")
    parser.add_argument("--metric", required=True)
    parser.add_argument("--minimum", required=True, type=float)
    parser.add_argument("--maximum", required=True, type=float)
    args = parser.parse_args(argv)
    try:
        root = Path(args.run_root).resolve()
        input_path = _contained(root, args.input, "input")
        output_path = _contained(root, args.output, "output")
        rows = status_filter(
            read_candidates(input_path),
            metric_path=args.metric,
            minimum=args.minimum,
            maximum=args.maximum,
        )
        _write_candidates(output_path, rows)
    except (CandidateFilterError, OSError, UnicodeError, ValueError) as exc:
        parser.error(str(exc))
    return 0


def diversity_main(argv: list[str] | None = None) -> int:
    parser = _base_parser("bsf-diversity-filter")
    parser.add_argument("--sequence-field", default="candidate_sequence")
    parser.add_argument("--maximum-similarity", required=True, type=float)
    args = parser.parse_args(argv)
    try:
        root = Path(args.run_root).resolve()
        input_path = _contained(root, args.input, "input")
        output_path = _contained(root, args.output, "output")
        rows = diversity_filter(
            read_candidates(input_path),
            sequence_field=args.sequence_field,
            maximum_similarity=args.maximum_similarity,
        )
        _write_candidates(output_path, rows)
    except (CandidateFilterError, OSError, UnicodeError, ValueError) as exc:
        parser.error(str(exc))
    return 0
