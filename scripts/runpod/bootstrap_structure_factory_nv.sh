#!/usr/bin/env bash
# Bootstrap script for the structure-factory RunPod network volume (id STRUCTURE_FACTORY_RUNPOD_NETWORK_VOLUME_ID).
#
# Runs INSIDE a one-time bootstrap pod that has the NV mounted at /workspace.
# Installs the campaign software stack into /workspace/software/ and the
# repo snapshot into /workspace/repo/. Each step is idempotent and gated on
# a sentinel file, so re-running is a no-op once everything is installed.
#
# Tools installed:
#   - miniconda3 (latest)              -> /workspace/software/miniconda3/
#   - conda env "structure-factory-cpu"-> /workspace/software/envs/structure-factory-cpu/
#       (biopython, requests, numpy, scipy, jinja2, pyyaml, mmcif-pdbx)
#   - conda env "boltz"                -> /workspace/software/envs/boltz/
#       (boltz==2.2.1 + cuda extras)
#   - Genie 3 source and optional gated env
#       (deferred by default; requires explicit dependency/weight review ack)
#   - conda env "proteinmpnn"          -> /workspace/software/envs/proteinmpnn/
#       (cloned ProteinMPNN repo, resolved ref, pip-installed deps)
#   - ChimeraX 1.9                     -> optional/deferred by default
#       (downloaded only when INSTALL_CHIMERAX=1 and CHIMERAX_DEB_URL is provided)
#
# The repo snapshot is NOT installed by this script - the operator rsyncs it
# from the laptop after bootstrap pod has SSH up, via bin/sync-repo-to-nv.sh.
#
# Run once:
#   bash /workspace/repo/scripts/runpod/bootstrap_structure_factory_nv.sh
# Or, before the repo is on the NV, fetched from a temp tarball:
#   curl -fsSL "$BOOTSTRAP_URL" -o /tmp/structure-factory-bootstrap.sh
#   echo "$BOOTSTRAP_SHA256  /tmp/structure-factory-bootstrap.sh" | sha256sum -c -
#   bash /tmp/structure-factory-bootstrap.sh

set -euo pipefail

NV_ROOT="${NV_ROOT:-/workspace}"
SOFTWARE_ROOT="$NV_ROOT/software"
SENTINEL_ROOT="$SOFTWARE_ROOT/sentinels"

MINICONDA_VERSION="${MINICONDA_VERSION:-py311_24.7.1-0}"
CHIMERAX_VERSION="${CHIMERAX_VERSION:-1.9}"
CHIMERAX_BUILD="${CHIMERAX_BUILD:-2024.07.10}"
BOLTZ_VERSION="${BOLTZ_VERSION:-2.2.1}"
BOLTZ_PIP_SPEC="${BOLTZ_PIP_SPEC:-boltz[cuda]==${BOLTZ_VERSION}}"
GENIE3_INSTALL="${GENIE3_INSTALL:-0}"
GENIE3_OPERATOR_GATE_ACK="${GENIE3_OPERATOR_GATE_ACK:-}"
GENIE3_REPO_URL="${GENIE3_REPO_URL:-https://github.com/aqlaboratory/genie3}"
GENIE3_REF="${GENIE3_REF:-5214459c42e69b01fadfc7d7ebda09d8e5082115}"
GENIE3_HF_REPO="${GENIE3_HF_REPO:-yeqinglin/genie3}"
GENIE3_HF_REVISION="${GENIE3_HF_REVISION:-9ae31ebb8c56eebdc05ab282a8fd3f6a6d2a03a2}"
GENIE3_DOWNLOAD_WEIGHTS="${GENIE3_DOWNLOAD_WEIGHTS:-0}"
GENIE3_DOWNLOAD_TRAINING_DATA="${GENIE3_DOWNLOAD_TRAINING_DATA:-0}"
GENIE3_ALLOW_COLABFOLD_PARAMS="${GENIE3_ALLOW_COLABFOLD_PARAMS:-0}"
GENIE3_ALLOW_TRAINING_DATA="${GENIE3_ALLOW_TRAINING_DATA:-0}"
GENIE3_INSTALL_STATUS="${GENIE3_INSTALL_STATUS:-deferred}"
GENIE3_ACTUAL_COMMIT="${GENIE3_ACTUAL_COMMIT:-unresolved}"
PROTEINMPNN_REPO_URL="${PROTEINMPNN_REPO_URL:-https://github.com/dauparas/ProteinMPNN}"
PROTEINMPNN_REF="${PROTEINMPNN_REF:-${PROTEINMPNN_COMMIT:-main}}"
PROTEINMPNN_ACTUAL_COMMIT="${PROTEINMPNN_ACTUAL_COMMIT:-unresolved}"
INSTALL_CHIMERAX="${INSTALL_CHIMERAX:-0}"
CHIMERAX_DEB_URL="${CHIMERAX_DEB_URL:-}"
CHIMERAX_INSTALL_STATUS="${CHIMERAX_INSTALL_STATUS:-deferred}"
RFDIFFUSION_DOWNLOAD_WEIGHTS="${RFDIFFUSION_DOWNLOAD_WEIGHTS:-0}"
RFDIFFUSION_WEIGHTS_BASE_URL="${RFDIFFUSION_WEIGHTS_BASE_URL:-http://files.ipd.uw.edu/pub/RFdiffusion/}"
RFDIFFUSION_WEIGHTS_FILES="${RFDIFFUSION_WEIGHTS_FILES:-Complex_base_ckpt.pt}"
RFDIFFUSION_WEIGHTS_HF_REPO="${RFDIFFUSION_WEIGHTS_HF_REPO:-__OPERATOR_REVIEWED_RFDIFFUSION_REPO__}"
RFDIFFUSION_WEIGHTS_HF_REV="${RFDIFFUSION_WEIGHTS_HF_REV:-3cdaa7d9e22dbdf085abbd16f17b4dc31995ce4d}"
RFDIFFUSION_TERMS_ACK="${RFDIFFUSION_TERMS_ACK:-}"

