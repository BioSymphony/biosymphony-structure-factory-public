# Public Repo And Private Image Policy

Last reviewed: 2026-05-01

This note records the current redistribution posture for BioSymphony Structure Factory. It is an engineering policy, not legal advice.

For the canonical public tool catalog and use-context guidance, see `docs/tooling-and-licensing.md`. This file focuses specifically on repository and container-image redistribution.

## Default Split

Public or private git repos may contain:

- Structure Factory orchestration code, manifests, validators, Dockerfiles, RunPod templates, task drafts, and docs.
- Tool names, citations, install recipes, official download URLs, accession IDs, hashes, deterministic subset rules, and placeholder environment variable names.
- License gates that report `ready`, `skipped`, or `blocked`.

Git repos must not contain:

- Real license IDs, license files, API tokens, RunPod secrets, deploy keys, private installer URLs, paid download links, or account-specific credentials.
- Raw cryo-EM movies, private maps/models, unpublished sequences, private biological data, large public datasets, or large model weights.
- Proprietary or access-controlled installers and binaries.

Container images are stricter than repos. A public image is redistribution. A private image avoids public exposure, but it can still be a copy of third-party software stored with a registry provider and pullable by any account with access. For license-gated tools, runtime install from user-owned secrets is the cleaner default.

GHCR is optional. It is one private-registry option, not a required Structure Factory dependency. When registry auth is not worth the complexity or the tool should not be redistributed in a public image, prefer a public base image plus runtime install or a dedicated RunPod Network Volume bootstrap.

## Image Classes

| Class | Public repo | Public image | Private image / runtime |
| --- | --- | --- | --- |
| Open-default | Allowed | Allowed with notices, citations, SBOM, and source-compliance where needed | Allowed |
| Review-required | Allowed as reference and scaffold | Only after exact current license/build review | Preferred until reviewed |
| Runtime-gated | Docs and gates only | Do not include | User/licensee runtime install or manual activation only |

## Open-Default: Public Repo And Public Image Candidates

These are generally safe for public scaffolding and public container images when we preserve license notices, citations, build recipes, and source-compliance obligations:

- Structure Factory scripts, schemas, RunPod entrypoints, and manifests.
- Public accession metadata: EMPIAR IDs, EMDB IDs, PDB IDs, official URLs, subset rules, and checksums.
- RELION, under GPLv2. Official docs state it is GPLv2 and free/open-source for academia and industry: https://relion.readthedocs.io/en/release-4.0/Installation.html
- Warp/M/WarpTools, under GPLv3, with GPL-compliant image distribution: https://github.com/warpem/warp
- Topaz, under GPLv3, with GPL-compliant image distribution: https://github.com/tbepler/topaz
- MotionCor3 from the CZI source repo, which GitHub reports as BSD-3-Clause: https://github.com/czimaginginstitute/MotionCor3
- ModelAngelo, MIT code. Prefer runtime cache for large weights unless redistribution terms are explicitly recorded: https://github.com/3dem/model-angelo
- Coot, GPLv3 when using the standalone open-source build: https://github.com/pemsley/coot
- PyMOL open-source builds, with notices and no paid Schrödinger assets: https://github.com/schrodinger/pymol-open-source
- gemmi, MPL-2.0: https://github.com/project-gemmi/gemmi
- Mol*, MIT: https://github.com/molstar/molstar
- Blender, GPL-compliant distribution: https://developer.blender.org/docs/license/
- Boltz/Boltz-2, MIT per current repository: https://github.com/jwohlwend/boltz
- Chai-1, Apache-2.0 per current repository. Pin and recheck on upgrades: https://github.com/chaidiscovery/chai-lab
- OpenMM, GROMACS, RDKit, AutoDock Vina, ProteinMPNN, and LigandMPNN, with normal notice/citation handling.

GPL/LGPL tools are not forbidden in public images, but distributing image layers is distributing binaries. The image lane needs license texts, source access/build recipes, and preferably SBOM/source-offer metadata.

## Review-Required: Public Docs OK, Image Review Required

These may be documented and scaffolded publicly, but should not be promoted into a public image until the exact build, binary source, and dependency posture are reviewed:

- CTFFIND and cisTEM: likely Janelia/BSD-style in common distributions, but verify exact package/license before baking binaries.
- GNINA: classify by exact binary. Default OpenBabel-linked builds are GPL; Apache-only posture requires a different build.
- cryoDRGN and other GPL-heavy heterogeneity images: OK only with GPL compliance.
- EMAN2 and Scipion/Xmipp: review dependency and plugin stack; do not bundle gated third-party plugins.
- DeepEMhancer: code appears public, but model-weight redistribution should be verified before baking weights.
- CUDA/NVIDIA base images: use only under current NVIDIA container terms and preserve notices.
- Large redistributable public weights and databases: prefer runtime download/cache even when license permits redistribution, to keep images small and auditable.
- RFdiffusion and related design-model weights: verify current code, model-weight terms, and user context before image inclusion or execution.
- Genie 3: repo and Hugging Face model metadata currently report Apache-2.0, but public image or execution posture still requires reviewing its setup stack, model weights, AlphaFold2/ColabFold dependencies, ProteinMPNN, IPSAE, FoldSeek, TMscore/TMalign, DSSP helper, and MSA-server privacy posture.

