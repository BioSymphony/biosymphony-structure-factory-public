# Binder Lane Round

A binder-lane round records one target, one comparison protocol, one or more toolchain arms, a control set, scientific constraints, execution routes, and a closeout contract. The CLI plans comparisons, verifies target inputs, checks local and remote execution contracts, and validates stage outputs before it records completion.

The round can use the pinned public workflow reference in [`../references/published-binder-comparison-workflow.json`](../references/published-binder-comparison-workflow.json). The repository includes workflow metadata only; published sequences, structures, measurements, rankings, and result values remain in their source release.

You and your agent choose the target and site, bounded stages, tool identities, execution route, use constraints, spend ceiling, round count, primary metric, and stopping rule. The request can check published tool identities, preserve only the workflow stages, replace selected tools, or compare replay and replacement arms under shared metrics.

## What The Lane Does

- lists binder-design tools by role, public evidence level, and license gate
- lists public local, cloud, neocloud, and operator-API profiles
- validates multiple toolchain arms under one target and scoring protocol
- records the objective, target-selection method, binder-length bounds, controls, inclusion and exclusion rules, failure-row policy, time cap, and spend cap
- declares one local, API, neocloud, RunPod, AWS, FAL, Modal, Lambda, cloud VM, or SSH/HPC route for each toolchain and stage
- hash-binds the plan to its request, capability ledger, workflow reference, synthetic fixture, provider profiles, and API adapter contract
- writes per-toolchain output-count contracts and preserves failed rows
- creates a synthetic JSON report without network, subprocess, provider, or external-tool calls
- validates bundled or user-supplied adapter registries
- runs fixed argument arrays with `shell=False`, a bounded environment, a timeout, and explicit authorization
- counts, parses, and hashes declared outputs before a real adapter reports success
- writes sanitized execution and stage receipts below `.runtime/`

`plan` writes a handoff packet. It does not start a process or provider job.

`run` reads the shipped synthetic fixture. It makes no tool-performance or biological claim.

`adapter` runs one reviewed local program. That program can be a local scientific tool or a user-selected client for an API, cloud job, scheduler, or container runtime.

`execute` reads a user-supplied controller request and runs a hash-bound local stage graph. It does not create a controller request.

`prepare-execution` maps an exact plan and target-verification report to runnable adapter IDs. It writes a controller request only when every selected tool stage has a matching adapter and complete typed bindings.

`remote-request` and `remote-receipt` enforce a provider-neutral boundary for remote stages. They validate the handoff and closeout records but do not contact a provider.

## Quick Start

Run from the repository root:

```bash
bsf binder-lane menu --workspace .

bsf binder-lane plan-request \
  examples/pd-l1-binder-design-public/binder-round-request.json \
  --workspace . \
  --ledger references/binder-lane-capability-ledger.json \
  --out .runtime/pd-l1-binder-round/plan.json

bsf binder-lane plan \
  .runtime/pd-l1-binder-round/plan.json \
  --workspace . \
  --out .runtime/pd-l1-binder-round/run

bsf binder-lane preflight --workspace . .runtime/pd-l1-binder-round/run
bsf binder-lane run --workspace . .runtime/pd-l1-binder-round/run
bsf binder-lane report --workspace . .runtime/pd-l1-binder-round/run

bsf binder-lane round-decision \
  .runtime/pd-l1-binder-round/plan.json \
  --workspace . \
  --history .runtime/pd-l1-binder-round/round-history.json \
  --out .runtime/pd-l1-binder-round/round-decision.json

bsf binder-lane adapters --workspace .
bsf binder-lane adapter boltz-local-v1 \
  --workspace . \
  --run-root .runtime/pd-l1-binder-round/boltz \
  --operation readiness \
  --dry-run
```

The example contains three arms and declares a mixed route:

- generation and sequence-design handoffs use the public neocloud profile
- cofold handoffs use the public operator-API adapter contract
- scoring, filtering, and reporting handoffs use the local profile

The synthetic run checks the toolchain, route, count, hash, and report contracts represented by the handoff. Use `adapter` for one local stage or `execute` for a checked local stage graph.

## Prepare A Controller Request

Run `target-check` before `prepare-execution`. Then write a stage-settings JSON object below `.runtime/`. Each key has the form `<toolchain>.<stage>.<tool>` or, for a variant, `<toolchain>.<stage>.<tool>@<variant>`. Its value can select an adapter and must supply that adapter's run bindings. The value can also record a non-negative cost estimate and a positive timeout.

