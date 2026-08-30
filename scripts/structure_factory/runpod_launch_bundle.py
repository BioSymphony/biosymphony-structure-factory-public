#!/usr/bin/env python3
"""Create a provider-neutral RunPod launch bundle."""

from __future__ import annotations

import argparse
import hashlib
import json
import shutil
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from runpod_manifest_check import validate


REPO_ROOT = Path(__file__).resolve().parents[2]


def sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def write_json(path: Path, data: dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(data, indent=2, sort_keys=True) + "\n")


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--manifest", type=Path, required=True)
    parser.add_argument("--out", type=Path, required=True)
    args = parser.parse_args()

    manifest = json.loads(args.manifest.read_text())
    validation = validate(manifest, manifest_path=args.manifest)
    if not validation["ok"]:
        print(json.dumps({"ok": False, "validation": validation}, indent=2, sort_keys=True))
        return 1

    out = args.out
    out.mkdir(parents=True, exist_ok=True)
    remote = out / "remote"
    remote.mkdir(exist_ok=True)

    bundle_manifest = {
        "schema_version": 1,
        "bundle_id": manifest["run_id"],
        "created_at": datetime.now(timezone.utc).isoformat(),
        "source_manifest": str(args.manifest.resolve()),
        "source_manifest_sha256": sha256(args.manifest),
        "launch_manifest": "launch-manifest.json",
        "stage_contract": "stage-contract.json",
        "run_later": "run-later.sh",
        "remote_runner": "remote/toolcheck_runner.py",
        "remote_helpers": [
            "remote/license_gate_check.py",
            "remote/input_audit.py",
            "remote/fanout_estimator.py",
            "remote/stage_contract_check.py",
            "remote/contract_self_check.py",
        ],
        "policy": "no RunPod launch, no data download; operator must run explicitly",
    }

    shutil.copy2(args.manifest, out / "launch-manifest.json")
    stage_contract = manifest.get("stage_contract")
    if isinstance(stage_contract, str) and stage_contract:
        shutil.copy2(REPO_ROOT / stage_contract, out / "stage-contract.json")
    modules_dest = out / "modules"
    if modules_dest.exists():
        shutil.rmtree(modules_dest)
    shutil.copytree(REPO_ROOT / "modules", modules_dest)
    shutil.copy2(Path(__file__).with_name("toolcheck_runner.py"), remote / "toolcheck_runner.py")
    shutil.copy2(Path(__file__).with_name("license_gate_check.py"), remote / "license_gate_check.py")
    shutil.copy2(Path(__file__).with_name("input_audit.py"), remote / "input_audit.py")
    shutil.copy2(Path(__file__).with_name("fanout_estimator.py"), remote / "fanout_estimator.py")
    shutil.copy2(Path(__file__).with_name("stage_contract_check.py"), remote / "stage_contract_check.py")
    shutil.copy2(Path(__file__).with_name("contract_self_check.py"), remote / "contract_self_check.py")
    write_json(out / "bundle-manifest.json", bundle_manifest)

    run_later = f"""#!/usr/bin/env bash
set -euo pipefail

# This script is intentionally inert until an operator fills runtime values.
# It does not launch a pod by itself.

MANIFEST=\"$(cd \"$(dirname \"${{BASH_SOURCE[0]}}\")\" && pwd)/launch-manifest.json\"
echo \"Prepared Structure Factory RunPod launch manifest: $MANIFEST\"
echo \"Next manual step after approval: create a RunPod Pod from runpod/templates/*.template.json\"
echo \"Then run the audit, toolcheck, and final self-check against /workspace/structure-factory/runs/{manifest['run_id']}\"
"""
    (out / "run-later.sh").write_text(run_later)
    (out / "run-later.sh").chmod(0o755)

    print(json.dumps({"ok": True, "out": str(out.resolve()), "bundle_manifest": bundle_manifest}, indent=2, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
