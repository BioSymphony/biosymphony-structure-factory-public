# BioSymphony Structure Factory Agent Guide

Use this repository to write and check structural biology campaign contracts, task packs, provider plans, and result records.

## Mission

Turn a target, accession, or screening request into files that another agent or scientist can inspect and continue.

The repo ships:

- portable agent instructions for any agent runtime
- campaign manifests, stage contracts, and provider profiles for RunPod, AWS, FAL, Modal, Lambda, neocloud, HPC, and local
- target-window files, generation, cofold, scoring, render, and screening lanes
- tracker-neutral task packs for Linear, GitHub Issues, Notion, or another queue
- validators, audit gates, capability catalog, and a dependency-free `bsf` CLI

Ownership boundary: raw cryo-EM movie intake, EMPIAR subset execution, RELION or CryoSPARC reconstruction, and map-to-model build execution belong to BioSymphony CryoCore. This repo keeps public metadata, handoff gates, downstream structure-mapping contracts, validation plans, and reviewable summaries.

## How To Drive A Mission

When the orchestrator hands you work, the loop is:

```text
goal
  -> bsf catalog .                              # what is available
  -> bsf scaffold-campaign <runtime>/<id> ...   # target, lanes, run boundaries
  -> bsf validate <runtime>/<id>                # campaign and stage contract sound
  -> bsf issue-dry-run                          # split into tracker work
  -> orchestrate workers or launch provider     # Symphony, Linear, Codex, others
  -> verify artifacts and sign closeout
```

Use multiple workers only when the task pack assigns separate paths, dependencies, validation commands, and outcomes.

## Provider Contract Coverage

- **Local:** a workstation profile for planning and fixtures.
- **RunPod:** pod profiles and public launch-contract templates.
- **AWS:** Batch and EC2 GPU profiles.
- **FAL:** a serverless GPU-job profile.
- **Modal:** a serverless GPU-function profile.
- **Lambda Cloud:** an ephemeral GPU-VM profile.
- **Neocloud and generic cloud:** GPU pod or VM profiles.
- **SSH or HPC:** a Slurm-oriented profile.

Each profile records operator, license, budget, cleanup, and closeout requirements. A profile does not prove account access or runtime readiness. Closeout requires artifacts, hashes, and validation notes.

## Orchestrators Supported

Use `skills/biosymphony-structure-factory/SKILL.md` with an agent that can read Markdown and call the local CLI. `docs/linear-orchestration.md` defines the Symphony with Linear task shape.

## Tool Records And Lane Contracts

- Design records: Genie3, RFdiffusion, HelixDiff, PepGLAD, EvoBind, ProteinMPNN, and the Baker miniprotein-GPCR recipe.
- Multistate design record: SwitchCraft.
- Construct-assembly record: DOMINO, with an unresolved upstream license noted in the tool card.
- Prediction and scoring records: Boltz, Chai, ESMFold2, and the cofold-scoring contract.
- Refinement and rendering records: ChimeraX, PyMOL, MD, and docking cards.
- Local checked paths: campaign scaffolding, public fixtures, validation, catalog generation, and provider-packet dry runs.

The presence of a tool card does not prove installation, provider service, or a successful biological result. Read [`references/software-registry.yaml`](references/software-registry.yaml), then verify runtime status before use.

## Public Safety Rules

Use public accessions, synthetic rows, or compact fixtures. Label source posture clearly. Do not add:

- private structures, maps, unpublished sequences, or patient data
- raw cryo-EM movies, half-maps, heavy databases, checkpoints, or model weights
- provider credentials, tokens, registry auth, signed URLs, or one-time transfer codes
- concrete private pod IDs, network volume IDs, account IDs, billing records, or raw provider logs
- private Linear issue text, internal run notes, or private workstation paths
- wet-lab synthesis instructions, dosing guidance, therapeutic conclusions, or clinical advice

## Agent Entry Points

- Read `PUBLIC_RELEASE.md` before release, publication, or handoff work.
- Read `docs/agentic-biology-harness.md` to understand the public BioSymphony or Symphony operating model.
- Use `skills/biosymphony-structure-factory/SKILL.md` as the portable agent-instruction entry point.
- Use `packs/task-packs/binder-design-fast-path-v0/` when a tracker-neutral task import is needed.
- Use `templates/operator-wave-runbook.md` before promoting paid, cloud, raw-download, or multi-agent waves.
- Treat `runpod/` as the repository's most detailed cloud contract. Other provider profiles must meet the same artifact and cleanup requirements.

## Key Patterns

- Treat task packs as campaign contracts, not generic todos.
- Keep every generated or predicted output attached to a clear result boundary.
- Use the public result states in manifests and closeouts: `planning`, `public_demo`, `public_synthetic_demo`, `computational_candidate`, `blocked`, or `insufficient_support`.
- Track source posture separately from result boundary. Source posture may describe where outputs came from, such as `public_data`, `synthetic_demo`, `generated_candidate`, `derived`, `provider_native`, `report_only`, `blocked`, or `insufficient_support`.
- Closeout requires stage events, expected artifacts, hashes, and validation notes.
- Public examples are for structure and workflow shape, not unreviewed wet-lab action.

## Common Checks

```bash
make harness-check
make release-check
make public-audit
make secret-scan
```

`make secret-scan` uses gitleaks when installed. If the target reports a skip, the release gate remains incomplete.

## Before A Paid Dispatch

Read [`docs/operational-gotchas.md`](docs/operational-gotchas.md) and [`docs/preflight-checklist.md`](docs/preflight-checklist.md) before a paid dispatch. They record preflight probes, output checks, operator approval, artifact requirements, and cleanup checks.

For **output-count validation** (G8 / class #34), a worker counts the expected outputs before it records a completed stage. Process exit alone does not satisfy the stage contract.

## Result Boundaries

This repo produces planning scaffolds, computational candidate rankings, and validation-roadmap artifacts. Binding, function, therapeutic value, safety, manufacturability, and clinical relevance are confirmed through wet-lab and clinical processes outside this repo. See [`NON_CLAIMS.md`](NON_CLAIMS.md) for the full boundary.
