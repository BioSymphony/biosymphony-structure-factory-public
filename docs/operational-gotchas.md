# Operational Gotchas Catalog

This catalog describes 45 documented failure classes for multi-stage structural-biology campaigns on RunPod and other cloud GPU providers. Read it before a dispatch that costs money or wall-clock time.

The goal is to detect each class **before** a dispatch burns time and money, and to have a one-line fix ready when it does fire. Most classes have a paste-ready pre-flight probe.

This catalog is target-agnostic. The lessons apply to any binder-design, cofold, model-comparison, or screening campaign on managed GPU compute.

---

## Failure Class Index

| # | Class | Symptom | Pre-flight probe |
|---|-------|---------|------------------|
| 1  | RunPod NV-bound capacity      | `POST /pods` 200 with "no instances available" | GraphQL `gpuTypes{nodeGroupDatacenters{gpuAvailability}}` |
| 2  | RunPod stuck-pod              | `desiredStatus=RUNNING`, port 22 connection-refused | check `runtime` field on `get-pod`; wait 12 min |
| 3  | RunPod multi-machine outage   | 6+ machine IDs in stuck state in <70 min across DCs | session-local bad-machine blocklist |
| 4  | RunPod 64KB payload limit     | `POST /pods` 500 "Something went wrong" | `len(dockerStartCmd) <= 50_000` before sending |
| 5  | CPU vcpuCount disk cap        | Pod create rejected on `containerDiskInGb` | `vcpuCount >= 2` for 20GB disk |
| 6  | Conda TOS not accepted        | `CondaToSNonInteractiveError` | `conda tos --json` |
| 7  | Conda env without pip         | `pip install` lands packages in system Python | `<env>/bin/pip --version` |
| 8  | Channel conflict (libgcc-ng)  | Solver fails: defaults vs conda-forge toolchain conflict | strip toolchain pins from env.yml |
| 9  | DGL CUDA wheel resolves to CPU| `DGLError: Operator Range does not support cuda device` | `pip show dgl \| grep Version` → must contain `+cu` |
| 10 | huggingface_hub.commands gone | `ModuleNotFoundError: huggingface_hub.commands` | use `huggingface-cli` or `snapshot_download` |
| 11 | apt-install fails             | `E: Unable to locate package <X>` | pre-stage debs on a network volume |
| 12 | UCSF download CGI is JS-gated | `wget` returns JS form HTML, not `.deb` | pre-stage `.deb` via S3 or operator transfer |
| 13 | rc-foundry rfd3 needs py3.12  | pip install fails on 3.11 | `python --version` before install |
| 14 | BindCraft Rosetta crash       | `surf_vol.cc:164` segfault in BuriedUnsatHbonds | try/except patch around `report_sm` |
| 15 | dockerStartCmd overrides SSH  | Pod boots but no SSH | write `$PUBLIC_KEY` to authorized_keys in startCmd |
| 16 | REST `ports` must be JSON arr | API rejects with schema error | array, not comma-separated string |
| 17 | RFdiffusion contig vs PDB     | `'A', N is not in pdb file!` after weights load | derive contig range from actual PDB ATOM records |
| 18 | RFD3 atom-spec vs residue     | `Could not find requested atoms 'CG,CZ' in atom array` | decode atom names → residue family pre-dispatch |
| 19 | IPD URL segments ≠ md5        | "checksum mismatch" on weights | use sha256 (HF LFS oid), not URL hash |
| 20 | Boltz CCD partial extract     | `CCD component ALA not found` | check `mols/ALA.pkl` exists |
| 21 | Boltz torch driver mismatch   | `NVIDIA driver too old (12040)` | `torch.__version__` vs `nvidia-smi` CUDA |
| 22 | Boltz `--write_full_pae` off  | downstream ipSAE fails: no `pae` in NPZ | grep `--write_full_pae` in entrypoint |
| 23 | Boltz `affinity_summary.json` | ranking reads small-molecule head, not protein iPTM | read `confidence_<name>.json` only |
| 24 | Chai-1 ESM-no-MSA default     | iPTM 0.3 lower than Boltz on identical complex | `use_esm_embeddings=False` + `msa_directory=...` |
| 25 | ColabFold MMseqs2 rate-limit  | 20+ jobs throttled, designs stall | pre-compute target `.a3m` once |
| 26 | Genie 3 pretrained CWD        | `FileNotFoundError: pretrained/v1/config.yaml` | `cd $GENIE3_HOME &&` before invoking |
| 27 | Genie 3 motif scaffolding     | Triad RMSD low but TM-score low (no fold rediscovery) | report triad ≠ fold separately |
| 28 | PDB chain ≠ what you assumed  | designed against the wrong chain for hours | verify first-20-aa vs UniProt before dispatch |
| 29 | Deposited PDB lacks domain    | pocket detection fails for residues that aren't resolved | SIFTS REST: confirm resolved range pre-dispatch |
| 30 | PepGLAD env.yml incomplete    | OpenMM cpu-only crash on GPU pod | manual `pip install ray torch-scatter torch-cluster` |
| 31 | PepGLAD ckpt URL drift        | `wget release/codesign.ckpt` 404 | local cached checkpoint copy |
| 32 | PepGLAD `detect_pocket` JSON  | Parser expected dict, file is list of `[chain,[resi,ins]]` | parse as list, not dict |
| 33 | PepGLAD OOD length            | CUDA device-side assert at length 20-30 | stay in 10-15 / `n_samples` ≤5 |
| 34 | STAGE_COMPLETE on empty out   | Orchestrator declares success on 0 outputs | gate marker on `ls *.pdb \| wc -l >= expected` |
| 35 | RFpeptides IGSO3 first-run    | 13-min hang on first invocation | pre-stage schedule pickle to NV |
| 36 | "Completed" agent looks dead  | Worker shows `status: completed`; assumed unreachable | use `SendMessage` to resume in background |
| 37 | Memory entries are point-in-time | Doc says "Boltz X ready"; actual is broken | run NV audit before trusting docs |
| 38 | Reading the wrong cofold output | iPTM gate passes false-positive on `affinity_summary.json` | gate on `confidence_*.json` `pair_chains_iptm` |
| 39 | NV mount-point drift          | Path `/workspace/nv/X` vs `/workspace/X` between pods | `mount \| grep workspace` first |
| 40 | Quota silently full           | Install fails midway with no specific error | `df -BG /workspace` in audit |
| 41 | Boltz `--num_workers>1` race  | CUDA `_cuda_init` fails on shared GPU host | force `--num_workers 1` |
| 42 | RFdiffusion polyG outputs     | Cofold iPTM uniformly ~0.1 | run ProteinMPNN before cofold |
| 43 | PepGLAD two-chain output      | Binder extractor reads wrong chain | select shortest chain ≥5 aa |
| 44 | ProteinMPNN on cyclic peptides | Zero sequences for cyclic backbones | use designer that bundles MPNN |
| 45 | Monitor pgrep race            | False-positive workload-dead detection | multi-process pgrep + heartbeat-age |

