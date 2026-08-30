# Execution Checks And Record Boundaries

Use this guide when you prepare or close a run with your agent. It lists public checks and record boundaries.

## Before A Real Start

1. Use public or approved inputs and record the selected result boundary.
2. Check the selected tool's current source, license, model or weight posture, and intended use.
3. Set the route, data posture, budget ceiling, runtime cap, expected artifacts, and cleanup requirement.
4. Dry-run the selected local adapter or controller request.
5. Before a paid provider start, non-public upload, terms acceptance, or large or license-gated download, obtain approval that names the route, data posture, budget, and runtime.

Keep credentials, provider resource IDs, raw inputs, generated structures, raw execution records, and private measurements outside public Git.

## Target Verification

Run `bsf binder-lane target-check --plan <plan.json>` on the coordinate file that generation will read. The command reads the chain and required residues from the plan, then records the plan, target-contract, structure, and sequence hashes without printing a sequence or absolute path.

Pass the target-verification report to `bsf binder-lane prepare-execution`. The command rejects a report from another plan, target, or site. A ready controller request binds the report to a USD ceiling, local adapter IDs, stage dependencies, and typed bindings. `plan` does not create a controller request.

## Local Execution

Use `bsf binder-lane adapter --dry-run` for one local adapter. Use `bsf binder-lane execute --dry-run` for a local stage graph. A real local process requires `--authorize-local-execution`.

Add `--authorize-network` only for an adapter that declares `runtime_review_required`. Add `--authorize-license-gates` only after the selected use passes terms review. The controller stops dependent stages after a readiness or output-contract failure.

## Remote Contracts

Use `remote-request` to validate a provider-neutral request before a remote start. Use `remote-receipt` to join a sanitized receipt to that exact request after artifact export and cleanup.

`biosymphony_structure_factory.remote_dispatch.dispatch_remote_tool` is the user-supplied Python dispatch API. It is not a CLI command. It requires a supplied adapter, the declared credential keys in runtime state, and `authorization="authorize_remote_dispatch"` before it invokes the adapter. A dry run performs readiness checks without an adapter call.

## Control Calibration And Round Decision

Use `calibrate-controls` to derive or adopt a control record for a measured primary metric. Inspect `ok`, `status`, and `readiness`; a completed diagnostic can have `readiness: blocked`.

Use `round-decision` only after the history contains a complete closeout for each completed round. Pass a ready calibration with `--calibration` when the primary metric requires it. The decision checks the metric, spend ceiling, stopping rule, and round limit without a provider call.

## Closeout

Use `closeout` after a real stage. It rejects missing, extra, empty, out-of-root, or symbolic-link outputs. A closeout receipt records exact artifact counts, hashes, validation notes, result boundary, and applicable export and cleanup evidence.

A process exit, scheduler state, or provider status does not complete a stage. A closed stage must satisfy its artifact and cleanup contract.

## ESMFold2 Posture

The registry records the pinned ESMFold2, ESMFold2-Fast, and ESMC-6B local-weight routes with a reviewed MIT source posture, third-party notices, and no repository-imposed license gate. The routes remain `planned` and `adapter_required` until the selected source revision, Python/Torch runtime, weight-cache posture, and adapter pass a dry run.

The API route has separate service terms, acceptable-use, budget, and data-handling review. Keep model weights, API credentials, generated structures, and raw execution records outside public Git. ESMFold2 output is prediction or foldability evidence, not a binding or functional claim.

## Public Records

Publish compact contracts, validation notes, hashes, and result-boundary summaries. Keep run-specific artifacts in ignored runtime state or a user-selected artifact store. See [`preflight-checklist.md`](preflight-checklist.md), [`no-false-success-hardening.md`](no-false-success-hardening.md), [`tooling-and-licensing.md`](tooling-and-licensing.md), and [`compute-backends.md`](compute-backends.md) for the related contracts.
