"""Public, provider-neutral binder-round planning and synthetic reporting."""

from __future__ import annotations

import hashlib
import json
import math
import re
from pathlib import Path, PurePosixPath
from typing import Any

from . import binder_target


REQUEST_SCHEMA = "structure-factory-binder-round-request-v1"
PLAN_SCHEMA = "structure-factory-binder-round-plan-v1"
CONTRACT_SCHEMA = "structure-factory-binder-round-contract-v1"
REPORT_SCHEMA = "structure-factory-binder-round-report-v1"
LEDGER_SCHEMA = "structure-factory-binder-capability-ledger-v1"
DECISION_SCHEMA = "structure-factory-binder-round-decision-v1"

MACHINE_PATH_RE = re.compile(
    r"(?:file://|\\\\[A-Za-z0-9._-]+\\|~[/\\]|/(?:Users|Volumes|home|root|tmp|var/(?:tmp|folders)|private/tmp|etc|mnt)/|(?<![A-Za-z])[A-Za-z]:[\\/])"
)
SENSITIVE_VALUE_PATTERNS = (
    re.compile(r"-----BEGIN [A-Z ]*PRIVATE KEY-----"),
    re.compile(r"(?i)\bbearer\s+[A-Za-z0-9._~+/-]{12,}"),
    re.compile(r"\beyJ[A-Za-z0-9_-]{8,}\.[A-Za-z0-9_-]{8,}\.[A-Za-z0-9_-]{8,}\b"),
    re.compile(r"\b(?:sk[-_](?:proj[-_])?|ghp_|hf_|rp_)[A-Za-z0-9_-]{12,}\b"),
    re.compile(r"\b(?:AKIA|ASIA)[A-Z0-9]{16}\b"),
    re.compile(r"\bxox[baprs]-[A-Za-z0-9-]{16,}\b"),
    re.compile(r"\bgithub_pat_[A-Za-z0-9_]{20,}\b"),
    re.compile(r"(?i)https?://[^/\s:@]+:[^@\s/]+@"),
    re.compile(r"(?i)https?://(?:local(?:host)|127\.0\.0\.1|10\.\d+\.\d+\.\d+|192\.168\.\d+\.\d+|172\.(?:1[6-9]|2\d|3[01])\.\d+\.\d+)(?::\d+)?"),
    re.compile(r"(?i)https?://(?:169\.254\.169\.254|100\.(?:6[4-9]|[7-9]\d|1[01]\d|12[0-7])\.\d+\.\d+)(?::\d+)?"),
    re.compile(r"(?i)https?://\[::1\](?::\d+)?"),
    re.compile(r"(?i)https?://\[(?:fc|fd|fe8|fe9|fea|feb)[0-9a-f:]+\](?::\d+)?"),
    re.compile(r"(?i)https?://[^\s?]+\?[^\s]*(?:sig|signature|x-amz-credential|x-amz-signature|x-goog-signature|token)="),
    re.compile(r"\b[ACDEFGHIKLMNPQRSTVWY]{20,}\b"),
)
SAFE_ID_RE = re.compile(r"^[a-z0-9][a-z0-9._-]{0,95}$")
PLATFORM_SKILL_REF_RE = re.compile(
    r"^[a-z0-9][a-z0-9._-]{0,95}(?::[a-z0-9][a-z0-9._-]{0,95})?$"
)
SHA256_RE = re.compile(r"^[0-9a-f]{64}$")
PUBLIC_ACCESSION_RE = re.compile(r"^(?:PDB:[A-Za-z0-9]{4}|UniProt:[A-Z0-9]{6,10}|AlphaFoldDB:[A-Za-z0-9_-]{6,})$")
FORBIDDEN_KEY_PARTS = {
    "account_id",
    "api_key",
    "auth_token",
    "candidate_sequence",
    "cost",
    "credential",
    "endpoint",
    "fasta",
    "internal_note",
    "operator_note",
    "reasoning",
    "agent_trace",
    "debug_log",
    "model_prompt",
    "meta_concern",
    "password",
    "private_path",
    "provider_id",
    "provider_resource",
    "secret",
    "sequence",
    "sequence_ref",
    "signed_url",
    "token",
    "thinking",
}
PUBLIC_SOURCE_POSTURES = {"public_data", "synthetic_demo", "report_only"}
PUBLIC_RESULT_BOUNDARIES = {"planning", "public_demo", "public_synthetic_demo", "insufficient_support", "blocked"}
ROUND_ROLES = ("generator", "sequence_designer", "predictor", "scorer", "filter")
ROUTABLE_STAGES = ("generation", "sequence_design", "cofold", "scoring", "filter", "report")
BACKENDS = {"local", "api", "fal", "neocloud", "runpod", "aws", "modal", "lambda", "cloud_vm", "ssh_hpc"}
ROUTE_EXECUTION_METHODS_BY_BACKEND = {
    "local": frozenset({"platform_skill", "self_hosted"}),
    "api": frozenset({"platform_skill", "hosted_api"}),
    "fal": frozenset({"platform_skill", "hosted_api", "self_hosted"}),
    "neocloud": frozenset({"platform_skill", "hosted_api", "self_hosted"}),
    "runpod": frozenset({"platform_skill", "hosted_api", "self_hosted"}),
    "aws": frozenset({"platform_skill", "hosted_api", "self_hosted"}),
    "modal": frozenset({"platform_skill", "hosted_api", "self_hosted"}),
    "lambda": frozenset({"platform_skill", "hosted_api", "self_hosted"}),
    "cloud_vm": frozenset({"platform_skill", "hosted_api", "self_hosted"}),
    "ssh_hpc": frozenset({"platform_skill", "hosted_api", "self_hosted"}),
}
BACKEND_PROVIDERS = {
    "local": {"local"},
    "fal": {"fal"},
    "neocloud": {"neocloud"},
    "runpod": {"runpod"},
    "aws": {"aws"},
    "modal": {"modal"},
    "lambda": {"lambda"},
    "cloud_vm": {"generic_cloud"},
    "ssh_hpc": {"ssh_hpc"},
}
WORKFLOW_STRATEGY_MODES = frozenset(
    {"published_shape_replay", "deliberate_tool_swap", "replay_and_swap", "independent"}
)
WORKFLOW_REFERENCE_SCOPES = frozenset({"published_workflow_shape", "published_tool_identities"})
API_ADAPTER_CONTRACT_REF = "templates/binder-api-adapter-contract.json"


class BinderLaneError(ValueError):
    """Raised when a public binder-round contract fails closed."""


def read_json(path: Path) -> Any:
    def reject_duplicates(pairs: list[tuple[str, Any]]) -> dict[str, Any]:
        result: dict[str, Any] = {}
        for key, value in pairs:
            if key in result:
                raise BinderLaneError("invalid JSON: duplicate object key")
            result[key] = value
        return result

    def reject_constant(_: str) -> None:
        raise BinderLaneError("invalid JSON: non-finite number")

    try:
        return json.loads(
            path.read_text(encoding="utf-8"),
            object_pairs_hook=reject_duplicates,
            parse_constant=reject_constant,
        )
    except json.JSONDecodeError as exc:
        raise BinderLaneError("invalid JSON in input file") from exc


def write_json(path: Path, payload: Any) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    try:
        encoded = json.dumps(payload, indent=2, sort_keys=True, allow_nan=False) + "\n"
    except ValueError as exc:
        raise BinderLaneError("JSON output contains a non-finite number") from exc
    path.write_text(encoded, encoding="utf-8")


