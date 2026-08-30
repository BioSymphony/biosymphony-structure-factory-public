# RFdiffusion3

## Purpose

Plan atom-level diffusion design lanes for protein binders, miniproteins, peptide-like binders, and biomolecular interfaces. RFdiffusion (and its all-atom variant) generates backbones conditioned on a target structure, hotspot residues, and contig specifications. Sequences are typically assigned by a downstream ProteinMPNN pass; structural confidence comes from an independent cofold step.

## Public-Safe Status

Public scaffold: yes. Runtime execution and image inclusion require current review of code, weights, Docker image, and dependency terms. Store weights and generated structures under ignored runtime storage or in a user-selected artifact store.

## When To Use

- De novo miniprotein binder backbones (50 aa and up) against a public target window.
- Motif-scaffolding when a substructure of the target is the design constraint.
- Symmetric or partial-diffusion variants when a known scaffold needs incremental refinement.
- Atom-level (all-atom) lanes when small molecules, glycans, or non-standard residues need explicit coordination at the binding interface.

## Hand A Mission To An Agent

```text
Use the BioSymphony Structure Factory skill with the RFdiffusion3 tool card. For target <PDB:ID> with window <chain or residues> and hotspots <residue list>, prepare an atom-level diffusion design lane. Specify contigs, sample count, the downstream ProteinMPNN sequence-design step, and the cofold validator slate (Boltz + Chai-1) the candidates feed into.
```

## Typical Inputs

- Target structure: public PDB or operator-approved structure with chain and residue selection.
- Hotspots: residue list on the target (`A50,A52,A55`) used to focus the binder interface.
- Contigs: design specification mixing fixed regions (`A19-127`) and designed regions (`50-70/0`) per the upstream contig grammar.
- Sample count and batch size.
- Optional model checkpoint selection (binder-design vs general-purpose vs all-atom).

## Typical Outputs

- Generated backbones (PDB) under the configured output directory, outside git.
- Per-design provenance: contig string, hotspots, seed, model checkpoint, time, RMSD/clash metrics.
- Trajectory PDBs if intermediate states are requested (large, keep outside git).
- Downstream handoff manifest pointing to the ProteinMPNN sequence-design step.

## Repo And References

- RFdiffusion: https://github.com/RosettaCommons/RFdiffusion
- RFdiffusion all-atom (RFdiffusionAA): https://github.com/baker-laboratory/rf_diffusion_all_atom
- Paper (RFdiffusion): Watson et al., Nature 2023.
- Paper (RFdiffusionAA): Krishna et al., Science 2024.

## Key Knobs

| Flag / setting | Recommendation | Why |
| --- | --- | --- |
| `inference.num_designs` | 50-200 for first pass | Generation budget; smaller for canary, larger for production. |
| `inference.ckpt_override_path` | binder-design checkpoint for binder lanes | The general checkpoint produces worse interface geometry on PPIs. |
| `contigmap.contigs` | `[A19-127/0 50-70]` style | Format: fixed regions on target / designed binder length range. |
| `ppi.hotspot_res` | `[A50,A52,A55]` | Steers the binder interface toward declared hotspots. |
| `denoiser.noise_scale_ca` | 1.0 default; 0-0.5 for tighter sampling | Lower noise reduces diversity but tightens to the conditioning. |
| `inference.symmetry` | only when designing symmetric assemblies | Most binder runs leave this off. |
| `diffuser.partial_T` | for partial diffusion / refinement | Lower T runs as a refiner; T=0 disables diffusion. |
| `--write_full_pae` (downstream Boltz) | on | Required for ipSAE rescoring of the cofold step. |

## Gotchas

- A clean backbone is not a viable binder. Always run a sequence pass (ProteinMPNN or SolubleMPNN) and an independent cofold (Boltz, Chai) before promoting any candidate.
- Backbones can clash with the target if hotspots and contigs are inconsistent; filter on clash count before sequence design to save downstream cost.
- The all-atom variant is heavier to run; reserve it for cases where ligand or non-standard residue coordination is part of the design objective.
- Random seeds matter: report seed plus checkpoint hash in the candidate ranking so failures are reproducible.
- iPTM alone is increasingly deprecated for binder ranking; cofold the candidates with at least one alternate validator and ipSAE-rescore the PAE matrices.

## Gates

- Validate hotspot references and contig grammar against the target-window file before expensive runs.
- Keep trajectories, generated PDBs, and large metrics outside git.
- Rebuild public launch packets from tracked source after operator approval; do not publish embedded payload manifests with private placement.
- Cap every candidate ranking at `computational_candidate` until independent validation exists.
- Run a currency check before any paid GPU dispatch: upstream repo HEAD (releases + recent commits) for RFdiffusion and the all-atom variant, current release notes, and recent preprints (biorxiv / chemrxiv) on de novo binder design or new RFdiffusion variants. Record the version pin and the date of the check in the candidate ranking or validation notes.
