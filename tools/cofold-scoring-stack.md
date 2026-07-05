# Cofold Scoring Stack

## Purpose

Cross-check candidate binders with multiple structure-prediction opinions, then score interface confidence and site geometry. Outputs are computational triage. Binding proof comes from wet-lab follow-up downstream of this stack.

## Public-Safe Status

Public scaffold: yes. Runtime execution: review required for current package terms, model weights, template and MSA posture, and provider setup.

## Hand A Mission To An Agent

```text
Use the BioSymphony Structure Factory skill with the Cofold Scoring Stack tool card. For target <PDB:ID> and candidate set <path>, prepare a multi-validator cofold lane that runs Boltz, Chai-1, AF2-Multimer, and optional OpenDDE in parallel, then rescores with ipSAE for a min-ipSAE consensus gate. Specify recycle and sample counts per validator and the closeout artifact list.
```

## Headline Finding (2026): Multi-Validator min-ipSAE Consensus

**Single-cofolder iPTM is increasingly deprecated as a binder-promotion gate.** The Adaptyv n=3,766 binder × 15 targets meta-analysis showed raw iPTM has ROC-AUC ~0.5 (random) for wet-lab binders. ipSAE rescore on the PAE matrix is ~1.4× more precise. Recent benchmarks (Bryant et al., bioRxiv `2026.02.26.708415`, 124 GPCR-peptide complexes) show that on under-represented target classes (class B GPCRs were the test case), top-of-distribution iPTM / ipSAE from a single validator is statistically indistinguishable from random as a ranking gate — every cofolder is systematically over-confident on misplaced peptides, but the failure mode is different per cofolder.

The fix is the **minimum ipSAE across a slate of ≥3 validators**, not a single-cofolder threshold. No cofolder is "primary"; all of them vote, and the lowest one is the gate.

## Composing The Slate

This card is the meta-lane. Individual cofold validators have their own cards:

- [Boltz](boltz.md) for fast cofold with full PAE output.
- [Chai-1](chai.md) for MSA-driven cofold with parquet inputs.
- [OpenDDE](opendde.md) for all-atom biomolecular cofolds, ABAG canaries, and optional PAE/PDE sidecars.
- AF2-Multimer (via LocalColabFold) as the long-established baseline validator.

A common slate:

1. **AF2-Multimer v3** via LocalColabFold (`alphafold2_multimer_v3` with `--templates` on for target classes with dense PDB coverage).
2. **Boltz-2** with optional template injection (`templates: [{cif:<ref>.cif, force:true}]` in YAML).
3. **Chai-1** with proper MSA + template (`use_esm_embeddings=False`, `msa_directory=<target_aligned.pqt>`).
4. **OpenDDE** for selected canaries or ranked candidates, especially antibody-antigen complexes where the ABAG checkpoint is relevant.

Each validator emits a PAE matrix → ipSAE post-hoc rescore.

If a validator emits only a scalar confidence row in the saved artifacts, mark
that validator's interface score incomplete. The reviewed model must be joinable
to its confidence sidecars by manifest row, stem, or hash.

## Typical Inputs

- Target sequence or deposited-structure chain.
- Candidate binder sequence(s).
- Pre-computed target MSA (`.a3m` for Boltz YAML, parquet for Chai).
- Optional public templates.
- Manifest declaring result boundary, expected artifacts, and forbidden conclusions.

## Typical Outputs

- Per-tool prediction status.
- PAE matrices, per-residue pLDDT, and confidence JSON per validator. See
  [confidence sidecars](../docs/confidence-sidecars.md).
- Interface score table with `ipSAE_*` and `iptm` columns per validator.
- Consensus column (`min_ipSAE`, `cofolders_passing`).
- Candidate ranking with source posture and result boundary.
- Provenance, command ledger, and hash ledger.

## Minimum-Viable Invocations

### Pre-compute target MSA once (the key cost lever)

Per-design ColabFold rate-limits are the dominant cost on multi-cofold campaigns. Compute the target MSA **once** to flat `.a3m`, then convert to Chai's `aligned.pqt`. Mount the cache on your network volume.

