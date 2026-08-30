# Result Boundaries And Source Posture

Structure Factory is useful when outputs stay tied to what actually ran. Use this guide when writing manifests, task packs, closeouts, reports, or provider runbooks.

## Public Result Boundaries

Use these values in public-facing campaign manifests, task packs, reports, agent closeouts, and docs:

| Result Boundary | Use When | Does Not Mean |
| --- | --- | --- |
| `planning` | The work defines scope, inputs, lanes, checks, or provider prep | A model was generated or reviewed |
| `public_demo` | The result demonstrates a workflow on public deposited data | New biology was proven |
| `public_synthetic_demo` | The result uses synthetic fixture data or toy outputs | Real screening/design support exists |
| `computational_candidate` | A generated, predicted, ranked, or rescored item may be worth review | Binding, function, safety, efficacy, selectivity, or therapeutic value |
| `insufficient_support` | The available artifacts do not support the requested statement | The hypothesis is false |
| `blocked` | A lane could not proceed because of missing data, tool, license, provider, cost, or authorization | The scientific question is resolved |

If support is partial, missing, mocked, dry-run, or fallback-derived, lower the result boundary instead of calling the run successful.

## Source Posture

Source posture describes where the artifact came from. Result boundary describes how far the output can be taken. Keep both visible.

| Source Posture | Meaning | Typical Result Boundary |
| --- | --- | --- |
| `report_only` | A plan, review, or checklist with no new computation | `planning` |
| `public_data` | Public deposited accession metadata, map/model files, or validation reports | `public_demo` |
| `synthetic_demo` | Small toy or fixture data designed for public examples | `public_synthetic_demo` |
| `generated_candidate` | Generated sequences, structures, poses, or designs | `computational_candidate` |
| `provider_native` | Artifacts emitted by the selected runtime/provider lane | depends on artifact and checks |
| `derived` | Local aggregation, rescore, conversion, or figure derived from earlier artifacts | no higher than source support |
| `blocked` | A required stage could not run | `blocked` |
| `insufficient_support` | A stage ran or produced something, but it does not support the requested statement | `insufficient_support` |

Provider state is not source posture. A pod, job, process exit code, or scheduler state only proves intent until artifacts are fetched, parsed, hashed, and joined to the declared inputs.

## Legacy Schema Values

Some low-level schemas and older stage contracts still contain machine values such as `candidate`, `processed`, `validated`, `publishable`, `fixture_or_demo`, or `calibrated`. Treat those as compatibility values for old artifacts, not as public release language.

| Legacy Or Machine Value | Public-Facing Translation |
| --- | --- |
| `candidate` | `computational_candidate` |
| `processed` | `public_demo` only when the artifact joins to public inputs and validation ledgers |
| `fixture_or_demo` | `public_synthetic_demo` unless it uses real public deposited data |
| `validated`, `publishable`, `calibrated` | Avoid in public closeouts unless an explicit external validation/review gate exists; otherwise use `public_demo`, `computational_candidate`, or `insufficient_support` |

When in doubt, write the stricter public value and add a note that an older schema field is being preserved for backward compatibility.

## Closeout Rules

Every public closeout should state:

- input posture: public, synthetic, generated, private-held, or blocked
- source posture
- result boundary
- validation commands run
- artifact packet path or `n/a`
- hash ledger path or `n/a`
- cost report and cleanup proof for paid/provider-backed runs
- downgrade reason when support is partial, derived, mocked, or missing

Never close a Structure Factory run as successful from provider launch, provider `RUNNING`, a process exit code, screenshots, placeholder outputs, or a report without artifact joins.

## Examples

Binder design planning:

```yaml
source_posture: report_only
result_boundary: planning
boundary_note: Target window and lane contract only; no generated structures or binding support.
```

Synthetic screening fixture:

```yaml
source_posture: synthetic_demo
result_boundary: public_synthetic_demo
boundary_note: Fixture demonstrates schema and fanout mechanics only.
```

Generated design ranking:

```yaml
source_posture: generated_candidate
result_boundary: computational_candidate
boundary_note: Ranking is computational triage; external validation is required before biological conclusions.
```

Provider-backed closeout after missing artifacts:

```yaml
source_posture: insufficient_support
result_boundary: insufficient_support
boundary_note: Provider job started, but required artifacts were not fetched and hash-joined.
```
