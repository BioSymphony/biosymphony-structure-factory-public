## Summary

Run a small real Structure Factory demo that uses only public RCSB/PDB coordinate metadata for PDB `9W0Q` / EMDB `EMD-65512`, produces a coordinate-derived report, and prepares a guarded RunPod Pod launch packet. This is the first open-tool demo path for Symphony + Linear + RunPod without licensed tools, raw movies, private data, or large downloads.

## Inputs

- `pdb:9W0Q` - public RCSB entry metadata from `https://data.rcsb.org/rest/v1/core/entry/9W0Q`.
- `coordinates:9W0Q.cif` - public mmCIF coordinates from `https://files.rcsb.org/download/9W0Q.cif`.
- `runpod bridge manifest` - generated under `.runtime/bridge-manifests/t2r14-structure-report.json`.
- `routing label` - `sym:structure-factory`.

## Expected Artifacts

- `runpod-execution/status.json` - terminal status for the demo workload.
- `runpod-execution/artifacts/report.md` - demo report with SVG figure panel references.
- `runpod-execution/artifacts/report_manifest.json` - artifact and claim-level manifest.
- `runpod-execution/artifacts/coordinate-summary.json` - parsed atom, chain, residue, and deposition metadata summary.
- `runpod-execution/artifacts/interchain-contact-matrix.json` - coordinate-derived inter-chain contact summary.
- `runpod-execution/artifacts/ligand-neighborhoods.json` - non-water HETATM neighborhood summary.
- `runpod-execution/artifacts/validation_ledger.md` - claim boundaries and downgraded claims.
- `runpod-execution/artifacts/provenance.md` - source URLs and tool policy.
- `runpod-execution/artifacts/runpod-execution.tar.gz` - small artifact packet.

## Stage / Progress Contract

- stage contract: `.runtime/bridge-manifests/t2r14-structure-report.json`
- progress ledger: `runpod-execution/artifacts/stage-progress.jsonl` and `runpod-execution/monitor_events.ndjson`
- resume command: `make demo-t2r14-check`
- partial success policy: local report generation plus RunPod dry-run is `partial_provider_ready`; RunPod execution uses an ignored runtime packet with runtime-secret references, explicit authorization, and cleanup closeout.

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

- [ ] `make demo-t2r14-check` succeeds from the repo root and emits a local public-coordinate report under `.runtime/t2r14-structure-report-local/runpod-execution/`.
- [ ] The report includes `report.md`, three SVG figure panels, provenance, validation ledger, validation files, artifact hashes, and an archive packet.
- [ ] The generated RunPod provider packet validates and prepares without credentials, raw EM data, private images, private data, or licensed tools.
- [ ] A no-cost RunPod dry-run emits an audited pod creation request for `python:3.12-slim`, CPU-only compute, a 45 minute budget, and an operator-defined maximum estimated cost.
- [ ] Real RunPod launch is not marked successful unless a pod actually executes, writes status/progress/hash artifacts, and is cleaned up.

## Validation Commands

```bash
make demo-t2r14-check
python3 -m py_compile scripts/structure_factory/t2r14_structure_report.py scripts/structure_factory/build_t2r14_report_bridge_manifest.py
PROVIDER_BRIDGE_CLI=${PROVIDER_BRIDGE_CLI:-symphony-neocloud-bridge}
$PROVIDER_BRIDGE_CLI validate-manifest .runtime/bridge-manifests/t2r14-structure-report.json --json
$PROVIDER_BRIDGE_CLI prepare .runtime/bridge-manifests/t2r14-structure-report.json --out-dir .runtime/t2r14-structure-report-packet --json
# To start paid provider work, validate an ignored `.runtime/` packet and obtain explicit human approval.
```

Materialize the RunPod packet under ignored `.runtime/` space, resolve its adapter and provider bindings, run the readiness checks, and obtain explicit human authorization before adding execution flags.

## Final Outcome Contract

- worker lane: `codex or trusted-after-run`
- closeout state: `issue-declared target state`
- final comment must include: `<!-- symphony-outcome -->`
- success requires: `declared artifacts, validation commands, and explicit partial/degraded/blocked closeout when evidence is incomplete`

## Touched Areas

- `demos/t2r14-structure-report/` - operator runbook for the contained open-tool demo.
- `scripts/structure_factory/t2r14_structure_report.py` - public coordinate report runner.
- `scripts/structure_factory/build_t2r14_report_bridge_manifest.py` - generated RunPod provider-packet builder.
- `.runtime/bridge-manifests/t2r14-structure-report.json` - generated RunPod bridge packet, not committed to public git.
- `Makefile` - demo validation targets.

## Dependencies

Requires: runtime provider credentials, explicit paid-run approval, and an immutable public source reference in the materialized packet.

## Risk Notes

- Do not store RunPod, GitHub, RCSB, or Linear credentials in git, Linear, artifacts, or reports.
- Do not use CryoSPARC, Phenix, ChimeraX, MotionCor, Rosetta/PyRosetta, AlphaFold 3, or other license-gated tools for this demo.
- Do not download raw EMPIAR movies, deposited maps, half maps, private structures, unpublished sequences, model weights, or large datasets.
- Treat coordinate-derived contact and ligand-neighborhood summaries as candidate observations, not biological mechanism claims.
- Do not mark the RunPod stage successful from `desiredStatus: RUNNING`; require workload status files, progress ledger entries, artifact hashes, and cleanup evidence.

## Complexity

tier: small

<!-- symphony:schema
schema_version: 1
subgroup: structure-factory
routing_label: sym:structure-factory
campaign_id: cryoem-raw-to-atomic-report
wave: DEMO-01
target_state: Backlog
touched_areas:
  - demos/t2r14-structure-report/
  - scripts/structure_factory/t2r14_structure_report.py
  - scripts/structure_factory/build_t2r14_report_bridge_manifest.py
  - .runtime/bridge-manifests/t2r14-structure-report.json
  - Makefile
complexity: small
-->
