# BindCraft

## Purpose

Plan automated binder-design lanes that combine backbone/sequence search,
AlphaFold-style scoring, ProteinMPNN-style sequence design, and Rosetta-family
filters. In Structure Factory, BindCraft is a high-fit design arm, but every
candidate still flows through independent cofold and claim-audit gates.

## Public-Safe Status

Public scaffold: yes. Runtime use is gated by PyRosetta/Rosetta terms,
AlphaFold2 weight posture, dependency review, target-use context, budget, and
artifact policy.

## When To Use

- Miniprotein binder campaigns where an integrated design pipeline is preferable
  to wiring RFdiffusion, MPNN, AF2, and filters by hand.
- Comparison against RFdiffusion3, Genie3, or peptide-design arms.
- A bounded public-target canary after target prep and cofold scoring contracts
  are already in place.

## Hand A Mission To An Agent

```text
Use the BioSymphony Structure Factory skill with the BindCraft tool card. For
target window <path>, prepare a BindCraft lane with public target inputs, allowed
hotspots, run budget, filter manifest, downstream Boltz/Chai cofold handoff, and
result-boundary caveats. Do not install PyRosetta, download AF2 weights, or run
GPU compute until the operator gate records license/use context and cache policy.
```

## Typical Inputs

- Public or operator-approved target structure and hotspot/window definition.
- BindCraft settings JSON and filter thresholds.
- Runtime access posture for PyRosetta/Rosetta and AlphaFold2-family weights.

## Typical Outputs

- `bindcraft_designs/` outside git.
- `bindcraft_filters.json` or equivalent pass/fail filter table.
- `design_manifest.json` with settings, versions, seeds, and target checksum.
- Downstream cofold scorecards and consensus ranking.

## Repo And References

- Repo: https://github.com/martinpacesa/BindCraft

## Gotchas

- BindCraft can produce candidates that look good under its own filters. Treat
  those as design hypotheses until independent cofold and geometry checks agree.
- PyRosetta/Rosetta access is use-context sensitive. Do not bake accepted-license
  state or license artifacts into the public repo.
- AF2 weights and generated designs are runtime artifacts, not public docs.

## Gates

- Runtime gate before restricted installs, weight downloads, or provider spend.
- Public examples use public deposited targets or synthetic fixtures only.
- Outputs are computational candidates, not binding, affinity, selectivity,
  safety, or therapeutic evidence.
