"""Run public binder adapters through a small local execution boundary.

The executor accepts argument arrays, not command strings. It runs only after
the caller grants local-execution authorization. Each attempt writes
a sanitized receipt under the repository's ``.runtime`` directory.
"""

from __future__ import annotations

import glob
import hashlib
import json
import math
import os
import re
import shutil
import subprocess
import tempfile
import uuid
from pathlib import Path, PurePath
from typing import Any, Mapping, Sequence


REGISTRY_SCHEMA_VERSION = "structure-factory-binder-execution-adapters-v1"
LOCAL_EXECUTION_AUTHORIZATION = "authorize_local_execution"
SUPPORTED_EXECUTION_KIND = "local_argv"
OPERATIONS = frozenset({"readiness", "run"})
ROUTE_BACKENDS = frozenset(
    {"local", "api", "fal", "neocloud", "runpod", "aws", "modal", "lambda", "cloud_vm", "ssh_hpc"}
)
ROUTE_EXECUTION_METHODS = frozenset({"platform_skill", "hosted_api", "self_hosted"})

_ID_RE = re.compile(r"^[a-z0-9]+(?:[a-z0-9._-]*[a-z0-9])?$")
_PROGRAM_RE = re.compile(r"^[A-Za-z0-9][A-Za-z0-9._+-]*$")
_ENVIRONMENT_NAME_RE = re.compile(r"^[A-Z_][A-Z0-9_]*$")
_PLACEHOLDER_NAME_RE = re.compile(r"^[a-z][a-z0-9_]*$")
_PLACEHOLDER_RE = re.compile(r"\{\{([a-z][a-z0-9_]*)\}\}")
_SHA256_RE = re.compile(r"^[0-9a-f]{64}$")
_SAFE_RELATIVE_PATTERN_RE = re.compile(r"^[A-Za-z0-9._*?\[\]/{}/-]+$")

_SHELL_PROGRAMS = frozenset(
    {"bash", "csh", "dash", "fish", "ksh", "sh", "tcsh", "zsh", "cmd", "cmd.exe", "powershell", "pwsh"}
)
_INLINE_INTERPRETERS = frozenset(
    {"bun", "deno", "node", "perl", "python", "python2", "python3", "rscript", "ruby"}
)
_INLINE_FLAGS = frozenset({"-c", "-e", "-E", "--command", "--eval", "--exec"})
_OUTPUT_KINDS = frozenset({"file", "directory", "json", "jsonl", "fasta", "pdb", "cif"})


class BinderExecutorError(ValueError):
    """Raised when an adapter or local run breaks the execution contract."""


def _require_exact_keys(value: Mapping[str, Any], required: set[str], optional: set[str], label: str) -> None:
    missing = sorted(required - set(value))
    unknown = sorted(set(value) - required - optional)
    if missing:
        raise BinderExecutorError(f"{label} is missing required fields: {', '.join(missing)}")
    if unknown:
        raise BinderExecutorError(f"{label} has unknown fields: {', '.join(unknown)}")


def _validate_string_list(value: Any, label: str, *, allow_empty: bool = False) -> list[str]:
    if not isinstance(value, list) or (not value and not allow_empty):
        raise BinderExecutorError(f"{label} must be a {'possibly empty ' if allow_empty else ''}string list")
    if any(not isinstance(item, str) or not item for item in value):
        raise BinderExecutorError(f"{label} must contain non-empty strings")
    if len(value) != len(set(value)):
        raise BinderExecutorError(f"{label} must not contain duplicates")
    return list(value)


def _validate_program(program: Any, label: str) -> str:
    if not isinstance(program, str) or not _PROGRAM_RE.fullmatch(program):
        raise BinderExecutorError(f"{label} must be a static program name without a path")
    lowered = program.lower()
    if lowered in _SHELL_PROGRAMS:
        raise BinderExecutorError(f"{label} must not name a shell program")
    return program


def _validate_argv_template(value: Any, label: str, placeholders: set[str], program: str) -> list[str]:
    argv = _validate_string_list(value, label, allow_empty=True)
    if argv and argv[0] == program:
        argv = argv[1:]
    for index, token in enumerate(argv):
        names = _PLACEHOLDER_RE.findall(token)
        unresolved = token.replace("{{", "").replace("}}", "") if "{{" in token or "}}" in token else ""
        if ("{{" in token or "}}" in token) and not names:
            raise BinderExecutorError(f"{label}[{index}] has a malformed placeholder")
        if any(name not in placeholders for name in names):
            raise BinderExecutorError(f"{label}[{index}] uses an undeclared placeholder")
        residue = _PLACEHOLDER_RE.sub("", token)
        if "{{" in residue or "}}" in residue or unresolved and not names:
            raise BinderExecutorError(f"{label}[{index}] has an unresolved placeholder")
        path_probe = _PLACEHOLDER_RE.sub("placeholder", token)
        if PurePath(path_probe).is_absolute() or ".." in PurePath(path_probe).parts:
            raise BinderExecutorError(f"{label}[{index}] must not contain a path outside the runtime root")
    if program.lower() in _INLINE_INTERPRETERS and any(token in _INLINE_FLAGS for token in argv):
        raise BinderExecutorError(f"{label} must not select an inline-code mode")
    return argv