```bash
# Local MMseqs2 if the DB shard is on the NV (preferred, ~5-30 s on L40S):
mmseqs createdb target_query.fasta msa_cache/qdb
mmseqs search msa_cache/qdb dbs/uniref30 msa_cache/result /tmp \
   --max-seq-id 0.95 -s 8 --num-iterations 3 -e 0.1
mmseqs result2msa msa_cache/qdb dbs/uniref30 \
   msa_cache/result msa_cache/target.a3m --msa-format-mode 2

# OR ColabFold MMseqs2 API fallback (~45 s):
python -m colabfold.batch --msa-only --num-recycle 1 \
   target_query.fasta msa_cache/
cp msa_cache/*_pair.a3m msa_cache/target.a3m

# Chai parquet form (requires an operator-supplied helper or upstream chai-lab utility):
# - one approach: use chai-lab's own MSA conversion helpers
# - another: write a small a3m → parquet converter that respects chai-lab's expected schema
python scripts/<your-chai-msa-helper>.py a3m_to_aligned_pqt \
   msa_cache/target.a3m msa_cache/target_aligned.pqt
```

### Boltz-2

```bash
boltz predict inputs/ \
    --out_dir boltz_out \
    --cache .boltz_cache \
    --recycling_steps 3 \
    --diffusion_samples 3 \
    --sampling_steps 200 \
    --write_full_pae \
    --no_kernels
# Per-design YAML refers to the cached MSA:
#   - protein: {id: A, sequence: <target>, msa: msa_cache/target.a3m}
#   - protein: {id: B, sequence: <peptide>, msa: empty}   # de novo design = single-seq
```

### Chai-1

```python
from chai_lab.chai1 import run_inference
run_inference(
    fasta_file="design_001.fasta",
    output_dir="chai_out/design_001/",
    use_esm_embeddings=False,              # CRITICAL: default True = single-seq ESM, no MSA
    msa_directory="msa_cache/",            # holds target_aligned.pqt
    num_trunk_recycles=3,
    num_diffn_timesteps=200,
    device="cuda:0",
)
```

### LocalColabFold AF2-Multimer

```bash
colabfold_batch \
    --model-type alphafold2_multimer_v3 \
    --num-models 5 --num-recycle 3 \
    --rank multimer \
    --templates \
    fasta_in/ \
    af2m_out/
```

5-model mean+stddev is your free orthogonal confidence proxy.

### OpenDDE

```bash
LAYERNORM_TYPE=torch opendde pred \
    -i inputs/design_001.opendde.json \
    -o opendde_out/design_001 \
    -n opendde_v1 \
    --use_msa false \
    --use_template false \
    --use_rna_msa false \
    --sample 3 \
    --step 200 \
    --cycle 10 \
    --need_atom_confidence true
```

Use `--load_checkpoint_path "$OPENDDE_ROOT_DIR/checkpoint/opendde_abag.pt"` for
the ABAG checkpoint. Preserve both summary confidence JSON and `full_data` JSON
when the output will feed an ipSAE-style or PAE/PDE sidecar gate. Summary-only
output is useful for triage but incomplete for interface-error rescoring.

### ABCFold (one-call multi-validator)

```bash
abcfold inputs/design_001.json abc_out/design_001 \
   -abc \
   --mmseqs2 \
   --custom_msa msa_cache/target.a3m \
   --model_params af3_params
# -a AF3, -b Boltz-2, -c Chai-1.
```

ABCFold takes one AF3-JSON in and runs AF3 + Boltz-2 + Chai-1 (+ optional Protenix / RF3 / OpenFold3) in one call. It does NOT emit a consensus rank — layer ipSAE on top yourself.

### ipSAE post-hoc rescore (on Boltz output)

```bash
cd boltz_out/predictions/design_001/
python /workspace/ipsae/ipsae.py \
    confidence_design_001_model_0.json \
    design_001_model_0.cif \
    10 5   # pae_cutoff (Å), dist_cutoff (Å) — Dunbrack defaults
# emits ipSAE_d0chn (the headline) plus pDockQ, ipAE, ipTM in a flat row.
```

## Key Knobs