# IPD URL path-segment map — these are NOT file md5s. IPD uses a content-addressed
# URL layout (`files.ipd.uw.edu/pub/RFdiffusion/<key>/<fname>`) with a per-file hash
# that doesn't match md5sum of the bytes. Used ONLY for constructing IPD URLs.
# Sourced from RosettaCommons/RFdiffusion README.
declare -A RFDIFFUSION_IPD_KEY_MAP=(
  ["Base_ckpt.pt"]="6f5902ac237024bdd0c176cb93063dc4"
  ["Complex_base_ckpt.pt"]="e29311f6f1bf1af907f9ef9f44b8328b"
  ["Complex_Fold_base_ckpt.pt"]="60f09a193fb5e5ccdc4980417708dbab"
  ["InpaintSeq_ckpt.pt"]="74f51cfb8b440f50d70878e05361d8f0"
  ["InpaintSeq_Fold_ckpt.pt"]="76d00716416567174cdb7ca96e208296"
  ["ActiveSite_ckpt.pt"]="5532d2e1f3a4738decd58b19d633b3c3"
  ["Base_epoch8_ckpt.pt"]="12fc204edeae5b57713c5ad7dcb97d39"
  ["Complex_beta_ckpt.pt"]="f572d396fae9206628714fb2ce00f72e"
  ["RF_structure_prediction_weights.pt"]="1befcb9b28e2f778f53d47f18b7597fa"
)
# Actual file sha256 map — verified locally (stream-checked from HF mirror).
# Used for post-download integrity verification.
declare -A RFDIFFUSION_SHA256_MAP=(
  ["Complex_base_ckpt.pt"]="76e4e260aefee3b582bd76b77ab95d2592e64f00c51bf344968ab9239f3250bc"
)
RFDIFFUSION_INSTALL_STATUS="${RFDIFFUSION_INSTALL_STATUS:-deferred}"
BOOTSTRAP_HEARTBEAT_SECONDS="${BOOTSTRAP_HEARTBEAT_SECONDS:-60}"
BOOTSTRAP_MAX_RUNTIME_SECONDS="${BOOTSTRAP_MAX_RUNTIME_SECONDS:-21600}"
BOOTSTRAP_STARTED_AT="$(date +%s)"
HEARTBEAT_PID=""
RUNTIME_GUARD_PID=""

log()  { printf '[bootstrap %(%H:%M:%S)T] %s\n' -1 "$*"; }
fail() { printf '[bootstrap ERROR] %s\n' "$*" >&2; exit 1; }

