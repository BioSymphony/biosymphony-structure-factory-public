# Use Cases

This guide gives users and their agents copyable prompts and concrete starting points for running real structural biology missions through Structure Factory. Use it when you want an agent to take a structural biology idea and produce a scaffolded campaign, multi-agent task plan, structure-mapping workflow, or provider-ready contract that other workers can finish.

Structure Factory helps a user and their agents plan, validate, package, run, and review computational structural biology work. Binding, activity, safety, efficacy, selectivity, and therapeutic value require wet-lab and clinical confirmation outside this repository.

For a route map across local prep, issue trackers, and cloud or provider execution, start with [`workflow-map.md`](workflow-map.md).
For a capability-by-capability map, use [`capabilities.md`](capabilities.md).

## Copyable Agent Prompts

## Capability Menu

| Capability | Ask For This | Start Here |
| --- | --- | --- |
| Binder design | target window, generation lanes, cofold triage, candidate ranking | [`examples/pd-l1-binder-design-public`](../examples/pd-l1-binder-design-public) |
| Binder toolchain comparison | study-shape replay, full-stack swaps, license policy, and mixed-backend handoffs | [`docs/binder-lane-round.md`](binder-lane-round.md) |
| Protein design lane | Genie/RFdiffusion-style generation plan plus Boltz/Chai-style triage | [`tools/`](../tools/) and [`docs/tooling-and-licensing.md`](tooling-and-licensing.md) |
| Model comparison | compare predicted/deposited models, preserve failures, rank candidates | [`tools/cofold-scoring-stack.md`](../tools/cofold-scoring-stack.md) |
| GPCR/state atlas | receptor/state work waves, prediction/render contracts, switch reports | Ask the skill to scaffold a state-atlas campaign |
| PDB/EMDB structure mapping | public accession provenance, validation plan, report outline | [`recipes/`](../recipes/) |
| Screening and active learning | fanout, shard ledgers, result schemas, candidate reports | [`examples/screening-superpowers`](../examples/screening-superpowers) |
| Cloud/GPU prep | provider profiles, tracked templates, runtime packets, preflight, and closeout checks | [`docs/compute-backends.md`](compute-backends.md) |
| Linear/Symphony handoff | tracker-neutral task plans with dependencies and validation commands | [`docs/linear-orchestration.md`](linear-orchestration.md) |

### Binder-Design Triage From A Public Interface

Use when you have a public structure and want a bounded campaign plan before generation or GPU work.

```text
Use the BioSymphony Structure Factory skill. Create a binder-design campaign scaffold from PDB 4ZQK. Define a target window, generation lanes, cofold/model-comparison lanes, expected artifacts, validation commands, and candidate ranking. Keep all outputs local and do not launch remote compute.
```

Suggested local commands:

```bash
bsf scaffold-campaign .runtime/pd-l1-binder-demo \
  --campaign-id pd-l1-binder-demo \
  --target-label "PD-L1 public interface demo" \
  --public-accession "PDB:4ZQK" \
  --window "public PD-1/PD-L1 interface window" \
  --mode binder-design
bsf validate .runtime/pd-l1-binder-demo
bsf audit .
```

Good output includes:

- `campaign-manifest.json` with input scope, lanes, and run posture
- target-window file with accession, chain/window, and uncertainty notes
- `stage-contract.json` with fail-closed stages and expected outputs
- run notes that separate completed work from future validation
- tracker-neutral tasks only after the scaffold is reviewed

### Anthropic Binder Study Replay And Toolchain Comparison

Use this lane with Claude Code, Codex, or another AI agent when you want to repeat or extend Anthropic's published binder-design study, compare alternative tools, or assign stages to local, API, platform-skill, self-hosted, or cloud execution. Read the [binder study decision loop](binder-study-decision-loop.md) before you plan a round.

```text
Use the binder-lane-round skill. Repeat or extend Anthropic's published binder-design study with a workflow-shape replay, an exact source-tool replay, or a deliberate tool-swap comparison. Declare the scientific constraints, license use context, tool gates, metric policy, and one route for every toolchain and stage. Materialize and preflight the handoff. Inspect the adapter registry, add runtime adapters for my selected tools, and request bounded approval before a paid provider start, non-public upload, terms acceptance, or large or license-gated download.
```

