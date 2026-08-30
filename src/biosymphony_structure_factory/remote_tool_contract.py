"""Provider-neutral requests and receipts for remote binder tools.

This module defines a control-plane boundary, not a provider transport. A
request selects a reviewed tool operation and structured inputs. It cannot
carry command text, credential values, controller paths, or executable code.
"""

from __future__ import annotations

import math
import re
from pathlib import PurePosixPath
from typing import Any, Mapping


CONTRACT_ID = "structure-factory-remote-tool.v1"
PROVIDER_IDS = frozenset(
    {
        "api",
        "local",
        "aws",
        "cloud_vm",
        "fal",
        "lambda",
        "modal",
        "neocloud",
        "runpod",
        "ssh_hpc",
    }
)
DEFAULT_TOOL_OPERATIONS = {
    "boltz": frozenset({"predict", "toolcheck"}),
    "esmfold2": frozenset({"predict", "toolcheck"}),
    "esmfold2-fast": frozenset({"predict", "toolcheck"}),
    "ipsae": frozenset({"score", "toolcheck"}),
    "proteinmpnn": frozenset({"design", "toolcheck"}),
    "rfdiffusion3": frozenset({"design", "toolcheck"}),
}
ROOT_FIELDS = frozenset(
    {
        "schema_version",
        "contract_id",
        "provider_id",
        "tool_id",
        "operation",
        "request_id",
        "input_payload",
        "artifact_prefix",
        "source_identity",
        "model_identity",
        "environment_identity",
        "credential_environment_keys",
        "budget",
    }
)
ADAPTER_REMOTE_FIELDS = frozenset(
    {
        "provider_id",
        "tool_id",
        "operation",
        "input_payload",
        "credential_environment_keys",
        "budget",
        "receipt_path_template",
    }
)
RECEIPT_FIELDS = frozenset(
    {
        "schema_version",
        "contract_id",
        "provider_id",
        "tool_id",
        "operation",
        "request_id",
        "source_identity",
        "model_identity",
        "environment_identity",
        "status",
        "artifacts",
        "cleanup",
    }
)
RECEIPT_OPTIONAL_FIELDS = frozenset({"artifact_count", "cost"})
FORBIDDEN_FIELD_NAMES = frozenset(
    {
        "api_key",
        "argv",
        "code",
        "command",
        "commands",
        "credential",
        "password",
        "script",
        "secret",
        "shell",
        "signed_url",
        "token",
    }
)
REQUEST_ID_RE = re.compile(r"^[a-z0-9][a-z0-9-]{0,127}$")
TOOL_ID_RE = re.compile(r"^[a-z0-9][a-z0-9._-]{0,95}$")
OPERATION_RE = re.compile(r"^[a-z][a-z0-9_-]{0,63}$")
ENVIRONMENT_KEY_RE = re.compile(r"^[A-Z][A-Z0-9_]{1,127}$")
SHA256_RE = re.compile(r"^[0-9a-f]{64}$")
MACHINE_PATH_RE = re.compile(
    r"(?:file://|~[/\\]|/(?:Users|Volumes|home|root|tmp|private/tmp|etc|mnt)/|(?<![A-Za-z])[A-Za-z]:[\\/])"
)


class RemoteToolContractError(ValueError):
    """A request or receipt is outside the fixed remote contract."""


def validate_operation_registry(value: Any) -> dict[str, frozenset[str]]:
    """Validate a tool-to-operation mapping used to authorize requests."""
    if not isinstance(value, Mapping) or not value:
        raise RemoteToolContractError("operation registry must be a non-empty object")
    normalized: dict[str, frozenset[str]] = {}
    for tool_id, operations in value.items():
        if not isinstance(tool_id, str) or TOOL_ID_RE.fullmatch(tool_id) is None:
            raise RemoteToolContractError("operation registry contains an invalid tool ID")
        if not isinstance(operations, (list, tuple, set, frozenset)) or not operations:
            raise RemoteToolContractError(f"operation registry entry for {tool_id} must be non-empty")
        if any(not isinstance(item, str) or OPERATION_RE.fullmatch(item) is None for item in operations):
            raise RemoteToolContractError(f"operation registry entry for {tool_id} has an invalid operation")
        if len(operations) != len(set(operations)):
            raise RemoteToolContractError(f"operation registry entry for {tool_id} contains duplicates")
        normalized[tool_id] = frozenset(operations)
    return normalized


def _walk_request_values(value: Any, path: str = "request") -> None:
    if isinstance(value, Mapping):
        for key, nested in value.items():
            if not isinstance(key, str):
                raise RemoteToolContractError(f"{path} keys must be strings")
            if key.casefold() in FORBIDDEN_FIELD_NAMES:
                raise RemoteToolContractError(
                    f"{path}.{key} is forbidden; remote requests cannot carry commands or credential values"
                )
            _walk_request_values(nested, f"{path}.{key}")
    elif isinstance(value, list):
        for index, nested in enumerate(value):
            _walk_request_values(nested, f"{path}[{index}]")
    elif isinstance(value, str) and MACHINE_PATH_RE.search(value):
        raise RemoteToolContractError(f"{path} contains a controller-local path")