def _validate_placeholder_specs(value: Any, label: str) -> dict[str, dict[str, Any]]:
    if isinstance(value, list):
        names = _validate_string_list(value, label, allow_empty=True)
        value = {
            name: {
                "type": (
                    "integer"
                    if name in {"count", "seed"} or name.endswith("_count")
                    else "path"
                    if name.endswith(("_path", "_dir", "_structure"))
                    else "string"
                )
            }
            for name in names
        }
    if not isinstance(value, dict):
        raise BinderExecutorError(f"{label} must be a string list or typed object")
    result: dict[str, dict[str, Any]] = {}
    for name, raw_spec in value.items():
        if not isinstance(name, str) or not _PLACEHOLDER_NAME_RE.fullmatch(name):
            raise BinderExecutorError(f"{label} has an invalid placeholder name")
        if not isinstance(raw_spec, dict):
            raise BinderExecutorError(f"{label}.{name} must be an object")
        _require_exact_keys(
            raw_spec,
            {"type"},
            {"required", "minimum", "maximum", "choices"},
            f"{label}.{name}",
        )
        kind = raw_spec.get("type")
        if kind not in {"string", "integer", "number", "boolean", "path"}:
            raise BinderExecutorError(f"{label}.{name}.type is not supported")
        if "required" in raw_spec and not isinstance(raw_spec["required"], bool):
            raise BinderExecutorError(f"{label}.{name}.required must be boolean")
        for bound in ("minimum", "maximum"):
            if bound in raw_spec and (
                isinstance(raw_spec[bound], bool) or not isinstance(raw_spec[bound], (int, float))
            ):
                raise BinderExecutorError(f"{label}.{name}.{bound} must be numeric")
        choices = raw_spec.get("choices")
        if choices is not None and (not isinstance(choices, list) or not choices):
            raise BinderExecutorError(f"{label}.{name}.choices must be a non-empty list")
        result[name] = dict(raw_spec)
    return result


def _validate_expected_outputs(value: Any, label: str) -> list[dict[str, Any]]:
    if not isinstance(value, list) or not value:
        raise BinderExecutorError(f"{label} must be a non-empty list")
    result: list[dict[str, Any]] = []
    for index, item in enumerate(value):
        row_label = f"{label}[{index}]"
        if isinstance(item, str):
            item = {
                "id": f"output-{index}",
                "path_template": item,
                "kind": "file",
                "minimum_count": 1,
                "maximum_count": 1,
            }
        if not isinstance(item, dict):
            raise BinderExecutorError(f"{row_label} must be a path string or object")
        _require_exact_keys(
            item,
            {"id", "path_template", "kind", "minimum_count"},
            {"maximum_count"},
            row_label,
        )
        output_id = item.get("id")
        if not isinstance(output_id, str) or not _ID_RE.fullmatch(output_id):
            raise BinderExecutorError(f"{row_label}.id is invalid")
        path = item.get("path_template")
        if not isinstance(path, str):
            raise BinderExecutorError(f"{row_label}.path_template must be a safe runtime pattern")
        path_probe = _PLACEHOLDER_RE.sub("placeholder", path)
        if (
            not path
            or not _SAFE_RELATIVE_PATTERN_RE.fullmatch(path)
            or PurePath(path_probe).is_absolute()
            or ".." in PurePath(path_probe).parts
        ):
            raise BinderExecutorError(f"{row_label}.path_template must be a safe runtime pattern")
        residue = _PLACEHOLDER_RE.sub("", path)
        if "{{" in residue or "}}" in residue:
            raise BinderExecutorError(f"{row_label}.path_template has a malformed placeholder")
        if item.get("kind") not in _OUTPUT_KINDS:
            raise BinderExecutorError(f"{row_label}.kind is not supported")
        minimum = item.get("minimum_count")
        maximum = item.get("maximum_count")
        if isinstance(minimum, bool) or not isinstance(minimum, int) or minimum < 1:
            raise BinderExecutorError(f"{row_label}.minimum_count must be a positive integer")
        if maximum is not None and (
            isinstance(maximum, bool) or not isinstance(maximum, int) or maximum < minimum
        ):
            raise BinderExecutorError(f"{row_label}.maximum_count must be an integer at least minimum_count")
        result.append(dict(item))
    return result


