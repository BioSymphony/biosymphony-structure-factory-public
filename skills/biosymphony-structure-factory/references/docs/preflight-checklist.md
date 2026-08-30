# Preflight Checklist

**Purpose:** no paid GPU dispatch leaves this repo without passing every HARD gate below. Most of these gates are zero-cost deterministic checks that catch the most expensive failure modes before a worker burns time or money.

This file is the **pattern**, not a finished script. Each gate documents what to check, why it matters, and a paste-ready fix recipe. Adapt to your stack.

The companion catalog with detailed failure-mode explanations is [`docs/operational-gotchas.md`](operational-gotchas.md). The hardening principle is in [`docs/no-false-success-hardening.md`](no-false-success-hardening.md).

---

## How to use

1. Write a preflight config file (see "Config schema" below) declaring your campaign's expected accessions, hotspots, tools, and operator approval ceiling.
2. Run the preflight checks against the config.
3. Only on full PASS, dispatch.

```bash
python3 scripts/structure_factory/preflight_check.py \
    --config inputs/campaign_preflight_config.json
# Only on PASS:
bash scripts/structure_factory/campaign_launcher.sh \
    inputs/campaign_preflight_config.json
```

**Hard rule:** if the preflight check exits non-zero, do NOT dispatch. Fix the failed gate(s) first.

The launcher should refuse to dispatch when any HARD gate fails. SOFT gates emit warnings but allow dispatch with an explicit override.

---

## The gates

### G1 — PDB chain identity (HARD)

**What it does:** reads the first 20 residues of the named chain in the named PDB and compares against the expected sequence. PDB chain IDs do NOT always map to what you think — a chain labeled "B" may be a Gβ1, a Fab fragment, or another partner rather than your intended target.

**Why it matters:** designing against the wrong chain wastes a full pod's runtime. The incident pattern: a worker ran 5 hours of design before the chain identity error was caught visually in the rendered output.

**Fix recipe (one line):**
```python
assert extract_first_20(pdb, chain) == expected_first_20
```

**Operator approval:** N/A — this is a $0 deterministic check.

---

### G2 — Hotspot atom-spec validity (HARD)

**What it does:** for each declared hotspot residue + required atom set, asserts the atoms exist on that residue.

**Why it matters:** a hotspot spec asking for `CG,CZ` (aromatic ring atoms — Phe / Tyr) at a position that is actually Ile (atoms `CG1,CG2,CD1`) crashes RFdiffusion3's pydantic validator mid-run with a cryptic error. The incident pattern: 0/25 designs lost from an arm after weights had already loaded.

**Fix recipe:**
```bash
python3 scripts/structure_factory/validate_hotspots_for_rfd3.py \
    target.pdb A --spec '{"33":["CG","CZ"], "36":["CZ2","CH2"]}'
```

The validator decodes atom names against the actual residue identity at each hotspot. Common atom-set patterns:
- `CG1/CG2` only: Val
- `CG1/CG2/CD1`: Ile or Leu
- `CG+CZ`: aromatic Phe/Tyr
- `CG` only: Phe / Trp / Tyr / His / Met / Lys / Arg / Asn / Asp / Gln / Glu

**Operator approval:** N/A — $0 deterministic check.

---

### G3 — Tool availability on the network volume (HARD)

**What it does:** checks canonical NV paths for each tool listed in `required_tools`. Off-pod, this becomes a WARN with deferred verification by the worker.

**Why it matters:** dispatching against a tool that is missing on the network volume costs an install pod ($0.20-$1) plus all the lost wall-clock waiting for the dispatch to crash.

**Canonical paths to check (adapt to your NV layout):**
- `boltz` env directory
- `chai` env directory
- `ipsae.py` script
- `colabfold_batch` binary
- AF2 / colabfold params directory (large, ~5 GB+)
- `chimerax_*.deb` installer (UCSF download cannot be reached headlessly)
- `RFdiffusion` source tree

**Fix recipe:** if a tool is missing, spin a one-time install pod and bake the tool onto the NV. Update the NV manifest afterwards so the next preflight passes.

**Operator approval:** required if an install pod must spin (estimate per-tool).

---

### G4 — Boltz CCD cache (HARD)

**What it does:** lists the canonical CCD tokens (20 amino acids + UNK) in the Boltz cache `mols/` directory. If any `.pkl` is missing, FAIL.

**Why it matters:** Boltz auto-extraction of `mols.tar` is unreliable and commonly leaves a partial cache (~31,000 of ~40,000 files). The first complex prediction crashes with "CCD component ALA not found" or similar.

**Fix recipe:**
```bash
cd /workspace/software/boltz_cache
for X in ALA ARG ASN ASP CYS GLN GLU GLY HIS ILE LEU LYS MET PHE PRO SER THR TRP TYR VAL UNK; do
  test -f mols/${X}.pkl || tar -xf mols.tar mols/${X}.pkl
done
ln -sfn /workspace/software/boltz_cache ~/.boltz
```