def _relative_posix_path(value: Any, label: str, *, prefix: str | None = None) -> str:
    if not isinstance(value, str) or not value or "\\" in value or "\x00" in value:
        raise RemoteToolContractError(f"{label} must be a non-empty POSIX relative path")
    path = PurePosixPath(value)
    if path.is_absolute() or any(part in {"", ".", ".."} for part in path.parts):
        raise RemoteToolContractError(f"{label} must stay inside its artifact root")
    if prefix is not None and (not path.parts or path.parts[0] != prefix):
        raise RemoteToolContractError(f"{label} must start with {prefix}/")
    return value


def validate_request(
    request: Mapping[str, Any],
    *,
    tool_operations: Mapping[str, Any] | None = None,
) -> dict[str, Any]:
    """Validate one provider-neutral tool request."""
    if not isinstance(request, Mapping):
        raise RemoteToolContractError("request must be an object")
    missing = sorted(ROOT_FIELDS - set(request))
    unknown = sorted(set(request) - ROOT_FIELDS)
    if missing:
        raise RemoteToolContractError(f"request is missing required fields: {', '.join(missing)}")
    if unknown:
        raise RemoteToolContractError(f"request has unknown fields: {', '.join(unknown)}")
    _walk_request_values(request)
    if request.get("schema_version") != 1 or request.get("contract_id") != CONTRACT_ID:
        raise RemoteToolContractError(f"request must select {CONTRACT_ID}")
    provider_id = request.get("provider_id")
    if provider_id not in PROVIDER_IDS:
        raise RemoteToolContractError(f"provider_id is not registered: {provider_id!r}")
    registry = validate_operation_registry(tool_operations or DEFAULT_TOOL_OPERATIONS)
    tool_id = request.get("tool_id")
    operation = request.get("operation")
    if tool_id not in registry or operation not in registry[tool_id]:
        raise RemoteToolContractError(f"operation {operation!r} is not registered for tool {tool_id!r}")
    request_id = request.get("request_id")
    if not isinstance(request_id, str) or REQUEST_ID_RE.fullmatch(request_id) is None:
        raise RemoteToolContractError("request_id must contain lowercase letters, digits, and hyphens")
    payload = request.get("input_payload")
    if not isinstance(payload, Mapping) or not payload:
        raise RemoteToolContractError("input_payload must be a non-empty object")
    _relative_posix_path(request.get("artifact_prefix"), "artifact_prefix", prefix="runs")
    for field in ("source_identity", "model_identity", "environment_identity"):
        if not isinstance(request.get(field), str) or not request[field].strip():
            raise RemoteToolContractError(f"{field} must be a non-empty string")
    credential_keys = request.get("credential_environment_keys")
    if not isinstance(credential_keys, list) or any(
        not isinstance(key, str) or ENVIRONMENT_KEY_RE.fullmatch(key) is None for key in credential_keys
    ):
        raise RemoteToolContractError("credential_environment_keys must contain environment-variable names only")
    if len(credential_keys) != len(set(credential_keys)):
        raise RemoteToolContractError("credential_environment_keys must not contain duplicates")
    budget = request.get("budget")
    if not isinstance(budget, Mapping) or set(budget) != {"max_spend_usd", "max_runtime_seconds"}:
        raise RemoteToolContractError("budget must contain max_spend_usd and max_runtime_seconds only")
    for field in ("max_spend_usd", "max_runtime_seconds"):
        value = budget.get(field)
        if not isinstance(value, (int, float)) or isinstance(value, bool) or value <= 0:
            raise RemoteToolContractError(f"budget.{field} must be positive")
    return dict(request)