def _validate_supported_routes(value: Any, label: str) -> list[dict[str, str]]:
    if not isinstance(value, list) or not value:
        raise BinderExecutorError(f"{label} must be a non-empty list")
    normalized: list[dict[str, str]] = []
    seen: set[tuple[str, str]] = set()
    for index, route in enumerate(value):
        route_label = f"{label}[{index}]"
        if not isinstance(route, dict):
            raise BinderExecutorError(f"{route_label} must be an object")
        _require_exact_keys(route, {"backend", "execution_method"}, set(), route_label)
        backend = route.get("backend")
        execution_method = route.get("execution_method")
        if backend not in ROUTE_BACKENDS:
            raise BinderExecutorError(f"{route_label}.backend is not supported")
        if execution_method not in ROUTE_EXECUTION_METHODS:
            raise BinderExecutorError(f"{route_label}.execution_method is not supported")
        identity = (backend, execution_method)
        if identity in seen:
            raise BinderExecutorError(f"{label} must not contain duplicate routes")
        seen.add(identity)
        normalized.append({"backend": backend, "execution_method": execution_method})
    return normalized


def _validate_supported_selections(value: Any, label: str) -> list[dict[str, str | None]]:
    if not isinstance(value, list) or not value:
        raise BinderExecutorError(f"{label} must be a non-empty list")
    normalized: list[dict[str, str | None]] = []
    seen: set[tuple[str, str | None]] = set()
    for index, selection in enumerate(value):
        selection_label = f"{label}[{index}]"
        if not isinstance(selection, dict):
            raise BinderExecutorError(f"{selection_label} must be an object")
        _require_exact_keys(selection, {"tool_id", "variant_id"}, set(), selection_label)
        tool_id = selection.get("tool_id")
        variant_id = selection.get("variant_id")
        if not isinstance(tool_id, str) or not _ID_RE.fullmatch(tool_id):
            raise BinderExecutorError(f"{selection_label}.tool_id is invalid")
        if variant_id is not None and (
            not isinstance(variant_id, str) or not _ID_RE.fullmatch(variant_id)
        ):
            raise BinderExecutorError(f"{selection_label}.variant_id is invalid")
        identity = (tool_id, variant_id)
        if identity in seen:
            raise BinderExecutorError(f"{label} must not contain duplicate selections")
        seen.add(identity)
        normalized.append({"tool_id": tool_id, "variant_id": variant_id})
    return normalized


def adapter_supports_route(adapter: Mapping[str, Any], route: Mapping[str, Any]) -> bool:
    """Return whether an adapter explicitly supports the plan route."""
    return any(
        capability["backend"] == route.get("backend")
        and capability["execution_method"] == route.get("execution_method")
        for capability in adapter["supported_routes"]
    )


def adapter_supports_selection(
    adapter: Mapping[str, Any], tool_id: Any, variant_id: Any
) -> bool:
    """Return whether an adapter explicitly supports the selected tool identity."""
    return any(
        selection["tool_id"] == tool_id and selection["variant_id"] == variant_id
        for selection in adapter["supported_selections"]
    )