Use the [`binder-lane-round` skill](../skills/binder-lane-round/SKILL.md) for agent instructions, [`binder-lane-round.md`](binder-lane-round.md) for planning, adapter, and closeout commands, and [`binder-study-decision-loop.md`](binder-study-decision-loop.md) for round choices and stopping rules. Set `published_workflow` to `null` for `toolchain-comparison`, `single-arm-replay`, and `custom` templates.

### Public PDB/EMDB Structure Mapping

Use when you want a reviewable plan for a deposited public PDB/EMDB structure, map, or model.

```text
Use the Structure Factory skill. Turn this public PDB/EMDB accession into a structure-mapping plan. Include accession provenance, expected artifacts, figure/report outline, validation commands, stage contracts, and next-step checks. If raw cryo-EM processing or reconstruction is requested, produce a CryoCore handoff contract instead of treating that work as Structure Factory-owned. Do not download raw data or launch remote compute unless I explicitly authorize it later.
```

Start from:

- [`recipes/`](../recipes/)
- [`examples/empiar-10204-v0`](../examples/empiar-10204-v0)
- [`docs/agentic-biology-harness.md`](agentic-biology-harness.md)

Good output includes a compact public plan, not raw movies, reconstruction outputs, generated maps, private structures, or overconfident interpretation.

### GPCR Or Multimer State Atlas

Use when you want a receptor/state campaign split into prediction lanes, alignment/switch reports, render contracts, and per-state summaries.

```text
Use the Structure Factory skill. Plan a GPCR activation-state atlas from public PDB accessions. Split work by receptor and state, include Boltz/MPNN-style prediction lanes, render contracts, task dependencies, validation commands, and per-state summaries. Do not launch remote compute.
```

Start from:

- ask the skill to scaffold a state-atlas campaign
- [`tools/cofold-scoring-stack.md`](../tools/cofold-scoring-stack.md), [`tools/proteinmpnn.md`](../tools/proteinmpnn.md), [`tools/chimerax-peptide-viz.md`](../tools/chimerax-peptide-viz.md)
- [`docs/compute-backends.md`](compute-backends.md)
- [`docs/linear-orchestration.md`](linear-orchestration.md)

Good output is a wave plan and run contract. Keep runtime-specific predictions, renders, and generated structures out of tracked git files until they are summarized safely.

### Screening Fixture And Active Learning

Use when you want a local synthetic fixture that demonstrates sharding, result schemas, fanout estimates, and candidate triage without storing real screening results.

```text
Use the Structure Factory skill. Run the public screening-superpowers fixture locally, explain the fanout estimate, check the result schema, and summarize the readiness checks and human authorization needed before a real provider-backed screening run.
```

Suggested local commands:

```bash
make screening-fanout-estimate
make screening-fixture-run
make screening-results-check
make screening-schema-check
```

Start from:

- [`recipes/screening-superpowers-local-fixture.md`](../recipes/screening-superpowers-local-fixture.md)
- [`examples/screening-superpowers`](../examples/screening-superpowers)
- [`docs/screening-superpowers.md`](screening-superpowers.md)

Good output explains scale, schema shape, shard boundaries, and what remains synthetic or blocked.

### Provider Preparation And Authorized Start

Use when you want RunPod, cloud, SSH/HPC, or local GPU readiness while keeping live execution state out of tracked git files.

```text
Use the Structure Factory skill. Prepare a provider-neutral execution contract for this campaign. Keep the reusable template free of live provider IDs and secrets. Materialize an ignored runtime packet, add budget, cleanup, license, and authorization gates, and run the readiness checks. Request bounded approval before a paid provider start, non-public upload, terms acceptance, or large or license-gated download.
```

Suggested local commands:

```bash
make runpod-public-template-check
make runpod-scope-check
SMOKE_MANIFEST=runpod/launch-manifests/no-download-smoke.json make launch-preflight
make launch-bundle
make contract-self-check
```

Start from:

- [`recipes/runpod-no-download-smoke.md`](../recipes/runpod-no-download-smoke.md)
- [`docs/compute-backends.md`](compute-backends.md)
- [`docs/runpod-stack.md`](runpod-stack.md)
- [`runpod/README.md`](../runpod/README.md)

Good output is a reviewed contract and checklist. Write live provider packets and bindings under ignored `.runtime/` space. After readiness checks and explicit human authorization, execute through a validated adapter. Keep pod IDs, registry auth, approval records, logs, and fetched artifacts out of tracked git files.

### Linear Or GitHub Task Pack From A Campaign