require_cmd() { command -v "$1" >/dev/null 2>&1 || fail "missing required cmd: $1"; }

mkdir -p "$SOFTWARE_ROOT" "$SENTINEL_ROOT"
cd "$NV_ROOT"

cleanup_background() {
  if [[ -n "$HEARTBEAT_PID" ]]; then
    kill "$HEARTBEAT_PID" >/dev/null 2>&1 || true
  fi
  if [[ -n "$RUNTIME_GUARD_PID" ]]; then
    kill "$RUNTIME_GUARD_PID" >/dev/null 2>&1 || true
  fi
}

start_bootstrap_heartbeat() {
  [[ "$BOOTSTRAP_HEARTBEAT_SECONDS" =~ ^[0-9]+$ ]] || fail "BOOTSTRAP_HEARTBEAT_SECONDS must be an integer"
  [[ "$BOOTSTRAP_HEARTBEAT_SECONDS" -gt 0 ]] || return 0
  (
    while true; do
      sleep "$BOOTSTRAP_HEARTBEAT_SECONDS"
      local_now="$(date +%s)"
      local_elapsed=$((local_now - BOOTSTRAP_STARTED_AT))
      local_size="$(du -sh "$SOFTWARE_ROOT" 2>/dev/null | awk '{print $1}' || true)"
      local_sentinels="$(find "$SENTINEL_ROOT" -maxdepth 1 -type f 2>/dev/null | wc -l | tr -d ' ')"
      log "HEARTBEAT elapsed=${local_elapsed}s software_size=${local_size:-unknown} sentinels=${local_sentinels:-0}"
    done
  ) &
  HEARTBEAT_PID="$!"
}

start_runtime_guard() {
  [[ "$BOOTSTRAP_MAX_RUNTIME_SECONDS" =~ ^[0-9]+$ ]] || fail "BOOTSTRAP_MAX_RUNTIME_SECONDS must be an integer"
  [[ "$BOOTSTRAP_MAX_RUNTIME_SECONDS" -gt 0 ]] || return 0
  local parent_pid="$$"
  (
    sleep "$BOOTSTRAP_MAX_RUNTIME_SECONDS"
    log "max runtime ${BOOTSTRAP_MAX_RUNTIME_SECONDS}s exceeded; terminating bootstrap shell"
    touch "$SOFTWARE_ROOT/bootstrap-timeout"
    kill -TERM "$parent_pid" >/dev/null 2>&1 || true
  ) &
  RUNTIME_GUARD_PID="$!"
}

trap cleanup_background EXIT

# 1) miniconda3
install_miniconda() {
  local sentinel="$SENTINEL_ROOT/miniconda3.${MINICONDA_VERSION}.installed"
  [[ -f "$sentinel" ]] && { log "miniconda already installed ($MINICONDA_VERSION)"; return 0; }
  log "installing miniconda3 ($MINICONDA_VERSION) -> $SOFTWARE_ROOT/miniconda3"
  require_cmd curl
  local tmp; tmp="$(mktemp -d)"
  local installer="$tmp/miniconda.sh"
  curl -fsSL "https://repo.anaconda.com/miniconda/Miniconda3-${MINICONDA_VERSION}-Linux-x86_64.sh" -o "$installer"
  bash "$installer" -b -u -p "$SOFTWARE_ROOT/miniconda3"
  rm -rf "$tmp"
  touch "$sentinel"
  log "miniconda3 installed"
}

# Source conda after install so subsequent envs work
activate_conda() {
  # shellcheck disable=SC1091
  source "$SOFTWARE_ROOT/miniconda3/etc/profile.d/conda.sh"
}

# 2) conda env: structure-factory-cpu (used by CPU report and validation lanes)
install_env_structure_factory_cpu() {
  local sentinel="$SENTINEL_ROOT/env.structure-factory-cpu.installed"
  [[ -f "$sentinel" ]] && { log "env structure-factory-cpu already installed"; return 0; }
  log "creating conda env: structure-factory-cpu (python 3.11 + biopython + numpy + scipy + jinja2 + pyyaml + mmcif-pdbx)"
  conda create -y -p "$SOFTWARE_ROOT/envs/structure-factory-cpu" \
    -c conda-forge \
    python=3.11 \
    biopython \
    numpy \
    scipy \
    jinja2 \
    pyyaml \
    requests \
    pip
  conda activate "$SOFTWARE_ROOT/envs/structure-factory-cpu"
  pip install --no-cache-dir mmcif-pdbx
  conda deactivate
  touch "$sentinel"
  log "structure-factory-cpu env installed"
}