def validate_registry(registry: Any) -> dict[str, Any]:
    """Validate an in-memory public adapter registry and return a normalized copy."""
    if not isinstance(registry, dict):
        raise BinderExecutorError("adapter registry must be an object")
    _require_exact_keys(registry, {"schema_version", "boundary", "adapters"}, set(), "adapter registry")
    if registry.get("schema_version") != REGISTRY_SCHEMA_VERSION:
        raise BinderExecutorError("adapter registry has an unsupported schema_version")
    adapters = registry.get("adapters")
    if not isinstance(adapters, list):
        raise BinderExecutorError("adapter registry adapters must be a list")
    normalized: list[dict[str, Any]] = []
    seen: set[str] = set()
    required = {
        "id",
        "tool_id",
        "supported_selections",
        "roles",
        "supported_routes",
        "license_gate",
        "implementation_status",
        "execution_kind",
        "program",
        "readiness_argv",
        "command_argv",
        "placeholders",
        "required_environment_names",
        "network_policy",
        "expected_outputs",
        "public_evidence",
    }
    for index, item in enumerate(adapters):
        label = f"adapter registry adapters[{index}]"
        if not isinstance(item, dict):
            raise BinderExecutorError(f"{label} must be an object")
        missing_capabilities = {"supported_selections", "supported_routes"} - set(item)
        if missing_capabilities:
            raise BinderExecutorError(
                f"{label} must declare {', '.join(sorted(missing_capabilities))}; "
                "add explicit selection and route capabilities when migrating this registry"
            )
        _require_exact_keys(item, required, set(), label)
        adapter_id = item.get("id")
        if not isinstance(adapter_id, str) or not _ID_RE.fullmatch(adapter_id):
            raise BinderExecutorError(f"{label}.id is invalid")
        if adapter_id in seen:
            raise BinderExecutorError("adapter registry IDs must be unique")
        seen.add(adapter_id)
        tool_id = item.get("tool_id")
        if not isinstance(tool_id, str) or not _ID_RE.fullmatch(tool_id):
            raise BinderExecutorError(f"{label}.tool_id is invalid")
        supported_selections = _validate_supported_selections(
            item.get("supported_selections"), f"{label}.supported_selections"
        )
        roles = _validate_string_list(item.get("roles"), f"{label}.roles")
        supported_routes = _validate_supported_routes(
            item.get("supported_routes"), f"{label}.supported_routes"
        )
        if not isinstance(item.get("license_gate"), str) or not item["license_gate"]:
            raise BinderExecutorError(f"{label}.license_gate must be a non-empty string")
        if not isinstance(item.get("implementation_status"), str) or not item["implementation_status"]:
            raise BinderExecutorError(f"{label}.implementation_status must be a non-empty string")
        execution_kind = item.get("execution_kind")
        if not isinstance(execution_kind, str) or not execution_kind:
            raise BinderExecutorError(f"{label}.execution_kind must be a non-empty string")
        program = item.get("program")
        if execution_kind == SUPPORTED_EXECUTION_KIND:
            program = _validate_program(program, f"{label}.program")
        elif program is not None:
            raise BinderExecutorError(f"{label}.program must be null outside local_argv execution")
        placeholders = _validate_placeholder_specs(item.get("placeholders"), f"{label}.placeholders")
        readiness = _validate_argv_template(
            item.get("readiness_argv"), f"{label}.readiness_argv", set(placeholders), program or ""
        )
        command = _validate_argv_template(
            item.get("command_argv"), f"{label}.command_argv", set(placeholders), program or ""
        )
        environment_names = _validate_string_list(
            item.get("required_environment_names"),
            f"{label}.required_environment_names",
            allow_empty=True,
        )
        if any(not _ENVIRONMENT_NAME_RE.fullmatch(name) for name in environment_names):
            raise BinderExecutorError(f"{label}.required_environment_names has an invalid name")
        if item.get("network_policy") not in {"forbidden", "runtime_review_required"}:
            raise BinderExecutorError(
                f"{label}.network_policy must be forbidden or runtime_review_required"
            )
        outputs = _validate_expected_outputs(item.get("expected_outputs"), f"{label}.expected_outputs")
        for output_index, output in enumerate(outputs):
            names = set(_PLACEHOLDER_RE.findall(output["path_template"]))
            if not names.issubset(placeholders):
                raise BinderExecutorError(
                    f"{label}.expected_outputs[{output_index}].path_template uses an undeclared placeholder"
                )
        public_evidence = _validate_string_list(
            item.get("public_evidence"), f"{label}.public_evidence", allow_empty=True
        )
        normalized.append(
            {
                **item,
                "roles": roles,
                "supported_selections": supported_selections,
                "supported_routes": supported_routes,
                "program": program,
                "readiness_argv": readiness,
                "command_argv": command,
                "placeholders": placeholders,
                "required_environment_names": environment_names,
                "expected_outputs": outputs,
                "public_evidence": public_evidence,
            }
        )
    boundary = registry.get("boundary")
    if not isinstance(boundary, dict):
        raise BinderExecutorError("adapter registry boundary must be an object")
    _require_exact_keys(
        boundary,
        {"execution", "readiness", "extensions"},
        set(),
        "adapter registry boundary",
    )
    if not isinstance(boundary.get("execution"), str) or not isinstance(boundary.get("readiness"), str):
        raise BinderExecutorError("adapter registry boundary text must be strings")
    _validate_string_list(boundary.get("extensions"), "adapter registry boundary.extensions")
    return {
        "schema_version": REGISTRY_SCHEMA_VERSION,
        "boundary": dict(boundary),
        "adapters": normalized,
    }


def _adapter(registry: Mapping[str, Any], adapter_id: str) -> dict[str, Any]:
    for adapter in registry["adapters"]:
        if adapter["id"] == adapter_id:
            return adapter
    raise BinderExecutorError("adapter registry does not contain the requested adapter")


