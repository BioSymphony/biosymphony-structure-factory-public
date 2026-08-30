# Capabilities

Structure Factory helps you and your AI agent turn a public accession or synthetic fixture plus a structured site into concrete lanes for binder design, protein modeling, structure mapping, screening, rendering, and execution.

Start with the [copyable campaign brief](../README.md#copyable-campaign-brief): choose the target and site, study mode, tools and routes, budget, rounds, primary metric, stopping rule, and closeout outputs. The repo supplies reusable scaffolds, fixtures, provider contracts, and report shapes. Your runtime holds any live credentials, paid execution, generated structures, accepted-license state, and private data.

Raw cryo-EM movie intake, EMPIAR subset execution, RELION or CryoSPARC reconstruction, and map-to-model build execution belong to BioSymphony CryoCore. Structure Factory owns the handoff, downstream structure-mapping workflow, design lanes, validation checks, and report/figure packaging.

## What You Can Build

| Capability | What It Does | Public Repo Support | Private/Runtime Adds |
| --- | --- | --- | --- |
| Binder-design campaign | Defines target window, hotspots, generation lanes, cofold triage, and candidate ranking | `examples/pd-l1-binder-design-public`, `recipes/pd-l1-binder-design-fast-path.md`, `bsf scaffold-campaign --mode binder-design` | generated structures, model weights, provider artifacts, experimental follow-up |
| Binder toolchain comparison | Holds target, controls, prediction panel, scoring, and failure policy fixed while comparing source-tool replay and deliberate tool-swap arms | `bsf binder-lane` target verification, local adapter and controller checks, remote-contract validation, control calibration, closeout, and round decision | credentials, installed tools and weights, provider resources, generated candidates |
| Protein design lane | Plans Genie/RFdiffusion-style generation and Boltz/Chai-style cofold checks | tool cards, stage contracts, task fields, provider templates | reviewed installs, weights, GPU execution, generated candidate packets |
| Cofold/model comparison | Compares candidate models with confidence summaries and failure rows | model-output schemas, task drafts, validation guide | real prediction outputs and derived comparison reports |
| GPCR or multimer state atlas | Splits receptor/state work into prediction lanes, alignment, switch reports, and renders | scaffold mode, tool cards (cofold-scoring-stack, chimerax, proteinmpnn) | provider-backed Boltz/MPNN/ChimeraX outputs and figure packets |
| PDB/EMDB structure mapping | Builds accession provenance, validation plan, figure outline, and map/model workflow | `recipes/`, structure-mapping scaffold mode | fetched deposited maps/models, validation outputs, figure renders |
| CryoCore handoff contract | Captures raw-data accession, raw/subset gate, expected artifacts, operator approval, and ownership boundary | `examples/empiar-10204-v0`, input-audit checks, metadata-only stage contracts | CryoCore-owned raw downloads, reconstruction artifacts, provider storage, map/model build outputs |
| Screening and active learning | Demonstrates ligand/receptor fixtures, fanout estimates, result schemas, candidate reports, and cloud shard ledgers | `examples/screening-superpowers`, `make screening-check`, provider adapter dry-run | real libraries, real docking/cofolding, paid cloud fanout |
| Platform skills and user-supplied adapters | Lets an agent invoke an installed platform skill or validates a literal local/API/cloud/scheduler/container command with typed bindings and declared outputs | stage handoffs, adapter contracts, `bsf binder-lane adapters`, `prepare-execution`, and `closeout` | installed skill or client, runtime bindings, credentials, and service access |
| Cloud/GPU execution prep | Defines local, API, FAL, Modal, RunPod, Lambda Cloud, AWS, neocloud, and SSH/HPC route contracts, launch preflight, and closeout requirements | `docs/compute-backends.md`, `runpod/`, `make runpod-public-template-check`, `make launch-bundle` | actual pod/job creation, secrets, runtime logs, artifact pulls, cleanup proof |
| Linear/Symphony task plans | Converts campaigns into durable agent tasks with owned paths, dependencies, validation commands, and outcome schema | `bsf issue-dry-run`, `packs/`, `docs/linear-orchestration.md` | live tracker state, private comments, operator approval records |
| Report and figure packaging | Produces report and visual-review shapes with provenance, hashes, artifact indexes, and review rules | templates, render contracts, release checks | source artifact archives, hash ledgers, cost reports, cleanup records |

## Choose A Route For Each Stage

You can mix these routes in one campaign:

| Route | What You Provide | What The Campaign Records |
| --- | --- | --- |
| Local/self-hosted | installed program and, when needed, a validated adapter registry | typed bindings, expected outputs, dry-run result, receipt, counts, and hashes |
| Platform skill | a skill your agent can invoke | target, data, budget, runtime, stage root, declared outputs, and closeout record |
| Hosted API | a user-selected client and any required runtime credential configuration | request/receipt boundary, output contract, spend and runtime limits |
| FAL, Modal, RunPod, Lambda Cloud, AWS, neocloud, or SSH/HPC | selected provider or scheduler client | provider profile, artifact and cleanup contract, and closeout requirements |
| Mixed | one of the preceding routes for each stage | the route, handoff, and receipt for every stage |

When a selected registry record says `adapter_required`, add a validated adapter registry below `.runtime/`. A platform-skill invocation uses the declared stage output contract and `bsf binder-lane closeout`; it does not need an adapter record for the skill invocation.

## Fast Starts

### Binder Design

```bash
bsf scaffold-campaign .runtime/pd-l1-binder-demo \
  --campaign-id pd-l1-binder-demo \
  --target-label "PD-L1 public interface demo" \
  --public-accession "PDB:4ZQK" \
  --window "public PD-1/PD-L1 interface window" \
  --mode binder-design
bsf validate .runtime/pd-l1-binder-demo
```

Agent prompt:

```text
Use the BioSymphony Structure Factory skill. Build a binder-design campaign for public PDB 4ZQK with a bounded interface site, design lanes, cofold checks, task drafts, and candidate ranking. Set the budget, runtime, primary metric, and stopping rule. Verify the coordinate target before generation. Inspect and dry-run the selected local adapters, platform skill, or controller request. Before a real provider start, present the named route, data posture, budget, runtime, terms, expected outputs, receipts, and cleanup action for approval.
```

For a multi-arm comparison with exact source-tool replay, workflow-shape replay, deliberate tool swaps, or an independent comparison, follow [`binder-lane-round.md`](binder-lane-round.md) and [`binder-study-decision-loop.md`](binder-study-decision-loop.md). The planner records tool and license choices, per-stage routes, output counts, handoff hashes, receipts, and the round decision. `target-check` verifies the input against the exact plan target and site. `execute` runs a local controller request after a dry run, and the remote contract uses `remote-request` and `remote-receipt`.

### Structure Mapping

```bash
bsf scaffold-campaign .runtime/map-model-demo \
  --campaign-id map-model-demo \
  --target-label "Public PDB/EMDB structure mapping demo" \
  --public-accession "PDB:4ZQK" \
  --window "deposited public structure window" \
  --mode structure-mapping
bsf validate .runtime/map-model-demo
```

Agent prompt:

```text
Use the Structure Factory skill. Turn this public PDB/EMDB accession into a structure-mapping plan with provenance, validation commands, expected artifacts, and figure outline. If the request involves raw cryo-EM processing or reconstruction, create a CryoCore handoff instead of treating that lane as Structure Factory-owned.
```

### Screening Fixture

```bash
make screening-fanout-estimate
make screening-fixture-run
make screening-results-check
```

Agent prompt:

```text
Use the Structure Factory skill. Run the screening-superpowers fixture locally, summarize the fanout and result schemas, then explain what would be required before a real cloud-backed screening run.
```

### Cloud Prep

```bash
make runpod-public-template-check
make runpod-scope-check
SMOKE_MANIFEST=runpod/launch-manifests/no-download-smoke.json make launch-preflight
make launch-bundle
```

Agent prompt:

```text
Use the Structure Factory skill. Prepare a provider-neutral GPU execution contract with budget, cleanup, runtime-secret references, expected artifacts, and closeout checks. Leave dispatch pending until the required approval is recorded.
```

## Run Results

A closeout records the route, what ran, expected and actual artifacts, output counts, hashes, validation status, receipts, cleanup result, and visual-review outputs when selected. Generated or predicted biological outputs remain computational candidates until downstream validation lands.

Store provider artifacts, hashes, raw execution records, cost reports, cleanup proof, and run summaries under ignored `.runtime/` storage or in a user-selected artifact store.

## Operational Checks

The repository ships operational checks ([`operational-gotchas.md`](operational-gotchas.md)) and a pre-dispatch checklist ([`preflight-checklist.md`](preflight-checklist.md)). They cover provider payload limits, environment errors, tool-specific input and output constraints, and stage completion with empty outputs.

Read both before any paid GPU dispatch. Every worker must validate the declared output count before it records `STAGE_COMPLETE`; process exit code alone is insufficient. See [`no-false-success-hardening.md`](no-false-success-hardening.md) for the full closeout rule.
