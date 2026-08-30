#!/usr/bin/env bash
set -euo pipefail

RUN_ID="${STRUCTURE_FACTORY_RUN_ID:-structure-factory-raw-subset}"
VOLUME_ROOT="${STRUCTURE_FACTORY_VOLUME_ROOT:-/workspace/structure-factory}"
RUN_ROOT="${VOLUME_ROOT}/runs/${RUN_ID}"
SCRATCH_ROOT="${VOLUME_ROOT}/scratch/${RUN_ID}"
REPO_ROOT="${STRUCTURE_FACTORY_REPO_ROOT:-/workspace/repo}"
MANIFEST="${STRUCTURE_FACTORY_LAUNCH_MANIFEST:-${REPO_ROOT}/runpod/launch-manifests/raw-subset-open.json}"
STAGE_CONTRACT="${STRUCTURE_FACTORY_STAGE_CONTRACT:-${REPO_ROOT}/runpod/stage-contracts/raw-subset-open.stage-contract.json}"
if [[ "${MANIFEST}" == *raw-subset-gated* ]]; then
  STAGE_CONTRACT="${STRUCTURE_FACTORY_STAGE_CONTRACT:-${REPO_ROOT}/runpod/stage-contracts/raw-subset-gated.stage-contract.json}"
fi
EXECUTION_MODE="${STRUCTURE_FACTORY_EXECUTION_MODE:-real}"
ENTRYPOINT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
CURRENT_STAGE=""

mkdir -p "${RUN_ROOT}/validation" "${SCRATCH_ROOT}"
source "${ENTRYPOINT_DIR}/stage-progress.sh"

on_error() {
  local rc=$?
  if [[ -n "${CURRENT_STAGE}" ]]; then
    sf_stage_fail "${CURRENT_STAGE}" "exit_code=${rc}"
    sf_partial_summary "${CURRENT_STAGE}" "degraded" "bash runpod/entrypoints/run-raw-subset-demo.sh" "partial"
  fi
  exit "${rc}"
}
trap on_error ERR

if [[ ! -f "${REPO_ROOT}/scripts/structure_factory/toolcheck_runner.py" && -n "${STRUCTURE_FACTORY_REPO_URL:-}" ]]; then
  bash "${ENTRYPOINT_DIR}/bootstrap-repo.sh"
fi

if [[ ! "${STRUCTURE_FACTORY_ALLOW_RAW_DOWNLOADS:-0}" =~ ^(1|true|yes)$ ]]; then
  echo "raw subset execution blocked: STRUCTURE_FACTORY_ALLOW_RAW_DOWNLOADS must be truthy" >&2
  sf_stage_event "operator_authorization" "failed" "STRUCTURE_FACTORY_ALLOW_RAW_DOWNLOADS not truthy"
  sf_partial_summary "operator_authorization" "blocked" "set STRUCTURE_FACTORY_ALLOW_RAW_DOWNLOADS after explicit operator approval and rerun" "none"
  exit 2
fi

if [[ ! "${STRUCTURE_FACTORY_OPERATOR_AUTHORIZED:-0}" =~ ^(1|true|yes)$ ]]; then
  echo "raw subset execution blocked: STRUCTURE_FACTORY_OPERATOR_AUTHORIZED must be truthy" >&2
  sf_stage_event "operator_authorization" "failed" "STRUCTURE_FACTORY_OPERATOR_AUTHORIZED not truthy"
  sf_partial_summary "operator_authorization" "blocked" "set STRUCTURE_FACTORY_OPERATOR_AUTHORIZED after explicit operator approval and rerun" "none"
  exit 2
fi

CURRENT_STAGE="manifest_preflight"
sf_stage_start "${CURRENT_STAGE}" "validating launch manifest"
python3 "${REPO_ROOT}/scripts/structure_factory/runpod_manifest_check.py" "${MANIFEST}" --json \
  > "${RUN_ROOT}/validation/runpod-manifest-check.json"
sf_stage_complete "${CURRENT_STAGE}" "launch manifest valid"
CURRENT_STAGE=""

if [[ "${MANIFEST}" == *raw-subset-gated* ]]; then
  CURRENT_STAGE="license_gate_probe"
  sf_stage_start "${CURRENT_STAGE}" "checking gated runtime access"
  python3 "${REPO_ROOT}/scripts/structure_factory/license_gate_check.py" \
    --manifest "${MANIFEST}" \
    --out "${RUN_ROOT}/validation/license-gates.json" \
    --json
  sf_stage_complete "${CURRENT_STAGE}" "license gate probe complete"
  CURRENT_STAGE=""
fi

CURRENT_STAGE="input_audit"
sf_stage_start "${CURRENT_STAGE}" "auditing raw subset inputs"
python3 "${REPO_ROOT}/scripts/structure_factory/input_audit.py" \
  --manifest "${MANIFEST}" \
  --out "${RUN_ROOT}/validation/input-audit.json" \
  --json
sf_stage_complete "${CURRENT_STAGE}" "input audit complete"
CURRENT_STAGE=""

CURRENT_STAGE="fanout_estimate"
sf_stage_start "${CURRENT_STAGE}" "estimating raw subset fanout before transfer"
python3 "${REPO_ROOT}/scripts/structure_factory/fanout_estimator.py" \
  --manifest "${MANIFEST}" \
  --out "${RUN_ROOT}/validation/fanout-estimate.json" \
  --json
sf_stage_complete "${CURRENT_STAGE}" "fanout estimate complete"
CURRENT_STAGE=""

CURRENT_STAGE="raw_subset_intake"
sf_stage_start "${CURRENT_STAGE}" "recording bounded raw subset intake"
python3 "${REPO_ROOT}/scripts/structure_factory/toolcheck_runner.py" \
  --manifest "${MANIFEST}" \
  --out "${RUN_ROOT}" \
  ${STRUCTURE_FACTORY_MOCK_GPU:+--mock-gpu}

cat > "${RUN_ROOT}/data-intake-ledger.json" <<JSON
{
  "schema_version": 1,
  "accession": "EMPIAR-13124",
  "source_url": "https://www.ebi.ac.uk/empiar/EMPIAR-13124/",
  "subset_profile": "${STRUCTURE_FACTORY_SUBSET_PROFILE:-raw_movies_100}",
  "deterministic_rule": "lexicographic_first_n_raw_movies_from_empiar_file_listing",
  "download_method": "not_executed_by_scaffold",
  "storage_path": "${SCRATCH_ROOT}",
  "file_count": 0,
  "checksum_policy": "not_available_until_downloader_lane_runs",
  "allow_processed_inputs": false,
  "status": "planned_not_downloaded_by_scaffold",
  "note": "Actual EMPIAR subset transfer must be performed by an approved downloader lane on RunPod scratch only."
}
JSON
sf_stage_complete "${CURRENT_STAGE}" "raw subset intake ledger recorded"
CURRENT_STAGE=""

cat > "${RUN_ROOT}/provenance.md" <<EOF
# Raw Subset Demo Provenance

- run_id: \`${RUN_ID}\`
- manifest: \`${MANIFEST}\`
- scratch_root: \`${SCRATCH_ROOT}\`
- raw_data_policy: \`RunPod scratch only; do not export raw movies\`
EOF

CURRENT_STAGE="contract_self_check"
sf_stage_start "${CURRENT_STAGE}" "joining raw subset artifacts to manifest"
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

echo "raw subset scaffold complete: ${RUN_ROOT}"
