# PLACER

## Purpose

Plan protein-ligand local conformational ensemble lanes for focused candidate
review. PLACER belongs after receptor/ligand preparation and before or alongside
pose-quality checks, not as a default wide-screen authority.

## Public-Safe Status

Public scaffold: yes. Runtime use requires current source, model-weight,
dependency, CCD/ligand, and provider-cache review.

## When To Use

- Focused follow-up on a small set of ligand or cofactor hypotheses.
- Compare local conformational uncertainty around a binding site.
- Add one method vote to a protein-ligand review packet after simpler baselines
  are already recorded.

## Hand A Mission To An Agent

```text
Use the BioSymphony Structure Factory skill with the PLACER tool card. For
prepared receptor/ligand inputs <path>, plan a focused PLACER lane with exact
input provenance, ligand definitions, model/cache posture, compact outputs, and
PoseBusters-style pose-quality follow-up.
```

## Typical Inputs

- Prepared receptor structure and ligand definition.
- Pocket or local context definition.
- Runtime model/cache posture and dependency versions.

## Typical Outputs

- `placer_complexes/` outside git.
- `method_summary.json` with settings, versions, input checksums, and failures.
- Optional pose-quality ledger from a downstream check.

## Repo And References

- Repo: https://github.com/baker-laboratory/PLACER

## Gotchas

- This is a focused review lane, not a high-throughput screening default.
- Ligand definitions and CCD handling need explicit provenance.
- Model weights and generated complexes stay outside public git.

## Gates

- Current terms and weight-source review before runtime use.
- Public examples use public or synthetic ligand/receptor fixtures.
- Outputs are computational pose/context hypotheses only.
