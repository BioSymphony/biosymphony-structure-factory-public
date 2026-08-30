"""Validate public-safe binder-stage artifacts and create bounded receipts.

This module does not start processes, read environment variables, or inspect
artifact payloads beyond the bytes needed to calculate a SHA-256 hash.
"""

from __future__ import annotations

import hashlib
import json
import os
import re
import tempfile
from pathlib import Path, PurePosixPath
from typing import Any, Iterable


LEDGER_SCHEMA = "structure-factory-binder-artifact-ledger-v1"
RECEIPT_SCHEMA = "structure-factory-binder-stage-receipt-v1"
SAFE_ID_RE = re.compile(r"^[a-z0-9][a-z0-9._-]{0,95}$")
MACHINE_PATH_RE = re.compile(
    r"(?:file://|\\\\[A-Za-z0-9._-]+\\|~[/\\\\]|/(?:Users|Volumes|home|root|tmp|var/(?:tmp|folders)|private/tmp|etc|mnt)/|(?<![A-Za-z])[A-Za-z]:[\\\\/])"
)
SENSITIVE_TEXT_PATTERNS = (
    re.compile(r"-----BEGIN [A-Z ]*PRIVATE KEY-----"),
    re.compile(r"(?i)\bbearer\s+[A-Za-z0-9._~+/-]{12,}"),
    re.compile(r"\beyJ[A-Za-z0-9_-]{8,}\.[A-Za-z0-9_-]{8,}\.[A-Za-z0-9_-]{8,}\b"),
    re.compile(r"\b(?:sk[-_](?:proj[-_])?|ghp_|hf_|rp_)[A-Za-z0-9_-]{12,}\b"),
    re.compile(r"\b(?:AKIA|ASIA)[A-Z0-9]{16}\b"),
    re.compile(r"(?i)https?://[^/\s:@]+:[^@\s/]+@"),
    re.compile(r"(?i)https?://(?:local(?:host)|127\.0\.0\.1|10\.\d+\.\d+\.\d+|192\.168\.\d+\.\d+|172\.(?:1[6-9]|2\d|3[01])\.\d+\.\d+)(?::\d+)?"),
    re.compile(r"\b[ACDEFGHIKLMNPQRSTVWY]{20,}\b"),
)
PRIVATE_PROSE_RE = re.compile(
    r"(?i)\b(?:internal|private|unpublished|patient|scratchpad|reasoning|agent[ _-]?trace|"
    r"reviewer[ _-]?note|meta[ _-]?concern|operator[ _-]?note|debug[ _-]?log|model[ _-]?prompt|thinking)\b"
)
RESULT_BOUNDARIES = {
    "planning",
    "public_demo",
    "public_synthetic_demo",
    "computational_candidate",
    "blocked",
    "insufficient_support",
}
EXECUTION_STATES = {"completed", "failed", "partial"}


class BinderReceiptError(ValueError):
    """Raised when a declaration, ledger, or receipt crosses the public boundary."""


def _read_json(path: Path) -> Any:
    def reject_duplicates(pairs: list[tuple[str, Any]]) -> dict[str, Any]:
        result: dict[str, Any] = {}
        for key, value in pairs:
            if key in result:
                raise BinderReceiptError("JSON input has a duplicate object key")
            result[key] = value
        return result

    try:
        return json.loads(path.read_text(encoding="utf-8"), object_pairs_hook=reject_duplicates)
    except (OSError, json.JSONDecodeError) as exc:
        raise BinderReceiptError("could not read the JSON input") from exc


def _write_json(path: Path, payload: Any) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    encoded = json.dumps(payload, indent=2, sort_keys=True, allow_nan=False) + "\n"
    with tempfile.NamedTemporaryFile("w", encoding="utf-8", dir=path.parent, delete=False) as handle:
        handle.write(encoded)
        temporary = Path(handle.name)
    os.replace(temporary, path)


