## Summary

<One or two sentence scientific goal and artifact outcome.>

## Inputs

- `<input id>` - <source accession, local secure-store path, RunPod volume path, or prior issue artifact>

## Expected Artifacts

- `<artifact>` - <path or manifest entry>

## Stage / Progress Contract

- stage contract: `<repo-relative path or n/a>`
- artifact granularity: `<per-campaign | per-wave | per-shard | n/a>`
- progress ledger: `<runtime path or n/a>`
- resume command: `<exact command or n/a>`
- partial success policy: `<how fallback/timeout is downgraded>`

## Provider / Execution Profile

- provider: `<runpod | local | aws | ssh-hpc | generic-cloud | neocloud | provider-neutral>`
- execution profile: `<no-download-smoke | raw-subset-open | raw-subset-gated | map-model-report | other>`
- setup posture: `<public image | private image | runtime bootstrap | runpod network volume bootstrap | local install | hpc module | neocloud volume | n/a>`
- writable volume/env: `<STRUCTURE_FACTORY_RUNPOD_NETWORK_VOLUME_ID | local path | hpc path | n/a>`
- operator gate required: `<yes/no>`

## Tooling / License Posture

- tools: `<tool names or n/a>`
- posture: `<open-default | review-required | runtime-gated | internal-only | mixed>`
- current primary source checked: `<yes/no + source note>`
- intended use context: `<personal | academic-nonprofit | non-commercial | commercial | institutional | unknown>`
- image/runtime action: `<mention | scaffold | runtime install | public image | private image | run | n/a>`
- operator action required: `<none or explicit action>`

## Acceptance Criteria

- [ ] <Specific, testable scientific or artifact assertion.>
- [ ] <Specific validation or figure assertion.>
- [ ] <Specific provenance, license, or caveat assertion.>

## Validation Commands

```bash
<exact command from repo root>
```

## Final Outcome Contract

- worker lane: `<codex | claude | trusted-after-run>`
- closeout state: `<Done | In Review | Blocked | Todo>`
- final comment must include: `<!-- symphony-outcome -->`
- source posture: `<provider_native | derived | fixture_or_demo | report_only | blocked_or_insufficient>`
- result boundary: `<planning | public_demo | public_synthetic_demo | computational_candidate | blocked | insufficient_support>`
- artifact packet: `<path or n/a>`
- hash ledger: `<path or n/a>`
- cost report: `<path or n/a>`
- cleanup proof: `<path or n/a>`
- success requires: `<artifact hashes, contract self-check, cleanup verification, or explicit partial/degraded closeout>`

## Touched Areas

- `<path>` - <why this area is in scope>

## Dependencies

Blocked by: <issue-id or none>

## Risk Notes

- Do not store secrets, raw cryo-EM movies, private structures, unpublished sequences, model weights, or large datasets in git or Linear.
- Record license constraints for CryoSPARC, Phenix, ChimeraX, MotionCor, Rosetta/PyRosetta, AlphaFold, or other restricted tools.
- GHCR/private images are optional. If RunPod is used, record whether the lane uses public images, private images, runtime bootstrap, or the Structure Factory Network Volume bootstrap path.
- Run `make runpod-scope-check` before any paid RunPod mutation and never target sibling campaign pods, volumes, templates, or registry auth IDs.
- Record confidence limitations for predicted structures, ligand fits, density interpretations, affinities, and generated designs.

## Complexity

tier: medium

<!-- symphony:schema
schema_version: 1
subgroup: structure-factory
touched_areas:
  - <path>
complexity: medium
-->
