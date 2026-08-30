# RunPod Stack

Structure Factory should treat RunPod as an execution plane, not the source of truth. Durable plans, manifests, and issue contracts live in git; heavy runtime state lives on persistent volumes.

Tracked Structure Factory manifests omit credentials, live provider IDs, accepted-license state, and execution authorization. Use them to review the execution contract and validate provider readiness. Then materialize an ignored runtime packet, obtain explicit human authorization, and execute it through a validated adapter or provider client. Keep live identifiers, secrets, logs, fetched artifacts, and cleanup records out of tracked git files.

## Planned Image Families

```text
biosymphony-structure-cryo-core
biosymphony-structure-cryosparc
biosymphony-structure-model-build
biosymphony-structure-ai-design
biosymphony-structure-md-docking
```

## Execution Profiles

```text
no-download-smoke   zero biological downloads; validates repo, GPU, storage, toolcheck, artifact manifest
raw-subset-open     CryoCore handoff profile for EMPIAR-13124 deterministic raw-movie subset; open tools only
raw-subset-gated    CryoCore handoff profile for the same raw subset; enables gated tools only when runtime secrets exist
map-model-report   Public EMDB/PDB map/model downloads only; no raw movies
```

All non-smoke profiles are scratch-only by default. They export only small artifacts and delete raw/intermediate scratch after the operator-reviewed run.

## First Test Mode

Use RunPod Pods, not Serverless, for the first Structure Factory test. The smoke pod should clone a public repo or operator-approved snapshot at a pinned commit, run local Python checks, record GPU visibility, write a manifest to `/workspace/structure-factory/runs/<run-id>/`, and exit without downloading EMPIAR data.

Do not interpret `desiredStatus: RUNNING` as execution progress. The closeout needs provider actual status, runtime uptime, image pull success or failure, and `stage-progress.jsonl` events. A pod that cannot pull the selected image has not started the Structure Factory workflow, even if the provider is still trying to run it.

Treat a pod with allocated machine/ports but `runtime.uptimeInSeconds` stuck at
`0` or null as a provider-start plateau. That state may be transient platform
startup, image pull, or volume mount trouble; RunPod's normal pod status fields
do not prove which. The operational response is the same: stop waiting after the
declared plateau timeout, delete the pod, record machine/datacenter/NV/cost
fields, and retry once. If the same signature repeats on the same placement,
switch placement or volume posture before another paid attempt.

For Symphony-dispatched tests, keep paid RunPod mutation out of the sandboxed
worker. The worker prepares `.symphony-runpod-launch-request.json` after local
validation; trusted host-side `after_run` creates the pod, verifies workload
artifacts, fetches and hashes outputs, deletes the pod, confirms no matching pod
remains, and only then closes Linear as successful.

Source delivery is part of the launch contract. Bridge manifests using
`repo.source: git_remote_or_snapshot` must point at a pushed, remote-fetchable
40-character commit SHA. A local-only branch or local-only SHA will clone and
then fail at checkout inside the pod. `inline_commands` is allowed only for
small/demo workloads whose commands are truly inline or whose `/workspace/repo`
snapshot was deliberately synced and recorded.

Required mounted layout:

```text
/workspace/structure-factory/
  cache/
  datasets/
  models/
  runs/
  scratch/
  software/
  weights/
```

Container disk is scratch only. Anything that should survive termination must be written under `/workspace`.

## Storage Policy

- Use a dedicated Structure Factory RunPod Network Volume for Structure Factory writable state. Tracked templates should use the runtime environment reference `STRUCTURE_FACTORY_RUNPOD_NETWORK_VOLUME_ID`; an ignored runtime packet may carry the resolved owned volume ID after scope validation.
- Do not reuse sibling campaign volumes for writable state. A sibling volume may be mounted read-only only when a tracked issue explicitly authorizes it.
- Use persistent RunPod network volumes for datasets, maps, particle stacks, model weights, tool caches, and long-running outputs.
- Use container disk only for temporary scratch.
- Emit run manifests with software versions, GPU type, image digest, volume paths, and artifact hashes.

## Tool Setup Postures

RunPod setup can use more than one compliant path:

- Public/prebuilt image: public Docker Hub, NVIDIA, or project image with reviewed redistribution posture.
- Private image: GHCR/Docker Hub/private registry with runtime registry auth. This is optional, not required.
- Runtime install to scratch: acceptable for prep/dev or short demos when version pins and commands are recorded.
- Network Volume bootstrap: public base image installs tools/weights once into `/workspace/structure-factory/software` and `/workspace/structure-factory/weights`, or into `/workspace/software` on a dedicated Structure Factory-only volume; later pods verify and reuse that state.

