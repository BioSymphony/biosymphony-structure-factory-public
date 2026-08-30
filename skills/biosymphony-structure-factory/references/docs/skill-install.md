# Install The Structure Factory Skill

Structure Factory ships two portable agent-instruction entry points:

- `skills/biosymphony-structure-factory/SKILL.md` for campaign planning and orchestration
- `skills/binder-lane-round/SKILL.md` for binder study-shape replay and toolchain comparison

Use that file directly from this repository, or copy the skill directory into another agent environment.

## Repo-Local Use

Open an agent in the repository root and ask it to use the BioSymphony Structure Factory skill. The skill tells the agent to read the release, boundary, harness, compute, licensing, and RunPod guidance before planning work.

Validate the local skill surface:

```bash
make harness-check
```

## Portable Use Outside This Repo

For other agent systems, copy `skills/biosymphony-structure-factory/` into that system's skill or instruction directory, then point the agent at this repository as the working tree.

Minimum prompt:

```text
Use the BioSymphony Structure Factory skill. Plan structural biology work with public or synthetic inputs only. Keep remote execution disabled unless explicitly authorized.
```

## Verify After Installation

Ask the agent to run:

```bash
bsf harness-check .
bsf audit .
```

The agent should report that the skill is a planning/control-plane harness, not a license bypass, wet-lab protocol system, or unsupported-result generator.