def _require_exact_keys(value: Any, expected: set[str], label: str) -> dict[str, Any]:
    if not isinstance(value, dict) or set(value) != expected:
        raise BinderReceiptError(f"{label} has missing or undeclared fields")
    return value


def _require_safe_id(value: Any, label: str) -> str:
    if not isinstance(value, str) or SAFE_ID_RE.fullmatch(value) is None:
        raise BinderReceiptError(f"{label} must be a lowercase stable ID")
    return value


def _relative_path(value: Any, label: str) -> Path:
    if not isinstance(value, str) or not value or "\x00" in value or "\\" in value:
        raise BinderReceiptError(f"{label} must be a non-empty POSIX relative path")
    pure = PurePosixPath(value)
    if pure.is_absolute() or any(part in {"", ".", ".."} for part in pure.parts):
        raise BinderReceiptError(f"{label} must stay below the run root")
    if MACHINE_PATH_RE.search(value):
        raise BinderReceiptError(f"{label} contains a machine-local path")
    return Path(*pure.parts)


def _run_root(value: Path) -> Path:
    root = Path(value).resolve()
    if not root.is_dir() or root.is_symlink():
        raise BinderReceiptError("run root must be an existing directory, not a symlink")
    return root


def _contained_file(root: Path, relative: str, label: str, *, required: bool) -> Path:
    safe = _relative_path(relative, label)
    current = root
    for part in safe.parts:
        current = current / part
        if current.exists() and current.is_symlink():
            raise BinderReceiptError(f"{label} must not use a symlink")
    path = (root / safe).resolve()
    try:
        path.relative_to(root)
    except ValueError as exc:
        raise BinderReceiptError(f"{label} resolves outside the run root") from exc
    if required and (not path.is_file() or path.is_symlink()):
        raise BinderReceiptError(f"{label} must name a regular file")
    return path


def _contained_directory(root: Path, relative: str, label: str) -> Path:
    path = _contained_file(root, relative, label, required=False)
    if not path.is_dir() or path.is_symlink():
        raise BinderReceiptError(f"{label} must name an existing directory")
    return path


def _sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def _safe_note(value: Any, label: str) -> str:
    if not isinstance(value, str) or not value.strip() or any(ord(char) < 32 for char in value):
        raise BinderReceiptError(f"{label} must be non-empty public text")
    if MACHINE_PATH_RE.search(value) or PRIVATE_PROSE_RE.search(value) or any(
        pattern.search(value) for pattern in SENSITIVE_TEXT_PATTERNS
    ):
        raise BinderReceiptError(f"{label} contains non-public text")
    return value


def _validate_declarations(declarations: Any, root: Path, artifact_root: Path) -> list[dict[str, str]]:
    if not isinstance(declarations, list) or not declarations:
        raise BinderReceiptError("artifact declarations must be a non-empty list")
    normalized: list[dict[str, str]] = []
    ids: set[str] = set()
    paths: set[str] = set()
    for index, declaration in enumerate(declarations):
        item = _require_exact_keys(declaration, {"artifact_id", "path"}, f"artifact declaration {index}")
        artifact_id = _require_safe_id(item["artifact_id"], f"artifact declaration {index} ID")
        relative = _relative_path(item["path"], f"artifact declaration {index} path").as_posix()
        resolved = _contained_file(root, relative, f"artifact declaration {index} path", required=False)
        try:
            resolved.relative_to(artifact_root)
        except ValueError as exc:
            raise BinderReceiptError("artifact declaration path must stay below the artifact root") from exc
        if artifact_id in ids or relative in paths:
            raise BinderReceiptError("artifact declarations must use unique IDs and paths")
        ids.add(artifact_id)
        paths.add(relative)
        normalized.append({"artifact_id": artifact_id, "path": relative})
    return normalized