---

## Capacity and infrastructure

### 1. RunPod NV-bound capacity (DC ∩ GPU ∩ machine-has-NV intersection empty)

- **Symptom:** `POST /pods` returns 200 with `"errors": [..."There are no instances currently available"...]` while a probe WITHOUT `networkVolumeId` lands fine.
- **Root cause:** the scheduler filter is three-dimensional. Only the subset of machines in the chosen DC that mount your NV need a free GPU of the chosen type. The intersection can be empty even when each axis has capacity.
- **Pre-flight probe:**
  ```bash
  curl -sS -X POST https://api.runpod.io/graphql \
    -H "Authorization: Bearer $RUNPOD_API_KEY" \
    -H "Content-Type: application/json" \
    -d '{"query":"query($f:GpuTypeFilter){gpuTypes(input:$f){id nodeGroupDatacenters{id gpuAvailability(input:{gpuCount:1 secureCloud:true}){available}}}}","variables":{"f":{"ids":["NVIDIA RTX A6000","NVIDIA L40","NVIDIA L40S"]}}}' \
    | jq '.data.gpuTypes[] | {id, dcs:[.nodeGroupDatacenters[]|select(.gpuAvailability.available==true)|.id]}'
  ```
- **Fix:** run a parallel-retry loop across GPU types × cloud types. Most intersections clear within ~5 min.

### 2. RunPod stuck-pod (control plane RUNNING, container never starts)

