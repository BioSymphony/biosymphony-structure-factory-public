## Summary

Turn extracted budget and provider phrases into bounded fanout plans before any cost-bearing screening work.

## Inputs

- `intent source` - compiled from --prompt
- `campaign ID` - screening-superpowers
- `routing label` - sym:structure-factory
- `intent mode` - openbind_calibration
- `natural-language goal` - screen TERT inhibitors with OpenBind-style calibration, method disagreement, RunPod then AWS then neocloud
- `target hint` - TERT
- `budget/provider extraction` - providers: runpod, aws_batch, neocloud_gpu_pod; max_spend_usd: 0; max_runtime_minutes: 10; max_ligands: 5
- `gated-tool blockers` - none
- `wave scope` - budget/provider extraction, fanout estimate, and operator-gate readiness

## Expected Artifacts

- `fanout estimate` - .runtime/screening-superpowers-fixture/validation/fanout-estimate.json
- `compiled intent manifest` - .runtime/screening-superpowers-fixture/budget-provider-intent.json

## Stage / Progress Contract

- stage contract: `runpod/stage-contracts/screening-superpowers.stage-contract.json`
- artifact granularity: `per-wave`
- progress ledger: `.runtime/screening-superpowers-fixture/stage-progress.jsonl`
- resume command: `python3 scripts/structure_factory/screening_fanout_estimator.py --manifest examples/screening-superpowers/screening-manifest.json --out .runtime/screening-superpowers-fixture/validation/fanout-estimate.json --json`
- partial success policy: `close blocked if requested budget/provider posture lacks explicit operator authorization`

## Provider / Execution Profile

- provider: `provider-neutral`
- execution profile: `screening-no-download-smoke`
- setup posture: `provider-declared: local, RunPod, AWS Batch, neocloud, or n/a`
- writable volume/env: `provider-specific; RunPod uses STRUCTURE_FACTORY_RUNPOD_NETWORK_VOLUME_ID`
- operator gate required: `no`

## Tooling / License Posture

- tools: `structure_intent_compile.py, screening_fanout_estimator.py`
- posture: `open-default`
- current primary source checked: `no; dry-run broker used local tooling docs and registry only; worker must verify current primary terms before install/run`
- intended use context: `unknown until operator gate; dry-run prep only`
- image/runtime action: `scaffold`
- operator action required: `operator approval only before paid execution`

## Acceptance Criteria

- [ ] Compiler extracts max spend, runtime, ligand count, top-N, and provider mentions from simple prompts.
- [ ] Fanout estimate runs before expensive transfer, docking, cofolding, or report promotion.
- [ ] Paid provider requests remain blocked until operator gate details are present.

## Validation Commands

```bash
python3 scripts/structure_factory/structure_intent_compile.py --prompt "screen 100 ligands against TERT on RunPod under $10 for 2 hours" --out .runtime/screening-superpowers-fixture/budget-provider-intent.json --json
python3 scripts/structure_factory/screening_fanout_estimator.py --manifest examples/screening-superpowers/screening-manifest.json --out .runtime/screening-superpowers-fixture/validation/fanout-estimate.json --json
```

## Final Outcome Contract

- worker lane: `codex`
- closeout state: `In Review`
- final comment must include: `<!-- symphony-outcome -->`
- success requires: `intent extraction records budget/provider constraints and fanout estimate completes`

## Touched Areas

- `scripts/structure_factory/` - intent compiler and fanout estimator
- `examples/screening-superpowers/` - fixture manifest used for estimates
- `runpod/stage-contracts/` - provider stage contract reference

## Dependencies

Blocked by: BSF-SCREENING-W02

## Risk Notes

- Do not store secrets, raw cryo-EM movies, private structures, unpublished sequences, model weights, or large datasets in git or Linear.
- Record license constraints for CryoSPARC, Phenix, ChimeraX, MotionCor, Rosetta/PyRosetta, AlphaFold, or other restricted tools.
- RunPod, AWS, neocloud, local heavy jobs, and gated-tool execution require explicit operator approval before launch.
- A prompt with a budget is not operator authorization to launch paid infrastructure.
- Provider priority is intent only until launch contracts, artifact pulls, hashes, and cleanup policy exist.

## Complexity

tier: medium

<!-- symphony:schema
schema_version: 1
subgroup: structure-factory
routing_label: sym:structure-factory
campaign_id: screening-superpowers
wave: W05
target_state: Backlog
touched_areas:
  - scripts/structure_factory/
  - examples/screening-superpowers/
  - runpod/stage-contracts/
complexity: medium
-->