def _runtime_root(workspace_root: Path, runtime_root: Path) -> tuple[Path, Path]:
    workspace_lexical = Path(os.path.abspath(workspace_root))
    workspace = workspace_lexical.resolve()
    if not workspace.is_dir():
        raise BinderExecutorError("workspace root does not exist")
    runtime_base_lexical = workspace_lexical / ".runtime"
    if runtime_base_lexical.is_symlink():
        raise BinderExecutorError(".runtime must not be a symbolic link")
    runtime_base_lexical.mkdir(exist_ok=True)
    runtime_base = runtime_base_lexical.resolve()
    raw = runtime_root if runtime_root.is_absolute() else workspace_lexical / runtime_root
    normalized = Path(os.path.abspath(os.path.normpath(raw)))
    try:
        normalized.relative_to(runtime_base_lexical)
    except ValueError as exc:
        raise BinderExecutorError("runtime root must stay below .runtime") from exc
    resolved = normalized.resolve()
    if resolved != runtime_base and runtime_base not in resolved.parents:
        raise BinderExecutorError("runtime root resolves outside .runtime")
    resolved.mkdir(parents=True, exist_ok=True)
    if resolved.is_symlink():
        raise BinderExecutorError("runtime root must not be a symbolic link")
    return workspace, resolved


def _binding_value(name: str, spec: Mapping[str, Any], bindings: Mapping[str, Any], runtime_root: Path) -> str:
    required = spec.get("required", True)
    if name not in bindings:
        if required:
            raise BinderExecutorError(f"runtime binding is missing: {name}")
        return ""
    value = bindings[name]
    kind = spec["type"]
    if kind == "string":
        if not isinstance(value, str) or not value or "\x00" in value or "\n" in value or "\r" in value:
            raise BinderExecutorError(f"runtime binding {name} must be a non-empty single-line string")
        if PurePath(value).is_absolute() or re.match(r"^[A-Za-z]:[\\/]", value):
            raise BinderExecutorError(f"runtime binding {name} must not contain an absolute path")
        rendered = value
    elif kind == "integer":
        if isinstance(value, bool) or not isinstance(value, int):
            raise BinderExecutorError(f"runtime binding {name} must be an integer")
        rendered = str(value)
    elif kind == "number":
        if isinstance(value, bool) or not isinstance(value, (int, float)) or not math.isfinite(float(value)):
            raise BinderExecutorError(f"runtime binding {name} must be a finite number")
        rendered = str(value)
    elif kind == "boolean":
        if not isinstance(value, bool):
            raise BinderExecutorError(f"runtime binding {name} must be boolean")
        rendered = "true" if value else "false"
    elif kind == "path":
        if not isinstance(value, str) or not value or "\x00" in value:
            raise BinderExecutorError(f"runtime binding {name} must be a path string")
        raw = Path(value)
        candidate = raw if raw.is_absolute() else runtime_root / raw
        candidate = Path(os.path.normpath(candidate)).resolve()
        if candidate != runtime_root and runtime_root not in candidate.parents:
            raise BinderExecutorError(f"runtime binding {name} resolves outside the runtime root")
        rendered = str(candidate)
    else:  # validate_registry closes this branch.
        raise BinderExecutorError(f"runtime binding {name} has an unsupported type")
    if "minimum" in spec:
        measured = value if kind in {"integer", "number"} else len(rendered)
        if measured < spec["minimum"]:
            raise BinderExecutorError(f"runtime binding {name} is below its minimum")
    if "maximum" in spec:
        measured = value if kind in {"integer", "number"} else len(rendered)
        if measured > spec["maximum"]:
            raise BinderExecutorError(f"runtime binding {name} is above its maximum")
    if "choices" in spec and value not in spec["choices"]:
        raise BinderExecutorError(f"runtime binding {name} is outside its allowed choices")
    return rendered


def _render_values(
    adapter: Mapping[str, Any],
    bindings: Mapping[str, Any],
    runtime_root: Path,
    operation: str,
) -> dict[str, str]:
    unknown = sorted(set(bindings) - set(adapter["placeholders"]))
    if unknown:
        raise BinderExecutorError("runtime bindings contain undeclared names")
    template = adapter["readiness_argv" if operation == "readiness" else "command_argv"]
    needed = {name for token in template for name in _PLACEHOLDER_RE.findall(token)}
    if operation == "run":
        needed.update(
            name
            for contract in adapter["expected_outputs"]
            for name in _PLACEHOLDER_RE.findall(contract["path_template"])
        )
    return {
        name: _binding_value(name, spec, bindings, runtime_root)
        for name, spec in adapter["placeholders"].items()
        if name in needed
    }


