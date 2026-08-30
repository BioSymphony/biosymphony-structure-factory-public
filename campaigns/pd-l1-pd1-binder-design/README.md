# PD-L1 / PD-1 Binder Design Campaign

**Status:** active public binder-design demo and launch-prep campaign. The repo
contains the target window, public sequence references, Genie 3 and RFdiffusion
lane planning, Boltz cofold inputs, stage contracts, and public
candidate-ranking summaries.

**Result boundary:** computational candidate support only. The campaign makes no
binding, inhibition, immune-checkpoint, therapeutic, selectivity, or wet-lab
recommendation claims.

## Why This Target

PD-L1 / PD-1 is a useful public benchmark for de novo binder workflows because
it has a compact protein-protein interface, public structural data, and a known
de novo binder positive-control context. The campaign uses public PDB `4ZQK`
chain A residues 19-127 as the PD-L1 target window and keeps all claims below
experimental validation.

## What Is Useful Here

- `target_window.json` is a legacy-named compatibility file that defines
  the public PD-L1 interface window, hotspots, and result boundaries.
- `boltz_inputs/` contains the public positive-control YAML input for the
  Boltz cofold validation step.
- `rankings/` is a compatibility path that contains public candidate-ranking
  summaries with synthetic example values. Runtime artifact paths, generated
  structures, and generated binder sequences live in ignored runtime storage
  or a user-selected artifact store.
- `sequences.json` lists the public reference sequences (4ZQK, 8ZNL) used by
  the campaign.
- `report/README.md` explains why generated runtime reports are not tracked in the
  public export.

Wave plans (Genie 3 generation shape, Boltz cofold validation posture,
RFdiffusion integration path) are resolved at runtime outside public git.
Files under `scripts/structure_factory/` and
`runpod/` are builders, templates, and stage contracts. They are not prior run
packets.

## Runtime Posture

Coordinate files are not tracked in git. The RFdiffusion lane materializes the
public 4ZQK chain A 19-127 slice at runtime and records the resulting SHA256 in
`validation/input-audit.json`.

Genie 3 weights and any license- or terms-sensitive dependencies remain
operator-gated. Boltz and Genie execution require a GPU runtime; local preflight
checks validate control-plane wiring but do not imply local inference readiness.

## Key Commands

```bash
make harness-check
make runpod-scope-check
make stage-contract-check
make preflight
make test
```

## Runtime Scripts

This campaign folder describes a binder-design contract shape; it does not
ship its own runners. To execute, build provider-side runners against the
contract files (`target_window.json`, `boltz_inputs/`, `rankings/`)
in an operator-gated environment outside public git. Bridge packets are written
under `.runtime/bridge-manifests/` only after an operator-gated build step;
stage contracts under `runpod/stage-contracts/pd-l1-*.json` document the
public launch contract shape.

The launch packets reference an operator-supplied runner named
`pd_l1_binder_hunt.py` (or whatever your stack calls it). The contract's
`resume_command` and `inline_commands` lines describe the runner interface
the contract assumes: `--stage <stage_name> --out <artifacts_dir> --json`.
Build your runner to match this interface, or rewrite the contract's
commands to match yours.

## Useful Output Shape

The output trail a successful run should produce: stage progress, executed
commands, candidate rows, top-candidate ranking, report artifacts, and explicit
result boundaries. Public candidate summaries in `rankings/` show the compatibility
schema shape; the values in the public file are synthetic schema-example
placeholders.
