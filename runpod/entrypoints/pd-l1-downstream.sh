#!/usr/bin/env bash
# PD-L1 / PD-1 downstream-only entrypoint.
#
# This public entrypoint is a downstream template. It expects an operator-gated
# runtime artifact root containing a declared design_candidates/ manifest set,
# a target-window report, and reviewed Boltz runtime setup. It never publishes
# private provider state, concrete pod IDs, accepted-license records, or
# generated structures in git. It fires only the later stages of the runner:
#
#   1. boltz_crosscheck_extended  (cofold all 38 reconstructed candidates)
#   2. ranking_synthesis             (rank top binders)
#   3. report                     (HTML + markdown)
#   4. validation_review                (validation ledger, methods, provenance, closeout)
#   5. contract_self_check        (final fail-closed gate)
#
# The runner reconstructs generation metadata from each declared
# design_candidates/<cid>/manifest.json plus resolved structure_path.
#
# Required env (bridge manifest runpod.env):
#   STRUCTURE_FACTORY_RUN_ID                       structure-factory-pd-l1-downstream-cofold
#   STRUCTURE_FACTORY_REPO_URL                     https://github.com/BioSymphony/structure-factory.git
#   STRUCTURE_FACTORY_GIT_REF                      main or pinned SHA
#   STRUCTURE_FACTORY_VOLUME_ROOT                  /workspace/structure-factory
#   STRUCTURE_FACTORY_REPO_ROOT                    /workspace/repo
#   STRUCTURE_FACTORY_SOFTWARE_ROOT                /workspace/software
#   STRUCTURE_FACTORY_BOLTZ_WEIGHTS_DIR            /workspace/software/weights/boltz
#   STRUCTURE_FACTORY_ARTIFACT_ROOT                /workspace/runpod-execution/artifacts
#   STRUCTURE_FACTORY_MVD_ROOT                     /workspace/runpod-execution/mvd
#   STRUCTURE_FACTORY_STAGE_CONTRACT               runpod/stage-contracts/pd-l1-downstream.stage-contract.json
#   STRUCTURE_FACTORY_TERMINAL_STATE               complete_tiny_tranche (default)

set -euo pipefail

RUN_ID="${STRUCTURE_FACTORY_RUN_ID:?STRUCTURE_FACTORY_RUN_ID is required}"
VOLUME_ROOT="${STRUCTURE_FACTORY_VOLUME_ROOT:-/workspace/structure-factory}"
REPO_ROOT="${STRUCTURE_FACTORY_REPO_ROOT:-/workspace/repo}"
SOFTWARE_ROOT="${STRUCTURE_FACTORY_SOFTWARE_ROOT:-/workspace/software}"
BOLTZ_WEIGHTS_DIR="${STRUCTURE_FACTORY_BOLTZ_WEIGHTS_DIR:-${SOFTWARE_ROOT}/weights/boltz}"
ARTIFACT_ROOT_ABS="${STRUCTURE_FACTORY_ARTIFACT_ROOT:-/workspace/runpod-execution/artifacts}"
MVD_ROOT_ABS="${STRUCTURE_FACTORY_MVD_ROOT:-/workspace/runpod-execution/mvd}"
STAGE_CONTRACT="${STRUCTURE_FACTORY_STAGE_CONTRACT:-${REPO_ROOT}/runpod/stage-contracts/pd-l1-downstream.stage-contract.json}"
TERMINAL_STATE="${STRUCTURE_FACTORY_TERMINAL_STATE:-complete_tiny_tranche}"
EXECUTION_MODE="${STRUCTURE_FACTORY_EXECUTION_MODE:-real}"
ENTRYPOINT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
CURRENT_STAGE=""

# Stages this entrypoint owns — kept in lock-step with pd-l1-downstream
# stage-contract.json and the runner's STAGE_ORDER tail.
RUNNER_STAGES=(
  "boltz_crosscheck_extended"
  "ranking_synthesis"
  "report"
  "validation_review"
  "contract_self_check"
)

mkdir -p "${ARTIFACT_ROOT_ABS}/validation" "${ARTIFACT_ROOT_ABS}/boltz_crosscheck" "${ARTIFACT_ROOT_ABS}/report" "${ARTIFACT_ROOT_ABS}/logs"
export STRUCTURE_FACTORY_STAGE_PROGRESS="${ARTIFACT_ROOT_ABS}/stage-progress.jsonl"
# shellcheck disable=SC1091
source "${ENTRYPOINT_DIR}/stage-progress.sh"

EXECUTED_COMMANDS="${ARTIFACT_ROOT_ABS}/executed-commands.jsonl"
# Append rather than truncate so an operator-gated resumed runtime can preserve
# any partial ledger already present in the artifact root.
touch "${EXECUTED_COMMANDS}"

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
    sf_partial_summary "${CURRENT_STAGE}" "degraded" "bash runpod/entrypoints/pd-l1-downstream.sh" "partial"
  fi
  python3 - "${ARTIFACT_ROOT_ABS}" "${RUN_ID}" "${CURRENT_STAGE}" "${rc}" <<'PY' || true
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

