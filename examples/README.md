# Examples

Each example folder contains a public, lightweight campaign manifest and the expected artifact contract that goes with it. Point your agent at one of these to learn the shape of a campaign before scaffolding your own.

Example folders contain compact public fixtures. Store raw datasets, maps, particle stacks, private structures, generated structures, provider logs, and model weights under ignored runtime storage or in a user-selected artifact store.

| Example | Best First? | Time | Use Case | Command | Result Boundary | What You Learn |
| --- | --- | --- | --- | --- | --- | --- |
| `pd-l1-binder-design-public` | Yes | 5 minutes | Binder-design fast path from public interface metadata | `bsf validate examples/pd-l1-binder-design-public` | `computational_candidate` | target-window file, stage contract, candidate ranking contract, validation notes |
| `standalone-local-binder-design` | Yes | 15 minutes | No-private-infrastructure starter path | see folder README for copy-paste command | `planning` | local scaffold and tracker-neutral task drafts |
| `screening-superpowers` | After quickstart | 30 minutes | Local screening fixture and fanout contracts | `make screening-check` | `public_synthetic_demo` | fixture screening outputs, fanout estimate, schema checks under `.runtime/` |
| `empiar-10204-v0` | After quickstart | 5 minutes | Metadata-only CryoCore handoff example | `bsf validate examples/empiar-10204-v0` | `public_demo` | public accession manifest, handoff gates, and expected downstream artifacts |
| `orchestration-fixtures` | Advanced | 30 minutes | Advanced schema fixtures for screening/design orchestration | `make screening-schema-check` | `public_synthetic_demo` / `planning` | schema-valid JSON fixtures |

New examples should start in `.runtime/` via `bsf scaffold-campaign`, then move under `examples/` only after public-release review.

Note: a few screening and artifact schemas retain legacy internal status values such as `candidate` and `processed`. Public campaign manifests and newcomer-facing docs should use `planning`, `public_demo`, `public_synthetic_demo`, `computational_candidate`, `blocked`, or `insufficient_support`.