**Operator approval:** N/A — cache fix runs in <1 min, costs ~$0.01.

---

### G5 — Chai-1 MSA flag presence (HARD)

**What it does:** greps your worker script for Chai-1 invocations. If found, asserts at least one of `--use-msa-server`, `--msa-directory`, `pre_msa_directory`, `use_msa_server=True`, or `msa_dir=`.

**Why it matters:** Chai-1's default is single-sequence ESM mode (`use_esm_embeddings=True`). Same complex on Boltz (MSA-driven) vs Chai-1 (no MSA) produces an apples-to-oranges iPTM gap, often ~0.3, that looks like a real disagreement but is actually a settings bug.

**Fix recipe:** pass `--use-msa-server --use-templates-server` to every Chai-1 invocation. For apples-to-apples vs Boltz, pre-compute the target MSA once and pass `--msa-directory` to both tools.

**Operator approval:** N/A.

---

### G6 — ipSAE / PAE matrix flags (HARD)

**What it does:** if your worker invokes Boltz, asserts `--write_full_pae` is present. If any fold or cofold lane will be scored, asserts the expected artifact list includes confidence sidecars for the exact reviewed model: PAE or equivalent interface-error matrix, per-residue pLDDT, confidence JSON, and hashes. Warns if PAE is dumped but no ipSAE rescore is wired in.

**Why it matters:** raw iPTM has ROC-AUC ~0.5 (random) for wet-lab binders per the Adaptyv n=3,766 study. ipSAE is a post-hoc rescore from the PAE matrix and is ~1.4× more precise. Multiple competition leaders abandoned raw iPTM gates entirely. If the stage saves only the scalar score, recovering the PAE or pLDDT later requires another fold and may not reproduce the same sample.

**Fix recipe:**
```bash
boltz predict --cache /workspace/software/boltz_cache \
    --write_full_pae --diffusion_samples 3 ... inputs.yaml
# then rescore:
python3 /workspace/ipsae/ipsae.py boltz_results_*/predictions/<stem>/
```

Declare the sidecar contract before launch:

```text
expected_artifacts:
  - <stem>.cif
  - confidence_<stem>.json
  - pae_<stem>.npz
  - plddt_<stem>.npz
  - hashes.json
```

See [`docs/confidence-sidecars.md`](confidence-sidecars.md) for the full rule.

**Operator approval:** N/A — `--write_full_pae` adds <2% wall time.

---

### G7 — Genie 3 CWD discipline (HARD)

**What it does:** if your worker invokes Genie 3, asserts the script either `cd`s to the Genie 3 install directory (or `$GENIE3_HOME`) or passes an absolute `--config-path` flag.

**Why it matters:** Genie 3's `cli.py` resolves `pretrained/v1/config.yaml` relative to CWD. A per-arm worker that `cd`s to its own per-arm directory crashes within 3 seconds of launch with a FileNotFoundError. If the worker emits STAGE_COMPLETE on bash exit, the failure cascades silently.

**Fix recipe:**
```bash
cd /workspace/genie3 && python -m genie3.cli generate \
    --output-dir /workspace/<campaign>/<stage>/<arm>/ ...
```

**Operator approval:** N/A.

---

### G8 — Output-count validation gates (HARD)

**What it does:** if your worker emits `STAGE_COMPLETE` markers, asserts the script has BOTH an output-count guard (`-ge $EXPECTED`, `ACTUAL`, `wc -l`) AND a counterpart `STAGE_FAILED` (or `STAGE_PARTIAL`) marker so the orchestrator can distinguish success from silent skip.

**Why it matters:** This is the single most expensive failure mode. The incident pattern: a 4-arm bake-off produced 0/25 designs in three arms because each arm hit a different first-order bug (apt-install fail, atom-spec mismatch, cwd-dependent config). The orchestrator emitted STAGE_COMPLETE on bash exit regardless. Subsequent stages cascaded with 1/4 of the planned inputs, ALL_COMPLETE fired, the pipeline "succeeded" on paper while producing degraded output.

**Fix recipe:**
```bash
python run_design.py || true   # capture exception, don't propagate failure yet
ACTUAL=$(ls "$OUTPUT_DIR"/*.pdb 2>/dev/null | wc -l)
if [ "$ACTUAL" -ge "$EXPECTED_COUNT" ]; then
  touch "$STAGE_DIR/STAGE_COMPLETE"
else
  echo "FAILED: $ARM produced $ACTUAL/$EXPECTED" > "$STAGE_DIR/STAGE_FAILED"
  exit 1
fi
```

The orchestrator polls for **both** markers and fails fast on `STAGE_FAILED`.

**Operator approval:** N/A. This is the most important gate in this file. A clean worker passes it for free; a copy-paste of an old script likely fails it loudly. See [`docs/no-false-success-hardening.md`](no-false-success-hardening.md) for the broader principle.

---

### G9 — Apt dependencies pre-staged (SOFT)

