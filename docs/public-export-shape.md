# Public Export Shape

Last reviewed: 2026-05-13

This public repository preserves the working shape of Structure Factory: campaign contracts, validator scripts, provider launch contracts, task packs, validation records, and bounded demos. The public export keeps local-only history and operator-specific material out while keeping the workflow understandable.

## What Should Match The Operating Model

Keep these areas substantially isomorphic so public users and Symphony workers can understand the real system:

| Area | Public shape | Why it is useful |
| --- | --- | --- |
| `campaigns/` | Public campaign specs, wave plans, and task drafts | Shows how a structural biology request becomes bounded work. |
| `docs/` | Architecture, safety policy, RunPod/provider posture, tool licensing, and lessons | Lets users judge result boundaries and operational maturity. |
| `modules/` | Data, lane, provider, image, artifact, and schema contracts | Gives agents machine-readable workflow structure. |
| `examples/` | Small public or synthetic fixtures that validate locally | Provides a fast path for adoption without private data. |
| `demos/` | Curated public result narratives and summaries | Shows the intended report style without publishing raw/heavy outputs. |
| `runpod/` | Public launch templates, manifests, stage contracts, and entrypoints | Documents provider expectations while keeping paid launch gated. |
| `scripts/` | Validators, materializers, dry-run generators, and stage checks | Makes the repo executable, not only descriptive. |
| `templates/` and `packs/` | Tracker-neutral task templates and task packs | Supports Symphony/Linear import without leaking private tracker IDs. |
| `tests/` | Public release, validator, and runner tests | Keeps the public export continuously checkable. |

## What Stays Out

The public export should not carry:

- non-public git history or branch archaeology
- local `.runtime/` artifacts, provider logs, cost logs, event logs, or generated closeout bundles
- repo-local agent configuration folders, personal agent settings, or local automation state
- run-specific notes, operator handoffs, account-specific runbooks, or private tracker text
- raw cryo-EM data, half-maps, generated structures, model weights, videos, archives, or other heavy artifacts
- API keys, tokens, registry credentials, license files, signed URLs, private installer links, concrete pod IDs, concrete volume IDs, or local workstation paths
- unpublished structures, private sequences, private ligand libraries, patient data, or confidential collaborator material

Public docs may name gated tools and provider patterns, but they must use placeholders and runtime-secret references. A public repo can explain how to prepare a gated lane; it should not publish credentials, proprietary installers, accepted-license state, concrete provider placement, embedded launch payloads, or heavy generated outputs.

## Public Positioning

Structure Factory is a skill repo for structural biology work programs. It helps agents turn broad structural biology requests into bounded work:

- turns vague target requests into target windows, stage contracts, task packs, and validation commands
- keeps Boltz/Genie/RFdiffusion-style design lanes behind explicit setup, license, runtime, and result gates
- separates generation, scoring, cross-checking, and reporting so failures and partial success are visible
- produces candidate rankings and structure reports that are useful for scientist review without implying wet-lab proof
- lets Linear/Symphony workers coordinate long-running GPU work without losing provenance, cost, cleanup, or artifact hashes

For computational binder-design campaigns, Structure Factory shortens the setup, planning, triage, and reporting loop. Binding, affinity, specificity, biological function, developability, safety, and therapeutic value require separate review and experiments.

## Release Bar

A public export is in good shape when:

1. `make public-switch-check` passes.
2. `make public-audit` reports no findings.
3. A strict local-path/private-token search reports no findings.
4. No heavy generated artifacts are tracked.
5. The first commit is a reviewed public root commit.
6. Public examples validate without network, credentials, GPU, or paid provider access.
