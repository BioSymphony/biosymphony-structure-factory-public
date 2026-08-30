#!/usr/bin/env python3
"""Run no-download Structure Factory smoke checks.

This is safe to run locally or on a RunPod Pod. It records environment and
storage facts without downloading biological data or launching restricted tools.
"""

from __future__ import annotations

import argparse
import json
import os
import platform
import shutil
import subprocess
import sys
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

SCRIPT_DIR = Path(__file__).resolve().parent
if str(SCRIPT_DIR) not in sys.path:
    sys.path.insert(0, str(SCRIPT_DIR))

from license_gate_check import evaluate_gates  # noqa: E402
from stage_contract_check import emit_event, evaluate as evaluate_stage_contract, load_json as load_stage_json  # noqa: E402


COMMANDS = {
    "python": ["python3", "--version"],
    "git": ["git", "--version"],
    "nvidia_smi": ["nvidia-smi"],
    "docker": ["docker", "--version"],
}

OPEN_TOOLS = {
    "relion": ["relion_refine", "--version"],
    "warp_m": ["WarpTools", "--help"],
    "topaz": ["topaz", "--help"],
    "ctffind": ["ctffind", "--help"],
    "modelangelo": ["model_angelo", "--help"],
    "boltz": ["boltz", "--help"],
    "openmm": ["python3", "-c", "import openmm; print(openmm.__version__)"],
    "rdkit": ["python3", "-c", "import rdkit; print(rdkit.__version__)"],
}

GATED_TOOLS = {
    "cryosparc": ["cryosparcm", "status"],
    "phenix": ["phenix.version"],
    "chimerax": ["ChimeraX", "--version"],
    "motioncor3": ["MotionCor3", "--help"],
    "pyrosetta": ["python3", "-c", "import pyrosetta; print(pyrosetta.__version__)"],
}


def run_command(command: list[str], timeout: int = 15) -> dict[str, Any]:
    exe = command[0]
    if shutil.which(exe) is None:
        return {"available": False, "command": command, "reason": "not_found"}
    try:
        result = subprocess.run(command, text=True, capture_output=True, timeout=timeout)
    except Exception as exc:
        return {"available": True, "command": command, "ok": False, "error": f"{type(exc).__name__}: {exc}"}
    return {
        "available": True,
        "command": command,
        "ok": result.returncode == 0,
        "returncode": result.returncode,
        "stdout": result.stdout[:2000],
        "stderr": result.stderr[:2000],
    }


def write_json(path: Path, data: dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(data, indent=2, sort_keys=True) + "\n")


def resolve_stage_contract(manifest_path: Path, manifest: dict[str, Any], out: Path) -> Path | None:
    rel = manifest.get("stage_contract")
    if not isinstance(rel, str) or not rel:
        return None
    candidates = [
        Path.cwd() / rel,
        manifest_path.resolve().parents[2] / rel if len(manifest_path.resolve().parents) >= 3 else manifest_path.resolve().parent / rel,
        out.parent / "stage-contract.json",
        out / "stage-contract.json",
    ]
    for candidate in candidates:
        if candidate.exists():
            return candidate
    return None


def write_prep_stage_artifacts(manifest_path: Path, manifest: dict[str, Any], out: Path) -> None:
    stage_contract = resolve_stage_contract(manifest_path, manifest, out)
    progress_path = out / "stage-progress.jsonl"
    if progress_path.exists():
        # A real entrypoint is already writing progress. Do not overwrite it with
        # prep-only toolcheck events.
        return
    stage_id = "toolcheck"
    if stage_contract is not None:
        try:
            contract = load_stage_json(stage_contract)
            contract_stage_ids = [stage.get("stage_id") for stage in contract.get("stages", []) if isinstance(stage, dict)]
            if stage_id not in contract_stage_ids and contract_stage_ids:
                stage_id = str(contract_stage_ids[0])
        except Exception:
            pass
    progress_path.write_text(
        json.dumps(emit_event(stage_id, "started", "prep toolcheck started"), sort_keys=True) + "\n"
        + json.dumps(emit_event(stage_id, "completed", "prep toolcheck completed"), sort_keys=True) + "\n"
    )
    if stage_contract is None:
        summary = {
            "ok": False,
            "check_type": "structure_factory_stage_contract_check",
            "errors": ["stage contract not found"],
            "warnings": [],
        }
    else:
        summary = evaluate_stage_contract(stage_contract, progress_path, require_terminal=False)
    write_json(out / "validation" / "stage-contract-check.json", summary)


