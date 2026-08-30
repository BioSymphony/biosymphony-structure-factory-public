# Agent Recipes

These recipes are promptable workflows for agents using the Structure Factory skill. Local recipes use repository files and Python. Provider recipes use the reader's selected account and runtime adapter.

For copyable end-to-end prompts, see [`docs/use-cases.md`](use-cases.md).

## Exact Result Values

Use the schema enum values in manifests, task packs, and closeouts. A friendly label is fine in prose, but the exact value should stay visible.

| Friendly Label | Exact Value | Use |
| --- | --- | --- |
| Planning | `planning` | Scaffolds, provider prep, and task design before outputs exist |
| Public demo | `public_demo` | Public deposited data demonstration |
| Public synthetic demo | `public_synthetic_demo` | Synthetic fixture or generated demo data |
| Computational candidate | `computational_candidate` | Candidate ranking or triage that still needs external validation |
| Blocked | `blocked` | A lane could not proceed |
| Insufficient support | `insufficient_support` | Outputs do not support the requested statement |

If you see older machine values such as `candidate`, `processed`, `fixture_or_demo`, `validated`, `insufficient_support`, or `publishable` in schema-level artifacts, translate them to the public labels before writing public prose or a final closeout.

## Recipe: Scaffold A Campaign

Use when a user has a public target or synthetic fixture and wants a structured work plan.

```bash
bsf scaffold-campaign .runtime/<campaign-id> \
  --campaign-id <campaign-id> \
  --target-label "<target name>" \
  --public-accession "<PDB/EMDB/UniProt/synthetic fixture>" \
  --window "<residue, domain, interface, or state window>" \
  --mode binder-design
```

Agent checklist:

- keep the scaffold in `.runtime/` until public inputs are reviewed
- set result boundaries before suggesting tool lanes
- use public accessions or synthetic fixtures only
- add an operator gate before any GPU, cloud, or license-gated step
- run `bsf validate` and `bsf audit .`

## Recipe: Binder-Design Fast Path

Use when the user asks for binder design from a public structure.

1. Create or validate `campaign-manifest.json`.
2. Write a target-window file with public accession, chain/window, hotspot plan, and uncertainty.
3. Declare generation lanes and cofold/model-comparison lanes.
4. Add expected artifacts and a fail-closed stage contract.
5. Render tracker-neutral issues with `bsf issue-dry-run`.
6. Keep candidate rankings at `computational_candidate` result boundary.

Do not present binding, inhibition, safety, selectivity, efficacy, or therapeutic value as established by this repo.

## Recipe: Binder Toolchain Comparison

Use when the user wants to repeat a public binder-workflow shape or compare different design stacks.

1. Start from `examples/pd-l1-binder-design-public/binder-round-request.json`.
2. Use `controlled_generation` when only generation and sequence design vary.
3. Use `exploratory_full_stack` when predictors, scorers, or filters also vary; set cross-arm ranking to `not_permitted`.
4. Declare metric direction, unit, missing-value policy, and tie break.
5. Declare the use context, allowed license gates, blocked tools, time cap, spend cap, and every stage route.
6. Run `plan-request`, `plan`, and `preflight`. Use `run` only for the hash-bound synthetic fixture.

The handoff sets `authorization: required_at_execution`. Dry-run the selected adapter, then obtain the recorded local or provider-dispatch authorization before execution.

## Recipe: GPCR Or Multimer State Atlas

Use when the user asks for activation states, receptor-state comparison, multimer-state analysis, or switch analysis.

1. Declare the receptor/state matrix and public accessions.
2. Split work into deposited-structure, prediction, alignment, render, and synthesis lanes.
3. Use issue waves so each receptor/state shard has owned paths and validation commands.
4. Keep prediction and render outputs in ignored/provider storage until summarized.
5. Cap prediction-only conclusions at `computational_candidate`.

Good public artifacts include wave plans, task drafts, provider contracts, accession tables, stage contracts, and report outlines.

## Recipe: Model Comparison Or Structure Mapping

Use when the user has existing public models, maps, or structures and wants review.

1. Identify public accessions and allowed local references.
2. Declare source posture for every artifact.
3. Separate provider-native outputs from derived local summaries.
4. Record missing optional tools as blocked or skipped, not silent success.
5. Produce a structure report with negative rows and uncertainty.

If the request starts from raw cryo-EM movies, EMPIAR subset processing, RELION/CryoSPARC reconstruction, or map-to-model build execution, create a CryoCore handoff contract. Do not present those lanes as Structure Factory-owned work.

## Recipe: Provider Prep Without Launch

Use when the user wants RunPod, cloud, HPC, or local GPU readiness but has not authorized execution.

1. Create provider-neutral stage contracts and launch templates.
2. Use placeholders for registry auth, volume IDs, placement, and credentials.
3. Run scope and preflight checks.
4. Keep live provider IDs, credentials, and approval out of tracked templates.
5. Materialize live provider packets below ignored `.runtime/` space after explicit human authorization.

## Agent Closeout

Every agent closeout should include:

- files changed
- validation commands run
- source posture
- result boundary
- privacy/security checks
- anything blocked, partial, or intentionally not launched
