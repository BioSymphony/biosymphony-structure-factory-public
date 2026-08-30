# BoltzGen

## Purpose

Plan Boltz-family binder-generation lanes. BoltzGen is a candidate design arm
for generating binder hypotheses that must be scored by the independent cofold
and refinement stack before any promotion.

## Public-Safe Status

Public scaffold: yes. Runtime use requires current source, dependency, weight,
and provider review. Treat this as a new design lane until smoke tests and
cross-validator contracts are recorded.

## When To Use

- Explore a Boltz-native binder-generation path alongside RFdiffusion3,
  BindCraft, Genie3, or peptide arms.
- Produce a small canary batch for downstream Boltz/Chai/ipSAE scoring.
- Compare generator diversity and failure modes across design arms.

## Hand A Mission To An Agent

```text
Use the BioSymphony Structure Factory skill with the BoltzGen tool card. For
target window <path>, prepare a BoltzGen canary lane with target checksum,
generator settings, seed policy, expected design tranche, and downstream cofold
scorecard contract. Do not run paid GPU work until source, weights, and provider
cache posture are recorded.
```

## Typical Inputs

- Public or operator-approved target window.
- Generator constraints, seeds, and target-site definition.
- Runtime cache and dependency posture.

## Typical Outputs

- `boltzgen_designs/` outside git.
- `design_tranche.json` with generated candidate pointers and checksums.
- Downstream scorecards from the cofold scoring stack.

## Repo And References

- Repo: https://github.com/HannesStark/boltzgen

## Gotchas

- Generator success is not binder success. Route every candidate through
  independent cofold and geometry review.
- Keep model weights, generated structures, and provider logs outside public git.

## Gates

- Current source and license review before runtime use.
- No private target inputs or generated design artifacts in the public repo.
- Result boundary remains computational candidate.