def storage_check(root: Path) -> dict[str, Any]:
    root.mkdir(parents=True, exist_ok=True)
    probe = root / ".structure_factory_write_probe"
    payload = f"structure-factory {datetime.now(timezone.utc).isoformat()}\n"
    probe.write_text(payload)
    readback = probe.read_text()
    probe.unlink(missing_ok=True)
    usage = shutil.disk_usage(root)
    return {
        "ok": readback == payload,
        "root": str(root),
        "total_bytes": usage.total,
        "used_bytes": usage.used,
        "free_bytes": usage.free,
    }


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--manifest", type=Path, required=True)
    parser.add_argument("--out", type=Path, required=True)
    parser.add_argument("--mock-gpu", action="store_true", help="Do not fail if nvidia-smi is absent")
    args = parser.parse_args()

    manifest = json.loads(args.manifest.read_text())
    out = args.out
    validation_dir = out / "validation"
    volume_root = Path(manifest.get("environment", {}).get("STRUCTURE_FACTORY_VOLUME_ROOT", "/workspace/structure-factory"))
    if str(out).startswith(".runtime"):
        storage_root = out / "storage-probe"
    else:
        storage_root = volume_root / "runs" / manifest.get("run_id", "structure-factory-smoke")

    command_results = {name: run_command(command) for name, command in COMMANDS.items()}
    open_results = {name: run_command(command) for name, command in OPEN_TOOLS.items()}
    gated_results = {name: run_command(command) for name, command in GATED_TOOLS.items()}
    license_gates = evaluate_gates(manifest)
    gpu_ok = command_results["nvidia_smi"].get("ok") is True or args.mock_gpu
    storage = storage_check(storage_root)

    run_manifest = {
        "schema_version": 1,
        "run_id": manifest.get("run_id"),
        "created_at": datetime.now(timezone.utc).isoformat(),
        "host": platform.node(),
        "platform": platform.platform(),
        "python": platform.python_version(),
        "no_download": manifest.get("data_policy", {}).get("allow_large_downloads") is False,
        "dry_run": args.mock_gpu,
        "mock_tools": args.mock_gpu,
        "gpu_ok": gpu_ok,
        "storage_ok": storage["ok"],
        "artifact_root": str(out.resolve()),
    }
    toolcheck = {
        "ok": bool(gpu_ok and storage["ok"] and license_gates["ok"]),
        "dry_run": args.mock_gpu,
        "mock_tools": args.mock_gpu,
        "evidence_level": "prep_mock" if args.mock_gpu else "environment_smoke",
        "required_commands": command_results,
        "open_tools": open_results,
        "gated_tools": gated_results,
        "license_gates": license_gates,
    }
    gpu = {
        "ok": gpu_ok,
        "mock_gpu": args.mock_gpu,
        "nvidia_smi": command_results["nvidia_smi"],
    }
    provenance = f"""# Structure Factory Smoke Provenance

- run_id: `{manifest.get('run_id')}`
- created_at: `{run_manifest['created_at']}`
- manifest: `{args.manifest.resolve()}`
- no_large_downloads: `{manifest.get('data_policy', {}).get('allow_large_downloads') is False}`
- storage_root: `{storage_root}`
"""

    write_json(out / "run-manifest.json", run_manifest)
    write_json(validation_dir / "toolcheck.json", toolcheck)
    write_json(validation_dir / "gpu.json", gpu)
    write_json(validation_dir / "storage.json", storage)
    write_json(validation_dir / "license-gates.json", license_gates)
    write_json(
        validation_dir / "versions.json",
        {
            "required": command_results,
            "open_tools": open_results,
            "gated_tools": gated_results,
            "license_gates": license_gates,
        },
    )
    (out / "provenance.md").write_text(provenance)
    write_prep_stage_artifacts(args.manifest, manifest, out)

    print(json.dumps({"ok": toolcheck["ok"], "out": str(out.resolve()), "run_manifest": run_manifest}, indent=2, sort_keys=True))
    return 0 if toolcheck["ok"] else 1


if __name__ == "__main__":
    raise SystemExit(main())
