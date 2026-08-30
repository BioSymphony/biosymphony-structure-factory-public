#!/usr/bin/env bash
set -euo pipefail

RUN_ID="${STRUCTURE_FACTORY_RUN_ID:-structure-factory-no-download-smoke}"
VOLUME_ROOT="${STRUCTURE_FACTORY_VOLUME_ROOT:-/workspace/structure-factory}"
REPO_ROOT="${STRUCTURE_FACTORY_REPO_ROOT:-/workspace/repo}"
MANIFEST="${STRUCTURE_FACTORY_LAUNCH_MANIFEST:-${REPO_ROOT}/runpod/launch-manifests/no-download-smoke.json}"
STAGE_CONTRACT="${STRUCTURE_FACTORY_STAGE_CONTRACT:-${REPO_ROOT}/runpod/stage-contracts/no-download-smoke.stage-contract.json}"
RUN_ROOT="${VOLUME_ROOT}/runs/${RUN_ID}"
EXECUTION_MODE="${STRUCTURE_FACTORY_EXECUTION_MODE:-real}"
ENTRYPOINT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
CURRENT_STAGE=""

mkdir -p "${RUN_ROOT}/validation"
source "${ENTRYPOINT_DIR}/stage-progress.sh"

on_error() {
  local rc=$?
  if [[ -n "${CURRENT_STAGE}" ]]; then
    sf_stage_fail "${CURRENT_STAGE}" "exit_code=${rc}"
    sf_partial_summary \
      "${CURRENT_STAGE}" \
      "blocked_or_insufficient" \
      "STRUCTURE_FACTORY_RUN_ID=${RUN_ID} ${BASH_SOURCE[0]}" \
      "partial"
  fi
  exit "${rc}"
}
trap on_error ERR

if [[ ! -f "${REPO_ROOT}/scripts/structure_factory/toolcheck_runner.py" && -n "${STRUCTURE_FACTORY_REPO_URL:-}" ]]; then
  bash "${ENTRYPOINT_DIR}/bootstrap-repo.sh"
fi

CURRENT_STAGE="manifest_preflight"
sf_stage_start "${CURRENT_STAGE}" "validating launch manifest"
python3 "${REPO_ROOT}/scripts/structure_factory/runpod_manifest_check.py" "${MANIFEST}" --json \
  > "${RUN_ROOT}/validation/runpod-manifest-check.json"
sf_stage_complete "${CURRENT_STAGE}" "launch manifest valid"
CURRENT_STAGE=""

CURRENT_STAGE="input_audit"
sf_stage_start "${CURRENT_STAGE}" "auditing inputs"
python3 "${REPO_ROOT}/scripts/structure_factory/input_audit.py" \
  --manifest "${MANIFEST}" \
  --out "${RUN_ROOT}/validation/input-audit.json" \
  --json
sf_stage_complete "${CURRENT_STAGE}" "input audit complete"
CURRENT_STAGE=""

CURRENT_STAGE="toolcheck"
sf_stage_start "${CURRENT_STAGE}" "running environment and tool checks"
python3 "${REPO_ROOT}/scripts/structure_factory/toolcheck_runner.py" \
  --manifest "${MANIFEST}" \
  --out "${RUN_ROOT}" \
  ${STRUCTURE_FACTORY_MOCK_GPU:+--mock-gpu}
sf_stage_complete "${CURRENT_STAGE}" "toolcheck complete"
CURRENT_STAGE=""

CURRENT_STAGE="contract_self_check"
sf_stage_start "${CURRENT_STAGE}" "joining artifacts to manifest"
python3 "${REPO_ROOT}/scripts/structure_factory/contract_self_check.py" \
  --manifest "${MANIFEST}" \
  --artifact-root "${RUN_ROOT}" \
  --execution-mode "${EXECUTION_MODE}" \
  --json
sf_stage_complete "${CURRENT_STAGE}" "contract self-check complete"
CURRENT_STAGE=""

python3 "${REPO_ROOT}/scripts/structure_factory/stage_contract_check.py" \
  --stage-contract "${STAGE_CONTRACT}" \
  --progress-jsonl "${RUN_ROOT}/stage-progress.jsonl" \
  --require-terminal \
  --out "${RUN_ROOT}/validation/stage-contract-check.json" \
  --json

echo "no-download smoke complete: ${RUN_ROOT}"