def _discover_artifacts(root: Path, artifact_root: Path) -> list[str]:
    discovered: list[str] = []
    for directory, child_directories, filenames in os.walk(artifact_root, followlinks=False):
        directory_path = Path(directory)
        for child in child_directories:
            if (directory_path / child).is_symlink():
                raise BinderReceiptError("artifact root contains a symlink")
        for filename in filenames:
            path = directory_path / filename
            if path.is_symlink():
                raise BinderReceiptError("artifact root contains a symlink")
            if not path.is_file():
                raise BinderReceiptError("artifact root contains a non-file output")
            try:
                discovered.append(path.resolve().relative_to(root).as_posix())
            except ValueError as exc:
                raise BinderReceiptError("artifact resolves outside the run root") from exc
    return sorted(discovered)


def create_artifact_ledger(
    run_root: Path,
    stage_id: str,
    artifact_root: str,
    declarations: list[dict[str, str]],
) -> dict[str, Any]:
    """Create a hash ledger for one declared stage output directory.

    The ledger records names, sizes, and hashes. It never reads or records
    biological payload text.
    """
    root = _run_root(run_root)
    normalized_stage = _require_safe_id(stage_id, "stage ID")
    artifact_relative = _relative_path(artifact_root, "artifact root").as_posix()
    artifacts_directory = _contained_directory(root, artifact_relative, "artifact root")
    normalized = _validate_declarations(declarations, root, artifacts_directory)
    discovered = _discover_artifacts(root, artifacts_directory)
    declared_paths = {item["path"] for item in normalized}
    found_declared = [item for item in normalized if item["path"] in set(discovered)]
    artifact_rows = []
    for item in found_declared:
        path = _contained_file(root, item["path"], "declared artifact", required=True)
        artifact_rows.append(
            {
                "artifact_id": item["artifact_id"],
                "path": item["path"],
                "sha256": _sha256(path),
                "bytes": path.stat().st_size,
            }
        )
    missing_count = len(declared_paths - set(discovered))
    extra_count = len(set(discovered) - declared_paths)
    notes: list[str] = []
    if missing_count:
        notes.append(f"{missing_count} declared output files are missing.")
    if extra_count:
        notes.append(f"{extra_count} undeclared output files are present.")
    if not notes:
        notes.append("Output count matches the declaration.")
    return {
        "schema_version": LEDGER_SCHEMA,
        "stage_id": normalized_stage,
        "artifact_root": artifact_relative,
        "expected_output_count": len(normalized),
        "found_output_count": len(discovered),
        "artifacts": artifact_rows,
        "validation_notes": notes,
    }


def validate_artifact_ledger(ledger: Any) -> dict[str, Any]:
    ledger = _require_exact_keys(
        ledger,
        {
            "schema_version",
            "stage_id",
            "artifact_root",
            "expected_output_count",
            "found_output_count",
            "artifacts",
            "validation_notes",
        },
        "artifact ledger",
    )
    if ledger["schema_version"] != LEDGER_SCHEMA:
        raise BinderReceiptError("artifact ledger has an invalid schema version")
    _require_safe_id(ledger["stage_id"], "artifact ledger stage ID")
    _relative_path(ledger["artifact_root"], "artifact ledger artifact root")
    for field in ("expected_output_count", "found_output_count"):
        if not isinstance(ledger[field], int) or isinstance(ledger[field], bool) or ledger[field] < 0:
            raise BinderReceiptError(f"artifact ledger {field} must be a non-negative integer")
    if not isinstance(ledger["artifacts"], list):
        raise BinderReceiptError("artifact ledger artifacts must be a list")
    ids: set[str] = set()
    paths: set[str] = set()
    for index, row in enumerate(ledger["artifacts"]):
        row = _require_exact_keys(row, {"artifact_id", "path", "sha256", "bytes"}, f"artifact row {index}")
        artifact_id = _require_safe_id(row["artifact_id"], f"artifact row {index} ID")
        relative = _relative_path(row["path"], f"artifact row {index} path").as_posix()
        if not isinstance(row["sha256"], str) or re.fullmatch(r"[0-9a-f]{64}", row["sha256"]) is None:
            raise BinderReceiptError(f"artifact row {index} SHA-256 is invalid")
        if not isinstance(row["bytes"], int) or isinstance(row["bytes"], bool) or row["bytes"] < 0:
            raise BinderReceiptError(f"artifact row {index} size is invalid")
        if artifact_id in ids or relative in paths:
            raise BinderReceiptError("artifact ledger has duplicate IDs or paths")
        ids.add(artifact_id)
        paths.add(relative)
    if len(ledger["artifacts"]) > ledger["expected_output_count"]:
        raise BinderReceiptError("artifact ledger has more rows than declared outputs")
    if not isinstance(ledger["validation_notes"], list) or not ledger["validation_notes"]:
        raise BinderReceiptError("artifact ledger needs validation notes")
    for index, note in enumerate(ledger["validation_notes"]):
        _safe_note(note, f"artifact ledger validation note {index}")
    return ledger


