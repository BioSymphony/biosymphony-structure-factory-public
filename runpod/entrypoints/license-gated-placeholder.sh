#!/usr/bin/env bash
set -euo pipefail

REPO_ROOT="${STRUCTURE_FACTORY_REPO_ROOT:-/workspace/repo}"
ENTRYPOINT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"

if [[ ! -f "${REPO_ROOT}/scripts/structure_factory/license_gate_check.py" && -n "${STRUCTURE_FACTORY_REPO_URL:-}" ]]; then
  bash "${ENTRYPOINT_DIR}/bootstrap-repo.sh"
fi

bash "${REPO_ROOT}/runpod/entrypoints/bootstrap-gated-tools.sh"