def validate_run_bindings(
    registry: Any,
    adapter_id: str,
    bindings: Mapping[str, Any],
    *,
    runtime_root: Path,
) -> dict[str, Any]:
    """Validate run bindings without checking installation or writing files."""
    validated = validate_registry(registry)
    adapter = _adapter(validated, adapter_id)
    if adapter["execution_kind"] != SUPPORTED_EXECUTION_KIND:
        raise BinderExecutorError("adapter has no local argv execution contract")
    values = _render_values(adapter, dict(bindings), Path(runtime_root).resolve(), "run")
    _render_argv(adapter, "run", values)
    for contract in adapter["expected_outputs"]:
        _render_token(contract["path_template"], values)
    return adapter


def _render_token(token: str, values: Mapping[str, str]) -> str:
    rendered = _PLACEHOLDER_RE.sub(lambda match: values[match.group(1)], token)
    if "{{" in rendered or "}}" in rendered or "\x00" in rendered:
        raise BinderExecutorError("adapter argument has an unresolved placeholder")
    return rendered


def _render_argv(adapter: Mapping[str, Any], operation: str, values: Mapping[str, str]) -> list[str]:
    template = adapter["readiness_argv" if operation == "readiness" else "command_argv"]
    rendered = [_render_token(token, values) for token in template]
    if adapter["program"].lower() in _INLINE_INTERPRETERS and any(token in _INLINE_FLAGS for token in rendered):
        raise BinderExecutorError("adapter arguments must not select an inline-code mode")
    return [adapter["program"], *rendered]


def _sanitized_environment(
    names: Sequence[str], source: Mapping[str, str], runtime_root: Path
) -> tuple[dict[str, str], list[str]]:
    missing = [name for name in names if not isinstance(source.get(name), str) or not source.get(name)]
    if missing:
        return {}, sorted(missing)
    runtime_home = runtime_root / ".executor-home"
    runtime_temp = runtime_root / ".executor-tmp"
    runtime_home.mkdir(exist_ok=True)
    runtime_temp.mkdir(exist_ok=True)
    environment = {
        "HOME": str(runtime_home),
        "TMPDIR": str(runtime_temp),
        "PATH": source.get("PATH", os.defpath),
        "LANG": source.get("LANG", "C.UTF-8"),
    }
    environment.update({name: source[name] for name in names})
    return environment, []


def _sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for block in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(block)
    return digest.hexdigest()


def _record_count(path: Path, kind: str) -> int:
    if kind == "directory":
        if not path.is_dir():
            raise BinderExecutorError("declared output directory is missing")
        count = sum(1 for child in path.rglob("*") if child.is_file() and not child.is_symlink())
        if count == 0:
            raise BinderExecutorError("declared output directory has no files")
        return count
    if not path.is_file() or path.stat().st_size == 0:
        raise BinderExecutorError("declared output is missing or empty")
    if kind == "json":
        json.loads(path.read_text(encoding="utf-8"))
        return 1
    if kind == "jsonl":
        count = 0
        for line in path.read_text(encoding="utf-8").splitlines():
            if not line.strip():
                continue
            if not isinstance(json.loads(line), dict):
                raise BinderExecutorError("declared JSONL output contains a non-object row")
            count += 1
        if count == 0:
            raise BinderExecutorError("declared JSONL output has no rows")
        return count
    if kind == "fasta":
        count = sum(1 for line in path.read_text(encoding="utf-8").splitlines() if line.startswith(">"))
        if count == 0:
            raise BinderExecutorError("declared FASTA output has no records")
        return count
    if kind == "pdb":
        count = sum(
            1
            for line in path.read_text(encoding="utf-8", errors="replace").splitlines()
            if line.startswith(("ATOM  ", "HETATM"))
        )
        if count == 0:
            raise BinderExecutorError("declared PDB output has no atom records")
        return count
    if kind == "cif":
        if "_atom_site." not in path.read_text(encoding="utf-8", errors="replace"):
            raise BinderExecutorError("declared mmCIF output has no atom_site category")
        return 1
    return 1


