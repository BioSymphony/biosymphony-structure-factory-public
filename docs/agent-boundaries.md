# Agent Boundaries

This repository exists to isolate Structure Factory work from other BioSymphony subgroups.

## Allowed Here

Agents working on Structure Factory may edit:

- `campaigns/`
- `containers/`
- `demos/`
- `docs/`
- `examples/`
- `modules/`
- `references/`
- `runpod/`
- `scripts/runpod/`
- `scripts/structure_factory/`
- `templates/`
- `tests/`
- this repo's `README.md`, `AGENTS.md`, and `.gitignore`

## Not Allowed Here

Do not edit sibling repositories from this repo unless the issue explicitly asks for cross-repo integration.

Especially do not casually edit:

```text
<biosymphony-hq-repo>/AGENTS.md
<biosymphony-hq-repo>/README.md
<biosymphony-hq-repo>/skills/biosymphony/SKILL.md
<biosymphony-hq-repo>/templates/linear-issue.md
```

Those are BioSymphony HQ/core files.

## Cross-Repo Changes

If Structure Factory needs a global contract, skill, or policy change:

1. Create a separate `biosymphony-core` issue.
2. Make the change in `<biosymphony-hq-repo>`.
3. Reference the core issue from the Structure Factory campaign.

## Branching Rule

Use one branch per Linear issue:

```text
codex/structure-factory-<short-task>
```

Do not combine unrelated campaign work in one branch.
