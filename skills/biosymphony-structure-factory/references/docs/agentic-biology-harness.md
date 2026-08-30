# Agentic Biology Harness

Last reviewed: 2026-05-13

BioSymphony Structure Factory stores structural biology work as campaign manifests, stage contracts, task packs, provider profiles, and result records.

The repo helps turn an open-ended biological request into a bounded work program:

```text
biological goal
  -> target window or structure set
  -> task plan
  -> agent lanes with owned paths
  -> RunPod or local/cloud execution profile
  -> artifacts, hashes, progress, and cleanup
  -> candidate ranking, reports, and figures
```

## What It Is For

Use Structure Factory when the useful work is bigger than one prompt:

- binder-design triage against a public target window
- Boltz, Genie/RFdiffusion-style generation setup, and cofold/model-comparison review
- CryoCore handoff, deposited PDB/EMDB structures, or structure-mapping planning
- GPCR or multimer state comparison with artifact provenance
- cloud GPU stage contracts that need budget, cleanup, and proof gates
- publication-style structural reports with explicit source posture and result boundaries
- Linear or similar tracker workflows where agents need durable campaign contracts

The repository carries manifests, schemas, task packs, validators, stage contracts, launch templates, and compact public demos. Store raw biological data, provider logs, private structures, model weights, and credentials under ignored runtime storage or in a user-selected artifact store.

## Drive Any Agent Stack

Structure Factory plugs into any orchestrator the user already runs: Codex, Claude Code, Symphony with Linear, a `/goal` command stack, GitHub Issues, Notion tasks, or any custom queue. The orchestrator decomposes goals, inspects files, picks local or cloud resources, and dispatches workers. Structure Factory provides the parts that are easy to lose in a long-horizon agent run:

- domain-specific intake defaults and run boundaries
- campaign manifests, stage contracts, expected artifacts, and provider profiles
- tracker-neutral task shapes with owned paths and validation commands
- local validators that catch privacy, launch, and false-success problems
- examples and recipes that show a capable agent where to start

When the contract, safety gates, and validation surface are present, an orchestrator can fill routine glue work directly. Reach for the repo's bespoke recipes for missions where the biology-specific shape matters.

For `/goal` style setups, the translation is:

```text
user goal
  -> Structure Factory skill
  -> campaign contract or existing example
  -> task pack or task queue when the work exceeds one turn
  -> local or provider prep gates
  -> checked outputs and reviewable closeout
```

## Public Outputs

The public workflow can produce target windows, campaign manifests, stage contracts, tracker-neutral task drafts, provider templates, candidate-ranking schemas, and structure-report specifications. Generated or predicted biology remains `computational_candidate` work until independent validation supports a narrower statement.

## Skill Surfaces

The repository exposes three checked interfaces:

| Surface | Path | Purpose |
| --- | --- | --- |
| Agent instructions | `skills/biosymphony-structure-factory/SKILL.md` | Portable operating rules for agents and orchestration workers. |
| Binder comparison instructions | `skills/binder-lane-round/SKILL.md` | Toolchain comparison, license, routing, handoff, and synthetic-report rules. |
| CLI gates | `src/biosymphony_structure_factory/cli.py` | Public audit, campaign validation, issue dry-run, and harness readiness checks. |

The skill is the recommended entry point for agents. The CLI is the guardrail that keeps examples, release posture, and the harness surface checkable.

## Symphony And Linear Role

Structure Factory works best as a BioSymphony sidecar:

- Symphony owns worker dispatch, bounded concurrency, wave review, and outcome parsing.
- Linear or a similar tracker owns durable issue contracts, state, dependencies, and comments.
- Structure Factory owns the domain-specific biological contract: inputs, lanes, result boundaries, provider profile, stage contract, expected artifacts, validation commands, and closeout notes.

The key label is:

```text
sym:structure-factory
```

Task packs should stay tracker-neutral enough to import into Linear, GitHub Issues, Notion tasks, or another queue. The public examples use Linear language because that is the current BioSymphony orchestration path, but the pattern is not locked to Linear.

Optional review workers can run as separate lanes. They review figures, reports, or biological plausibility and close with the same source posture, result boundary, validation summary, and artifact references.

## RunPod Execution Contract

The `runpod/` directory contains the repository's most detailed provider templates, stage contracts, and scope checks. Tracked templates omit launch authorization and concrete provider resources. A user and agent materialize the executable packet below ignored `.runtime/` space, run the checks, and record bounded human authorization before a paid provider start or non-public upload.

The RunPod path preserves this verification flow:

```text
manifest
  -> input audit
  -> launch preflight
  -> stage-progress ledger
  -> expected artifacts
  -> artifact fetch and hashes
  -> cleanup proof
  -> contract self-check
  -> tracker closeout
```

Other provider profiles must satisfy the same contract:

- AWS Batch for cloud-scale or multi-shard GPU jobs
- SSH/HPC where institutional data or licenses must stay on site
- local high-resource workstations for prep, small runs, or GUI review
- generic cloud/neocloud pods when provider-specific cleanup and artifact export are proven

The default public docs should use placeholders and runtime-secret references. Public users can choose public base image plus runtime bootstrap, a dedicated RunPod Network Volume, a private image with registry auth, or an institutional runtime. The issue must declare the posture before launch.

## Canonical Workflow

1. **Intake**
   Define target, public accession or safe local reference, desired output, source posture, privacy posture, runtime constraints, and result boundaries.

2. **Contract**
   Create or update `campaign-manifest.json`, target-window file, stage contract, expected artifacts, and validation notes.

3. **Task Pack**
   Render tracker-neutral issues with owned paths, dependencies, validation commands, risk notes, operator gates, and `sym:structure-factory` routing.

4. **Preparation**
   Validate schemas, run public audit, check tool/license posture, and keep cost-bearing work in backlog until authorized.

5. **Execution**
   Use local prep for no-download checks. Use RunPod when a real remote GPU profile is selected and authorized. Emit progress, artifacts, and hashes.

6. **Closeout**
   Compare artifacts to the stage contract, label partial work honestly, attach result boundaries, and produce a candidate ranking or structure report.

## Public Release Minimum

A public release should pass:

```bash
make harness-check
make release-check
make secret-scan
```

`make harness-check` verifies that the public repo still exposes the skill, docs, task pack, RunPod posture, and orchestration entry points expected by BioSymphony users.