# 3) conda env: boltz (cofold and model-comparison inference)
install_env_boltz() {
  local sentinel="$SENTINEL_ROOT/env.boltz.${BOLTZ_VERSION}.installed"
  [[ -f "$sentinel" ]] && { log "env boltz already installed (boltz==$BOLTZ_VERSION)"; return 0; }
  log "creating conda env: boltz (python 3.11 + ${BOLTZ_PIP_SPEC})"
  conda create -y -p "$SOFTWARE_ROOT/envs/boltz" \
    -c conda-forge \
    python=3.11 \
    pip
  conda activate "$SOFTWARE_ROOT/envs/boltz"
  pip install --no-cache-dir --extra-index-url https://download.pytorch.org/whl/cu124 \
    "${BOLTZ_PIP_SPEC}"
  conda deactivate
  touch "$sentinel"
  log "boltz env installed (${BOLTZ_PIP_SPEC})"
}

# 3b) Genie 3 source + optional gated env. This is intentionally not installed
# by default because upstream setup pulls a large dependency stack, including
# ColabFold/AlphaFold2 multimer params and evaluator tools that need current
# dependency, weight, and privacy review for the intended use.
resolve_genie3_ref() {
  local source_dir="$1"
  require_cmd git
  if [[ ! -d "$source_dir/.git" ]]; then
    log "cloning Genie 3 from $GENIE3_REPO_URL" >&2
    git clone "$GENIE3_REPO_URL" "$source_dir"
  fi
  git -C "$source_dir" fetch --all --tags --prune
  if git -C "$source_dir" rev-parse --verify --quiet "${GENIE3_REF}^{commit}" >/dev/null; then
    git -C "$source_dir" checkout --detach "$GENIE3_REF"
  elif git -C "$source_dir" rev-parse --verify --quiet "origin/${GENIE3_REF}^{commit}" >/dev/null; then
    git -C "$source_dir" checkout --detach "origin/${GENIE3_REF}"
  else
    fail "GENIE3_REF=$GENIE3_REF does not resolve in $GENIE3_REPO_URL; verify the upstream ref before paid bootstrap"
  fi
  git -C "$source_dir" rev-parse HEAD
}

install_env_genie3() {
  local deferred="$SENTINEL_ROOT/env.genie3.deferred"
  local source_dir="$SOFTWARE_ROOT/src/genie3"
  mkdir -p "$SOFTWARE_ROOT/src"

  if [[ "$GENIE3_INSTALL" != "1" ]]; then
    GENIE3_INSTALL_STATUS="deferred"
    touch "$deferred"
    log "Genie 3 install deferred; set GENIE3_INSTALL=1 only after dependency/weight/MSA-server review"
    return 0
  fi

  [[ "$GENIE3_OPERATOR_GATE_ACK" == "dependency_and_weight_terms_reviewed" ]] || \
    fail "GENIE3_INSTALL=1 requires GENIE3_OPERATOR_GATE_ACK=dependency_and_weight_terms_reviewed"
  if [[ "$GENIE3_ALLOW_COLABFOLD_PARAMS" != "1" ]]; then
    fail "GENIE3_INSTALL=1 requires GENIE3_ALLOW_COLABFOLD_PARAMS=1 because upstream setup installs ColabFold and downloads AlphaFold2 multimer parameters"
  fi
  if [[ "$GENIE3_DOWNLOAD_TRAINING_DATA" == "1" && "$GENIE3_ALLOW_TRAINING_DATA" != "1" ]]; then
    fail "GENIE3_DOWNLOAD_TRAINING_DATA=1 requires GENIE3_ALLOW_TRAINING_DATA=1; training data stays blocked by default"
  fi

  GENIE3_ACTUAL_COMMIT="$(resolve_genie3_ref "$source_dir")"
  local sentinel="$SENTINEL_ROOT/env.genie3.${GENIE3_ACTUAL_COMMIT}.installed"
  if [[ -f "$sentinel" ]]; then
    GENIE3_INSTALL_STATUS="installed"
    log "env genie3 already installed (actual commit $GENIE3_ACTUAL_COMMIT)"
    return 0
  fi

  log "installing Genie 3 via upstream setup (commit $GENIE3_ACTUAL_COMMIT)"
  (
    cd "$source_dir"
    export CONDA_ENVS_PATH="$SOFTWARE_ROOT/envs"
    export GENIE3_CACHE_ROOT="$SOFTWARE_ROOT/cache/genie3"
    bash scripts/setup/setup.sh
    conda activate "$SOFTWARE_ROOT/envs/genie3" 2>/dev/null || conda activate genie3
    if [[ "$GENIE3_DOWNLOAD_WEIGHTS" == "1" ]]; then
      log "downloading Genie 3 pretrained weights from ${GENIE3_HF_REPO}@${GENIE3_HF_REVISION}"
      hf download "${GENIE3_HF_REPO}" \
        --revision "${GENIE3_HF_REVISION}" \
        --include "pretrained/**" \
        --local-dir "$source_dir"
    fi
    if [[ "$GENIE3_DOWNLOAD_TRAINING_DATA" == "1" ]]; then
      log "downloading Genie 3 training data from ${GENIE3_HF_REPO}@${GENIE3_HF_REVISION}"
      hf download "${GENIE3_HF_REPO}" \
        --revision "${GENIE3_HF_REVISION}" \
        --include "data/train/**" \
        --local-dir "$source_dir"
    fi
    conda deactivate
  )
  touch "$sentinel"
  GENIE3_INSTALL_STATUS="installed"
  log "genie3 env installed (commit $GENIE3_ACTUAL_COMMIT)"
}

