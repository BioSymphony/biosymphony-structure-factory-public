# Linear Orchestration

Linear is optional, but it is the clearest way to run Structure Factory as a durable multi-agent workflow. The same contracts can be adapted to GitHub Issues, Notion tasks, or another queue.

For the full local-to-tracker-to-cloud ladder, see [`workflow-map.md`](workflow-map.md).

## Newcomer Flow

1. Create or validate a local campaign scaffold.

```bash
bsf validate examples/pd-l1-binder-design-public
```

2. Render tracker-neutral task drafts.

```bash
bsf issue-dry-run examples/pd-l1-binder-design-public --out .runtime/pd-l1-issues
```

3. Review the drafts before import. They should have public inputs, result boundaries, owned paths, dependencies, validation commands, expected artifacts, risk notes, and operator-gate status.

4. Import into Linear only after removing local-only paths and confirming there are no credentials, provider IDs, private URLs, raw data references, generated structures, or launchable provider packets.

5. Keep most work in `Backlog`; activate only the current wave in `Todo`.

6. For cloud or provider work, require an ignored runtime packet, readiness checks, and explicit human authorization before execution.

## Campaign To Linear Procedure

Use this exact sequence when turning a public campaign into Linear work:

1. Scaffold or choose the campaign.

```bash
bsf validate examples/pd-l1-binder-design-public
```

2. Render review drafts under ignored runtime space.

```bash
make issue-dry-run
make issue-dry-run-check
```

3. Decide whether to import the generated campaign-specific drafts or adapt a task pack from [`../packs/`](../packs/). Pack tasks are reusable starter contracts; generated drafts are tied to the selected campaign manifest.

4. In Linear, create or select a project and labels:

```text
sym:structure-factory
campaign:<campaign-id>
provider:<provider>
wave:<wave-id>
gate:<gate-id>
risk:<risk-id>
```

5. Put future, cloud, GPU, raw-download, or license-gated work in `Backlog`.

6. Move only the current wave to `Todo`. Start with one Symphony worker until the no-download and task-contract gates pass.

7. Attach the relevant workflow template from [`../references/`](../references/) only after replacing public placeholders with operator-owned values.

8. Provider-backed tasks move to `Done` only after artifacts, hashes, cost report, cleanup proof, and validation review pass. Local prep can close directly when validation passes.

## Skill Composition

Structure Factory task contracts add domain-specific provider, profile, stage, and validation gates on top of the base Symphony task schema. They do not replace the shared Symphony rules.

- Orchestrator setup, workflow metadata, monitoring, and wave review: the operator's Symphony orchestration skill bundle.
- Worker tracker operations: the operator's Linear or GitHub task skill bundle.
- Optional visual or review lanes: any reviewer skill bundle approved by the operator.
- Structure Factory domain gates: `skills/biosymphony-structure-factory/SKILL.md`

New workflows must declare `campaign.mode`, `campaign.routing_label`, `campaign.trust`, and `campaign.integration_owner` in the workflow file. Use the base task sections from Symphony ops plus the Structure Factory additions in `templates/linear-issue.md`.

## Required Task Shape

Every Structure Factory task should answer these questions before a worker starts:

| Question | Required Answer |
| --- | --- |
| What is the biological scope? | target, accession, window, and run boundaries |
| What can this task produce? | source posture and result boundary |
| Where may the worker edit? | owned repo paths and ignored runtime paths |
| What provider is selected? | `local`, `runpod`, `aws`, `ssh-hpc`, `generic-cloud`, `neocloud`, or `provider-neutral` |
| Is this cost-bearing? | operator gate, budget/runtime cap, cleanup policy, or `n/a` |
| What proves success? | expected artifacts, validation commands, stage contract, and closeout policy |
| What blocks or limits success? | license, secret, provider, data, cost, or missing-output risks |

If a task cannot answer those questions, leave it in `Backlog` or treat it as planning only.

## Cross-Inventory Gate

`scripts/structure_factory/issue_check.py` is a schema gate by default. Before dispatching a generated task wave, run file-reference mode so referenced repo-controlled paths are checked against the actual checkout:

```bash
make issue-file-check
python3 scripts/structure_factory/issue_check.py campaigns/<campaign>/linear-issues --check-file-references --json
```

This catches task templates that name a non-existent script, launch manifest, bridge manifest, stage contract, or other source-controlled path. It intentionally focuses on repo-controlled paths; runtime artifacts under `.runtime/`, `runpod-execution/`, `artifacts/`, and `outputs/` are validated by stage contracts and contract self-checks after execution.

