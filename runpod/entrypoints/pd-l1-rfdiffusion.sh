#!/usr/bin/env bash
# PD-L1 RFdiffusion binder-design entrypoint (canary mode).
#
# Runs RFdiffusion against the PD-L1 (4ZQK chain A) target slice to generate
# binder backbones, then feeds them through ProteinMPNN for sequence design.
# Canary defaults to 8 designs (~10-15 min on a 4090); the full wave bumps
# STRUCTURE_FACTORY_RFDIFFUSION_NUM_DESIGNS to 256.
#
# Stack: this entrypoint installs RFdiffusion + deps in-stage on top of the
# public pytorch/pytorch:2.4.0-cuda12.4-cudnn9-runtime image. The first run
# caches everything to /workspace/software/rfdiffusion/ on the campaign NV
# so re-runs skip the ~5 min install.
#
# Required env (bridge manifest runpod.env):
#   STRUCTURE_FACTORY_RUN_ID                       structure-factory-pd-l1-rfdiffusion-canary
#   STRUCTURE_FACTORY_REPO_URL                     https://github.com/BioSymphony/structure-factory.git
#   STRUCTURE_FACTORY_GIT_REF                      main or pinned SHA
#   STRUCTURE_FACTORY_VOLUME_ROOT                  /workspace/structure-factory
#   STRUCTURE_FACTORY_REPO_ROOT                    /workspace/repo
#   STRUCTURE_FACTORY_SOFTWARE_ROOT                /workspace/software
#   STRUCTURE_FACTORY_RFDIFFUSION_WEIGHTS_DIR      /workspace/software/weights/rfdiffusion
#   STRUCTURE_FACTORY_RFDIFFUSION_NUM_DESIGNS      8 (canary) | 256 (full)
#   STRUCTURE_FACTORY_RFDIFFUSION_CONTIGS          "A19-127/0 60-90"
#   STRUCTURE_FACTORY_RFDIFFUSION_HOTSPOTS         "A122,A125,A113,A121,A123"
#   STRUCTURE_FACTORY_TARGET_PDB                   absolute path to PD-L1 chain A slice PDB
#   STRUCTURE_FACTORY_MPNN_WEIGHTS_DIR             /workspace/software/weights/proteinmpnn (optional)
#   STRUCTURE_FACTORY_STAGE_CONTRACT               runpod/stage-contracts/pd-l1-rfdiffusion.stage-contract.json

set -euo pipefail

# Stage 0: fail-fast on bad GPU allocation BEFORE apt-get/pip/weights download.
# r525/r535 community hosts list a GPU via nvidia-smi but PyTorch 2.4.0+cu124
# can't initialize on them; allowedCudaVersions filter at scheduler time
# catches most, this catches the rest. Exit 97 -> bridge retries.
nvidia-smi -L >&2 || { echo "[s0] no_gpu" >&2; exit 97; }
python3 -c "import torch; t=torch.zeros(1,device='cuda'); t.add_(1).item()" >&2 || { echo "[s0] cuda_unusable" >&2; exit 97; }

RUN_ID="${STRUCTURE_FACTORY_RUN_ID:?STRUCTURE_FACTORY_RUN_ID is required}"
VOLUME_ROOT="${STRUCTURE_FACTORY_VOLUME_ROOT:-/workspace/structure-factory}"
REPO_ROOT="${STRUCTURE_FACTORY_REPO_ROOT:-/workspace/repo}"
SOFTWARE_ROOT="${STRUCTURE_FACTORY_SOFTWARE_ROOT:-/workspace/software}"
RFDIFFUSION_WEIGHTS_DIR="${STRUCTURE_FACTORY_RFDIFFUSION_WEIGHTS_DIR:-${SOFTWARE_ROOT}/weights/rfdiffusion}"
RFDIFFUSION_HOME="${STRUCTURE_FACTORY_RFDIFFUSION_HOME:-${SOFTWARE_ROOT}/rfdiffusion}"
RFDIFFUSION_REPO_URL="${STRUCTURE_FACTORY_RFDIFFUSION_REPO_URL:-https://github.com/RosettaCommons/RFdiffusion.git}"
RFDIFFUSION_REF="${STRUCTURE_FACTORY_RFDIFFUSION_REF:-2d0c003df46b9db41d119321f15403dec3716cd9}"
NUM_DESIGNS="${STRUCTURE_FACTORY_RFDIFFUSION_NUM_DESIGNS:-8}"
CONTIGS="${STRUCTURE_FACTORY_RFDIFFUSION_CONTIGS:-A19-127/0 60-90}"
HOTSPOTS="${STRUCTURE_FACTORY_RFDIFFUSION_HOTSPOTS:-A122,A125,A113,A121,A123}"
SEED="${STRUCTURE_FACTORY_RFDIFFUSION_SEED:-0}"
TARGET_PDB="${STRUCTURE_FACTORY_TARGET_PDB:-${REPO_ROOT}/campaigns/pd-l1-pd1-binder-design/structure_inputs/4ZQK_chainA_19-127.pdb}"
MPNN_WEIGHTS_DIR="${STRUCTURE_FACTORY_MPNN_WEIGHTS_DIR:-${SOFTWARE_ROOT}/weights/proteinmpnn}"
STAGE_CONTRACT="${STRUCTURE_FACTORY_STAGE_CONTRACT:-${REPO_ROOT}/runpod/stage-contracts/pd-l1-rfdiffusion.stage-contract.json}"
EXECUTION_MODE="${STRUCTURE_FACTORY_EXECUTION_MODE:-real}"
ARTIFACT_ROOT="runpod-execution/artifacts"
ENTRYPOINT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
CURRENT_STAGE=""

