# CLI Reference

The `bsf` CLI is dependency-free and intended to run in local development, CI, and agent sandboxes.

Install it with:

```bash
python -m pip install -e .
```

## `bsf scaffold-campaign`

Create a campaign skeleton.

```bash
bsf scaffold-campaign .runtime/my-target-demo \
  --campaign-id my-target-demo \
  --target-label "A2A receptor" \
  --public-accession "PDB:5G53" \
  --window "TM6 activation microswitch" \
  --mode binder-design
```

Modes:

- `binder-design`
- `model-comparison`
- `structure-mapping`
- `screening`

The command rejects obvious release blockers such as private workstation paths, private tracker IDs, assigned credential-like values, and literal provider resource IDs. It writes only compact text and JSON control-plane files.

## `bsf validate`

Validate a public campaign example.

```bash
bsf validate examples/pd-l1-binder-design-public
```

The validator checks public/privacy posture, result boundaries, target accession/window, lane boundaries, expected artifacts, stage contract fail-closed posture, and candidate ranking source posture.

## `bsf issue-dry-run`

Render tracker-neutral task drafts for a validated campaign. The issue plan is
mode-aware for `binder-design`, `model-comparison`, `structure-mapping`, and
`screening` campaign manifests.

```bash
bsf issue-dry-run examples/pd-l1-binder-design-public --out .runtime/pd-l1-issues
```

The output is ignored by git. Review it before importing into Linear, GitHub Issues, Notion tasks, or another tracker. The generated task IDs use mode-specific prefixes such as `BSF-BINDER-*`, `BSF-MODEL-*`, `BSF-MAP-*`, and `BSF-SCREEN-*`.

## `bsf binder-lane`

Plan, check, and close a binder toolchain comparison:

```bash
bsf binder-lane menu --workspace .
bsf binder-lane plan-request examples/pd-l1-binder-design-public/binder-round-request.json \
  --workspace . --out .runtime/pd-l1-binder-round/plan.json
bsf binder-lane plan .runtime/pd-l1-binder-round/plan.json \
  --workspace . --out .runtime/pd-l1-binder-round/run
bsf binder-lane preflight --workspace . .runtime/pd-l1-binder-round/run
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
  --stages filter \
  --out .runtime/pd-l1-binder-round/controller-request.json \
  --readiness-out .runtime/pd-l1-binder-round/execution-readiness.json
bsf binder-lane execute .runtime/pd-l1-binder-round/controller-request.json \
  --workspace . --plan .runtime/pd-l1-binder-round/plan.json \
  --run-root .runtime/pd-l1-binder-round/execution --dry-run
bsf binder-lane remote-request .runtime/pd-l1-binder-round/cofold/request.json \
  --workspace . --out .runtime/pd-l1-binder-round/cofold/validated-request.json
bsf binder-lane remote-receipt .runtime/pd-l1-binder-round/cofold/receipt.json \
  --request .runtime/pd-l1-binder-round/cofold/validated-request.json --workspace .
bsf binder-lane target-check .runtime/pd-l1-binder-round/target/target.cif \
  --workspace . --plan .runtime/pd-l1-binder-round/plan.json \
  --expected-sequence-file .runtime/pd-l1-binder-round/target/expected-sequence.txt \
  --sequence-basis entity --out .runtime/pd-l1-binder-round/target/verification.json
```

