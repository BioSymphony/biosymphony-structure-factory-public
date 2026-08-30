---
name: biosymphony-structure-factory
description: Use when planning structural biology campaigns, binder-design triage, model comparison, structure mapping, RunPod or cloud GPU stage contracts, or Symphony or Linear task packs for long-running biological agent work.
---

# BioSymphony Structure Factory

Use this skill to turn a target, accession, or campaign request into a campaign manifest, task plan, provider contract, candidate report, or structure report.

## Always Read

- `references/README.md`
- `references/AGENTS.md`
- `references/NON_CLAIMS.md`

## Read When Applicable

- `references/docs/intake-interview.md` for ambiguous, data-bearing, license-bearing, cost-bearing, or workflow-sized requests.
- `references/docs/agentic-biology-harness.md` before multi-agent or provider-coordinated work.
- `references/docs/public-export-shape.md` before release, publication, or public handoff work.
- `references/docs/linear-orchestration.md` before generating or dispatching Symphony or Linear task packs.
- `references/docs/compute-backends.md` when selecting local, FAL, Modal, RunPod, Lambda Cloud, AWS Batch, SSH or HPC, generic cloud, or neocloud execution.
- `references/docs/runpod-stack.md` before RunPod prep or launch.
- `references/docs/tooling-and-licensing.md` before selecting, installing, baking, or running tool lanes.
- `references/docs/confidence-sidecars.md` before editing or launching any fold, cofold, scoring, ranking, or render lane that depends on confidence metrics.
- `references/docs/no-false-success-hardening.md` before provider-backed execution or scientific closeout.
- `references/docs/operational-gotchas.md` before any paid GPU dispatch: a 45-class catalog of failure modes with pre-flight probes and fixes.
- `references/docs/preflight-checklist.md` for the 10-gate pre-dispatch checklist pattern (PDB chain identity, hotspot atom-spec, output-count validation, operator approval, etc.).
- `references/docs/agent-run-learnings.md` for execution checks and public record boundaries.
- `references/examples/pd-l1-binder-design-public/README.md` for the public binder-design fast path.
- `references/docs/binder-lane-round.md` for multi-arm binder comparisons and mixed-backend handoff contracts.
- `references/docs/binder-study-decision-loop.md` before choosing the target, study mode, tools, execution routes, budget, rounds, metric, and stopping rule.
- `references/docs/binder-controls.md` before deriving or adopting measured-control gates for a round decision.
- `references/docs/quickstart-tour.md`, `references/docs/cli-reference.md`, and `references/docs/agent-recipes.md` when helping a public user start from scratch.
- `references/docs/faq.md` and `references/docs/glossary.md` when a user or a general-purpose agent is unfamiliar with structural biology terms, agent harness conventions, or how to operate the repo without a tracker.

## Mission Modes

- `planning`: define target, data posture, result boundaries, lanes, risks, dependencies, and task pack.
- `public_demo`: use public accessions, synthetic fixtures, and compact reports.
- `gpu_prep`: prepare RunPod, cloud, or local stage contracts, launch templates, and validation commands without provider execution.
- `symphony_dispatch`: generate tracker-neutral issues for Symphony, Linear, or any agent queue.
- `report_or_review`: synthesize existing outputs into candidate rankings, validation notes, structural reports, and figures.
- `provider_run`: when explicitly authorized, require budget, runtime cap, cleanup policy, artifact list, hashes, and closeout gates.

## Operating Rules

- Use public accessions, synthetic examples, or explicit operator-approved data references.
- Keep credentials, provider IDs, private paths, generated structure archives, raw cryo-EM data, unpublished sequences, patient data, and model weights outside public git.
- Mark source posture and result boundary on every closeout. Computational candidates stay at `computational_candidate` until independent validation exists.
- Closeout requires stage events, expected artifacts, hashes, and validation notes. A passing process exit alone does not finish the work.
- Long or GPU workflows need stage contracts, expected artifacts, progress ledgers, partial-success policy, and result boundaries.
- License-gated tools stay gated until the user's use context and runtime access are explicit.
- Before a paid run, check each selected tool's primary repository, releases, and relevant preprints.
- Record the checked date and exact version, commit, or model revision in the validation notes.
- Resolve a conflict between a public tool card and a current primary source before provider preparation.

## Multi-Agent Dispatch

Use `bsf issue-dry-run <campaign> --out <directory>` to render tracker-neutral Markdown tasks. Each task carries dependencies, owned paths, expected artifacts, and validation commands. Adapt those files to the selected tracker outside public git.

Use routing label:

```text
sym:structure-factory
```

Do not dispatch high-cost, data-bearing, license-gated, or provider-backed work until the required approval names the route, data posture, budget, runtime, and applicable terms. Close review work with source posture, result boundary, validation summary, and artifact references.

## RunPod And Cloud Resources

This repository includes its most detailed cloud contracts under `runpod/`. FAL, Modal, Lambda Cloud, AWS, local, SSH or HPC, generic cloud, and neocloud profiles must preserve the same input, artifact, cleanup, and self-check requirements.

For a paid provider run, declare the execution profile and setup posture, run readiness and scope checks, obtain the required approval, export and hash the declared artifacts, verify cleanup, and label partial or missing outputs accurately.

## Binder-Design Fast Path

1. If starting fresh, run `bsf scaffold-campaign` into `.runtime/` first.
2. Define target accession, chain or window, hotspot plan, and result boundaries.
3. Pick generation lanes and cofold or model-comparison lanes.
4. Add runtime gates for GPU tools, weights, and use-context checks.
5. Declare expected artifacts and the stage contract.
6. Generate tracker-neutral task drafts.
7. Produce the candidate ranking and validation notes.

For a comparison round:

1. Inspect `references/published-binder-comparison-workflow.json` and `references/binder-execution-adapters.json`. Set `reference_scope` to `published_tool_identities` for a checked source-tool replay or `published_workflow_shape` for a shape-only replay.
2. Materialize and preflight the plan. Classify each arm as replay or replacement.
3. Run `bsf binder-lane target-check --plan <plan.json>` on the coordinate input before generation.
4. Use `bsf binder-lane prepare-execution` to bind selected local stages to the exact plan and target report. Resolve its readiness gaps before `bsf binder-lane execute --dry-run`.
5. For a remote route, use `remote-request` and `remote-receipt`. The `remote_dispatch.dispatch_remote_tool` Python API is a user-supplied transport, not a CLI command.
6. Add `--authorize-local-execution` only before the approved local start. Use `calibrate-controls` for a measured primary metric, `closeout` to count and hash exact outputs, and `round-decision` to apply the metric, spend ceiling, round count, and stopping rule.

Wet-lab validation happens outside the repository.

## Validation

Run:

```bash
make harness-check
make release-check
```

Before publication, run gitleaks through:

```bash
make secret-scan
```

A skipped scan leaves the publication gate incomplete.
