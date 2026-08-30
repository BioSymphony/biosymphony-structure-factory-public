"""Dispatch validated remote tool requests through a user-supplied adapter.

The dispatcher is the transport between the fixed remote-tool contract and
a provider client. It validates the sanitized request, resolves the route
identity, checks the spend and runtime limits, and invokes one Python adapter
callable. It never builds a command string, never spawns a process, and never
writes a credential value. Provider endpoints, resource identifiers, and
transport code stay in the caller's adapter.

Missing credentials and a missing adapter are readiness states: the
dispatcher returns a ``blocked`` outcome that names the gap and invokes
nothing. A receipt is written only when the adapter returns a result with
verified cleanup, so every receipt carries a cleanup proof.
"""

from __future__ import annotations

import copy
import hashlib
import json
import math
import os
import re
import tempfile
import time
from pathlib import Path
from typing import Any, Callable, Mapping

from . import remote_tool_contract


DISPATCH_SCHEMA_VERSION = "structure-factory-remote-dispatch.v1"
DISPATCH_AUTHORIZATION = "authorize_remote_dispatch"
RECEIPT_NAME = "remote-tool-receipt.json"
ROUTE_RE = re.compile(r"^[a-z][a-z0-9_-]{0,63}$")
ADAPTER_RESULT_FIELDS = frozenset({"status", "artifacts", "cost", "cleanup_verified"})
ADAPTER_ARTIFACT_FIELDS = frozenset({"path", "sha256", "byte_count"})
ADAPTER_COST_FIELDS = frozenset({"reported_spend_usd"})

# Route identities are dispatch paths, not evidence of account access or
# live provider readiness.
PROVIDER_ROUTES: dict[str, frozenset[str]] = {
    "local": frozenset({"workstation"}),
    "api": frozenset({"hosted_api"}),
    "aws": frozenset({"batch", "ec2"}),
    "cloud_vm": frozenset({"gpu_vm"}),
    "fal": frozenset({"serverless_gpu"}),
    "lambda": frozenset({"ephemeral_gpu_vm"}),
    "modal": frozenset({"serverless_gpu"}),
    "neocloud": frozenset({"gpu_pod", "gpu_vm"}),
    "runpod": frozenset({"serverless_gpu", "gpu_pod"}),
    "ssh_hpc": frozenset({"slurm"}),
}


class RemoteDispatchError(ValueError):
    """A dispatch input, adapter result, or route is outside the contract."""


def resolve_provider_route(provider_id: Any, route: Any) -> str:
    """Resolve and validate the route identity for one provider class."""
    routes = PROVIDER_ROUTES.get(provider_id) if isinstance(provider_id, str) else None
    if routes is None:
        raise RemoteDispatchError(f"provider_id has no dispatch route: {provider_id!r}")
    if route is None:
        if len(routes) == 1:
            return next(iter(routes))
        raise RemoteDispatchError(
            f"provider_id {provider_id!r} supports several routes; select one of: {', '.join(sorted(routes))}"
        )
    if not isinstance(route, str) or ROUTE_RE.fullmatch(route) is None or route not in routes:
        raise RemoteDispatchError(
            f"route {route!r} is not registered for provider_id {provider_id!r}; registered: "
            f"{', '.join(sorted(routes))}"
        )
    return route


def _sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for block in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(block)
    return digest.hexdigest()


def _artifact_issues(
    root: Path, descriptor: Mapping[str, Any], index: int
) -> tuple[list[str], dict[str, Any] | None]:
    """Check one adapter artifact against the attempt directory."""
    label = f"adapter artifact {index}"
    path_value = descriptor.get("path")
    if not isinstance(path_value, str) or not path_value or "\\" in path_value or "\x00" in path_value:
        return [f"{label} path must be a non-empty POSIX relative path"], None
    if remote_tool_contract.MACHINE_PATH_RE.search(path_value):
        return [f"{label} path names a controller machine path"], None
    candidate = Path(path_value)
    if candidate.is_absolute() or any(part in {"", ".", ".."} for part in candidate.parts):
        return [f"{label} path must stay inside the attempt directory"], None
    staged = root / candidate
    if staged.is_symlink() or staged.is_dir():
        return [f"{label} path must resolve to a regular file below the attempt directory"], None
    resolved = staged.resolve()
    if resolved != root and root not in resolved.parents:
        return [f"{label} path resolves outside the attempt directory"], None
    if not resolved.is_file():
        return [f"{label} {path_value} is missing below the attempt directory"], None
    claimed_sha = descriptor.get("sha256")
    if claimed_sha is not None:
        if not isinstance(claimed_sha, str) or remote_tool_contract.SHA256_RE.fullmatch(claimed_sha) is None:
            return [f"{label} sha256 must be a lowercase SHA-256 digest or null"], None
    claimed_bytes = descriptor.get("byte_count")
    if isinstance(claimed_bytes, bool) or not isinstance(claimed_bytes, int) or claimed_bytes < 1:
        return [f"{label} byte_count must be a positive integer"], None
    computed_sha = _sha256(resolved)
    byte_count = resolved.stat().st_size
    issues: list[str] = []
    if claimed_sha is not None and claimed_sha != computed_sha:
        issues.append(f"{label} {path_value} hash does not match the staged file")
    if claimed_bytes != byte_count:
        issues.append(f"{label} {path_value} byte count does not match the staged file")
    if issues:
        return issues, None
    return issues, {"path": path_value, "sha256": computed_sha, "byte_count": byte_count}