| Tool | Flag | Default | Recommendation | Why |
|------|------|---------|----------------|-----|
| Boltz | `--recycling_steps` | 3 | 3 | Default is fine; +1 buys <0.01 iPTM |
| Boltz | `--diffusion_samples` | 1 | 3 | Median > top-1 for stable ranking |
| Boltz | `--sampling_steps` | 200 | 50 for triage | Ranking-only; full 200 wastes time |
| Boltz | `--write_full_pae` | off | **on** | Required for ipSAE rescore |
| Boltz | `--no_kernels` | off | **on** on L40/Ada | v2.2 fused-kernel regression |
| Boltz | `--num_workers` | 1 | **1** on shared hosts | Multi-process CUDA init races on community pods |
| Boltz | YAML `msa:` (target) | server | cached `.a3m` | Removes rate-limit |
| Boltz | YAML `msa:` (de novo binder) | server | `empty` | Designed binders have no informative MSA |
| Chai-1 | `use_esm_embeddings` | True | **False** | Default = single-seq ESM, no MSA |
| Chai-1 | `msa_directory` | None | **target's `aligned.pqt`** | Else MSA mode is dead |
| Chai-1 | `num_trunk_recycles` | 3 | 3 | |
| Chai-1 | `num_diffn_timesteps` | 200 | 200 | |
| AF2M | `--model-type` | auto | **`alphafold2_multimer_v3`** | Right one for protein-protein |
| AF2M | `--num-models` | 5 | 5 | mean+stddev is free orthogonal signal |
| AF2M | `--num-recycle` | 3 | 3 | Bump to 5 for borderline calls |
| AF2M | `--rank` | plddt | **`multimer`** | iPTM-weighted ranking |
| AF2M | `--templates` | off | **on** when target has PDB coverage | Templates pin register where cofolders hallucinate |
| OpenDDE | `--need_atom_confidence` | false | **true** for ranked candidates | Saves PAE/PDE/contact sidecars. |
| OpenDDE | `--use_msa`, `--use_template`, `--use_rna_msa` | true/false by flag | **false for first canary** | Avoids public-service and large-database dependencies. |
| OpenDDE | `--load_checkpoint_path` | default `opendde.pt` | use `opendde_abag.pt` for ABAG canaries | Selects antibody-antigen checkpoint. |
| ipSAE | `pae_cutoff` (Å) | 10 | 10 | Dunbrack default |
| ipSAE | `dist_cutoff` (Å) | 5 | 5 | Dunbrack default |
| ABCFold | `-abc` | — | **-abc** | Three cofolders, one call |
| ABCFold | `--mmseqs2` | off | **on** | Unless you mount a `--custom_msa` |

## Output Fields To Actually Read

**CRITICAL:** for protein-protein iPTM, **read `confidence_<name>.json`**, NOT `affinity_summary.json`. The latter is the small-molecule affinity head and does not apply to protein-protein interfaces.

| Cofolder | File | Field | What it is |
|----------|------|-------|------------|
| Boltz-2 | `confidence_<name>_model_<k>.json` | `confidence_score` | global ranking number |
| Boltz-2 | `confidence_<name>_model_<k>.json` | `complex_iplddt` | interface-conditioned pLDDT (gate alongside iPTM) |
| Boltz-2 | `confidence_<name>_model_<k>.json` | `pair_chains_iptm[binder, target]` | the iPTM you actually want |
| Boltz-2 | `confidence_<name>_model_<k>.json` | `ptm`, `complex_ipde` | secondary diagnostics |
| Chai-1 | NPZ from `run_inference` | `aggregate_score` | preferred single ranker |
| Chai-1 | NPZ | `per_chain_pair_iptm[binder, target]` | interface iPTM (not global `iptm`) |
| AF2M | `<job>_summary_confidences.json` | `iptm`, `ranking_confidence`, `ptm` | top-rank model |
| AF2M | `<job>_scores_rank_<k>.json` | `ptm`, `iptm`, `predicted_aligned_error` | per-model, for the 5-model spread |
| OpenDDE | `<job>_summary_confidence_sample_<k>.json` | `chain_pair_iptm`, `iptm`, `ptm`, `gpde`, `ranking_score` | scalar and chain-pair confidence diagnostics |
| OpenDDE | `<job>_full_data_sample_<k>.json` | `token_pair_pae`, `token_pair_pde`, `contact_probs` | sidecars for downstream interface-error scoring |
| ipSAE | stdout / CSV | `ipSAE_d0chn`, `ipSAE_max`, mean interface PAE | post-hoc |

## Consensus Gate

The current default gate uses min-ipSAE across ≥3 validators:

```
min(ipSAE_AF2-Multimer, ipSAE_Boltz, ipSAE_Chai) ≥ 0.45
  AND (optional) Rosetta ΔG (InterfaceAnalyzer + FastRelax200) in top tertile
```

The 0.45 threshold is the binder-presence floor from Overath / Rygaard 2025 (`bioRxiv 2025.08.14.670059v2`); applying it to **all three** validators at once is what discriminates real designs from misplaced ones, per the Bryant 2026 GPCR benchmark.

iPTM remains a diagnostic column. Do not gate on `pair_chains_iptm` alone.

For target classes that are under-represented in cofolder training distributions (the well-known case is class B GPCRs, but the same caution applies to many membrane-protein / RNP / nucleic-acid-containing assemblies), layer a **target-class-specific check** after the min-ipSAE gate:

- A receptor-state classifier (e.g. Hyaline for GPCRs) gating against poses that look reasonable backbone-wise but are in the wrong functional state.
- Pocket-distance and anchor-contact checks for residues known to define the intended binding mode.
- Peptide-side motif/register checks when the campaign is trying to mimic a public reference ligand.
- Off-target or related-family checks when the campaign is selectivity-aware.

Class-specific checks are layered on top of the min-ipSAE gate, not used as a substitute.

For functional-state campaigns, distinguish four different questions:

| Question | Example check | What it can support |
| --- | --- | --- |
| Is there a plausible interface? | min-ipSAE across the validator slate | computational interface support |
| Is the interface at the intended site? | hotspot contact map, pocket-centroid distance, anchor-residue distances | site-specific triage |
| Is the receptor in the intended state? | active/inactive geometry, state classifier, conserved-motion measurement | state-consistent triage |
| Is the candidate biologically active? | wet-lab or downstream experimental data | outside this repo |

A candidate that passes the first row but fails site or state checks should close as a misplaced or insufficiently supported computational candidate, not as a functional binder.

## Gotchas / Known Issues