```json
{
  "diffusion-mpnn.filter.status-preserving-filter": {
    "bindings": {
      "run_root": ".",
      "input_path": "inputs/candidates.jsonl",
      "output_path": "outputs/status.jsonl",
      "metric": "metrics.cofold_confidence_proxy",
      "minimum": 0,
      "maximum": 1
    },
    "estimated_cost_usd": 0,
    "timeout_seconds": 300
  }
}
```

When a later adapter consumes an earlier adapter's file or directory bundle, add `input_handoffs` to the later selector. Each handoff names an earlier runnable `source_selector`, one `source_output_id`, and the downstream path placeholder as `destination_binding`. The selected output contract determines whether the source is a file or directory.

The controller accepts exactly one matched artifact for each handoff. For a file, it verifies the same-run source receipt, hash, size, and record count before it copies the file. For a directory, the adapter receipt lists every member's relative path, hash, byte count, and record count. The controller verifies the complete member list and aggregate hash, copies the members to a temporary directory, and promotes the complete bundle to the downstream stage root. It rejects symbolic links, path escapes, overlapping handoff destinations, and existing destination paths. A handoff does not infer member names or expose absolute paths in the controller receipt.

Prepare all plan stages or select an ordered subset:

```bash
bsf binder-lane prepare-execution \
  .runtime/pd-l1-binder-round/plan.json \
  --workspace . \
  --target-report .runtime/pd-l1-binder-round/target/verification.json \
  --registry references/binder-execution-adapters.json \
  --stage-settings .runtime/pd-l1-binder-round/stage-settings.json \
  --stages filter \
  --out .runtime/pd-l1-binder-round/controller-request.json \
  --readiness-out .runtime/pd-l1-binder-round/execution-readiness.json
```

The command checks the report's plan hash, normalized target contract, and target-contract digest before it writes a controller request. Each controller stage records the toolchain, plan stage, tool and variant, route, backend, execution method, adapter ID, dependencies, typed bindings, cost estimate, and timeout. The request also preserves replay and replacement arm assignments, the round index, the primary metric, the stage subset, and the round budget.

If a selected stage lacks a runnable adapter or complete bindings, the command returns `planning_with_readiness_gaps`, exits successfully, and omits the controller request. Each gap names the selector, route, reason, and next actions. A provider profile or tool card never counts as a runnable adapter. For a remote route, select a validated local client adapter explicitly. For a platform-skill route, let the user's agent run the skill and close the declared outputs with `bsf binder-lane closeout`.

## Run Tools Through Adapters

The shipped registry is [`../references/binder-execution-adapters.json`](../references/binder-execution-adapters.json). The Boltz, ESMFold2 full, ESMFold2 Fast, supplied-backbone, status-filter, and diversity-filter records contain complete fixed-argument commands. Other records describe stable inputs and outputs even when this repository does not bundle a command for that installation.

`adapter_required` means that the repository has no bundled command for that installation. Supply a validated registry below `.runtime/` for an installed program, API client, cloud client, scheduler, or container entry point, or select a platform-skill route. Each adapter declares the supported tool and variant identities plus backend and execution-method pairs. A runnable record also declares a literal program, typed placeholders, argument arrays, environment-variable names, network policy, expected outputs, and public evidence. Keep credential values, service addresses, and private resource identifiers in runtime state.

Use an ignored project-local directory such as `.runtime/tools/<tool-id>` for a reusable local installation. Point the adapter's declared environment variables to that directory. Do not use `/tmp` as the tool root for a reusable installation.

Run a local adapter in three steps:

1. Write its bindings as a JSON object below `.runtime/`. Path bindings resolve below the adapter run root.
2. Dry-run the adapter to validate its registry, bindings, program lookup, environment-variable names, output contract, and receipt path.
3. Add `--authorize-local-execution` to start the program. The executor writes process output to a local `.runtime/` log, passes no shell, and records no argument or environment values in the receipt.

For `boltz-local-v1`, the bindings file has this shape:

```json
{
  "input_path": "inputs/complex.yaml",
  "output_dir": "outputs"
}
```

```bash
bsf binder-lane adapter boltz-local-v1 \
  --workspace . \
  --registry references/binder-execution-adapters.json \
  --run-root .runtime/pd-l1-binder-round/boltz \
  --bindings .runtime/pd-l1-binder-round/boltz/bindings.json \
  --dry-run

bsf binder-lane adapter boltz-local-v1 \
  --workspace . \
  --registry references/binder-execution-adapters.json \
  --run-root .runtime/pd-l1-binder-round/boltz \
  --bindings .runtime/pd-l1-binder-round/boltz/bindings.json \
  --authorize-local-execution
```

