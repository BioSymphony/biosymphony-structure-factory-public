# Compute Backends

Structure Factory records local and remote execution contracts. A provider profile describes a selected route; it does not establish account access, installation readiness, or a completed biological result.

Profiles cover RunPod Pods, AWS Batch GPU jobs, FAL and Modal serverless GPU jobs, Lambda Cloud GPU VMs, generic cloud VMs, neocloud pods, and SSH/HPC. Every route uses the same input, artifact, cleanup, and closeout checks.

For the newcomer route map, see [`workflow-map.md`](workflow-map.md). Keep credentials and live provider identifiers in ignored runtime state. Before a paid provider start or non-public upload, obtain approval for the named route, data posture, budget, and runtime.

## Public To Cloud Workflow

| Phase | Stored In Public Git | Stored Outside Public Git |
| --- | --- | --- |
| Local contract | campaign manifest, target-window file, validation notes, stage contract | private target notes, unpublished sequences, local data |
| Tracker plan | tracker-neutral task drafts, validation commands, risk notes | private tracker URLs, live comments with secrets, operator approvals |
| Provider prep | tracked templates, provider profiles, scope checks, runtime-secret reference names | live pod IDs, concrete placement, accepted-license state, credentials |
| Provider run | expected artifact list, schema, closeout checklist | logs, raw outputs, generated structures, model weights, provider archives |
| Closeout | compact report, hashes, provenance summary, result boundary | heavy artifacts and private result packets |

Use this sequence for a remote stage:

```text
local contract -> provider profile -> readiness check -> explicit approval -> execution -> verified closeout
```

Close a remote stage only after expected artifacts are exported, parsed, hashed, checked, and accompanied by cleanup proof and validation notes.

## Setup Postures

The files, data, tools, and weights can be assembled in several valid ways. The chosen posture is an execution detail, not a different science contract.

| Posture | Where Setup Happens | Best Use | Required Guardrail |
| --- | --- | --- | --- |
| Public/prebuilt image | Pulled by provider | Open-default tools with redistributable binaries | Digest pin before real launch |
| Private image | GHCR/Docker Hub/registry | Fast cold start for reviewed private stacks | Runtime registry auth; no secrets in image layers |
| Runtime bootstrap | Pod boot or job prologue | Public base image plus pinned installs | Record commands, versions, and bootstrap risk |
| RunPod Network Volume bootstrap | A setup run populates an owned runtime cache | Repeated tool or weight use without a private registry | Dedicated volume, idempotent bootstrap, and per-run verification |
| Local high-resource workstation | User machine | Small demos, GUI review, local-only campaigns | No large/raw downloads without explicit local authorization |
| SSH/HPC modules | Institutional cluster | Data or licenses must stay on site | Same artifact tree and self-check output |
| Generic cloud/neocloud volume | Provider volume or object store | Cloud capacity with runtime storage | Must preserve scoping, secrets, artifact export, and cleanup policy |
| FAL serverless GPU job | User-selected FAL client and runtime | Bounded GPU canaries and small jobs without a long-lived pod | Declared concurrency, timeout, budget; fetched+hashed artifacts; cleanup record |
| Modal serverless function | User-selected function image | Bounded GPU canaries and small fanouts without a long-lived pod | Declared concurrency, timeout, storage, budget; exported and hashed artifacts; cleanup record |
| Lambda ephemeral GPU VM | Short-lived instance, no persistent disk | Single no-filesystem canaries with fast-terminate discipline | Egress + remote-archive hash + immediate terminate + post-terminate listing |

A private registry, runtime bootstrap, and a runtime cache are optional setup postures. Select the posture that satisfies the selected tool's license, data, artifact, and cleanup requirements.

## Backend Classes

| Backend | Class | Intended Use | Status |
| --- | --- | --- | --- |
| RunPod | `pod` | No-download smoke, CryoCore handoff prep, gated tools, PDB/EMDB structure mapping, AI-design runtime | Reviewed profile |
| AWS Batch | `batch_job` | Cloud-scale lanes and multi-shard GPU jobs | Profile available |
| FAL | `serverless_function` | Bounded GPU canaries and small jobs through a user-selected client or API adapter | Requires validated adapter |
| Modal | `serverless_function` | Bounded single-function GPU canaries and small fanouts | Profile available |
| Lambda Cloud | `cloud_vm` | Ephemeral single-instance GPU canaries with no persistent filesystem | Profile available |
| Local workstation | `workstation` | Repo validation, figure review, and local tasks | Local contract |
| SSH/HPC | `slurm_job` | Institutional GPU or CPU batch lanes where licenses/data stay on site | Requires validated adapter |
| Generic cloud VM | `cloud_vm` | GPU VM with mounted disk or object storage | Requires validated adapter |
| Neocloud GPU pod | `gpu_pod` | GPU pod with private-image and scratch-volume support | Requires validated adapter |

