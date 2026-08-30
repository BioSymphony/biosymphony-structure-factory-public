# BioEmu

## Purpose

Plan sequence-conditioned protein ensemble sampling lanes. BioEmu is useful for
asking whether a public or operator-approved monomer sequence has high
conformational variability before a design, docking, or report lane leans on one
static structure.

## Public-Safe Status

Public scaffold: yes. Runtime use requires current source, model-weight,
AlphaFold2/ColabFold dependency, MSA, and provider-cache review. Do not commit
weights, generated ensembles, MSA results, model caches, or private sequences.

## When To Use

- Triage monomer flexibility before treating one predicted structure as stable.
- Compare ensemble spread across a small set of public candidates.
- Produce a flexibility-risk note for downstream cofolding, docking, or report
  review.

## Hand A Mission To An Agent

```text
Use the BioSymphony Structure Factory skill with the BioEmu tool card. For
public sequence <accession or FASTA>, prepare a BioEmu ensemble-sampling lane
with sample count, model checkpoint, MSA/cache posture, expected compact
artifacts, and result boundary. Do not download weights or call an MSA service
until the operator gate records the data and cache policy.
```

## Typical Inputs

- Public or operator-approved protein sequence.
- Optional precomputed A3M MSA.
- Sample count, batch size, checkpoint name, and steering settings.
- Runtime cache declaration for model and MSA-related weights.

## Typical Outputs

- Ensemble structures or trajectories outside git.
- `ensemble_manifest.json` with sequence checksum, sample count, checkpoint,
  cache posture, and tool version.
- `flexibility_risk_report.json` with compact spread and failure summaries.
- Optional side-chain reconstruction or short relaxation summary.

## Repo And References

- Repo: https://github.com/microsoft/bioemu
- Paper: Science 2025, "Scalable emulation of protein equilibrium ensembles
  with generative deep learning."

## Gotchas

- BioEmu is a monomer ensemble lane. It is not a protein-protein, protein-ligand,
  or binder validation lane.
- First use can materialize model and AlphaFold2/ColabFold-related weights.
  Keep those caches outside public git and outside public images unless the
  exact redistribution posture is reviewed.
- MSA retrieval can touch external services. Private or unpublished sequences
  need an explicit local/precomputed MSA posture.

## Gates

- No weights, generated structures, trajectories, or MSA output in git.
- Public examples must use public accessions or synthetic fixtures.
- Result boundary is flexibility and ensemble context only, not binding,
  mechanism, function, safety, or experimental validation.
- Provider runs require budget, cache, artifact pull, hash, and cleanup proof.
