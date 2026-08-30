#!/usr/bin/env bash
# PD-L1 + 8ZNL positive-control Boltz cofold entrypoint.
#
# One-shot cheap prediction (~20 min, ~$0.11 on RTX 4090 COMMUNITY) to validate
# the Boltz plumbing on a known-good 58-aa de novo binder (8ZNL chain A,
# picomolar KD vs PD-L1) before any design wave fires. No delta-vs-experiment,
# no MPNN/Genie sidecars — single cofold from a prebaked Boltz YAML.
#
# Required env (bridge manifest runpod.env):
#   STRUCTURE_FACTORY_RUN_ID            structure-factory-pd-l1-positive-control-8znl
#   STRUCTURE_FACTORY_VOLUME_ROOT       /workspace/structure-factory
#   STRUCTURE_FACTORY_REPO_ROOT         /workspace/repo
#   STRUCTURE_FACTORY_SOFTWARE_ROOT     /workspace/software
#   STRUCTURE_FACTORY_BOLTZ_WEIGHTS_DIR /workspace/software/weights/boltz
#   STRUCTURE_FACTORY_BOLTZ_YAML        campaigns/pd-l1-pd1-binder-design/boltz_inputs/positive_control_8znl.yaml
#   STRUCTURE_FACTORY_STAGE_CONTRACT    runpod/stage-contracts/pd-l1-positive-control.stage-contract.json

set -euo pipefail

RUN_ID="${STRUCTURE_FACTORY_RUN_ID:?STRUCTURE_FACTORY_RUN_ID is required}"
VOLUME_ROOT="${STRUCTURE_FACTORY_VOLUME_ROOT:-/workspace/structure-factory}"
REPO_ROOT="${STRUCTURE_FACTORY_REPO_ROOT:-/workspace/repo}"
SOFTWARE_ROOT="${STRUCTURE_FACTORY_SOFTWARE_ROOT:-/workspace/software}"
BOLTZ_WEIGHTS_DIR="${STRUCTURE_FACTORY_BOLTZ_WEIGHTS_DIR:-${SOFTWARE_ROOT}/weights/boltz}"
BOLTZ_YAML_REL="${STRUCTURE_FACTORY_BOLTZ_YAML:-campaigns/pd-l1-pd1-binder-design/boltz_inputs/positive_control_8znl.yaml}"
STAGE_CONTRACT="${STRUCTURE_FACTORY_STAGE_CONTRACT:-${REPO_ROOT}/runpod/stage-contracts/pd-l1-positive-control.stage-contract.json}"
EXECUTION_MODE="${STRUCTURE_FACTORY_EXECUTION_MODE:-real}"
ARTIFACT_ROOT="runpod-execution/artifacts"
ENTRYPOINT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
CURRENT_STAGE=""

mkdir -p "${ARTIFACT_ROOT}/validation" "${ARTIFACT_ROOT}/boltz" "${ARTIFACT_ROOT}/logs"
export STRUCTURE_FACTORY_STAGE_PROGRESS="${ARTIFACT_ROOT}/stage-progress.jsonl"
# shellcheck disable=SC1091
source "${ENTRYPOINT_DIR}/stage-progress.sh"

EXECUTED_COMMANDS="${ARTIFACT_ROOT}/executed-commands.jsonl"
: > "${EXECUTED_COMMANDS}"

record_command() {
  local stage_id="$1"; shift
  local rc="$1"; shift
  local cmd="$*"
  python3 - "${EXECUTED_COMMANDS}" "${stage_id}" "${rc}" "${cmd}" <<'PY'
import json, sys
from datetime import datetime, timezone
path, stage_id, rc, cmd = sys.argv[1:5]
event = {
    "schema_version": 1,
    "timestamp": datetime.now(timezone.utc).isoformat(),
    "stage_id": stage_id,
    "exit_code": int(rc),
    "command": cmd,
}
with open(path, "a", encoding="utf-8") as fh:
    fh.write(json.dumps(event, sort_keys=True) + "\n")
PY
}

on_error() {
  local rc=$?
  if [[ -n "${CURRENT_STAGE}" ]]; then
    sf_stage_fail "${CURRENT_STAGE}" "exit_code=${rc}"
    sf_partial_summary "${CURRENT_STAGE}" "degraded" "bash runpod/entrypoints/pd-l1-positive-control.sh" "partial"
  fi
  python3 - "${ARTIFACT_ROOT}" "${RUN_ID}" "${CURRENT_STAGE}" "${rc}" <<'PY' || true
import json, sys
from datetime import datetime, timezone
from pathlib import Path
root, run_id, failed_stage, rc = sys.argv[1:5]
status = {
    "ok": False,
    "status": "failed",
    "run_id": run_id,
    "failed_stage": failed_stage,
    "exit_code": int(rc),
    "artifact_root": str(root),
    "completed_at": datetime.now(timezone.utc).isoformat(),
}
Path(root).parent.mkdir(parents=True, exist_ok=True)
(Path(root).parent / "status.json").write_text(json.dumps(status, indent=2, sort_keys=True) + "\n")
PY
  exit "${rc}"
}
trap on_error ERR