Use when a campaign is too large for one agent turn and needs durable tasks, dependencies, and review gates.

```text
Use the Structure Factory skill. Turn this campaign into tracker-neutral tasks suitable for Linear or GitHub Issues. Include target/accession, provider profile, operator-gate status, run boundaries, owned paths, dependencies, validation commands, expected artifacts, risk notes, and a symphony:schema block. Do not include private tracker URLs, provider IDs, credentials, or runtime logs.
```

Suggested local commands:

```bash
bsf validate examples/pd-l1-binder-design-public
bsf issue-dry-run examples/pd-l1-binder-design-public --out .runtime/pd-l1-issues
python3 scripts/structure_factory/issue_check.py .runtime/pd-l1-issues --json
```

Start from:

- [`packs/README.md`](../packs/README.md)
- [`docs/linear-orchestration.md`](linear-orchestration.md)
- [`templates/github-issue.md`](../templates/github-issue.md)
- [`templates/linear-issue.md`](../templates/linear-issue.md)

Good output can be imported into Linear, GitHub Issues, Notion tasks, or another queue. Linear/Symphony users should preserve `sym:structure-factory`, wave labels, state policy, and parseable worker outcomes.

### Public-Release Review

Use when you want an agent to check whether a campaign, docs update, or repo export is fit for public release.

```text
Use the Structure Factory skill. Review this repo for public-release readiness and newcomer usefulness. Check README paths, docs, recipes, examples, task packs, diagrams, provider templates, privacy markers, generated artifacts, and release gates. Make local fixes where safe, then run make public-switch-check.
```

Suggested local commands:

```bash
make release-check
make public-switch-check
bsf audit .
```

Start from:

- [`PUBLIC_RELEASE.md`](../PUBLIC_RELEASE.md)
- [`docs/public-switch-checklist.md`](public-switch-checklist.md)
- [`docs/privacy-and-security-model.md`](privacy-and-security-model.md)

Good output names exactly what changed, what checks passed, and what remains intentionally local or blocked.

### Tool And Lane Review

Use when you want an agent to decide whether a tool belongs in the docs, local runtime setup, provider preparation, or an authorization-required execution lane.

```text
Use the Structure Factory skill. Review this proposed structure/design tool for documentation and execution readiness. Classify it as docs-only, optional local runtime, provider preparation, or authorization-required execution. Add license and use constraints, expected artifacts, validation commands, and result boundaries. If no bundled command exists, describe the missing readiness facts and the `.runtime/` adapter registry needed to run it.
```

Start from:

- [`tools/README.md`](../tools/README.md)
- [`docs/tooling-and-licensing.md`](tooling-and-licensing.md)
- [`references/software-registry.yaml`](../references/software-registry.yaml)

Good output separates public documentation from actual install or execution authorization.

## Choosing The Right Path

| Goal | Use This First | Main Gate |
| --- | --- | --- |
| Try the repo in five minutes | [`docs/quickstart-tour.md`](quickstart-tour.md) | `make harness-check` |
| Understand the whole workflow | [`docs/workflow-map.md`](workflow-map.md) | choose local, tracker, or cloud-prep mode |
| Ask an agent to plan a campaign | [`docs/agent-recipes.md`](agent-recipes.md) | `bsf validate` and `bsf audit .` |
| Install the portable skill | [`docs/skill-install.md`](skill-install.md) | `make harness-check` |
| Run a compact fixture | [`recipes/`](../recipes/) | recipe-specific checks |
| Split work into tasks | [`packs/README.md`](../packs/README.md) | `bsf issue-dry-run` |
| Prepare cloud/GPU work | [`docs/compute-backends.md`](compute-backends.md) | bounded human authorization before paid starts, non-public uploads, terms acceptance, or gated downloads |
| Publish or export | [`docs/public-switch-checklist.md`](public-switch-checklist.md) | `make public-switch-check` |

## Default Guardrails

When in doubt, ask the agent to keep these defaults:

- public or synthetic inputs only
- local prep before provider work
- bounded human authorization before paid starts, non-public uploads, terms acceptance, or gated downloads
- no credentials, provider IDs, private paths, raw datasets, generated structures, model weights, or logs in git
- result boundaries set before tool lanes are proposed
- partial, missing, or unverifiable outputs labeled honestly instead of called success
- every closeout includes files changed, validation commands, source posture, result boundary, and safety checks
