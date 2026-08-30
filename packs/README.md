# Task Packs

Task packs are tracker-neutral work bundles for agents. They can be imported into Linear, GitHub Issues, Notion tasks, or another queue after public validation.

Current pack:

- `task-packs/binder-design-fast-path-v0/` - four-task binder-design scaffold covering target/window setup, generation readiness, cofold ranking, and report review.

Public task packs should include:

- routing label `sym:structure-factory`
- result boundary
- exact public inputs
- expected artifacts
- owned paths
- dependencies
- risk notes
- validation commands
- `<!-- symphony:schema -->` block

Do not put private tracker IDs, private URLs, provider credentials, private data, or live run logs in a public task pack.

## How To Use A Pack

1. Read the pack README or `pack.yaml`.
2. Validate the source campaign or example:

```bash
bsf validate examples/pd-l1-binder-design-public
```

3. Generate tracker-neutral drafts:

```bash
bsf issue-dry-run examples/pd-l1-binder-design-public --out .runtime/pd-l1-issues
```

4. Review the drafts before importing them into Linear, GitHub Issues, Notion, or another tracker.
5. Keep cloud or GPU issues in backlog until an ignored runtime packet passes its readiness checks and has explicit human authorization.

For the broader workflow, see [`../docs/workflow-map.md`](../docs/workflow-map.md) and [`../docs/linear-orchestration.md`](../docs/linear-orchestration.md).
