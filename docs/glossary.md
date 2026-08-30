# Glossary

Structural biology and Structure Factory terms a newcomer or general-purpose agent may want defined before reading further. Definitions are short on purpose. For deeper context see [`docs/capabilities.md`](capabilities.md) and [`docs/agentic-biology-harness.md`](agentic-biology-harness.md).

## Biology And Public Data

- **PDB.** Protein Data Bank. Public repository of deposited macromolecular structures. Accession example: `4ZQK`.
- **EMDB.** Electron Microscopy Data Bank. Public repository of deposited cryo-EM density maps. Accession example: `EMD-12345`.
- **EMPIAR.** Electron Microscopy Public Image Archive. Public repository of raw cryo-EM movies and image data. Accession example: `EMPIAR-10204`.
- **UniProt.** Public protein sequence and functional database. Accession example: `P00533`.
- **Target window.** The residue range or interface region of a protein that a campaign is designed against.
- **Hotspot.** A residue or small set of residues critical to binding or function. Used to condition design or scoring.
- **Interface.** The contact surface between two or more chains. Common target for binder design.

## Design And Prediction

- **Binder design.** Generating candidate molecules (peptide, protein, or small ligand) intended to bind a target.
- **Cofold.** Predicting the structure of two or more molecules together (target plus candidate) to evaluate the interface.
- **Model comparison.** A set of independent structural predictions (across tools or seeds) compared to triage candidates.
- **Candidate ranking.** A ranked list of designed candidates with confidence metrics, failure rows, and provenance.
- **Genie3, RFdiffusion, HelixDiff, PepGLAD, EvoBind, ProteinMPNN.** Protein design tools. See [`tools/`](../tools/) for usage cards.
- **Boltz, Chai.** Cofolding and structure-prediction tools. See [`tools/cofold-scoring-stack.md`](../tools/cofold-scoring-stack.md).
- **ChimeraX.** Structure visualization and rendering toolkit.

## Confidence Metrics

- **pLDDT.** Predicted Local Distance Difference Test. Per-residue confidence score from structure-prediction models, range 0 to 100. Higher is better.
- **iPTM.** Interface Predicted TM-score. Confidence in the predicted protein-protein interface, range 0 to 1. Higher is better.
- **ipSAE.** Interface Predicted Aligned Error variant. Local interface error metric in Ångström. Lower is better.
- **TM-score.** Template Modeling score for global fold similarity. Range 0 to 1.

## Structure Factory Vocabulary

- **Campaign manifest.** The top-level JSON describing a Structure Factory campaign: target, lanes, expected artifacts, result boundary.
- **Campaign mode.** One of `binder-design`, `structure-mapping`, `model-comparison`, `screening`. Selects the lane shapes and task templates.
- **Structure report.** A bundled metadata and validation package about one subject in the campaign, designed to be reviewed by a human or downstream agent without re-deriving the work. Common variants:
  - **Target-window report.** Accession, chain or window, uncertainty notes, hotspot plan, and provenance for the protein the campaign designs against.
  - **Structural report.** A deposited PDB or EMDB structure packaged with accession provenance, validation plan, figure outline, and validation notes.
  - **Map-model report.** A cryo-EM density map (EMDB) paired with its atomic model (PDB), validation outputs, and figure plan.
  - **Candidate report.** A bundle for one or more designed candidates with metrics, structures, failure rows, and provenance.
- **Stage contract.** A JSON document declaring the sequence of fail-closed stages for a provider run.
- **Stage ledger.** Append-only record of stage events emitted during a real provider run (for example `stage-progress.jsonl`).
- **Task pack.** A tracker-neutral set of tasks ready for Linear, GitHub Issues, Notion, or any queue.
- **Bridge manifest.** A tracked RunPod template that captures pod shape, budget, and posture without live execution state.
- **Launch manifest.** A provider-specific runtime artifact built from a bridge manifest after readiness checks and explicit human approval.
- **Validation notes.** A record of what a campaign can support, what remains blocked, and what requires later validation.

## Posture And Gates

- **Result boundary.** The strongest category an output supports. Common values: `planning`, `public_demo`, `public_synthetic_demo`, `computational_candidate`, `blocked`, `insufficient_support`.
- **Source posture.** Where a closeout's inputs came from. Common values: `public_data`, `synthetic_demo`, `generated_candidate`, `derived`, `provider_native`, `report_only`, `blocked`, `insufficient_support`.
- **Operator gate.** A human approval checkpoint required before a step proceeds. Common before paid compute, raw data download, or license-gated tools.
- **License gate.** A check that a tool's terms and use context are satisfied before installation or runtime.
- **Runtime gate.** A check that the runtime environment can actually execute a tool (weights present, dependencies installed, GPU available).
- **Fail-closed.** A stage that aborts the run if any check fails.
- **Input audit.** A scripted check that the inputs to a stage are public, accessible, and within posture.
- **Closeout.** The final artifact bundle of a campaign: manifests, artifacts, hashes, validation summary, source posture, and result boundary.
- **Partial closeout.** A closeout that marks missing or incomplete outputs honestly instead of calling them success.

## Compute And Providers

- **Provider profile.** A JSON describing a compute provider (RunPod, AWS Batch, neocloud, generic cloud VM, HPC, local) and its operator gates, license gates, budget, and cleanup requirements.
- **Execution profile.** The selected provider profile for a campaign or lane.
- **Network volume.** Persistent storage attached to a RunPod pod. Resolve its ID at runtime and keep the value out of public git.
- **Runtime secret.** A credential or token used at runtime. References use placeholders in public files; the real value lives in operator infrastructure.

## Ecosystem

- **BioSymphony.** The umbrella for biology agent harnesses.
- **CryoCore.** The BioSymphony subsystem that owns raw cryo-EM intake, EMPIAR processing, RELION or CryoSPARC reconstruction, and map-to-model build. Structure Factory hands off raw work to CryoCore and consumes its deposited structures downstream.
- **Symphony.** A multi-worker orchestration layer that dispatches agents against Linear issues.
- **`/goal` stack.** A user-facing goal orchestrator that translates a request into a sequence of agent steps.
- **`bsf`.** The Structure Factory command-line interface. Built into the agent skill workflow and usable directly by humans.
