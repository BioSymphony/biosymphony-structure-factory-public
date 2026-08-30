## Summary

Run the next Structure Factory RunPod demo: a two-target public deposited-structure comparison that executes and joins a T2R14 coordinate report (`PDB 9W0Q` / `EMD-65512`) and a pol theta map/model report (`PDB 9ASJ` / `EMD-43816`). This proves multi-lane artifact joining, exact command ledgers, campaign-level figures, provenance, and result review without raw movies or license-gated tools.

## Inputs

- `pdb:9W0Q` and `emdb:EMD-65512` - public deposited T2R14 receptor-complex lane.
- `pdb:9ASJ` and `emdb:EMD-43816` - public deposited pol theta map/model lane.
- `wwpdb-validation:9ASJ` - public validation XML/PDF from wwPDB validation endpoints.
- `runpod bridge manifest` - generated under `.runtime/bridge-manifests/dual-structure-comparison.json`.
- `routing label` - `sym:structure-factory`.

## Expected Artifacts

- `runpod-execution/status.json` - terminal workload status.
- `runpod-execution/artifacts/campaign-summary.json` - joined two-target summary.
- `runpod-execution/artifacts/data-intake-ledger.json` - materialized public files, hashes, and target joins.
- `runpod-execution/artifacts/executed-commands.jsonl` - exact route command ledger.
- `runpod-execution/artifacts/validation/contract-self-check.json` - strict real-mode no-false-success check.
- `runpod-execution/artifacts/figures/evidence-matrix.svg` - campaign evidence matrix.
- `runpod-execution/artifacts/figures/maturity-ladder.svg` - maturity ladder panel.
- `runpod-execution/artifacts/targets/t2r14/artifacts/report.md` - T2R14 target report.
- `runpod-execution/artifacts/targets/poltheta/artifacts/report.md` - pol theta target report.
- `runpod-execution/artifacts/report.md` - joined campaign report.
- `runpod-execution/artifacts/runpod-execution.tar.gz` - small export packet.

## Stage / Progress Contract

- stage contract: `.runtime/bridge-manifests/dual-structure-comparison.json`
- progress ledger: `runpod-execution/artifacts/stage-progress.jsonl` and `runpod-execution/monitor_events.ndjson`
- resume command: `make demo-structure-ranking-prep-check`
- partial success policy: local prep/dry-run is `partial_provider_ready`; real success requires fetched RunPod status, artifact hashes, target reports, campaign self-check, and pod cleanup.

## Provider / Execution Profile

- provider: `runpod`
- execution profile: `map-model-report`
- operator gate required: `yes`

## Tooling / License Posture

- tools: `repo validators, public metadata tooling, provider dry-run scaffolds as declared by the issue`
- posture: `mixed`
- current primary source checked: `no; repo-local contract posture only`
- intended use context: `unknown until operator gate`
- image/runtime action: `scaffold or dry-run only unless the issue explicitly authorizes execution`
- operator action required: `explicit approval before paid provider mutation, gated tool installation, raw data download, or private-data handling`

## Acceptance Criteria

- [ ] Run downloads only public deposited PDB/EMDB/wwPDB artifacts, never raw EMPIAR movies or private data.
- [ ] Both targets produce real target-level reports and figures.
- [ ] `data-intake-ledger.json` joins `9W0Q`, `EMD-65512`, `9ASJ`, and `EMD-43816` to concrete campaign evidence.
- [ ] `executed-commands.jsonl` records exact stage commands, exit codes, outputs, and timestamps.
- [ ] `validation/contract-self-check.json` reports `ok: true` and rejects missing target reports, mock outputs, raw-data claims, or license-gated tool usage.
- [ ] Joined report includes campaign evidence matrix and maturity ladder figures.
- [ ] Required artifacts are fetched and hashed before cleanup.
- [ ] Pod is deleted after artifact fetch; closeout must not rely on RunPod `RUNNING` state alone.

## Validation Commands

```bash
python3 -m py_compile scripts/structure_factory/dual_structure_comparison.py scripts/structure_factory/build_dual_structure_comparison_bridge_manifest.py scripts/structure_factory/t2r14_structure_report.py scripts/structure_factory/poltheta_map_model_report.py
python3 scripts/structure_factory/build_dual_structure_comparison_bridge_manifest.py
PROVIDER_BRIDGE_CLI=${PROVIDER_BRIDGE_CLI:-symphony-neocloud-bridge}
$PROVIDER_BRIDGE_CLI validate-manifest .runtime/bridge-manifests/dual-structure-comparison.json --json
$PROVIDER_BRIDGE_CLI prepare .runtime/bridge-manifests/dual-structure-comparison.json --out-dir .runtime/dual-structure-comparison-packet --json
# To start paid provider work, validate an ignored `.runtime/` packet and obtain explicit human approval.
```

Materialize the RunPod packet under ignored `.runtime/` space with authorization, budget, cleanup policy, runtime-secret references, immutable source reference, expected artifacts, and closeout checks. Run the readiness checks before adding execution flags.

## Final Outcome Contract

- worker lane: `codex or trusted-after-run`
- closeout state: `issue-declared target state`
- final comment must include: `<!-- symphony-outcome -->`
- success requires: `declared artifacts, validation commands, and explicit partial/degraded/blocked closeout when evidence is incomplete`

## Touched Areas

- `demos/dual-structure-comparison/` - operator runbook.
- `scripts/structure_factory/dual_structure_comparison.py` - public two-target campaign runner.
- `scripts/structure_factory/build_dual_structure_comparison_bridge_manifest.py` - generated RunPod provider-packet builder.
- `.runtime/bridge-manifests/dual-structure-comparison.json` - generated RunPod bridge packet, not committed to public git.
- `Makefile` - demo validation targets.

## Dependencies

Blocked by: operator approval for this public dual-report RunPod execution and centralized RunPod API access.

## Risk Notes

- Do not store RunPod credentials in git, Linear, artifacts, or reports.
- Do not use CryoSPARC, Phenix, ChimeraX, MotionCor, Rosetta/PyRosetta, AlphaFold 3, or other license-gated tools.
- Do not download raw EMPIAR movies, particle stacks, private structures, unpublished sequences, model weights, or large private datasets.
- Treat density-support, contacts, and ligand-neighborhood outputs as candidate/processed observations, not final mechanism or publishability claims.
- Do not mark success from pod creation or `desiredStatus: RUNNING`; require workload status, ledgers, artifacts, self-check, hashes, and cleanup.

## Complexity

tier: medium

<!-- symphony:schema
schema_version: 1
subgroup: structure-factory
routing_label: sym:structure-factory
campaign_id: cryoem-raw-to-atomic-report
wave: DEMO-04
target_state: Todo
touched_areas:
  - demos/dual-structure-comparison/
  - scripts/structure_factory/dual_structure_comparison.py
  - scripts/structure_factory/build_dual_structure_comparison_bridge_manifest.py
  - .runtime/bridge-manifests/dual-structure-comparison.json
  - Makefile
complexity: medium
-->
