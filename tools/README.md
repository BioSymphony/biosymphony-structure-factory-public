# Tool Cards

These cards describe the Structure Factory tool lanes your agent can compose into a campaign. Each card lists the lane, the runtime gate, the typical inputs and outputs, and the license posture so an agent or operator can decide what to include and what to defer.

Each card follows the same shape:

- Public docs describe the lane and the expected evidence it produces.
- Runtime use needs current primary-source review and the user's intended use context.
- Public images include tools whose redistribution posture has been reviewed.
- License-gated tools install at runtime after the user reviews and accepts their terms. Store private install paths, provider records, accepted-license state, credentials, weights, and generated biological artifacts under ignored runtime storage or in a user-selected artifact store.

The wider tool knowledge base lives in [`references/software-registry.yaml`](../references/software-registry.yaml). Candidate tools that are useful but do not yet deserve a full card are tracked in [`docs/tool-and-skill-radar.md`](../docs/tool-and-skill-radar.md).

## Cards

### Backbone And Peptide Design

- [Published binder cohort](published-binder-cohort.md). Exact Anthropic-study identities, replay-versus-swap semantics, and runtime binding rules.
- [RFdiffusion3](rfdiffusion3.md). Atom-level diffusion for binder backbones, miniproteins, and biomolecular interfaces.
- [RFpeptides](rfpeptides.md). Cyclic and constrained peptide design in the RFdiffusion family.
- [BindCraft](bindcraft.md). Integrated binder-design pipeline behind PyRosetta, AF2-weight, dependency, and use-context gates.
- [FreeBindCraft](freebindcraft.md). BindCraft-family generation without a required PyRosetta step.
- [BoltzGen](boltzgen.md). Boltz-family binder generation lane for canaries and method comparison.
- [PXDesign](pxdesign.md). Target-conditioned binder backbone generation with explicit sequence-design handoff.
- [Proteina-Complexa](proteina-complexa.md). Protein-, ligand-, and motif-binder co-design for predefined or custom targets.
- [HelixDiff](helixdiff.md). Short helical peptide design conditioned on target hotspots.
- [PepGLAD](pepglad.md). Full-atom peptide sequence-structure co-design.
- [EvoBind](evobind.md). Sequence-centered peptide optimization for ranked candidate sets.
- [Genie3 peptides and miniproteins](genie3-peptides.md). Length-aware peptide and miniprotein generation.
- [Baker miniprotein-GPCR pipeline](baker-miniprotein-gpcr.md). Motif-directed RFdiffusion + ProteinMPNN + AF2 recipe for Class B GPCR ECD binders. A methods bundle, not a forked tool.

### Sequence Design

- [ProteinMPNN](proteinmpnn.md). Backbone-to-sequence design. Includes SolubleMPNN for soluble targets.

### Antibody Sequence Evolution And Scoring

- [CoSiNE](cosine.md). Antibody affinity maturation as a neural CTMC: sequence-only evolutionary likelihood, zero-shot variant-effect prediction (VEP), and oracle-guided CDR/FR maturation. Structure-free; route candidates through the cofold scoring stack for an orthogonal structural check.

### Multistate And Switch Design

- [SwitchCraft](switchcraft.md). De novo design of state-switching proteins: one sequence, multiple ligand-conditioned conformations (allostery, induced binding, ligand discrimination, small-molecule biosensors). Route every switch through the cofold scoring stack for an orthogonal check.

### Construct Assembly And Multidomain Fusion

- [DOMINO](domino.md). Domain co-occurrence scoring and multidomain sequence generation for fusion constructs downstream of a validated binder. Adjacent to the binder stack, not a binder designer; upstream license unresolved at review.

### Cofold, Structure Prediction, And Scoring

- [Cofold scoring stack](cofold-scoring-stack.md). Multi-validator slate plus ipSAE rescore. Reads from the individual cards below.
- [Boltz](boltz.md). Open biomolecular cofold with confidence and full PAE outputs.
- [Chai-1](chai.md). Open biomolecular cofold with MSA-driven prediction.
- [OpenDDE](opendde.md). Open all-atom biomolecular cofold/prediction lane with ABAG checkpoint and optional PAE/PDE sidecars.
- [ESMFold2](esmfold2.md). Biohub structure prediction and foldability review lane, with Hugging Face weights as the first cloud canary route and Biohub API as optional/deferred.
- [ESMFold2 binder control notes](esmfold2-binder-controls.md). Sequence, structure, interface, logit, and optimization controls for constraining ESMFold2/Biohub binder-design runs against a deposited target site.
- [SimpleFold](simplefold.md). Apple single-protein structure and conformational-ensemble prediction through PyTorch or MLX, behind the released-model research-use gate.
- [Protenix](protenix.md). Biomolecular complex prediction; Protenix-v2 is the exact published binder-study scoring variant.
- [BioEmu](bioemu.md). Sequence-conditioned monomer ensemble sampling for flexibility-risk review.

### Refinement And Visualization

- [Refinement stack](refinement-stack.md). Energy minimization, interface analysis, and quality filters.
- [MolViewSpec](molviewspec.md). Declarative molecular-view state files for compact, reproducible report scenes.
- [ChimeraX peptide visualization](chimerax-peptide-viz.md). Publication-style render lanes for figures.
- [ChimeraX onboarding](chimerax-onboarding.md). Single-file teammate-handoff brief for first render in ~30 minutes.