- **Symptom:** `desiredStatus: RUNNING`, public IP + port assigned, `runtime: null`, port 22 connection-refused for the entire pod lifetime.
- **Root cause:** either a slow-first-boot host (12 min SSH bind on fresh docker pull) or a wedged machine.
- **Pre-flight probe:** check `get-pod`'s `runtime` field. If populated, the container is fine and SSH is just lagging.
- **Fix:** wait at least **12 minutes** before considering the pod wedged. If still stuck after 12 min and `runtime: null` the whole time, delete and retry without `machine.id` pin.

### 3. RunPod multi-machine outage

- **Symptom:** 6+ different machine IDs stuck in <70 min across DCs and cloud types.
- **Root cause:** provider-side scheduler bug that re-assigns known-bad machines across declared DCs.
- **Fix:** maintain a session-local bad-machine blocklist; refuse to dispatch onto seen-wedged machine IDs. Recovery window is typically 2-4 hours.

### 4. RunPod POST /pods 64KB payload limit

- **Symptom:** `POST /pods` 500 "create pod: Something went wrong. Please try again later or contact support."
- **Root cause:** `dockerStartCmd` > ~64 KB. The error message is identical to a transient platform outage, so the cause is not obvious from the response.
- **Pre-flight probe:**
  ```bash
  python3 -c "import sys,json; d=json.load(open('payload.json')); print(len(d['dockerStartCmd'][2]))"
  ```
- **Fix:** gzip + base64 the embedded script, decode at runtime. Or move the script to a network volume and reference it from the start command.

### 5. CPU flavor disk caps scale with vcpuCount

- **Symptom:** Pod create rejected when `containerDiskInGb` exceeds the flavor cap for the chosen `vcpuCount`.
- **Pre-flight probe:** before creating a CPU pod, set `vcpuCount` so its disk cap exceeds `containerDiskInGb`:
  - cpu3c v=1: 10 GB; v=2: 20 GB
  - cpu3g v=1: 10 GB
  - cpu5c v=1: 15 GB
  - cpu5g v=1: 15 GB

### 39. NV mount-point drift between pods

- **Symptom:** smoke #1 mounts NV at `/workspace/nv`, smoke #2 mounts at `/workspace`. Path-hardcoded scripts break.
- **Pre-flight probe (in dispatch script):** `mount | grep -E ' on /workspace ' | head -1`
- **Fix:** every script should resolve the mount root dynamically: `NV_ROOT=$(mount | awk '$3 ~ /^\/workspace/ {print $3; exit}')`.

### 40. NV free space < 15 GB

- **Symptom:** install fails midway with a truncated tarball or no-space-left error.
- **Pre-flight probe:** `df -BG /workspace | awk 'NR==2 {print $4}'` — must be > 15 GB.
- **Fix:** investigate `du -sh /workspace/* | sort -h` and remove agent-orphaned scratch dirs.

---

## Conda and Python

### 6. Conda TOS not accepted

- **Symptom:** `CondaToSNonInteractiveError: You must accept the Terms of Service for the channel...`.
- **Pre-flight probe:**
  ```bash
  conda tos --json | jq '.[] | select(.channel | test("anaconda.com"))'
  ```
- **Fix (run as first line of any conda-using entrypoint):**
  ```bash
  conda tos accept --override-channels --channel https://repo.anaconda.com/pkgs/main
  conda tos accept --override-channels --channel https://repo.anaconda.com/pkgs/r
  ```

### 7. `conda create -y -n FOO python=3.11` without `pip`

- **Symptom:** `conda activate FOO; pip install torch` lands a 5 GB torch in `/usr/local/lib/python3.11/dist-packages/`, not inside FOO.
- **Root cause:** `conda create` does NOT include pip unless explicitly requested. `which pip` resolves to system pip after activation.
- **Pre-flight probe (in dispatch script):**
  ```bash
  conda activate FOO
  which pip | grep -q "$CONDA_PREFIX" || { echo "FAIL: pip not in env"; exit 1; }
  ```
- **Fix:** `conda create -y -n FOO python=3.11 pip` (include pip explicitly), or pivot entirely to system Python and skip the conda env.

### 8. Channel conflict on libgcc-ng / openmm

