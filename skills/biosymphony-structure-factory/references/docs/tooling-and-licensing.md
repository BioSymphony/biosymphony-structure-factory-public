# Tooling And Licensing

Review source dates and exact license posture in `references/software-registry.yaml`.

This is the public, human-readable tool posture for BioSymphony Structure Factory. It complements the machine-readable registry at `references/software-registry.yaml`.

This is engineering guidance, not legal advice. Mentioning a tool in public docs is allowed; installing it, baking it into an image, running it for a user, or redistributing it requires checking the current primary license/source terms and the user's use case.

For result-boundary vocabulary that tool outputs may support, see [`result-boundaries.md`](result-boundaries.md).

## Agent Rule

Before selecting a tool lane, you and your agent must record:

- current primary source checked
- intended use: personal, academic/non-profit, non-commercial, commercial, or institutional
- action: mention, scaffold, install at runtime, bake into public image, bake into private image, or run
- setup posture: public/prebuilt image, private image, runtime bootstrap, RunPod Network Volume bootstrap, AWS Batch image, local install, SSH/HPC module, or neocloud/generic cloud volume
- redistribution posture: none, source build, binary layer, model weights, database, installer, or license file
- required user action, if any

If a required fact is missing, label the lane `review_required` or `runtime_gated`. Do not schedule execution until the missing review is complete.

## Public Vs Private Split

Public docs and repos may mention all relevant tools, including gated tools, as long as they do not include secrets, license files, private installer URLs, proprietary binaries, private data, large public data, or model weights.

Public images are stricter because image layers redistribute software. Only reviewed redistributable tools belong in public images.

Store run-specific notes in ignored runtime state. Record secret-store references and environment-variable names, never secret values, license files, private installer URLs, or private biological data.

A private image, runtime bootstrap, and a runtime cache are setup postures. Select one that meets the selected tool's redistribution, data, and runtime requirements.

## Posture Classes

| Class | Public docs | Public image | Private/runtime use |
| --- | --- | --- | --- |
| Open-default | Mention and scaffold | Usually OK with notices, citations, SBOM, and source-compliance | OK |
| Review-required | Mention and scaffold with caveats | Only after exact current license/build review | OK after review |
| Runtime-gated | Mention and scaffold gates only | Do not include | User/licensee runtime install or manual activation only |
| Internal-only | Do not publish private details | Do not include | Local ignored notes only |

## Open-Default Candidates

These are the default candidates for ambitious no-license-application demos, subject to preserving notices, citations, and source-compliance obligations:

- Structure Factory scripts, schemas, RunPod entrypoints, manifests, and public accession metadata.
- RELION.
- Warp/M/WarpTools.
- Topaz.
- MotionCor3 from the CZI source repository.
- ModelAngelo code. Keep large weights as runtime caches unless redistribution terms are explicitly recorded.
- Coot open-source builds.
- PyMOL open-source builds with no paid Schrodinger assets.
- gemmi.
- Mol*.
- Blender.
- Boltz/Boltz-2, pinned to PyPI 2.2.1 in the registry.
- Chai-1, with current upstream Apache-2.0 code and weights. Pin and recheck on upgrades, and record MSA-server/privacy posture.
- Biohub ESMFold2, ESMFold2-Fast, and ESMC-6B local-weight routes. The registry records a reviewed MIT source posture with third-party notices and no repository-imposed license gate. These routes remain `planned` and `adapter_required` until the selected source revision, Python/Torch runtime, weight-cache posture, and adapter pass a dry run. A Biohub API route has separate service terms, acceptable-use, budget, and data-handling review.
- OpenMM.
- GROMACS.
- AutoDock Vina.
- RDKit.
- MolViewSpec.
- PoseBusters.
- MolPAL, when used as an active-learning planner over public fixtures or operator-approved runtime libraries.
- ProteinMPNN.
- LigandMPNN.
- CoSiNE antibody CTMC evolution/VEP, MIT-licensed. Mention and scaffold are open; execution is GPU-only (flash-attn/jax install bar), so treat running it as runtime-gated on GPU access.

For a public image, GPL/LGPL tools require normal compliance work: license texts, source/build recipes, citation metadata, and ideally SBOM/source-offer notes.

## Review-Required Candidates

These can be useful and can be mentioned publicly, but agents should not treat them as no-license-needed image contents until the exact current package, binary source, dependency stack, and redistribution terms are checked:

