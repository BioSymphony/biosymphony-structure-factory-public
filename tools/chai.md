# Chai-1

## Purpose

Plan cofold lanes with Chai-1, an open-source biomolecular structure prediction model. Used as an independent vote in multi-validator slates alongside Boltz and AF2-Multimer for binder triage.

## Public-Safe Status

Public scaffold: yes. Runtime use requires current source, dependency, and weight review.

## When To Use

- One member of a multi-validator slate for binder triage.
- Independent vote in min-ipSAE consensus gating.
- Cofold structures where MSA-driven prediction is preferred over single-sequence inference.

## Hand A Mission To An Agent

```text
Use the BioSymphony Structure Factory skill with the Chai-1 tool card. For target <PDB:ID> and candidate sequence <FASTA>, prepare a Chai-1 cofold lane in MSA mode. Reference the cached target MSA, switch off single-sequence ESM mode, and define the closeout artifacts (per_chain_pair_iptm, aggregate_score, CIF outputs).
```

## Typical Inputs

- Target sequence and candidate binder sequence (FASTA).
- MSA directory containing the target's aligned parquet (`aligned.pqt`).
- Number of trunk recycles and diffusion timesteps.

## Typical Outputs

- Predicted complex structures (CIF).
- NPZ confidence file with `aggregate_score` and `per_chain_pair_iptm`.

## Repo And References

- Repo: https://github.com/chaidiscovery/chai-lab
- Tech report and lab releases linked in the repo.

## Key Knobs

| Knob | Recommendation | Why |
| --- | --- | --- |
| `use_esm_embeddings` | `False` | Default `True` selects single-sequence ESM mode. MSA mode needs `False` plus an MSA directory. |
| `msa_directory` | path containing `aligned.pqt` | Required when `use_esm_embeddings=False`. |
| `num_trunk_recycles` | 3 | Typical default. |
| `num_diffn_timesteps` | 200 | Typical default. |

## Gotchas

- Default `use_esm_embeddings=True` runs single-sequence mode. Many real binder pipelines need MSA mode; switch the flag and supply the MSA explicitly.
- `chai_lab` 0.6.x with pandas 2.2 needs a one-line patch to the parquet `groupby` behavior in `aligned_pqt.py`. Track the upstream issue tracker for the fixed version.
- Chai shows a calibration offset versus Boltz on real binders. Calibrate per-model rather than comparing iPTMs across model families.
- Read `per_chain_pair_iptm[binder, target]` for the interface iPTM rather than the global `iptm` field.

## Gates

- Weight download and runtime use require current upstream license terms.
- Public targets only in public examples.
- Multi-validator slate recommended. Do not promote candidates from Chai alone.
- Run a currency check before any paid GPU dispatch: upstream repo HEAD (releases + recent commits), current release notes, and recent preprints (biorxiv / chemrxiv / arxiv) on the relevant lane. Record the version pin and the date of the check in the candidate ranking or validation notes.