- **Symptom:** `Mamba solver failed` after 60+ sec of churn; output mentions `libgcc-ng=11.2.0` (defaults) vs `libgcc>=14` (conda-forge openmm).
- **Root cause:** an env.yml pins `libgcc-ng=11.2.0` from `defaults` while pulling `openmm` from `conda-forge` (which needs ≥14).
- **Fix:** strip toolchain pins from env.yml before `mamba env create`:
  ```bash
  grep -vE '_libgcc_mutex|_openmp_mutex|libgcc-ng|libstdcxx-ng|libgomp|ca-certificates|openssl' \
    env.yml > env_patched.yml
  sed -i '/^channels:/,/^[^ ]/{/defaults/d}' env_patched.yml
  mamba env create -f env_patched.yml
  ```

### 9. DGL CUDA wheel resolves to PyPI's CPU-only build

- **Symptom:** `dgl.__version__ == '1.1.3'` (imports fine!) but `DGLError: Operator Range does not support cuda device` inside a forward pass.
- **Root cause:** `pip install 'dgl==1.1.3' --extra-index-url <dgl url>` picks PyPI's plain `1.1.3` because PyPI is consulted first.
- **Pre-flight probe:**
  ```bash
  python -c "import dgl; v=dgl.__version__; assert '+cu' in v, f'CPU DGL: {v}'"
  ```
- **Fix:** pin the local-version segment and use `-f`:
  ```bash
  pip install --no-cache-dir 'dgl==1.1.3+cu121' -f https://data.dgl.ai/wheels/cu121/repo.html
  ```

### 10. `huggingface_hub.commands` removed in 0.20+

- **Symptom:** `ModuleNotFoundError: No module named 'huggingface_hub.commands'`.
- **Root cause:** the `python -m huggingface_hub.commands.huggingface_cli` invocation path is long-dead.
- **Fix:** use the shell entry point or the Python API:
  ```python
  from huggingface_hub import snapshot_download
  snapshot_download(repo_id=REPO, revision=REV, local_dir=cache)
  ```

### 11. `apt install <X>` fails on RunPod base image

- **Symptom:** `E: Unable to locate package <X>` → cascade failure.
- **Root cause:** stale apt sources, no `apt update` in the base image, or transient rate-limit.
- **Fix:** pre-stage `.debs` at NV bake time:
  ```bash
  apt-get install -y --download-only unzip wget curl git build-essential rsync jq
  cp /var/cache/apt/archives/*.deb /workspace/installers/apt-packages/
  ```
  At dispatch: `dpkg -i /workspace/installers/apt-packages/*.deb || apt-get install -f -y`.

### 12. UCSF ChimeraX download CGI is JS+cookie gated

- **Symptom:** `wget` of the UCSF site returns the JS-rendered form HTML, not the `.deb`.
- **Root cause:** UCSF gates the download behind a one-time terms-acceptance click per session.
- **Fix:** supply an approved installer path or user-selected download client after license review. A Network Volume is one option.

### 13. `rc-foundry[rfd3]` is Python 3.12 only

- **Symptom:** pip install fails with a version-incompatibility error on 3.11.
- **Fix:** create a dedicated env: `conda create -n rfd3 python=3.12 pip && conda activate rfd3 && pip install 'rc-foundry[rfd3]'`.

### 14. BindCraft Rosetta `surf_vol.cc:164` crash

- **Symptom:** segfault in `BuriedUnsatHbonds.report_sm` during interface scoring.
- **Fix:** try/except wrapper around the report call. The crash does not invalidate the rest of the metrics; gate on whether the wrapper caught a known signature.

### 15. RunPod custom `dockerStartCmd` overrides default SSH

- **Symptom:** pod boots `RUNNING` but you can't SSH in.
- **Fix:** include in dockerStartCmd: `echo "$PUBLIC_KEY" >> /root/.ssh/authorized_keys && chmod 600 /root/.ssh/authorized_keys`.

### 16. REST `ports` must be JSON array

- **Symptom:** `POST /pods` returns 400 with a schema error.
- **Fix:** `"ports": ["22/tcp"]` (array), not `"ports": "22/tcp"`. Also: `memoryInGb` is not in the schema for this endpoint.

---

## Designer-specific gotchas

### 17. RFdiffusion contig range must match PDB residues