- CTFFIND.
- cisTEM.
- cryoDRGN and related GPL-heavy heterogeneity stacks.
- EMAN2.
- Scipion/Xmipp and plugin stacks.
- GNINA, because license posture depends on exact build/dependencies.
- DeepEMhancer, especially model-weight redistribution.
- CUDA/NVIDIA base images and drivers under current NVIDIA container terms.
- Large public weights, maps, databases, or reference bundles even when redistribution is technically permitted.
- RFdiffusion, its container dependencies, and mirrored or non-official weights. The official source and README-referenced weights are under the upstream BSD license; keep dependency, CUDA/SE3, exact-commit, weight-hash, and claim-ceiling review before execution, and treat mirrored or non-official weights as review-required until their source and terms are recorded.
- AlloGen, because the Hugging Face metadata and README front matter report Apache-2.0 while the raw repository `LICENSE` file is MIT. Public mention and scaffolding are OK, but image inclusion, checkpoint redistribution, or execution requires recording the exact license posture, the Hugging Face snapshot revision, checkpoint hashes, and whether the lane is scoring-only or active guidance through RFdiffusion/PXDesign/Proteina-style priors.
- Genie 3 and related setup/evaluation dependencies until the repo, Hugging Face weights, ColabFold/AlphaFold2 parameters, ProteinMPNN, IPSAE, FoldSeek, TMscore/TMalign, DSSP helper, CUDA/JAX, and any MSA-server use are recorded for the intended use. Structure Factory bootstrap requires an explicit `GENIE3_ALLOW_COLABFOLD_PARAMS=1` acknowledgement before upstream setup can download AlphaFold2 multimer parameters.
- BioEmu until model checkpoints, AlphaFold2/ColabFold-related weights, MSA-source posture, and cache policy are recorded for the intended use. Public docs may mention and scaffold the lane, but weights, generated ensembles, MSA output, and provider logs stay outside public git.
- Protenix and OpenFold3-preview until exact code, model-parameter, dependency, and benchmark posture are recorded for the intended use.
- BoltzGen and PLACER until exact source, model-weight, dependency, and downstream validation posture are recorded.

- SwitchCraft multistate/switch design and its vendored cofolder and sequence-model weights, until the repo's pinned dependencies and weight terms are recorded for the intended use. The framework is MIT-licensed; outputs are single-cofolder computational candidates and should be cross-checked with the cofold scoring stack.
- DOMINO multidomain construct design. Upstream license is unresolved: no LICENSE file in the repo, an empty Hugging Face model card, and a no-reuse preprint license at review. Mention and scaffold only; do not bake into an image, redistribute weights, or run paid compute until the authors publish terms.

A review-required tool can run after the operator records the current terms and intended use. Image inclusion, redistribution, and execution can have different terms, so record the action that the review covers.

## Runtime-Gated Or Use-Context-Gated Tools

These may be documented and scaffolded publicly, but should stay out of public images and out of "no-license-needed" demos unless the user/operator has accepted the relevant terms and supplied runtime access through secure configuration:

- CryoSPARC.
- Phenix.
- ChimeraX and ISOLDE.
- MotionCor2 UCSF binary.
- crYOLO.
- Gctf unless a redistributable current license is confirmed.
- RECOVAR, due to academic/non-commercial use-context terms.
- Rosetta/PyRosetta.
- AlphaFold 3 model parameters and related restricted weights/databases.
- Apple SimpleFold released model assets. The source code is MIT-licensed, but
  `LICENSE_MODEL` limits the released models and derivatives to the research
  purposes defined there. Record the intended non-commercial scientific
  research or academic-development use before model acquisition or execution.
- Schrodinger/Incentive PyMOL binaries and license files.

For these, public docs should say what the lane would do and what evidence it would emit, but the lane must report `skipped`, `blocked`, or `ready` based on runtime checks.

## Demo Planning Defaults

For no-license-application Structure Factory demos, prefer:

- CryoCore handoff docs for raw/subset requests: RELION, Topaz, CTFFIND only after review, MotionCor3 after current source/build check
- deposited PDB/EMDB structure-mapping reports: ModelAngelo, gemmi, Mol*, Blender, Coot open-source, PyMOL open-source
- heterogeneity: cryoDRGN after GPL/source-compliance review; RECOVAR only as runtime/use-context gated
- MD/docking side lanes: OpenMM, GROMACS, AutoDock Vina, RDKit
- AI/model-comparison side lanes: Boltz, Chai after current terms check, ESMFold2 local weights after source, runtime, weight-cache, and adapter review; the API route also requires service terms and data-handling review; SimpleFold after the Apple model-use gate and runtime-adapter review; BioEmu after current source/weights/MSA review, ProteinMPNN, LigandMPNN, RFdiffusion after dependency/weight-hash review, AlloGen after license-metadata and checkpoint-hash review, Genie 3 after current dependency/weights review
- screening review side lanes: MolPAL for active-learning tranches and PoseBusters for pose plausibility checks, with private ligand libraries and generated poses kept outside public git

ChimeraX can remain a strong visual lane for internal or private demos when the operator's use context permits it, but it is not part of the public no-license-needed stack.

## Required Artifact Notes

Any run using these tools should emit:

- `versions.json` or tool-specific version files
- runtime execution record with command status, without secrets or private argument values
- citation notes
- license/use-context notes
- artifact hashes
- validation notes separating `planning`, `public_demo`, `public_synthetic_demo`, `computational_candidate`, `insufficient_support`, and `blocked`

Open-source tool outputs need provenance, version, citation, and result boundaries. Runtime-gated tool outputs also need use-context notes.