def sha256_path(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for block in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(block)
    return digest.hexdigest()


def sha256_json(payload: Any) -> str:
    encoded = json.dumps(payload, sort_keys=True, separators=(",", ":"), ensure_ascii=True).encode("utf-8")
    return hashlib.sha256(encoded).hexdigest()


def validate_api_adapter_contract(payload: Any) -> dict[str, Any]:
    contract = _require_public_document(payload, "API adapter contract")
    _require_exact_keys(
        contract,
        {
            "schema_version",
            "contract_id",
            "provider_class",
            "implementation_status",
            "network_access",
            "launch_authorization",
            "required_reviews",
            "request_contract",
            "boundary",
        },
        "API adapter contract",
    )
    if (
        contract.get("schema_version") != "structure-factory-binder-api-adapter-contract-v1"
        or contract.get("contract_id") != "operator-api-adapter"
        or contract.get("provider_class") != "api"
        or contract.get("implementation_status") != "operator_supplied"
        or contract.get("network_access") != "operator_gated"
        or contract.get("launch_authorization") != "not_granted"
    ):
        raise BinderLaneError("API adapter contract has an invalid execution boundary")
    expected_reviews = [
        "current service terms and tool license",
        "input retention and model-training policy",
        "private-data eligibility",
        "runtime credential injection",
        "request limit and budget",
        "artifact export and deletion",
    ]
    if contract.get("required_reviews") != expected_reviews:
        raise BinderLaneError("API adapter contract review requirements changed")
    expected_request = {
        "input": "stage-specific manifest resolved outside public git",
        "output": "stage artifact index with counts, hashes, and validation notes",
        "failure_policy": "preserve failed rows and stop before downstream promotion",
    }
    if contract.get("request_contract") != expected_request:
        raise BinderLaneError("API adapter request contract changed")
    if contract.get("boundary") != (
        "This template defines a handoff shape. It contains no service address, account identifier, "
        "credential, accepted-license state, or launch instruction."
    ):
        raise BinderLaneError("API adapter public boundary changed")
    return contract


def safe_relative_path(value: str, label: str) -> Path:
    if not isinstance(value, str) or not value.strip() or "\x00" in value or "\\" in value:
        raise BinderLaneError(f"{label} must be a non-empty POSIX relative path")
    pure = PurePosixPath(value)
    if pure.is_absolute() or any(part in {"", ".", ".."} for part in pure.parts):
        raise BinderLaneError(f"{label} must stay below the workspace root")
    if MACHINE_PATH_RE.search(value):
        raise BinderLaneError(f"{label} contains a machine-local path")
    return Path(*pure.parts)


def require_public_prose(value: Any, label: str) -> str:
    if not isinstance(value, str) or not value.strip() or any(ord(character) < 32 for character in value):
        raise BinderLaneError(f"{label} must be non-empty public text")
    if re.search(
        r"(?i)\b(?:internal|private|unpublished|patient|scratchpad|reasoning|agent[ _-]?trace|reviewer[ _-]?note|meta[ _-]?concern|operator[ _-]?note|debug[ _-]?log|model[ _-]?prompt)\b",
        value,
    ):
        raise BinderLaneError(f"{label} contains non-public process text")
    return value


def contained_path(root: Path, relative: str, label: str, *, must_exist: bool = False) -> Path:
    root = root.resolve()
    path = (root / safe_relative_path(relative, label)).resolve()
    try:
        path.relative_to(root)
    except ValueError as exc:
        raise BinderLaneError(f"{label} resolves outside the workspace root") from exc
    if must_exist and not path.is_file():
        raise BinderLaneError(f"{label} does not name a file")
    return path


def runtime_path(root: Path, relative: str, label: str, *, must_exist: bool = False) -> Path:
    safe = safe_relative_path(relative, label)
    if not safe.parts or safe.parts[0] != ".runtime" or len(safe.parts) == 1:
        raise BinderLaneError(f"{label} must be below .runtime/")
    lexical = root.resolve()
    for part in safe.parts:
        lexical = lexical / part
        if lexical.exists() and lexical.is_symlink():
            raise BinderLaneError(f"{label} must not use symlink components")
    path = contained_path(root, safe.as_posix(), label)
    if must_exist and not path.exists():
        raise BinderLaneError(f"{label} does not exist")
    return path


def require_runtime_root(workspace_root: Path, run_root: Path, *, must_exist: bool) -> Path:
    workspace = workspace_root.resolve()
    resolved = run_root.resolve()
    try:
        relative = resolved.relative_to(workspace)
    except ValueError as exc:
        raise BinderLaneError("run root must stay below the workspace") from exc
    if len(relative.parts) < 2 or relative.parts[0] != ".runtime":
        raise BinderLaneError("run root must be below .runtime/")
    current = workspace
    for part in relative.parts:
        current = current / part
        if current.exists() and current.is_symlink():
            raise BinderLaneError("run root must not use symlink components")
    if must_exist and not resolved.is_dir():
        raise BinderLaneError("run root must name an existing directory")
    return resolved


def _scan_public_value(value: Any, location: str = "document") -> list[str]:
    findings: list[str] = []
    if isinstance(value, dict):
        for key, child in value.items():
            normalized = re.sub(r"(?<!^)(?=[A-Z])", "_", str(key)).lower().replace("-", "_")
            if normalized in FORBIDDEN_KEY_PARTS or normalized.endswith(("_secret", "_token", "_password")):
                findings.append(f"forbidden field below {location}")
            findings.extend(_scan_public_value(child, f"{location}.field"))
    elif isinstance(value, list):
        for index, child in enumerate(value):
            findings.extend(_scan_public_value(child, f"{location}[{index}]"))
    elif isinstance(value, str):
        if MACHINE_PATH_RE.search(value):
            findings.append(f"machine-local path at {location}")
        if any(pattern.search(value) for pattern in SENSITIVE_VALUE_PATTERNS):
            findings.append(f"secret-shaped or private-network value at {location}")
    return findings


def _require_public_document(payload: Any, label: str) -> dict[str, Any]:
    if not isinstance(payload, dict):
        raise BinderLaneError(f"{label} must be a JSON object")
    findings = _scan_public_value(payload, label)
    if findings:
        raise BinderLaneError("; ".join(findings))
    return payload


def _require_exact_keys(payload: dict[str, Any], expected: set[str], label: str) -> None:
    missing = expected - set(payload)
    extra = set(payload) - expected
    if missing or extra:
        raise BinderLaneError(f"{label} has missing or undeclared fields")


def _registry_ids(path: Path) -> set[str]:
    ids: set[str] = set()
    for line in path.read_text(encoding="utf-8").splitlines():
        match = re.match(r"^  ([A-Za-z0-9_-]+):\s*$", line)
        if match:
            ids.add(match.group(1))
    return ids


def _registry_license_gates(path: Path) -> dict[str, str]:
    gates: dict[str, str] = {}
    current: str | None = None
    for line in path.read_text(encoding="utf-8").splitlines():
        entry = re.match(r"^  ([A-Za-z0-9_-]+):\s*$", line)
        if entry:
            current = entry.group(1)
            continue
        gate = re.match(r"^    license_gate:\s*['\"]?([^'\"]+?)['\"]?\s*$", line)
        if current and gate:
            gates[current] = gate.group(1)
    return gates


def validate_ledger(payload: Any, workspace_root: Path | None = None) -> dict[str, Any]:
    ledger = _require_public_document(payload, "capability ledger")
    _require_exact_keys(
        ledger,
        {"schema_version", "evidence_scope", "state_definitions", "tools", "boundary"},
        "capability ledger",
    )
    if ledger.get("schema_version") != LEDGER_SCHEMA:
        raise BinderLaneError(f"capability ledger schema_version must be {LEDGER_SCHEMA}")
    if ledger.get("evidence_scope") != "public_repository_only":
        raise BinderLaneError("capability ledger evidence_scope must be public_repository_only")
    definitions = ledger.get("state_definitions")
    if not isinstance(definitions, dict):
        raise BinderLaneError("capability ledger state_definitions must be an object")
    _require_exact_keys(definitions, {"listed", "documented", "contract_checked"}, "capability ledger state_definitions")
    if not all(isinstance(value, str) and value.strip() for value in definitions.values()):
        raise BinderLaneError("capability ledger state definitions must be non-empty strings")
    for value in definitions.values():
        require_public_prose(value, "capability ledger state definition")
    if not isinstance(ledger.get("boundary"), str) or not ledger["boundary"].strip():
        raise BinderLaneError("capability ledger boundary must be a non-empty string")
    require_public_prose(ledger["boundary"], "capability ledger boundary")
    tools = ledger.get("tools")
    if not isinstance(tools, list) or not tools:
        raise BinderLaneError("capability ledger tools must be a non-empty list")
    seen: set[str] = set()
    for index, tool in enumerate(tools):
        if not isinstance(tool, dict):
            raise BinderLaneError(f"capability ledger tool {index} must be an object")
        _require_exact_keys(
            tool,
            {
                "id",
                "kind",
                "registry_id",
                "roles",
                "evidence_level",
                "license_gate",
                "provider_bound",
                "execution_available",
                "public_evidence",
            },
            f"capability ledger tool {index}",
        )
        tool_id = tool.get("id")
        if not isinstance(tool_id, str) or SAFE_ID_RE.fullmatch(tool_id) is None:
            raise BinderLaneError(f"capability ledger tool {index} has an invalid id")
        if tool_id in seen:
            raise BinderLaneError(f"duplicate capability ledger tool: {tool_id}")
        seen.add(tool_id)
        roles = tool.get("roles")
        if not isinstance(roles, list) or not roles or len(roles) != len(set(roles)) or not set(roles).issubset(ROUND_ROLES):
            raise BinderLaneError(f"capability ledger tool {tool_id} has invalid roles")
        if tool.get("evidence_level") not in {"listed", "documented", "contract_checked"}:
            raise BinderLaneError(f"capability ledger tool {tool_id} has invalid evidence_level")
        kind = tool.get("kind")
        registry_id = tool.get("registry_id")
        if kind not in {"software", "built_in"}:
            raise BinderLaneError(f"capability ledger tool {tool_id} has invalid kind")
        if kind == "software" and (not isinstance(registry_id, str) or not registry_id):
            raise BinderLaneError(f"capability ledger tool {tool_id} needs registry_id")
        if kind == "built_in" and registry_id is not None:
            raise BinderLaneError(f"built-in capability {tool_id} must not claim a registry row")
        if tool.get("provider_bound") is not False or not isinstance(tool.get("execution_available"), bool):
            raise BinderLaneError(f"public capability {tool_id} has an invalid execution state")
        if tool["execution_available"] and tool["evidence_level"] != "contract_checked":
            raise BinderLaneError(f"executable public capability {tool_id} needs contract-checked evidence")
        if not isinstance(tool.get("license_gate"), str) or not tool["license_gate"].strip():
            raise BinderLaneError(f"capability ledger tool {tool_id} needs a license_gate")
        evidence = tool.get("public_evidence")
        if not isinstance(evidence, list) or not evidence or not all(isinstance(item, str) for item in evidence):
            raise BinderLaneError(f"capability ledger tool {tool_id} needs public_evidence")
        for item in evidence:
            evidence_path = safe_relative_path(item, f"capability evidence for {tool_id}")
            if evidence_path.parts[0] not in {"docs", "examples", "modules", "references", "src", "tools"}:
                raise BinderLaneError(f"capability evidence for {tool_id} must use a public evidence directory")
    if workspace_root is not None:
        registry_path = contained_path(workspace_root, "references/software-registry.yaml", "software registry", must_exist=True)
        registry_ids = _registry_ids(registry_path)
        registry_gates = _registry_license_gates(registry_path)
        for tool in tools:
            if tool["kind"] == "software" and tool["registry_id"] not in registry_ids:
                raise BinderLaneError(f"capability {tool['id']} names an unknown software registry id")
            if tool["kind"] == "software" and tool["license_gate"] != registry_gates.get(tool["registry_id"]):
                raise BinderLaneError(f"capability {tool['id']} license gate differs from the software registry")
            for evidence_path in tool["public_evidence"]:
                path = contained_path(workspace_root, evidence_path, f"capability evidence for {tool['id']}", must_exist=True)
                if path.is_symlink():
                    raise BinderLaneError(f"capability evidence for {tool['id']} must not be a symlink")
    return ledger


def provider_profiles(workspace_root: Path) -> list[dict[str, Any]]:
    root = workspace_root.resolve()
    profiles: list[dict[str, Any]] = []
    profile_root = root / "modules" / "provider-profiles"
    for path in sorted(profile_root.glob("**/*.json")):
        if path.is_symlink():
            raise BinderLaneError("provider profile must not be a symlink")
        payload = _require_public_document(read_json(path), path.name)
        profile_id = payload.get("profile_id")
        provider = payload.get("provider")
        operator_gate_required = payload.get("operator_gate_required")
        if (
            not isinstance(profile_id, str)
            or not isinstance(provider, str)
            or not isinstance(operator_gate_required, bool)
        ):
            continue
        profiles.append(
            {
                "profile_id": profile_id,
                "provider": provider,
                "provider_class": payload.get("provider_class"),
                "profile_ref": path.relative_to(root).as_posix(),
                "operator_gate_required": operator_gate_required,
                "execution_ready_requires": payload.get("execution_ready_requires", []),
            }
        )
    profiles.append(
        {
            "profile_id": "operator-api-adapter",
            "provider": "api",
            "provider_class": "operator_adapter",
            "profile_ref": None,
            "operator_gate_required": True,
            "execution_ready_requires": ["operator_adapter", "runtime_secret_reference", "terms_review", "explicit_operator_launch"],
        }
    )
    return profiles


def menu(ledger: dict[str, Any], workspace_root: Path | None = None) -> dict[str, Any]:
    validated = validate_ledger(ledger, workspace_root)
    profiles = provider_profiles(workspace_root) if workspace_root is not None else []
    profile_refs_by_backend: dict[str, list[str | None]] = {backend: [] for backend in BACKENDS}
    for profile in profiles:
        backend = (
            "api"
            if profile["provider"] == "api"
            else next(
                backend
                for backend, providers in BACKEND_PROVIDERS.items()
                if profile["provider"] in providers
            )
        )
        profile_refs_by_backend[backend].append(profile["profile_ref"])
    route_contracts = []
    for backend in sorted(BACKENDS):
        for execution_method in sorted(ROUTE_EXECUTION_METHODS_BY_BACKEND[backend]):
            route_contracts.append(
                {
                    "backend": backend,
                    "execution_method": execution_method,
                    "profile_refs": sorted(
                        profile_refs_by_backend[backend], key=lambda value: value or ""
                    ),
                    "platform_skill_id_required": execution_method == "platform_skill",
                    "adapter_route_declaration_required": execution_method != "platform_skill",
                }
            )
    return {
        "schema_version": "structure-factory-binder-round-menu-v1",
        "planning_available": True,
        "direct_launch_available": any(tool["execution_available"] for tool in validated["tools"]),
        "evidence_scope": "public_repository_only",
        "roles": {
            role: [
                {
                    "id": tool["id"],
                    "evidence_level": tool["evidence_level"],
                    "license_gate": tool["license_gate"],
                    "planning_selectable": True,
                    "bundled_execution_available": tool["execution_available"],
                    "runtime_status": "not_checked",
                }
                for tool in validated["tools"]
                if role in tool["roles"]
            ]
            for role in ROUND_ROLES
        },
        "provider_profiles": profiles,
        "route_contracts": route_contracts,
        "supported_topologies": sorted(BACKENDS | {"mixed"}),
        "boundary": "The menu reports route-contract choices separately from bundled adapter availability and provider service. A platform skill needs its public skill ID. A hosted or self-hosted route needs an adapter that declares the selected route.",
    }


def _request_selection(value: Any, label: str) -> tuple[str, str | None]:
    if isinstance(value, str):
        return value, None
    if not isinstance(value, dict):
        raise BinderLaneError(f"{label} must name a tool or a tool and public variant")
    _require_exact_keys(value, {"tool_id", "variant_id"}, label)
    tool_id = value.get("tool_id")
    variant_id = value.get("variant_id")
    if not isinstance(tool_id, str) or SAFE_ID_RE.fullmatch(tool_id) is None:
        raise BinderLaneError(f"{label} tool_id must be a lowercase public slug")
    if variant_id is not None and (
        not isinstance(variant_id, str) or SAFE_ID_RE.fullmatch(variant_id) is None
    ):
        raise BinderLaneError(f"{label} variant_id must be null or a lowercase public slug")
    return tool_id, variant_id


def _selection_record(row: dict[str, Any], variant_id: str | None = None) -> dict[str, Any]:
    return {
        "tool_id": row["id"],
        "variant_id": variant_id,
        "registry_id": row.get("registry_id"),
        "evidence_level": row["evidence_level"],
        "public_evidence": row["public_evidence"],
        "license_gate": row["license_gate"],
        "runtime_status": "not_checked",
    }


def _require_tool(rows: dict[str, dict[str, Any]], tool_id: Any, role: str) -> dict[str, Any]:
    if not isinstance(tool_id, str) or tool_id not in rows or role not in rows[tool_id]["roles"]:
        raise BinderLaneError(f"selected {role} tool is not listed for that role: {tool_id}")
    return rows[tool_id]


def _provider_profile_map(workspace_root: Path | None) -> dict[str, dict[str, Any]]:
    if workspace_root is None:
        return {}
    return {profile["profile_ref"]: profile for profile in provider_profiles(workspace_root) if profile["profile_ref"]}


def _validate_routes(
    policy: Any,
    workspace_root: Path | None,
    toolchain_ids: set[str],
) -> tuple[dict[str, Any], list[dict[str, Any]]]:
    if not isinstance(policy, dict):
        raise BinderLaneError("request execution_policy must be an object")
    _require_exact_keys(
        policy,
        {"topology", "authorization", "max_spend_usd", "max_wall_clock_minutes", "routes"},
        "execution_policy",
    )
    topology = policy.get("topology")
    if topology not in BACKENDS | {"mixed"}:
        raise BinderLaneError("execution_policy topology is not supported")
    if policy.get("authorization") != "plan_then_explicit_runtime_authorization":
        raise BinderLaneError(
            "execution_policy authorization must require explicit runtime authorization after planning"
        )
    routes = policy.get("routes")
    if not isinstance(routes, list) or not routes:
        raise BinderLaneError("execution_policy routes must be a non-empty list")
    profile_map = _provider_profile_map(workspace_root)
    covered: list[tuple[str, str]] = []
    normalized: list[dict[str, Any]] = []
    used_backends: set[str] = set()
    route_ids: set[str] = set()
    for index, route in enumerate(routes):
        if not isinstance(route, dict):
            raise BinderLaneError(f"execution route {index} must be an object")
        common_route_keys = {
            "id",
            "toolchain_ids",
            "stages",
            "backend",
            "execution_method",
            "profile_ref",
            "operator_adapter_required",
        }
        expected_route_keys = common_route_keys | (
            {"adapter_contract_ref", "api_policy"} if route.get("backend") == "api" else set()
        ) | ({"platform_skill_id"} if route.get("execution_method") == "platform_skill" else set())
        if route.get("execution_method") == "platform_skill" and "platform_skill_id" not in route:
            raise BinderLaneError(f"execution route {index} platform_skill_id is required")
        _require_exact_keys(route, expected_route_keys, f"execution route {index}")
        route_id = route.get("id")
        if not isinstance(route_id, str) or SAFE_ID_RE.fullmatch(route_id) is None or route_id in route_ids:
            raise BinderLaneError(f"execution route {index} has an invalid or duplicate id")
        route_ids.add(route_id)
        stages = route.get("stages")
        backend = route.get("backend")
        execution_method = route.get("execution_method")
        if not isinstance(stages, list) or not stages or not all(stage in ROUTABLE_STAGES for stage in stages):
            raise BinderLaneError(f"execution route {index} has invalid stages")
        if backend not in BACKENDS:
            raise BinderLaneError(f"execution route {index} has invalid backend")
        if execution_method not in ROUTE_EXECUTION_METHODS_BY_BACKEND[backend]:
            raise BinderLaneError(f"execution route {index} has an unsupported backend and execution_method")
        platform_skill_id = route.get("platform_skill_id")
        if execution_method == "platform_skill" and (
            not isinstance(platform_skill_id, str)
            or PLATFORM_SKILL_REF_RE.fullmatch(platform_skill_id) is None
        ):
            raise BinderLaneError(
                f"execution route {index} platform_skill_id must be a public skill or namespace:skill reference"
            )
        route_toolchains = route.get("toolchain_ids")
        if not isinstance(route_toolchains, list) or not route_toolchains or not all(item in toolchain_ids for item in route_toolchains):
            raise BinderLaneError(f"execution route {index} has invalid toolchain_ids")
        if len(route_toolchains) != len(set(route_toolchains)):
            raise BinderLaneError(f"execution route {index} repeats a toolchain id")
        covered.extend((toolchain_id, stage) for toolchain_id in route_toolchains for stage in stages)
        used_backends.add(backend)
        profile_ref = route.get("profile_ref")
        adapter_required = route.get("operator_adapter_required")
        if not isinstance(adapter_required, bool):
            raise BinderLaneError(f"execution route {index} operator_adapter_required must be boolean")
        operator_gate_required = True
        if backend == "api":
            if profile_ref is not None:
                raise BinderLaneError(f"{backend} routes must not name a provider profile")
            if adapter_required is not True:
                raise BinderLaneError("api routes require an operator adapter")
            adapter_contract_ref = route.get("adapter_contract_ref")
            if adapter_contract_ref != API_ADAPTER_CONTRACT_REF:
                raise BinderLaneError("api routes require the approved public adapter contract")
            if workspace_root is not None:
                adapter_contract_path = contained_path(workspace_root, adapter_contract_ref, "api adapter contract", must_exist=True)
                if adapter_contract_path.is_symlink() or adapter_contract_path.suffix != ".json":
                    raise BinderLaneError("api adapter contract must be a regular public JSON file")
                validate_api_adapter_contract(read_json(adapter_contract_path))
            api_policy = route.get("api_policy")
            if not isinstance(api_policy, dict) or api_policy != {
                "terms_review_required": True,
                "input_retention_review_required": True,
                "runtime_secret_reference_required": True,
            }:
                raise BinderLaneError("api routes require terms, input-retention, and runtime-secret review")
        else:
            if not isinstance(profile_ref, str):
                raise BinderLaneError(f"{backend} routes require a public provider profile reference")
            safe_relative_path(profile_ref, f"execution route {index} profile_ref")
            if workspace_root is not None and profile_ref not in profile_map:
                raise BinderLaneError(f"execution route {index} names an unknown provider profile")
            if workspace_root is not None:
                provider = profile_map[profile_ref]["provider"]
                if provider not in BACKEND_PROVIDERS[backend]:
                    raise BinderLaneError(f"execution route {index} backend does not match its provider profile")
                operator_gate_required = profile_map[profile_ref]["operator_gate_required"]
        normalized_route = {
            "id": route_id,
            "toolchain_ids": route_toolchains,
            "stages": stages,
            "backend": backend,
            "execution_method": execution_method,
            "profile_ref": profile_ref,
            "operator_adapter_required": bool(adapter_required),
            "operator_gate_required": operator_gate_required,
        }
        if execution_method == "platform_skill":
            normalized_route["platform_skill_id"] = platform_skill_id
        if profile_ref is not None and workspace_root is not None:
            normalized_route["profile_sha256"] = sha256_path(contained_path(workspace_root, profile_ref, "provider profile", must_exist=True))
        if backend == "api":
            normalized_route["adapter_contract_ref"] = route["adapter_contract_ref"]
            if workspace_root is not None:
                normalized_route["adapter_contract_sha256"] = sha256_path(adapter_contract_path)
            normalized_route["api_policy"] = route["api_policy"]
        normalized.append(normalized_route)
    expected_pairs = {(toolchain_id, stage) for toolchain_id in toolchain_ids for stage in ROUTABLE_STAGES}
    if set(covered) != expected_pairs or len(covered) != len(set(covered)):
        raise BinderLaneError("execution routes must cover each toolchain and routable stage exactly once")
    if (len(used_backends) > 1 and topology != "mixed") or (len(used_backends) == 1 and topology != next(iter(used_backends))):
        raise BinderLaneError("execution_policy topology must match the configured route backends")
    maximum_spend = policy.get("max_spend_usd")
    if maximum_spend is not None and (
        isinstance(maximum_spend, bool)
        or not isinstance(maximum_spend, (int, float))
        or not math.isfinite(maximum_spend)
        or maximum_spend < 0
    ):
        raise BinderLaneError("execution_policy max_spend_usd must be null or non-negative")
    maximum_minutes = policy.get("max_wall_clock_minutes")
    if not isinstance(maximum_minutes, int) or isinstance(maximum_minutes, bool) or maximum_minutes <= 0:
        raise BinderLaneError("execution_policy max_wall_clock_minutes must be a positive integer")
    return {
        "topology": topology,
        "authorization": "plan_then_explicit_runtime_authorization",
        "max_spend_usd": maximum_spend,
        "max_wall_clock_minutes": maximum_minutes,
        "routes": normalized,
    }, normalized


def _validate_optimization_policy(
    policy: Any,
    metrics: dict[str, str],
    toolchains: list[dict[str, Any]],
    execution_policy: dict[str, Any],
) -> dict[str, Any]:
    if not isinstance(policy, dict):
        raise BinderLaneError("request optimization_policy must be an object")
    _require_exact_keys(
        policy,
        {
            "round_count",
            "current_round_index",
            "primary_metric_id",
            "direction",
            "candidate_policy",
            "stopping_rule",
            "round_budget_usd",
        },
        "optimization_policy",
    )
    round_count = policy.get("round_count")
    if not isinstance(round_count, int) or isinstance(round_count, bool) or not 1 <= round_count <= 1000:
        raise BinderLaneError("optimization_policy round_count must be between 1 and 1000")
    current_round_index = policy.get("current_round_index")
    if (
        not isinstance(current_round_index, int)
        or isinstance(current_round_index, bool)
        or not 1 <= current_round_index <= round_count
    ):
        raise BinderLaneError("optimization_policy current_round_index must be between 1 and round_count")
    primary_metric_id = policy.get("primary_metric_id")
    if not isinstance(primary_metric_id, str) or primary_metric_id not in metrics:
        raise BinderLaneError("optimization_policy primary_metric_id must name a comparison metric")
    direction = policy.get("direction")
    expected_direction = "maximize" if metrics[primary_metric_id] == "higher_is_better" else "minimize"
    if direction != expected_direction:
        raise BinderLaneError("optimization_policy direction must match the primary metric direction")
    candidate_policy = policy.get("candidate_policy")
    if not isinstance(candidate_policy, dict):
        raise BinderLaneError("optimization_policy candidate_policy must be an object")
    _require_exact_keys(
        candidate_policy,
        {"mode", "candidate_count_per_toolchain"},
        "optimization_policy candidate_policy",
    )
    if candidate_policy.get("mode") != "fixed_per_toolchain":
        raise BinderLaneError("optimization_policy candidate_policy mode must be fixed_per_toolchain")
    candidate_count = candidate_policy.get("candidate_count_per_toolchain")
    if (
        not isinstance(candidate_count, int)
        or isinstance(candidate_count, bool)
        or not 1 <= candidate_count <= 10000
    ):
        raise BinderLaneError("optimization_policy candidate_count_per_toolchain must be between 1 and 10000")
    if any(toolchain["candidate_count"] != candidate_count for toolchain in toolchains):
        raise BinderLaneError("optimization_policy candidate count must match every toolchain")
    stopping_rule = policy.get("stopping_rule")
    if not isinstance(stopping_rule, dict):
        raise BinderLaneError("optimization_policy stopping_rule must be an object")
    stopping_type = stopping_rule.get("type")
    if stopping_type == "fixed_round_count":
        _require_exact_keys(stopping_rule, {"type"}, "optimization_policy stopping_rule")
        normalized_stopping_rule = {"type": "fixed_round_count"}
    elif stopping_type == "target_threshold":
        _require_exact_keys(
            stopping_rule,
            {"type", "threshold", "direction"},
            "optimization_policy stopping_rule",
        )
        threshold = stopping_rule.get("threshold")
        if isinstance(threshold, bool) or not isinstance(threshold, (int, float)) or not math.isfinite(threshold):
            raise BinderLaneError("optimization_policy target threshold must be finite")
        if stopping_rule.get("direction") != direction:
            raise BinderLaneError("optimization_policy target threshold direction must match the primary metric")
        normalized_stopping_rule = {
            "type": "target_threshold",
            "threshold": threshold,
            "direction": direction,
        }
    elif stopping_type == "no_improvement":
        _require_exact_keys(
            stopping_rule,
            {"type", "patience_rounds", "minimum_delta", "direction"},
            "optimization_policy stopping_rule",
        )
        patience_rounds = stopping_rule.get("patience_rounds")
        if (
            not isinstance(patience_rounds, int)
            or isinstance(patience_rounds, bool)
            or not 1 <= patience_rounds <= round_count
        ):
            raise BinderLaneError("optimization_policy patience_rounds must be between 1 and round_count")
        if stopping_rule.get("direction") != direction:
            raise BinderLaneError("optimization_policy no_improvement direction must match the primary metric")
        minimum_delta = stopping_rule.get("minimum_delta")
        if (
            isinstance(minimum_delta, bool)
            or not isinstance(minimum_delta, (int, float))
            or not math.isfinite(minimum_delta)
            or minimum_delta < 0
        ):
            raise BinderLaneError("optimization_policy minimum_delta must be a non-negative finite value")
        normalized_stopping_rule = {
            "type": "no_improvement",
            "patience_rounds": patience_rounds,
            "minimum_delta": minimum_delta,
            "direction": direction,
        }
    else:
        raise BinderLaneError("optimization_policy stopping_rule type is not supported")
    budgets = policy.get("round_budget_usd")
    if not isinstance(budgets, list) or len(budgets) != round_count:
        raise BinderLaneError("optimization_policy round_budget_usd must contain one value for each round")
    maximum_spend = execution_policy.get("max_spend_usd")
    if maximum_spend is None:
        if any(value is not None for value in budgets):
            raise BinderLaneError("optimization_policy uses null round budgets when execution_policy max_spend_usd is null")
    else:
        if any(
            isinstance(value, bool)
            or not isinstance(value, (int, float))
            or not math.isfinite(value)
            or value < 0
            for value in budgets
        ):
            raise BinderLaneError("optimization_policy round_budget_usd must contain non-negative finite values")
        if not math.isclose(sum(budgets), maximum_spend, rel_tol=0.0, abs_tol=1e-9):
            raise BinderLaneError("optimization_policy round budgets must equal execution_policy max_spend_usd")
    return {
        "round_count": round_count,
        "current_round_index": current_round_index,
        "primary_metric_id": primary_metric_id,
        "direction": direction,
        "candidate_policy": {
            "mode": "fixed_per_toolchain",
            "candidate_count_per_toolchain": candidate_count,
        },
        "stopping_rule": normalized_stopping_rule,
        "round_budget_usd": list(budgets),
    }


def _validate_workflow_strategy(
    strategy: Any,
    study_template: str,
    toolchain_ids: set[str],
) -> dict[str, Any]:
    if not isinstance(strategy, dict):
        raise BinderLaneError("request workflow_strategy must be an object")
    _require_exact_keys(
        strategy,
        {"mode", "reference_scope", "replay_toolchain_ids", "swap_toolchain_ids"},
        "workflow_strategy",
    )
    mode = strategy.get("mode")
    if not isinstance(mode, str) or mode not in WORKFLOW_STRATEGY_MODES:
        raise BinderLaneError("workflow_strategy mode is not supported")
    reference_scope = strategy.get("reference_scope")
    replay_ids = strategy.get("replay_toolchain_ids")
    swap_ids = strategy.get("swap_toolchain_ids")
    for label, values in (("replay_toolchain_ids", replay_ids), ("swap_toolchain_ids", swap_ids)):
        if (
            not isinstance(values, list)
            or not all(isinstance(item, str) and item in toolchain_ids for item in values)
            or len(values) != len(set(values))
        ):
            raise BinderLaneError(f"workflow_strategy {label} must contain unique declared toolchain IDs")
    replay_set = set(replay_ids)
    swap_set = set(swap_ids)
    if replay_set.intersection(swap_set):
        raise BinderLaneError("workflow_strategy replay and swap toolchains must be disjoint")
    if mode == "independent":
        if reference_scope is not None or replay_set or swap_set:
            raise BinderLaneError("independent workflow_strategy must not classify reference toolchains")
    else:
        if study_template != "published-binder-comparison-shape":
            raise BinderLaneError("reference workflow strategies require the published comparison template")
        if not isinstance(reference_scope, str) or reference_scope not in WORKFLOW_REFERENCE_SCOPES:
            raise BinderLaneError(
                "reference workflow strategies must use published_workflow_shape or published_tool_identities"
            )
        if replay_set.union(swap_set) != toolchain_ids:
            raise BinderLaneError("workflow_strategy must classify every toolchain")
        if mode == "published_shape_replay" and (replay_set != toolchain_ids or swap_set):
            raise BinderLaneError("published_shape_replay must classify every toolchain as replay")
        if mode == "deliberate_tool_swap" and (swap_set != toolchain_ids or replay_set):
            raise BinderLaneError("deliberate_tool_swap must classify every toolchain as a swap")
        if mode == "replay_and_swap" and (not replay_set or not swap_set):
            raise BinderLaneError("replay_and_swap requires at least one replay and one swap toolchain")
    return {
        "mode": mode,
        "reference_scope": reference_scope,
        "replay_toolchain_ids": list(replay_ids),
        "swap_toolchain_ids": list(swap_ids),
    }


def _selection_identity(selection: dict[str, Any]) -> tuple[str, str | None]:
    return selection["tool_id"], selection.get("variant_id")


def _published_identity_set(
    rows: Any,
    label: str,
    variant_key: str,
) -> set[tuple[str, str | None]]:
    if not isinstance(rows, list) or not rows:
        raise BinderLaneError(f"published workflow {label} must be a non-empty list")
    identities: set[tuple[str, str | None]] = set()
    for row in rows:
        if not isinstance(row, dict):
            raise BinderLaneError(f"published workflow {label} entries must be objects")
        tool_id = row.get("tool_id")
        variant_id = row.get(variant_key)
        if (
            not isinstance(tool_id, str)
            or SAFE_ID_RE.fullmatch(tool_id) is None
            or variant_id is not None
            and (not isinstance(variant_id, str) or SAFE_ID_RE.fullmatch(variant_id) is None)
        ):
            raise BinderLaneError(f"published workflow {label} contains an invalid identity")
        identities.add((tool_id, variant_id))
    if len(identities) != len(rows):
        raise BinderLaneError(f"published workflow {label} contains duplicate identities")
    return identities


def _published_identity_matches(
    toolchain: dict[str, Any],
    bounded_stage_ids: list[str],
    workflow: dict[str, Any],
) -> tuple[bool, list[str]]:
    cohort = workflow["published_tool_cohort"]
    mismatches: list[str] = []
    selected_stages = set(bounded_stage_ids)
    if "generation" in selected_stages:
        published_generators = _published_identity_set(
            cohort.get("generators"), "generators", "variant_id"
        )
        if _selection_identity(toolchain["generator"]) not in published_generators:
            mismatches.append("generation")
    if "sequence_design" in selected_stages:
        published_designers = _published_identity_set(
            cohort.get("sequence_designers"), "sequence_designers", "variant_id"
        )
        native_codesign = cohort.get("native_codesign")
        native_codesign_selected = (
            isinstance(native_codesign, dict)
            and native_codesign.get("method_id") == "native-codesign"
            and native_codesign.get("tool_selected_by_generator") is True
            and _selection_identity(toolchain["sequence_designer"])
            == _selection_identity(toolchain["generator"])
        )
        if (
            _selection_identity(toolchain["sequence_designer"]) not in published_designers
            and not native_codesign_selected
        ):
            mismatches.append("sequence_design")
    if "cofold" in selected_stages:
        published_predictors = _published_identity_set(
            cohort.get("published_score_predictors"), "published_score_predictors", "variant_id"
        )
        if {_selection_identity(row) for row in toolchain["predictors"]} != published_predictors:
            mismatches.append("cofold")
    if "scoring" in selected_stages:
        published_scorers = _published_identity_set(
            cohort.get("published_interface_scorers"), "published_interface_scorers", "measurement_id"
        )
        if {_selection_identity(row) for row in toolchain["scorers"]} != published_scorers:
            mismatches.append("scoring")
    return not mismatches, mismatches


def _validate_published_identity_strategy(
    strategy: dict[str, Any],
    toolchains: list[dict[str, Any]],
    bounded_stage_ids: list[str],
    workflow: dict[str, Any] | None,
) -> None:
    if strategy["reference_scope"] != "published_tool_identities":
        return
    if workflow is None:
        raise BinderLaneError(
            "published_tool_identities requires the public workflow reference in a workspace"
        )
    replay_ids = set(strategy["replay_toolchain_ids"])
    swap_ids = set(strategy["swap_toolchain_ids"])
    identity_stages = {"generation", "sequence_design", "cofold", "scoring"}
    if not identity_stages.intersection(bounded_stage_ids):
        raise BinderLaneError(
            "published_tool_identities requires generation, sequence_design, cofold, or scoring in bounded_stage_ids"
        )
    for toolchain in toolchains:
        matches, mismatches = _published_identity_matches(toolchain, bounded_stage_ids, workflow)
        if toolchain["id"] in replay_ids and not matches:
            raise BinderLaneError(
                "replay toolchain does not match published identities at stages: " + ", ".join(mismatches)
            )
        if toolchain["id"] in swap_ids and matches:
            raise BinderLaneError(
                "swap toolchain must differ from a published tool identity in the bounded stages"
            )


def plan_request(
    request: Any,
    ledger: Any,
    workspace_root: Path | None = None,
    *,
    request_ref: str | None = None,
    ledger_ref: str | None = None,
) -> dict[str, Any]:
    request = _require_public_document(request, "request")
    _require_exact_keys(
        request,
        {
            "schema_version",
            "round_id",
            "study_template",
            "published_workflow",
            "workflow_strategy",
            "comparison_policy",
            "optimization_policy",
            "source_posture",
            "result_boundary",
            "target",
            "toolchains",
            "constraints",
            "license_policy",
            "execution_policy",
            "synthetic_fixture",
        },
        "request",
    )
    ledger = validate_ledger(ledger, workspace_root)
    if request.get("schema_version") != REQUEST_SCHEMA:
        raise BinderLaneError(f"request schema_version must be {REQUEST_SCHEMA}")
    round_id = request.get("round_id")
    if not isinstance(round_id, str) or SAFE_ID_RE.fullmatch(round_id) is None:
        raise BinderLaneError("request round_id must be a lowercase public slug")
    if request.get("source_posture") not in PUBLIC_SOURCE_POSTURES:
        raise BinderLaneError("request source_posture is not supported")
    if request.get("result_boundary") not in {"planning", "public_synthetic_demo"}:
        raise BinderLaneError("request result_boundary must be planning or public_synthetic_demo")
    if request.get("result_boundary") == "public_synthetic_demo" and request.get("source_posture") != "synthetic_demo":
        raise BinderLaneError("public_synthetic_demo requests require synthetic_demo source posture")
    study_template = request.get("study_template")
    if study_template not in {"published-binder-comparison-shape", "toolchain-comparison", "single-arm-replay", "custom"}:
        raise BinderLaneError("request study_template is not supported")
    workflow_request = request.get("published_workflow")
    workflow_reference_ref: str | None = None
    workflow_reference_sha256: str | None = None
    workflow: dict[str, Any] | None = None
    published_stage_ids: list[str] = []
    if study_template == "published-binder-comparison-shape":
        if not isinstance(workflow_request, dict) or workflow_request.get("published_result_values_imported") is not False:
            raise BinderLaneError("published workflow requests must state that result values were not imported")
        _require_exact_keys(
            workflow_request,
            {"reference_ref", "bounded_stage_ids", "published_result_values_imported"},
            "published_workflow",
        )
        workflow_reference_ref = workflow_request.get("reference_ref")
        if not isinstance(workflow_reference_ref, str) or not workflow_reference_ref.startswith("references/"):
            raise BinderLaneError("published workflow requests need a public reference_ref")
        published_stage_ids = workflow_request.get("bounded_stage_ids")
        if (
            not isinstance(published_stage_ids, list)
            or len(published_stage_ids) < 2
            or published_stage_ids[0] != "target"
            or len(published_stage_ids) != len(set(published_stage_ids))
            or any(stage not in ROUTABLE_STAGES for stage in published_stage_ids[1:])
            or published_stage_ids[1:] != sorted(
                published_stage_ids[1:], key=list(ROUTABLE_STAGES).index
            )
        ):
            raise BinderLaneError(
                "published workflow bounded_stage_ids must start with target and contain an ordered stage subset"
            )
        if workspace_root is not None:
            workflow_path = contained_path(workspace_root, workflow_reference_ref, "published workflow reference", must_exist=True)
            workflow = _require_public_document(read_json(workflow_path), "published workflow reference")
            _require_exact_keys(
                workflow,
                {
                    "schema_version",
                    "reference_id",
                    "primary_report",
                    "public_dataset",
                    "public_dataset_revision",
                    "bounded_stage_ids",
                    "contract_categories",
                    "published_tool_cohort",
                    "replay_policy",
                    "published_result_values_imported",
                    "boundary",
                },
                "published workflow reference",
            )
            if workflow.get("schema_version") != "structure-factory-published-binder-workflow-reference-v1" or workflow.get("published_result_values_imported") is not False:
                raise BinderLaneError("published workflow reference has an invalid boundary")
            if (
                not isinstance(workflow.get("reference_id"), str)
                or SAFE_ID_RE.fullmatch(workflow["reference_id"]) is None
                or not isinstance(workflow.get("primary_report"), str)
                or not workflow["primary_report"].startswith("https://")
                or not isinstance(workflow.get("public_dataset"), str)
                or not workflow["public_dataset"].startswith("https://")
                or not isinstance(workflow.get("public_dataset_revision"), str)
                or re.fullmatch(r"[0-9a-f]{40}", workflow["public_dataset_revision"]) is None
                or workflow.get("bounded_stage_ids") != ["target", *ROUTABLE_STAGES]
                or not isinstance(workflow.get("contract_categories"), list)
                or not workflow["contract_categories"]
                or not all(isinstance(item, str) and item.strip() for item in workflow["contract_categories"])
                or not isinstance(workflow.get("published_tool_cohort"), dict)
                or not workflow["published_tool_cohort"]
                or not isinstance(workflow.get("replay_policy"), dict)
                or not {"exact_stack", "deliberate_swap", "runtime_binding"}.issubset(workflow["replay_policy"])
                or not all(
                    isinstance(value, str) and value.strip()
                    for value in workflow["replay_policy"].values()
                )
                or not isinstance(workflow.get("boundary"), str)
                or not workflow["boundary"].strip()
            ):
                raise BinderLaneError("published workflow reference fields are invalid")
            workflow_reference_sha256 = sha256_path(workflow_path)
    elif workflow_request is not None:
        raise BinderLaneError("published_workflow is only valid for the published comparison shape")
    comparison_policy = request.get("comparison_policy")
    if not isinstance(comparison_policy, dict):
        raise BinderLaneError("request comparison_policy must be an object")
    _require_exact_keys(
        comparison_policy,
        {"mode", "cross_arm_ranking", "metrics", "tie_break"},
        "comparison_policy",
    )
    comparison_mode = comparison_policy.get("mode")
    cross_arm_ranking = comparison_policy.get("cross_arm_ranking")
    if comparison_mode not in {"controlled_generation", "exploratory_full_stack"}:
        raise BinderLaneError("comparison_policy mode is not supported")
    if cross_arm_ranking not in {"shared_metrics_only", "not_permitted"}:
        raise BinderLaneError("comparison_policy cross_arm_ranking is not supported")
    if comparison_mode == "exploratory_full_stack" and cross_arm_ranking != "not_permitted":
        raise BinderLaneError("exploratory full-stack comparisons must not rank across arms")
    metrics = comparison_policy.get("metrics")
    if not isinstance(metrics, list) or not metrics:
        raise BinderLaneError("comparison_policy metrics must be a non-empty list")
    metric_ids: list[str] = []
    metric_directions: dict[str, str] = {}
    for index, metric in enumerate(metrics):
        if not isinstance(metric, dict):
            raise BinderLaneError(f"comparison metric {index} must be an object")
        _require_exact_keys(metric, {"id", "direction", "unit", "missing_value_policy"}, f"comparison metric {index}")
        metric_id = metric.get("id")
        if not isinstance(metric_id, str) or SAFE_ID_RE.fullmatch(metric_id) is None or metric_id in metric_ids:
            raise BinderLaneError(f"comparison metric {index} has an invalid or duplicate id")
        if metric.get("direction") not in {"higher_is_better", "lower_is_better"}:
            raise BinderLaneError(f"comparison metric {index} has an invalid direction")
        if metric.get("unit") not in {"unitless_proxy", "angstrom", "probability", "score"}:
            raise BinderLaneError(f"comparison metric {index} has an unsupported unit")
        if metric.get("missing_value_policy") != "preserve_as_failure":
            raise BinderLaneError(f"comparison metric {index} must preserve missing values as failures")
        metric_ids.append(metric_id)
        metric_directions[metric_id] = metric["direction"]
    tie_break = comparison_policy.get("tie_break")
    if not isinstance(tie_break, list) or not tie_break or tie_break[-1] != "candidate_id":
        raise BinderLaneError("comparison_policy tie_break must end with candidate_id")
    if len(tie_break) != len(set(tie_break)) or any(item != "candidate_id" and item not in metric_ids for item in tie_break):
        raise BinderLaneError("comparison_policy tie_break names unknown or duplicate fields")
    try:
        target = binder_target.normalize_target_contract(request.get("target"), "request target")
    except binder_target.BinderTargetError as exc:
        raise BinderLaneError(str(exc)) from exc
    if (
        target.get("input_posture") not in {"public_reference", "synthetic"}
        or not all(
            isinstance(target.get(key), str) and target[key].strip()
            for key in ("label", "public_accession", "window")
        )
    ):
        raise BinderLaneError(
            "request target needs a public or synthetic input posture, label, accession, window, and site"
        )
    require_public_prose(target["label"], "target label")
    require_public_prose(target["window"], "target window")
    if target["input_posture"] == "public_reference" and PUBLIC_ACCESSION_RE.fullmatch(target["public_accession"]) is None:
        raise BinderLaneError("public target accession must use a supported public namespace")
    if target["input_posture"] == "synthetic" and not target["public_accession"].startswith("SYNTHETIC:"):
        raise BinderLaneError("synthetic target accession must use the SYNTHETIC namespace")
    rows = {tool["id"]: tool for tool in ledger["tools"]}
    toolchains = request.get("toolchains")
    if not isinstance(toolchains, list) or not toolchains:
        raise BinderLaneError("request toolchains must be a non-empty list")
    if study_template == "single-arm-replay" and len(toolchains) != 1:
        raise BinderLaneError("single-arm-replay requires exactly one toolchain")
    if study_template in {"published-binder-comparison-shape", "toolchain-comparison"} and len(toolchains) < 2:
        raise BinderLaneError("comparison study templates require at least two toolchains")
    normalized_toolchains: list[dict[str, Any]] = []
    selected_rows: list[dict[str, Any]] = []
    arm_ids: set[str] = set()
    for index, arm in enumerate(toolchains):
        if not isinstance(arm, dict):
            raise BinderLaneError(f"toolchain {index} must be an object")
        _require_exact_keys(
            arm,
            {"id", "label", "candidate_count", "generator", "sequence_designer", "predictors", "scorers", "filters"},
            f"toolchain {index}",
        )
        arm_id = arm.get("id")
        if not isinstance(arm_id, str) or SAFE_ID_RE.fullmatch(arm_id) is None or arm_id in arm_ids:
            raise BinderLaneError(f"toolchain {index} has an invalid or duplicate id")
        arm_ids.add(arm_id)
        if not isinstance(arm.get("label"), str) or not arm["label"].strip():
            raise BinderLaneError(f"toolchain {arm_id} needs a label")
        require_public_prose(arm["label"], f"toolchain {arm_id} label")
        generator_id, generator_variant = _request_selection(
            arm.get("generator"), f"toolchain {arm_id} generator"
        )
        designer_id, designer_variant = _request_selection(
            arm.get("sequence_designer"), f"toolchain {arm_id} sequence_designer"
        )
        generator = _require_tool(rows, generator_id, "generator")
        designer = _require_tool(rows, designer_id, "sequence_designer")
        predictors = arm.get("predictors")
        scorers = arm.get("scorers")
        filters = arm.get("filters")
        if not isinstance(predictors, list) or not predictors:
            raise BinderLaneError(f"toolchain {arm_id} needs unique predictors")
        if not isinstance(scorers, list) or not scorers:
            raise BinderLaneError(f"toolchain {arm_id} needs unique scorers")
        if not isinstance(filters, list) or not filters or len(filters) != len(set(filters)):
            raise BinderLaneError(f"toolchain {arm_id} needs unique filters")
        predictor_selections = [
            _request_selection(item, f"toolchain {arm_id} predictor") for item in predictors
        ]
        scorer_selections = [
            _request_selection(item, f"toolchain {arm_id} scorer") for item in scorers
        ]
        if len(predictor_selections) != len(set(predictor_selections)):
            raise BinderLaneError(f"toolchain {arm_id} needs unique predictors")
        if len(scorer_selections) != len(set(scorer_selections)):
            raise BinderLaneError(f"toolchain {arm_id} needs unique scorers")
        predictor_rows = [_require_tool(rows, item[0], "predictor") for item in predictor_selections]
        scorer_rows = [_require_tool(rows, item[0], "scorer") for item in scorer_selections]
        filter_rows = [_require_tool(rows, item, "filter") for item in filters]
        candidate_count = arm.get("candidate_count")
        if not isinstance(candidate_count, int) or isinstance(candidate_count, bool) or not 1 <= candidate_count <= 10000:
            raise BinderLaneError(f"toolchain {arm_id} candidate_count must be between 1 and 10000")
        selected_rows.extend([generator, designer, *predictor_rows, *scorer_rows, *filter_rows])
        normalized_toolchains.append(
            {
                "id": arm_id,
                "label": arm.get("label", arm_id),
                "candidate_count": candidate_count,
                "generator": _selection_record(generator, generator_variant),
                "sequence_designer": _selection_record(designer, designer_variant),
                "predictors": [
                    _selection_record(row, selection[1])
                    for row, selection in zip(predictor_rows, predictor_selections)
                ],
                "scorers": [
                    _selection_record(row, selection[1])
                    for row, selection in zip(scorer_rows, scorer_selections)
                ],
                "filters": [_selection_record(row) for row in filter_rows],
            }
        )
    if (
        study_template in {"published-binder-comparison-shape", "toolchain-comparison"}
        and comparison_mode == "controlled_generation"
    ):
        comparison_shapes = {
            (
                arm["candidate_count"],
                tuple(_selection_identity(row) for row in arm["predictors"]),
                tuple(_selection_identity(row) for row in arm["scorers"]),
                tuple(row["tool_id"] for row in arm["filters"]),
            )
            for arm in normalized_toolchains
        }
        if len(comparison_shapes) != 1:
            raise BinderLaneError("controlled generation comparisons must share candidate count, predictors, scorers, and filters")
    workflow_strategy = _validate_workflow_strategy(
        request.get("workflow_strategy"),
        study_template,
        arm_ids,
    )
    _validate_published_identity_strategy(
        workflow_strategy,
        normalized_toolchains,
        published_stage_ids,
        workflow,
    )
    constraints = request.get("constraints")
    if not isinstance(constraints, dict):
        raise BinderLaneError("request constraints must be an object")
    _require_exact_keys(
        constraints,
        {
            "objective",
            "target_selection_method",
            "binder_length",
            "required_controls",
            "inclusion_rules",
            "exclusion_rules",
            "interpretation_limit",
            "preserve_failure_rows",
            "top_per_arm",
        },
        "request constraints",
    )
    for field in ("objective", "target_selection_method", "interpretation_limit"):
        require_public_prose(constraints.get(field), f"constraints {field}")
    for field in ("inclusion_rules", "exclusion_rules"):
        values = constraints.get(field)
        if not isinstance(values, list) or not values or not all(isinstance(item, str) and item.strip() for item in values):
            raise BinderLaneError(f"constraints {field} must be a non-empty string list")
        for item in values:
            require_public_prose(item, f"constraints {field}")
    binder_length = constraints.get("binder_length")
    if not isinstance(binder_length, dict):
        raise BinderLaneError("constraints binder_length must be an object")
    _require_exact_keys(binder_length, {"minimum", "maximum"}, "constraints binder_length")
    minimum = binder_length.get("minimum")
    maximum = binder_length.get("maximum")
    if not all(isinstance(value, int) and not isinstance(value, bool) for value in (minimum, maximum)) or not 10 <= minimum <= maximum <= 1000:
        raise BinderLaneError("binder length must satisfy 10 <= minimum <= maximum <= 1000")
    if constraints.get("preserve_failure_rows") is not True:
        raise BinderLaneError("constraints preserve_failure_rows must be true")
    top_per_arm = constraints.get("top_per_arm")
    if not isinstance(top_per_arm, int) or isinstance(top_per_arm, bool) or top_per_arm < 1 or any(top_per_arm > arm["candidate_count"] for arm in normalized_toolchains):
        raise BinderLaneError("constraints top_per_arm must fit every toolchain")
    controls = constraints.get("required_controls")
    if (
        not isinstance(controls, list)
        or not controls
        or not all(isinstance(item, str) and SAFE_ID_RE.fullmatch(item) is not None for item in controls)
        or len(controls) != len(set(controls))
    ):
        raise BinderLaneError("constraints required_controls must be a non-empty unique string list")
    license_policy = request.get("license_policy")
    if not isinstance(license_policy, dict) or license_policy.get("require_operator_review_for_gated") is not True:
        raise BinderLaneError("license_policy must require operator review for gated tools")
    _require_exact_keys(
        license_policy,
        {"allowed_gates", "blocked_tools", "require_operator_review_for_gated", "review_dimensions", "use_context"},
        "license_policy",
    )
    allowed_gates = license_policy.get("allowed_gates")
    blocked_tools = license_policy.get("blocked_tools")
    if not isinstance(allowed_gates, list) or not all(isinstance(item, str) for item in allowed_gates):
        raise BinderLaneError("license_policy allowed_gates must be a string list")
    if not isinstance(blocked_tools, list) or not all(isinstance(item, str) for item in blocked_tools):
        raise BinderLaneError("license_policy blocked_tools must be a string list")
    if len(allowed_gates) != len(set(allowed_gates)) or len(blocked_tools) != len(set(blocked_tools)):
        raise BinderLaneError("license_policy lists must not contain duplicates")
    known_gates = {row["license_gate"] for row in ledger["tools"]}
    if not set(allowed_gates).issubset(known_gates):
        raise BinderLaneError("license_policy allowed_gates contains an unknown gate")
    if not set(blocked_tools).issubset(rows):
        raise BinderLaneError("license_policy blocked_tools contains an unknown tool")
    if license_policy.get("use_context") not in {
        "personal",
        "academic_noncommercial",
        "research_evaluation",
        "institutional",
        "commercial",
    }:
        raise BinderLaneError("license_policy use_context is not supported")
    review_dimensions = license_policy.get("review_dimensions")
    expected_dimensions = {"code", "weights", "dependencies", "api_terms", "redistribution"}
    if (
        not isinstance(review_dimensions, dict)
        or set(review_dimensions) != expected_dimensions
        or any(value not in {"review_required", "not_applicable"} for value in review_dimensions.values())
    ):
        raise BinderLaneError("license_policy review_dimensions must cover code, weights, dependencies, api_terms, and redistribution")
    selected_ids = {row["id"] for row in selected_rows}
    denied = selected_ids.intersection(blocked_tools)
    if denied:
        raise BinderLaneError("selected tools are blocked by license_policy: " + ", ".join(sorted(denied)))
    disallowed_gates = {row["license_gate"] for row in selected_rows if row["license_gate"] not in allowed_gates}
    if disallowed_gates:
        raise BinderLaneError("selected tools require license gates not allowed by policy: " + ", ".join(sorted(disallowed_gates)))
    execution_policy, routes = _validate_routes(request.get("execution_policy"), workspace_root, arm_ids)
    optimization_policy = _validate_optimization_policy(
        request.get("optimization_policy"),
        metric_directions,
        normalized_toolchains,
        execution_policy,
    )
    fixture = request.get("synthetic_fixture")
    fixture_sha256: str | None = None
    if request["result_boundary"] == "public_synthetic_demo":
        safe_relative_path(fixture, "request synthetic_fixture")
        if workspace_root is not None:
            fixture_path = contained_path(workspace_root, fixture, "synthetic fixture", must_exist=True)
            _synthetic_candidates(read_json(fixture_path))
            fixture_sha256 = sha256_path(fixture_path)
    elif fixture is not None:
        raise BinderLaneError("planning requests must not name a synthetic fixture")
    return {
        "schema_version": PLAN_SCHEMA,
        "request_ref": request_ref,
        "request_sha256": (
            sha256_path(contained_path(workspace_root, request_ref, "request reference", must_exist=True))
            if workspace_root is not None and request_ref is not None
            else sha256_json(request)
        ),
        "capability_ledger_ref": ledger_ref,
        "capability_ledger_sha256": (
            sha256_path(contained_path(workspace_root, ledger_ref, "capability ledger reference", must_exist=True))
            if workspace_root is not None and ledger_ref is not None
            else sha256_json(ledger)
        ),
        "workflow_reference_ref": workflow_reference_ref,
        "workflow_reference_sha256": workflow_reference_sha256,
        "published_stage_ids": published_stage_ids,
        "round_id": round_id,
        "study_template": study_template,
        "workflow_strategy": workflow_strategy,
        "comparison_policy": comparison_policy,
        "optimization_policy": optimization_policy,
        "target": target,
        "source_posture": request["source_posture"],
        "result_boundary": request["result_boundary"],
        "toolchains": normalized_toolchains,
        "constraints": constraints,
        "license_policy": {**license_policy, "review_status": "not_recorded", "allowed_gates_are_not_acceptance": True},
        "execution_policy": execution_policy,
        "synthetic_fixture": fixture,
        "synthetic_fixture_sha256": fixture_sha256,
        "execution": {
            "mode": "public_synthetic_only" if request["result_boundary"] == "public_synthetic_demo" else "planning_and_handoff",
            "provider_calls": 0,
            "adapter_execution_supported": True,
            "adapter_execution_authorization": "explicit_runtime_authorization_required",
            "handoff_generation_supported": True,
        },
        "operator_gates": [
            "Review current tool terms before execution.",
            "Use the selected provider profile or a validated runtime adapter.",
            "Keep credentials and live provider identifiers in runtime state.",
        ],
    }


def validate_plan(plan: Any, workspace_root: Path | None = None) -> dict[str, Any]:
    plan = _require_public_document(plan, "plan")
    _require_exact_keys(
        plan,
        {
            "schema_version",
            "request_ref",
            "request_sha256",
            "capability_ledger_ref",
            "capability_ledger_sha256",
            "workflow_reference_ref",
            "workflow_reference_sha256",
            "published_stage_ids",
            "round_id",
            "study_template",
            "workflow_strategy",
            "comparison_policy",
            "optimization_policy",
            "target",
            "source_posture",
            "result_boundary",
            "toolchains",
            "constraints",
            "license_policy",
            "execution_policy",
            "synthetic_fixture",
            "synthetic_fixture_sha256",
            "execution",
            "operator_gates",
        },
        "plan",
    )
    if plan.get("schema_version") != PLAN_SCHEMA:
        raise BinderLaneError(f"plan schema_version must be {PLAN_SCHEMA}")
    published_stage_ids = plan.get("published_stage_ids")
    if plan.get("study_template") == "published-binder-comparison-shape":
        if (
            not isinstance(published_stage_ids, list)
            or len(published_stage_ids) < 2
            or published_stage_ids[0] != "target"
            or len(published_stage_ids) != len(set(published_stage_ids))
            or any(stage not in ROUTABLE_STAGES for stage in published_stage_ids[1:])
            or published_stage_ids[1:] != sorted(
                published_stage_ids[1:], key=list(ROUTABLE_STAGES).index
            )
        ):
            raise BinderLaneError("plan published_stage_ids are invalid")
    elif published_stage_ids != []:
        raise BinderLaneError("nonpublished plans must not declare published_stage_ids")
    if plan.get("source_posture") not in PUBLIC_SOURCE_POSTURES or plan.get("result_boundary") not in {"planning", "public_synthetic_demo"}:
        raise BinderLaneError("plan source posture or result boundary is invalid")
    try:
        normalized_target = binder_target.normalize_target_contract(
            plan.get("target"), "plan target"
        )
    except binder_target.BinderTargetError as exc:
        raise BinderLaneError(str(exc)) from exc
    if plan.get("target") != normalized_target:
        raise BinderLaneError(
            "plan target site must contain normalized, unique residue labels"
        )
    require_public_prose(normalized_target["label"], "target label")
    require_public_prose(normalized_target["window"], "target window")
    if (
        normalized_target["input_posture"] == "public_reference"
        and PUBLIC_ACCESSION_RE.fullmatch(normalized_target["public_accession"]) is None
    ):
        raise BinderLaneError("public target accession must use a supported public namespace")
    if (
        normalized_target["input_posture"] == "synthetic"
        and not normalized_target["public_accession"].startswith("SYNTHETIC:")
    ):
        raise BinderLaneError("synthetic target accession must use the SYNTHETIC namespace")
    expected_mode = "public_synthetic_only" if plan["result_boundary"] == "public_synthetic_demo" else "planning_and_handoff"
    if plan.get("execution") != {
        "mode": expected_mode,
        "provider_calls": 0,
        "adapter_execution_supported": True,
        "adapter_execution_authorization": "explicit_runtime_authorization_required",
        "handoff_generation_supported": True,
    }:
        raise BinderLaneError("plan execution boundary is invalid")
    if plan.get("license_policy", {}).get("review_status") != "not_recorded" or plan["license_policy"].get("allowed_gates_are_not_acceptance") is not True:
        raise BinderLaneError("plan must not record license acceptance")
    comparison_policy = plan.get("comparison_policy")
    toolchains = plan.get("toolchains")
    execution_policy = plan.get("execution_policy")
    if not isinstance(comparison_policy, dict) or not isinstance(toolchains, list) or not isinstance(execution_policy, dict):
        raise BinderLaneError("plan optimization inputs are invalid")
    if execution_policy.get("authorization") != "plan_then_explicit_runtime_authorization":
        raise BinderLaneError("plan execution authorization is invalid")
    routes = execution_policy.get("routes")
    if not isinstance(routes, list) or not routes:
        raise BinderLaneError("plan execution routes are invalid")
    for route in routes:
        if (
            not isinstance(route, dict)
            or route.get("backend") not in BACKENDS
            or route.get("execution_method")
            not in ROUTE_EXECUTION_METHODS_BY_BACKEND[route.get("backend")]
            or not isinstance(route.get("operator_adapter_required"), bool)
            or not isinstance(route.get("operator_gate_required"), bool)
            or (
                route.get("execution_method") == "platform_skill"
                and (
                    not isinstance(route.get("platform_skill_id"), str)
                    or PLATFORM_SKILL_REF_RE.fullmatch(route["platform_skill_id"]) is None
                )
            )
            or (
                route.get("execution_method") != "platform_skill"
                and "platform_skill_id" in route
            )
        ):
            raise BinderLaneError("plan execution route is invalid")
    comparison_metrics = comparison_policy.get("metrics")
    if not isinstance(comparison_metrics, list):
        raise BinderLaneError("plan comparison_policy metrics are invalid")
    metric_directions = {
        item.get("id"): item.get("direction")
        for item in comparison_metrics
        if isinstance(item, dict) and isinstance(item.get("id"), str) and isinstance(item.get("direction"), str)
    }
    if not metric_directions or any(direction not in {"higher_is_better", "lower_is_better"} for direction in metric_directions.values()):
        raise BinderLaneError("plan comparison metric directions are invalid")
    toolchain_ids = {
        item.get("id") for item in toolchains if isinstance(item, dict) and isinstance(item.get("id"), str)
    }
    if len(toolchain_ids) != len(toolchains) or plan.get("workflow_strategy") != _validate_workflow_strategy(
        plan.get("workflow_strategy"),
        plan.get("study_template"),
        toolchain_ids,
    ):
        raise BinderLaneError("plan workflow_strategy is invalid")
    if plan.get("optimization_policy") != _validate_optimization_policy(
        plan.get("optimization_policy"),
        metric_directions,
        toolchains,
        execution_policy,
    ):
        raise BinderLaneError("plan optimization_policy is invalid")
    if workspace_root is not None:
        for ref_key, hash_key, label in (
            ("request_ref", "request_sha256", "request reference"),
            ("capability_ledger_ref", "capability_ledger_sha256", "capability ledger reference"),
            ("workflow_reference_ref", "workflow_reference_sha256", "workflow reference"),
        ):
            ref = plan.get(ref_key)
            if ref is not None:
                path = contained_path(workspace_root, ref, label, must_exist=True)
                if sha256_path(path) != plan.get(hash_key):
                    raise BinderLaneError(f"{label} hash changed")
        for route in plan.get("execution_policy", {}).get("routes", []):
            if route.get("profile_ref") is not None:
                profile = contained_path(workspace_root, route["profile_ref"], "provider profile", must_exist=True)
                if sha256_path(profile) != route.get("profile_sha256"):
                    raise BinderLaneError("provider profile hash changed")
            if route.get("backend") == "api":
                adapter = contained_path(workspace_root, route["adapter_contract_ref"], "api adapter contract", must_exist=True)
                if sha256_path(adapter) != route.get("adapter_contract_sha256"):
                    raise BinderLaneError("api adapter contract hash changed")
        if plan.get("synthetic_fixture") is not None:
            fixture = contained_path(workspace_root, plan["synthetic_fixture"], "synthetic fixture", must_exist=True)
            if sha256_path(fixture) != plan.get("synthetic_fixture_sha256"):
                raise BinderLaneError("synthetic fixture hash changed")
        if plan.get("request_ref") is not None and plan.get("capability_ledger_ref") is not None:
            expected = plan_request(
                read_json(contained_path(workspace_root, plan["request_ref"], "request reference", must_exist=True)),
                read_json(
                    contained_path(
                        workspace_root,
                        plan["capability_ledger_ref"],
                        "capability ledger reference",
                        must_exist=True,
                    )
                ),
                workspace_root,
                request_ref=plan["request_ref"],
                ledger_ref=plan["capability_ledger_ref"],
            )
            if plan != expected:
                raise BinderLaneError("plan differs from its hash-bound request and capability ledger")
    return plan


def _handoff_selection(selection: dict[str, Any]) -> dict[str, str | None]:
    return {
        "tool_id": selection["tool_id"],
        "variant_id": selection.get("variant_id"),
    }


def _tools_for_stage(toolchain: dict[str, Any], stage: str) -> list[dict[str, str | None]]:
    if stage == "generation":
        return [_handoff_selection(toolchain["generator"])]
    if stage == "sequence_design":
        return [_handoff_selection(toolchain["sequence_designer"])]
    if stage == "cofold":
        return [_handoff_selection(row) for row in toolchain["predictors"]]
    if stage == "scoring":
        return [_handoff_selection(row) for row in toolchain["scorers"]]
    if stage == "filter":
        return [_handoff_selection(row) for row in toolchain["filters"]]
    return []


def _candidate_counts_per_round(plan: dict[str, Any]) -> dict[str, int]:
    return {toolchain["id"]: toolchain["candidate_count"] for toolchain in plan["toolchains"]}


def execution_handoff(plan: Any, plan_sha256: str | None = None) -> dict[str, Any]:
    plan = validate_plan(plan)
    packages = []
    toolchains = {arm["id"]: arm for arm in plan["toolchains"]}
    round_index = plan["optimization_policy"]["current_round_index"]
    for route in plan["execution_policy"]["routes"]:
        for stage in route["stages"]:
            packages.append(
                {
                    "package_id": f"{route['id']}.{stage}",
                    "round_index": round_index,
                    "stage": stage,
                    "route_id": route["id"],
                    "toolchain_ids": route["toolchain_ids"],
                    "tools_by_toolchain": {
                        toolchain_id: _tools_for_stage(toolchains[toolchain_id], stage)
                        for toolchain_id in route["toolchain_ids"]
                    },
                    "backend": route["backend"],
                    "execution_method": route["execution_method"],
                    **(
                        {"platform_skill_id": route["platform_skill_id"]}
                        if route["execution_method"] == "platform_skill"
                        else {}
                    ),
                    "profile_ref": route["profile_ref"],
                    "profile_sha256": route.get("profile_sha256"),
                    "operator_adapter_required": route["operator_adapter_required"],
                    "operator_gate_required": route["operator_gate_required"],
                    "authorization": "required_at_execution",
                    "authorization_action": (
                        "authorize_local_adapter_execution"
                        if route["backend"] == "local"
                        else "authorize_external_or_provider_dispatch"
                    ),
                    "license_review_status": "not_recorded",
                    "execution_state": "not_executed",
                    "input_contract_ids": [f"binder-round.{stage}.input.v1"],
                    "output_contract_ids": [f"binder-round.{stage}.output.v1"],
                    "expected_record_counts_by_toolchain": {
                        toolchain_id: _candidate_counts_per_round(plan)[toolchain_id]
                        for toolchain_id in route["toolchain_ids"]
                    },
                    "transfer": {
                        "data_class": "public_or_synthetic_only",
                        "source_package_ids": [],
                        "destination_package_id": f"{route['id']}.{stage}",
                        "credentials_embedded": False,
                    },
                    "required_closeout": [
                        "stage_event",
                        "output_count",
                        "artifact_hashes",
                        "validation_notes",
                        "failure_rows",
                        "cleanup_result",
                    ],
                    "closeout_contract": {
                        "failure_rows": "one_row_per_failed_or_missing_candidate",
                        "cleanup_result": (
                            "not_applicable_for_local"
                            if route["backend"] == "local"
                            else "required_for_external_or_provider_dispatch"
                        ),
                    },
                    **(
                        {
                            "adapter_contract_ref": route["adapter_contract_ref"],
                            "adapter_contract_sha256": route.get("adapter_contract_sha256"),
                            "api_policy": route["api_policy"],
                        }
                        if route["backend"] == "api"
                        else {}
                    ),
                }
            )
    package_for_work: dict[tuple[str, str], str] = {}
    for package in packages:
        for toolchain_id in package["toolchain_ids"]:
            package_for_work[(toolchain_id, package["stage"])] = package["package_id"]
    stage_order = list(ROUTABLE_STAGES)
    for package in packages:
        stage_index = stage_order.index(package["stage"])
        dependencies = (
            []
            if stage_index == 0
            else sorted(
                {
                    package_for_work[(toolchain_id, stage_order[stage_index - 1])]
                    for toolchain_id in package["toolchain_ids"]
                }
            )
        )
        package["depends_on_package_ids"] = dependencies
        package["transfer"]["source_package_ids"] = dependencies
    return {
        "schema_version": "structure-factory-binder-execution-handoff-v1",
        "round_id": plan["round_id"],
        "plan_sha256": plan_sha256,
        "topology": plan["execution_policy"]["topology"],
        "optimization_horizon": {
            "current_round_index": round_index,
            "maximum_round_count": plan["optimization_policy"]["round_count"],
            "primary_metric_id": plan["optimization_policy"]["primary_metric_id"],
            "stopping_rule": plan["optimization_policy"]["stopping_rule"],
            "current_round_budget_usd": plan["optimization_policy"]["round_budget_usd"][round_index - 1],
            "later_round_state": "conditional_on_stopping_rule",
        },
        "provider_calls": 0,
        "credentials_embedded": False,
        "concrete_provider_resources_embedded": False,
        "packages": packages,
        "launch_boundary": "Generating this handoff makes no provider calls. Dry-run each adapter, then run it only after the user or operator grants explicit runtime authorization and completes the listed reviews.",
    }


def round_contract(plan: Any, plan_sha256: str | None = None) -> dict[str, Any]:
    plan = validate_plan(plan)
    stages = [
        ("target", "target-contract.json"),
        ("generation", "generation-status.json"),
        ("sequence_design", "sequence-design-status.json"),
        ("cofold", "cofold-status.json"),
        ("scoring", "scoring-status.json"),
        ("filter", "filter-status.json"),
        ("report", "round-report.json"),
    ]
    candidate_counts = _candidate_counts_per_round(plan)
    round_index = plan["optimization_policy"]["current_round_index"]
    return {
        "schema_version": CONTRACT_SCHEMA,
        "round_id": plan["round_id"],
        "plan_sha256": plan_sha256,
        "execution_mode": plan["execution"]["mode"],
        "provider_calls": 0,
        "fail_closed": True,
        "toolchain_count": len(plan["toolchains"]),
        "planned_candidate_count": sum(candidate_counts.values()),
        "optimization_horizon": {
            "current_round_index": round_index,
            "maximum_round_count": plan["optimization_policy"]["round_count"],
            "primary_metric_id": plan["optimization_policy"]["primary_metric_id"],
            "stopping_rule": plan["optimization_policy"]["stopping_rule"],
            "current_round_budget_usd": plan["optimization_policy"]["round_budget_usd"][round_index - 1],
            "later_round_state": "conditional_on_stopping_rule",
        },
        "completion_rule": "Complete only when every expected artifact exists, per-toolchain record counts match, and every artifact SHA-256 is recorded.",
        "stages": [
            {
                "id": stage_id,
                "expected_artifacts": [artifact],
                "minimum_output_count": 1,
                "expected_record_counts_by_toolchain": (
                    {arm_id: 1 for arm_id in candidate_counts}
                    if stage_id == "target"
                    else candidate_counts
                ),
            }
            for stage_id, artifact in stages
        ],
    }


def round_decision(plan: Any, history: Any) -> dict[str, Any]:
    """Evaluate the current round closeout against the budget and stopping rule."""
    plan = validate_plan(plan)
    if not isinstance(history, list) or not history:
        raise BinderLaneError("round decision history must contain the current round closeout")
    current_round_index = plan["optimization_policy"]["current_round_index"]
    if len(history) != current_round_index:
        raise BinderLaneError("round decision history must contain rounds 1 through current_round_index")
    metric_values: list[float] = []
    spend_values: list[float | None] = []
    metric_provenance: list[dict[str, Any]] = []
    for index, row in enumerate(history, start=1):
        if not isinstance(row, dict):
            raise BinderLaneError("round decision history rows must be objects")
        _require_exact_keys(
            row,
            {
                "round_index",
                "primary_metric_value",
                "actual_spend_usd",
                "closeout_complete",
                "metric_provenance",
            },
            f"round decision history row {index}",
        )
        if row.get("round_index") != index or row.get("closeout_complete") is not True:
            raise BinderLaneError("round decision history must be sequential and closed out")
        metric = row.get("primary_metric_value")
        if isinstance(metric, bool) or not isinstance(metric, (int, float)) or not math.isfinite(metric):
            raise BinderLaneError("round decision primary metric values must be finite numbers")
        spend = row.get("actual_spend_usd")
        if spend is not None and (
            isinstance(spend, bool) or not isinstance(spend, (int, float)) or not math.isfinite(spend) or spend < 0
        ):
            raise BinderLaneError("round decision actual spend values must be null or non-negative finite numbers")
        metric_values.append(float(metric))
        spend_values.append(None if spend is None else float(spend))
        provenance = row.get("metric_provenance")
        if not isinstance(provenance, dict):
            raise BinderLaneError("round decision metric_provenance must be an object")
        _require_exact_keys(
            provenance,
            {
                "metric_id",
                "metric_source",
                "source_artifact_sha256",
                "calibration_state",
                "calibration_scope_id",
                "calibration_artifact_sha256",
            },
            f"round decision history row {index} metric_provenance",
        )
        if provenance.get("metric_id") != plan["optimization_policy"]["primary_metric_id"]:
            raise BinderLaneError("round decision metric provenance must name the plan primary metric")
        source = provenance.get("metric_source")
        if source not in {"stage_closeout", "operator_supplied", "synthetic_fixture"}:
            raise BinderLaneError("round decision metric_source is not supported")
        source_digest = provenance.get("source_artifact_sha256")
        if source == "synthetic_fixture":
            if source_digest is not None:
                raise BinderLaneError("synthetic metric provenance must not claim a source artifact digest")
        elif not isinstance(source_digest, str) or SHA256_RE.fullmatch(source_digest) is None:
            raise BinderLaneError("measured metric provenance requires a source artifact SHA-256")
        calibration_state = provenance.get("calibration_state")
        if calibration_state not in {
            "calibrated",
            "borrowed",
            "operator_defined",
            "uncalibrated",
            "not_applicable",
        }:
            raise BinderLaneError("round decision calibration_state is not supported")
        scope_id = provenance.get("calibration_scope_id")
        if not isinstance(scope_id, str) or SAFE_ID_RE.fullmatch(scope_id) is None:
            raise BinderLaneError("round decision calibration_scope_id must be a stable public-safe ID")
        calibration_digest = provenance.get("calibration_artifact_sha256")
        if calibration_state in {"calibrated", "borrowed"}:
            if not isinstance(calibration_digest, str) or SHA256_RE.fullmatch(calibration_digest) is None:
                raise BinderLaneError("calibrated or borrowed metrics require a calibration artifact SHA-256")
        elif calibration_digest is not None:
            raise BinderLaneError("calibration artifact digest requires calibrated or borrowed state")
        if source == "synthetic_fixture" and calibration_state != "not_applicable":
            raise BinderLaneError("synthetic metric provenance must use not_applicable calibration state")
        metric_provenance.append(dict(provenance))
    first_provenance = metric_provenance[0]
    for provenance in metric_provenance[1:]:
        if any(
            provenance[field] != first_provenance[field]
            for field in ("metric_id", "calibration_state", "calibration_scope_id", "calibration_artifact_sha256")
        ):
            raise BinderLaneError("round decision history must use one comparable calibration scope")
    maximum_spend = plan["execution_policy"]["max_spend_usd"]
    if maximum_spend is None:
        if any(value is not None for value in spend_values):
            raise BinderLaneError("round decision spend values must be null when the plan has no spend ceiling")
        actual_spend: float | None = None
        remaining_budget: float | None = None
    else:
        if any(value is None for value in spend_values):
            raise BinderLaneError("round decision spend values are required when the plan has a spend ceiling")
        actual_spend = sum(value for value in spend_values if value is not None)
        remaining_budget = max(0.0, float(maximum_spend) - actual_spend)

    decision = "continue"
    reason = "stopping_rule_not_met"
    stopping_rule = plan["optimization_policy"]["stopping_rule"]
    direction = plan["optimization_policy"]["direction"]
    latest_metric = metric_values[-1]
    if stopping_rule["type"] == "target_threshold" and first_provenance["calibration_state"] in {
        "uncalibrated",
        "not_applicable",
    }:
        raise BinderLaneError(
            "target-threshold decisions require calibrated, borrowed, or operator-defined metric provenance"
        )
    if maximum_spend is not None and actual_spend is not None and actual_spend >= float(maximum_spend):
        decision = "stop"
        reason = "budget_ceiling_reached"
    elif stopping_rule["type"] == "target_threshold":
        threshold_met = (
            latest_metric >= stopping_rule["threshold"]
            if direction == "maximize"
            else latest_metric <= stopping_rule["threshold"]
        )
        if threshold_met:
            decision = "stop"
            reason = "target_threshold_reached"
    elif stopping_rule["type"] == "no_improvement" and len(metric_values) > 1:
        best = metric_values[0]
        stale_rounds = 0
        for metric in metric_values[1:]:
            delta = metric - best if direction == "maximize" else best - metric
            if delta >= stopping_rule["minimum_delta"]:
                best = metric
                stale_rounds = 0
            else:
                stale_rounds += 1
        if stale_rounds >= stopping_rule["patience_rounds"]:
            decision = "stop"
            reason = "no_improvement_patience_reached"
    maximum_round_count = plan["optimization_policy"]["round_count"]
    if decision == "continue" and current_round_index >= maximum_round_count:
        decision = "stop"
        reason = "maximum_round_count_reached"
    next_round_index = current_round_index + 1 if decision == "continue" else None
    next_round_budget = (
        plan["optimization_policy"]["round_budget_usd"][next_round_index - 1]
        if next_round_index is not None
        else None
    )
    if (
        decision == "continue"
        and remaining_budget is not None
        and next_round_budget is not None
        and next_round_budget > remaining_budget
    ):
        decision = "stop"
        reason = "insufficient_remaining_budget"
        next_round_index = None
        next_round_budget = None
    return {
        "schema_version": DECISION_SCHEMA,
        "round_id": plan["round_id"],
        "current_round_index": current_round_index,
        "history_round_count": len(history),
        "primary_metric_id": plan["optimization_policy"]["primary_metric_id"],
        "metric_source": metric_provenance[-1]["metric_source"],
        "metric_source_artifact_sha256": metric_provenance[-1]["source_artifact_sha256"],
        "calibration_state": first_provenance["calibration_state"],
        "calibration_scope_id": first_provenance["calibration_scope_id"],
        "calibration_artifact_sha256": first_provenance["calibration_artifact_sha256"],
        "latest_primary_metric_value": latest_metric,
        "actual_spend_usd": actual_spend,
        "remaining_budget_usd": remaining_budget,
        "decision": decision,
        "reason": reason,
        "next_round_index": next_round_index,
        "next_round_budget_usd": next_round_budget,
        "provider_calls": 0,
    }


def validate_round_contract(contract: Any, plan: dict[str, Any]) -> dict[str, Any]:
    contract = _require_public_document(contract, "round contract")
    _require_exact_keys(
        contract,
        {
            "schema_version",
            "round_id",
            "plan_sha256",
            "execution_mode",
            "provider_calls",
            "fail_closed",
            "toolchain_count",
            "planned_candidate_count",
            "optimization_horizon",
            "completion_rule",
            "stages",
        },
        "round contract",
    )
    if contract.get("schema_version") != CONTRACT_SCHEMA or contract.get("round_id") != plan["round_id"]:
        raise BinderLaneError("round contract identity is invalid")
    if contract.get("provider_calls") != 0 or contract.get("fail_closed") is not True:
        raise BinderLaneError("round contract execution boundary is invalid")
    if (
        contract.get("execution_mode") != plan["execution"]["mode"]
        or contract.get("toolchain_count") != len(plan["toolchains"])
        or contract.get("planned_candidate_count") != sum(_candidate_counts_per_round(plan).values())
    ):
        raise BinderLaneError("round contract counts or mode differ from the plan")
    if contract != round_contract(plan, contract.get("plan_sha256")):
        raise BinderLaneError("round contract differs from the plan-derived contract")
    stages = contract.get("stages")
    if not isinstance(stages, list) or [stage.get("id") for stage in stages if isinstance(stage, dict)] != ["target", *ROUTABLE_STAGES]:
        raise BinderLaneError("round contract stages are invalid")
    expected_counts = _candidate_counts_per_round(plan)
    for stage in stages:
        if set(stage) != {"id", "expected_artifacts", "minimum_output_count", "expected_record_counts_by_toolchain"}:
            raise BinderLaneError("round contract stage fields are invalid")
        expected = {arm_id: 1 for arm_id in expected_counts} if stage["id"] == "target" else expected_counts
        if stage["expected_record_counts_by_toolchain"] != expected:
            raise BinderLaneError("round contract per-toolchain counts are invalid")
    return contract


def validate_execution_handoff(handoff: Any, plan: dict[str, Any]) -> dict[str, Any]:
    handoff = _require_public_document(handoff, "execution handoff")
    _require_exact_keys(
        handoff,
        {
            "schema_version",
            "round_id",
            "plan_sha256",
            "topology",
            "optimization_horizon",
            "provider_calls",
            "credentials_embedded",
            "concrete_provider_resources_embedded",
            "packages",
            "launch_boundary",
        },
        "execution handoff",
    )
    if (
        handoff.get("schema_version") != "structure-factory-binder-execution-handoff-v1"
        or handoff.get("round_id") != plan["round_id"]
        or handoff.get("topology") != plan["execution_policy"]["topology"]
        or handoff.get("provider_calls") != 0
        or handoff.get("credentials_embedded") is not False
        or handoff.get("concrete_provider_resources_embedded") is not False
    ):
        raise BinderLaneError("execution handoff boundary is invalid")
    if handoff != execution_handoff(plan, handoff.get("plan_sha256")):
        raise BinderLaneError("execution handoff differs from the plan-derived handoff")
    return handoff


def materialize_plan(plan: Any, run_root: Path, workspace_root: Path) -> dict[str, Any]:
    plan = validate_plan(plan, workspace_root)
    if plan.get("request_ref") is None or plan.get("capability_ledger_ref") is None:
        raise BinderLaneError("materialization requires hash-bound request and capability-ledger references")
    run_root = require_runtime_root(workspace_root, run_root, must_exist=False)
    if run_root.exists() and any(run_root.iterdir()):
        raise BinderLaneError("run root must be absent or empty")
    run_root.mkdir(parents=True, exist_ok=True)
    write_json(run_root / "plan.json", plan)
    plan_sha256 = sha256_path(run_root / "plan.json")
    contract = round_contract(plan, plan_sha256)
    handoff = execution_handoff(plan, plan_sha256)
    write_json(run_root / "round-contract.json", contract)
    write_json(run_root / "execution-handoff.json", handoff)
    return {"ok": True, "files": ["plan.json", "round-contract.json", "execution-handoff.json"]}


def _artifact_hash_mismatches(run_root: Path, expected: set[str]) -> list[str]:
    hashes = _require_public_document(read_json(run_root / "artifact-hashes.json"), "artifact hashes")
    _require_exact_keys(hashes, {"schema_version", "artifacts"}, "artifact hashes")
    if hashes.get("schema_version") != "structure-factory-artifact-hashes-v1":
        raise BinderLaneError("artifact hash ledger has the wrong schema_version")
    rows = hashes.get("artifacts")
    if not isinstance(rows, list):
        raise BinderLaneError("artifact hash ledger needs an artifacts list")
    mismatches: list[str] = []
    recorded: list[str] = []
    for row in rows:
        if not isinstance(row, dict) or set(row) != {"path", "sha256"}:
            mismatches.append("invalid_hash_ledger_row")
            continue
        relative = row.get("path")
        digest = row.get("sha256")
        if not isinstance(relative, str) or not isinstance(digest, str) or re.fullmatch(r"[0-9a-f]{64}", digest) is None:
            mismatches.append("invalid_hash_ledger_row")
            continue
        recorded.append(relative)
        try:
            path = contained_path(run_root, relative, "hash-ledger path", must_exist=True)
        except BinderLaneError:
            mismatches.append("invalid_hash_ledger_path")
            continue
        if sha256_path(path) != digest:
            mismatches.append(relative)
    if len(recorded) != len(set(recorded)):
        mismatches.append("duplicate_hash_ledger_path")
    if set(recorded) != expected:
        mismatches.append("hash_ledger_coverage")
    return mismatches


def _preflight_findings(run_root: Path, workspace_root: Path) -> list[str]:
    findings: list[str] = []
    validated_plan: dict[str, Any] | None = None
    if run_root.is_symlink():
        findings.append("run root must not be a symlink")
        return findings
    for name, schema in (
        ("plan.json", PLAN_SCHEMA),
        ("round-contract.json", CONTRACT_SCHEMA),
        ("execution-handoff.json", "structure-factory-binder-execution-handoff-v1"),
    ):
        path = run_root / name
        if not path.is_file() or path.is_symlink():
            findings.append(f"missing regular file: {name}")
            continue
        try:
            payload = _require_public_document(read_json(path), name)
        except BinderLaneError as exc:
            findings.append(str(exc))
            continue
        if payload.get("schema_version") != schema:
            findings.append(f"{name} has the wrong schema_version")
    if not findings:
        try:
            validated_plan = validate_plan(read_json(run_root / "plan.json"), workspace_root)
            validate_round_contract(read_json(run_root / "round-contract.json"), validated_plan)
            validate_execution_handoff(read_json(run_root / "execution-handoff.json"), validated_plan)
        except BinderLaneError as exc:
            findings.append(str(exc))
    base_files = {"plan.json", "round-contract.json", "execution-handoff.json"}
    allowed_files = set(base_files)
    expected_artifacts: set[str] = set()
    generated_artifacts_present = False
    contract_path = run_root / "round-contract.json"
    if contract_path.is_file():
        try:
            expected_artifacts = {
                artifact
                for stage in read_json(contract_path).get("stages", [])
                for artifact in stage.get("expected_artifacts", [])
            }
        except (BinderLaneError, AttributeError, TypeError):
            expected_artifacts = set()
        generated_artifacts_present = (run_root / "artifact-hashes.json").exists() or any(
            (run_root / name).exists() for name in expected_artifacts
        )
        if generated_artifacts_present:
            allowed_files.update(expected_artifacts)
            allowed_files.add("artifact-hashes.json")
    for path in sorted(run_root.rglob("*")):
        if path.is_symlink():
            findings.append(f"symlink is forbidden: {path.relative_to(run_root).as_posix()}")
        elif path.is_file():
            relative = path.relative_to(run_root).as_posix()
            if relative not in allowed_files:
                findings.append("undeclared run artifact")
                continue
            try:
                _require_public_document(read_json(path), path.name)
            except BinderLaneError as exc:
                findings.append(str(exc))
            except (UnicodeDecodeError, OSError):
                findings.append(f"non-JSON or unreadable artifact: {path.relative_to(run_root).as_posix()}")
    if generated_artifacts_present:
        required_generated = expected_artifacts | {"artifact-hashes.json"}
        if any(not (run_root / name).is_file() for name in required_generated):
            findings.append("generated synthetic artifact set is incomplete")
        elif validated_plan is not None and validated_plan.get("result_boundary") == "public_synthetic_demo":
            try:
                fixture = contained_path(
                    workspace_root,
                    validated_plan["synthetic_fixture"],
                    "synthetic fixture",
                    must_exist=True,
                )
                candidates = _synthetic_candidates(read_json(fixture))
                counts = _candidate_counts_per_round(validated_plan)
                actual_counts = {arm_id: 0 for arm_id in counts}
                for candidate in candidates:
                    if candidate["toolchain_id"] not in actual_counts:
                        raise BinderLaneError("synthetic fixture names a toolchain outside the plan")
                    actual_counts[candidate["toolchain_id"]] += 1
                if actual_counts != counts:
                    raise BinderLaneError("synthetic fixture counts do not match planned toolchain counts")
                expected_payloads = _synthetic_stage_files(validated_plan, candidates, actual_counts)
                expected_payloads["round-report.json"] = _synthetic_report(validated_plan, candidates, actual_counts)
                for name, expected_payload in expected_payloads.items():
                    if read_json(run_root / name) != expected_payload:
                        findings.append(f"{name} differs from the plan-derived synthetic artifact")
                if _artifact_hash_mismatches(run_root, expected_artifacts):
                    findings.append("artifact hash ledger does not match the generated artifacts")
            except BinderLaneError as exc:
                findings.append(str(exc))
    return sorted(set(findings))


def preflight(run_root: Path, workspace_root: Path) -> dict[str, Any]:
    run_root = require_runtime_root(workspace_root, run_root, must_exist=True)
    findings = _preflight_findings(run_root, workspace_root)
    if not findings:
        plan_hash = sha256_path(run_root / "plan.json")
        for name in ("round-contract.json", "execution-handoff.json"):
            payload = read_json(run_root / name)
            if payload.get("plan_sha256") != plan_hash:
                findings.append(f"{name} is not bound to plan.json")
    return {
        "schema_version": "structure-factory-binder-round-preflight-v1",
        "ok": not findings,
        "provider_calls": 0,
        "checks": {
            "path_containment": not any("symlink" in item for item in findings),
            "public_fields": not any(
                "forbidden field" in item
                or "machine-local path" in item
                or "secret-shaped or private-network value" in item
                for item in findings
            ),
            "contracts_present": not any("missing regular file" in item for item in findings),
        },
        "findings": findings,
    }


def _synthetic_candidates(fixture: Any) -> list[dict[str, Any]]:
    fixture = _require_public_document(fixture, "synthetic fixture")
    _require_exact_keys(
        fixture,
        {
            "schema_version",
            "campaign_id",
            "result_boundary",
            "source_posture",
            "ranking_policy",
            "candidates",
            "boundaries",
        },
        "synthetic fixture",
    )
    if (
        fixture.get("schema_version") != "structure-factory-candidate-ranking-v1"
        or fixture.get("source_posture") != "synthetic_demo"
        or fixture.get("result_boundary") != "public_synthetic_demo"
    ):
        raise BinderLaneError("run accepts only the public synthetic candidate-ranking fixture")
    if not isinstance(fixture.get("campaign_id"), str) or SAFE_ID_RE.fullmatch(fixture["campaign_id"]) is None:
        raise BinderLaneError("synthetic fixture campaign_id is invalid")
    boundaries = fixture.get("boundaries")
    if not isinstance(boundaries, list) or not boundaries:
        raise BinderLaneError("synthetic fixture boundaries must be a non-empty list")
    for boundary in boundaries:
        require_public_prose(boundary, "synthetic fixture boundary")
    ranking_policy = fixture.get("ranking_policy")
    if not isinstance(ranking_policy, dict):
        raise BinderLaneError("synthetic fixture ranking_policy must be an object")
    _require_exact_keys(ranking_policy, {"primary", "secondary", "note"}, "synthetic fixture ranking_policy")
    if (
        ranking_policy.get("primary") != "cofold_confidence_proxy"
        or ranking_policy.get("secondary") != ["interface_confidence_proxy", "failure_status"]
        or not isinstance(ranking_policy.get("note"), str)
    ):
        raise BinderLaneError("synthetic fixture ranking policy is invalid")
    require_public_prose(ranking_policy["note"], "synthetic fixture ranking note")
    rows = fixture.get("candidates")
    if not isinstance(rows, list) or not rows:
        raise BinderLaneError("synthetic fixture needs candidate rows")
    sanitized: list[dict[str, Any]] = []
    seen_ids: set[str] = set()
    seen_ranks: set[tuple[str, int]] = set()
    for index, row in enumerate(rows):
        if not isinstance(row, dict):
            raise BinderLaneError(f"synthetic candidate {index} must be an object")
        _require_exact_keys(
            row,
            {
                "rank",
                "id",
                "toolchain_id",
                "source_posture",
                "result_boundary",
                "cofold_status",
                "scores",
                "artifact_refs",
            },
            f"synthetic candidate {index}",
        )
        candidate_id = row.get("id")
        toolchain_id = row.get("toolchain_id")
        if (
            not isinstance(candidate_id, str)
            or SAFE_ID_RE.fullmatch(candidate_id) is None
            or candidate_id in seen_ids
            or not isinstance(toolchain_id, str)
            or SAFE_ID_RE.fullmatch(toolchain_id) is None
        ):
            raise BinderLaneError(f"synthetic candidate {index} needs an id and toolchain_id")
        seen_ids.add(candidate_id)
        rank = row.get("rank")
        if not isinstance(rank, int) or isinstance(rank, bool) or rank < 1 or (toolchain_id, rank) in seen_ranks:
            raise BinderLaneError(f"synthetic candidate {index} has an invalid or duplicate rank")
        seen_ranks.add((toolchain_id, rank))
        if row.get("source_posture") != "synthetic_demo" or row.get("result_boundary") != "public_synthetic_demo":
            raise BinderLaneError(f"synthetic candidate {index} has an invalid public boundary")
        if row.get("cofold_status") not in {"completed", "failed", "not_executed"}:
            raise BinderLaneError(f"synthetic candidate {index} has an invalid status")
        scores = row.get("scores")
        if not isinstance(scores, dict):
            raise BinderLaneError(f"synthetic candidate {index} scores must be an object")
        _require_exact_keys(scores, {"cofold_confidence_proxy", "interface_confidence_proxy"}, f"synthetic candidate {index} scores")
        if any(
            value is not None
            and (
                isinstance(value, bool)
                or not isinstance(value, (int, float))
                or not math.isfinite(value)
            )
            for value in scores.values()
        ):
            raise BinderLaneError(f"synthetic candidate {index} scores must be numeric or null")
        if row.get("artifact_refs") != []:
            raise BinderLaneError(f"synthetic candidate {index} artifact_refs must be empty")
        sanitized.append(
            {
                "id": candidate_id,
                "toolchain_id": toolchain_id,
                "rank": rank,
                "status": row["cofold_status"],
                "scores": scores,
                "source_posture": "synthetic_demo",
                "result_boundary": "public_synthetic_demo",
                "artifact_refs": [],
            }
        )
    return sanitized


def _synthetic_report(
    plan: dict[str, Any],
    candidates: list[dict[str, Any]],
    counts_by_toolchain: dict[str, int],
) -> dict[str, Any]:
    marker = {"mode": "synthetic_fixture", "not_a_measurement": True}
    return {
        "schema_version": REPORT_SCHEMA,
        "report_kind": "synthetic_fixture",
        "comparison_interpretation": "not_evaluable",
        "round_id": plan["round_id"],
        "source_posture": "synthetic_demo",
        "result_boundary": "public_synthetic_demo",
        "execution": {
            "mode": "public_synthetic_only",
            "provider_calls": 0,
            "external_tool_invocations": 0,
            "network_calls": 0,
            "planned_topology": plan["execution_policy"]["topology"],
        },
        "construction": marker,
        "target": plan["target"],
        "toolchains": plan["toolchains"],
        "candidate_count": len(candidates),
        "toolchain_counts": counts_by_toolchain,
        "candidates": candidates,
        "claims": {
            "supported": ["The public fixture passed the binder-round contract."],
            "not_supported": ["binding", "function", "selectivity", "safety", "therapeutic value", "clinical relevance"],
        },
    }


def _synthetic_stage_files(
    plan: dict[str, Any],
    candidates: list[dict[str, Any]],
    counts_by_toolchain: dict[str, int],
) -> dict[str, dict[str, Any]]:
    marker = {"mode": "synthetic_fixture", "not_a_measurement": True}
    count = len(candidates)
    target_counts = {arm_id: 1 for arm_id in counts_by_toolchain}
    return {
        "target-contract.json": {
            "stage": "target",
            "status": "materialized",
            "target": plan["target"],
            "record_counts_by_toolchain": target_counts,
            "construction": marker,
        },
        **{
            filename: {
                "stage": stage,
                "status": "synthetic_fixture_only",
                "output_count": count,
                "record_counts_by_toolchain": counts_by_toolchain,
                "construction": marker,
            }
            for filename, stage in (
                ("generation-status.json", "generation"),
                ("sequence-design-status.json", "sequence_design"),
                ("cofold-status.json", "cofold"),
                ("scoring-status.json", "scoring"),
                ("filter-status.json", "filter"),
            )
        },
    }


def run_synthetic(run_root: Path, workspace_root: Path) -> dict[str, Any]:
    run_root = require_runtime_root(workspace_root, run_root, must_exist=True)
    check = preflight(run_root, workspace_root)
    if not check["ok"]:
        raise BinderLaneError("preflight failed: " + "; ".join(check["findings"]))
    plan = read_json(run_root / "plan.json")
    if plan.get("result_boundary") != "public_synthetic_demo":
        raise BinderLaneError("run requires a public_synthetic_demo plan")
    fixture_path = contained_path(workspace_root, plan.get("synthetic_fixture"), "synthetic fixture", must_exist=True)
    candidates = _synthetic_candidates(read_json(fixture_path))
    expected_by_toolchain = _candidate_counts_per_round(plan)
    actual_by_toolchain = {arm_id: 0 for arm_id in expected_by_toolchain}
    for candidate in candidates:
        if candidate["toolchain_id"] not in actual_by_toolchain:
            raise BinderLaneError("synthetic fixture names a toolchain outside the plan")
        actual_by_toolchain[candidate["toolchain_id"]] += 1
    if actual_by_toolchain != expected_by_toolchain:
        raise BinderLaneError("synthetic fixture counts do not match planned toolchain counts")
    stage_files = _synthetic_stage_files(plan, candidates, actual_by_toolchain)
    for name, payload in stage_files.items():
        write_json(run_root / name, payload)
    report = _synthetic_report(plan, candidates, actual_by_toolchain)
    write_json(run_root / "round-report.json", report)
    expected = [artifact for stage in read_json(run_root / "round-contract.json")["stages"] for artifact in stage["expected_artifacts"]]
    missing = [name for name in expected if not (run_root / name).is_file()]
    if missing:
        raise BinderLaneError("expected artifacts are missing: " + ", ".join(missing))
    hashes = [{"path": name, "sha256": sha256_path(run_root / name)} for name in sorted(expected)]
    write_json(run_root / "artifact-hashes.json", {"schema_version": "structure-factory-artifact-hashes-v1", "artifacts": hashes})
    return report


def report_summary(run_root: Path, workspace_root: Path) -> dict[str, Any]:
    run_root = require_runtime_root(workspace_root, run_root, must_exist=True)
    check = preflight(run_root, workspace_root)
    hash_finding = "artifact hash ledger does not match the generated artifacts"
    if any(finding != hash_finding for finding in check["findings"]):
        raise BinderLaneError("preflight failed before report verification")
    report_path = run_root / "round-report.json"
    hashes_path = run_root / "artifact-hashes.json"
    if not report_path.is_file() or not hashes_path.is_file():
        raise BinderLaneError("run has no complete synthetic report")
    report = _require_public_document(read_json(report_path), "round report")
    contract = _require_public_document(read_json(run_root / "round-contract.json"), "round contract")
    plan = validate_plan(read_json(run_root / "plan.json"), workspace_root)
    fixture_path = contained_path(workspace_root, plan.get("synthetic_fixture"), "synthetic fixture", must_exist=True)
    candidates = _synthetic_candidates(read_json(fixture_path))
    expected_counts = _candidate_counts_per_round(plan)
    if report != _synthetic_report(plan, candidates, expected_counts):
        raise BinderLaneError("round report differs from the plan-derived synthetic report")
    expected = {artifact for stage in contract.get("stages", []) for artifact in stage.get("expected_artifacts", [])}
    mismatches = _artifact_hash_mismatches(run_root, expected)
    return {
        "ok": not mismatches,
        "schema_version": "structure-factory-binder-round-summary-v1",
        "round_id": report.get("round_id"),
        "result_boundary": report.get("result_boundary"),
        "source_posture": report.get("source_posture"),
        "candidate_count": report.get("candidate_count"),
        "provider_calls": 0,
        "hash_mismatches": mismatches,
        "not_supported": report.get("claims", {}).get("not_supported", []),
    }