if [[ ! -f "${REPO_ROOT}/${BOLTZ_YAML_REL}" && -n "${STRUCTURE_FACTORY_REPO_URL:-}" ]]; then
  bash "${ENTRYPOINT_DIR}/bootstrap-repo.sh"
fi
cd "${REPO_ROOT}"
BOLTZ_YAML_PATH="${REPO_ROOT}/${BOLTZ_YAML_REL}"

# Source the prebaked boltz conda env from the network volume.
if [[ -f "${SOFTWARE_ROOT}/miniconda3/etc/profile.d/conda.sh" ]]; then
  # shellcheck disable=SC1091
  source "${SOFTWARE_ROOT}/miniconda3/etc/profile.d/conda.sh"
  if [[ -d "${SOFTWARE_ROOT}/envs/boltz" ]]; then
    conda activate "${SOFTWARE_ROOT}/envs/boltz" || true
  fi
fi
if [[ -x "${SOFTWARE_ROOT}/envs/boltz/bin/boltz" ]]; then
  export PATH="${SOFTWARE_ROOT}/envs/boltz/bin:${PATH}"
fi

CURRENT_STAGE="manifest_preflight"
sf_stage_start "${CURRENT_STAGE}" "verifying YAML input and stage contract are present"
[[ -f "${BOLTZ_YAML_PATH}" ]] || { sf_stage_fail "${CURRENT_STAGE}" "missing ${BOLTZ_YAML_PATH}"; exit 1; }
[[ -f "${STAGE_CONTRACT}" ]] || { sf_stage_fail "${CURRENT_STAGE}" "missing ${STAGE_CONTRACT}"; exit 1; }
python3 - "${BOLTZ_YAML_PATH}" "${ARTIFACT_ROOT}/validation/manifest-preflight.json" <<'PY'
import hashlib, json, sys
from datetime import datetime, timezone
from pathlib import Path
yaml_path = Path(sys.argv[1])
out = Path(sys.argv[2])
out.parent.mkdir(parents=True, exist_ok=True)
data = yaml_path.read_bytes()
report = {
    "yaml_path": str(yaml_path),
    "yaml_sha256": hashlib.sha256(data).hexdigest(),
    "yaml_bytes": len(data),
    "verified_at": datetime.now(timezone.utc).isoformat(),
}
out.write_text(json.dumps(report, indent=2, sort_keys=True) + "\n")
PY
sf_stage_complete "${CURRENT_STAGE}" "yaml + stage contract present"
CURRENT_STAGE=""

CURRENT_STAGE="input_audit"
sf_stage_start "${CURRENT_STAGE}" "auditing positive-control input pair"
python3 - "${BOLTZ_YAML_PATH}" "${ARTIFACT_ROOT}/validation/input-audit.json" <<'PY'
import json, re, sys
from datetime import datetime, timezone
from pathlib import Path
yaml_path = Path(sys.argv[1])
out = Path(sys.argv[2])
out.parent.mkdir(parents=True, exist_ok=True)
text = yaml_path.read_text()
# Light-weight YAML extraction: pull sequences without requiring pyyaml so we
# can audit the input independently of the env. Each protein block looks like
#   - protein:\n      id: A\n      sequence: <ONE_LETTERS>
chains = []
for m in re.finditer(r"id:\s*(\S+)\s*\n\s*sequence:\s*([A-Za-z]+)", text):
    chains.append({"chain_id": m.group(1), "length": len(m.group(2)), "sequence": m.group(2)})
report = {
    "yaml_path": str(yaml_path),
    "chains": chains,
    "chain_count": len(chains),
    "target_label": "PD-L1",
    "binder_label": "8ZNL chain A (58-aa de novo, picomolar KD)",
    "verified_at": datetime.now(timezone.utc).isoformat(),
}
out.write_text(json.dumps(report, indent=2, sort_keys=True) + "\n")
PY
sf_stage_complete "${CURRENT_STAGE}" "input audit complete"
CURRENT_STAGE=""