### Run A Local Stage Graph

`execute` uses a controller request that you create below `.runtime/`. The request binds an ordered set of local adapters to the plan SHA-256, a successful target-verification report, a USD ceiling, stage dependencies, and typed bindings. `plan` does not generate that request.

Dry-run the controller before a process starts:

```bash
bsf binder-lane execute .runtime/pd-l1-binder-round/controller-request.json \
  --workspace . \
  --plan .runtime/pd-l1-binder-round/plan.json \
  --run-root .runtime/pd-l1-binder-round/execution \
  --dry-run
```

For a real local run, add `--authorize-local-execution`. Add `--authorize-network` only when a selected adapter requires network review. Add `--authorize-license-gates` only after the selected use passes terms review. The controller stops dependent stages after a readiness or output-contract failure and writes a sanitized receipt.

For an API or cloud route, use a user-selected client as the literal program, declare its matching `supported_routes` pair, and set `network_policy` to `runtime_review_required`. A missing program or environment-variable name is a readiness result. Configure the selected route, then rerun the dry run.

For a platform-skill route, the user's agent runs the selected skill under the handoff's tool, data, budget, and runtime bounds. The skill writes the declared outputs below the stage run root. Close the stage with the same `bsf binder-lane closeout` declaration used for local and provider-backed stages; no adapter record is required for the skill invocation.

### Bundled ESMFold2 Predictor

Installing this package exposes `bsf-esmfold2-predict`. The full and Fast registry records call the same wrapper with different pinned model identities. Each record prohibits network access and reads cached snapshots only.

The wrapper's presence makes the fixed-argument contract ready. It does not prove that the optional model runtime is ready. The `readiness` operation checks these runtime requirements without loading a model or sending a network request:

- the pinned Biohub `esm` package, `torch`, `transformers`, and `huggingface_hub`
- a CUDA device visible to `torch`
- the selected ESMFold2 snapshot and the pinned ESMC-6B snapshot under `HF_HOME`
- a reviewed cached `ccd.pkl` file named by `ESMFOLD2_CCD_PATH`

The bundled local records need no provider account or API token. To permit a weight download, create a reviewed runtime registry that adds `--allow-weight-download` and sets `network_policy` to `runtime_review_required`.

The input is JSONL with one row per candidate. Every row has a unique `candidate_id` and `status`. An eligible row also has at least two protein chains:

```json
{
  "candidate_id": "candidate-001",
  "status": "eligible",
  "chains": [
    {"chain_id": "A", "type": "protein", "sequence": "ACDE"},
    {"chain_id": "B", "type": "protein", "sequence": "FGHI"}
  ]
}
```

Use these bindings below the adapter run root:

```json
{
  "run_root": ".",
  "input_path": "inputs/candidates.jsonl",
  "output_path": "outputs/predictions.jsonl",
  "artifact_dir": "outputs/predictions",
  "seed": 0,
  "expected_count": 1
}
```

The wrapper writes one output row for every input row in the same order. It preserves upstream failures and filtered rows as `not_evaluable`. A successful row records hashes for the mmCIF structure, compressed PAE/pLDDT sidecar, and confidence summary. The wrapper fails the run when its output count differs from `expected_count`, every eligible prediction fails, a confidence array has the wrong shape, or an artifact hash cannot be recorded.

### Bundled Supplied-Backbone Adapter

Installing this package also exposes `bsf-supplied-backbone`. This dependency-free adapter runs no design model. It verifies the recorded hash of each user-supplied PDB file, copies one polymer chain into an adapter-owned pose, and labels the output as `supplied_structure`.

An eligible input row carries a run-root-relative `structure_path` and its lowercase SHA-256 digest. Use these bindings:

```json
{
  "run_root": ".",
  "input_path": "inputs/backbones.jsonl",
  "output_path": "outputs/backbones.jsonl",
  "pose_dir": "outputs/poses",
  "source_chain": "A",
  "binder_chain": "B",
  "minimum_length": 40,
  "maximum_length": 200,
  "expected_count": 1
}
```

The adapter reads only the first PDB model, excludes HETATM records, preserves insertion-code residue identities in its length count, and records the source and pose hashes. It preserves failed and filtered upstream rows. A copied pose is workflow input for a later sequence designer; it is not a generated backbone or a biological result.

