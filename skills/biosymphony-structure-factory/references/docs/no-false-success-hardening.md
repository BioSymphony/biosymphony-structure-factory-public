# No-False-Success Hardening

Structure Factory runs must separate launch mechanics from scientific evidence. Raw cryo-EM movie intake, reconstruction, and map-to-model build execution are CryoCore-owned; Structure Factory validates handoff contracts, gates, and downstream closeout evidence around those lanes.

## Required Artifacts

Every RunPod-capable execution profile now has:

- a repo-committed `runpod/stage-contracts/*.stage-contract.json`
- a runtime `stage-progress.jsonl`
- a `validation/stage-contract-check.json`
- a `validation/input-audit.json`
- CryoCore raw-subset handoff profiles: a `validation/fanout-estimate.json`
- a `validation/contract-self-check.json`
- a `partial-summary.json` whenever a stage fails, closes partial, times out, or uses fallback

Fold and cofold stages that support scoring or ranking must also declare the
confidence sidecars they will preserve: PAE or equivalent interface-error
matrices, per-residue pLDDT, confidence JSON, and hashes. See
[`docs/confidence-sidecars.md`](confidence-sidecars.md). Do not use scalar-only
iPTM, pTM, or complex pLDDT rows as complete interface-scoring inputs.

The stage contract declares stage IDs, expected outputs, timeout budgets, checkpoint markers, done markers, resume commands, partial-summary policy, stale-output policy, and `fail_closed: true`. The progress ledger records `started`, `heartbeat`, `completed`, `failed`, `partial`, or `skipped` events with timestamps.

Stage-contract granularity is part of the control-plane contract. Default to one
stage contract per wave and put shard-specific paths in bridge manifests. If a
campaign uses per-shard stage contracts, the issue template and touched-area
schema must name those concrete files. Run `make issue-file-check` before
dispatch; schema-only issue validation is not enough to prove referenced scripts,
manifests, and contracts exist.

## Fanout Before Expensive Lanes

CryoCore-owned raw cryo-EM lanes can multiply quickly: movies become frames, micrographs,
particles, classes, maps, validation panels, and context annotations. Before
any raw movie transfer or exhaustive context work, prepare the handoff with:

```bash
make screening-fanout-estimate
python3 scripts/structure_factory/fanout_estimator.py \
  --manifest runpod/launch-manifests/raw-subset-open.json \
  --json
```

`validation/fanout-estimate.json` separates primary evidence lanes from context
lanes. Primary evidence can support a partial closeout if context lanes time
out; context artifacts cannot silently turn a failed primary route into
success. Raw tool output is not a deliverable by itself. Downstream workers need
normalized ledgers with provenance, joins to declared accessions/subsets,
evidence class, and review status.

For paid fanout, run a single canary shard through the exact same launch,
watch, artifact pull, hash verification, cleanup, and summary-ledger path before
starting the wider wave. The canary must prove artifact egress, not just pod
creation or proxy allocation.

Launcher scripts that use `set -euo pipefail` must treat expected-missing probe
data as status, not as a shell crash. Avoid `grep | python` or `grep | jq`
pipelines for optional JSON/JSONL lookups unless they are wrapped so cleanup and
summary writing still run. Missing hash ledgers, malformed JSONL rows, absent
artifacts, or proxy 404s should become explicit `HASH_FAIL`,
`MISSING_ARTIFACT`, `PARTIAL`, or `BLOCKED` rows in the fanout summary.

RunPod proxy 404 is not readiness. Only treat proxy probes as useful when the
HTTP status is explicitly allowed and the expected artifact/status/sentinel file
is non-empty and, where applicable, hash-matched.

## Provider Truth

RunPod `desiredStatus: RUNNING` is intent, not proof that the container pulled, started, or executed the workload. A worker must monitor:

- provider actual status
- runtime uptime
- image pull success or failure
- `stage-progress.jsonl` heartbeat and terminal events

A pod with no progress ledger is not a running Structure Factory workflow.

A machine allocation, port mapping, or stable `desiredStatus` still does not
prove the container started. If `runtime.uptimeInSeconds` remains `0` or null
past the launch plateau budget and no status file, sentinel, or
`stage-progress.jsonl` heartbeat appears, classify the attempt as
`provider_start_plateau`. Delete it, record provider fields, cost/rate,
datacenter, machine ID, Network Volume ID, and retry count, and close degraded
or retry once according to the issue contract.

