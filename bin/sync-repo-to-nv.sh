#!/usr/bin/env bash
# Sync the local working tree to /workspace/repo on a RunPod bootstrap pod's NV.
#
# Usage:
#   bin/sync-repo-to-nv.sh <pod-ssh-user@host> <ssh-port>
#
# Example:
#   bin/sync-repo-to-nv.sh root@ssh.runpod.io 12345
#
# Requirements (on the local machine):
#   - rsync, ssh, an ed25519 key registered as the pod's PUBLIC_KEY env at create-pod time
#
# Sends:
#   - all repo files except version-control state, runtime outputs, and other
#     ignored artifacts.
#   - sha-pinned snapshot of the working tree, not the git history.
#
# Receives nothing; prints a one-line summary on success.

set -euo pipefail

if [[ $# -lt 2 ]]; then
  printf 'usage: %s <ssh-user@host> <ssh-port>\n' "$0" >&2
  exit 2
fi

POD_SSH="$1"
POD_PORT="$2"
REPO_ROOT="$(cd "$(dirname "$0")/.." && pwd)"
DEST="/workspace/repo"

# Sanity: rsync over ssh
command -v rsync >/dev/null 2>&1 || { echo "rsync not found" >&2; exit 1; }
command -v ssh   >/dev/null 2>&1 || { echo "ssh not found"   >&2; exit 1; }

# Ensure dest exists, then rsync.
ssh -p "$POD_PORT" -o StrictHostKeyChecking=accept-new "$POD_SSH" "mkdir -p $DEST"

rsync -avz --delete \
  --exclude='.git/' \
  --exclude='.runtime/' \
  --exclude='node_modules/' \
  --exclude='__pycache__/' \
  --exclude='.DS_Store' \
  --exclude='.venv/' \
  --exclude='.mypy_cache/' \
  --exclude='*.pyc' \
  -e "ssh -p $POD_PORT -o StrictHostKeyChecking=accept-new" \
  "$REPO_ROOT/" "$POD_SSH:$DEST/"

# Stamp the sync time on the NV for traceability.
ssh -p "$POD_PORT" "$POD_SSH" "date -u +%Y-%m-%dT%H:%M:%SZ > $DEST/.synced-at"

local_sha="$(git -C "$REPO_ROOT" rev-parse HEAD 2>/dev/null || echo 'no-git-head')"
local_dirty="$(git -C "$REPO_ROOT" status --porcelain 2>/dev/null | head -1)"
ssh -p "$POD_PORT" "$POD_SSH" \
  "printf '%s%s\n' '$local_sha' '$( [[ -n "$local_dirty" ]] && printf -- "-dirty" )' > $DEST/.synced-from"

echo "ok: synced $REPO_ROOT/ -> $POD_SSH:$DEST (sha=$local_sha)"