## Required Provider Contract

Every provider profile should declare:

- `provider`
- `provider_class`
- `profile_id`
- `maps_campaign_profile`
- `workspace_root`
- `artifact_root`
- `secret_mode`
- `operator_gate_required`
- `execution_ready_requires`
- provider-specific storage, GPU, image, scheduler, or connection fields

Every provider must support the same verification flow:

```text
manifest -> input audit -> materialized inputs -> run artifacts -> contract self-check -> closeout
```

## Closeout Requirements

- A submitted job, launched pod, passing process exit code, or `--full-run` flag does not complete a stage.
- Reject a result when required outputs contain `mock_gpu`, `mock_tools`, or `dry_run`.
- A raw-data download requires explicit approval; an environment default does not grant it.
- Keep heavy data in the selected runtime store. Public Git receives only manifests, small reports, provenance, hashes, and validation notes.

## Backend-Specific Notes

### RunPod

Use the `runpod/` launch kit for public templates, stage contracts, and preflight checks. Keep image credentials and license secrets in runtime configuration. Write durable artifacts under the declared runtime artifact root.

Use a runtime reference for an owned volume after scope validation. Do not reuse a writable volume from another campaign. Before a paid mutation, run `make runpod-scope-check` and verify that the requested resources match the selected contract.

### AWS Batch

Use AWS Batch for cloud-scale work when the selected contract records budget, artifact export, and cleanup proof. AWS EC2 debug VMs require the same input-audit and contract-self-check gates.

### Modal

Use Modal serverless GPU functions for bounded canaries and small fanouts. Declare concurrency, timeout, storage, budget, and cleanup before execution. Closeout requires exported artifacts, exact counts, hashes, validation notes, and cleanup proof. Keep credentials and raw provider records outside public Git. Profile: `modules/provider-profiles/modal/gpu-function-no-download.v1.json`.

### FAL

Use the FAL profile with a user-selected client or API adapter for bounded serverless GPU jobs. The user chooses the model or container, reviews its terms and data handling, and supplies runtime authentication outside the repository. Declare concurrency, timeout, retries, and spend before launch. Closeout requires exported artifacts, exact counts, hashes, validation notes, and the applicable cleanup record. Profile: `modules/provider-profiles/fal/serverless-gpu-no-download.v1.json`.

### Lambda Cloud

Use Lambda Cloud GPU VMs for short-lived, no-persistent-filesystem canaries. Export artifacts, verify the archive hash, terminate the instance, and record cleanup before closeout. Profile: `modules/provider-profiles/lambda/gpu-vm-no-download.v1.json`.

### Local Workstation

Use local execution for prep, validation, visual review, and tiny deposited-structure or figure tasks. A user with substantial local CPU/GPU/storage may run larger lanes locally, but only when the task declares local materialization paths, data-retention policy, and cleanup expectations. Do not download raw EMPIAR subsets locally unless a separate CryoCore-owned task explicitly authorizes it. Local mock GPU is prep output only.

### SSH/HPC

Use when data or licenses must stay inside an institution. The adapter should generate a job script that writes the same artifact tree and self-check output. Scheduler success is not enough; the self-check must pass.

### Generic Cloud / Neocloud

Use a generic cloud or neocloud route when a validated adapter, input/secret boundary, storage boundary, artifact export, and cleanup contract are available. Keep provider resource IDs, SSH key names, API credentials, images, logs, costs, and raw artifacts outside public Git.

## AI-Design Route Selection

For Boltz and Genie-style AI design lanes, choose a route that meets the tool's runtime, data, budget, artifact, and cleanup requirements:

1. Use local execution for work that fits the declared local runtime and data-retention boundary.
2. Use a selected remote profile with a validated adapter for a bounded canary or larger run.
3. Use a provider-specific storage or image posture only after its license and runtime checks pass.