mkdir -p "${ARTIFACT_ROOT}/validation" "${ARTIFACT_ROOT}/rfdiffusion" "${ARTIFACT_ROOT}/mpnn" "${ARTIFACT_ROOT}/logs"
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
    sf_partial_summary "${CURRENT_STAGE}" "degraded" "bash runpod/entrypoints/pd-l1-rfdiffusion.sh" "partial"
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

if [[ ! -f "${REPO_ROOT}/runpod/entrypoints/pd-l1-rfdiffusion.sh" && -n "${STRUCTURE_FACTORY_REPO_URL:-}" ]]; then
  bash "${ENTRYPOINT_DIR}/bootstrap-repo.sh"
fi
cd "${REPO_ROOT}"

# ---------------------------------------------------------------------------
# Stage 1: manifest_preflight
# ---------------------------------------------------------------------------
CURRENT_STAGE="manifest_preflight"
sf_stage_start "${CURRENT_STAGE}" "verifying stage contract and bridge manifest references"
[[ -f "${STAGE_CONTRACT}" ]] || { sf_stage_fail "${CURRENT_STAGE}" "missing ${STAGE_CONTRACT}"; exit 1; }
python3 - "${STAGE_CONTRACT}" "${ARTIFACT_ROOT}/validation/manifest-preflight.json" \
  "${RUN_ID}" "${NUM_DESIGNS}" "${CONTIGS}" "${HOTSPOTS}" "${SEED}" <<'PY'
import hashlib, json, sys
from datetime import datetime, timezone
from pathlib import Path
contract = Path(sys.argv[1])
out = Path(sys.argv[2])
run_id, num_designs, contigs, hotspots, seed = sys.argv[3:8]
out.parent.mkdir(parents=True, exist_ok=True)
data = contract.read_bytes()
report = {
    "schema_version": 1,
    "run_id": run_id,
    "stage_contract": str(contract),
    "stage_contract_sha256": hashlib.sha256(data).hexdigest(),
    "stage_contract_bytes": len(data),
    "rfdiffusion": {
        "num_designs": int(num_designs),
        "contigs": contigs,
        "hotspots": hotspots,
        "seed": int(seed),
    },
    "verified_at": datetime.now(timezone.utc).isoformat(),
}
out.write_text(json.dumps(report, indent=2, sort_keys=True) + "\n")
PY
sf_stage_complete "${CURRENT_STAGE}" "stage contract present; RFdiffusion params recorded"
CURRENT_STAGE=""