def _directory_manifest(path: Path) -> tuple[str, int, list[dict[str, Any]]]:
    """Return a content-bound manifest for one directory output."""
    if path.is_symlink() or not path.is_dir():
        raise BinderExecutorError("declared output directory is missing or symbolic")
    members: list[dict[str, Any]] = []
    for child in sorted(path.rglob("*"), key=lambda item: item.relative_to(path).as_posix()):
        if child.is_symlink():
            raise BinderExecutorError("declared output directory contains a symbolic link")
        if child.is_dir():
            continue
        if not child.is_file():
            raise BinderExecutorError("declared output directory contains a non-file entry")
        members.append(
            {
                "path": child.relative_to(path).as_posix(),
                "bytes": child.stat().st_size,
                "records": 1,
                "sha256": _sha256(child),
            }
        )
    if not members:
        raise BinderExecutorError("declared output directory has no files")
    encoded = json.dumps(
        members,
        sort_keys=True,
        separators=(",", ":"),
        ensure_ascii=True,
        allow_nan=False,
    ).encode("ascii")
    return hashlib.sha256(encoded).hexdigest(), sum(row["bytes"] for row in members), members


def _validate_outputs(
    adapter: Mapping[str, Any], runtime_root: Path, values: Mapping[str, str]
) -> tuple[list[dict[str, Any]], list[str]]:
    records: list[dict[str, Any]] = []
    findings: list[str] = []
    claimed: set[Path] = set()
    for contract in adapter["expected_outputs"]:
        rendered_pattern = _render_token(contract["path_template"], values)
        raw_pattern = Path(rendered_pattern)
        pattern_path = (raw_pattern if raw_pattern.is_absolute() else runtime_root / raw_pattern).resolve()
        if pattern_path != runtime_root and runtime_root not in pattern_path.parents:
            findings.append("declared output pattern resolves outside the runtime root")
            continue
        matches = sorted(Path(value) for value in glob.glob(str(pattern_path), recursive=False))
        files: list[dict[str, Any]] = []
        for path in matches:
            resolved = path.resolve()
            if path.is_symlink() or (resolved != runtime_root and runtime_root not in resolved.parents):
                findings.append("declared output resolves outside the runtime root")
                continue
            if resolved in claimed:
                findings.append("two output contracts claim the same file")
                continue
            claimed.add(resolved)
            try:
                count = _record_count(resolved, contract["kind"])
                members: list[dict[str, Any]] | None = None
                if contract["kind"] == "directory":
                    digest, bytes_count, members = _directory_manifest(resolved)
                else:
                    digest, bytes_count = _sha256(resolved), resolved.stat().st_size
            except (BinderExecutorError, OSError, UnicodeError, json.JSONDecodeError):
                findings.append("declared output failed content validation")
                continue
            artifact = {
                "path": resolved.relative_to(runtime_root).as_posix(),
                "bytes": bytes_count,
                "records": count,
                "sha256": digest,
            }
            if members is not None:
                artifact["members"] = members
            files.append(artifact)
        count = len(files)
        if count < contract["minimum_count"]:
            findings.append("declared output count is below minimum_count")
        maximum = contract.get("maximum_count")
        if maximum is not None and count > maximum:
            findings.append("declared output count is above maximum_count")
        records.append(
            {
                "id": contract["id"],
                "pattern_template": contract["path_template"],
                "kind": contract["kind"],
                "minimum_count": contract["minimum_count"],
                "maximum_count": maximum,
                "matched_count": count,
                "files": files,
            }
        )
    return records, findings


def _write_receipt(runtime_root: Path, receipt: Mapping[str, Any]) -> Path:
    receipt_dir = runtime_root / "receipts"
    if receipt_dir.is_symlink():
        raise BinderExecutorError("receipt directory must not be a symbolic link")
    receipt_dir.mkdir(parents=True, exist_ok=True)
    if runtime_root not in receipt_dir.resolve().parents:
        raise BinderExecutorError("receipt directory resolves outside the runtime root")
    path = receipt_dir / f"{receipt['adapter_id']}-{receipt['operation']}-{uuid.uuid4().hex}.json"
    payload = json.dumps(receipt, indent=2, sort_keys=True, allow_nan=False) + "\n"
    with tempfile.NamedTemporaryFile("w", encoding="utf-8", dir=receipt_dir, delete=False) as handle:
        handle.write(payload)
        temporary = Path(handle.name)
    os.replace(temporary, path)
    return path


def _execution_log(runtime_root: Path, adapter_id: str, operation: str) -> tuple[Path, str]:
    log_dir = runtime_root / "logs"
    if log_dir.is_symlink():
        raise BinderExecutorError("log directory must not be a symbolic link")
    log_dir.mkdir(parents=True, exist_ok=True)
    resolved = log_dir.resolve()
    if resolved != runtime_root and runtime_root not in resolved.parents:
        raise BinderExecutorError("log directory resolves outside the runtime root")
    path = resolved / f"{adapter_id}-{operation}-{uuid.uuid4().hex}.log"
    return path, path.relative_to(runtime_root).as_posix()