- **Symptom:** ~30-60s after dispatch (weights loaded): `('A', 18) is not in pdb file!` from `contigs.py`.
- **Pre-flight probe (in dispatch script, before sending):**
  ```python
  res = set()
  for line in open(pdb_file):
      if line.startswith('ATOM'):
          res.add((line[21], int(line[22:26])))
  nums = sorted(n for c,n in res if c==chain)
  assert contig_range == (min(nums), max(nums))
  ```
- **Fix:** derive the contig from the file, not the conceptual residue range. PDBs frequently have gaps at chain termini or near disordered loops.

### 18. RFD3 atom-spec must match residue identity

- **Symptom:** `pydantic_core._pydantic_core.ValidationError: Could not find requested atoms 'CG,CZ' in atom array`.
- **Root cause:** hotspot atom specs like `CG,CZ` are aromatic-specific (Phe/Tyr). If the residue at that position is Ile (only has `CG1,CG2,CD1`), the validation fails after weights load.
- **Pre-flight probe (must run first thing in any RFD3 worker):** decode atom names against the actual residue identity at each hotspot before dispatch:
  - `CG1/CG2` only: Val
  - `CG1/CG2/CD1`: Ile or Leu
  - `CG+CZ`: aromatic Phe/Tyr
  - `CG` only: Phe/Trp/Tyr/His/Met/Lys/Arg/Asn/Asp/Gln/Glu
- **Fix:** load the target PDB locally, extract the residue at each hotspot, and emit a compatible atom-spec.

### 19. IPD URL path-segment is not the md5 of the bytes

- **Symptom:** sha256 verification fails on RFdiffusion weight download despite a full-byte download.
- **Root cause:** the upstream `<key>` URL segment is an internal hash, not the md5 of the file body.
- **Fix:** integrity-check with sha256. The HuggingFace LFS oid is the source of truth, never the URL path segment.

### 26. Genie 3 CWD-dependent pretrained config

- **Symptom:** `FileNotFoundError: [Errno 2] No such file or directory: 'pretrained/v1/config.yaml'` (crashes within 3 sec of launch).
- **Root cause:** `genie3/cli.py` resolves `pretrained/v1/config.yaml` relative to CWD.
- **Fix:** always `cd $GENIE3_HOME &&` before invocation, or symlink `pretrained/` into the per-arm working directory.

### 27. Genie 3 motif scaffolding ≠ fold rediscovery

- **Symptom:** 25/25 triad RMSD < 2 Å (motif placement works) but 0/25 global TM-score ≥ 0.5 (the global fold is not rediscovered).
- **Lesson:** with only 3 anchor residues there is not enough information to pin a global fold. Genie 3 finds many topologies that hold the motif.
- **Fix:** for fold-rediscovery demos, add more conserved residues or shift to binder-design mode. Report triad RMSD and fold TM-score separately rather than blending them into one "success" metric.

### 30. Per-design env files are often incomplete

- **Symptom:** `ModuleNotFoundError: ray` or `torch_scatter` mid-run; `OpenMM CPU plugin missing` on a GPU pod.
- **Root cause:** upstream `env.yml` files commonly omit `ray`, `torch-scatter`, `torch-cluster` and ship CPU-only OpenMM.
- **Fix (after `mamba env create`):**
  ```bash
  pip install ray
  pip install torch-scatter -f https://data.pyg.org/whl/torch-2.4.0+cu124.html
  pip install torch-cluster -f https://data.pyg.org/whl/torch-2.4.0+cu124.html
  # Skip OpenMM relaxation; use Boltz / Rosetta FastRelax downstream
  ```

### 31. Designer checkpoint URLs drift

- **Symptom:** `wget https://github.com/.../releases/download/v1.0/codesign.ckpt` returns 404.
- **Root cause:** upstream may pull or rename releases without warning.
- **Fix:** keep a local cached copy of any checkpoint you depend on. Pre-flight audit gates on the local file's minimum size (some checkpoints are smaller than you might naively assume).

### 32. PepGLAD `detect_pocket.py` JSON is a list, not a dict

- **Symptom:** dispatch parser KeyError on `binding_site_residues`.
- **Root cause:** the actual output shape is:
  ```json
  [["R", [27, " "]], ["R", [28, " "]], ...]
  ```
  i.e. `[[chain, [resi, insertion_code]], ...]`. The shape is positional, not keyed.
- **Fix:** parse as a list of (chain, (resi, ins)) tuples, not a dict.

### 33. PepGLAD long-length is OOD

