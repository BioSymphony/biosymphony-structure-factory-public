# Boltz

## Purpose

Plan cofold and structure-prediction lanes for protein-protein interfaces, including binder triage. Boltz takes a target plus one or more partners and emits predicted complex structures with confidence metrics suitable for ranking and downstream ipSAE rescoring.

## Public-Safe Status

Public scaffold: yes. Runtime use requires current source, dependency, and weight review against upstream license terms.

## When To Use

- Cofold an existing target and candidate binder for interface confidence.
- Produce PAE matrices for downstream ipSAE rescoring.
- Run as one vote in a multi-validator slate alongside Chai-1 and AF2-Multimer when single-cofolder iPTM is known to over-fit a given target class.

## Hand A Mission To An Agent

```text
Use the BioSymphony Structure Factory skill with the Boltz tool card. For target <PDB:ID> and candidate sequence <FASTA>, prepare a Boltz cofold lane: pre-compute the target MSA once, write per-design YAML inputs that reference the cached MSA, and define the closeout artifacts (confidence JSON per model, full PAE matrices for ipSAE).
```

## Typical Inputs

- Target sequence and reference structure.
- Candidate binder sequence (de novo or known).
- Cached target MSA in `.a3m` form (binders are typically single-sequence).
- Optional active-state or inactive-state structural template.

## Typical Outputs

- Predicted complex structures (CIF or PDB) under `boltz_results_<stem>/predictions/<stem>/`.
- `confidence_<name>_model_<k>.json` with `confidence_score`, `complex_iplddt`, `pair_chains_iptm`, and `ptm`.
- Full PAE matrices when `--write_full_pae` is set.

## Repo And References

- Repo: https://github.com/jwohlwend/boltz
- Boltz-2 preprint: https://www.biorxiv.org/content/10.1101/2025.06.14.659707v1

## Key Knobs

| Flag | Recommendation | Why |
| --- | --- | --- |
| `--recycling_steps` | 3 | Default is usually sufficient; small marginal gains beyond. |
| `--diffusion_samples` | 3 or more | Median across samples is more stable than top-1. |
| `--sampling_steps` | 50 for ranking, 200 for final | Lower steps are fine for triage; bump for promoted candidates. |
| `--write_full_pae` | on | Required for ipSAE post-hoc rescoring. |
| YAML `msa:` (target) | cached `.a3m` path | Avoids per-design MSA server calls and rate limits. |
| YAML `msa:` (de novo binder) | `empty` | Designed binders have no informative MSA. |

## Gotchas

- `affinity_summary.json` is the small-molecule affinity head, not protein-protein iPTM. Read `confidence_<name>.json` for binder ranking metrics.
- The Boltz-2 paper acknowledges GPCRs, transporters, and channels are under-represented in training. Use a multi-validator slate for these target classes.
- Outputs nest under `boltz_results_<stem>/predictions/<stem>/`. Flatten before downstream consumers.
- Single-cofolder iPTM alone is not a sufficient gate for binder promotion. Recent benchmarks favor min-ipSAE across multiple validators.

## Gates

- Weight download and runtime use require current upstream license terms.
- Public targets only in public examples.
- Real provider runs need budget, cleanup, and operator-gate approval per the campaign's provider profile.
- Run a currency check before any paid GPU dispatch: upstream repo HEAD (releases + recent commits), current release notes, and recent preprints (biorxiv / chemrxiv / arxiv) on the relevant lane. Record the version pin and the date of the check in the candidate ranking or validation notes.
