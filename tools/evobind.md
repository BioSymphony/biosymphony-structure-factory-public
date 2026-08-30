# EvoBind

## Purpose

Plan sequence-centered peptide optimization lanes where the main artifact is a ranked candidate set for downstream structural checks. EvoBind uses AlphaFold-based scoring inside an evolutionary loop to optimize peptide sequences against a target, producing a ranked candidate list rather than a single best design.

## Public-Safe Status

Public scaffold: yes. Runtime use requires current source and dependency review. AlphaFold-family weights are license-gated; route through the operator gate.

## When To Use

- Sequence-only optimization where structural diversity is less important than ranking many candidates against a single objective.
- Targets where the binding-mode geometry is uncertain but the target sequence and structure are known.
- As a complement to structure-first designers (RFdiffusion, HelixDiff) when the goal is many ranked sequences rather than one curated shortlist.

## Hand A Mission To An Agent

```text
Use the BioSymphony Structure Factory skill with the EvoBind tool card. For target <PDB:ID> with target-window file <path>, prepare a sequence-centered peptide optimization lane. Specify peptide length range, scoring objective, stopping criteria (iterations or convergence), and the structural cross-checks expected at closeout.
```

## Typical Inputs

- Target-window file with chain, residue range, and hotspot evidence.
- Peptide length range or fixed length.
- Optional motif constraints (anchor residues to preserve).
- Scoring objective: AlphaFold-Multimer iPTM, complex pLDDT, or composite.
- Stopping criteria: max iterations or score convergence.
- Seed sequence(s) for initialization (random or known peptide).

## Typical Outputs

- Ranked candidate sequence table (CSV / JSON) outside public git when candidates are generated.
- Scoring / provenance ledger: per-iteration scores, accepted/rejected moves, seeds.
- Cofold and refinement handoff manifest.
- Optional best-of-N structure prediction artifacts (kept outside git).

## Repo And References

- EvoBind: https://github.com/patrickbryant1/EvoBind
- Paper: Bryant & Elofsson, "EvoBind: in silico directed evolution of peptide binders with AlphaFold," 2022.

## Key Knobs

| Setting | Recommendation | Why |
| --- | --- | --- |
| Peptide length | 8-25 aa | Outside this range, structure-first designers usually win. |
| Iterations | 100-1000 | Diminishing returns past ~500 for most targets; canary at 100 first. |
| Scoring objective | composite plus site checks | Single-metric optimization is brittle; interface distance or iPTM alone can reward the wrong site. |
| Anchor residues | 0-3 | Sparse anchors preserve diversity. |
| Population / parallel chains | 1-8 | More chains explore more local optima at extra cost. |
| Mutation rate | 0.05-0.2 per residue per step | Lower for convergence, higher for exploration. |

## Gotchas

- AlphaFold-Multimer iPTM as the optimization objective can drive sequences toward template-like patterns that look high-confidence but are not novel binders. Cross-check the final shortlist with an independent cofold (Boltz, Chai) on the same target window.
- Interface-distance objectives can be site-blind. A peptide can minimize distance to any receptor surface while missing the intended pocket or functional site. Always measure distance to the declared hotspot centroid or anchor residues, not just nearest-neighbor receptor contact.
- Sequence-only metrics cannot support binding or affinity claims. The ranked list is a starting point for structural triage, not a validated shortlist.
- AlphaFold-family weights are license-gated; runtime use needs explicit operator authorization recorded in validation notes and the launch record.
- A converged EvoBind run can still produce sequences that fail downstream cofold; budget for at least one cofold pass per top-N candidate before promotion.

## Site-Specific Checks

For pocketed targets, GPCRs, enzyme active sites, and any campaign where the binding site matters, add these checks before a candidate can advance:

- **Pocket-distance check:** compute peptide centroid or closest-heavy-atom distance to the declared hotspot centroid and to each critical anchor residue.
- **Contact-map check:** require contacts to the intended residue set, not just any receptor chain.
- **State check:** if the target has active/inactive or open/closed states, compare the receptor geometry against the intended state reference.
- **Independent cofold check:** re-run top candidates with a cofolder outside EvoBind's optimization loop and rescore with PAE-derived metrics.
- **Visual sanity check:** render or inspect the top few complexes with hotspots labeled. A high score at the wrong surface is a failed design for a site-specific campaign.

## Gates

- Generated sequences are private runtime artifacts by default.
- Sequence-only scores cannot support binding or activity claims.
- Require structural cross-checks (Boltz, Chai, AF2-Multimer, or another independent validator) and result-boundary downgrade rules at closeout.
- Cap every candidate ranking at `computational_candidate` until independent validation exists.
- For site-specific campaigns, treat missing pocket-distance, anchor-contact, or state-geometry checks as `insufficient_support`.
- Run a currency check before any paid GPU dispatch: upstream repo HEAD (releases + recent commits), current release notes, and recent preprints (biorxiv / chemrxiv / arxiv) on the relevant lane. Record the version pin and the date of the check in the candidate ranking.