- **Symptom:** CUDA `device-side assert triggered` mid-design, no Python traceback.
- **Root cause:** PepGLAD's training distribution covers shorter peptides; very-long combined with many-samples pushes it out-of-distribution.
- **Fix:** stay in length 10-15 / `n_samples` ≤ 5 for the first pass. Expand only after a working baseline.

### 35. RFpeptides IGSO3 first-run hang

- **Symptom:** silent 13-min hang on first invocation, no log progress.
- **Fix:** pre-stage the `schedules/T_50_...schedule_linear.pkl` file to the network volume via a small warmup pod. Subsequent runs read the cached pickle and start immediately.

---

## Cofold scoring

### 20. Boltz CCD cache partial extract

- **Symptom:** `CCD component ALA not found` or similar.
- **Root cause:** Boltz auto-extraction of `mols.tar` is unreliable and commonly leaves a partial cache.
- **Pre-flight probe:**
  ```bash
  ls /workspace/software/boltz_cache/mols/ | wc -l   # should be ~40,000
  for X in ALA ARG ASN ASP CYS GLN GLU GLY HIS ILE LEU LYS MET PHE PRO SER THR TRP TYR VAL UNK; do
    test -f /workspace/software/boltz_cache/mols/$X.pkl || echo "MISSING: $X"
  done
  ```
- **Fix:**
  ```bash
  cd /workspace/software/boltz_cache && rm -rf mols && tar -xf mols.tar
  ln -sfn /workspace/software/boltz_cache ~/.boltz
  # In CLI: --cache MUST come BEFORE the positional input
  boltz predict --cache /workspace/software/boltz_cache --out_dir OUT ... inputs.yaml
  ```

### 21. Boltz torch CUDA version vs driver mismatch

- **Symptom:** `RuntimeError: The NVIDIA driver on your system is too old (found version 12040)`.
- **Root cause:** another worker bumped the Boltz env to a newer torch + cuda; the current pod driver is older.
- **Fix:** pin Boltz to a known-good env (system Python with torch 2.6.0+cu124 works; uninstall torchvision/torchaudio which pin torch 2.4.1 and conflict).

### 22. Boltz `--write_full_pae` flag missing

- **Symptom:** ipSAE rescore fails with "no `pae` key in NPZ".
- **Pre-flight probe:** `grep -- --write_full_pae runpod/entrypoints/*.sh` (or equivalent for your stack).
- **Fix:** every Boltz invocation must include `--write_full_pae`. Wall-time cost is <2%.

### 23. Boltz `affinity_summary.json` is the wrong file for protein-protein iPTM

- **Symptom:** ranking iPTM column populated from the small-molecule affinity head, not the protein-protein iPTM.
- **Pre-flight probe (in ranking synthesis code):** grep for which JSON file is being read; should be `confidence_<name>.json`, not `affinity_summary.json`.
- **Fix:** read `confidence_<name>.json` and use `pair_chains_iptm[binder, target]`. The affinity head is for small-molecule binding and does not apply to protein-protein interfaces.

### 24. Chai-1 silent ESM-no-MSA default

- **Symptom:** Chai iPTM ~0.3 lower than Boltz on identical complex.
- **Root cause:** `use_esm_embeddings=True` is the default, which runs single-sequence ESM mode. Apples-to-oranges against Boltz's MSA-driven prediction.
- **Pre-flight probe:** `grep "use_esm_embeddings" scripts/structure_factory/*.py` — should be `False` for protein-protein cofold.
- **Fix:**
  ```python
  run_inference(..., use_esm_embeddings=False, msa_directory="/workspace/msa_cache/<target>/")
  ```

### 25. ColabFold MMseqs2 rate-limit at ~20 jobs

- **Symptom:** designs stall after ~20 cofolds; the ColabFold API returns 429s.
- **Fix:** pre-compute the target `.a3m` once and pass to every per-design YAML's `msa:` field. Removes per-design API calls and the entire rate-limit class.

### 38. Reading the wrong Chai-1 iPTM field

- **Symptom:** Chai ranking disagrees with Boltz on the same designs.
- **Fix:** Chai-1 emits both global `iptm` and `per_chain_pair_iptm`. For binder/target ranking, use `per_chain_pair_iptm[binder, target]`, not the global `iptm`.

### 41. Boltz `--num_workers > 1` crashes on shared GPU hosts

