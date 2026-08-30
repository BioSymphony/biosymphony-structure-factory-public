# ESMFold2 Binder Control Notes

Public-safe notes for controlling and constraining ESMFold2/Biohub-style
binder-design runs in Structure Factory.

These notes distinguish three layers:

- Model-facing controls: logits, mutable positions, target sequence, scaffold,
  optimizer settings, and loss terms.
- Wrapper controls: hard masks, soft biases, per-position rules, fanout policy,
  and campaign-specific scoring.
- Downstream filters: site overlap, pI, composition, clashes, confidence, and
  validation notes.

The result boundary for these runs is a `computational_candidate`: site-recovery
or a foldability/interface-geometry hypothesis. These controls do not by
themselves establish binding, affinity, specificity, inhibition, or activity.
Wet-lab confirmation lives downstream of this card.

## Where These Controls Live

The controls split across three places, and a campaign wrapper wires them
together:

- The ESMFold2/Biohub binder-design loop exposes the model-facing controls
  (mutable `#` prompt slots, target sequence, scaffold, loss terms, optimizer
  settings). See [ESMFold2](esmfold2.md).
- A thin wrapper adds the hard masks, soft biases, per-position rules, fanout
  policy, and campaign scoring that the base loop does not.
- Downstream scoring compares candidates against a deposited target site, applies
  the filters below, and routes survivors through the
  [cofold scoring stack](cofold-scoring-stack.md) for an orthogonal check.

Constrained-alphabet runs use an `allowed_amino_acids` hard mask on mutable
binder positions: disallowed residue logits are driven to a very low value and
their gradients are masked. Fixed scaffold residues can remain outside the
allowed alphabet.

## Sequence Controls

- Hard amino-acid allow list: only a declared set such as `LEK` or `GPWYF`.
- Hard amino-acid deny list: no cysteine, no proline, no aromatics, no glycine,
  or other exclusions.
- Soft amino-acid bias: favor or discourage residues without banning the rest.
- Per-position amino-acid rules: different allowed sets for different binder
  positions.
- Composition targets: desired ranges for charged, hydrophobic, aromatic, polar,
  or special-case residues.
- Net charge and pI targets: acidic, neutral, basic, or bounded pI designs.
- Low-complexity avoidance: penalize repeats, single-residue runs, and simple
  sequence patterns.
- Motif avoidance: avoid N-glycosylation motifs, methionine oxidation motifs,
  deamidation-prone motifs, protease motifs, or other liabilities.
- Motif encouragement: bias helix caps, salt-bridge patterns, aromatic patches,
  or other local motifs.
- Fixed residues: keep specified binder positions constant.
- Mutable residues: expose only selected positions through the `#` prompt slots.
- Sequence length: run separate bins such as 60, 90, 120, or 160 residues.
- Family diversity: select candidates with sequence distance or composition
  diversity instead of near-duplicates.

## Structure Controls

- Binder scaffold: free minibinder, antibody framework, or custom scaffold.
- Mutable-region length ranges: CDR length, loop length, or full minibinder
  length.
- Compactness and globularity: reward compact folds and penalize rod-like
  shapes.
- Internal contact density: reward a packed binder core.
- Helix bias: encourage mostly helical binders.
- Sheet avoidance: avoid beta-rich or aggregation-looking designs.
- Loop control: restrict loop length, glycine/proline use, or flexibility.
- Repeat control: encourage or avoid repeat-like shapes.
- Disulfide posture: forbid cysteine, allow cysteine, or add explicit
  disulfide-pair logic in a future wrapper.
- Surface exposure pattern: hydrophobic residues buried, polar and charged
  residues exposed.
- Shape class: compact bundle, long helix, flat patch, clamp-like binder, or
  loop-dominant binder.

## Interface Controls

- General target contact: reward binder-target proximity.
- Target hotspot contact: reward contacts to specified receptor residues.
- Off-site penalty: penalize contacts away from the intended target region.
- Contact count target: require at least a minimum number of target-contact
  residues.
- Contact distance target: tune the target-contact distance threshold.
- Interface area target: encourage larger or smaller buried surface.
- Interface chemistry: bias salt bridges, hydrogen bonds, hydrophobic packing,
  or aromatic contacts.
- Clash penalty: reject or penalize severe overlap.
- Orientation control: favor approach from a specific receptor side.
- Negative design: penalize contacts to related receptors or wrong receptor
  regions.
- Multistate design: reward one receptor conformation and penalize another.

## Logits And Model-Signal Uses

The Biohub logits API fields are best treated as observability and possible
auxiliary loss signals unless the wrapper explicitly turns them into controls.

- Sequence logits: show where the model preferred residues blocked by a mask.
- Structure logits: detect uncertain or unstable structural regions.
- Secondary-structure logits: bias toward helices or away from beta-rich and
  floppy regions.
- SASA logits: encourage exposed polar residues and buried hydrophobics.
- Function logits: screen for unwanted functional or domain-like signals once
  label semantics are understood.
- Residue-annotation logits: inspect residue-level predicted annotations or
  liabilities.
- Logit entropy: flag indecisive positions.
- Mask pressure: measure where the hard mask most strongly opposed the model.
- Per-position alternatives: report top residue choices before and after a
  constraint.

## Optimization Controls

- Design step count.
- Learning rate.
- Temperature schedule.
- Batch size.
- Seed count and seed ranges.
- Critic model choice.
- Fast versus full scoring.
- Number of fold samples.
- Number of final refolds.
- Structure-loss weight.
- Language-model plausibility weight.
- Binder compactness weight.
- Interface-contact weight.
- Candidate selection order.

## Downstream Filters And Ranking

- Deposited-site overlap.
- Interface confidence.
- Fold confidence.
- Length.
- pI.
- Net charge.
- Hydrophobicity.
- Aromatic fraction.
- Glycine/proline fraction.
- Cysteine count.
- Low-complexity score.
- Repeat score.
- Clash score.
- Target drift.
- Candidate diversity.
- Weak or off-site contrast selection for visualization.

## Useful Next Experiments

- Hard mask versus soft bias: keep the same amino-acid theme but test whether
  soft bias gives cleaner structures.
- Helical-face constraint: hydrophobic residues on one helix face and
  polar/charged residues on the other.
- Compact constrained-alphabet rescue: keep a small alphabet but cap length and
  reward compactness to reduce rod-like shapes.
- Pocket-first design: reward contacts to a deposited receptor pocket region
  (for example, the GLP-1R semaglutide-contact region) during generation.
- Off-target penalty: reward pocket contact while penalizing non-pocket contact.
- Aromatic patch stress test: run `FWY` or `GPWYF` with aromatic-fraction caps.
- Salt-bridge ladder: bias alternating acidic/basic residues on helical
  positions.
- Tiny binder challenge: constrain to short binders only.
- Designability map: visualize positions where constraints helped or fought the
  model.

## Public Wording

Good public-safe summary:

> We constrained the amino-acid choices available to the ESMFold2/Biohub
> binder-design loop, generated candidate mini-protein complexes on a cloud GPU
> backend, and compared the candidates against the same deposited receptor
> pocket region. The result is a structure-comparison demo, not binding or
> activity evidence.

Avoid wording that suggests measured binding, potency, specificity, therapeutic
effect, or marketed-drug-like activity.
