#!/usr/bin/env bash
set -euo pipefail

REPO_URL="${STRUCTURE_FACTORY_REPO_URL:?STRUCTURE_FACTORY_REPO_URL is required}"
GIT_REF="${STRUCTURE_FACTORY_GIT_REF:?STRUCTURE_FACTORY_GIT_REF is required}"
REPO_ROOT="${STRUCTURE_FACTORY_REPO_ROOT:-/workspace/repo}"
RUN_ID="${STRUCTURE_FACTORY_RUN_ID:-structure-factory-run}"
VOLUME_ROOT="${STRUCTURE_FACTORY_VOLUME_ROOT:-/workspace/structure-factory}"
RUN_ROOT="${VOLUME_ROOT}/runs/${RUN_ID}"

mkdir -p "$(dirname "${REPO_ROOT}")" "${RUN_ROOT}/validation"

if [[ ! -d "${REPO_ROOT}/.git" ]]; then
  git clone "${REPO_URL}" "${REPO_ROOT}"
fi

cd "${REPO_ROOT}"
git fetch --tags origin
git checkout --detach "${GIT_REF}"

cat > "${RUN_ROOT}/validation/repo-clone-manifest.json" <<EOF
{
  "schema_version": 1,
  "repo_root": "${REPO_ROOT}",
  "git_ref": "${GIT_REF}",
  "resolved_commit": "$(git rev-parse HEAD)",
  "remote": "$(git remote get-url origin | sed -E 's#(https://)[^/@]+@#\\1***@#')"
}
EOF

echo "repo ready at ${REPO_ROOT} ($(git rev-parse --short HEAD))"
