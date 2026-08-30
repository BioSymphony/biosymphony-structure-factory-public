## Summary

Run the second real Structure Factory RunPod demo: a public map/model report for EMDB `EMD-43816` and PDB `9ASJ`, human DNA polymerase theta helicase domain with AMP-PNP. This lane proves real map/model materialization, exact command ledgers, density-support evidence, figures, provenance, and result review without raw movies or license-gated tools.

## Inputs

- `emdb:EMD-43816` - public deposited EMDB map from `https://ftp.ebi.ac.uk/pub/databases/emdb/structures/EMD-43816/map/emd_43816.map.gz`.
- `pdb:9ASJ` - public PDB mmCIF model from `https://files.rcsb.org/download/9ASJ.cif`.
- `wwpdb-validation:9ASJ` - public validation XML/PDF from `https://files.rcsb.org/pub/pdb/validation_reports/as/9asj/`.
- `runpod bridge manifest` - generated under `.runtime/bridge-manifests/poltheta-map-model-report.json`.
- `routing label` - `sym:structure-factory`.

## Expected Artifacts

- `runpod-execution/status.json` - terminal workload status.
- `runpod-execution/artifacts/data-intake-ledger.json` - materialized map/model/validation files, sizes, hashes, and source URLs.
- `runpod-execution/artifacts/executed-commands.jsonl` - exact route command ledger.
- `runpod-execution/artifacts/validation/map_model_fit.json` - real map/model density-support and validation XML summary.
- `runpod-execution/artifacts/validation/contract-self-check.json` - strict real-mode no-false-success check.
- `runpod-execution/artifacts/report.md` - figure report summary.
- `runpod-execution/artifacts/figures/` - map slice, model inventory, AMP-PNP neighborhood, and density-support SVG panels.
- `runpod-execution/artifacts/validation_ledger.md` - explicit claim/evidence/caveat ledger.
- `runpod-execution/artifacts/runpod-execution.tar.gz` - small export packet.

## Stage / Progress Contract

- stage contract: `.runtime/bridge-manifests/poltheta-map-model-report.json`
- progress ledger: `runpod-execution/artifacts/stage-progress.jsonl` and `runpod-execution/monitor_events.ndjson`
- resume command: `make demo-poltheta-prep-check`
- partial success policy: local prep/dry-run is `partial_provider_ready`; real success requires fetched RunPod status, artifact hashes, real-mode contract self-check, and pod cleanup.

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

- [ ] Run downloads only public EMDB/PDB/wwPDB validation artifacts, never raw EMPIAR movies or private data.
- [ ] `data-intake-ledger.json` joins `EMD-43816` and `9ASJ` to concrete materialized files with hashes and byte counts.
- [ ] `executed-commands.jsonl` records exact stage commands, exit codes, outputs, and timestamps.
- [ ] `validation/map_model_fit.json` contains computed map/model evidence, including voxel spacing, geometry/FSC provenance, density-support proxy, and handedness/grid coverage check.
- [ ] `validation/contract-self-check.json` reports `ok: true` in `real` mode.
- [ ] Required figure/report/provenance/claim artifacts are fetched from the RunPod pod before cleanup.
- [ ] Pod is deleted after artifact fetch; closeout must not rely on RunPod `RUNNING` state alone.

## Validation Commands

```bash
python3 -m py_compile scripts/structure_factory/poltheta_map_model_report.py scripts/structure_factory/build_poltheta_report_bridge_manifest.py scripts/structure_factory/contract_self_check.py
python3 scripts/structure_factory/build_poltheta_report_bridge_manifest.py
PROVIDER_BRIDGE_CLI=${PROVIDER_BRIDGE_CLI:-symphony-neocloud-bridge}
$PROVIDER_BRIDGE_CLI validate-manifest .runtime/bridge-manifests/poltheta-map-model-report.json --json
$PROVIDER_BRIDGE_CLI prepare .runtime/bridge-manifests/poltheta-map-model-report.json --out-dir .runtime/poltheta-map-model-packet --json
# To start paid provider work, validate an ignored `.runtime/` packet and obtain explicit human approval.
```

Materialize the RunPod packet under ignored `.runtime/` space, supply provider credentials through runtime secret references, run the readiness checks, and obtain explicit human authorization before adding execution flags.

## Final Outcome Contract

- worker lane: `codex or trusted-after-run`
- closeout state: `issue-declared target state`
- final comment must include: `<!-- symphony-outcome -->`
- success requires: `declared artifacts, validation commands, and explicit partial/degraded/blocked closeout when evidence is incomplete`

## Touched Areas

- `demos/poltheta-map-model-report/` - operator runbook.
- `scripts/structure_factory/poltheta_map_model_report.py` - public map/model report runner.
- `scripts/structure_factory/build_poltheta_report_bridge_manifest.py` - generated RunPod provider-packet builder.
- `.runtime/bridge-manifests/poltheta-map-model-report.json` - generated RunPod bridge packet, not committed to public git.
- `scripts/structure_factory/contract_self_check.py` - real-route self-check hardening.
- `modules/artifact-contracts/structure-report.v1.json` - map/model report required artifacts.
- `references/validation-gates.md` - exact-route and placeholder-output gates.
- `docs/no-false-success-hardening.md` - general hardening notes.
- `Makefile` - demo validation targets.

## Dependencies

Blocked by: operator approval for this public map/model RunPod execution and operator-managed provider credential access.

## Risk Notes

- Do not store RunPod credentials in git, Linear, artifacts, or reports.
- Do not use CryoSPARC, Phenix, ChimeraX, MotionCor, Rosetta/PyRosetta, AlphaFold 3, or other license-gated tools.
- Do not download raw EMPIAR movies, half-map raw data, private structures, unpublished sequences, model weights, or large private datasets.
- Treat density-support and ligand-neighborhood outputs as candidate/processed observations, not final mechanism or publishability claims.
- Do not mark success from pod creation or `desiredStatus: RUNNING`; require workload status, ledgers, artifacts, self-check, hashes, and cleanup.

## Complexity

tier: medium

<!-- symphony:schema
schema_version: 1
subgroup: structure-factory
routing_label: sym:structure-factory
campaign_id: cryoem-raw-to-atomic-report
wave: DEMO-02
target_state: Todo
touched_areas:
  - demos/poltheta-map-model-report/
  - scripts/structure_factory/poltheta_map_model_report.py
  - scripts/structure_factory/build_poltheta_report_bridge_manifest.py
  - .runtime/bridge-manifests/poltheta-map-model-report.json
  - scripts/structure_factory/contract_self_check.py
  - modules/artifact-contracts/structure-report.v1.json
  - references/validation-gates.md
  - docs/no-false-success-hardening.md
  - Makefile
complexity: medium
-->
