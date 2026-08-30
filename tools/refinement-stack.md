# Refinement Stack

## Purpose

Refine and filter cofolded candidate complexes before a report or ranking step reviews them.

## Public-Safe Status

Public scaffold: yes. OpenMM and RDKit lanes are usually publishable after current-term checks. Rosetta, PyRosetta, Phenix, and other license-gated tools require operator runtime access.

## Hand A Mission To An Agent

```text
Use the BioSymphony Structure Factory skill with the Refinement Stack tool card. For cofolded complex <path> with chain mapping <details>, prepare a refinement lane. Specify the minimization scope, the interface analysis pass, the quality thresholds, and the clash, geometry, and interface summary expected at closeout.
```

## Typical Inputs

- Cofolded complex model outside git.
- Chain mapping and interface definition.
- Result boundary and quality thresholds.

## Typical Outputs

- Minimized or relaxed model outside git.
- Clash/geometry/interface summary.
- Filter pass/fail table.
- Provenance and command ledger.

## Gates

- Geometry cleanup is not experimental validation.
- Gated tools must record runtime license posture.
- Failed refinement should downgrade the candidate, not disappear it.
- Run a currency check before any paid GPU dispatch: upstream repo HEAD (releases + recent commits), current release notes, and recent preprints (biorxiv / chemrxiv / arxiv) on the relevant lane. Record the version pin and the date of the check in the candidate ranking or validation notes.