### Bundled Candidate Filters

Installing this package exposes `bsf-status-filter` and `bsf-diversity-filter`. Their registry records run them through the same fixed-argument executor as any other local tool.

The status filter reads JSONL rows with unique `candidate_id` and `status` fields, applies numeric bounds to a selected dotted metric field, and appends a `filter_results` record. A failed upstream row becomes `not_evaluable`; it is never deleted. The diversity filter considers only rows that remain eligible, walks them in stable input order, and appends a pass/filter result based on normalized edit similarity to previously retained sequences. It also preserves failed and filtered rows. The similarity is a deterministic workflow filter, not a biological novelty claim.

Use bindings below the adapter run root:

```json
{
  "run_root": ".",
  "input_path": "inputs/candidates.jsonl",
  "output_path": "outputs/status-filtered.jsonl",
  "metric": "metrics.ipsae_min",
  "minimum": 0.3,
  "maximum": 1.0
}
```

For `diversity-filter-v1`, use `run_root`, `input_path`, `output_path`, `sequence_field`, and `maximum_similarity`. Candidate sequences remain below `.runtime/`; execution receipts contain output paths, row counts, byte counts, and hashes, not sequence values.

## Run A Remote Tool Through A Fixed Contract

A user-selected platform skill, hosted API client, or self-hosted provider client can consume the same provider-neutral request. The request names a registered tool operation, provider class, artifact namespace, source/model/environment identities, credential environment-variable names, and hard spend and runtime ceilings. It excludes shell commands, argument arrays, executable code, credential values, signed URLs, and controller-local paths.

Validate a request before dispatch:

```bash
bsf binder-lane remote-request \
  .runtime/pd-l1-binder-round/cofold/request.json \
  --workspace . \
  --out .runtime/pd-l1-binder-round/cofold/validated-request.json
```

The client returns a sanitized receipt after artifact export and cleanup. Validate its exact identity join, artifact hashes, byte counts, and cleanup state:

```bash
bsf binder-lane remote-receipt \
  .runtime/pd-l1-binder-round/cofold/receipt.json \
  --request .runtime/pd-l1-binder-round/cofold/validated-request.json \
  --workspace . \
  --out .runtime/pd-l1-binder-round/cofold/validated-receipt.json
```

### Dispatch A Request Through A User-Supplied Adapter

The `biosymphony_structure_factory.remote_dispatch.dispatch_remote_tool` Python API connects the fixed contract to a provider client. It is not a `bsf binder-lane dispatch` command. The function validates the request, resolves the route, and calls one adapter callable that you supply. It does not build a shell command, spawn a process, or write a credential value.

The adapter receives the validated request and a runtime context with the attempt directory, budget, route, and declared credential keys. It returns status, artifact hashes and byte counts, reported spend, and cleanup status. The dispatcher verifies each artifact below the attempt directory, recomputes its SHA-256, enforces spend and runtime ceilings, and writes `remote-tool-receipt.json` joined to the request.

The route identity is fixed per provider class: `workstation` for `local`, `hosted_api` for `api`, `serverless_gpu` for `fal` and `modal`, `serverless_gpu` or `gpu_pod` for `runpod`, `ephemeral_gpu_vm` for `lambda`, `batch` or `ec2` for `aws`, `gpu_vm` for `cloud_vm`, `gpu_pod` or `gpu_vm` for `neocloud`, and `slurm` for `ssh_hpc`. A route name records the dispatch path only; it is not evidence of account access or live provider readiness.

Missing credential keys or an adapter are readiness states. The dispatcher returns a `blocked` outcome and invokes nothing. A real dispatch requires `authorization="authorize_remote_dispatch"`; without it the dispatcher raises before an adapter call. `dry_run=True` returns a `planned` outcome with the same readiness checks and no adapter call.

The built-in operation registry covers the common binder stack. To use another reviewed tool, pass `--operations` with a JSON object below the workspace that maps tool IDs to allowed operation names, for example `{ "selected-tool": ["toolcheck", "predict"] }`. This extends tool selection without weakening the fixed request shape. Provider-specific authentication, endpoints, resource identifiers, and transport code remain in the user's runtime environment.

## Verify The Target Before Generation

Declare `target.site.chain_id` and `target.site.required_residues` in the round request. Each residue entry is a number, an inclusive range, or a numbered residue with an insertion code. Separate entries support noncontiguous sites.

