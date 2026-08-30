# PepGLAD

## Purpose

Plan peptide sequence-structure co-design lanes when full-atom peptide generation is a better fit than miniprotein scaffolding. PepGLAD generates both the peptide structure and sequence together at full-atom resolution, conditioned on a target receptor window, motif constraints, and length.

## Public-Safe Status

Public scaffold: yes. Runtime use requires current branch, dependency, model-weight, and license review. Store weights and generated peptides under ignored runtime storage or in a user-selected artifact store.

## When To Use

- Linear peptide binders (10-30 aa) where sequence and structure should be co-designed rather than handed off between stages.
- Targets where a sequence-only or structure-only approach has not produced viable candidates.
- Cases where preserving a known motif (a few anchor residues) while diversifying the rest of the peptide is the design objective.

## Hand A Mission To An Agent

```text
Use the BioSymphony Structure Factory skill with the PepGLAD tool card. For target <PDB:ID> with target window <chain or residues>, prepare a full-atom peptide sequence-structure co-design lane. Specify length, topology, motif or anchor-residue constraints, and the cofold and refinement handoff downstream.
```

## Typical Inputs

- Target-window report with chain, residue range, and hotspot evidence.
- Peptide length and topology constraints.
- Optional motif: anchor residues to preserve from a known reference peptide.
- Sample count.

## Typical Outputs

- Candidate peptide models (PDB) outside git, with both backbone and sequence in one shot.
- Runtime manifest including version, branch, dependency posture, and seed.
- Confidence / scoring summary per candidate.
- Cofold-ready candidate table for downstream validator slate.

## Repo And References

- PepGLAD is described in the recent full-atom peptide design literature; consult the primary source for current repo, model weights, and license terms before runtime use.

## Key Knobs

| Setting | Recommendation | Why |
| --- | --- | --- |
| Peptide length | 10-25 aa | Outside this range, switch to RFpeptides (shorter) or HelixDiff / miniproteins (longer). |
| Anchor / motif residues | 0-4 residues | Preserve known interface contacts; over-constraining suppresses diversity. |
| Sample count | 100-500 first pass | Joint generation is expensive; canary first before scaling. |
| Topology constraint | linear default | Cyclic / constrained topologies need explicit specification. |
| Temperature / noise | upstream default | Lower noise sharpens; higher noise diversifies. |

## Gotchas

- Joint sequence-structure generation can produce sequences that look reasonable but are structurally implausible at the side-chain level. Run an independent cofold (Boltz, Chai) on every candidate before promotion.
- Anchor residues that conflict with the natural peptide register will produce kinked or broken backbones; check the residue numbering carefully against the target hotspot evidence.
- Different runs with the same seed are not always bit-identical depending on the upstream library version; record version pins.
- Public benchmark numbers do not always translate to performance on a novel target; do not promote based on training-set-style metrics alone.

## Gates

- Keep model weights and generated structures out of git.
- Record version, branch, dependency posture, and seeds in the candidate ranking.
- Close as `partial` or `blocked` if the runtime cannot reproduce the declared configuration.
- Cap every candidate ranking at `computational_candidate` until independent validation exists.
- Run a currency check before any paid GPU dispatch: upstream repo HEAD (releases + recent commits), current release notes, and recent preprints (biorxiv / chemrxiv / arxiv) on the relevant lane. Record the version pin and the date of the check in the candidate ranking or validation notes.
