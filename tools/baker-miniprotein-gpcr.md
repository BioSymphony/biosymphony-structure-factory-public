# Baker Miniprotein-GPCR Pipeline

## Purpose

Plan de novo miniprotein modulator lanes for G-protein-coupled receptors,
including the Class B targets GLP1R, GIPR, and GCGR. This is a **methods bundle,
not a forked tool**: the Baker lab protocol layers three existing upstream tools —
RFdiffusion (motif-scaffolded), ProteinMPNN, and AlphaFold2 as an initial-guess
filter — with GPCR-specific input preparation (active-state versus extracellular-
domain targeting, peptide-motif anchoring, hotspot picking). The published work
also includes an industrialized mammalian-cell screen; that wet-lab stage is out
of scope here. This card covers the in silico design and filtering cascade only.

## Public-Safe Status

Public scaffold: yes. There is no first-party code repository — the protocol is a
recipe over upstream RFdiffusion + ProteinMPNN + AlphaFold2, reconstructed from
the paper's methods. Cite the paper, not a Baker lab repo, in deliverables. The
upstream tools keep their own license posture (see their cards). Store weights
and generated structures under ignored runtime storage or in a user-selected
artifact store.

## When To Use

- Class B GPCR extracellular-domain (ECD) antagonists, by mimicking the N-terminal
  helix of the cognate peptide hormone (glucagon for GCGR, GLP-1 for GLP1R, GIP
  for GIPR).
- When a literature-anchored hotspot set and a peptide-mimicry baseline exist for
  the target, so the design is motif-directed rather than generic.
- As a GPCR-tuned variant of a generic RFdiffusion + ProteinMPNN + AF2 binder run:
  same three tools, GPCR-specific inputs.
- Class B ECD targeting suits a folded soluble target (no membrane-embedded
  receptor and no detergent/lipid handling downstream).

## How It Differs From A Generic Binder Run

A generic baseline is vanilla RFdiffusion + ProteinMPNN + AF2 with generic
hotspots. This card is the same three tools with GPCR-tuned inputs: a peptide
motif anchored into the contig, ECD-specific published hotspots, a
partial-diffusion noise schedule for motif-preserving refinement, and
target-specific filter thresholds. It tests whether GPCR-tuned priors beat the
generic protocol on a GPCR target.

## Hand A Mission To An Agent

```text
Use the BioSymphony Structure Factory skill with the Baker miniprotein-GPCR tool
card. For a Class B GPCR ECD target (for example GCGR), prepare a motif-directed
RFdiffusion lane: anchor the cognate peptide's ECD-facing motif into the contig,
set the published ECD hotspots, run partial diffusion for motif preservation, then
SolubleMPNN sequencing and an AF2 initial-guess filter, feeding survivors into the
cofold scoring stack. Use public deposited structures only; cite the paper, not a
repo; do not run paid compute until the operator gate records budget and cleanup.
```

## Typical Inputs

- Target ECD structure from a public deposited entry (for GCGR: PDB 4ERS chain B
  ECD, or 6LMK; references 5XEZ).
- The cognate peptide motif as a small structural fragment (for GCGR: glucagon
  residues around the ECD-facing pentamer, from 4ERS/6LMK).
- Published Class B ECD hotspots for the target.
- A contig specification anchoring the motif with flanking designed regions.

## Typical Outputs

- Generated backbones (one structure plus metadata per design), outside git.
- SolubleMPNN sequences per backbone.
- AF2 and cofold metrics per design (binder confidence, interface PAE, interface
  energy, motif RMSD to the cognate peptide, scaffold topology).
- A handoff manifest into the cofold scoring stack.

## Repo And References

- No first-party code repo. Upstream tools:
  - RFdiffusion: https://github.com/RosettaCommons/RFdiffusion
  - ProteinMPNN: https://github.com/dauparas/ProteinMPNN
- Paper: Muratspahić E, Feldman D, Kim DE, Qu X, Krumm BE, Tate CG, Baker D, et al.
  *De novo design of miniprotein agonists and antagonists targeting G protein-
  coupled receptors.* bioRxiv 2025.03.23.644666 (v2, 2025).
- DOI: https://doi.org/10.1101/2025.03.23.644666
- PubMed: https://pubmed.ncbi.nlm.nih.gov/40501737/ (PMC: PMC12157396)
- Baker lab publications: https://www.bakerlab.org/publications/

## Key Knobs

| Knob | GPCR-tuned value | Why |
| --- | --- | --- |
| `contigmap.contigs` | anchor the cognate peptide's 6-residue ECD-facing motif with ~30/30 flanking designed regions | Scaffolds a binder around the peptide-mimicry motif. |
| `ppi.hotspot_res` | published Class B ECD hotspots (GCGR: B33, B36, B87; GLP1R and GIPR have their own published picks) | Steers the interface to the cognate-peptide groove. |
| `diffuser.partial_T` | 10-20 (partial) | Motif-preserving refinement rounds; do not run partial diffusion against a target PDB with missing residues, which silently scrambles the motif. |
| `inference.num_designs` | large for production | Class B ECD binders are low-yield; the paper screens on the order of 10^4 designs to surface a small expressing set. |
| ProteinMPNN sequences per backbone | ~10 | Use SolubleMPNN (`--use_soluble_model`) for these soluble ECD targets. |
| AF2 interface-PAE filter | tight (for example < 8) | Paper Class B filter. |
| AF2 binder-confidence filter | high (for example > 85, tighter for the hardest targets) | Paper Class B filter. |
| Interface-energy filter | strict for in silico triage | When the screen is not run, in silico filters do all triage; prefer the paper's strict thresholds. |

## Gotchas

- No first-party code release: the protocol is reconstructed from the paper's
  methods. The integrator owns the wiring; cite the paper.
- The peptide-mimicry motif requires structural data. If the cognate peptide is
  unstructured at the binding interface, the protocol degrades to a generic
  RFdiffusion run.
- Hotspots must reference the chain id actually used in the contig; the paper uses
  different chain letters across targets, so relabel input PDBs to a consistent
  receptor chain before running.
- Without the mammalian-cell screen, the published expression hit rates do not
  apply; in silico filters must do all triage, which biases toward conservative
  (strict) thresholds.
- The paper's metaproteome-derived scaffold variant is not released; only the
  motif-directed RFdiffusion track is reproducible from public tools.

## Gates

- Public examples use deposited targets. Store generated structures and sequences
  under ignored runtime storage or in a user-selected artifact store.
- This card composes other cards — sequence design via [ProteinMPNN](proteinmpnn.md)
  (SolubleMPNN), backbones via [RFdiffusion3](rfdiffusion3.md), validation via the
  [cofold scoring stack](cofold-scoring-stack.md); each keeps its own gates. See
  [GCGR target prep](gcgr-target-prep.md) for the target-window pattern.
- Cap every candidate ranking at `computational_candidate`; binding, agonism,
  antagonism, and therapeutic value are confirmed downstream by wet-lab and
  clinical processes outside this repo.
- Run a currency check before any paid GPU dispatch: upstream RFdiffusion and
  ProteinMPNN repo HEAD, and the current preprint version. Record the version pin
  and the date of the check in the candidate ranking or validation notes.
