#!/usr/bin/env python3
"""Evaluate Structure Factory license-gated runtime lanes.

The checker is safe before licenses exist. Missing optional gates are reported
as skipped; enabled or required gates without usable runtime access are blocked.
"""

from __future__ import annotations

import argparse
import json
import os
import re
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Mapping


PLACEHOLDER_MARKERS = {
    "changeme",
    "change_me",
    "dummy",
    "example",
    "placeholder",
    "todo",
    "runpod_secret",
}


@dataclass(frozen=True)
class GateSpec:
    gate_id: str
    env_refs: tuple[str, ...]
    enable_env: str
    note: str


GATE_SPECS: dict[str, GateSpec] = {
    "cryosparc": GateSpec(
        gate_id="cryosparc",
        env_refs=("CRYOSPARC_LICENSE_ID",),
        enable_env="STRUCTURE_FACTORY_ENABLE_CRYOSPARC",
        note="CryoSPARC single-workstation master/worker install.",
    ),
    "phenix": GateSpec(
        gate_id="phenix",
        env_refs=("PHENIX_ACCESS_REF", "PHENIX_INSTALLER_PATH", "PHENIX_INSTALLER_URL"),
        enable_env="STRUCTURE_FACTORY_ENABLE_PHENIX",
        note="Phenix runtime installer or secure access reference.",
    ),
    "chimerax": GateSpec(
        gate_id="chimerax",
        env_refs=("CHIMERAX_ACCESS_REF", "CHIMERAX_INSTALLER_PATH", "CHIMERAX_INSTALLER_URL", "CHIMERAX_LICENSE_ACCEPTED"),
        enable_env="STRUCTURE_FACTORY_ENABLE_CHIMERAX",
        note="ChimeraX non-commercial acceptance plus installer access.",
    ),
    "motioncor3": GateSpec(
        gate_id="motioncor3",
        env_refs=("MOTIONCOR3_ACCESS_REF", "MOTIONCOR3_BINARY_PATH", "MOTIONCOR3_INSTALLER_URL"),
        enable_env="STRUCTURE_FACTORY_ENABLE_MOTIONCOR3",
        note="MotionCor3 approved binary or secure access reference.",
    ),
    "rosetta_pyrosetta": GateSpec(
        gate_id="rosetta_pyrosetta",
        env_refs=("ROSETTA_ACCESS_REF", "PYROSETTA_ACCESS_REF", "PYROSETTA_USERNAME", "PYROSETTA_INSTALLER_URL"),
        enable_env="STRUCTURE_FACTORY_ENABLE_ROSETTA",
        note="Rosetta/PyRosetta licensed access.",
    ),
    "alphafold3": GateSpec(
        gate_id="alphafold3",
        env_refs=("ALPHAFOLD3_ACCESS_REF", "ALPHAFOLD3_WEIGHTS_PATH", "ALPHAFOLD3_MODEL_PARAMETERS_PATH"),
        enable_env="STRUCTURE_FACTORY_ENABLE_ALPHAFOLD3",
        note="AlphaFold 3 code/weights access.",
    ),
}

ALIASES = {
    "motioncor": "motioncor3",
    "rosetta": "rosetta_pyrosetta",
    "pyrosetta": "rosetta_pyrosetta",
    "af3": "alphafold3",
}


def load_manifest(path: Path | None) -> dict[str, Any]:
    if path is None:
        return {}
    return json.loads(path.read_text())


def normalize_gate(gate: str) -> str:
    key = gate.strip().lower().replace("-", "_")
    return ALIASES.get(key, key)


def truthy(value: str | None) -> bool:
    return str(value or "").strip().lower() in {"1", "true", "yes", "on", "enabled", "required"}


def is_placeholder(value: str) -> bool:
    clean = value.strip().lower()
    if not clean:
        return True
    return any(marker in clean for marker in PLACEHOLDER_MARKERS)


def value_is_valid(env_name: str, value: str) -> tuple[bool, str]:
    if is_placeholder(value):
        return False, "placeholder_or_empty"
    if env_name == "CRYOSPARC_LICENSE_ID":
        if not re.match(r"^[0-9a-fA-F]{8}-[0-9a-fA-F]{4}-[0-9a-fA-F]{4}-[0-9a-fA-F]{4}-[0-9a-fA-F]{12}$", value):
            return False, "cryosparc_license_id_must_look_like_uuid"
    if env_name == "CHIMERAX_LICENSE_ACCEPTED" and not truthy(value):
        return False, "chimerax_license_acceptance_must_be_truthy"
    return True, "ok"