def write_artifact_ledger(run_root: Path, ledger_path: str, ledger: Any) -> Path:
    """Write a validated ledger below the run root."""
    root = _run_root(run_root)
    validated = validate_artifact_ledger(ledger)
    path = _contained_file(root, ledger_path, "artifact ledger path", required=False)
    _write_json(path, validated)
    return path


def verify_artifact_ledger(
    run_root: Path,
    ledger_path: str,
    declarations: list[dict[str, str]],
) -> dict[str, Any]:
    """Verify that a stored ledger still matches the declared files and hashes."""
    root = _run_root(run_root)
    path = _contained_file(root, ledger_path, "artifact ledger path", required=True)
    stored = validate_artifact_ledger(_read_json(path))
    observed = create_artifact_ledger(root, stored["stage_id"], stored["artifact_root"], declarations)
    hash_mismatches: list[str] = []
    stored_rows = {row["path"]: row for row in stored["artifacts"]}
    observed_rows = {row["path"]: row for row in observed["artifacts"]}
    if set(stored_rows) != set(observed_rows):
        hash_mismatches.append("artifact path coverage differs from the ledger")
    for relative in sorted(set(stored_rows).intersection(observed_rows)):
        if stored_rows[relative]["sha256"] != observed_rows[relative]["sha256"]:
            hash_mismatches.append("an artifact hash differs from the ledger")
            break
        if stored_rows[relative]["bytes"] != observed_rows[relative]["bytes"]:
            hash_mismatches.append("an artifact size differs from the ledger")
            break
    count_matches = (
        stored["expected_output_count"] == observed["expected_output_count"]
        and stored["found_output_count"] == observed["found_output_count"]
        and observed["expected_output_count"] == observed["found_output_count"]
    )
    if not count_matches:
        hash_mismatches.append("output count differs from the declaration")
    return {
        "ok": not hash_mismatches,
        "expected_output_count": observed["expected_output_count"],
        "found_output_count": observed["found_output_count"],
        "findings": hash_mismatches,
    }