# The bridge tool clones / checks out the pinned SHA before this script fires.
# Only re-bootstrap if the repo isn't already present (defensive; should not
# normally hit this path).
if [[ ! -d "${REPO_ROOT}/.git" && -n "${STRUCTURE_FACTORY_REPO_URL:-}" ]]; then
  bash "${ENTRYPOINT_DIR}/bootstrap-repo.sh"
fi
cd "${REPO_ROOT}"

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
export BOLTZ_CACHE="${BOLTZ_WEIGHTS_DIR}"

# Hop to the structure-factory volume root so the runner's relative path use
# matches the previous pod's artifact layout (it tolerates absolute --out
# anyway; this keeps any cwd-relative logging consistent).
mkdir -p "${VOLUME_ROOT}"
cd "${VOLUME_ROOT}"

RUNNER="${REPO_ROOT}/scripts/structure_factory/pd_l1_binder_hunt.py"

# ---------------------------------------------------------------------------
# Stage 0a: downstream_preflight
# ---------------------------------------------------------------------------
CURRENT_STAGE="downstream_preflight"
sf_stage_start "${CURRENT_STAGE}" "verifying operator-gated candidate artifacts"
python3 - "${ARTIFACT_ROOT_ABS}" "${MVD_ROOT_ABS}" "${RUNNER}" "${STAGE_CONTRACT}" "${ARTIFACT_ROOT_ABS}/validation/downstream-preflight.json" <<'PY'
import json, sys
from datetime import datetime, timezone
from pathlib import Path

artifact_root = Path(sys.argv[1])
mvd_root = Path(sys.argv[2])
runner = Path(sys.argv[3])
stage_contract = Path(sys.argv[4])
out = Path(sys.argv[5])
out.parent.mkdir(parents=True, exist_ok=True)

if not runner.is_file():
    raise SystemExit(f"runner missing: {runner}")
if not stage_contract.is_file():
    raise SystemExit(f"stage contract missing: {stage_contract}")
if not mvd_root.is_dir():
    raise SystemExit(f"mvd_root missing: {mvd_root} (target_window.json must be reachable here)")

report = mvd_root / "target_window.json"
if not report.is_file():
    # The runner reads it via load_json(mvd_root / "target_window.json")
    # and fails closed if absent — surface that here for an earlier signal.
    raise SystemExit(f"target_window.json missing under mvd_root: {report}")

design_root = artifact_root / "design_candidates"
candidates = []
generated = 0
if design_root.is_dir():
    for cdir in sorted(design_root.iterdir()):
        if not cdir.is_dir():
            continue
        manifest = cdir / "manifest.json"
        if not manifest.is_file():
            candidates.append({"candidate_id": cdir.name, "status": "no_manifest"})
            continue
        try:
            m = json.loads(manifest.read_text())
        except Exception as exc:
            candidates.append({"candidate_id": cdir.name, "status": "manifest_parse_error", "error": str(exc)})
            continue
        struct = m.get("structure_path")
        if not struct:
            all_pdbs = m.get("all_genie3_pdbs") or []
            struct = all_pdbs[0] if all_pdbs else None
        on_disk = bool(struct and Path(struct).is_file())
        if on_disk:
            generated += 1
        candidates.append({
            "candidate_id": cdir.name,
            "status": "on_disk" if on_disk else "missing_structure",
            "structure_path": struct,
        })

report = {
    "schema_version": 1,
    "verified_at": datetime.now(timezone.utc).isoformat(),
    "runner_path": str(runner),
    "stage_contract": str(stage_contract),
    "mvd_root": str(mvd_root),
    "design_root": str(design_root),
    "candidate_count": len(candidates),
    "candidates_with_structure_on_disk": generated,
    "candidates": candidates,
}
out.write_text(json.dumps(report, indent=2, sort_keys=True) + "\n")

if generated < 1:
    raise SystemExit(f"no on-disk candidate structures found under {design_root}; nothing to cofold")
PY
sf_stage_complete "${CURRENT_STAGE}" "candidates present, runner + stage contract reachable"
CURRENT_STAGE=""

# ---------------------------------------------------------------------------
# Stage 0b: boltz_runtime_check
# ---------------------------------------------------------------------------
CURRENT_STAGE="boltz_runtime_check"
sf_stage_start "${CURRENT_STAGE}" "confirming boltz CLI and weights cache"
BOLTZ_PATH="$(command -v boltz || true)"
[[ -n "${BOLTZ_PATH}" ]] || { sf_stage_fail "${CURRENT_STAGE}" "boltz CLI not on PATH after sourcing ${SOFTWARE_ROOT}/envs/boltz"; exit 1; }
python3 - "${BOLTZ_WEIGHTS_DIR}" "${BOLTZ_PATH}" "${ARTIFACT_ROOT_ABS}/validation/boltz_runtime_check.json" <<'PY'
import json, sys
from datetime import datetime, timezone
from pathlib import Path
weights_dir = Path(sys.argv[1])
boltz_path = sys.argv[2]
out = Path(sys.argv[3])
out.parent.mkdir(parents=True, exist_ok=True)
weights_dir.mkdir(parents=True, exist_ok=True)
files = list(weights_dir.rglob("*"))
total = sum(p.stat().st_size for p in files if p.is_file())
report = {
    "schema_version": 1,
    "boltz_path": boltz_path,
    "weights_dir": str(weights_dir),
    "weight_file_count": sum(1 for p in files if p.is_file()),
    "weight_total_bytes": total,
    "cache_state": "populated" if total > 0 else "empty_will_populate_on_first_run",
    "verified_at": datetime.now(timezone.utc).isoformat(),
}
out.write_text(json.dumps(report, indent=2, sort_keys=True) + "\n")
PY
sf_stage_complete "${CURRENT_STAGE}" "boltz at ${BOLTZ_PATH}"
CURRENT_STAGE=""

