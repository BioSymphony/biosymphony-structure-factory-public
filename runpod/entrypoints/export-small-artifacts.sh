#!/usr/bin/env bash
set -euo pipefail

RUN_ID="${STRUCTURE_FACTORY_RUN_ID:?STRUCTURE_FACTORY_RUN_ID is required}"
VOLUME_ROOT="${STRUCTURE_FACTORY_VOLUME_ROOT:-/workspace/structure-factory}"
RUN_ROOT="${VOLUME_ROOT}/runs/${RUN_ID}"
EXPORT_ROOT="${STRUCTURE_FACTORY_EXPORT_ROOT:-${VOLUME_ROOT}/exports/${RUN_ID}}"

mkdir -p "${EXPORT_ROOT}"

rsync -a \
  --exclude='*.eer' \
  --exclude='*.tif' \
  --exclude='*.tiff' \
  --exclude='*.mrcs' \
  --exclude='raw_movies/' \
  --exclude='particle_stacks/' \
  "${RUN_ROOT}/" "${EXPORT_ROOT}/"

find "${EXPORT_ROOT}" -maxdepth 5 -type f | sort > "${EXPORT_ROOT}/export-file-list.txt"

if [[ "${STRUCTURE_FACTORY_DELETE_SCRATCH_AFTER_EXPORT:-0}" =~ ^(1|true|yes)$ ]]; then
  SCRATCH_ROOT="${VOLUME_ROOT}/scratch/${RUN_ID}"
  if [[ -d "${SCRATCH_ROOT}" && "${SCRATCH_ROOT}" == /workspace/structure-factory/scratch/* ]]; then
    rm -rf "${SCRATCH_ROOT}"
  fi
fi

echo "small artifact export complete: ${EXPORT_ROOT}"