def build_stage_request(
    remote_contract: Mapping[str, Any],
    *,
    stage_id: str,
    attempt_id: str,
    source_identity: str,
    model_identity: str,
    environment_identity: str,
    tool_operations: Mapping[str, Any] | None = None,
) -> dict[str, Any]:
    """Build a fixed request from a reviewed stage adapter record."""
    if not isinstance(remote_contract, Mapping):
        raise RemoteToolContractError("remote_contract must be an object")
    missing = sorted(ADAPTER_REMOTE_FIELDS - set(remote_contract))
    unknown = sorted(set(remote_contract) - ADAPTER_REMOTE_FIELDS)
    if missing:
        raise RemoteToolContractError(f"remote_contract is missing required fields: {', '.join(missing)}")
    if unknown:
        raise RemoteToolContractError(f"remote_contract has unknown fields: {', '.join(unknown)}")
    if not isinstance(stage_id, str) or REQUEST_ID_RE.fullmatch(stage_id) is None:
        raise RemoteToolContractError("stage_id must be a request-id component")
    if not isinstance(attempt_id, str) or re.fullmatch(r"[a-f0-9]{32}", attempt_id) is None:
        raise RemoteToolContractError("attempt_id must be a UUID hex string")
    if remote_contract.get("receipt_path_template") != "{{attempt_dir}}/remote-tool-receipt.json":
        raise RemoteToolContractError("receipt_path_template must use the fixed attempt receipt path")
    request_id = f"{stage_id}-{attempt_id}"
    request = {
        "schema_version": 1,
        "contract_id": CONTRACT_ID,
        "provider_id": remote_contract.get("provider_id"),
        "tool_id": remote_contract.get("tool_id"),
        "operation": remote_contract.get("operation"),
        "request_id": request_id,
        "input_payload": remote_contract.get("input_payload"),
        "artifact_prefix": f"runs/{request_id}",
        "source_identity": source_identity,
        "model_identity": model_identity,
        "environment_identity": environment_identity,
        "credential_environment_keys": remote_contract.get("credential_environment_keys"),
        "budget": remote_contract.get("budget"),
    }
    return validate_request(request, tool_operations=tool_operations)


def validate_receipt(
    receipt: Mapping[str, Any],
    request: Mapping[str, Any],
    *,
    tool_operations: Mapping[str, Any] | None = None,
) -> dict[str, Any]:
    """Validate a sanitized receipt and join it to its exact request."""
    validate_request(request, tool_operations=tool_operations)
    if not isinstance(receipt, Mapping):
        raise RemoteToolContractError("receipt must be an object")
    missing = sorted(RECEIPT_FIELDS - set(receipt))
    unknown = sorted(set(receipt) - RECEIPT_FIELDS - RECEIPT_OPTIONAL_FIELDS)
    if missing:
        raise RemoteToolContractError(f"receipt is missing required fields: {', '.join(missing)}")
    if unknown:
        raise RemoteToolContractError(f"receipt has unknown fields: {', '.join(unknown)}")
    if receipt.get("schema_version") != 1 or receipt.get("contract_id") != CONTRACT_ID:
        raise RemoteToolContractError(f"receipt must select {CONTRACT_ID}")
    for field in (
        "provider_id",
        "tool_id",
        "operation",
        "request_id",
        "source_identity",
        "model_identity",
        "environment_identity",
    ):
        if receipt.get(field) != request.get(field):
            raise RemoteToolContractError(f"receipt {field} does not join to the request")
    if receipt.get("status") not in {"completed", "failed", "partial"}:
        raise RemoteToolContractError("receipt status must be completed, failed, or partial")
    artifacts = receipt.get("artifacts")
    if not isinstance(artifacts, list):
        raise RemoteToolContractError("receipt artifacts must be a list")
    if receipt.get("status") == "completed" and not artifacts:
        raise RemoteToolContractError("a completed receipt must carry validated artifact hashes")
    for index, artifact in enumerate(artifacts):
        if not isinstance(artifact, Mapping) or set(artifact) != {"path", "sha256", "byte_count"}:
            raise RemoteToolContractError(f"receipt artifact {index} has an invalid shape")
        _relative_posix_path(artifact.get("path"), f"receipt artifact {index} path")
        digest = artifact.get("sha256")
        if not isinstance(digest, str) or SHA256_RE.fullmatch(digest) is None:
            raise RemoteToolContractError(f"receipt artifact {index} must carry a lowercase SHA-256")
        byte_count = artifact.get("byte_count")
        if isinstance(byte_count, bool) or not isinstance(byte_count, int) or byte_count < 1:
            raise RemoteToolContractError(f"receipt artifact {index} byte_count must be positive")
    cleanup = receipt.get("cleanup")
    if not isinstance(cleanup, Mapping) or set(cleanup) != {"verified"} or cleanup.get("verified") is not True:
        raise RemoteToolContractError("receipt cleanup.verified must be true")
    if "artifact_count" in receipt:
        artifact_count = receipt["artifact_count"]
        if isinstance(artifact_count, bool) or not isinstance(artifact_count, int) or artifact_count != len(artifacts):
            raise RemoteToolContractError("receipt artifact_count must equal the artifact list length")
    if "cost" in receipt:
        cost = receipt.get("cost")
        if not isinstance(cost, Mapping) or set(cost) != {"max_spend_usd", "reported_spend_usd"}:
            raise RemoteToolContractError("receipt cost must contain max_spend_usd and reported_spend_usd only")
        if cost.get("max_spend_usd") != request["budget"]["max_spend_usd"]:
            raise RemoteToolContractError("receipt cost max_spend_usd does not join to the request budget")
        reported = cost.get("reported_spend_usd")
        if (
            isinstance(reported, bool)
            or not isinstance(reported, (int, float))
            or not math.isfinite(float(reported))
            or reported < 0
        ):
            raise RemoteToolContractError("receipt cost reported_spend_usd must be a finite non-negative number")
    return dict(receipt)