# ---------------------------------------------------------------------------
# Runner stages: each in its own python3 call so failures are scoped to a
# single stage_id and the on_error trap reports the right CURRENT_STAGE.
# ---------------------------------------------------------------------------
for stage in "${RUNNER_STAGES[@]}"; do
  CURRENT_STAGE="${stage}"
  sf_stage_start "${CURRENT_STAGE}" "invoking runner --stage ${stage}"
  RUNNER_CMD=(python3 "${RUNNER}"
    --out "${ARTIFACT_ROOT_ABS}"
    --mvd-root "${MVD_ROOT_ABS}"
    --stage "${stage}"
    --terminal-state "${TERMINAL_STATE}"
    --json)
  set +e
  "${RUNNER_CMD[@]}" >> "${ARTIFACT_ROOT_ABS}/logs/runner_${stage}.log" 2>&1
  RUNNER_RC=$?
  set -e
  record_command "${CURRENT_STAGE}" "${RUNNER_RC}" "${RUNNER_CMD[*]}"
  if [[ "${RUNNER_RC}" -ne 0 ]]; then
    sf_stage_fail "${CURRENT_STAGE}" "runner exit ${RUNNER_RC}"
    exit "${RUNNER_RC}"
  fi
  sf_stage_complete "${CURRENT_STAGE}" "runner exit 0"
  CURRENT_STAGE=""
done

# ---------------------------------------------------------------------------
# Final stage: archive_and_status
# ---------------------------------------------------------------------------
CURRENT_STAGE="archive_and_status"
sf_stage_start "${CURRENT_STAGE}" "writing final status.json and packing artifact archive"
python3 - "${ARTIFACT_ROOT_ABS}" "${RUN_ID}" "${STAGE_CONTRACT}" <<'PY'
import hashlib, json, sys
from datetime import datetime, timezone
from pathlib import Path

root = Path(sys.argv[1])
run_id = sys.argv[2]
stage_contract_path = Path(sys.argv[3])

required = [
    "validation/boltz_crosscheck_extended.json",
    "candidate_ranking.json",
    "report/README.md",
    "validation_ledger.json",
    "validation/contract-self-check.json",
    "stage-progress.jsonl",
    "executed-commands.jsonl",
]
missing = [rel for rel in required if not (root / rel).is_file()]

contract_self_check = root / "validation" / "contract-self-check.json"
contract_ok = False
if contract_self_check.is_file():
    try:
        contract_ok = bool(json.loads(contract_self_check.read_text()).get("ok"))
    except Exception:
        contract_ok = False

claim_level = None
claim_path = root / "validation_ledger.json"
if claim_path.is_file():
    try:
        claim_level = json.loads(claim_path.read_text()).get("claim_level")
    except Exception:
        claim_level = None

ok = (not missing) and contract_ok

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
    "stage_contract_ref": str(stage_contract_path),
    "missing_artifacts": missing,
    "contract_self_check_ok": contract_ok,
    "claim_level": claim_level,
    "artifact_root": str(root),
    "completed_at": datetime.now(timezone.utc).isoformat(),
}
(root.parent / "status.json").write_text(json.dumps(status, indent=2, sort_keys=True) + "\n")
if not ok:
    raise SystemExit(f"downstream contract failed: missing={missing} contract_ok={contract_ok}")
PY

ARCHIVE_PATH="${ARTIFACT_ROOT_ABS}/runpod-execution.tar.gz"
TAR_CMD=(tar --exclude="runpod-execution.tar.gz" -czf "${ARCHIVE_PATH}" -C "${ARTIFACT_ROOT_ABS}" .)
set +e
"${TAR_CMD[@]}" >> "${ARTIFACT_ROOT_ABS}/logs/archive.log" 2>&1
TAR_RC=$?
set -e
record_command "${CURRENT_STAGE}" "${TAR_RC}" "${TAR_CMD[*]}"
if [[ "${TAR_RC}" -ne 0 ]]; then
  sf_stage_fail "${CURRENT_STAGE}" "tar exit ${TAR_RC}"
  exit "${TAR_RC}"
fi
sf_stage_complete "${CURRENT_STAGE}" "archive at ${ARCHIVE_PATH}"
CURRENT_STAGE=""

echo "pd-l1-downstream complete: ${RUN_ID} -> ${ARTIFACT_ROOT_ABS}"