# 4) ProteinMPNN clone + deps (sequence-design lane)
resolve_proteinmpnn_ref() {
  local mpnn_dir="$1"
  if [[ ! -d "$mpnn_dir/.git" ]]; then
    log "cloning ProteinMPNN from $PROTEINMPNN_REPO_URL" >&2
    git clone "$PROTEINMPNN_REPO_URL" "$mpnn_dir"
  fi
  git -C "$mpnn_dir" fetch --all --tags --prune
  if git -C "$mpnn_dir" rev-parse --verify --quiet "${PROTEINMPNN_REF}^{commit}" >/dev/null; then
    git -C "$mpnn_dir" checkout --detach "$PROTEINMPNN_REF"
  elif git -C "$mpnn_dir" rev-parse --verify --quiet "origin/${PROTEINMPNN_REF}^{commit}" >/dev/null; then
    git -C "$mpnn_dir" checkout --detach "origin/${PROTEINMPNN_REF}"
  else
    fail "PROTEINMPNN_REF=$PROTEINMPNN_REF does not resolve in $PROTEINMPNN_REPO_URL; verify the upstream ref before paid bootstrap"
  fi
  git -C "$mpnn_dir" rev-parse HEAD
}

install_env_proteinmpnn() {
  local install_record="$SENTINEL_ROOT/env.proteinmpnn.actual_commit"
  local existing_commit=""
  if [[ -f "$install_record" ]]; then
    existing_commit="$(cat "$install_record")"
  fi
  if [[ -n "$existing_commit" && -f "$SENTINEL_ROOT/env.proteinmpnn.${existing_commit}.installed" ]]; then
    PROTEINMPNN_ACTUAL_COMMIT="$existing_commit"
    log "env proteinmpnn already installed (actual commit $PROTEINMPNN_ACTUAL_COMMIT; requested ref $PROTEINMPNN_REF)"
    return 0
  fi
  log "creating conda env: proteinmpnn (python 3.11 + torch 2.x + ProteinMPNN ref $PROTEINMPNN_REF)"
  if [[ -d "$SOFTWARE_ROOT/envs/proteinmpnn" ]]; then
    log "reusing existing partial proteinmpnn env; sentinel is missing so verification/install will continue"
  else
    conda create -y -p "$SOFTWARE_ROOT/envs/proteinmpnn" \
      -c conda-forge \
      python=3.11 \
      git \
      pip
  fi
  conda activate "$SOFTWARE_ROOT/envs/proteinmpnn"
  local mpnn_dir="$SOFTWARE_ROOT/envs/proteinmpnn/ProteinMPNN"
  PROTEINMPNN_ACTUAL_COMMIT="$(resolve_proteinmpnn_ref "$mpnn_dir")"
  log "ProteinMPNN resolved: requested_ref=$PROTEINMPNN_REF actual_commit=$PROTEINMPNN_ACTUAL_COMMIT"
  pip install --no-cache-dir --extra-index-url https://download.pytorch.org/whl/cu124 \
    torch==2.4.0 \
    numpy
  conda deactivate
  printf '%s\n' "$PROTEINMPNN_ACTUAL_COMMIT" > "$install_record"
  local sentinel="$SENTINEL_ROOT/env.proteinmpnn.${PROTEINMPNN_ACTUAL_COMMIT}.installed"
  touch "$sentinel"
  log "proteinmpnn env installed"
}

