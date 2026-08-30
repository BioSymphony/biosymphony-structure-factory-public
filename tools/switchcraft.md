# SwitchCraft

## Purpose

Plan multistate / switch design lanes — the design of a single sequence that
adopts different structures in different ligand contexts. SwitchCraft (MIT,
ICML 2026) is a gradient-design framework built on BoltzDesign1 that optimizes a
single cofolder's distogram head to produce apo-versus-holo, bound-versus-unbound,
or ligand-1-versus-ligand-2 conformations. It opens a category the other cards do
not cover: allostery, induced binding (a molecular AND gate), ligand
discrimination, motif toggling, and de novo small-molecule biosensors. It is
**not** a binder designer and not a competitor to RFdiffusion3 or the peptide
arms. Its deliverable is a conformational change — a morph between states.

## Public-Safe Status

Public scaffold: yes. The framework is MIT-licensed and vendors an open cofolder
plus an open sequence-design model. Runtime execution still requires current
source review of the repo and its pinned dependencies, plus weight-download and
cost posture. Generated sequences and structures stay in ignored runtime
storage or a user-selected artifact store.

## When To Use

- Allostery: a motif that forms or breaks on ligand binding.
- Induced binding: a two-input AND gate where output engages only with both
  inputs present.
- Ligand discrimination: distinct conformations for distinct ligands.
- De novo small-molecule biosensors: a designed fold that switches on a target
  small molecule. See the worked example in
  [`switchcraft/sting-exploration.md`](switchcraft/sting-exploration.md).
- When the deliverable is a conformational change you can render as a morph.

## How It Works

The optimization touches the distogram head only; 3D coordinates are sampled once
at the end and never fed back into the loss, so "conformational change" means a
change in predicted pairwise-distance distribution. The same designed sequence is
folded in each ligand context (ligand tokens differ, protein tokens are shared),
and the signature loss maximizes the divergence between two states' distograms to
reward a localized, large change. An optional tied multistate sequence redesign +
re-fold step is the only in-loop guard against single-model adversarial
sequences.

## Verified Paper Results

Read the denominators — these are low-yield design tasks where the controls make
the relative signal credible (random natural miniproteins pass at ~zero).

| Task | Reported success / total |
| --- | --- |
| Positive/negative allostery | 11/24 motifs had at least one hit (100 designs each) |
| Motif switching | 3/100 |
| Ligand modification | ~10/558 |
| Induced binding (AND gate) | ~8/940 |
| Ligand discrimination (3-state) | ~12/465 |
| De novo biosensor (SAM/cGMP/ATP) | 44 confirmed from ~13,858 |

A small wet-lab toehold (conditional zinc-induced binders) is reported by the
authors as preliminary.

## Hand A Mission To An Agent

```text
Use the BioSymphony Structure Factory skill with the SwitchCraft tool card. For a
two-state design (apo and a target small-molecule holo state), plan a multistate
design lane: define the per-state ligand contexts, the conformational-change and
ligand-contact losses, and a length sweep. Then route every output through the
cofold scoring stack for an orthogonal switch check before any render. Do not run
paid compute until operator budget, runtime, weight-download, and cleanup are
recorded. Smoke at N=1 on the real config before scaling.
```

## Typical Inputs

- Number of states and the per-state ligand context (CCD codes for in-dictionary
  ligands, or SMILES for novel chemotypes), public ligands only in public
  examples.
- Designed length (and a sweep), optional motif constraints.
- A loss configuration (conformational-change, ligand-contact, compactness) with
  per-term strengths.

## Typical Outputs

- Per-state predicted structures (one file per state per sample), outside git.
- A per-residue conformational-change map derived from the divergence loss.
- A morph between states for rendering.
- A handoff manifest into the cofold scoring stack and the refinement stack.

## Repo And References

- Repo: https://github.com/bjing2016/switchcraft (MIT)
- Paper: *SwitchCraft: A Programmatic Framework for Designing State-Switching
  Proteins.* ICML 2026, https://arxiv.org/abs/2605.31236
- Base framework (BoltzDesign1): https://github.com/yehlincho/BoltzDesign1
- Cofolder (Boltz): https://github.com/jwohlwend/boltz
- Sequence model (LigandMPNN): https://github.com/dauparas/LigandMPNN

## Key Knobs

| Knob | Recommendation | Why |
| --- | --- | --- |
| States | Start with 2 (apo + one holo) | Smaller graph, cleaner signal than 3-state. |
| Switch loss strength | Strong on the discriminating terms | The conformational-change and ligand-contact terms define the switch; compactness terms are hygiene. |
| Length | Sweep around the paper's biosensor range | Yield is length-sensitive; a sweep finds the workable band. |
| Tied redesign + re-fold | On when feasible | The only in-loop antidote to single-model adversarial sequences. |
| Working directory | Run from the repo root | Checkpoints and motif files load by relative path. |
| First run | Smoke at N=1, parse one structure, confirm the states differ | Per repo discipline; never scale before a parsed, validated N=1. |

## Gotchas

- Single-cofolder, circular loop: the design optimizes one cofolder's distogram
  and the shipped code "validates" with the same model. This is the most
  important caveat — route every output through an orthogonal cofolder.
- The shipped evaluation code reports metrics but defines no pass/fail threshold;
  reproducing "success" means re-deriving thresholds yourself.
- Switches can be kinetically implausible: only the endpoints are optimized, never
  the transition path. Claim the endpoints, not the mechanism.
- The vendored cofolder is one generation behind the cofold scoring stack's
  primary, so the orthogonal check also moves the prediction forward a generation.
- Some repo conveniences are brittle (a visualization helper is broken upstream,
  the model reloads per design, there is no RNG seeding). Treat the shipped code
  as a starting point.

## Gates

- Route every designed switch through the [cofold scoring stack](cofold-scoring-stack.md)
  for an independent confirmation that the conformational change survives a second
  predictor, then the [refinement stack](refinement-stack.md) before any render.
- A switch here is a single-model hypothesis, not a validated sensor or allosteric
  protein; cap results at `computational_candidate` until an orthogonal cofolder
  confirms the change.
- Public ligands and accessions only in public examples; novel-chemotype SMILES
  must be public.
- Weights, generated sequences, and structures stay in ignored runtime storage
  or a user-selected artifact store.
- For bolting a reporter or effector onto a validated switch, hand off to
  [`domino.md`](domino.md) under its own license gate.
- Run a currency check before any paid GPU dispatch: upstream repo HEAD, the
  pinned cofolder/sequence-model versions, and recent preprints on multistate or
  switch design. Record the version pin and the date of the check.
