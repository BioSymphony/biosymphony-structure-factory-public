---
name: binder-lane-round
description: Plan and run study-shaped protein-binder rounds with interchangeable toolchains, execution profiles, license gates, output checks, and result boundaries.
---

# Binder Lane Round

Use one round contract to compare one or more binder-design toolchains against a fixed public target and site.

## Read First

- `references/docs/binder-lane-round.md`
- `references/docs/binder-study-decision-loop.md`
- `references/docs/binder-controls.md`
- `references/NON_CLAIMS.md`
- `references/docs/tooling-and-licensing.md`
- `references/docs/compute-backends.md`

## Scope

The lane validates requests, materializes plans and handoffs, runs synthetic contract checks, and runs validated fixed-argument local adapters after explicit authorization. A runtime registry below `.runtime/` can describe another local tool, API client, cloud client, scheduler, or container entry point.

## Required Decisions

Declare:

- the public or synthetic target accession, chain, and required residue selections
- whether `reference_scope` preserves the Anthropic workflow shape or checks the published tool identities on the bounded stages
- whether each arm replays those identities, replaces tools, or joins a replay-and-replacement comparison
- the generator, sequence designer, predictors, scorers, and filters
- the execution mix for each stage
- code, weight, dependency, API-term, redistribution, and use-context constraints
- the budget ceiling and runtime cap
- the planned round count
- one primary metric and a checkable stopping rule
- the required and optional controls for any measured calibration
- the expected artifacts, exact counts, hashes, validation notes, and cleanup requirements

## Workflow

1. Record the target, site, study mode, tool mix, execution mix, use constraints, budget, rounds, metric, and stopping rule.
2. Run `bsf binder-lane menu`, then validate the request with `plan-request`.
3. Materialize `plan.json`, `round-contract.json`, and `execution-handoff.json` with `plan`.
4. Run `preflight`, then run `target-check` on the coordinate input before generation.
5. Use `run` only for a `public_synthetic_demo` plan.
6. Run `adapters` to inspect bundled records. If a selected tool has no bundled command, create a validated adapter registry below `.runtime/`.
7. Run `prepare-execution` with the exact target report and stage settings. Resolve its per-selector readiness gaps before local controller execution.
8. Dry-run each local adapter or the prepared controller request.
9. For a remote route, validate the request with `remote-request`. Use `remote-receipt` after the user-supplied dispatcher exports artifacts and verifies cleanup.
10. Before a real start, obtain approval for the named route, data posture, budget, runtime, and any paid launch, non-public upload, terms acceptance, or large or license-gated download.
11. Start an approved local adapter or controller with `--authorize-local-execution`. Add `--authorize-network` or `--authorize-license-gates` only when the selected adapter requires them.
12. Run `closeout` to count, parse, and hash the exact declared outputs before stage completion.
13. For a measured primary metric, run `calibrate-controls` and inspect its readiness record.
14. Run `round-decision` against the sequential round history. Pass the ready calibration with `--calibration` when the metric requires it.
15. Start another round only when the decision is `continue` and the remaining budget covers that round.

## Commands

```bash
bsf binder-lane menu --workspace .
bsf binder-lane plan-request examples/pd-l1-binder-design-public/binder-round-request.json \
  --workspace . \
  --ledger references/binder-lane-capability-ledger.json \
  --out .runtime/pd-l1-binder-round/plan.json
bsf binder-lane plan .runtime/pd-l1-binder-round/plan.json \
  --workspace . \
  --out .runtime/pd-l1-binder-round/run
bsf binder-lane preflight --workspace . .runtime/pd-l1-binder-round/run
bsf binder-lane target-check .runtime/pd-l1-binder-round/target/target.cif \
  --workspace . --plan .runtime/pd-l1-binder-round/plan.json \
  --expected-sequence-file .runtime/pd-l1-binder-round/target/expected-sequence.txt \
  --sequence-basis entity --out .runtime/pd-l1-binder-round/target/verification.json
bsf binder-lane run --workspace . .runtime/pd-l1-binder-round/run
bsf binder-lane report --workspace . .runtime/pd-l1-binder-round/run
bsf binder-lane calibrate-controls examples/binder-controls-synthetic/control-panel.json \
  --workspace . \
  --observations examples/binder-controls-synthetic/control-observations.jsonl \
  --out .runtime/pd-l1-binder-round/control-calibration.json
bsf binder-lane round-decision .runtime/pd-l1-binder-round/plan.json \
  --workspace . --history .runtime/pd-l1-binder-round/round-history.json \
  --out .runtime/pd-l1-binder-round/round-decision.json
bsf binder-lane adapters --workspace .
bsf binder-lane adapter boltz-local-v1 --workspace . \
  --run-root .runtime/pd-l1-binder-round/boltz --operation readiness --dry-run
bsf binder-lane prepare-execution .runtime/pd-l1-binder-round/plan.json \
  --workspace . \
  --target-report .runtime/pd-l1-binder-round/target/verification.json \
  --stage-settings .runtime/pd-l1-binder-round/stage-settings.json \
  --out .runtime/pd-l1-binder-round/controller-request.json \
  --readiness-out .runtime/pd-l1-binder-round/execution-readiness.json
bsf binder-lane execute .runtime/pd-l1-binder-round/controller-request.json \
  --workspace . --plan .runtime/pd-l1-binder-round/plan.json \
  --run-root .runtime/pd-l1-binder-round/execution --dry-run
bsf binder-lane remote-request .runtime/pd-l1-binder-round/cofold/request.json \
  --workspace . --out .runtime/pd-l1-binder-round/cofold/validated-request.json
bsf binder-lane remote-receipt .runtime/pd-l1-binder-round/cofold/receipt.json \
  --request .runtime/pd-l1-binder-round/cofold/validated-request.json --workspace .
```

## Gates

- Separate bundled adapter availability from local installation and service readiness.
- If the registry lacks a bundled command, let the user supply a validated adapter or choose another route.
- Treat allowed license gates as requested planning posture. Record license acceptance separately.
- Before a real start, request approval for the named route, data posture, budget, runtime, and any paid provider start, external upload of non-public data, terms acceptance, or large or license-gated download. The `adapter` and `execute` commands require `--authorize-local-execution` before a local process start.
- Keep credentials, service addresses, provider resources, accepted-license state, private paths, private inputs, generated biology, logs, and actual spend outside public Git.
- Keep runtime bindings, custom adapter registries, and execution receipts below `.runtime/`.
- Accept user-selected tools and backends when their adapter records satisfy the fixed-argument, typed-binding, path-containment, and output contracts.
- Reject a comparison when arms do not share the candidate count, predictor panel, scorers, filters, controls, and failure policy.
- Require output counts before stage completion.

## Boundaries

Synthetic rows are constructed examples. Computational candidates remain computational candidates until independent validation supports a narrower statement. The lane does not establish binding, affinity, function, selectivity, safety, manufacturability, therapeutic value, or clinical relevance.