- **Symptom:** Boltz multi-process CUDA init hits a "driver too old" race even when single-worker mode works on the same pod. Failure is in `_cuda_init`, not in inference.
- **Root cause:** multi-process CUDA initialization races on shared L40 / L40S hosts; only the first process binds correctly.
- **Fix:** force `--num_workers 1` for Boltz on community / shared cloud GPU hosts. Note that if Boltz fails even at `--num_workers 1` on a given pod, the host driver itself may be incompatible — pivot to AF2-Multimer + ipSAE rather than burning hours on a host-specific driver issue.

### 42. RFdiffusion outputs are backbone-only (polyG)

- **Symptom:** cofolding designs against the target gives uniformly meaningless iPTM ~0.1 across the batch.
- **Root cause:** RFdiffusion (and similar backbone-only generators) emits structures where all residues are labeled GLY as a placeholder. Cofold tools score polyG against any target as essentially noise.
- **Fix:** always run ProteinMPNN (SolubleMPNN for soluble targets) on RFdiffusion / RFpeptides / Genie 3 outputs **before** the cofold step. PepGLAD and BindCraft bundle sequence design implicitly. RFdiffusion's "backbone only" character is easy to forget when comparing across designer arms.

### 43. PepGLAD output PDBs contain two chains

- **Symptom:** binder extractor reads the wrong chain (often the target context, ~339 aa) instead of the actual designed peptide (~10-20 aa).
- **Root cause:** PepGLAD co-folds the peptide with the target context for scoring; the output PDB therefore contains BOTH chains, not just the designed peptide.
- **Fix:** binder extractor should select the **shortest chain with length ≥ 5 aa**, not chain A or chain B by default. Verify with a quick `pdb_select_chains` step before downstream cofold.

### 44. ProteinMPNN cyclic mode does not cover all cyclic constraints

- **Symptom:** RFpeptides cyclic backbones do not get sequences assigned; sequence design step produces zero output for cyclic peptides.
- **Root cause:** the head-to-tail cyclic constraint is not always representable in standard ProteinMPNN's masking scheme.
- **Fix:** for cyclic peptides, prefer designers that bundle their own sequence design (BindCraft-style stacks) or accept that vanilla ProteinMPNN may not produce valid sequences for some cyclic topologies. Always verify a sequence file is produced before launching cofold.

### 45. Monitor / supervisor race conditions through SSH heredocs

- **Symptom:** a monitor process declares the workload dead via `pgrep` even though the workload is still running; orchestration falsely terminates.
- **Root cause:** `pgrep -f "$pattern"` through an SSH heredoc can transiently return no matches due to process-table scan timing, especially when the workload spawns short-lived helpers.
- **Fix:** use multi-process pgrep with a OR-list and a heartbeat-age fallback:
  ```bash
  alive=N
  for p in name1 name2 name3; do
    pgrep -f "$p" >/dev/null && alive=Y
  done
  # Also: don't declare dead until the heartbeat file's mtime is older than 2× the expected interval.
  ```

---

## Target prep

### 28. PDB chain ID is not what you assume

- **Symptom:** worker designs against the wrong chain for hours. Often the chain you think is the receptor turns out to be a G-protein subunit, a Fab, an immunoglobulin partner, etc.
- **Pre-flight probe (in dispatch script, FIRST step):**
  ```bash
  head_seq=$(python3 - <<PY
  with open("$pdb") as f:
      seq = []
      seen = set()
      for line in f:
          if line.startswith("ATOM") and line[21] == "$chain" and line[12:16].strip() == "CA":
              n = int(line[22:26])
              if n not in seen:
                  seq.append(line[17:20])
                  seen.add(n)
              if len(seq) == 20: break
  print("".join({"ALA":"A","CYS":"C","ASP":"D","GLU":"E","PHE":"F","GLY":"G","HIS":"H","ILE":"I","LYS":"K","LEU":"L","MET":"M","ASN":"N","PRO":"P","GLN":"Q","ARG":"R","SER":"S","THR":"T","VAL":"V","TRP":"W","TYR":"Y"}[r] for r in seq))
  PY
  )
  [ "$head_seq" = "$expected" ] || { echo "WRONG CHAIN: got $head_seq"; exit 1; }
  ```
