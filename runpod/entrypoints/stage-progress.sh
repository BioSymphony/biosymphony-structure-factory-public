#!/usr/bin/env bash
set -euo pipefail

sf_progress_path() {
  local run_id="${STRUCTURE_FACTORY_RUN_ID:-structure-factory-run}"
  local volume_root="${STRUCTURE_FACTORY_VOLUME_ROOT:-/workspace/structure-factory}"
  printf '%s/runs/%s/stage-progress.jsonl' "${volume_root}" "${run_id}"
}

sf_stage_event() {
  local stage_id="$1"
  local status="$2"
  local message="${3:-}"
  local observed_output_count="${4:-}"
  local progress_path="${STRUCTURE_FACTORY_STAGE_PROGRESS:-$(sf_progress_path)}"
  mkdir -p "$(dirname "${progress_path}")"
  python3 - "$progress_path" "$stage_id" "$status" "$message" "$observed_output_count" <<'PY'
import json
import sys
from datetime import datetime, timezone

path, stage_id, status, message, observed_output_count = sys.argv[1:6]
event = {
    "schema_version": 1,
    "timestamp": datetime.now(timezone.utc).isoformat(),
    "stage_id": stage_id,
    "status": status,
    "message": message,
}
if observed_output_count:
    event["observed_output_count"] = int(observed_output_count)
with open(path, "a", encoding="utf-8") as handle:
    handle.write(json.dumps(event, sort_keys=True) + "\n")
PY
}

sf_stage_start() {
  sf_stage_event "$1" "started" "${2:-}"
}

sf_stage_complete() {
  local stage_id="$1"
  local message="${2:-}"
  local contract_path="${STRUCTURE_FACTORY_STAGE_CONTRACT:-${STAGE_CONTRACT:-}}"
  local artifact_root="${STRUCTURE_FACTORY_ARTIFACT_ROOT:-${ARTIFACT_ROOT_ABS:-${ARTIFACT_ROOT:-${RUN_ROOT:-}}}}"

  if [[ -z "${contract_path}" || -z "${artifact_root}" ]]; then
    printf 'cannot complete %s: stage contract and artifact root are required\n' "${stage_id}" >&2
    return 1
  fi

  local observed_output_count
  observed_output_count="$({
    python3 - "${contract_path}" "${artifact_root}" "${stage_id}" <<'PY'
import json
import sys
from pathlib import Path

contract_path, artifact_root, stage_id = sys.argv[1:4]
contract = json.loads(Path(contract_path).read_text())
stage = next((item for item in contract.get("stages", []) if item.get("stage_id") == stage_id), None)
if stage is None:
    raise SystemExit(f"unknown stage_id: {stage_id}")

root = Path(artifact_root)
expected = stage.get("expected_outputs", [])
present = [relative for relative in expected if (root / relative).exists()]
missing = [relative for relative in expected if relative not in present]
minimum = stage.get("output_validation", {}).get("minimum_expected_paths")
if not isinstance(minimum, int) or minimum <= 0:
    raise SystemExit(f"stage {stage_id} has no valid output-count rule")
if len(present) < minimum:
    raise SystemExit(
        f"stage {stage_id} has {len(present)}/{minimum} required output paths; missing: {', '.join(missing)}"
    )
print(len(present))
PY
  })" || return 1

  sf_stage_event "${stage_id}" "completed" "${message}" "${observed_output_count}"
}

sf_stage_fail() {
  sf_stage_event "$1" "failed" "${2:-}"
}

sf_partial_summary() {
  local failed_stage="$1"
  local claim_level="${2:-degraded}"
  local resume_command="${3:-rerun the failed stage command from the stage contract}"
  local artifact_status="${4:-partial}"
  local run_id="${STRUCTURE_FACTORY_RUN_ID:-structure-factory-run}"
  local volume_root="${STRUCTURE_FACTORY_VOLUME_ROOT:-/workspace/structure-factory}"
  local run_root="${volume_root}/runs/${run_id}"
  local progress_path="${STRUCTURE_FACTORY_STAGE_PROGRESS:-$(sf_progress_path)}"
  mkdir -p "${run_root}"
  python3 - "$run_root/partial-summary.json" "$progress_path" "$failed_stage" "$claim_level" "$resume_command" "$artifact_status" <<'PY'
import json
import sys
from datetime import datetime, timezone
from pathlib import Path

out, progress_path, failed_stage, claim_level, resume_command, artifact_status = sys.argv[1:7]
events = []
path = Path(progress_path)
if path.exists():
    for line in path.read_text().splitlines():
        if not line.strip():
            continue
        try:
            events.append(json.loads(line))
        except json.JSONDecodeError:
            events.append({"parse_error": True})
completed = [
    event.get("stage_id")
    for event in events
    if event.get("status") == "completed" and event.get("stage_id")
]
summary = {
    "schema_version": 1,
    "timestamp": datetime.now(timezone.utc).isoformat(),
    "completed_stages": completed,
    "failed_stage": failed_stage,
    "resume_command": resume_command,
    "artifact_status": artifact_status,
    "claim_level": claim_level,
    "progress_ledger": str(path),
}
Path(out).write_text(json.dumps(summary, indent=2, sort_keys=True) + "\n")
PY
}
