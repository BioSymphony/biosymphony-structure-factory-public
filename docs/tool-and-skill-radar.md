# Tool And Skill Radar

Snapshot date: 2026-06-21

This is a planning snapshot, not legal advice and not a current license determination. Before installing, baking into an image, running, or redistributing any third-party tool, recheck the primary source terms and record the user's intended use context.

## June 2026 Candidate Additions

These are unvalidated watchlist entries from a fresh public-source pass. They are useful enough to keep in the public tool knowledge base, but they are not promoted dependencies until a smoke run emits the named contract and the current license/use-context check is recorded.

| Candidate | Fit | First Structure Factory Contract | Gate |
| --- | --- | --- | --- |
| [BindCraft](https://github.com/martinpacesa/BindCraft) | High-fit protein binder design pipeline using AF2 backpropagation, MPNN, and PyRosetta. | `bindcraft_designs/`, filter ledger, `design_manifest.json`, downstream cofold scorecards. | PyRosetta, AF2 weights, dependency terms, and target-use context. |
| [Proto](https://github.com/evo-design/proto-language) | Biological design programming layer for composing sequences, generators, constraints, and optimizers. | `proto_program.json`, `proto_run_manifest.json`, exported assets, version ledger. | Hosted API/MCP input policy, runtime credential handling, tool wrappers, caches, and export shape. |
| [AlloGen](https://huggingface.co/ChatterjeeLab/AlloGen) | State-selective allosteric protein-design scorer/generator candidate for apo/holo comparison lanes. | `allogen_manifest.json`, `allogen_scores.json`, selectivity ranking. | Checkpoint terms, input policy, generator provenance, and orthogonal structure scoring. |
| [BinderFlow](https://github.com/cryoEM-CNIO/BinderFlow) | Binder campaign pipeline/benchmark candidate for comparison lanes. | `binderflow_manifest.json`, benchmark table, cofold handoff ledger. | Repo, dependency, and runtime review. |
| [ProteinDJ](https://github.com/PapenfussLab/proteindj) | Protein design pipeline watchlist item. | `proteindj_manifest.json`, design batch, validator scorecards. | Repo, weights, and independent validation review. |
| [Promera](https://github.com/bjing2016/promera) | Unified cofolding plus minibinder/nanobody design model in the Boltz-family lane. | `promera_manifest.json`, cofold/design outputs, confidence sidecars, downstream cofold scorecards. | Repo, weights, MSA setup, confidence output shape, and independent scoring. |
| [DeCAF](https://github.com/genesistherapeutics/decaf) | Few-step cofolding accelerator watchlist for high-throughput triage if released weights support useful confidence outputs. | `decaf_manifest.json`, speed/quality smoke table, confidence sidecars. | Code/weight release, PAE or confidence output, complex-type support, and ranking smoke. |
| [DockQ](https://github.com/wallnerlab/DockQ) v2 | Reference-based interface scoring for protein, nucleic-acid, and small-molecule docking models. | `interface_quality_scores.tsv`, chain mapping, reference complex ledger. | Requires a suitable reference complex and current package check. |
| [BioEmu](https://github.com/microsoft/bioemu) | Protein monomer ensemble sampling for flexibility-risk review. | `bioemu_ensembles/`, `ensemble_manifest.json`, `flexibility_risk_report.json`. | Model caches, AF2/ColabFold-related weights, MSA posture, and monomer-only boundary. |
| [MolViewSpec](https://github.com/molstar/mol-view-spec) | Portable molecular-view state files for review packets and static reports. | `molviewspec_states/`, `structure_view_manifest.json`. | Keep states compact and avoid heavy generated structures in git. |
| [MolPAL](https://github.com/coleygroup/molpal) | Active-learning tranche planner for large screening libraries. | `active_learning_tranches.json`, `acquisition_report.json`. | Score-provider, library-policy, and external execution review. |
| [PoseBusters](https://github.com/maabuu/posebusters) | Pose plausibility checks for generated or docked ligand poses. | `pose_validity.jsonl`, `pose_quality_ledger.json`. | Pose-quality evidence only; not binding or affinity proof. |
| [Workflow Run RO-Crate](https://www.researchobject.org/workflow-run-crate/) | Provenance envelope for provider closeout and artifact bundles. | `ro-crate-metadata.json` with public path-omission policy. | Profile mapping and private-path omission review. |
| [nf-core/proteinfold](https://github.com/nf-core/proteinfold) | Nextflow folding workflow candidate once Structure Factory contracts are mapped. | `proteinfold_launch_manifest.json`, `tool_versions.yml`, Nextflow report. | Wrapped tool, database, weight, and container-digest review. |
| [PDBe MCP Servers](https://github.com/pdbeurope/pdbe-mcp-servers) | Agent-accessible public structure metadata lookup. | `resolved_accessions.json`, source/citation ledger. | Public accession queries only; do not send private biological inputs. |
| [DynaMight](https://github.com/3dem/DynaMight) and cryoDRGN-AI-style tools | Cryo-EM heterogeneity and ensemble-context watchlist. | `heterogeneity_report.json`, model/version ledger. | CryoCore boundary, map/data posture, and weight/license review. |
| [FoldMason](https://github.com/steineggerlab/foldmason) | Fast multi-structure alignment and tree/report generation. | `structure_alignment.a3m`, `structure_alignment.html`, `structure_tree.nwk`. | License/source check and reference-structure provenance. |

## Ready In The Public Harness

- Public campaign contracts, stage contracts, provider profiles, task packs, validators, and audit gates.
- Local no-download examples for PD-L1 binder-design planning and screening fixture runs.
- Tracked RunPod bridge templates that document required fields without embedding live payloads, provider identifiers, or approvals.
- Portable agent instructions and Symphony and tracker-neutral task packs for `sym:structure-factory`.
- A machine-readable software registry for planned, gated, and pinned tool lanes: `references/software-registry.yaml`.

## Open Or Default Scaffolding

These are suitable for public mention and scaffolded planning after normal citation and current-term checks:

- Boltz-style cofolding and confidence extraction.
- ProteinMPNN or LigandMPNN-style sequence design lanes.
- RDKit, AutoDock Vina, OpenMM, GROMACS, gemmi, Mol*, MolViewSpec, Blender, and open-source PyMOL builds.
- MolPAL-style active-learning planning and PoseBusters-style pose plausibility checks when ligand libraries and pose files are public fixtures or operator-approved runtime artifacts.
- ModelAngelo-style model building where weights and downloads are handled through reviewed runtime caches.

## Review Required

These can be useful, but public image inclusion or execution should wait for exact build and dependency review:

- RFdiffusion-family and RFdiffusion3-family design lanes, including code, weights, and Docker image posture.
- Genie 3 and peptide/miniprotein use, especially weights, ColabFold or AlphaFold2 dependencies, MSA service posture, and evaluation helpers.
- Chai, LocalColabFold, ABCFold, ipSAE wrappers, and cofold consensus stacks.
- SwitchCraft multistate/switch design, including its vendored cofolder and sequence-model weights and pinned dependencies; route designs through the cofold scoring stack for an orthogonal check.
- DOMINO multidomain construct assembly, downstream of a validated binder; upstream license is unresolved (no LICENSE, empty model card, no-reuse preprint), so treat reuse and image inclusion as blocked until terms are published.
- Baker miniprotein-GPCR recipe (motif-directed RFdiffusion + ProteinMPNN + AF2 over public deposited targets), inheriting the upstream tools' posture.
- CTFFIND, cisTEM, GNINA, cryoDRGN, EMAN2, Scipion/Xmipp, DeepEMhancer, CUDA/NVIDIA bases, and large public weight/database bundles.
- Protenix, OpenFold3 v0.5.0 with OpenBind v0 parameters, BioEmu, PLACER, and BoltzGen until exact source, model-weight, dependency, and cache posture are recorded for the intended use.

## Runtime Gated

Public docs may describe these lanes, but committed public artifacts must not include installers, binaries, license files, credentials, or accepted-license state:

- CryoSPARC, Phenix, ChimeraX, ISOLDE, Rosetta/PyRosetta, AlphaFold 3 parameters, commercial PyMOL binaries, and similar terms-controlled tools.
- Any tool requiring private registry credentials, signed URLs, private installer links, or account-specific access.

## Omitted Or Private

Keep these out of public git:

- Private run notes, local checkpoints, provider cost ledgers, concrete pod IDs, concrete volume IDs, and operator incident reports.
- Generated PDB/CIF/MMCIF/MRC/MAP/TRB/PML/MP4/GIF/NPZ/model-weight artifacts.
- Private demos that have not been rewritten as narrative-only public summaries.

## Export Priorities

1. Keep Makefile targets aligned with documented commands.
2. Publish concise tool cards under `tools/` with posture, inputs, outputs, and gates.
3. Prefer narrative demos and compact public tables over result dumps.
4. Keep live execution state out of tracked templates. Materialize an ignored runtime packet after readiness checks and explicit human authorization.
