# MolPAL

## Purpose

Plan active-learning tranches for high-throughput virtual screening. MolPAL is
an acquisition and library-prioritization lane; it does not replace docking,
cofolding, assay data, or final hit review.

## Public-Safe Status

Public scaffold: yes. The upstream repo reports an MIT license, but runtime use
still needs current package, dependency, ligand-library, and score-provider
review.

## When To Use

- Split a large ligand library into active-learning rounds after receptor,
  ligand, and score contracts are known.
- Prioritize follow-up tranches from method disagreement, controls, or top-hit
  uncertainty.
- Keep screening compute bounded by a declared acquisition budget.

## Hand A Mission To An Agent

```text
Use the BioSymphony Structure Factory skill with the MolPAL tool card. For
screening manifest <path> and ligand library <path>, plan an active-learning
lane that emits acquisition rounds, tranche budgets, library hashes, and a
score-provider contract. Do not upload private libraries or run external scoring
without a data-policy gate.
```

## Typical Inputs

- Ligand library pointer and hashes.
- Score-provider contract, for example Vina, a fixture score, or a reviewed
  docking/affinity lane.
- Acquisition function, seed, batch size, and stop policy.

## Typical Outputs

- `active_learning_tranches.json`.
- `acquisition_report.json`.
- Library and score-provider provenance rows.

## Repo And References

- Repo: https://github.com/coleygroup/molpal

## Gotchas

- MolPAL is only as meaningful as the score source and library normalization.
- Online docking or distributed execution inherits the downstream tool and
  provider gates.
- Store library IDs, hashes, and tranches, not private ligand libraries.

## Gates

- Public examples use synthetic or explicitly public ligand fixtures.
- External score providers require terms, data, and provider preflight.
- Output supports prioritization, not biological activity or binding proof.
