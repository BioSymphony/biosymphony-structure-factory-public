#!/usr/bin/env bash
set -euo pipefail

RUN_ID="${STRUCTURE_FACTORY_RUN_ID:-structure-factory-gated-bootstrap}"
VOLUME_ROOT="${STRUCTURE_FACTORY_VOLUME_ROOT:-/workspace/structure-factory}"
RUN_ROOT="${VOLUME_ROOT}/runs/${RUN_ID}"
VALIDATION_DIR="${RUN_ROOT}/validation"
INSTALL_ROOT="${STRUCTURE_FACTORY_GATED_INSTALL_ROOT:-/opt/structure-factory/gated-tools}"
ALLOW_INSTALLS="${STRUCTURE_FACTORY_ALLOW_GATED_INSTALLS:-0}"
REPO_ROOT="${STRUCTURE_FACTORY_REPO_ROOT:-/workspace/repo}"

mkdir -p "${VALIDATION_DIR}" "${INSTALL_ROOT}"

python3 "${REPO_ROOT}/scripts/structure_factory/license_gate_check.py" \
  --manifest "${STRUCTURE_FACTORY_LAUNCH_MANIFEST:-${REPO_ROOT}/runpod/launch-manifests/no-download-smoke.json}" \
  --out "${VALIDATION_DIR}/license-gates.json" \
  --json

record_status() {
  local tool="$1"
  local status="$2"
  local reason="$3"
  mkdir -p "${VALIDATION_DIR}/gated-installs"
  printf '{"tool":"%s","status":"%s","reason":"%s"}\n' "${tool}" "${status}" "${reason}" \
    > "${VALIDATION_DIR}/gated-installs/${tool}.json"
}

if [[ "${ALLOW_INSTALLS}" != "1" && "${ALLOW_INSTALLS}" != "true" && "${ALLOW_INSTALLS}" != "yes" ]]; then
  record_status "all" "prepared_not_installed" "STRUCTURE_FACTORY_ALLOW_GATED_INSTALLS is not enabled"
  exit 0
fi

if [[ "${STRUCTURE_FACTORY_ENABLE_CRYOSPARC:-0}" =~ ^(1|true|yes)$ ]]; then
  if [[ -z "${CRYOSPARC_LICENSE_ID:-}" ]]; then
    record_status "cryosparc" "blocked" "missing CRYOSPARC_LICENSE_ID"
    exit 2
  fi
  VERSION="${CRYOSPARC_VERSION:-latest}"
  CRYOSPARC_ROOT="${INSTALL_ROOT}/cryosparc"
  mkdir -p "${CRYOSPARC_ROOT}"
  curl -L "https://get.cryosparc.com/download/master-${VERSION}/${CRYOSPARC_LICENSE_ID}" -o "${CRYOSPARC_ROOT}/cryosparc_master.tar.gz"
  curl -L "https://get.cryosparc.com/download/worker-${VERSION}/${CRYOSPARC_LICENSE_ID}" -o "${CRYOSPARC_ROOT}/cryosparc_worker.tar.gz"
  record_status "cryosparc" "downloaded" "packages downloaded to pod scratch; installation still requires explicit runtime authorization"
fi

if [[ "${STRUCTURE_FACTORY_ENABLE_PHENIX:-0}" =~ ^(1|true|yes)$ ]]; then
  if [[ -n "${PHENIX_INSTALLER_PATH:-}" && -f "${PHENIX_INSTALLER_PATH}" ]]; then
    record_status "phenix" "installer_available" "PHENIX_INSTALLER_PATH exists"
  else
    record_status "phenix" "blocked" "set PHENIX_INSTALLER_PATH or approved PHENIX_INSTALLER_URL at runtime"
  fi
fi

if [[ "${STRUCTURE_FACTORY_ENABLE_CHIMERAX:-0}" =~ ^(1|true|yes)$ ]]; then
  if [[ -n "${CHIMERAX_INSTALLER_PATH:-}" && -f "${CHIMERAX_INSTALLER_PATH}" ]]; then
    record_status "chimerax" "installer_available" "CHIMERAX_INSTALLER_PATH exists"
  else
    record_status "chimerax" "blocked" "set CHIMERAX_INSTALLER_PATH or approved CHIMERAX_INSTALLER_URL at runtime"
  fi
fi

if [[ "${STRUCTURE_FACTORY_ENABLE_MOTIONCOR3:-0}" =~ ^(1|true|yes)$ ]]; then
  if [[ -n "${MOTIONCOR3_BINARY_PATH:-}" && -x "${MOTIONCOR3_BINARY_PATH}" ]]; then
    record_status "motioncor3" "binary_available" "MOTIONCOR3_BINARY_PATH exists and is executable"
  else
    record_status "motioncor3" "blocked" "set MOTIONCOR3_BINARY_PATH or approved runtime access"
  fi
fi
