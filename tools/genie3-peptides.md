# Genie 3 Peptides And Miniproteins

## Purpose

Plan peptide or miniprotein backbone generation lanes while respecting the model's length and setup assumptions. Genie 3 is a diffusion-based protein structure generator; the binder-design mode produces backbones conditioned on a target structure, hotspot residues, and a binder length range. Sequences come from a downstream ProteinMPNN pass; structural confidence comes from an independent cofold.

## Public-Safe Status

Public scaffold: yes. Runtime execution requires source, weight, dependency, MSA-service, and intended-use review. Store weights and generated structures under ignored runtime storage or in a user-selected artifact store.

## When To Use

- Miniprotein binder backbones (~50-150 aa) against a public or operator-approved target window.
- As an alternative to RFdiffusion when its specific training distribution or ColabFold-based evaluation step is preferred.
- When the binderbench-style binder design layout (problems / targets / MSA pre-computed) fits the workflow.

## Hand A Mission To An Agent

```text
Use the BioSymphony Structure Factory skill with the Genie3 tool card. For target <PDB:ID> with target-window report <path>, prepare a peptide or miniprotein generation lane. Respect the length floor near 50 aa, specify hotspot and extended interface residue sets, the binder length range, the ProteinMPNN sequence pass, and the Boltz + Chai cofold handoff.
```

## Practical Boundary

Treat very short peptides (under ~30 aa) as out-of-distribution until a campaign records evidence otherwise. Miniprotein-length binder scaffolds (50-150 aa) are the safer planning lane. For shorter peptides, switch to RFpeptides, HelixDiff, or PepGLAD.

## Typical Inputs

- Public target structure or target-window file.
- Hotspot and extended interface residue sets on the target.
- Binder length range (`50-100` typical for miniproteins).
- Runtime config generated from a manifest (problem JSON + target dataset).
- Pre-computed target MSA (Genie 3 expects ColabFold-format MSA at evaluation time).
- Sample count per problem.

## Typical Outputs

- Generated backbone candidates (PDB) outside git, under `<rootdir>/<selection>/pdbs/<selection>_<sample_idx>.pdb`.
- Generation manifest with seeds, config, source refs, weight refs, and execution time.
- Downstream ProteinMPNN sequence-design input.
- Cofold ranking input manifest.

## Repo And References

- Genie (v1/v2): https://github.com/aqlaboratory/genie
- Genie2 (newer release): https://github.com/aqlaboratory/genie2
- Paper (Genie): Lin & AlQuraishi, "Generative diffusion models for protein design," 2023.

## Key Knobs

| Setting | Recommendation | Why |
| --- | --- | --- |
| Binder length range | 50-100 aa | Below ~50 aa is out-of-distribution; above ~150 aa, sample count needs to grow. |
| `n_sample` per problem | 4-32 first pass | Canary at 4; scale to 32 once the lane proves end-to-end. |
| `direction_scale` | 1.0 default, up to 2.0 for hotspot steering | Higher values steer harder toward hotspots but can overfit. |
| Hotspot residues | 3-8 on target | Anchors the binder placement. |
| Extended interface residues | 5-20 on target | Defines the surface region the binder can engage. |
| Downstream ProteinMPNN | SolubleMPNN for soluble targets | Sequence pass on the binder using target as context. |
| Cofold validator | Boltz + Chai-1 slate | iPTM + ipSAE consensus; single-cofolder iPTM is unreliable for binder ranking. |

## Gotchas

- Genie 3 reads `target_pdb_filepath` from the problem JSON via Python `open()`, which resolves relative paths from cwd. Synthesize the problem JSON with absolute paths or run from the configured weights directory.
- `genie3 run` does generate-then-evaluate; the evaluate step needs ProteinMPNN (separate package, not pip-resolvable from upstream setup.py). Use `genie3 generate` instead and run ProteinMPNN as a separate stage. The Boltz cofold acts as the independent validator.
- `genie3 generate` writes outputs to `<rootdir>/<selection>/pdbs/<selection>_<sample_idx>.pdb`, not the README-documented `results/v0_success/successful_complexes/`. Search the entire `<rootdir>/<cid>/` subtree.
- The binderbench dataset layout requires `problems/<sel>.json` plus `targets/{pdb,fasta,msa}/<sel>{,-chain_X}.{pdb,fasta,a3m}`. The README's per-problem JSON shape is correct; the surrounding layout is non-obvious.
- Boltz cofold downstream needs `numpy < 2.2` due to its numba dependency, but Genie 3's `pip install -e .` upgrades numpy past 2.1. Re-pin numpy inside the Boltz stage itself, not just at startup.
- HuggingFace weights revision pinning is required for reproducibility; record the revision in the candidate ranking alongside the seed.

## Gates

- Weight download requires operator authorization.
- Public MSA service calls are allowed for public targets only.
- Candidate claims require cofold, artifact, provenance, and validation-ledger checks before promotion.
- Cap every candidate ranking at `computational_candidate` until independent validation exists.
- Run a currency check before any paid GPU dispatch: upstream repo HEAD (releases + recent commits), current release notes, and recent preprints (biorxiv / chemrxiv / arxiv) on the relevant lane. Record the version pin (Genie version + HuggingFace weights revision) and the date of the check in the candidate ranking or validation notes.