- `menu` lists public tool evidence, license gates, and provider profiles.
- `plan-request` validates toolchain arms, controls, constraints, license policy, and per-stage routes.
- `plan` writes a hash-bound plan, round contract, and execution handoff. Each work package requires explicit authorization at execution time.
- `preflight` revalidates paths, routes, semantic contracts, and hashes without external calls.
- `run` accepts a `public_synthetic_demo` plan and its hash-bound fixture. It writes no tool or provider outputs.
- `report` checks artifact-hash coverage and prints the synthetic result boundary.
- `calibrate-controls` derives predictor-separated gates from JSON or JSONL observations, or adopts a reviewed gate record. It records required and optional gaps and makes no provider calls.
- `round-decision` evaluates sequential round closeouts against the primary metric, spend ceiling, stopping rule, and maximum round count. `--calibration` binds a ready measured-control record to metric provenance. The command makes no provider calls.
- `adapters` validates and lists bundled or `.runtime/` adapter registries.
- `adapter` dry-runs, checks, or runs one fixed-argument local program. A real process start requires `--authorize-local-execution`.
- `prepare-execution` maps selected plan stages and tool identities to explicit adapter IDs and routes. It rejects a target report from another plan, target, or site. A ready request binds the plan and report hashes, replay and replacement arms, round metric, round budget, and typed bindings.
- `execute` runs the prepared local stage graph through the adapter executor. It materializes declared file and directory-bundle handoffs between dependent stages. Each completed stage records the adapter receipt path and SHA-256. A failed readiness, handoff, or output check stops dependent stages.
- Run `execute --dry-run` before local execution. For a real run, add `--authorize-local-execution`. Add `--authorize-network` only when an adapter declares `runtime_review_required`. Add `--authorize-license-gates` after the selected use passes its terms review.
- `closeout` validates exact stage outputs and writes SHA-256 artifact and stage receipts.
- `remote-request` validates a registered remote operation, pinned identities, budgets, and artifact namespace without starting a provider job.
- `remote-receipt` joins sanitized remote results to the exact request and requires hashed artifacts plus verified cleanup.
- `biosymphony_structure_factory.remote_dispatch.dispatch_remote_tool` is the user-supplied Python dispatch API. It is not a CLI subcommand.
- `target-check` reads the chain and required residue selections from the exact plan. It verifies them against a PDB or mmCIF and can compare an optional coordinate or entity sequence.

See [`binder-lane-round.md`](binder-lane-round.md) for runtime adapter records, custom tools, mixed compute routes, and closeout declarations. See [`binder-controls.md`](binder-controls.md) for panel, observation, derivation, adoption, and readiness contracts.

Run `target-check` before generation, `closeout` after a real stage, and `round-decision` only after the sequential history has a complete closeout. For a measured primary metric, pass the ready `calibrate-controls` output through `--calibration`.

On failure, binder-lane commands return an `error` string and a structured `failure` record with a stable check ID and viable next actions. An agent can present the actions for readiness, target, budget, calibration, authorization, and artifact-contract failures.

## `bsf audit`

Scan the repo tree for public-release blockers.

```bash
bsf audit .
```

The audit rejects common privacy and security hazards:

- private workstation paths
- private tracker IDs and tracker URLs
- assigned credential-like values
- presigned provider URL parameter values (X-Amz, Google, and AWS credential parameters)
- one-time transfer links
- literal provider resource IDs
- private measurement, provider-log, and GPU-telemetry directories
- runtime packet directories
- generated candidate sequences
- generated/heavy structural biology file suffixes
- public bridge manifests with embedded launch payloads or real approvals

## `bsf harness-check`

Verify the public skill repo shape.

```bash
bsf harness-check .
```

This checks that the README, skill files, public docs, task pack, RunPod posture, tool cards, templates, and release guidance expected by BioSymphony users are present and internally linked.

## `bsf catalog`

Summarize what the repo can do in a machine-readable JSON map or a human-readable
Markdown index.

```bash
bsf catalog .
bsf catalog . --out .runtime/public-capability-catalog.json
bsf catalog . --format markdown
bsf catalog . --format markdown --out .runtime/public-capability-catalog.md
```

The catalog lists task recipes, campaign modules, public examples, task packs,
stage contracts, provider profiles, recipes, and starter commands. It is
intended for fresh users and agents that need to choose an entry point without
reading the whole repository. Use JSON for automation and Markdown for reviews,
READMEs, or agent handoffs.

## `bsf doctor`

Run three local checks for a fresh public checkout: `harness-check`, `audit .`, and validation of the default public campaign.

```bash
bsf doctor .
```

Use `--example` to validate a different repo-relative campaign scaffold:

```bash
bsf doctor . --example .runtime/my-target-demo
```

The command emits one JSON summary with check results and next local commands. It does not call provider APIs, download data, create tracker issues, or mutate remote state.

## Make Targets

Common local targets:

```bash
make release-check
make catalog
make catalog-md
make read-only-audit
make public-contract-check
make public-switch-check
make clean
```

`make public-switch-check` is the strongest local public gate. It is still a current-tree check; public publication also requires a reviewed history path.
Use `make read-only-audit` when a reviewer wants a no-write confidence check
for the CLI harness, public documentation references, and tracked RunPod
templates.