## Runtime-Gated Only

These can have public docs, gates, and runtime placeholders, but no public images, committed installers, committed binaries, committed weights, or committed secrets:

- CryoSPARC. The non-commercial agreement is non-transferable and restricts copying, distribution, third-party use, and commercial use: https://guide.cryosparc.com/licensing/non-commercial-license-agreement
- Phenix. Free use is for non-profit work and requires accepting terms at download; treat installer access as runtime-gated: https://phenix-online.org/license
- ChimeraX and ISOLDE. ChimeraX is no-cost for non-commercial use after accepting UCSF terms; commercial use requires a separate license: https://www.cgl.ucsf.edu/chimerax/docs/licensing.html
- MotionCor2 UCSF binary. UCSF states it may only be downloaded and used for free by academic and/or non-profit users; others need licensing: https://emcore.ucsf.edu/ucsf-software
- crYOLO. Its license is non-commercial academic/research only and restricts copying/distribution/modification: https://cryolo.readthedocs.io/en/stable/other/license.html
- Gctf, unless a redistributable current license is confirmed.
- RECOVAR, because the repository identifies a Princeton academic/non-commercial license: https://github.com/ma-gilles/recovar
- Rosetta/PyRosetta. Treat as runtime-gated and licensee-specific; current licensing status must be checked from the Rosetta license page before use: https://github.com/RosettaCommons/rosetta/blob/main/LICENSE.md
- AlphaFold 3 model parameters. The weights are governed by separate terms and include confidentiality/access restrictions; do not publish or share them in images: https://github.com/google-deepmind/alphafold3/blob/main/WEIGHTS_TERMS_OF_USE.md
- Schrödinger/Incentive PyMOL binaries and license files.

## Private Image Guidance

Private images are possible, but the default Structure Factory posture is:

1. Build public/open images only from open-default tools after current-term and source-compliance review.
2. Use private registry images for our own code and reviewed open-source stacks when a faster cold start is worth it.
3. Use runtime-gated installs for CryoSPARC, Phenix, ChimeraX, MotionCor2, Rosetta/PyRosetta, AlphaFold 3 weights, and similar terms-controlled tools.
4. Inject credentials through RunPod registry credentials, template secrets, or runtime environment variables. Never bake them into image layers.
5. Keep image access limited to the licensee/operator. Do not grant pull access to generic Symphony workers unless they are authorized under the relevant license.

## Network Volume Bootstrap Guidance

The RunPod Network Volume bootstrap posture avoids image redistribution:

- A setup pod starts from a public base image.
- Pinned scripts install allowed tools into `/workspace/structure-factory/software/`.
- Public weights/cacheable assets go under `/workspace/structure-factory/weights/` only when their terms allow that use.
- Every installed tool writes a manifest with version, source URL, command, hash where available, license posture, and smoke command.
- Later pods verify the manifest and smoke command before scientific execution.

This posture is especially useful for ChimeraX-style tools where local noncommercial runtime use may be acceptable for the operator, but public image redistribution is not the right default. It does not remove the need to check current terms or the user's use context.

RunPod supports private container registry credentials through `runpodctl registry` and template registry auth IDs:

- https://docs.runpod.io/runpodctl/reference/runpodctl-registry
- https://docs.runpod.io/pods/templates/manage-templates

Docker Hub supports restricted repositories and collaborator controls:

- https://docs.docker.com/docker-hub/repos/
- https://docs.docker.com/docker-hub/repos/manage/access/

GitHub Container Registry supports private packages and package visibility/access controls:

- https://docs.github.com/en/packages/guides/about-github-container-registry

## Personal And Academic Use Caveat

Personal use is not a universal pass. The relevant distinction is usually:

- personal academic/non-profit use
- non-commercial use
- commercial/industry use
- licensee-only use
- redistribution or third-party access

For a one-person, non-commercial, academic-style RunPod experiment, many gated tools become feasible after the operator accepts each license and supplies runtime credentials. That still does not mean we should bake every gated tool into a reusable image. Runtime install keeps the workflow portable, avoids accidental redistribution, and makes license gates auditable.

## Generated Outputs

Open-source processing outputs such as STAR files, maps, QC plots, classes, and figure panels are usually not forced into the tool license just because an open-source tool produced them. Still record software versions and citations.

Outputs from non-commercial or restricted tools should carry use-context caveats. AlphaFold 3 outputs deserve special handling because the model-parameter terms govern use of the system even though Google does not claim ownership of original generated output.