Stage-contract granularity must be declared before task generation. The default is one stage contract per wave, with per-shard IDs and inputs carried by bridge manifests. Use per-shard stage contracts only when the campaign explicitly declares that granularity and the corresponding files exist.

## Routing

Every Structure Factory Symphony task should use:

```text
sym:structure-factory
```

Additional campaign labels:

```text
campaign:empiar-10204-v0
family:cryoem-raw-to-atomic
```

## Wave Labels

```text
wave:00-control
wave:01-provider-prep
wave:02-smoke
wave:03-data
wave:04-processing
wave:05-model-map
wave:06-report
```

## Gate Labels

```text
gate:contract
gate:environment
gate:data-intake
gate:processing
gate:model-map
gate:figure
gate:validation-review
```

## Lane Labels

```text
lane:cryo-core
lane:cryosparc
lane:model-build
lane:ai-design
lane:md-docking
lane:figure
lane:audit
```

## Risk Labels

```text
risk:license-gated
risk:large-download
risk:gpu-cost
risk:secret-required
risk:gui-required
risk:human-authorization
```

## Provider Labels

```text
provider:runpod
provider:local
provider:aws
provider:ssh-hpc
provider:generic-cloud
provider:neocloud
```

| Provider | Public Repo Action | Operator Gate | Validation Entry |
| --- | --- | --- | --- |
| `local` | prep, fixtures, small local checks | only for heavy/private/local raw data | `make release-check` |
| `runpod` | tracked templates, scope checks, launch bundles | explicit human authorization required for pod creation | `make runpod-public-template-check` |
| `aws` | provider profile and packet dry-run | required for AWS Batch/EC2 mutation | `make provider-check` |
| `ssh-hpc` | adapter contract only | required for scheduler submission | `make provider-check` |
| `generic-cloud` | adapter contract only | required for VM/pod mutation | `make provider-check` |
| `neocloud` | adapter contract and scope posture | required for pod mutation | `make neocloud-scope-check` |

RunPod is the default reviewed paid-pod provider for the first Structure Factory demos. AWS Batch is the reviewed cloud-scale provider after adapter closeout parity. SSH/HPC, generic cloud, and neocloud labels are for adapter planning or local prep unless a task explicitly authorizes provider-specific execution.

## State Policy

- `Backlog`: default for future or cost-bearing work.
- `Todo`: only the current active wave.
- `In Progress`: active Symphony worker.
- `In Review`: gate check, snapshot/manual integration, or human/operator review.
- `Blocked`: license, secret, provider, data, cost, or authorization blocker.
- `Done`, `Canceled`, `Duplicate`: terminal states.

Start Structure Factory with `max_concurrent_agents: 1` until Wave 0 passes. Increase to 3 only after repo, workflow, task contracts, and no-download manifests are validated.

## Outcome Convention

Every final worker comment must include a parseable `<!-- symphony-outcome -->` block with `outcome_version: 1`.

- Codex workers use the `symphony-linear` skill and worker-safe `linear_graphql` tool.
- All workers use the public outcome contract and record source posture, result boundary, validation, artifacts, and any required integration state.
- Trusted-after-run RunPod closeout may move a task to `Done` only after declared artifacts are fetched, validated, hashed, scanned, and cleanup is verified.
- Snapshot/manual-integration workers move to `In Review`; the orchestrator or trusted hook moves to `Done`.

Provider success is never enough for the outcome block. The outcome must state the workload status, source posture, result boundary, validation summary, artifact packet path, hash ledger, cleanup proof, cost report when applicable, and any degraded/partial fallback.

## Importing Public Packs

Task packs under [`../packs/`](../packs/) are safe starting points because they are tracker-neutral. A typical import flow is:

1. Run the pack or example through `bsf validate`.
2. Generate task drafts with `bsf issue-dry-run` or copy the pack Markdown.
3. Run `scripts/structure_factory/issue_check.py` on the generated drafts.
4. Import to Linear with labels from this document.
5. Put provider-backed tasks in `Backlog` until authorization exists.
6. Keep closeout records compact: hashes, provenance, validation notes, and links to operator-held artifact packets.

Do not paste provider secrets, pod IDs, non-public repository URLs, private tracker URLs, local absolute paths, raw data locations, or accepted-license state into public task packs or public Linear templates.
