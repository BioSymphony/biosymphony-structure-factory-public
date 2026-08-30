# RFpeptides

## Purpose

Plan cyclic or constrained peptide design lanes in the RFdiffusion family. RFpeptides extends the RFdiffusion approach to peptide-scale binders (6-15 amino acids), including head-to-tail cyclization, disulfide constraints, and other backbone-link patterns that small-molecule-style peptides require.

## Public-Safe Status

Public scaffold: yes. Runtime use requires current RFdiffusion-family code, weight, and dependency review. Store weights and generated peptides under ignored runtime storage or in a user-selected artifact store.

## When To Use

- Short cyclic peptide binders (6-15 aa) against a defined target hotspot window.
- Peptidomimetic design where backbone constraints (head-to-tail cyclization, disulfide bridges) are non-negotiable.
- Cases where a linear miniprotein is too large for the target geometry but a small constrained peptide could thread the interface.

## Hand A Mission To An Agent

```text
Use the BioSymphony Structure Factory skill with the RFpeptides tool card. For target <PDB:ID> with hotspot window <residues>, prepare a cyclic or constrained peptide design lane. Specify cyclization style (head-to-tail, disulfide), residue length range, the ProteinMPNN cyclic-mode sequence pass, and the cofold handoff.
```

## Typical Inputs

- Public target structure and hotspot window (3-5 critical residues).
- Peptide length range (6-15 aa typical).
- Cyclization specification: head-to-tail backbone closure, disulfide pair, or other backbone link constraint.
- Sample count.
- Optional template peptide when refining a known starting point.

## Typical Outputs

- Generated peptide backbones (PDB) outside git, often shown as ribbon/cartoon rather than all-atom because side chains come from the downstream MPNN pass.
- Per-design constraint satisfaction summary: cyclization closure RMSD, hotspot contact count, clash count.
- Sequence-design handoff (typically ProteinMPNN in cyclic mode) and cofold ranking input manifest.

## Repo And References

- RFdiffusion family: https://github.com/RosettaCommons/RFdiffusion
- Cyclic peptide / macrocycle design with RFdiffusion is described in the RFdiffusion all-atom and follow-up Baker lab papers (Krishna et al. 2024; cyclic-peptide methods preprints).

## Key Knobs

| Setting | Recommendation | Why |
| --- | --- | --- |
| Peptide length | 6-12 aa for cyclics | Above ~15 aa, switch to HelixDiff / PepGLAD or miniproteins. |
| Cyclization mode | head-to-tail or disulfide | Match the chemistry the downstream synthesis lane supports. |
| `ppi.hotspot_res` | 3-5 hotspot residues | Too few = weak interface; too many = over-constrained. |
| `inference.num_designs` | 100-500 | Small backbones; sample density matters. |
| Backbone-link RMSD gate | < 0.5 Å closure | Fail-closed: reject designs that do not close cleanly. |
| Downstream ProteinMPNN cyclic | mandatory | Sequence pass for cyclic backbones must respect closure. |

## Gotchas

- Cyclic backbones that look closed in the generated PDB may still have unsatisfied valences; verify the bond geometry before sequence assignment.
- ProteinMPNN must be invoked in cyclic mode (`--cyclic 1` or equivalent) or the resulting sequence will treat the peptide as linear.
- Cofold validators were largely trained on linear sequences; their iPTM may under-report binder quality on cyclic peptides. Use ipSAE on the PAE matrix and visual inspection alongside iPTM.
- Disulfide-constrained designs need explicit cysteine positions specified ahead of time; otherwise the sequence pass will not place them where the constraint expects.
- Wet-lab synthesis of cyclic peptides has its own constraints (residue tolerances, head-to-tail cyclization yield); cap claims at `computational_candidate` and consult chemistry before promotion.

## Gates

- Check cyclization closure RMSD and target hotspot contacts before downstream spend.
- Do not commit generated PDBs, trajectories, or candidate batches.
- Keep claims at `computational_candidate` until orthogonal cofold + chemistry review.
- Rebuild public launch packets from tracked source; never publish embedded payload manifests with private synthesis routes.
- Run a currency check before any paid GPU dispatch: upstream repo HEAD (releases + recent commits), current release notes, and recent preprints (biorxiv / chemrxiv / arxiv) on cyclic peptide design and the RFdiffusion family. Record the version pin and the date of the check in the candidate ranking or validation notes.
