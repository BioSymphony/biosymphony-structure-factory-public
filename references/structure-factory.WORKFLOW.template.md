---
tracker:
  kind: linear
  api_key: $LINEAR_API_KEY
  project_slug: "replace-with-structure-factory-project-slug"
  issue_filters:
    labels:
      - "sym:structure-factory"
  active_states:
    - Todo
    - In Progress
  terminal_states:
    - Done
    - Closed
    - Cancelled
    - Canceled
    - Duplicate

campaign:
  mode: direct-done
  routing_label: "sym:structure-factory"
  trust: trusted-local
  integration_owner: trusted-after-run

workspace:
  root: $SYMPHONY_WORKSPACES_ROOT

hooks:
  after_create: |
    rm -rf ./* ./.[!.]* 2>/dev/null || true
    git clone --depth 1 --branch ${STRUCTURE_FACTORY_PUBLIC_REF:-main} https://github.com/BioSymphony/structure-factory.git . || {
      git clone --depth 1 --branch ${STRUCTURE_FACTORY_PUBLIC_REF:-main} https://github.com/BioSymphony/structure-factory.git repo
      shopt -s dotglob && mv repo/* repo/.git . 2>/dev/null; rm -rf repo
    }
    rm -f .symphony-promote-ready .symphony-promoted .symphony-promote-result .symphony-github-handoff .symphony-github-handoff-result .symphony-runpod-launch-request.json

agent:
  max_concurrent_agents: 1
  overlap_aware: true
  max_turns: 30
  auto_stop_when_idle: true
  idle_grace_checks: 3

codex:
  command: 'CODEX_HOME="$SYMPHONY_CODEX_HOME" codex --model <operator-chosen-codex-model> --config ''shell_environment_policy.include_only=["LINEAR_API_KEY"]'' --config model_reasoning_effort=medium app-server'
  approval_policy: never
  thread_sandbox: workspace-write
---

## Public Operator Prerequisites

This template is a public starting point. Before using it with a real
orchestrator, replace the project slug, branch/ref, workspace root, and Codex
home placeholders with operator-owned values.

Required outside this repo:

- Linear API key or another tracker adapter
- Symphony workspace root
- Codex home for worker sessions
- pushed public repo ref for workers to clone
- validated provider client and explicit human authorization for paid cloud mutation

Without that runtime setup, use this file as a workflow shape and
run the local CLI/Make checks directly.

You are working on Linear issue {{ issue.identifier }} for BioSymphony Structure Factory.

Title: {{ issue.title }}

Body:
{{ issue.description }}

## Required behavior

- Read `AGENTS.md`, `README.md`, and relevant campaign/module docs before editing.
- Use `skills/biosymphony-structure-factory/SKILL.md` as the repo-local agent-instruction entry point when relevant.
- Keep changes bounded to the issue `## Touched Areas`.
- Do not launch RunPod, local heavy jobs, SSH/HPC jobs, cloud/neocloud instances, download raw EMPIAR data, install restricted tools, or write secrets from the worker shell. For authorized RunPod smokes, validate and prepare a launch request marker for trusted host-side closeout.
- Run validation commands exactly as written.
- Treat RunPod as the default reviewed remote path, but keep campaign science provider-neutral and preserve input-audit plus contract-self-check gates for every backend.
- Use `$symphony-linear` for Linear comments, state changes, and handoff metadata.
- Move completed non-RunPod prep issues directly to `Done` after self-review and validation. For trusted RunPod smokes, do not move the issue to `Done`; the host-side `after_run` closeout owns the final state after artifact proof and cleanup.
- Write `.symphony-runpod-launch-request.json` only after local validation passes. It must include issue identifier, manifest path, max spend, requested action `create_verify_cleanup`, and result boundary.
- Post a final Linear comment with a `<!-- symphony-outcome -->` block containing status, files touched, validation summary, and suggested action.
