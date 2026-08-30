## Summary

Make the Screening Superpowers campaign concrete for users and Symphony workers without launching providers, downloading data, or editing implementation code.

## Inputs

- `campaign_readme` - `campaigns/screening-superpowers/README.md`
- `campaign_dag` - `campaigns/screening-superpowers/issue-dag.md`
- `public_doc` - `docs/screening-superpowers.md`
- `fixture_manifest` - `examples/screening-superpowers/screening-manifest.json`
- `campaign_module` - `modules/campaigns/screening-superpowers.v1.json`

## Expected Artifacts

- Updated campaign README that explains example inputs, output bundle, candidate-report purpose, dispatch posture, and no-paid vs paid gates.
- Updated issue DAG that names the committed W00 draft and generated later-wave posture.
- Updated public doc that explains how users should interpret ledgers, candidate reports, and result boundaries.
- Static W00 issue draft under `campaigns/screening-superpowers/linear-issues/`.

## Stage / Progress Contract

- stage contract: `n/a`
- artifact granularity: `n/a`
- progress ledger: `n/a`
- resume command: `n/a`
- partial success policy: documentation-only issue; close `In Review` or `Blocked` if the campaign cannot state inputs, outputs, gates, and acceptance criteria without touching scripts or schemas.

## Provider / Execution Profile

- provider: `provider-neutral`
- execution profile: `screening-no-download-smoke`
- setup posture: `n/a`
- writable volume/env: `n/a`
- operator gate required: `no`

## Tooling / License Posture

- tools: `RDKit`, `AutoDock Vina`, `Boltz`, `GNINA`, `DiffDock`, `AlphaFold 3`, `Chai`, `Phenix`, `ChimeraX`, `CryoSPARC`
- posture: `mixed`
- current primary source checked: `no; W00 documents posture only and does not authorize install, image inclusion, or execution`
- intended use context: `unknown`
- image/runtime action: `mention`
- operator action required: `none for W00; paid/provider or gated-tool use requires later explicit operator gate`

## Acceptance Criteria

- [ ] Users can identify the fixture inputs: screening manifest, ligand library, receptor ensemble, and campaign module.
- [ ] Users can identify the expected ledger and candidate-report outputs without reading scripts.
- [ ] Documentation states that candidate reports are selective review packets, not per-ligand throughput output or binding proof.
- [ ] Documentation states how Symphony/Linear dispatch works, including routing label, issue body as contract, W00-only active state, and final `<!-- symphony-outcome -->` expectation.
- [ ] Documentation separates no-paid fixture gates from paid/provider-backed gates.
- [ ] Public text contains no secrets, private data, heavy artifacts, model weights, raw data, or unsupported scientific claims.

## Validation Commands

```bash
git status --short -- campaigns/screening-superpowers docs/screening-superpowers.md
find campaigns/screening-superpowers -maxdepth 3 -type f | sort
```

## Final Outcome Contract

- worker lane: `codex`
- closeout state: `In Review`
- final comment must include: `<!-- symphony-outcome -->`
- success requires: changed-file report and confirmation that no provider launch, heavy download, restricted install, script edit, or schema edit was performed.

## Touched Areas

- `campaigns/screening-superpowers/README.md` - campaign-facing contract and gates.
- `campaigns/screening-superpowers/issue-dag.md` - wave state and W00-W03 dispatch slice.
- `docs/screening-superpowers.md` - public user-facing campaign explanation.
- `campaigns/screening-superpowers/linear-issues/` - hand-authored W00-W03 drafts plus broker-generated W04-W13 drafts.

## Dependencies

Blocked by: none

## Risk Notes

- This issue does not authorize provider launch, public raw-data download, private data, model-weight download, restricted tool install, or paid compute.
- Fixture and prediction-only language must stay at `candidate` result boundary or below.
- Do not edit scripts, schemas, generated broker output, or unrelated campaign files.

## Complexity

tier: medium

<!-- symphony:schema
schema_version: 1
subgroup: structure-factory
routing_label: sym:structure-factory
campaign_id: screening-superpowers
wave: W00
target_state: Todo
touched_areas:
  - campaigns/screening-superpowers/README.md
  - campaigns/screening-superpowers/issue-dag.md
  - docs/screening-superpowers.md
  - campaigns/screening-superpowers/linear-issues/
complexity: medium
-->
