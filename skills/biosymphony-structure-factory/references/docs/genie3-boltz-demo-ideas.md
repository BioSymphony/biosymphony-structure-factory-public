# Genie 3 And Boltz Demo Ideas

Last reviewed: 2026-05-08

This note captures public, visually impressive demo concepts for combining
Genie 3 generation with Boltz prediction/cross-checking inside Structure
Factory. These are computational candidate demos only. They do not authorize
wet-lab synthesis, therapeutic conclusions, private target use, or paid RunPod
execution without the normal operator gate.

## Shared Demo Contract

Every Genie 3 + Boltz demo should emit:

- `genie3_manifest.json` with repo commit, HF model revision, config, seeds,
  target/motif source, and sample count.
- `weights_manifest.json` for Genie 3 and any Boltz/ColabFold/AlphaFold2
  weights actually used.
- `executed-commands.jsonl`, `versions.json`, and `validation_ledger.json`.
- `design_candidates/` with generated PDBs or FASTA/PDB pairs.
- `boltz_crosscheck/` with per-candidate prediction artifacts and confidence.
- `ranking_summary.csv` comparing Genie 3 native scores, Boltz confidence,
  self-consistency metrics, interface metrics where relevant, and failure mode.
- A compact Markdown summary with figure-panel references and no `validated` language.

Default result boundary: `computational_candidate`.

Before any real Genie 3 + Boltz demo, run `make harness-check` locally
and `make harness-check` inside the actual GPU image or Network Volume
runtime. The local check validates contracts and reports missing runtime tools;
the strict runtime check must pass before candidate generation. See
`docs/ai-design-runtime-readiness.md` for the current Boltz/Genie upstream-doc
gotchas and provider selection order.

## Demo 1: Motif Scaffold Showcase

Use a public motif scaffolding problem from Genie 3's example set or a public
PDB-derived motif. Genie 3 scaffolds the motif, then Boltz predicts whether the
designed full sequence maintains a compatible fold. The report shows motif
RMSD, Boltz confidence, sequence diversity, and cluster spread.

Why it is impressive:

- Easy to explain visually: fixed motif in color, generated scaffold around it.
- Good no-private-data canary for all-atom generation.
- Lets Structure Factory show design diversity plus independent structure
  agreement in one panel.

Guardrails:

- Treat in-silico motif retention as candidate evidence only.
- Record exact motif source and residue ranges.
- Reject any candidate without source/motif provenance.

## Demo 3: Tiny Fold Zoo

Run Genie 3 unconditional generation across a small length ladder, for example
50, 100, and 150 residues with a tiny sample count. Boltz and/or ESMFold
cross-check each design, then the report clusters by FoldSeek and reports fold
diversity, confidence, and model disagreement.

Why it is impressive:

- Fastest public-data visual demo after weights are cached.
- Produces a gallery of novel-looking mini proteins.
- Good smoke test for sharding, artifact hashing, and result reduction.

Guardrails:

- Keep sample counts small for the first canary.
- Do not label generated folds as novel without database search evidence.
- Use `public_synthetic_demo` or `computational_candidate` result boundary until a real search/novelty
  lane is added.

## Demo 4: Design Disagreement Museum

Generate a small mixed tranche from Genie 3: unconditional mini proteins, motif
scaffolds, and one public binder target. Run Boltz cross-checks and collect the
most interesting agreement and disagreement cases into a curated Markdown summary.

Why it is impressive:

- Shows the value of cross-model review instead of one-model scoring.
- Makes failure modes visible: collapsed folds, low-confidence interfaces,
  motif drift, or high-confidence disagreements.
- Fits Structure Factory's validation-ledger posture well.

Guardrails:

- Do not hide failed candidates.
- Require a row in `ranking_summary.csv` for every generated candidate.
- Claims inherit the weakest source posture.

## Demo 5: Public Benchmark Micro-Run

Use one or two public Genie 3 example binderbench or motifbench cases with
minimal `n_sample`. Keep the run small enough to inspect manually, then compare
Genie 3's reported success filters with Boltz re-prediction and Structure
Factory's own artifact contract.

Why it is impressive:

- Demonstrates reproducibility against an upstream benchmark shape.
- Provides a clean first Linear issue because inputs and expected outputs are
  already structured.
- Lets us validate the lane before inventing new campaign-specific wrappers.

Guardrails:

- Training-data download remains opt-in and blocked by default.
- MSA server use must be declared; private targets require precomputed/local
  MSAs.
- Do not mark upstream benchmark success as Structure Factory validation unless
  our self-check, hashes, and validation ledger pass.

## First Wave Recommendation

Start with two issues:

1. `genie3-no-download-toolcheck`: clone/pin source, validate CLI/config/import
   shape, record dependency and license findings, no weights, no GPU.
2. `genie3-public-motif-canary`: one public motif scaffold with tiny sample
   count, Genie 3 weights only, Boltz cross-check, full candidate validation ledger.

Add a receptor-window report as a no-download planning issue against any
public target window. Defer state-binder demos until the public canary proves
source checkout, weights cache, GPU pickup, artifact collection, and Boltz
cross-check closeout.
