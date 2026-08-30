## Summary

Harden Structure Factory provider adapter contracts so RunPod remains the default reviewed remote path while local, SSH/HPC, generic cloud VM, and neocloud profiles can share the same BioSymphony + Linear + Symphony evidence contract.

## Inputs

- `provider docs` - `docs/compute-backends.md`.
- `provider profiles` - `modules/provider-profiles/`.
- `validation scripts` - provider, module, RunPod, input-audit, and contract-self-check validators.

## Expected Artifacts

- `docs/compute-backends.md` - backend contract and success rules.
- `modules/provider-profiles/local/` - local workstation prep profile.
- `modules/provider-profiles/ssh-hpc/` - SSH/HPC adapter profile.
- `modules/provider-profiles/cloud-vm/` - generic cloud VM adapter profile.
- `modules/provider-profiles/neocloud/` - pod-style neocloud adapter profile.
- `scripts/structure_factory/provider_profile_check.py` - provider profile validator.
- `scripts/structure_factory/runpod_scope_check.py` - Structure Factory RunPod resource boundary validator.

## Stage / Progress Contract

- stage contract: `n/a`
- artifact granularity: `n/a`
- progress ledger: `n/a`
- resume command: `make provider-check && make runpod-scope-check`
- partial success policy: `adapter-contract prep only; provider launch readiness remains blocked until provider-specific execution gates pass`

## Provider / Execution Profile

- provider: `provider-neutral`
- execution profile: `no-download-smoke`
- setup posture: `provider-declared: image, runtime bootstrap, local install, hpc module, RunPod Network Volume, or neocloud volume`
- writable volume/env: `provider-specific; RunPod uses STRUCTURE_FACTORY_RUNPOD_NETWORK_VOLUME_ID`
- operator gate required: `no`

## Tooling / License Posture

- tools: `RunPod, local workstation, SSH/HPC, generic cloud VM, neocloud pod providers`
- posture: `mixed`
- current primary source checked: `yes; docs/compute-backends.md and provider-profile manifests`
- intended use context: `provider-neutral prep`
- image/runtime action: `scaffold`
- operator action required: `provider-specific execution approval before any heavy/local/cloud run`

## Acceptance Criteria

- [ ] RunPod profiles are marked as the default reviewed remote path.
- [ ] Non-RunPod provider profiles are adapter contracts and do not imply execution readiness.
- [ ] Every provider profile requires `input_audit` and `contract_self_check`.
- [ ] Provider validation fails profiles that omit artifact roots, secret mode, operator gate policy, or self-check gates.
- [ ] Local, SSH/HPC, cloud VM, and neocloud docs preserve no-false-success and no-raw-data-in-git rules.
- [ ] Setup posture is explicit for each provider family and does not assume GHCR/private images are required.
- [ ] RunPod provider packets fail validation if they reference sibling campaign pods, volumes, templates, or generic writable volume variables.

## Validation Commands

```bash
make provider-check
make module-check
make runpod-scope-check
make test
```

## Final Outcome Contract

- worker lane: `codex`
- closeout state: `In Review`
- final comment must include: `<!-- symphony-outcome -->`
- success requires: `provider-check, runpod-scope-check, and tests pass without granting execution readiness to non-RunPod adapters`

## Touched Areas

- `docs/` - compute backend and orchestration docs.
- `modules/provider-profiles/` - provider adapter contracts.
- `scripts/structure_factory/` - provider profile validator.
- `tests/` - provider validation coverage.

## Dependencies

Blocked by: BSF-W12

## Risk Notes

- This issue does not authorize local heavy jobs, SSH/HPC submission, cloud/neocloud launch, RunPod launch, or raw data download.
- Provider success is not scientific success; final evidence still requires the contract self-check.
- Keep provider-specific secrets out of git and Linear.
- A provider fallback, including private image to bootstrap or RunPod to local, must close partial/degraded unless the issue explicitly re-approves the new route and reruns the artifact self-check.

## Complexity

tier: medium

<!-- symphony:schema
schema_version: 1
subgroup: structure-factory
routing_label: sym:structure-factory
campaign_id: cryoem-raw-to-atomic-report
wave: W13
target_state: Backlog
touched_areas:
  - docs/
  - modules/provider-profiles/
  - scripts/structure_factory/
  - tests/
complexity: medium
-->