def _validated_adapter_result(result: Any) -> tuple[str, list[dict[str, Any]], float, bool]:
    """Check the adapter result shape and return its parts."""
    if not isinstance(result, Mapping) or set(result) != ADAPTER_RESULT_FIELDS:
        raise RemoteDispatchError(
            "adapter result must contain exactly: " + ", ".join(sorted(ADAPTER_RESULT_FIELDS))
        )
    status = result["status"]
    if status not in {"completed", "failed", "partial"}:
        raise RemoteDispatchError("adapter result status must be completed, failed, or partial")
    cleanup_verified = result["cleanup_verified"]
    if not isinstance(cleanup_verified, bool):
        raise RemoteDispatchError("adapter result cleanup_verified must be boolean")
    cost = result["cost"]
    if not isinstance(cost, Mapping) or set(cost) != ADAPTER_COST_FIELDS:
        raise RemoteDispatchError("adapter result cost must contain reported_spend_usd only")
    reported = cost["reported_spend_usd"]
    if (
        isinstance(reported, bool)
        or not isinstance(reported, (int, float))
        or not math.isfinite(float(reported))
        or reported < 0
    ):
        raise RemoteDispatchError(
            "adapter result cost reported_spend_usd must be a finite non-negative number"
        )
    artifacts = result["artifacts"]
    if not isinstance(artifacts, list):
        raise RemoteDispatchError("adapter result artifacts must be a list")
    for index, descriptor in enumerate(artifacts):
        if (
            not isinstance(descriptor, Mapping)
            or not ADAPTER_ARTIFACT_FIELDS.issubset(descriptor)
            or set(descriptor) != ADAPTER_ARTIFACT_FIELDS
        ):
            raise RemoteDispatchError(f"adapter artifact {index} must contain path, sha256, and byte_count")
    return status, list(artifacts), float(reported), cleanup_verified


def _write_receipt(attempt_dir: Path, receipt: Mapping[str, Any]) -> Path:
    path = attempt_dir / RECEIPT_NAME
    payload = json.dumps(receipt, indent=2, sort_keys=True, allow_nan=False) + "\n"
    with tempfile.NamedTemporaryFile("w", encoding="utf-8", dir=attempt_dir, delete=False) as handle:
        handle.write(payload)
        temporary = Path(handle.name)
    temporary.replace(path)
    return path