def create_stage_receipt(
    run_root: Path,
    stage_id: str,
    result_boundary: str,
    exit_code: int | None,
    artifact_ledger: Any,
    *,
    requested_state: str = "completed",
    validation_notes: Iterable[str] = (),
) -> dict[str, Any]:
    """Create a receipt that marks a stage complete only after every check passes."""
    _run_root(run_root)
    normalized_stage = _require_safe_id(stage_id, "stage ID")
    if result_boundary not in RESULT_BOUNDARIES:
        raise BinderReceiptError("result boundary is not supported")
    if requested_state not in EXECUTION_STATES:
        raise BinderReceiptError("requested execution state is not supported")
    if exit_code is not None and (
        not isinstance(exit_code, int) or isinstance(exit_code, bool) or exit_code < 0
    ):
        raise BinderReceiptError("exit code must be null or a non-negative integer")
    ledger = validate_artifact_ledger(artifact_ledger)
    if ledger["stage_id"] != normalized_stage:
        raise BinderReceiptError("stage receipt and artifact ledger stage IDs differ")
    notes = list(ledger["validation_notes"])
    for index, note in enumerate(validation_notes):
        notes.append(_safe_note(note, f"validation note {index}"))
    counts_match = ledger["expected_output_count"] == ledger["found_output_count"]
    artifacts_match = len(ledger["artifacts"]) == ledger["expected_output_count"]
    completed = requested_state == "completed" and exit_code == 0 and counts_match and artifacts_match
    if completed:
        state = "completed"
        notes.append("Exit code and declared output count passed.")
    elif requested_state == "partial" and ledger["found_output_count"] > 0:
        state = "partial"
        notes.append("The stage ended with a partial output set.")
    else:
        state = "failed"
        if exit_code == 0 and not counts_match:
            notes.append("Exit code 0 did not satisfy the declared output count.")
        elif exit_code not in {0, None}:
            notes.append("The process reported a nonzero exit code.")
        else:
            notes.append("The stage did not satisfy its completion checks.")
    return {
        "schema_version": RECEIPT_SCHEMA,
        "stage_id": normalized_stage,
        "execution_state": state,
        "result_boundary": result_boundary,
        "exit_code": exit_code,
        "expected_output_count": ledger["expected_output_count"],
        "found_output_count": ledger["found_output_count"],
        "artifact_hashes": list(ledger["artifacts"]),
        "validation_notes": notes,
    }


def validate_stage_receipt(receipt: Any) -> dict[str, Any]:
    receipt = _require_exact_keys(
        receipt,
        {
            "schema_version",
            "stage_id",
            "execution_state",
            "result_boundary",
            "exit_code",
            "expected_output_count",
            "found_output_count",
            "artifact_hashes",
            "validation_notes",
        },
        "stage receipt",
    )
    if receipt["schema_version"] != RECEIPT_SCHEMA:
        raise BinderReceiptError("stage receipt has an invalid schema version")
    _require_safe_id(receipt["stage_id"], "stage receipt stage ID")
    if receipt["execution_state"] not in EXECUTION_STATES:
        raise BinderReceiptError("stage receipt has an invalid execution state")
    if receipt["result_boundary"] not in RESULT_BOUNDARIES:
        raise BinderReceiptError("stage receipt has an invalid result boundary")
    if receipt["exit_code"] is not None and (
        not isinstance(receipt["exit_code"], int) or isinstance(receipt["exit_code"], bool) or receipt["exit_code"] < 0
    ):
        raise BinderReceiptError("stage receipt has an invalid exit code")
    for field in ("expected_output_count", "found_output_count"):
        if not isinstance(receipt[field], int) or isinstance(receipt[field], bool) or receipt[field] < 0:
            raise BinderReceiptError(f"stage receipt {field} is invalid")
    if not isinstance(receipt["artifact_hashes"], list) or len(receipt["artifact_hashes"]) > receipt["expected_output_count"]:
        raise BinderReceiptError("stage receipt artifact hashes are invalid")
    validate_artifact_ledger(
        {
            "schema_version": LEDGER_SCHEMA,
            "stage_id": receipt["stage_id"],
            "artifact_root": "receipt-artifacts",
            "expected_output_count": receipt["expected_output_count"],
            "found_output_count": receipt["found_output_count"],
            "artifacts": receipt["artifact_hashes"],
            "validation_notes": receipt["validation_notes"],
        }
    )
    if receipt["execution_state"] == "completed" and (
        receipt["exit_code"] != 0
        or receipt["expected_output_count"] != receipt["found_output_count"]
        or len(receipt["artifact_hashes"]) != receipt["expected_output_count"]
    ):
        raise BinderReceiptError("a completed stage receipt must pass exit, count, and hash checks")
    return receipt


def write_stage_receipt(run_root: Path, receipt_path: str, receipt: Any) -> Path:
    """Write a validated stage receipt below the run root."""
    root = _run_root(run_root)
    validated = validate_stage_receipt(receipt)
    path = _contained_file(root, receipt_path, "stage receipt path", required=False)
    _write_json(path, validated)
    return path