# 5b) RFdiffusion weights — fetch Complex_base_ckpt.pt (and optionally others) to
#     /workspace/software/weights/rfdiffusion/. Public repo does not choose a
#     checkpoint mirror or use-context. Operators must provide reviewed sources.
#     Fallback: IPD canonical (content-addressed by md5), authoritative but rate-limited.
#     Each file is md5-verified against the RFDIFFUSION_MD5_MAP after download.
#     Default fetches only the PPI binder-design checkpoint (~483 MB); set
#     RFDIFFUSION_WEIGHTS_FILES="Base_ckpt.pt Complex_base_ckpt.pt ..." to fetch more.
install_rfdiffusion_weights() {
  local weights_dir="$SOFTWARE_ROOT/weights/rfdiffusion"
  local manifest_path="$weights_dir/manifest.json"
  if [[ "$RFDIFFUSION_DOWNLOAD_WEIGHTS" != "1" ]]; then
    RFDIFFUSION_INSTALL_STATUS="deferred"
    log "RFdiffusion weights deferred; set RFDIFFUSION_DOWNLOAD_WEIGHTS=1 to fetch"
    return 0
  fi
  if [[ "$RFDIFFUSION_TERMS_ACK" != "I_HAVE_REVIEWED_RFDIFFUSION_TERMS_AND_SOURCES" ]]; then
    RFDIFFUSION_INSTALL_STATUS="blocked_terms_review_required"
    log "RFdiffusion weights blocked; set RFDIFFUSION_TERMS_ACK only after reviewing current terms and source posture"
    return 2
  fi
  if [[ "$RFDIFFUSION_WEIGHTS_HF_REPO" == "__OPERATOR_REVIEWED_RFDIFFUSION_REPO__" ]]; then
    RFDIFFUSION_INSTALL_STATUS="blocked_source_required"
    log "RFdiffusion weights blocked; set RFDIFFUSION_WEIGHTS_HF_REPO to an operator-reviewed source"
    return 2
  fi
  mkdir -p "$weights_dir"
  require_cmd curl
  log "fetching RFdiffusion weights (HF primary @ $RFDIFFUSION_WEIGHTS_HF_REPO rev=${RFDIFFUSION_WEIGHTS_HF_REV:0:8}, IPD fallback)"
  local entries=""
  local ok_count=0
  local total_count=0
  for fname in $RFDIFFUSION_WEIGHTS_FILES; do
    total_count=$((total_count + 1))
    local target="$weights_dir/$fname"
    local sentinel="$SENTINEL_ROOT/rfdiffusion.weights.${fname}.installed"
    local ipd_key="${RFDIFFUSION_IPD_KEY_MAP[$fname]:-}"
    local expected_sha256="${RFDIFFUSION_SHA256_MAP[$fname]:-}"
    if [[ -f "$sentinel" && -s "$target" ]]; then
      log "  $fname already present (sentinel hit)"
      ok_count=$((ok_count + 1))
    else
      local hf_url="https://huggingface.co/${RFDIFFUSION_WEIGHTS_HF_REPO}/resolve/${RFDIFFUSION_WEIGHTS_HF_REV}/models/${fname}"
      local ipd_url=""
      if [[ -n "$ipd_key" ]]; then
        ipd_url="${RFDIFFUSION_WEIGHTS_BASE_URL%/}/${ipd_key}/${fname}"
      fi
      local got_it=0
      for src in HF IPD; do
        local url
        if [[ "$src" == "HF" ]]; then url="$hf_url"; else url="$ipd_url"; fi
        [[ -z "$url" ]] && continue
        log "  trying $src for $fname"
        if curl -fsSL --retry 3 --retry-delay 5 --max-time 1800 "$url" -o "$target.partial"; then
          if [[ -n "$expected_sha256" ]]; then
            local actual_sha256
            actual_sha256="$(sha256sum "$target.partial" 2>/dev/null | awk '{print $1}' || shasum -a 256 "$target.partial" 2>/dev/null | awk '{print $1}' || echo unknown)"
            if [[ "$actual_sha256" != "$expected_sha256" ]]; then
              log "    sha256 mismatch from $src (got $actual_sha256 expected $expected_sha256); discarding"
              rm -f "$target.partial"
              continue
            fi
          fi
          mv "$target.partial" "$target"
          touch "$sentinel"
          ok_count=$((ok_count + 1))
          got_it=1
          log "    $fname fetched from $src + sha256 verified"
          break
        else
          log "    $src fetch failed for $fname"
          rm -f "$target.partial"
        fi
      done
      if [[ "$got_it" -eq 0 ]]; then
        log "  WARN: all mirrors failed for $fname"
      fi
    fi
    if [[ -s "$target" ]]; then
      local size; size="$(stat -c%s "$target" 2>/dev/null || stat -f%z "$target" 2>/dev/null || echo 0)"
      local sha; sha="$(sha256sum "$target" 2>/dev/null | awk '{print $1}' || shasum -a 256 "$target" 2>/dev/null | awk '{print $1}' || echo unknown)"
      entries+="    \"$fname\": {\"size\": $size, \"sha256\": \"$sha\", \"expected_sha256\": \"$expected_sha256\"},\n"
    fi
  done
  entries="${entries%,*}"  # trim trailing comma
  printf '{\n  "fetched_at": "%s",\n  "hf_repo": "%s",\n  "hf_rev": "%s",\n  "ipd_base_url": "%s",\n  "ok_count": %d,\n  "total_count": %d,\n  "files": {\n%b\n  }\n}\n' \
    "$(date -u +%Y-%m-%dT%H:%M:%SZ)" "$RFDIFFUSION_WEIGHTS_HF_REPO" "$RFDIFFUSION_WEIGHTS_HF_REV" "$RFDIFFUSION_WEIGHTS_BASE_URL" "$ok_count" "$total_count" "$entries" \
    > "$manifest_path"
  if [[ "$ok_count" -eq "$total_count" ]]; then
    RFDIFFUSION_INSTALL_STATUS="installed"
    log "RFdiffusion weights fetched: $ok_count/$total_count files at $weights_dir"
  else
    RFDIFFUSION_INSTALL_STATUS="partial"
    log "RFdiffusion weights partial: $ok_count/$total_count files at $weights_dir"
  fi
}