Run `target-check` on the exact coordinate file that the generation stage will read. The command reads the chain and required residues from the plan, inspects the first PDB or mmCIF model, and can compare the modeled coordinate sequence or deposited entity sequence with a one-letter sequence file.

```bash
bsf binder-lane target-check \
  .runtime/pd-l1-binder-round/target/target.cif \
  --workspace . \
  --plan .runtime/pd-l1-binder-round/plan.json \
  --expected-sequence-file .runtime/pd-l1-binder-round/target/expected-sequence.txt \
  --sequence-basis entity \
  --out .runtime/pd-l1-binder-round/target/verification.json
```

The report records the plan hash, normalized target contract and digest, structure hash, chain, residue counts, covered span, sequence basis, sequence length, and sequence hash. It contains no sequence payload or absolute path. `prepare-execution` rejects a report from another plan, accession, window, chain, or residue selection. Pass the report's `structure_sha256` into the source identity of any remote request so the target check and provider receipt join to the same input.

## Read Command Failures

Binder-lane command failures keep the concise `error` string and also return a structured `failure` record. The record has a stable check ID, category, summary, and two or more `next_actions`. The actions cover target correction, runtime preparation, route changes, bounded authorization, budget reduction, calibration, and artifact recovery as applicable. They do not contain input values, commands, credentials, provider identities, or absolute paths. An agent can present the viable actions; make a runtime change only after you authorize it.

## Study Contract

### Target

Public requests use an accession, bounded window, chain ID, and required residue selections. Target coordinate files and generated structures stay outside public Git. The public request schema does not accept target paths or sequence payloads.

### Toolchain Arms

Each arm names:

- one generator
- one sequence designer
- one or more predictors
- one or more scorers
- one or more filters
- a candidate count

Use `controlled_generation` to hold candidate counts, predictor panels, scorers, and filters constant while the generation and sequence-design toolchain varies. Use `exploratory_full_stack` to swap any declared tool role. Exploratory full-stack rounds set `cross_arm_ranking: not_permitted` because their metrics can be incompatible. Use `single-arm-replay` when the request has one arm.

For a source-tool replay, set `reference_scope: published_tool_identities` and select generator, sequence-designer, predictor variant, and scorer identities from `published_tool_cohort` in the pinned reference. Tool variants use `{ "tool_id": "...", "variant_id": "..." }` records. The validator checks each replay arm against the published identities on the declared bounded stages. A swap arm must differ on at least one bounded stage.

For a workflow-shape replay, set `reference_scope: published_workflow_shape`. This scope preserves the published stage and comparison structure without claiming the source-tool identities.

The comparison policy declares each metric's direction, unit, missing-value policy, and deterministic tie break. The synthetic fixture carries illustrative values only.

The capability ledger distinguishes three evidence levels:

- `listed`: the public software registry names the tool
- `documented`: a public tool card or workflow document describes it
- `contract_checked`: a public local contract or toolcheck module exists

These evidence levels describe the public documentation. `execution_available` records whether the repository contains a validated adapter contract, and `runtime_status` records the local check.

### Controls And Constraints

The request records a binder-length range, required controls, top rows per arm, and a required failure-row policy. A failed or missing row remains in the report. A provider success state or process exit code cannot replace output-count validation.

The public comparison fixture uses constructed proxy values. Do not interpret their ordering as a tool benchmark.

Use [`binder-controls.md`](binder-controls.md) to construct a predictor/control/seed index, derive or adopt metric gates, and bind the resulting artifact to round-decision provenance. A missing optional control produces an optional gap unless the selected metric marks it as required.

### License Policy

The request can allow or block tool gates and records the intended use context. It also tracks review requirements for code, weights, dependencies, API terms, and redistribution.

An allowed gate records planning intent. Every materialized plan records `review_status: not_recorded`; license acceptance, approver identity, account access, and private review notes stay outside public artifacts.

### Execution Topology

Every `(toolchain, stage)` pair has exactly one route. A route names a stable ID, backend, public provider profile or API adapter contract, and whether execution requires approval. The planner rejects backend/profile mismatches and a topology that does not match the routes.

API routes additionally require terms, input-retention, and runtime-secret review. The public API contract contains no service address, account identifier, credential, or launch instruction.

You choose tools, licenses, installation methods, compute providers, data routes, and authorization bounds. Before a real start, approve the named route, data posture, budget, runtime, and any paid launch, non-public upload, terms acceptance, or gated download. The executor records the selected license gate and network policy; it does not accept terms or change those bounds.

## Handoff And Closeout