- **Boltz `affinity_summary.json` is a trap** — that's the small-molecule head, not protein-protein iPTM. Always read `confidence_<name>.json`.
- **Chai-1 `use_esm_embeddings` defaults to True** → single-sequence ESM mode, no MSAs. Force `False` and supply `msa_directory`. This is one of the most common "Chai is worse than Boltz" disagreement causes.
- **Chai-1 has a ~0.3 iPTM calibration offset vs Boltz** on real binders — same complex can score Boltz 0.96 / Chai 0.67. This is a model-family property (chai-lab issue #287), **not a configuration bug**. Calibrate per-model; do not compare iPTM values across cofolder families.
- **AF2-Multimer 5-model mean+stddev is free** and orthogonal — record it as a confidence proxy. The variance across the 5 models often catches scrambled / mis-placed designs that the top-rank model confidently reports.
- **ABCFold does not emit a consensus rank.** Layer ipSAE (and optionally Rosetta ΔG) on top yourself.
- **iPTM is officially deprecated for binder ranking** (Overath / Rygaard 2025). Replace headline metric with ipSAE; keep iPTM for diagnostics.
- **Nearest-surface contact is not pocket contact.** If the design objective uses interface distance, compute distances to declared hotspots or pocket centroids as a separate gate. A peptide that contacts the wrong receptor surface is a failed candidate for a site-specific campaign even when a global interface score looks strong.
- **ColabFold MMseqs2 server rate-limits at ~20 jobs.** Pre-compute the target MSA once and mount it; per-design submissions become near-instant.
- **chai_lab 0.6.1 + pandas 2.2** needs a 1-line patch to `aligned_pqt.py` (groupby drops the parquet column on newer pandas). Apply post-install with a small patch script that re-adds the column after the groupby.
- **Boltz 2.2 fused kernels regress on L40 / Ada GPUs** — pass `--no_kernels`. ~5% slower, no NaNs.
- **Boltz `--num_workers > 1` crashes on shared community hosts** with a CUDA `_cuda_init` driver-too-old race even when single-worker mode works. Force `--num_workers 1`.
- **LocalColabFold's pixi installer is the current supported install path** (2026-01 pivot); the older `install_colabbatch_linux.sh` still works on Ubuntu 22.04.
- **AF2-Multimer fetches its own MSAs** (per-job, ColabFold MMseqs2). Even if you have cached a Boltz / Chai `.a3m`, AF2M does not reuse it — rate-limit risk reappears on >20 jobs.
- **OpenDDE package install currently needs source or Docker** as of the 2026-07-05 review; the advertised PyPI package route was not visible. Pin the source commit or Docker digest in provider packets.
- **OpenDDE summary-only output is not enough for ipSAE-style gates.** Use `--need_atom_confidence true` and preserve `full_data`, then budget for larger artifacts.
- **OpenDDE uses public MMseqs2 by default for protein MSA search.** Use precomputed A3M or a self-hosted `MMSEQS_SERVICE_HOST_URL` for private sequences or batch fanout.
- **For peptide ligands with disordered or partly-cleaved N-termini** (common in GPCR-peptide complexes), expect interface ipSAE to be lower due to peptide flexibility. Not a bad model — a real biological feature. Calibrate the threshold against a known positive-control complex.

## Citations And References

- Bryant et al., "Assessment of Generative De Novo Peptide Design Methods for GPCRs," bioRxiv 2026.02.26.708415 — the multi-validator min-ipSAE consensus is the published response to this benchmark.
- Boltz-2: jwohlwend/boltz, paper bioRxiv 2025.06.14.659707
- Chai-1: chaidiscovery/chai-lab; chai-lab issue #287 documents the iPTM calibration offset
- LocalColabFold: YoshitakaMo/localcolabfold (2026-01 pixi pivot)
- AF2-Multimer: Evans et al. bioRxiv 2021.10.04.463034
- ABCFold: Elliott et al., Bioinformatics Advances 5(1) vbaf153, 2025; PMID 40708869
- ipSAE: DunbrackLab/IPSAE; paper bioRxiv 2025.02.10.637595v2
- Overath / Rygaard binder-presence floor: bioRxiv 2025.08.14.670059v2
- DigBioLab reference pipeline (defines the consensus gate): https://github.com/DigBioLab/de_novo_binder_scoring
- BindEnergyCraft / pTMEnergy (free upgrade on pAE logits): arXiv 2505.21241
- OpenDDE: https://github.com/aurekaresearch/OpenDDE

## Currency Check (Run Before Reusing This Card)

The cofold landscape moves faster than most lanes in this repo. Model releases (Boltz, Chai, AF3, HelixFold), gate revisions (the Bryant 2026 finding documented above superseded a 2025 single-cofolder framework that looked locked-in at the time), and rescoring tools (ipSAE, pTMEnergy / BindEnergyCraft) appear on a months-not-years cadence.

Before reusing this card's recipe in a real campaign, run a primary-source freshness check:

1. **Upstream repos.** Check the releases tab and recent commits on each cofolder (jwohlwend/boltz, chaidiscovery/chai-lab, YoshitakaMo/localcolabfold, DunbrackLab/IPSAE, rigdenlab/ABCFold). Flag any major version bump since this card's last review.
2. **bioRxiv search.** Query terms like "min-ipSAE", "binder ranking gate", "[target-class] cofold benchmark", "BindCraft", "iPTM deprecation". Recent benchmarks can supersede the consensus threshold (0.45 today is the Overath / Rygaard floor; expect future papers to refine it per target class).
3. **arXiv search.** Query for new rescoring or energy-style methods (pTMEnergy / BECraft, etc.) that may layer cleanly on top of the same PAE matrices we already write.
4. **Record the result.** In the candidate ranking or validation notes, log the cofold versions used, the gate threshold applied, and the date of this currency check. A future agent should be able to re-verify against the literature as it existed at run time rather than re-discovering it.

The Bryant 2026 finding embedded above is itself a snapshot. Expect this pattern — a benchmark paper supersedes a framework that previously looked settled — to repeat. The recipe here is what was current at last review; verify before scaling.

## Gates

- No private target sequence may be sent to public MSA services.
- Affinity-like outputs stay diagnostic unless an independent validation lane supports them.
- Consensus failure closes as `insufficient_evidence`, not success.
- Cap every candidate ranking at `computational_candidate` until independent validation exists.
- Treat missing target-site or functional-state checks as a support gap, even when cofold confidence is high.
- Run the Currency Check above before any paid GPU dispatch that uses this recipe.