CURRENT_STAGE="boltz_weights_check"
sf_stage_start "${CURRENT_STAGE}" "verifying Boltz weights cache at ${BOLTZ_WEIGHTS_DIR}"
python3 - "${BOLTZ_WEIGHTS_DIR}" "${ARTIFACT_ROOT}/validation/boltz_weights_manifest.json" <<'PY'
import json, sys
from datetime import datetime, timezone
from pathlib import Path
weights_dir = Path(sys.argv[1])
out = Path(sys.argv[2])
out.parent.mkdir(parents=True, exist_ok=True)
weights_dir.mkdir(parents=True, exist_ok=True)
files = []
total = 0
for path in sorted(weights_dir.rglob("*")):
    if path.is_file():
        size = path.stat().st_size
        total += size
        files.append({"path": str(path.relative_to(weights_dir)), "size": size})
manifest = {
    "weights_dir": str(weights_dir),
    "file_count": len(files),
    "total_bytes": total,
    "files": files[:50],
    "verified_at": datetime.now(timezone.utc).isoformat(),
    "cache_state": "populated" if files else "empty_will_populate_on_first_run",
}
out.write_text(json.dumps(manifest, indent=2, sort_keys=True) + "\n")
PY
BOLTZ_PATH="$(command -v boltz || true)"
[[ -n "${BOLTZ_PATH}" ]] || { sf_stage_fail "${CURRENT_STAGE}" "boltz CLI not on PATH"; exit 1; }
sf_stage_complete "${CURRENT_STAGE}" "boltz at ${BOLTZ_PATH}"
CURRENT_STAGE=""

CURRENT_STAGE="boltz_predict"
sf_stage_start "${CURRENT_STAGE}" "Boltz cofold for ${RUN_ID}"
WORK_DIR="${ARTIFACT_ROOT}/boltz/work"
mkdir -p "${WORK_DIR}"
YAML_STEM="$(basename "${BOLTZ_YAML_PATH}" .yaml)"
STAGED_YAML="${WORK_DIR}/${YAML_STEM}.yaml"
cp "${BOLTZ_YAML_PATH}" "${STAGED_YAML}"

BOLTZ_CMD=("boltz" "predict" "${STAGED_YAML}"
  "--use_msa_server"
  "--write_full_pae"
  "--no_kernels"
  "--cache" "${BOLTZ_WEIGHTS_DIR}"
  "--out_dir" "${WORK_DIR}")
set +e
"${BOLTZ_CMD[@]}" >> "${ARTIFACT_ROOT}/logs/boltz_predict.log" 2>&1
BOLTZ_RC=$?
set -e
record_command "${CURRENT_STAGE}" "${BOLTZ_RC}" "${BOLTZ_CMD[*]}"
if [[ "${BOLTZ_RC}" -ne 0 ]]; then
  sf_stage_fail "${CURRENT_STAGE}" "boltz exit ${BOLTZ_RC}"
  exit "${BOLTZ_RC}"
fi
sf_stage_complete "${CURRENT_STAGE}" "boltz exit 0"
CURRENT_STAGE=""

CURRENT_STAGE="boltz_postprocess"
sf_stage_start "${CURRENT_STAGE}" "promoting nested boltz outputs to flat paths"
python3 - "${WORK_DIR}" "${YAML_STEM}" "${ARTIFACT_ROOT}/boltz" "${ARTIFACT_ROOT}/validation/boltz_postprocess.json" <<'PY'
import hashlib, json, sys
from datetime import datetime, timezone
from pathlib import Path

work_dir = Path(sys.argv[1])
stem = sys.argv[2]
boltz_out = Path(sys.argv[3])
report_path = Path(sys.argv[4])
report_path.parent.mkdir(parents=True, exist_ok=True)
boltz_out.mkdir(parents=True, exist_ok=True)

# Boltz 2.x writes nested at <out_dir>/boltz_results_<stem>/predictions/<stem>/
nested_root = work_dir / f"boltz_results_{stem}" / "predictions" / stem
mapping = {
    f"{stem}_model_0.cif": "prediction.cif",
    f"pae_{stem}_model_0.npz": "prediction.pae.npz",
    f"plddt_{stem}_model_0.npz": "prediction.plddt.npz",
    f"confidence_{stem}_model_0.json": "confidence.json",
}

def sha256_of_file(p: Path) -> str:
    h = hashlib.sha256()
    with p.open("rb") as fh:
        for chunk in iter(lambda: fh.read(1024 * 1024), b""):
            h.update(chunk)
    return h.hexdigest()