**What it does:** greps your worker script for `apt install` or `apt-get install` lines and warns on any found (except `apt-get install -f` for dependency-resolve).

**Why it matters:** `apt install <X>` at dispatch time is a coin flip. The apt repo can be rate-limited or temporarily missing a package, and the failure cascades silently if downstream code uses the binary that did not install. The incident pattern: `apt install unzip` failed → unzip never extracted a checkpoint zip → torch.load crashed → design loop exited with 0 outputs → STAGE_COMPLETE fired.

**Fix recipe:** pre-stage `.deb`s to `/workspace/installers/apt-packages/` once on a network-volume bake pod:
```bash
apt-get install -y --download-only unzip wget curl git build-essential rsync jq
cp /var/cache/apt/archives/*.deb /workspace/installers/apt-packages/
```
At dispatch:
```bash
dpkg -i /workspace/installers/apt-packages/*.deb || apt-get install -f -y
```

**Operator approval:** required for the one-time NV bake.

---

### G10 — Operator approval (HARD)

**What it does:** reads `estimated_cost_usd` and `operator_approved_ceiling_usd` from the config. FAILS if estimated > ceiling, or if either field is missing.

**Why it matters:** makes the policy "no paid GPU dispatch without operator presence" executable as a gate.

**Fix recipe:** set both fields in the preflight config:
```json
{
  "estimated_cost_usd": 2.50,
  "operator_approved_ceiling_usd": 3.00,
  "operator_approval_note": "Approved on <date> for <campaign>"
}
```

**Operator approval:** required — this is THE operator approval check.

---

## Config schema

The preflight script expects a JSON file with this shape. All fields are optional except where noted; missing fields cause the relevant gate to SKIP.

```json
{
  "campaign_name": "<your-campaign-id>",

  "pdb_identity": {
    "pdb": "/abs/path/to/target.pdb",
    "chain": "R",
    "expected_first_20_aa": "QVMDFLFEKWKLYGDQCHHN"
  },

  "hotspot_validation": {
    "pdb": "/abs/path/to/target.pdb",
    "chain": "R",
    "spec": {
      "33": ["CG", "CZ"],
      "36": ["CZ2", "CH2"],
      "65": ["CE1", "CE2", "OH"],
      "84": ["CE1", "CE2", "OH"],
      "87": ["CZ2", "CH2"]
    }
  },

  "required_tools": ["boltz", "chai", "ipsae", "colabfold"],
  "nv_root": "/workspace",

  "boltz_cache": {
    "mols_dir": "/workspace/software/boltz_cache/mols"
  },

  "worker_sh": "/abs/path/to/worker.sh",

  "estimated_cost_usd": 2.50,
  "operator_approved_ceiling_usd": 3.00,
  "operator_approval_note": "Approved by <operator> on <date> for <campaign>"
}
```

---

## Sign-off

Before any paid dispatch, the operator fills out this template and commits it alongside the preflight config. The launcher writes a `PREFLIGHT_PASSED.json` automatically when all gates pass.

```
Campaign:           ___________________________________________
Operator:           ___________________________________________
Date:               ___________________________________________
Git SHA:            ___________________________________________
Estimated cost:     $__________
Approved ceiling:   $__________
Pod hours expected: ___________________________________________

Gate sign-off (initial each row after preflight PASS):
  [ ]  G1   PDB chain identity
  [ ]  G2   Hotspot atom-spec
  [ ]  G3   Tool availability
  [ ]  G4   Boltz CCD cache
  [ ]  G5   Chai-1 MSA flag
  [ ]  G6   ipSAE / PAE flag
  [ ]  G7   Genie 3 CWD
  [ ]  G8   Validation gates
  [ ]  G9   Apt deps pre-staged
  [ ]  G10  Operator approval

Operator signature: ___________________________________________
```

---

## Skipping gates

Local (off-pod) runs can defer NV-side checks (G3, G4) to the worker script. Do NOT skip G1, G2, G7, G8, or G10 — those are zero-cost gates that guard against the highest-EV failure modes.

The launcher should refuse `--skip` for HARD gates without an explicit operator override flag. A non-zero exit from any HARD gate should write a sign-off-failed marker that the orchestrator polls before dispatch.

---

## Adding new gates

When a campaign hits a new failure class, add it here:

1. Pick a gate number (G11 onward).
2. Write the gate following the same template (What it does / Why it matters / Fix recipe / Operator approval).
3. Add the corresponding entry to [`docs/operational-gotchas.md`](operational-gotchas.md).
4. Implement the check in your preflight script.
5. Add the line to the sign-off block above.

Gates that have been added in past campaigns and may be worth adopting:
- Boltz `--num_workers 1` flag (multi-process CUDA init races on shared GPU hosts).
- Binder-extractor chain selection (PepGLAD outputs two-chain PDBs; selector must pick the shortest chain ≥5 aa).
- Designer-output sequence-content check (RFdiffusion / RFpeptides / Genie 3 outputs are polyG until ProteinMPNN runs; cofold gate should refuse polyG inputs).