- **Fix:** always verify the first 20 residues of the chosen chain against the UniProt sequence of your intended target before downstream design.

### 29. Deposited PDB does not "cover the full receptor"

- **Symptom:** pocket detection fails because residues 26-136 (or another expected range) are not present in the deposited structure.
- **Root cause:** cryo-EM and X-ray depositions frequently omit flexible domains. Pre-activation states often lack ECDs; activated states often lack disordered N-/C-terminal tails.
- **Pre-flight probe:**
  ```bash
  curl -s https://www.ebi.ac.uk/pdbe/api/mappings/uniprot/<pdb_id> \
    | jq '."<pdb_id>".UniProt.<uniprot_id>.mappings[] | {start, end, unp_start, unp_end}'
  ```
- **Fix:** for binding-mode design, check the SIFTS mapping before dispatch. Choose a deposition that resolves the residues your design needs.

---

## Orchestration and dispatch

### 34. STAGE_COMPLETE emitted on zero outputs

- **Symptom:** stage 1 declares success; stages 2/3/4 cascade-run on partial data; "ALL_COMPLETE" fires with a fraction of planned outputs.
- **Root cause:** stage gates are exit-code-driven, not output-driven. `set -e` + `touch STAGE_COMPLETE` is unsafe because a script can fail silently and still exit 0 through `|| true` or unchecked branches.
- **Pre-flight probe (in worker.sh, BEFORE emitting marker):**
  ```bash
  python run_design.py || true   # don't propagate failure yet
  ACTUAL=$(ls "$OUT_DIR"/*.pdb 2>/dev/null | wc -l)
  if [ "$ACTUAL" -ge "$EXPECTED_COUNT" ]; then
    touch "$STAGE_DIR/STAGE_COMPLETE"
  else
    echo "FAILED: $ARM produced $ACTUAL/$EXPECTED" > "$STAGE_DIR/STAGE_FAILED"
    exit 1
  fi
  ```
- **Fix:** every worker validates output count before declaring success. The orchestrator polls for BOTH `STAGE_COMPLETE` and `STAGE_FAILED` markers, never just exit code. See `docs/no-false-success-hardening.md` for the broader principle.

### 36. Agent `status: completed` is resumable

- **Symptom:** a worker shows `status: completed`; assumed dead; spawn a fresh agent and lose all prior context.
- **Fix:** try `SendMessage` first. Completed agents resume in background with full prior context. Only spawn a fresh agent if "No agent named is currently addressable" comes back.

### 37. Memory entries are point-in-time, not live state

- **Symptom:** memory or a doc says "Tool X version Y ready"; actual state was bumped by another agent and is broken. Or: a recipe in this catalog cites a benchmark / version pin that has since been superseded by a newer release.
- **Fix:** run an NV / environment audit as the **first step of every campaign**. Update the manifest the moment any install pod modifies the volume. Never trust a written "ready" status without a live probe.
- **Currency dimension:** also run a primary-source freshness check before reusing any known-good recipe in this catalog. Check upstream repo HEAD (releases tab + recent commits), current release notes, and recent preprints (biorxiv, chemrxiv, arxiv) for newer versions and benchmark revisions. Record the version pin you used and the date of the check in the candidate ranking so a future agent can re-verify rather than re-discover. See [`tools/cofold-scoring-stack.md#currency-check-run-before-reusing-this-card`](../tools/cofold-scoring-stack.md) for a worked example of how a 2025 framework was superseded by a 2026 benchmark.

---

## Render (ChimeraX) and downstream

All ChimeraX-specific gotchas live in [`tools/chimerax-peptide-viz.md`](../tools/chimerax-peptide-viz.md). The most common one (UCSF download CGI is JS-gated) is captured above as class #12.

---

## How to use this catalog

1. **At session start:** scan the TL;DR; note any class you might trip over given your stack and target.
2. **Before any campaign dispatch:** run the pre-flight probes that apply to your stack. Most can be wrapped into one or two shell scripts.
3. **During the campaign:** any new failure mode → add a class to this catalog with symptom, root cause, probe, fix.
4. **After the campaign:** update the relevant `tools/*.md` cards with corrections so the gotcha lives at the point of use.

Adding a new class: keep the same shape (TL;DR row, then a detailed entry under the right section). The TL;DR is the part agents and operators scan; the detail is where the fix recipe lives.