def dispatch_remote_tool(
    request: Mapping[str, Any],
    adapter: Callable[[Mapping[str, Any], Mapping[str, Any]], Mapping[str, Any]] | None,
    *,
    attempt_dir: str | Path,
    route: str | None = None,
    environment: Mapping[str, str] | None = None,
    authorization: str | None = None,
    dry_run: bool = False,
    tool_operations: Mapping[str, Any] | None = None,
) -> dict[str, Any]:
    """Validate one remote request, run the adapter, and write a joined receipt.

    The adapter receives a copy of the validated request and a context with the
    attempt directory, budget, route, and the credential environment values
    named by the request. It returns the status, artifact descriptors, reported
    spend, and a cleanup flag. The dispatcher verifies each artifact below the
    attempt directory, recomputes its SHA-256, enforces the spend and runtime
    ceilings, and writes ``remote-tool-receipt.json`` joined to the request.
    """
    validated = remote_tool_contract.validate_request(request, tool_operations=tool_operations)
    provider_route = resolve_provider_route(validated["provider_id"], route)
    root_arg = Path(attempt_dir)
    root_raw = root_arg.expanduser()
    if root_raw.is_symlink():
        raise RemoteDispatchError("attempt_dir must not be a symbolic link")
    root = root_raw.resolve()
    root.mkdir(parents=True, exist_ok=True)
    if not root.is_dir():
        raise RemoteDispatchError("attempt_dir must be a directory")

    environment = dict(os.environ if environment is None else environment)
    keys = list(validated["credential_environment_keys"])
    missing_keys = [key for key in keys if not environment.get(key)]
    credentials = {key: environment[key] for key in keys if environment.get(key)}

    outcome: dict[str, Any] = {
        "dispatch_schema_version": DISPATCH_SCHEMA_VERSION,
        "request_id": validated["request_id"],
        "provider_id": validated["provider_id"],
        "provider_route": provider_route,
        "tool_id": validated["tool_id"],
        "operation": validated["operation"],
        "status": "planned" if dry_run else "not_started",
        "adapter_invoked": False,
        "findings": [],
        "receipt_path": None,
    }
    findings = outcome["findings"]
    if adapter is None:
        findings.append("supply a provider adapter callable for the selected route")
    if missing_keys:
        findings.append("supply the missing credential environment variables: " + ", ".join(missing_keys))
    if dry_run:
        outcome["status"] = "planned"
        return outcome
    if adapter is None or missing_keys:
        outcome["status"] = "blocked"
        return outcome
    if authorization != DISPATCH_AUTHORIZATION:
        raise RemoteDispatchError(f"remote dispatch requires authorization={DISPATCH_AUTHORIZATION!r}")

    context = {
        "attempt_dir": str(root),
        "artifact_prefix": validated["artifact_prefix"],
        "budget": dict(validated["budget"]),
        "provider_route": provider_route,
        "credential_environment": credentials,
        "credential_environment_keys": keys,
    }
    started = time.monotonic()
    outcome["adapter_invoked"] = True
    try:
        result = adapter(copy.deepcopy(validated), context)
    except Exception as exc:  # the adapter is caller-supplied code
        findings.append(f"adapter raised {type(exc).__name__}; no receipt was written")
        outcome["status"] = "failed"
        return outcome
    elapsed = time.monotonic() - started
    status, artifacts, reported_spend, cleanup_verified = _validated_adapter_result(result)

    if not cleanup_verified:
        findings.append(
            "adapter reported unverified cleanup; verify artifact export and cleanup, then dispatch again"
        )
        outcome["status"] = "blocked"
        return outcome

    verified: list[dict[str, Any]] = []
    for index, descriptor in enumerate(artifacts):
        issues, computed = _artifact_issues(root, descriptor, index)
        findings.extend(issues)
        if computed is not None:
            verified.append(computed)
    if artifacts and len(verified) != len(artifacts):
        status = "failed"
    if status == "completed" and not verified:
        findings.append("a completed result requires at least one verified artifact")
        status = "failed"
    if elapsed > float(validated["budget"]["max_runtime_seconds"]):
        findings.append("adapter runtime exceeded max_runtime_seconds")
        status = "failed"
    if reported_spend > float(validated["budget"]["max_spend_usd"]):
        findings.append("adapter reported spend above max_spend_usd")
        status = "failed"

    receipt = {
        "schema_version": 1,
        "contract_id": remote_tool_contract.CONTRACT_ID,
        "provider_id": validated["provider_id"],
        "tool_id": validated["tool_id"],
        "operation": validated["operation"],
        "request_id": validated["request_id"],
        "source_identity": validated["source_identity"],
        "model_identity": validated["model_identity"],
        "environment_identity": validated["environment_identity"],
        "status": status,
        "artifacts": verified,
        "artifact_count": len(verified),
        "cost": {
            "max_spend_usd": validated["budget"]["max_spend_usd"],
            "reported_spend_usd": reported_spend,
        },
        "cleanup": {"verified": True},
    }
    remote_tool_contract.validate_receipt(receipt, validated, tool_operations=tool_operations)
    receipt_path = _write_receipt(root, receipt)
    outcome["status"] = status
    outcome["artifact_count"] = len(verified)
    outcome["reported_spend_usd"] = reported_spend
    outcome["findings"] = findings
    outcome["receipt_path"] = str(root_arg / RECEIPT_NAME)
    outcome["receipt"] = receipt
    return outcome
