# HelixDiff

## Purpose

Plan short helical peptide design lanes for targets where a helix-like binder or ligand mimic is plausible. HelixDiff generates short alpha-helical backbones (15-40 aa) conditioned on a target hotspot window, intended for binders that engage a groove or shallow pocket via helical secondary structure.

## Public-Safe Status

Public scaffold: yes. Runtime use requires current source, dependency, and weight review. Store weights and generated peptides under ignored runtime storage or in a user-selected artifact store.

## When To Use

- Linear helical peptide binders (15-40 aa) against grooves, helical pockets, or shallow surfaces.
- Targets where a known helical binder context exists (helical hot-segment surfaces, BCL-2-family-style grooves, GPCR helical interfaces).
- As an alternative to PepGLAD when helical conformation is desired up-front rather than co-designed.

## Hand A Mission To An Agent

```text
Use the BioSymphony Structure Factory skill with the HelixDiff tool card. For target <PDB:ID> with target-window report <path>, prepare a short-helix design lane. Specify peptide length range (15-40 aa), helical motif or contact constraints, ProteinMPNN sequence pass on the receptor context, and the cofold + interface checks downstream.
```

## Typical Inputs

- Target-window report with chain, residue range, and hotspot evidence.
- Desired peptide length range (typically 15-40 aa).
- Helical motif constraints (e.g., amphipathic, leucine-zipper-like, or template-derived).
- Optional public template peptide for initialization.
- Sample count.

## Typical Outputs

- Candidate helical peptide backbones (PDB) outside git.
- Per-candidate geometry: helix length, hotspot contact count, clash count.
- Sequence-design handoff manifest (typically ProteinMPNN with the receptor as context).
- Cofold ranking input manifest for the validator slate.

## Repo And References

- HelixDiff is described in the conditional full-atom peptide diffusion literature (Liu et al., 2024). Check primary source for current implementation, weights, and license terms before runtime use.

## Key Knobs

| Setting | Recommendation | Why |
| --- | --- | --- |
| Peptide length | 15-30 aa typical | Below 15 aa, switch to RFpeptides; above 40 aa, consider miniproteins. |
| Hotspot constraint count | 3-6 residues | Anchors the helix to the interface; too many over-constrains. |
| Helical content gate | > 70% helix predicted | Reject designs that lose helical character at sequence-assignment time. |
| Sample count | 100-500 first pass | Filter aggressively before cofold to save compute. |
| Downstream ProteinMPNN | with receptor context | Soluble target → SolubleMPNN; membrane / non-soluble → vanilla MPNN. |

## Gotchas

- HelixDiff produces backbones that are helical by construction, but the sequence pass can introduce helix-breakers (prolines, glycines in the middle) that destabilize the helix. Filter the post-MPNN helical content.
- The cofold validator may report a low iPTM if the helix is too short to register a confident interface; do not promote based on iPTM alone for sub-20-aa helices — inspect the PAE matrix and ipSAE.
- Hotspot constraints that are spread across more than one face of the helix are physically incompatible; check the spatial arrangement of hotspots before specifying.
- Wet-lab synthesis of helical peptides at this length needs helix stapling or terminal capping to maintain conformation in solution. The repo does not generate synthesis routes; cap claims at `computational_candidate`.

## Gates

- Treat generated helices as computational candidates only.
- Require orthogonal cofold + interface checks before shortlist promotion.
- Do not publish generated sequences or structures unless explicitly curated and audited.
- Keep weights, trajectories, and per-design metrics outside git.
- Run a currency check before any paid GPU dispatch: upstream repo HEAD (releases + recent commits), current release notes, and recent preprints (biorxiv / chemrxiv / arxiv) on the relevant lane. Record the version pin and the date of the check in the candidate ranking or validation notes.
