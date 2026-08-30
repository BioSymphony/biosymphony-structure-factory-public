# PoseBusters

## Purpose

Plan plausibility checks for generated or docked small-molecule poses. PoseBusters
is a pose-quality gate for screening and docking lanes, not a binding or
affinity predictor.

## Public-Safe Status

Public scaffold: yes. The upstream repo reports an MIT license and pip
installation path. Runtime use still needs current package and dependency review.

## When To Use

- Check generated ligand poses for basic physical and chemistry plausibility.
- Add a quality ledger after Vina, GNINA, DiffDock, Boltz-style ligand outputs,
  or other pose-generating lanes.
- Separate pose failures from score failures in a screening report.

## Hand A Mission To An Agent

```text
Use the BioSymphony Structure Factory skill with the PoseBusters tool card. For
pose outputs <path>, prepare a pose-validity lane that checks each ligand pose,
records pass/fail reasons, and joins the result back to the screening consensus
ranking. Keep generated pose files outside git unless they are tiny public
fixtures.
```

## Typical Inputs

- Predicted ligand pose SDF files.
- Optional receptor structure, reference ligand, or file table.
- Method and ligand-prep provenance from the upstream scoring lane.

## Typical Outputs

- `pose_validity.jsonl`.
- `pose_quality_ledger.json`.
- Failure summaries joined to `consensus_ranking.csv`.

## Repo And References

- Repo: https://github.com/maabuu/posebusters

## Gotchas

- Passing PoseBusters does not prove binding. It only removes obvious pose or
  chemistry failures.
- Reference-ligand checks require a suitable reference complex and clean chain
  mapping.

## Gates

- Public examples use fixture poses or public structures only.
- Pose files, receptor files, and ligand libraries follow the campaign artifact
  policy.
- Result boundary remains pose plausibility or computational candidate.
