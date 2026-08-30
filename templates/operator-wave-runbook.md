# Operator Wave Runbook

Use this template for paid compute, raw public-data intake, cloud launch, SSH/HPC submission, license-gated tools, or multi-agent dispatch. Keep the filled copy in an operator-controlled record outside public Git. A public campaign can include a sanitized copy.

Do not paste credentials, provider resource IDs, private tracker text, private workstation paths, unpublished biological data, or raw provider logs into this record.

## Campaign

- campaign ID:
- routing label: `sym:structure-factory`
- tracker or queue:
- wave:
- provider: `<local | fal | modal | runpod | lambda-cloud | aws-batch | ssh-hpc | generic-cloud | neocloud | provider-neutral>`
- execution method: `<platform-skill | hosted-api | self-hosted | mixed>`
- adapter or skill ID:
- execution profile:
- setup posture:
- operator gate issue:
- result boundary:
- source posture:

## Pre-Wave Gate

- [ ] Previous wave closed with expected artifacts, hashes, and result boundary.
- [ ] Current issue batch is bounded and dependencies are explicit.
- [ ] Stage contract exists or the issue explains why `n/a` is acceptable.
- [ ] Expected artifacts are listed with required/optional status.
- [ ] Progress ledger path is declared.
- [ ] Resume command is declared.
- [ ] Partial-success policy is declared.
- [ ] Public/private data posture is declared.
- [ ] License and tool posture is declared.
- [ ] Operator authorization is explicit for paid, raw-download, cloud, SSH/HPC, or license-gated work.
- [ ] Budget and runtime caps are explicit.
- [ ] Cleanup policy is explicit.

## RunPod-Specific Gate

RunPod has the repository's most detailed paid-pod templates. Provider status records intent; stage progress, artifacts, hashes, and cleanup proof establish workload completion.

- [ ] `make runpod-scope-check` passes.
- [ ] `make launch-preflight` or the campaign-specific launch preflight passes.
- [ ] Bridge manifest uses a public placeholder such as `STRUCTURE_FACTORY_RUNPOD_NETWORK_VOLUME_ID` or an operator-approved private record outside the public repo.
- [ ] Image posture is declared: public digest-pinned image, private image with runtime registry auth, runtime bootstrap, or Network Volume bootstrap.
- [ ] Source posture is declared: pushed immutable commit, reviewed source archive, or intentionally small `inline_commands`.
- [ ] No sibling campaign pod, Network Volume, template, or registry auth is targeted.
- [ ] Expected artifact fetch path is declared.
- [ ] Cleanup verification path is declared.

## Multi-Agent Dispatch Gate

- [ ] Worker lane is declared: `codex`, `claude`, `trusted-after-run`, or another named lane.
- [ ] Concurrency cap is declared.
- [ ] First shard/canary exercises launch, progress, artifact pull, hash check, cleanup, and summary writing.
- [ ] Remaining issues stay in backlog until the canary passes.
- [ ] Workers close provider-backed issues to review, blocked, or partial unless the workflow explicitly supports direct closeout.
- [ ] Final comments include `<!-- symphony-outcome -->` or an equivalent machine-readable outcome block.

## Wave Promotion Record

```text
Wave:
Date:
Operator:
Issues promoted:
Max spend:
Max runtime:
Provider profile:
Setup posture:
Expected artifact packet:
Cleanup proof:
Result boundary:
Notes:
```

## Done Definition

Close the wave after these checks pass:

- [ ] Tracker state matches the intended closeout state.
- [ ] Required artifacts exist and are non-empty.
- [ ] Hash ledger joins artifacts to declared inputs, code/ref, commands, and stage contract.
- [ ] Validation commands passed or failures are recorded as partial, degraded, blocked, or insufficiently supported.
- [ ] Provider resources were deleted or retention is explicitly authorized.
- [ ] Cost report is recorded for paid work.
- [ ] Validation notes state the supported and unsupported conclusions.
- [ ] Public report distinguishes provider-native, derived, fixture/demo, report-only, and insufficiently supported outputs.

## Stop Conditions

Stop the wave and block or mark the closeout partial if any of these occur:

- provider status shows running but no workload heartbeat or stage progress appears within the declared plateau window
- artifact proxy returns missing, empty, malformed, or HTML error bodies
- actual provider cost, GPU class, or runtime exceeds authorization
- required artifact hashes are missing or do not match
- a worker marks scientific success from pod creation, scheduler state, process exit, screenshots, or placeholder outputs
- private data, credentials, provider IDs, local paths, or raw logs appear in public files
- a license-gated tool is installed, run, or redistributed without the declared user context and operator approval
- any mutating cloud operation targets a resource outside the campaign scope