promoted = {}
missing = []
for src_name, dst_name in mapping.items():
    src = nested_root / src_name
    dst = boltz_out / dst_name
    if src.exists():
        dst.write_bytes(src.read_bytes())
        promoted[dst_name] = {
            "size": dst.stat().st_size,
            "sha256": sha256_of_file(dst),
        }
    else:
        missing.append(src_name)

iptm = None
ptm = None
complex_plddt = None
conf_path = boltz_out / "confidence.json"
if conf_path.exists():
    try:
        conf = json.loads(conf_path.read_text())
        iptm = conf.get("iptm")
        ptm = conf.get("ptm")
        complex_plddt = conf.get("complex_plddt")
    except Exception as exc:
        missing.append(f"confidence_parse_error:{exc}")

manifest = {
    "schema_version": 1,
    "nested_root": str(nested_root),
    "boltz_out": str(boltz_out),
    "promoted": promoted,
    "missing": missing,
    "iptm": iptm,
    "ptm": ptm,
    "complex_plddt": complex_plddt,
    "verified_at": datetime.now(timezone.utc).isoformat(),
}
report_path.write_text(json.dumps(manifest, indent=2, sort_keys=True) + "\n")
(boltz_out / "boltz_manifest.json").write_text(json.dumps(manifest, indent=2, sort_keys=True) + "\n")
if "prediction.cif" not in promoted:
    raise SystemExit(f"prediction.cif missing after boltz run; nested_root={nested_root}")
PY
sf_stage_complete "${CURRENT_STAGE}" "flat paths promoted; iPTM captured"
CURRENT_STAGE=""

CURRENT_STAGE="contract_self_check"
sf_stage_start "${CURRENT_STAGE}" "verifying required artifacts and recording status"
python3 - "${ARTIFACT_ROOT}" "${RUN_ID}" "${STAGE_CONTRACT}" <<'PY'
import hashlib, json, sys
from datetime import datetime, timezone
from pathlib import Path

root = Path(sys.argv[1])
run_id = sys.argv[2]
stage_contract_path = Path(sys.argv[3])

required = [
    "boltz/prediction.cif",
    "boltz/confidence.json",
    "boltz/boltz_manifest.json",
    "validation/manifest-preflight.json",
    "validation/input-audit.json",
    "validation/boltz_weights_manifest.json",
    "validation/boltz_postprocess.json",
    "stage-progress.jsonl",
    "executed-commands.jsonl",
]
missing = [rel for rel in required if not (root / rel).is_file()]

iptm = None
manifest_path = root / "boltz" / "boltz_manifest.json"
if manifest_path.is_file():
    try:
        iptm = json.loads(manifest_path.read_text()).get("iptm")
    except Exception:
        iptm = None

ok = not missing and (root / "boltz" / "prediction.cif").stat().st_size > 0
report = {
    "schema_version": 1,
    "ok": ok,
    "run_id": run_id,
    "stage_contract_ref": str(stage_contract_path),
    "missing_artifacts": missing,
    "iptm": iptm,
    "iptm_note": "positive control expectation: iptm >= 0.5 to validate plumbing; >= 0.7 if Boltz training overlap with 8ZNL",
    "checked_at": datetime.now(timezone.utc).isoformat(),
}
out = root / "validation" / "contract-self-check.json"
out.parent.mkdir(parents=True, exist_ok=True)
out.write_text(json.dumps(report, indent=2, sort_keys=True) + "\n")

# Hash all non-archive artifacts.
hashes = {}
for path in sorted(root.rglob("*")):
    if path.is_file() and path.name != "runpod-execution.tar.gz":
        h = hashlib.sha256()
        with path.open("rb") as fh:
            for chunk in iter(lambda: fh.read(1024 * 1024), b""):
                h.update(chunk)
        hashes[str(path.relative_to(root))] = h.hexdigest()
(root.parent / "artifact_hashes.json").write_text(
    json.dumps({"sha256": hashes}, indent=2, sort_keys=True) + "\n"
)

status = {
    "ok": ok,
    "status": "completed" if ok else "failed",
    "run_id": run_id,
    "iptm": iptm,
    "missing_artifacts": missing,
    "artifact_root": str(root),
    "completed_at": datetime.now(timezone.utc).isoformat(),
}
(root.parent / "status.json").write_text(json.dumps(status, indent=2, sort_keys=True) + "\n")
if not ok:
    raise SystemExit(f"contract self-check failed: missing={missing}")
PY
sf_stage_complete "${CURRENT_STAGE}" "contract self-check ok"
CURRENT_STAGE=""

echo "pd-l1-positive-control complete: ${RUN_ID} -> ${ARTIFACT_ROOT}"
