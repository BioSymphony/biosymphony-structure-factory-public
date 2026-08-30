# RunPod No-Download Smoke

Use this recipe to validate the tracked RunPod contract before you materialize a runtime packet.

## Prerequisites

- public templates only
- no provider mutation
- no credentials, real pod IDs, or accepted-license state in git

## Copyable Agent Prompt

```text
Use the BioSymphony Structure Factory skill. Review the RunPod no-download smoke path as public provider prep. Validate templates and contracts, keep all provider values as placeholders, and do not create pods or prepare a live launch packet.
```

## Commands

```bash
make runpod-check
make runpod-public-template-check
make runpod-scope-check
make launch-preflight
make input-audit
make contract-self-check
```

Expected success:

- launch manifests validate locally
- `make launch-preflight` may report unresolved bindings such as image tags or non-commit refs while still returning OK; resolve them in the ignored runtime packet before execution
- scope checks keep public templates inside Structure Factory boundaries
- input audit and contract self-check write only ignored `.runtime/` artifacts

## Files To Inspect

- `runpod/launch-manifests/no-download-smoke.json`
- `runpod/bridge-manifests/public-runtime-template.json`
- `runpod/stage-contracts/`
- `docs/runpod-stack.md`

Expected public state:

- no credentials
- no concrete placement
- no real provider IDs
- no embedded launch payloads
- no accepted-license state
- no remote launch approval

## Done Criteria

- tracked templates contain no live bindings or authorization
- operator gate, budget cap, cleanup policy, runtime-secret references, and expected artifacts are documented
- no paid mutation is attempted

## Blocked Or Degraded Criteria

Mark the run blocked or degraded if a manifest contains concrete provider IDs, embedded launch payloads, approval timestamps, credentials, or any command path that would create paid infrastructure.

To execute remotely, materialize an ignored `.runtime/` packet with explicit authorization, budget, cleanup policy, immutable source reference, runtime-secret references, expected artifacts, and closeout checks. Run the scope and readiness checks, then start it through the selected provider adapter.

## Post-Run Closeout Shape

After a provider run, pull artifacts into an ignored local folder such as `.runtime/provider-artifacts/<run-id>/`. Then run:

```bash
PROVIDER_ARTIFACT_ROOT=.runtime/provider-artifacts/<run-id> make provider-closeout-check
```

Real execution closeout should include `validation/artifact-pull-report.json`, `cost_report.json`, `cleanup_proof.json`, stage progress, expected artifacts, hashes, and validation notes. Provider `RUNNING` or a process exit code is not closeout proof by itself.