`ssh connection refused` is not by itself diagnostic when the base image was not
supposed to run SSH. Treat it only as supporting evidence that no expected
debug/listener service came up. The stronger evidence is no runtime uptime plus
no workload-owned heartbeat.

Provider cost/rate is also evidence. Immediately after pod creation, compare
actual GPU count, `costPerHr`, and runtime posture with the issue's max-spend
contract. If RunPod rejects a CPU profile or silently routes to a paid GPU
profile above budget, delete the pod and close the lane as blocked/degraded.
Do not let a cost posture mismatch become a long-running "bootstrap in
progress" story.

For bootstrap/setup pods, heartbeats are required when an install can exceed ten
minutes. The heartbeat should include elapsed time, current stage, approximate
software/cache size, and sentinel count. One-shot watchers are not enough;
watchers should keep emitting progress or a stale-heartbeat warning until the
pod exits or is stopped.

## Exact Route Proof

Live readiness must prove the exact route, not just an installed dependency or a
runner flag. A stage that will call `relion_refine`,
`phenix.real_space_refine`, `ChimeraX`, a ModelAngelo command, or a repo-local
Python entrypoint must record that callable path before launch and record the
actual command, exit code, and output paths during execution.

For provider pods, "repo is pinned" means the commit can actually be fetched by
the provider route. A 40-character SHA that exists only in the local worktree is
not evidence. Before a paid launch, the source-delivery check must prove
`git_remote_or_snapshot` refs are reachable from the declared remote URL, or the
issue must explicitly downgrade to a small `inline_commands`/synced-NV posture.

For map/model demos, this means:

- `validation/input-audit.json` records declared PDB/EMDB accessions and source URLs.
- `data-intake-ledger.json` joins those accessions to materialized map/model files and checksums.
- `executed-commands.jsonl` joins stage IDs to command strings, exit codes, and result artifacts.
- `validation/map_model_fit.json` must contain real map/model evidence in live mode; placeholder, reference-only, and metadata-only evidence must downgrade the closeout.
- `validation/contract-self-check.json` fails real mode if any required artifact is mock, dry-run, fixture, provider-search, reference-only, or target-placeholder evidence.

## Private Images

Private GHCR images require runtime registry auth references before launch. GHCR is optional; a public base image plus runtime bootstrap or a dedicated RunPod Network Volume bootstrap is a valid setup posture when it is declared, version-pinned, and verified. The repo may name secret reference variables, but must not contain credentials.

Launch readiness is blocked until:

- the image is digest-pinned
- the repo ref is a 40-character commit SHA
- one configured private-registry auth reference is present at runtime
- Structure Factory pod and Network Volume references pass `make runpod-scope-check`
- `STRUCTURE_FACTORY_REMOTE_LAUNCH_ALLOWED` is explicitly truthy for execution-ready launch

Use:

```bash
make runpod-scope-check
make launch-preflight
python3 scripts/structure_factory/runpod_launch_preflight.py \
  --manifest runpod/launch-manifests/no-download-smoke.json \
  --execution-ready \
  --json
```

The first command is a no-launch prep check and may report blockers without failing. The second command is the real launch gate and fails closed.

## Fallbacks And Partial Success

Fallbacks are allowed only when they are explicit. If a run falls back from RunPod to local, private image to install-at-boot, real data to mock, teammate to subagent, or full route to rescue route, closeout status must be `partial`, `degraded`, `blocked`, or `failed`.

`contract_self_check.py` rejects silent fallback markers and rejects undegraded success after fallback. When any stage fails or closes partial, the runner writes `partial-summary.json` with completed stages, failed stage, resume command, artifact status, and downgraded result boundary. A summary stage placed after an expensive context lane is not enough; the trap/watcher path has to write the partial summary even if later stages never run.

## Stale Output Guards

Persistent volumes are useful for resuming expensive runs, but done markers must
be tied to the actual inputs and code that produced them. Stage contracts now
declare a `stale_output_policy` requiring input hashes, code-ref hashes, and
invalidation on manifest, contract, data-intake, subset-rule, license-gate, or
repo-commit changes. Reusing an old `done_marker` without those joins is a
stale-output risk, not success.

## Mock Evidence

Mock, fixture, dry-run, planned-only, reference-only, or screenshot-only outputs can satisfy prep gates only. Real execution mode rejects `mock_tools`, `mock_gpu`, `dry_run`, and planned raw-data ledgers.