### Screening And Pose Review

- [MolPAL](molpal.md). Active-learning tranche planner for large ligand libraries.
- [PoseBusters](posebusters.md). Pose plausibility checks for generated or docked ligand poses.
- [PLACER](placer.md). Focused protein-ligand local conformational ensemble lane.

### Target Prep

- [GCGR target prep](gcgr-target-prep.md). Worked example of public-deposited target preparation.

## When To Use What

A short routing guide. Pick the designer arm by target and binder length, then add the rest of the stack.

| If you want | Start with | Add downstream |
| --- | --- | --- |
| Short cyclic peptides (6 to 15 aa) | [RFpeptides](rfpeptides.md) | [ProteinMPNN](proteinmpnn.md) cyclic mode, [Cofold scoring stack](cofold-scoring-stack.md) |
| Linear helical peptides (15 to 40 aa) | [HelixDiff](helixdiff.md) or [PepGLAD](pepglad.md) | [ProteinMPNN](proteinmpnn.md) on the receptor context, [Cofold scoring stack](cofold-scoring-stack.md) |
| Sequence-centered peptide optimization | [EvoBind](evobind.md) | Optional [ProteinMPNN](proteinmpnn.md) consistency check, [Cofold scoring stack](cofold-scoring-stack.md) |
| Miniprotein binders (50 aa and up) | [RFdiffusion3](rfdiffusion3.md) or [Genie3](genie3-peptides.md) | [ProteinMPNN](proteinmpnn.md) (SolubleMPNN for soluble targets), [Cofold scoring stack](cofold-scoring-stack.md) |
| Integrated binder-design canary | [BindCraft](bindcraft.md) or [BoltzGen](boltzgen.md) | [Cofold scoring stack](cofold-scoring-stack.md), [Refinement stack](refinement-stack.md) |
| Class B GPCR ECD antagonist by peptide mimicry | [Baker miniprotein-GPCR](baker-miniprotein-gpcr.md) | [ProteinMPNN](proteinmpnn.md) (SolubleMPNN), [Cofold scoring stack](cofold-scoring-stack.md) |
| A protein that changes shape on ligand binding (allostery, AND gate, biosensor) | [SwitchCraft](switchcraft.md) | [Cofold scoring stack](cofold-scoring-stack.md) for the orthogonal switch check |
| Add a function or effector to a validated binder (fusion construct) | [DOMINO](domino.md) | [Cofold scoring stack](cofold-scoring-stack.md) to prove both modules fold |
| Triage or mature antibody variant libraries (sequence-only) | [CoSiNE](cosine.md) | [Cofold scoring stack](cofold-scoring-stack.md) for an orthogonal structural check |
| Cofold one designed candidate against a target | [Boltz](boltz.md), [Chai-1](chai.md), or [OpenDDE](opendde.md) alone | [Cofold scoring stack](cofold-scoring-stack.md) for multi-validator gating |
| Check foldability or uncertainty for a public sequence/candidate | [ESMFold2](esmfold2.md) | [Cofold scoring stack](cofold-scoring-stack.md) when interface or binder claims are requested |
| Sample alternate monomer conformations from a public sequence | [SimpleFold](simplefold.md) | [Cofold scoring stack](cofold-scoring-stack.md) when interface or binder claims are requested |
| Check monomer conformational spread | [BioEmu](bioemu.md) | [MolViewSpec](molviewspec.md) for report scenes, [Cofold scoring stack](cofold-scoring-stack.md) when interface claims are requested |
| Prioritize a large ligand library | [MolPAL](molpal.md) | Score provider lane, [PoseBusters](posebusters.md), screening consensus ranking |
| Check ligand pose plausibility | [PoseBusters](posebusters.md) | [PLACER](placer.md) or refinement follow-up for focused cases |
| Promote a candidate from a design batch | [Cofold scoring stack](cofold-scoring-stack.md) | [Refinement stack](refinement-stack.md), [ChimeraX](chimerax-peptide-viz.md) |
| Prepare a target from public deposited evidence | [GCGR target prep](gcgr-target-prep.md) as a pattern | Plug the output target-window file into any designer arm |

## Stack Pattern

A common end-to-end binder campaign:

```text
target prep
  -> designer (RFdiffusion3 | RFpeptides | HelixDiff | PepGLAD | EvoBind | Genie3)
  -> sequence design (ProteinMPNN or SolubleMPNN)
  -> foldability/uncertainty review (ESMFold2 where useful)
  -> cofold slate (Boltz + Chai-1 + AF2-Multimer + optional OpenDDE)
  -> ipSAE rescore on PAE matrices
  -> consensus gate
  -> refinement
  -> rendered report
```

The cofold scoring stack card explains how to compose Boltz, Chai-1,
AF2-Multimer, and optional OpenDDE into the validator slate.

## Important Context

- iPTM alone is increasingly deprecated for binder ranking. Recent benchmarks prefer ipSAE and multi-validator consensus over single-cofolder iPTM.
- Wet-lab confirmation lives downstream of every card here. The cards describe in silico triage and provenance, not binding proof.
- For each new target, start with a target-prep step that pins accession, chain, hotspots, and uncertainty. The designer arms expect this target-window file as input.