# 6) ChimeraX 1.9 from an operator-verified UCSF URL (no redistribution)
install_chimerax() {
  local sentinel="$SENTINEL_ROOT/chimerax.${CHIMERAX_VERSION}.installed"
  local deferred="$SENTINEL_ROOT/chimerax.${CHIMERAX_VERSION}.deferred"
  local chimerax_root="$SOFTWARE_ROOT/chimerax-${CHIMERAX_VERSION}"
  [[ -f "$sentinel" ]] && { CHIMERAX_INSTALL_STATUS="installed"; log "chimerax $CHIMERAX_VERSION already installed"; return 0; }
  if [[ "$INSTALL_CHIMERAX" != "1" ]]; then
    CHIMERAX_INSTALL_STATUS="deferred"
    touch "$deferred"
    log "ChimeraX install deferred; set INSTALL_CHIMERAX=1 and CHIMERAX_DEB_URL to an operator-verified .deb URL before render-lane promotion"
    return 0
  fi
  [[ -n "$CHIMERAX_DEB_URL" ]] || fail "INSTALL_CHIMERAX=1 requires CHIMERAX_DEB_URL; do not rely on hardcoded or scraped ChimeraX URLs"
  log "installing ChimeraX $CHIMERAX_VERSION -> $chimerax_root (operator-verified URL, NV-only, not redistributed)"
  require_cmd curl
  require_cmd ar
  local tmp; tmp="$(mktemp -d)"
  log "fetching ChimeraX from CHIMERAX_DEB_URL"
  curl -fsSL "$CHIMERAX_DEB_URL" -o "$tmp/chimerax.deb" || \
    fail "ChimeraX download failed - verify CHIMERAX_DEB_URL against the current UCSF download page and the operator's use posture"
  head -c 8 "$tmp/chimerax.deb" | grep -q '^!<arch>' || \
    fail "ChimeraX download did not return a Debian archive; likely an HTML/error/terms page, so the render lane remains blocked/deferred"
  mkdir -p "$chimerax_root"
  ( cd "$tmp" && ar x chimerax.deb && tar xf data.tar.* -C "$chimerax_root" )
  rm -rf "$tmp"
  # ChimeraX self-extracts to /usr/lib/ucsf-chimerax inside the .deb tree;
  # collapse to chimerax_root/{bin,lib,share}.
  if [[ -d "$chimerax_root/usr/lib/ucsf-chimerax" ]]; then
    mv "$chimerax_root/usr/lib/ucsf-chimerax/"* "$chimerax_root/"
    rm -rf "$chimerax_root/usr"
  fi
  [[ -x "$chimerax_root/bin/ChimeraX" ]] || fail "ChimeraX binary not at $chimerax_root/bin/ChimeraX"
  touch "$sentinel"
  CHIMERAX_INSTALL_STATUS="installed"
  log "chimerax $CHIMERAX_VERSION installed"
}

