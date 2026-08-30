# Binder Study Decision Loop

Use this decision loop to repeat or extend Anthropic's published binder-design study with your AI agent. It also supports public or synthetic workflow-shape replays, deliberate tool swaps, and independent comparisons.

You set the scientific question, target and site, acceptable use, route, spending, and stopping rule. The agent turns those choices into a validated plan, execution handoff, and closeout record.

## Record The Round

Before planning, record these decisions in the request or an ignored file below `.runtime/`:

| Decision | Record |
| --- | --- |
| Target and site | Public accession, target chain, and bounded residue window or site-selection rule. |
| Study mode | Exact source-tool replay, workflow-shape replay, deliberate tool swap, replay-and-swap comparison, or an independent comparison. |
| Tool mix | Generator, sequence designer, predictors, scorers, and filters for each arm. |
| Execution mix | One route per stage: user-supplied platform skill, hosted API client, self-hosted local tool, FAL, Modal, RunPod, Lambda Cloud, AWS, neocloud, SSH/HPC, or a mixed route. |
| Use constraints | Intended use plus code, weight, dependency, API-term, and redistribution limits. |
| Budget | Maximum spend and maximum runtime for the round. |
| Rounds | Maximum round count and candidate count per arm. |
| Decision rule | One primary metric and a stopping rule that names a threshold, comparison, or exhausted limit. |
| Closeout | Exact outputs, counts, file types, hashes, local or provider receipts, failure-row policy, cleanup evidence, and figures or renders when selected. |

The pinned public reference is [`published-binder-comparison-workflow.json`](../references/published-binder-comparison-workflow.json). It defines the bounded stages, the published tool cohort, and the reference revision.

- **Exact source-tool replay:** Set `reference_scope: published_tool_identities`. Select the generator, sequence designer, predictor variant, and scorer identities from `published_tool_cohort`. A variant has the form `{ "tool_id": "esmfold2", "variant_id": "esmfold2-fast" }`. The validator checks replay arms against the published identities on `bounded_stage_ids`.
- **Workflow-shape replay:** Set `reference_scope: published_workflow_shape` and `workflow_strategy.mode: published_shape_replay`. This preserves the declared stages and comparison structure without asserting source tool identities.
- **Deliberate tool swap:** Set `workflow_strategy.mode: deliberate_tool_swap` or `replay_and_swap`. Record the replacement tool, its role, and the stage that differs. Each swap arm differs on at least one bounded stage.
- **Independent comparison:** Use `toolchain-comparison` or `custom`. When arms use different predictor panels, scorers, or metrics, classify the comparison as exploratory and avoid a cross-arm ranking.

## Choose The Execution Mix

Choose each stage independently. The plan can combine:

- an installed platform skill that prepares or operates the selected tool
- a hosted API client
- a self-hosted local command
- FAL, Modal, RunPod, Lambda Cloud, AWS, neocloud, or generic cloud compute
- an SSH or HPC scheduler client

A provider profile records the selected route's requirements. Confirm account access, installation, terms, capacity, and request readiness with the selected client or dry run.

The shipped registry includes complete commands where the repository can state them accurately. `adapter_required` means that the registry has no bundled command for the selected installation and route. Supply a validated adapter registry below `.runtime/` for an installed program, API client, cloud client, scheduler, or container entry point, or use a platform-skill route. A runnable local record names a literal program, fixed argument arrays, typed placeholders, environment-variable names, network policy, and exact expected outputs. Keep credential values, service addresses, provider resources, and private paths in runtime state.

For a platform-skill route, your agent runs the selected skill within the target, data, budget, runtime, and output bounds in the handoff. The skill writes its declared outputs below the stage root; close them with `bsf binder-lane closeout` and the same count, hash, and receipt requirements.

## Set The Metric And Stopping Rule

Choose one primary metric before the first run. Record its direction, unit, missing-value policy, and tie break.

Write a stopping rule that the closeout files can evaluate. For example:

```text
Primary metric: interface score, unitless, higher is better.
Stop after three rounds, when the score does not increase by at least 0.02 between
consecutive valid rounds, or when the approved spend reaches $75, whichever happens first.
```

To change the stopping rule after results exist, record a new plan revision before another round.

## Plan And Dry-Run

To prepare the first round, do the following:

1. Inspect the tool and route choices with `bsf binder-lane menu` and `bsf binder-lane adapters`.
2. Validate the request with `bsf binder-lane plan-request`.
3. Materialize the plan, round contract, and handoff with `bsf binder-lane plan`.
4. Check the materialized files with `bsf binder-lane preflight`.
5. Dry-run each selected adapter and external client.

For a local adapter, use a registry and bindings file below `.runtime/`:

```bash
bsf binder-lane adapter <adapter-id> \
  --workspace . \
  --registry .runtime/<round-id>/adapters.json \
  --run-root .runtime/<round-id>/<stage-id> \
  --bindings .runtime/<round-id>/<stage-id>/bindings.json \
  --dry-run
```

The dry run checks the registry, typed bindings, program lookup, declared environment-variable names, runtime paths, timeout, and receipt location. It starts no process and makes no provider request.

## Approve The Start

After the dry run passes, record these facts for approval:

- selected tool and version or revision
- selected execution route
- license and use checks that remain open
- maximum spend and runtime
- external data sent by the route
- expected outputs, receipts, and cleanup action

Ask for explicit approval before a paid provider start, non-public upload, terms acceptance, or large or license-gated download. One approval covers a bounded run with named tools, providers, data posture, budget, and runtime. Record a new approval when those bounds change.

To start an adapter process, add `--authorize-local-execution`. This flag starts the local process only; the bounded run approval covers associated provider requests or spending. Keep credentials in the runtime environment, not in arguments, bindings, receipts, or tracked files.

## Close The Round

After every stage, run `bsf binder-lane closeout` against the declared artifact root and output declarations.

A file closeout has all of these records:

- the expected output paths and no undeclared output
- the expected file count
- a SHA-256 digest for every declared file
- validation notes, the applicable cleanup result, and selected figures or renders

For an adapter-backed or provider-backed stage, join its execution receipt to the file closeout before recording stage completion. The execution receipt adds parsed record counts and failure-row coverage. A stage completes when its declared outputs are present, valid, contained by the run root, count-checked, and hashed.

After closeout, compare the primary metric with the stopping rule. If the rule permits another round, subtract the recorded spend from the budget and plan the next round before starting it.

Use the CLI to make that decision reproducible:

```bash
bsf binder-lane round-decision \
  .runtime/<round-id>/plan.json \
  --workspace . \
  --history .runtime/<round-id>/round-history.json \
  --out .runtime/<round-id>/round-decision.json
```

The command checks the sequential metric values, recorded spend, maximum round count, and stopping rule. It starts no process and makes no provider call.

The history file contains one row per completed round with `round_index`, `primary_metric_value`, `actual_spend_usd`, `closeout_complete`, and a `metric_provenance` record. The provenance binds the value to its metric artifact and records whether its interpretation is calibrated, borrowed, user-defined, uncalibrated, or not applicable. See the [synthetic round-history example](../examples/pd-l1-binder-design-public/round-history.synthetic.example.json). Replace its constructed values with joined closeout and calibration records before running the command.

Keep generated sequences, structures, provider logs, actual resource identifiers, and private results outside public Git. Record provider-backed outputs as `computational_candidate` until independent validation supports another result boundary.
