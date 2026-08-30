# Container Image Plans

These folders define Structure Factory image families. They are build plans, not license bundles. Restricted tools stay runtime-gated unless their terms explicitly allow redistribution.

## Image Families

- `cryo-core`: open-source cryo-EM processing and smoke tooling.
- `cryosparc`: CryoSPARC planning lane with runtime license requirements.
- `model-build`: ModelAngelo, Coot, Phenix-gated refinement, ChimeraX-gated review.
- `ai-design`: Boltz, Chai, ProteinMPNN, LigandMPNN, AlphaFold/RFdiffusion gated lanes.
- `md-docking`: OpenMM, GROMACS, AutoDock Vina, GNINA, RDKit, MDAnalysis.

The first ready-to-run image should be `cryo-core` and must pass the no-download smoke manifest.