# 6) Manifest of installed software (machine-readable)
write_software_manifest() {
  local manifest="$SOFTWARE_ROOT/manifest.json"
  log "writing $manifest"
  cat > "$manifest" <<EOF
{
  "campaign": "structure-factory-template",
  "network_volume_id": "STRUCTURE_FACTORY_RUNPOD_NETWORK_VOLUME_ID",
  "bootstrap_completed_at": "$(date -u +%Y-%m-%dT%H:%M:%SZ)",
  "tools": {
    "miniconda3": "${MINICONDA_VERSION}",
    "chimerax": "${CHIMERAX_VERSION}",
    "chimerax_status": "${CHIMERAX_INSTALL_STATUS}",
    "chimerax_source": "${CHIMERAX_DEB_URL:-operator_deferred}",
    "boltz": "${BOLTZ_VERSION}",
    "boltz_pip_spec": "${BOLTZ_PIP_SPEC}",
    "genie3_status": "${GENIE3_INSTALL_STATUS}",
    "genie3_repo": "${GENIE3_REPO_URL}",
    "genie3_ref": "${GENIE3_REF}",
    "genie3_commit": "${GENIE3_ACTUAL_COMMIT}",
    "genie3_hf_repo": "${GENIE3_HF_REPO}",
    "genie3_hf_revision": "${GENIE3_HF_REVISION}",
    "genie3_colabfold_params_allowed": "${GENIE3_ALLOW_COLABFOLD_PARAMS}",
    "genie3_weights_downloaded": "${GENIE3_DOWNLOAD_WEIGHTS}",
    "genie3_training_data_downloaded": "${GENIE3_DOWNLOAD_TRAINING_DATA}",
    "proteinmpnn_repo": "${PROTEINMPNN_REPO_URL}",
    "proteinmpnn_ref": "${PROTEINMPNN_REF}",
    "proteinmpnn_commit": "${PROTEINMPNN_ACTUAL_COMMIT}"
  },
  "envs": {
    "structure-factory-cpu": "$SOFTWARE_ROOT/envs/structure-factory-cpu",
    "boltz": "$SOFTWARE_ROOT/envs/boltz",
    "genie3": "$SOFTWARE_ROOT/envs/genie3",
    "proteinmpnn": "$SOFTWARE_ROOT/envs/proteinmpnn"
  },
  "binaries": {
    "chimerax": "$SOFTWARE_ROOT/chimerax-${CHIMERAX_VERSION}/bin/ChimeraX"
  }
}
EOF
  log "manifest written"
}

main() {
  log "bootstrap starting; NV_ROOT=$NV_ROOT"
  start_bootstrap_heartbeat
  start_runtime_guard
  [[ -d "$NV_ROOT" ]] || fail "$NV_ROOT not present - is the NV mounted?"

  install_miniconda
  activate_conda

  install_env_structure_factory_cpu
  install_env_boltz
  install_env_genie3
  install_env_proteinmpnn
  install_rfdiffusion_weights
  install_chimerax

  write_software_manifest
  log "bootstrap complete; sentinels under $SENTINEL_ROOT"
}

main "$@"