def manifest_gate_entries(manifest: Mapping[str, Any]) -> dict[str, dict[str, Any]]:
    entries: dict[str, dict[str, Any]] = {}
    for raw in manifest.get("license_gates", []):
        if isinstance(raw, str):
            gate_id = normalize_gate(raw)
            entries[gate_id] = {"id": gate_id}
        elif isinstance(raw, Mapping):
            gate_id = normalize_gate(str(raw.get("id") or raw.get("gate_id") or ""))
            if gate_id:
                entries[gate_id] = dict(raw)
                entries[gate_id]["id"] = gate_id
    for gate_id in manifest.get("active_gated_lanes", []):
        normalized = normalize_gate(str(gate_id))
        entries.setdefault(normalized, {"id": normalized})["enabled"] = True
    for gate_id in manifest.get("required_license_gates", []):
        normalized = normalize_gate(str(gate_id))
        entries.setdefault(normalized, {"id": normalized})["required"] = True
    return entries


def configured_gates(manifest: Mapping[str, Any]) -> list[str]:
    entries = manifest_gate_entries(manifest)
    if entries:
        return sorted(entries)
    return sorted(GATE_SPECS)


def evaluate_gates(manifest: Mapping[str, Any], env: Mapping[str, str] | None = None) -> dict[str, Any]:
    env = env or os.environ
    entries = manifest_gate_entries(manifest)
    gates: dict[str, Any] = {}
    blocked_required: list[str] = []
    blocked_enabled: list[str] = []

    for gate_id in configured_gates(manifest):
        spec = GATE_SPECS.get(gate_id)
        if spec is None:
            gates[gate_id] = {
                "status": "blocked",
                "required": True,
                "enabled": True,
                "reason": "unknown_license_gate",
                "env_refs": [],
            }
            blocked_required.append(gate_id)
            continue

        entry = entries.get(gate_id, {})
        required = bool(entry.get("required"))
        enabled = bool(entry.get("enabled")) or truthy(env.get(spec.enable_env))
        present_refs = [name for name in spec.env_refs if env.get(name)]
        invalid_refs: list[dict[str, str]] = []
        for name in present_refs:
            valid, reason = value_is_valid(name, str(env[name]))
            if not valid:
                invalid_refs.append({"env": name, "reason": reason})

        if invalid_refs:
            status = "blocked"
            reason = "invalid_runtime_access"
        elif present_refs:
            status = "ready"
            reason = "runtime_access_present"
        elif required or enabled:
            status = "blocked"
            reason = "missing_required_runtime_access"
        else:
            status = "skipped"
            reason = "optional_gate_not_enabled"

        if status == "blocked" and required:
            blocked_required.append(gate_id)
        if status == "blocked" and enabled:
            blocked_enabled.append(gate_id)

        gates[gate_id] = {
            "status": status,
            "required": required,
            "enabled": enabled,
            "reason": reason,
            "env_refs": list(spec.env_refs),
            "present_env_refs": present_refs,
            "invalid_env_refs": invalid_refs,
            "note": spec.note,
        }

    return {
        "ok": not blocked_required and not blocked_enabled,
        "gates": gates,
        "blocked_required": blocked_required,
        "blocked_enabled": blocked_enabled,
    }


def write_json(path: Path, data: dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(data, indent=2, sort_keys=True) + "\n")


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--manifest", type=Path)
    parser.add_argument("--out", type=Path, help="Optional JSON output path")
    parser.add_argument("--json", action="store_true")
    args = parser.parse_args()

    manifest = load_manifest(args.manifest)
    summary = evaluate_gates(manifest)
    if args.manifest:
        summary["manifest_path"] = str(args.manifest.resolve())
    if args.out:
        write_json(args.out, summary)

    if args.json or not args.out:
        print(json.dumps(summary, indent=2, sort_keys=True))
    else:
        print(f"ok: {summary['ok']}")
        for gate_id, gate in summary["gates"].items():
            print(f"{gate_id}: {gate['status']} ({gate['reason']})")

    return 0 if summary["ok"] else 1


if __name__ == "__main__":
    raise SystemExit(main())
