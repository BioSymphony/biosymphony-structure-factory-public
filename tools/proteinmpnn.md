# ProteinMPNN

## Purpose

Plan sequence-design lanes that assign sequences to a generated backbone or scaffolded interface. ProteinMPNN takes a structure as input and produces sequences that fold to that structure.

## Public-Safe Status

Public scaffold: yes. Runtime use requires current source review against upstream terms. Weights are openly released.

## When To Use

- After RFdiffusion, RFdiffusion3, Genie3, HelixDiff, or PepGLAD to assign sequences to a generated backbone.
- After motif-anchored scaffolding to design sequence around a preserved binding motif.
- For comparing wild-type sequence likelihood at design positions.

## Variants

- **Vanilla ProteinMPNN.** Original release. General-purpose backbone-to-sequence design.
- **SolubleMPNN.** Activate with `--use_soluble_model`. Favors solubility-correlated residue choices. Public benchmarks have reported higher wet-lab expression rates with SolubleMPNN compared to vanilla for soluble-protein design; check the current benchmark literature for your target class.

## Hand A Mission To An Agent

```text
Use the BioSymphony Structure Factory skill with the ProteinMPNN tool card. For backbone <PDB path or RFdiffusion output>, prepare a sequence-design lane. Use SolubleMPNN for soluble targets, fix the motif residues if a binding anchor must be preserved, generate 8 to 10 sequences per backbone, and define the closeout artifacts (FASTA, score files, per-position log-probabilities).
```

## Typical Inputs

- Backbone PDB or CIF file.
- Optional design mask indicating positions to design.
- Optional fixed residues to preserve a motif or known anchor.
- Number of sequences per backbone.

## Typical Outputs

- Designed sequences in FASTA.
- Per-position log-probabilities.
- Score files for ranking.

## Repo And References

- Repo: https://github.com/dauparas/ProteinMPNN
- ProteinMPNN paper: Dauparas et al., *Science* 2022.

## Key Knobs

| Knob | Recommendation | Why |
| --- | --- | --- |
| `--num_seq_per_target` | 8 to 10 | Standard range across published benchmarks. |
| `--sampling_temp` | 0.1 to 0.3 | Lower for stricter sequences, higher for diversity. |
| `--use_soluble_model` | on for soluble targets | Use SolubleMPNN variant. |
| `--fix_residues` | required for motif anchors | Preserve residues that must keep contact with the target. |

## Gotchas

- Standard ProteinMPNN is not cyclic-aware. Use the cyclic flag or a cyclic variant for macrocyclic peptide work.
- For interface design, condition on the receptor context (include the target chain) rather than designing the binder in isolation.
- Sequence diversity is sensitive to `sampling_temp`. Sweep it for downstream cofold lanes that benefit from a broader ensemble.

## Gates

- Public targets only in public examples.
- Store sequences for private targets under ignored runtime storage or in a user-selected artifact store.
- Wet-lab confirmation lives downstream of this card.
- Run a currency check before any paid GPU dispatch: upstream repo HEAD (releases + recent commits), current release notes, and recent preprints (biorxiv / chemrxiv / arxiv) on the relevant lane. Record the version pin and the date of the check in the candidate ranking or validation notes.