def run_adapter(
    registry: Any,
    adapter_id: str,
    *,
    workspace_root: Path,
    runtime_root: Path,
    bindings: Mapping[str, Any] | None = None,
    operation: str = "run",
    authorization: str | None = None,
    dry_run: bool = False,
    timeout_seconds: int = 300,
    source_environment: Mapping[str, str] | None = None,
) -> dict[str, Any]:
    """Validate and run one local adapter, then write a sanitized receipt."""
    validated = validate_registry(registry)
    if operation not in OPERATIONS:
        raise BinderExecutorError("operation must be readiness or run")
    if isinstance(timeout_seconds, bool) or not isinstance(timeout_seconds, int) or timeout_seconds < 1:
        raise BinderExecutorError("timeout_seconds must be a positive integer")
    workspace, runtime = _runtime_root(Path(workspace_root), Path(runtime_root))
    adapter = _adapter(validated, adapter_id)
    if adapter["execution_kind"] != SUPPORTED_EXECUTION_KIND:
        raise BinderExecutorError("adapter has no local argv execution contract")
    if not dry_run and authorization != LOCAL_EXECUTION_AUTHORIZATION:
        raise BinderExecutorError("local execution requires explicit authorization")
    values = _render_values(adapter, dict(bindings or {}), runtime, operation)
    rendered_argv = _render_argv(adapter, operation, values)
    environment, missing_environment = _sanitized_environment(
        adapter["required_environment_names"],
        os.environ if source_environment is None else source_environment,
        runtime,
    )
    program_path = shutil.which(adapter["program"])
    readiness_findings: list[str] = []
    if program_path is None:
        readiness_findings.append("program was not found")
    if missing_environment:
        readiness_findings.append("required environment names are missing")
    receipt: dict[str, Any] = {
        "schema_version": "structure-factory-binder-execution-receipt-v1",
        "adapter_id": adapter["id"],
        "tool_id": adapter["tool_id"],
        "implementation_status": adapter["implementation_status"],
        "operation": operation,
        "dry_run": dry_run,
        "authorized": authorization == LOCAL_EXECUTION_AUTHORIZATION,
        "execution_kind": adapter["execution_kind"],
        "network_policy": adapter["network_policy"],
        "program": adapter["program"],
        "argument_count": len(rendered_argv) - 1,
        "environment_names": sorted(adapter["required_environment_names"]),
        "missing_environment_names": missing_environment,
        "runtime_root": runtime.relative_to(workspace).as_posix(),
        "timeout_seconds": timeout_seconds,
        "status": "planned" if dry_run else "not_started",
        "returncode": None,
        "timed_out": False,
        "log_path": None,
        "outputs": [],
        "findings": readiness_findings,
    }
    if dry_run:
        receipt["ok"] = not readiness_findings
        receipt_path = _write_receipt(runtime, receipt)
        return {**receipt, "receipt_path": receipt_path.relative_to(workspace).as_posix()}
    if readiness_findings:
        receipt["status"] = "blocked"
        receipt["ok"] = False
        receipt_path = _write_receipt(runtime, receipt)
        return {**receipt, "receipt_path": receipt_path.relative_to(workspace).as_posix()}
    log_path, log_relative = _execution_log(runtime, adapter["id"], operation)
    receipt["log_path"] = log_relative
    try:
        with log_path.open("w", encoding="utf-8") as log_handle:
            completed = subprocess.run(
                [str(program_path), *rendered_argv[1:]],
                cwd=runtime,
                env=environment,
                stdin=subprocess.DEVNULL,
                stdout=log_handle,
                stderr=subprocess.STDOUT,
                text=True,
                timeout=timeout_seconds,
                check=False,
                shell=False,
            )
    except subprocess.TimeoutExpired:
        receipt["status"] = "failed"
        receipt["timed_out"] = True
        receipt["findings"].append("adapter exceeded timeout_seconds")
    except OSError:
        receipt["status"] = "failed"
        receipt["findings"].append("adapter process could not start")
    else:
        receipt["returncode"] = completed.returncode
        if completed.returncode != 0:
            receipt["status"] = "failed"
            receipt["findings"].append("adapter process returned a non-zero status")
        elif operation == "readiness":
            receipt["status"] = "completed"
        else:
            outputs, output_findings = _validate_outputs(adapter, runtime, values)
            receipt["outputs"] = outputs
            receipt["findings"].extend(output_findings)
            receipt["status"] = "completed" if not output_findings else "failed"
    receipt["ok"] = receipt["status"] == "completed"
    receipt_path = _write_receipt(runtime, receipt)
    return {**receipt, "receipt_path": receipt_path.relative_to(workspace).as_posix()}