# ---------------------------------------------------------------------------
# Stage 2: input_audit
# ---------------------------------------------------------------------------
CURRENT_STAGE="input_audit"
sf_stage_start "${CURRENT_STAGE}" "auditing target PDB + hotspots"
if [[ ! -f "${TARGET_PDB}" && "${STRUCTURE_FACTORY_ALLOW_PUBLIC_PDB_FETCH:-1}" = "1" ]]; then
  mkdir -p "$(dirname "${TARGET_PDB}")"
  FETCHED_FULL_PDB="$(dirname "${TARGET_PDB}")/4ZQK.full.pdb"
  FETCH_CMD=(curl -fsSL https://files.rcsb.org/download/4ZQK.pdb -o "${FETCHED_FULL_PDB}")
  set +e
  "${FETCH_CMD[@]}" >> "${ARTIFACT_ROOT}/logs/input_audit.log" 2>&1
  FETCH_RC=$?
  set -e
  record_command "${CURRENT_STAGE}" "${FETCH_RC}" "${FETCH_CMD[*]}"
  [[ "${FETCH_RC}" -eq 0 ]] || { sf_stage_fail "${CURRENT_STAGE}" "4ZQK public fetch rc=${FETCH_RC}"; exit "${FETCH_RC}"; }
  python3 - "${FETCHED_FULL_PDB}" "${TARGET_PDB}" <<'PY'
import sys
from pathlib import Path

source = Path(sys.argv[1])
target = Path(sys.argv[2])
target.parent.mkdir(parents=True, exist_ok=True)
selected = []
for line in source.read_text().splitlines():
    if not line.startswith(("ATOM  ", "HETATM")) or len(line) < 26:
        continue
    if line[21] != "A":
        continue
    try:
        resnum = int(line[22:26].strip())
    except ValueError:
        continue
    if 19 <= resnum <= 127:
        selected.append(line)
target.write_text("\n".join(selected + ["TER", "END"]) + "\n")
PY
  rm -f "${FETCHED_FULL_PDB}"
fi
[[ -f "${TARGET_PDB}" ]] || { sf_stage_fail "${CURRENT_STAGE}" "missing target PDB ${TARGET_PDB}"; exit 1; }
python3 - "${TARGET_PDB}" "${HOTSPOTS}" "${CONTIGS}" "${ARTIFACT_ROOT}/validation/input-audit.json" <<'PY'
import hashlib, json, sys
from datetime import datetime, timezone
from pathlib import Path
pdb = Path(sys.argv[1])
hotspots = sys.argv[2]
contigs = sys.argv[3]
out = Path(sys.argv[4])
out.parent.mkdir(parents=True, exist_ok=True)
data = pdb.read_bytes()
# Lightweight chain/resnum extraction without biopython.
chains = {}
for line in data.decode("utf-8", errors="ignore").splitlines():
    if line.startswith("ATOM") and len(line) >= 22:
        chain_id = line[21]
        try:
            resnum = int(line[22:26].strip())
        except ValueError:
            continue
        chains.setdefault(chain_id, set()).add(resnum)
chain_summary = {
    cid: {
        "residue_count": len(resnums),
        "resnum_min": min(resnums),
        "resnum_max": max(resnums),
    }
    for cid, resnums in chains.items()
}
report = {
    "schema_version": 1,
    "target_pdb": str(pdb),
    "target_pdb_sha256": hashlib.sha256(data).hexdigest(),
    "target_pdb_bytes": len(data),
    "chains": chain_summary,
    "hotspots": hotspots.split(",") if hotspots else [],
    "contigs": contigs,
    "target_label": "PD-L1",
    "source_pdb": "4ZQK",
    "verified_at": datetime.now(timezone.utc).isoformat(),
}
out.write_text(json.dumps(report, indent=2, sort_keys=True) + "\n")
PY
sf_stage_complete "${CURRENT_STAGE}" "target PDB hashed; hotspot list confirmed"
CURRENT_STAGE=""

# ---------------------------------------------------------------------------
# Stage 3: rfdiffusion_install (clone + pip install, cached to NV)
# ---------------------------------------------------------------------------
CURRENT_STAGE="rfdiffusion_install"
sf_stage_start "${CURRENT_STAGE}" "installing RFdiffusion + deps (cached to NV)"
mkdir -p "${SOFTWARE_ROOT}"
SENTINEL_DIR="${SOFTWARE_ROOT}/sentinels"
mkdir -p "${SENTINEL_DIR}"
RFD_SENTINEL="${SENTINEL_DIR}/rfdiffusion.${RFDIFFUSION_REF}.installed"

# Clone (or refresh) RFdiffusion to NV-persistent path.
if [[ ! -d "${RFDIFFUSION_HOME}/.git" ]]; then
  CLONE_CMD=(git clone "${RFDIFFUSION_REPO_URL}" "${RFDIFFUSION_HOME}")
  set +e
  "${CLONE_CMD[@]}" >> "${ARTIFACT_ROOT}/logs/rfdiffusion_install.log" 2>&1
  CLONE_RC=$?
  set -e
  record_command "${CURRENT_STAGE}" "${CLONE_RC}" "${CLONE_CMD[*]}"
  [[ "${CLONE_RC}" -eq 0 ]] || { sf_stage_fail "${CURRENT_STAGE}" "git clone rc=${CLONE_RC}"; exit "${CLONE_RC}"; }
fi
git -C "${RFDIFFUSION_HOME}" fetch --all --tags --prune >> "${ARTIFACT_ROOT}/logs/rfdiffusion_install.log" 2>&1 || true
if git -C "${RFDIFFUSION_HOME}" rev-parse --verify --quiet "${RFDIFFUSION_REF}^{commit}" >/dev/null; then
  git -C "${RFDIFFUSION_HOME}" checkout --detach "${RFDIFFUSION_REF}" >> "${ARTIFACT_ROOT}/logs/rfdiffusion_install.log" 2>&1
elif git -C "${RFDIFFUSION_HOME}" rev-parse --verify --quiet "origin/${RFDIFFUSION_REF}^{commit}" >/dev/null; then
  git -C "${RFDIFFUSION_HOME}" checkout --detach "origin/${RFDIFFUSION_REF}" >> "${ARTIFACT_ROOT}/logs/rfdiffusion_install.log" 2>&1
else
  sf_stage_fail "${CURRENT_STAGE}" "RFDIFFUSION_REF=${RFDIFFUSION_REF} did not resolve"
  exit 1
fi
RFDIFFUSION_ACTUAL_SHA="$(git -C "${RFDIFFUSION_HOME}" rev-parse HEAD)"

# Pip-install deps on top of pytorch:2.4.0-cuda12.4-cudnn9-runtime (torch
# already present). Skip if sentinel says we already installed this SHA.
if [[ -f "${RFD_SENTINEL}" ]]; then
  echo "[rfdiffusion_install] sentinel present for ${RFDIFFUSION_ACTUAL_SHA}; skipping pip install" \
    >> "${ARTIFACT_ROOT}/logs/rfdiffusion_install.log"
else
  PIP_DEPS=(
    "numpy<2"
    "scipy"
    "biopython"
    "e3nn==0.5.1"
    "hydra-core==1.3.2"
    "wandb"
    "pynvml"
    "decorator"
    "pyrsistent"
    "icecream"
    "omegaconf"
    "opt_einsum"
  )
  PIP_CMD=(pip install --no-cache-dir "${PIP_DEPS[@]}")
  set +e
  "${PIP_CMD[@]}" >> "${ARTIFACT_ROOT}/logs/rfdiffusion_install.log" 2>&1
  PIP_RC=$?
  set -e
  record_command "${CURRENT_STAGE}" "${PIP_RC}" "${PIP_CMD[*]}"
  [[ "${PIP_RC}" -eq 0 ]] || { sf_stage_fail "${CURRENT_STAGE}" "pip install deps rc=${PIP_RC}"; exit "${PIP_RC}"; }

  # dgl 1.1.3+cu121: pin the LOCAL VERSION explicitly, otherwise pip resolves
  # 'dgl==1.1.3' against PyPI's CPU-only wheel even with --extra-index-url.
  # Use --find-links so only the DGL index is consulted for this package.
  echo "[rfdiffusion_install] installing dgl==1.1.3+cu121 from cu121 wheel index" \
    >> "${ARTIFACT_ROOT}/logs/rfdiffusion_install.log"
  set +e
  pip install --no-cache-dir 'dgl==1.1.3+cu121' \
    -f https://data.dgl.ai/wheels/cu121/repo.html \
    >> "${ARTIFACT_ROOT}/logs/rfdiffusion_install.log" 2>&1
  DGL_RC=$?
  set -e
  echo "[rfdiffusion_install] dgl install rc=${DGL_RC}" \
    >> "${ARTIFACT_ROOT}/logs/rfdiffusion_install.log"
  record_command "${CURRENT_STAGE}" "${DGL_RC}" "pip install dgl --extra-index cu121"
  if [[ "${DGL_RC}" -ne 0 ]]; then
    echo "[rfdiffusion_install] dgl install failed (rc=${DGL_RC}); continuing — SE3Transformer install will likely fail" \
      >> "${ARTIFACT_ROOT}/logs/rfdiffusion_install.log"
  fi

  set +e
  pip install --no-cache-dir "${RFDIFFUSION_HOME}/env/SE3Transformer" \
    >> "${ARTIFACT_ROOT}/logs/rfdiffusion_install.log" 2>&1
  SE3_RC=$?
  set -e
  record_command "${CURRENT_STAGE}" "${SE3_RC}" "pip install SE3Transformer"
  [[ "${SE3_RC}" -eq 0 ]] || { sf_stage_fail "${CURRENT_STAGE}" "SE3Transformer install rc=${SE3_RC}"; exit "${SE3_RC}"; }

  RFD_PIP_CMD=(pip install --no-cache-dir -e "${RFDIFFUSION_HOME}")
  set +e
  "${RFD_PIP_CMD[@]}" >> "${ARTIFACT_ROOT}/logs/rfdiffusion_install.log" 2>&1
  RFD_PIP_RC=$?
  set -e
  record_command "${CURRENT_STAGE}" "${RFD_PIP_RC}" "${RFD_PIP_CMD[*]}"
  [[ "${RFD_PIP_RC}" -eq 0 ]] || { sf_stage_fail "${CURRENT_STAGE}" "RFdiffusion install rc=${RFD_PIP_RC}"; exit "${RFD_PIP_RC}"; }

  touch "${RFD_SENTINEL}"
fi

python3 - "${RFDIFFUSION_HOME}" "${RFDIFFUSION_ACTUAL_SHA}" "${RFDIFFUSION_REF}" "${ARTIFACT_ROOT}/validation/rfdiffusion_install.json" <<'PY'
import json, shutil, subprocess, sys
from datetime import datetime, timezone
from pathlib import Path
home = Path(sys.argv[1])
actual_sha = sys.argv[2]
ref = sys.argv[3]
out = Path(sys.argv[4])
out.parent.mkdir(parents=True, exist_ok=True)
def safe_version(pkg):
    try:
        import importlib.metadata as m
        return m.version(pkg)
    except Exception:
        return None
report = {
    "schema_version": 1,
    "rfdiffusion_home": str(home),
    "rfdiffusion_requested_ref": ref,
    "rfdiffusion_actual_sha": actual_sha,
    "run_inference_present": (home / "scripts" / "run_inference.py").is_file(),
    "torch": safe_version("torch"),
    "dgl": safe_version("dgl"),
    "e3nn": safe_version("e3nn"),
    "hydra-core": safe_version("hydra-core"),
    "numpy": safe_version("numpy"),
    "biopython": safe_version("biopython"),
    "verified_at": datetime.now(timezone.utc).isoformat(),
}
out.write_text(json.dumps(report, indent=2, sort_keys=True) + "\n")
PY

sf_stage_complete "${CURRENT_STAGE}" "RFdiffusion installed (sha=${RFDIFFUSION_ACTUAL_SHA})"
CURRENT_STAGE=""

# ---------------------------------------------------------------------------
# Stage 4: rfdiffusion_weights_check
# ---------------------------------------------------------------------------
CURRENT_STAGE="rfdiffusion_weights_check"
sf_stage_start "${CURRENT_STAGE}" "verifying RFdiffusion weights cache at ${RFDIFFUSION_WEIGHTS_DIR}"
mkdir -p "${RFDIFFUSION_WEIGHTS_DIR}"

# 483 MB ckpt. Public repo does not bless a checkpoint mirror or terms posture.
# Operators must provide reviewed sources and an explicit terms/use-context ack.
if [[ "${STRUCTURE_FACTORY_RFDIFFUSION_TERMS_ACK:-}" != "I_HAVE_REVIEWED_RFDIFFUSION_TERMS_AND_SOURCES" ]]; then
  sf_stage_fail "${CURRENT_STAGE}" "RFdiffusion checkpoint download requires STRUCTURE_FACTORY_RFDIFFUSION_TERMS_ACK=I_HAVE_REVIEWED_RFDIFFUSION_TERMS_AND_SOURCES"
  exit 2
fi
if [[ -z "${STRUCTURE_FACTORY_RFDIFFUSION_WEIGHTS_HF_REPO:-}" && -z "${STRUCTURE_FACTORY_RFDIFFUSION_CKPT_URL:-}" ]]; then
  sf_stage_fail "${CURRENT_STAGE}" "RFdiffusion checkpoint source must be provided by the operator after terms review"
  exit 2
fi
RFDIFFUSION_WEIGHTS_HF_REPO="${STRUCTURE_FACTORY_RFDIFFUSION_WEIGHTS_HF_REPO:-__OPERATOR_REVIEWED_RFDIFFUSION_REPO__}"
RFDIFFUSION_WEIGHTS_HF_REV="${STRUCTURE_FACTORY_RFDIFFUSION_WEIGHTS_HF_REV:-3cdaa7d9e22dbdf085abbd16f17b4dc31995ce4d}"
RFDIFFUSION_CKPT_IPD_KEY="${STRUCTURE_FACTORY_RFDIFFUSION_CKPT_IPD_KEY:-e29311f6f1bf1af907f9ef9f44b8328b}"
RFDIFFUSION_CKPT_SHA256="${STRUCTURE_FACTORY_RFDIFFUSION_CKPT_SHA256:-76e4e260aefee3b582bd76b77ab95d2592e64f00c51bf344968ab9239f3250bc}"
RFDIFFUSION_CKPT_HF_URL="https://huggingface.co/${RFDIFFUSION_WEIGHTS_HF_REPO}/resolve/${RFDIFFUSION_WEIGHTS_HF_REV}/models/Complex_base_ckpt.pt"
RFDIFFUSION_CKPT_IPD_URL="${STRUCTURE_FACTORY_RFDIFFUSION_CKPT_URL:-http://files.ipd.uw.edu/pub/RFdiffusion/${RFDIFFUSION_CKPT_IPD_KEY}/Complex_base_ckpt.pt}"
DOWNLOAD_LOG="${ARTIFACT_ROOT}/logs/rfdiffusion_weights_download.log"
TARGET_CKPT="${RFDIFFUSION_WEIGHTS_DIR}/Complex_base_ckpt.pt"

echo "[stage4d] curl=$(command -v curl) sha256sum=$(command -v sha256sum)" >&2

ckpt_hash_ok() {
  local actual
  actual="$(sha256sum "$1" 2>/dev/null | awk '{print $1}')"
  [[ "${actual}" == "${RFDIFFUSION_CKPT_SHA256}" ]]
}

if [[ -f "${TARGET_CKPT}" ]] && ckpt_hash_ok "${TARGET_CKPT}"; then
  echo "[stage4] Complex_base_ckpt.pt present + md5 verified, skipping download" \
    >> "${DOWNLOAD_LOG}"
else
  if [[ -f "${TARGET_CKPT}" ]]; then
    echo "[stage4] Existing checkpoint failed md5 check, re-downloading" >> "${DOWNLOAD_LOG}"
    rm -f "${TARGET_CKPT}"
  fi
  PARTIAL="${TARGET_CKPT}.partial"
  CKPT_OK=0
  for SOURCE_NAME in HF IPD; do
    if [[ "${SOURCE_NAME}" == "HF" ]]; then
      CKPT_URL="${RFDIFFUSION_CKPT_HF_URL}"
    else
      CKPT_URL="${RFDIFFUSION_CKPT_IPD_URL}"
    fi
    echo "[stage4d] try ${SOURCE_NAME}" >&2
    set +e
    curl -fSL --retry 3 --retry-delay 5 --max-time 1800 \
        "${CKPT_URL}" -o "${PARTIAL}" >> "${DOWNLOAD_LOG}" 2>&1
    CURL_RC=$?
    set -e
    if [[ "${CURL_RC}" -eq 0 ]]; then
      PSIZE=$(stat -c %s "${PARTIAL}" 2>/dev/null || echo 0)
      if ckpt_hash_ok "${PARTIAL}"; then
        mv "${PARTIAL}" "${TARGET_CKPT}"
        echo "[stage4d] ${SOURCE_NAME} OK size=${PSIZE}" >&2
        CKPT_OK=1
        break
      else
        echo "[stage4d] ${SOURCE_NAME} md5 mismatch size=${PSIZE}" >&2
        rm -f "${PARTIAL}"
      fi
    else
      echo "[stage4d] ${SOURCE_NAME} curl rc=${CURL_RC}" >&2
      rm -f "${PARTIAL}"
    fi
  done
  if [[ "${CKPT_OK}" -eq 0 ]]; then
    echo "[stage4d] all mirrors failed; dump:" >&2
    cat "${DOWNLOAD_LOG}" >&2 2>/dev/null || true
    ls -la "${RFDIFFUSION_WEIGHTS_DIR}/" >&2 2>/dev/null || true
  fi
fi

python3 - "${RFDIFFUSION_WEIGHTS_DIR}" "${ARTIFACT_ROOT}/validation/rfdiffusion_weights_manifest.json" <<'PY'
import json, sys
from datetime import datetime, timezone
from pathlib import Path
weights_dir = Path(sys.argv[1])
out = Path(sys.argv[2])
out.parent.mkdir(parents=True, exist_ok=True)
files = []
total = 0
for path in sorted(weights_dir.rglob("*")):
    if path.is_file():
        size = path.stat().st_size
        total += size
        files.append({"path": str(path.relative_to(weights_dir)), "size": size})
required_for_ppi = "Complex_base_ckpt.pt"
have_required = any(f["path"].endswith(required_for_ppi) for f in files)
report = {
    "schema_version": 1,
    "weights_dir": str(weights_dir),
    "file_count": len(files),
    "total_bytes": total,
    "files": files,
    "required_for_ppi": required_for_ppi,
    "have_required": have_required,
    "verified_at": datetime.now(timezone.utc).isoformat(),
    "cache_state": "populated" if files else "empty_will_populate_on_first_run",
}
out.write_text(json.dumps(report, indent=2, sort_keys=True) + "\n")
if not have_required:
    raise SystemExit(
        f"RFdiffusion PPI checkpoint {required_for_ppi} missing under {weights_dir}; "
        "run scripts/runpod/bootstrap_structure_factory_nv.sh with RFDIFFUSION_DOWNLOAD_WEIGHTS=1 first"
    )
PY
sf_stage_complete "${CURRENT_STAGE}" "Complex_base_ckpt.pt present"
CURRENT_STAGE=""

# ---------------------------------------------------------------------------
# Stage 5: rfdiffusion_design
# ---------------------------------------------------------------------------
CURRENT_STAGE="rfdiffusion_design"
sf_stage_start "${CURRENT_STAGE}" "RFdiffusion design: ${NUM_DESIGNS} backbones, hotspots=${HOTSPOTS}"
DESIGN_OUT_DIR="${ARTIFACT_ROOT}/rfdiffusion"
OUTPUT_PREFIX="${DESIGN_OUT_DIR}/design"
CHECKPOINT_PATH="${RFDIFFUSION_WEIGHTS_DIR}/Complex_base_ckpt.pt"

RFD_CMD=(python "${RFDIFFUSION_HOME}/scripts/run_inference.py"
  "inference.input_pdb=${TARGET_PDB}"
  "inference.output_prefix=${OUTPUT_PREFIX}"
  "inference.num_designs=${NUM_DESIGNS}"
  "inference.ckpt_override_path=${CHECKPOINT_PATH}"
  "contigmap.contigs=[${CONTIGS}]"
  "ppi.hotspot_res=[${HOTSPOTS}]"
  "denoiser.noise_scale_ca=0"
  "denoiser.noise_scale_frame=0")
if [[ "${SEED}" != "0" ]]; then
  RFD_CMD+=("inference.seed=${SEED}")
fi

echo "[s5d] cmd=${RFD_CMD[*]}" >&2
export HYDRA_FULL_ERROR=1
set +e
"${RFD_CMD[@]}" 2>&1 | tee -a "${ARTIFACT_ROOT}/logs/rfdiffusion_design.log" >&2
RFD_RC=${PIPESTATUS[0]}
set -e
echo "[s5d] rc=${RFD_RC}" >&2
record_command "${CURRENT_STAGE}" "${RFD_RC}" "${RFD_CMD[*]}"
if [[ "${RFD_RC}" -ne 0 ]]; then
  sf_stage_fail "${CURRENT_STAGE}" "rfdiffusion exit ${RFD_RC}"
  exit "${RFD_RC}"
fi
sf_stage_complete "${CURRENT_STAGE}" "rfdiffusion exit 0"
CURRENT_STAGE=""

# ---------------------------------------------------------------------------
# Stage 6: rfdiffusion_postprocess
# ---------------------------------------------------------------------------
CURRENT_STAGE="rfdiffusion_postprocess"
sf_stage_start "${CURRENT_STAGE}" "hashing design_*.pdb and emitting rfdiffusion_manifest.json"
python3 - "${DESIGN_OUT_DIR}" "${OUTPUT_PREFIX}" "${RFDIFFUSION_ACTUAL_SHA}" \
  "${CHECKPOINT_PATH}" "${NUM_DESIGNS}" "${CONTIGS}" "${HOTSPOTS}" "${SEED}" \
  "${TARGET_PDB}" "${ARTIFACT_ROOT}/validation/rfdiffusion_postprocess.json" <<'PY'
import hashlib, json, re, sys
from datetime import datetime, timezone
from pathlib import Path

design_dir = Path(sys.argv[1])
output_prefix = sys.argv[2]
rfd_sha = sys.argv[3]
ckpt = sys.argv[4]
num_designs = int(sys.argv[5])
contigs = sys.argv[6]
hotspots = sys.argv[7]
seed = int(sys.argv[8])
target_pdb = sys.argv[9]
report_path = Path(sys.argv[10])
report_path.parent.mkdir(parents=True, exist_ok=True)
design_dir.mkdir(parents=True, exist_ok=True)

def sha256_of_file(p: Path) -> str:
    h = hashlib.sha256()
    with p.open("rb") as fh:
        for chunk in iter(lambda: fh.read(1024 * 1024), b""):
            h.update(chunk)
    return h.hexdigest()

# RFdiffusion writes <prefix>_0.pdb, <prefix>_1.pdb, ...
prefix_path = Path(output_prefix)
prefix_stem = prefix_path.name
pattern = re.compile(rf"^{re.escape(prefix_stem)}_(\d+)\.pdb$")
designs = []
for path in sorted(prefix_path.parent.glob(f"{prefix_stem}_*.pdb")):
    m = pattern.match(path.name)
    if not m:
        continue
    designs.append({
        "index": int(m.group(1)),
        "path": str(path.relative_to(design_dir.parent.parent)) if design_dir.parent.parent in path.parents else str(path),
        "size": path.stat().st_size,
        "sha256": sha256_of_file(path),
    })

manifest = {
    "schema_version": 1,
    "designer": "rfdiffusion",
    "rfdiffusion_sha": rfd_sha,
    "checkpoint_path": ckpt,
    "checkpoint_basename": Path(ckpt).name,
    "num_designs_requested": num_designs,
    "num_designs_produced": len(designs),
    "contigs": contigs,
    "hotspots": hotspots.split(",") if hotspots else [],
    "seed": seed,
    "target_pdb": target_pdb,
    "designs": designs,
    "generated_at": datetime.now(timezone.utc).isoformat(),
}
(design_dir / "rfdiffusion_manifest.json").write_text(
    json.dumps(manifest, indent=2, sort_keys=True) + "\n"
)
report_path.write_text(json.dumps({
    "schema_version": 1,
    "num_designs_produced": len(designs),
    "design_files": [d["path"] for d in designs],
    "manifest_path": str(design_dir / "rfdiffusion_manifest.json"),
    "verified_at": datetime.now(timezone.utc).isoformat(),
}, indent=2, sort_keys=True) + "\n")
if len(designs) == 0:
    raise SystemExit(f"no design_*.pdb produced under {design_dir}")
PY
sf_stage_complete "${CURRENT_STAGE}" "design PDBs hashed; rfdiffusion_manifest.json emitted"
CURRENT_STAGE=""

# ---------------------------------------------------------------------------
# Stage 7: mpnn_sequence_design — reuse the established ProteinMPNN pattern
# ---------------------------------------------------------------------------
CURRENT_STAGE="mpnn_sequence_design"
sf_stage_start "${CURRENT_STAGE}" "ProteinMPNN sequence design over RFdiffusion backbones"

# Source the proteinmpnn conda env if it's preinstalled on the NV; otherwise
# fall back to inline pip-installed torch from the base image.
if [[ -f "${SOFTWARE_ROOT}/miniconda3/etc/profile.d/conda.sh" ]]; then
  # shellcheck disable=SC1091
  source "${SOFTWARE_ROOT}/miniconda3/etc/profile.d/conda.sh"
  if [[ -d "${SOFTWARE_ROOT}/envs/proteinmpnn" ]]; then
    conda activate "${SOFTWARE_ROOT}/envs/proteinmpnn" || true
  fi
fi
MPNN_SCRIPT="${SOFTWARE_ROOT}/envs/proteinmpnn/ProteinMPNN/protein_mpnn_run.py"
if [[ ! -f "${MPNN_SCRIPT}" ]]; then
  MPNN_SCRIPT="${SOFTWARE_ROOT}/ProteinMPNN/protein_mpnn_run.py"
fi
if [[ ! -f "${MPNN_SCRIPT}" ]]; then
  echo "[mpnn_sequence_design] ProteinMPNN not preinstalled on NV; cloning to ${SOFTWARE_ROOT}/ProteinMPNN" \
    >> "${ARTIFACT_ROOT}/logs/mpnn_sequence_design.log"
  CLONE_CMD=(git clone https://github.com/dauparas/ProteinMPNN "${SOFTWARE_ROOT}/ProteinMPNN")
  set +e
  "${CLONE_CMD[@]}" >> "${ARTIFACT_ROOT}/logs/mpnn_sequence_design.log" 2>&1
  CR=$?
  set -e
  record_command "${CURRENT_STAGE}" "${CR}" "${CLONE_CMD[*]}"
  MPNN_SCRIPT="${SOFTWARE_ROOT}/ProteinMPNN/protein_mpnn_run.py"
fi
[[ -f "${MPNN_SCRIPT}" ]] || { sf_stage_fail "${CURRENT_STAGE}" "ProteinMPNN script unavailable at ${MPNN_SCRIPT}"; exit 1; }

MPNN_OUT_DIR="${ARTIFACT_ROOT}/mpnn"
mkdir -p "${MPNN_OUT_DIR}"

# Per-design MPNN run; collect FASTAs into a single sequences.fasta.
: > "${MPNN_OUT_DIR}/sequences.fasta"
DESIGN_COUNT=0
for design_pdb in "${DESIGN_OUT_DIR}"/design_*.pdb; do
  [[ -f "${design_pdb}" ]] || continue
  DESIGN_BASENAME="$(basename "${design_pdb}" .pdb)"
  MPNN_WORKDIR="${MPNN_OUT_DIR}/${DESIGN_BASENAME}"
  mkdir -p "${MPNN_WORKDIR}"
  MPNN_CMD=(python "${MPNN_SCRIPT}"
    --pdb_path "${design_pdb}"
    --out_folder "${MPNN_WORKDIR}"
    --num_seq_per_target 2
    --sampling_temp 0.1
    --seed 37
    --batch_size 1)
  set +e
  "${MPNN_CMD[@]}" >> "${ARTIFACT_ROOT}/logs/mpnn_sequence_design.log" 2>&1
  MPNN_RC=$?
  set -e
  record_command "${CURRENT_STAGE}" "${MPNN_RC}" "${MPNN_CMD[*]}"
  if [[ "${MPNN_RC}" -ne 0 ]]; then
    sf_stage_fail "${CURRENT_STAGE}" "ProteinMPNN failed on ${design_pdb} rc=${MPNN_RC}"
    exit "${MPNN_RC}"
  fi
  # Append all FASTAs from this design's seqs/ subdirectory.
  if [[ -d "${MPNN_WORKDIR}/seqs" ]]; then
    for fa in "${MPNN_WORKDIR}/seqs"/*.fa "${MPNN_WORKDIR}/seqs"/*.fasta; do
      [[ -f "${fa}" ]] || continue
      cat "${fa}" >> "${MPNN_OUT_DIR}/sequences.fasta"
    done
  fi
  DESIGN_COUNT=$((DESIGN_COUNT + 1))
done

python3 - "${MPNN_OUT_DIR}" "${DESIGN_COUNT}" "${ARTIFACT_ROOT}/validation/mpnn_sequence_design.json" <<'PY'
import json, sys
from datetime import datetime, timezone
from pathlib import Path
out_dir = Path(sys.argv[1])
design_count = int(sys.argv[2])
report = Path(sys.argv[3])
report.parent.mkdir(parents=True, exist_ok=True)
fasta = out_dir / "sequences.fasta"
sequences = 0
total_bytes = 0
if fasta.is_file():
    total_bytes = fasta.stat().st_size
    for line in fasta.read_text().splitlines():
        if line.startswith(">"):
            sequences += 1
report.write_text(json.dumps({
    "schema_version": 1,
    "sequences_fasta": str(fasta),
    "sequences_fasta_bytes": total_bytes,
    "sequence_count": sequences,
    "designs_processed": design_count,
    "verified_at": datetime.now(timezone.utc).isoformat(),
}, indent=2, sort_keys=True) + "\n")
if sequences == 0:
    raise SystemExit("ProteinMPNN produced 0 sequences")
PY
sf_stage_complete "${CURRENT_STAGE}" "ProteinMPNN sequences collected"
CURRENT_STAGE=""

# ---------------------------------------------------------------------------
# Stage 8: boltz_cofold (optional — runs if STRUCTURE_FACTORY_RUN_COFOLD=1)
# ---------------------------------------------------------------------------
if [[ "${STRUCTURE_FACTORY_RUN_COFOLD:-1}" = "1" ]]; then
  CURRENT_STAGE="boltz_cofold"
  sf_stage_start "${CURRENT_STAGE}" "Boltz cofold each RFdiffusion design against PD-L1"

  echo "[boltz_cofold] installing boltz 2.2.1 (no torchvision swap; DGL coexists)" \
    >> "${ARTIFACT_ROOT}/logs/boltz_cofold.log"
  set +e
  pip install --no-cache-dir 'boltz==2.2.1' \
    >> "${ARTIFACT_ROOT}/logs/boltz_cofold.log" 2>&1
  BOLTZ_INSTALL_RC=$?
  if [[ "${BOLTZ_INSTALL_RC}" -eq 0 ]]; then
    pip install --no-cache-dir 'numpy<2.2' \
      >> "${ARTIFACT_ROOT}/logs/boltz_cofold.log" 2>&1 || true
  fi
  set -e
  record_command "${CURRENT_STAGE}" "${BOLTZ_INSTALL_RC}" "pip install boltz==2.2.1 + pins"
  [[ "${BOLTZ_INSTALL_RC}" -eq 0 ]] || { sf_stage_fail "${CURRENT_STAGE}" "boltz install rc=${BOLTZ_INSTALL_RC}"; exit "${BOLTZ_INSTALL_RC}"; }

  COFOLD_SCRIPT="${REPO_ROOT}/scripts/structure_factory/boltz_cofold_rfdiffusion.py"
  if [[ ! -f "${COFOLD_SCRIPT}" ]]; then
    echo "[boltz_cofold] runner not found at ${COFOLD_SCRIPT}; skipping cofold stage" \
      >> "${ARTIFACT_ROOT}/logs/boltz_cofold.log"
    sf_stage_complete "${CURRENT_STAGE}" "runner absent — skipped"
  else
    BOLTZ_CACHE_DIR="${BOLTZ_CACHE:-${SOFTWARE_ROOT}/weights/boltz}"
    mkdir -p "${BOLTZ_CACHE_DIR}"
    MAX_COFOLDS="${STRUCTURE_FACTORY_COFOLD_MAX:-16}"
    MAX_SEQS_PER_DESIGN="${STRUCTURE_FACTORY_COFOLD_SEQS_PER_DESIGN:-2}"
    COFOLD_CMD=(python3 "${COFOLD_SCRIPT}"
      --artifact-root "${ARTIFACT_ROOT}"
      --target-pdb "${TARGET_PDB}"
      --target-chain A
      --max-cofolds "${MAX_COFOLDS}"
      --max-seqs-per-design "${MAX_SEQS_PER_DESIGN}"
      --boltz-cache "${BOLTZ_CACHE_DIR}")
    set +e
    "${COFOLD_CMD[@]}" >> "${ARTIFACT_ROOT}/logs/boltz_cofold.log" 2>&1
    COFOLD_RC=$?
    set -e
    record_command "${CURRENT_STAGE}" "${COFOLD_RC}" "${COFOLD_CMD[*]}"
    if [[ "${COFOLD_RC}" -ne 0 ]]; then
      sf_stage_fail "${CURRENT_STAGE}" "boltz_cofold runner rc=${COFOLD_RC}"
      exit "${COFOLD_RC}"
    fi
    sf_stage_complete "${CURRENT_STAGE}" "candidate_ranking.json emitted"
  fi
  CURRENT_STAGE=""
fi

# ---------------------------------------------------------------------------
# Stage 9: contract_self_check
# ---------------------------------------------------------------------------
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
    "rfdiffusion/rfdiffusion_manifest.json",
    "mpnn/sequences.fasta",
    "validation/manifest-preflight.json",
    "validation/input-audit.json",
    "validation/rfdiffusion_install.json",
    "validation/rfdiffusion_weights_manifest.json",
    "validation/rfdiffusion_postprocess.json",
    "validation/mpnn_sequence_design.json",
    "stage-progress.jsonl",
    "executed-commands.jsonl",
]
missing = [rel for rel in required if not (root / rel).is_file()]

# Confirm at least one design_*.pdb exists and is non-empty.
design_pdbs = sorted((root / "rfdiffusion").glob("design_*.pdb"))
design_pdbs_nonempty = [p for p in design_pdbs if p.stat().st_size > 0]
designs_ok = len(design_pdbs_nonempty) > 0

# Pull num_designs_produced for the status report.
num_produced = None
manifest = root / "rfdiffusion" / "rfdiffusion_manifest.json"
if manifest.is_file():
    try:
        num_produced = json.loads(manifest.read_text()).get("num_designs_produced")
    except Exception:
        num_produced = None

ok = (not missing) and designs_ok
report = {
    "schema_version": 1,
    "ok": ok,
    "run_id": run_id,
    "stage_contract_ref": str(stage_contract_path),
    "missing_artifacts": missing,
    "num_designs_produced": num_produced,
    "designs_nonempty": len(design_pdbs_nonempty),
    "claim_level_ceiling": "candidate",
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
    "num_designs_produced": num_produced,
    "missing_artifacts": missing,
    "artifact_root": str(root),
    "completed_at": datetime.now(timezone.utc).isoformat(),
}
(root.parent / "status.json").write_text(json.dumps(status, indent=2, sort_keys=True) + "\n")
if not ok:
    raise SystemExit(f"contract self-check failed: missing={missing} designs_nonempty={len(design_pdbs_nonempty)}")
PY
sf_stage_complete "${CURRENT_STAGE}" "contract self-check ok"
CURRENT_STAGE=""

set +e
tar -czf /tmp/rpe.tar.gz -C "${ARTIFACT_ROOT}" .
TAR_RC=$?
set -e
[[ "${TAR_RC}" -eq 0 ]] || { echo "[archive] rc=${TAR_RC}" >&2; exit "${TAR_RC}"; }
mv /tmp/rpe.tar.gz "${ARTIFACT_ROOT}/runpod-execution.tar.gz"

echo "pd-l1-rfdiffusion complete: ${RUN_ID} -> ${ARTIFACT_ROOT}"