For Structure Factory, the Network Volume bootstrap path is the default alternative when GHCR auth is unnecessary friction or when a tool such as ChimeraX should not be redistributed through a public image. The bootstrap script must be idempotent, version-pinned, and followed by a verifier that records exact versions and hashes. Mutable volume state is not scientific evidence by itself.

## Bootstrap Lessons

Apply these five launch gates:

- Provider intent can change the cost posture. A requested CPU/free route can be rejected or replaced by a paid GPU route, so the bridge must inspect actual `costPerHr`, GPU count, and runtime immediately after pod creation and delete the pod if it exceeds the issue budget.
- Network Volume filesystems can be much slower for many-small-file writes than container scratch. Conda/pip installs, source checkouts, and weight extraction need conservative time estimates, caches, tarball extraction, or prebuilt images when repeated.
- Long installs need recurring heartbeats. A package manager sitting at a silent "installing packages" phase is not proof of death or progress; emit bootstrap heartbeats and stage progress on a fixed interval.
- Upstream refs and URLs must be verified before heavy work. Git refs are resolved before large pip/conda installs, and binary downloads are checked for expected archive magic before extraction.
- License/GUI tools such as ChimeraX are optional downstream gates by default. If the verified download route is unclear, mark ChimeraX `deferred` and let non-render planning, cofold, and report lanes proceed while the render lane stays blocked.
- Zero-uptime pod plateaus are lifecycle failures, not scientific failures. Record them separately from workload exit status so a later retry can still succeed without hiding the provider-start degradation.
- Fanout launchers need a canary shard. The first shard must exercise the same launch, proxy probe, artifact egress, hash verification, cleanup, and summary path before the remaining pods are fired.
- Shell launchers running under `set -euo pipefail` must parse optional JSON/JSONL and status probes defensively. Missing evidence should be recorded as an explicit failed/partial status, not crash the fanout controller before cleanup.
- Proxy 404 is a negative signal. Treat HTTP proxy readiness as valid only when the expected artifact or status endpoint returns an allowed status and non-empty, hash-verifiable content.

## Image And Launch Gate

Private GHCR images are allowed, but only through runtime registry auth references. GHCR is a convenience posture, not a hard dependency for Structure Factory. The repo records reference variable names such as `RUNPOD_GHCR_REGISTRY_AUTH_ID`, not credentials.

The public launch ladder is:

```text
tracked manifest -> template check -> ignored runtime packet -> execution-ready preflight -> explicit human authorization -> validated adapter -> paid create -> artifact/hash/cleanup closeout
```

The tracked manifest does not contain the live values needed for `paid create`. A user and agent may materialize those values under ignored `.runtime/` space. The packet remains a review artifact until the preflight passes and a human explicitly authorizes a validated adapter or provider client to execute it.

Before a real launch, `runpod_launch_preflight.py --execution-ready` must pass:

- image is digest-pinned
- repo ref is a commit SHA
- bridge-manifest repo commit is fetchable from its declared remote URL
- private registry auth reference is present at runtime when a private image posture is selected
- bridge manifests pass `make runpod-scope-check`
- source delivery passes `make runpod-source-check` or `make ls-remote-sha-check`
- launch authorization env is explicit
- stage contract exists in the cloneable repo

Tag-based images and install-at-boot are prep/dev risks unless the issue explicitly selects a bootstrap posture, records the installed versions, and validates the resulting volume state before scientific execution.

## First Public Smoke Target

Use no-download metadata first. If the campaign requires bounded EMPIAR-13124 raw-subset execution, hand it to CryoCore after operator authorization:

```text
examples/empiar-10204-v0/
modules/data-modules/empiar-13124.raw-subset.v1.json
```

The first milestone should prove:

- environment build
- dataset intake ledger
- subset processing or documented dry run
- artifact manifest
- validation gates
- figure report skeleton

## First Honest Raw Subset

The first CryoCore raw-data handoff shape is `EMPIAR-13124`, mouse heavy-chain apoferritin. Structure Factory may keep the metadata, budget, handoff, and downstream report contract; CryoCore owns the downloader, motion/CTF, classification, reconstruction, and map-to-model execution.

Non-cheating rules:

- raw EER movies only
- deterministic file choice by manifest rule
- no deposited maps, models, particles, aligned micrographs, or author stacks during processing
- deposited reference artifacts may be used only after processing for validation/comparison

## Secrets And Licenses

Use runtime environment variables or RunPod secrets for:

- non-public source token or deploy key, when an operator chooses a restricted source-delivery posture
- CryoSPARC license identifier
- Phenix installer/license access
- Rosetta/PyRosetta credentials
- AlphaFold or model-weight gated access

Never commit these values to this repository or Linear.

See `docs/public-repo-and-private-image-policy.md` for the public repo, public image, private image, and runtime-gated tool policy.
