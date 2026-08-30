# FAQ

Common questions for users and agents new to Structure Factory.

## Do I need a GPU?

No. The agent skill and the `bsf` CLI run on a regular laptop. Planning, scaffolding, task-pack generation, validation, and audits happen locally with no compute beyond Python. For GPU work, choose a provider such as RunPod, AWS Batch, neocloud, or HPC. Materialize live bindings in ignored `.runtime/` space, validate the adapter, and record bounded human authorization before a paid provider start or non-public upload.

## Do I have to run the CLI commands myself?

No. The intended use is to point your agent at this repo and let the agent call the CLI. The CLI is the machinery the agent uses, not the user front door. Power users who want to inspect or drive it manually are welcome to. See [`README.md`](../README.md#inspect-or-run-the-repo-yourself).

## Which agents work with this?

Any agent runtime that can read a skill file. The repo ships:

- A portable skill at [`skills/biosymphony-structure-factory/SKILL.md`](../skills/biosymphony-structure-factory/SKILL.md) for Codex, Claude Code, Symphony workers, `/goal` stacks, and custom runtimes.
- A binder comparison skill at [`skills/binder-lane-round/SKILL.md`](../skills/binder-lane-round/SKILL.md) for study-shape replay, tool swaps, license policy, and mixed-backend handoffs.

If your agent can read Markdown and call a CLI, it can use this skill.

## Can I use Claude Code for an Anthropic binder-study replay?

Yes. Point Claude Code, Codex, Symphony, or another Markdown-capable AI agent at this repository. Ask it to use the [`binder-lane-round` skill](../skills/binder-lane-round/SKILL.md), then follow the [binder lane round guide](binder-lane-round.md) and [binder study decision loop](binder-study-decision-loop.md). The lane supports an exact source-tool replay, a workflow-shape replay, or a deliberate tool comparison.

You can use your chosen AI agent and mix platform skills, hosted APIs, local or self-hosted tools, and cloud routes by stage. The decision loop records the route, use constraints, budget, stopping rule, and closeout requirements before execution.

## Can I Swap Tools In A Binder Comparison?

Yes. `controlled_generation` varies generation and sequence-design tools while predictors, scorers, filters, and candidate counts stay fixed. `exploratory_full_stack` can vary every declared tool role but sets cross-arm ranking to `not_permitted`. See [`binder-lane-round.md`](binder-lane-round.md).

## Can I use this without Linear or any tracker?

Yes. The skill works in a single agent turn for short missions. Task packs are useful when work spans multiple agents or sessions. With no tracker, the agent writes campaign manifests, target reports, validation reports, and task drafts to `.runtime/` and you read them directly.

## Can I run this on my laptop?

Yes. The repo is local-first. `bsf doctor`, `bsf catalog`, `bsf scaffold-campaign`, `bsf validate`, `bsf issue-dry-run`, and `bsf audit` all run on a standard Python 3.10+ install with no extra dependencies. The repo has no required network calls.

## What if I just want to read the code?

Run `bsf catalog . --format markdown` after `pip install -e .` for a one-screen overview of campaigns, examples, providers, recipes, and starter commands. Or browse [`docs/capabilities.md`](capabilities.md) and [`docs/use-cases.md`](use-cases.md) directly. The [`docs/glossary.md`](glossary.md) is a short reference for the structural biology and Structure Factory terms used across the repo.

## How do I add my own tool, provider, or campaign mode?

- **Tool.** Drop a new card under [`tools/`](../tools/) following the existing card format. Add it to [`references/software-registry.yaml`](../references/software-registry.yaml) if it is a recognized public tool.
- **Provider.** Add a profile under `modules/provider-profiles/<provider>/` matching the JSON shape in existing profiles.
- **Campaign mode.** Extend the mode list in [`src/biosymphony_structure_factory/cli.py`](../src/biosymphony_structure_factory/cli.py) and add a matching template under `modules/campaigns/`.
- Run `make harness-check` to confirm the public surface still validates after your addition.

## What if my agent makes a mistake?

Every campaign manifest is validated by `bsf validate` before task packs or provider contracts are generated. The `bsf audit` command checks release posture: no credentials, private paths, large generated files, or known leaks. The `make harness-check` command verifies the load-bearing parts of the repo are still in place. If the agent produces a manifest the validator rejects, the work pauses until the manifest is fixed.

## Does this run wet-lab protocols or clinical workflows?

No. Wet-lab execution, clinical validation, and therapeutic conclusions live outside this repo. See [`NON_CLAIMS.md`](../NON_CLAIMS.md) and [`BIOSAFETY.md`](../BIOSAFETY.md) for the boundary.

## Is this a replacement for Symphony or Linear?

No. Symphony coordinates workers. Linear or another tracker carries task state. Structure Factory provides the biology-specific contracts and validation that those orchestrators dispatch against. The three layers compose: orchestrator drives, tracker holds state, Structure Factory keeps the work biology-correct and traceable.

## What does "result boundary" mean?

The strongest status a campaign output is allowed to reach. Generated or predicted biology stays at `computational_candidate` until independent validation arrives. See [`docs/glossary.md`](glossary.md) for short definitions.

## Where does the data live?

Public examples use public accessions (PDB, EMDB, EMPIAR, UniProt). Synthetic fixtures are compact and embedded in the repo. Provider runs write artifacts, hashes, logs, and closeouts to user-controlled runtime storage. Keep those files, live identifiers, and credentials out of tracked git files. The repository records what each run should produce and how to verify it.

## How do I know it is working?

```bash
make harness-check     # public surface intact
make read-only-audit   # validators clean
bsf doctor .           # first-confidence checks
bsf catalog .          # what the repo offers
```

All four return `ok: true` on a clean checkout.

## What should I read before any paid GPU dispatch?

[`docs/operational-gotchas.md`](operational-gotchas.md) and [`docs/preflight-checklist.md`](preflight-checklist.md). The catalog lists ~45 failure classes with paste-ready pre-flight probes and fix recipes (RunPod payload limits, conda env traps, designer-specific gotchas, cofold output-field traps, orchestration cascade failures). The checklist is a ten-gate pre-dispatch pattern (PDB chain identity, hotspot atom-spec validity, output-count validation, human approval, and seven more) that catches the highest-value failure modes at zero cost.

For ChimeraX render lanes specifically, [`tools/chimerax-onboarding.md`](../tools/chimerax-onboarding.md) is the single-file teammate-handoff brief.

## What does "silent cascade failure" mean?

A pipeline whose stage gates are exit-code-driven (rather than output-driven) will silently degrade to whatever subset of inputs survived — and call it success. The incident pattern: a 4-arm designer bake-off where three arms produce 0 designs because each hit a different first-order bug, but the orchestrator emits `STAGE_COMPLETE` on bash exit regardless. Subsequent stages cascade with 1/4 of the planned inputs, the pipeline reports `ALL_COMPLETE`, and the failure is invisible until visual inspection of the output. The fix is gate G8 in the preflight checklist: every worker validates output count before declaring success, and the orchestrator polls for both `STAGE_COMPLETE` and `STAGE_FAILED` markers.