`plan` writes three files below `.runtime/`:

- `plan.json`: the frozen comparison and routing decision, including `published_stage_ids` and a nullable `variant_id` for every resolved tool selection
- `round-contract.json`: stages, expected artifacts, and per-toolchain record counts
- `execution-handoff.json`: stage packages with `authorization: required_at_execution`, route-specific authorization actions, dependencies, typed input and output contracts, expected row counts, transfer boundaries, and closeout requirements

The handoff is bound to `plan.json`. Referenced public request, ledger, workflow, provider-profile, and API-contract files are also hash-pinned. `preflight` fails when any pinned input changes.

For local execution, keep the separate controller request below `.runtime/`. It must reference the selected plan hash and a successful target-verification report. The controller request is runtime input, not a public plan artifact.

A remote stage must close with:

- a stage event
- expected and actual output counts
- artifact hashes
- validation notes
- applicable artifact export and cleanup proof

Concrete provider resources, credentials, endpoints, accepted-license state, logs, private paths, actual spend, sequences, structures, and unpublished results stay outside public Git.

Use `closeout` to count and hash an exact output declaration:

```bash
bsf binder-lane closeout \
  --workspace . \
  .runtime/pd-l1-binder-round/boltz \
  --stage-id cofold \
  --artifact-root outputs \
  --declarations .runtime/pd-l1-binder-round/boltz/output-declarations.json \
  --exit-code 0
```

The declaration is a JSON list of `artifact_id` and run-root-relative `path` pairs. `closeout` fails when an output is missing, extra, empty, outside the run root, or reached through a symbolic link.

Run `round-decision` on the sequential round history to produce a machine-readable `continue` or `stop` decision. The command checks the primary metric, spend ceiling, stopping rule, and maximum round count without making a provider call.

The history file is a JSON list with one row per completed round:

```json
[
  {
    "round_index": 1,
    "primary_metric_value": 0.42,
    "actual_spend_usd": 0.0,
    "closeout_complete": true,
    "metric_provenance": {
      "metric_id": "cofold_confidence_proxy",
      "metric_source": "synthetic_fixture",
      "source_artifact_sha256": null,
      "calibration_state": "not_applicable",
      "calibration_scope_id": "synthetic-demo",
      "calibration_artifact_sha256": null
    }
  }
]
```

Use [`../examples/pd-l1-binder-design-public/round-history.synthetic.example.json`](../examples/pd-l1-binder-design-public/round-history.synthetic.example.json) as the shape only. For a real decision, record the selected metric, spend, joined stage-closeout state, and metric provenance in ignored runtime state.

For a measured metric, set `metric_source` to `stage_closeout` or `operator_supplied` and bind `source_artifact_sha256` to the exact metric artifact. Use `calibrated` for a calibration derived in the selected scope, `borrowed` for a reviewed calibration from another declared scope, `operator_defined` for a threshold policy chosen by the user, or `uncalibrated` when no threshold interpretation is justified. Calibrated and borrowed states require the calibration artifact hash. All compared rounds must use the same calibration state, scope, and calibration artifact. A `target_threshold` stopping rule accepts calibrated, borrowed, or operator-defined provenance; it does not treat an uncalibrated score as a calibrated threshold.

## Agent Workflow

A person can point Claude Code, Codex, or another agent at this repository and ask it to:

```text
Use the binder-lane-round skill. Work with me to select a public target and bounded site, study mode, tool mix, execution route, license posture, budget, runtime cap, round count, primary metric, and stopping rule. Run target verification before generation. Materialize and preflight the handoff, then dry-run selected local adapters or the local controller. For a remote route, validate the request and identify the user-supplied dispatcher. Before a real start, show the approval needed for the named paid launch, non-public upload, terms acceptance, or large or license-gated download.
```

To use a different tool or backend, edit the request, then rerun `plan-request`. Add its execution record to a registry below `.runtime/`; the public registry schema does not restrict adapters to the bundled tool list.

## Result Boundaries

The shipped run uses:

```text
source_posture: synthetic_demo
result_boundary: public_synthetic_demo
comparison_interpretation: not_evaluable
```

After a verified closeout, record provider-backed design outputs as `computational_candidate` with provenance. The lane does not establish binding, affinity, function, selectivity, safety, manufacturability, therapeutic value, or clinical relevance.

## Checks

```bash
make binder-lane-check
make release-check
make public-switch-check
```

Generated round files belong below ignored `.runtime/` paths and must not be committed.
