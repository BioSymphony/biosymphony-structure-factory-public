# SwitchCraft Worked Example — De Novo cGAMP / STING Conformational-Switch Sensor

Companion to [`../switchcraft.md`](../switchcraft.md).

**Status:** worked example — verified public inputs plus draft configs. Outputs
are ranked in-silico single-cofolder hypotheses; result boundary is
`computational_candidate`.

This note shows how to take the SwitchCraft card from "a tool that designs
switches" to a concrete, public-data, design-time plan: a de novo small protein
that is predicted to change conformation when it binds the second-messenger
2'3'-cGAMP, with the human STING sensor used only as a public structural
reference for the switch.

## Source verification log

Every structural input below was checked against a primary public source (RCSB
PDB, PubChem, UniProt/SIFTS) before use. The SwitchCraft schema, loss classes,
and task templates were read directly from the public repository.

| Claim | Source | Verified |
| --- | --- | --- |
| SwitchCraft schema / loss classes / task templates | upstream repo (ICML 2026) | Yes |
| Biosensor precedent (SAM/cGMP/ATP, two-state, len 150-200) | arXiv 2605.31236 | Yes |
| Conditional ligand-induced binders, preliminary wet-lab | arXiv 2605.31236 | Yes |
| Bundled cofolder is one generation behind the cofold stack's primary | repo packaging | Yes |
| Cofolder ships the full wwPDB chemical-component dictionary | repo source | Yes |
| Cofolder training cutoff = PDB released before late 2021 | cofolder paper | Yes |
| STING lid closure + inward rotation on 2'3'-cGAMP | structural papers below | Yes |
| 2'3'-cGAMP = CCD `1SY`, in dozens of deposited entries | RCSB ligand record | Yes |
| 4KSY = human STING CTD + cGAMP, chain A ~152-336 | RCSB + mmCIF parse | Yes |
| 4F5E = human STING CTD apo (buffer only) | RCSB + mmCIF parse | Yes |
| diABZI = PubChem CID 131986624, SMILES below | PubChem | Yes |

Not fully verifiable, flagged: the paper gives an optimizer schedule but not exact
per-loss weights, so the shipped task templates are the only concrete weight
source (strong on discriminating terms, default elsewhere). There is no published
benchmark isolating cyclic-dinucleotide ligand-pose accuracy for the cofolder, so
that is treated as a caveat.

## 1. STING biology — the ligand-induced conformational switch

Human STING (gene STING1 / TMEM173, UniProt Q86WV6) is an ER-membrane adaptor.
Its cytosolic cyclic-dinucleotide-binding domain (CBD/CTD, ~residues 138-379)
forms a V-shaped homodimer with a single ligand pocket at the dimer interface.

The apo to 2'3'-cGAMP-bound switch, as captured by public crystal structures:

1. Wing closure: cGAMP binding pulls the two wing tips together and rotates both
   protomers inward toward the pocket.
2. Lid ordering: a four-stranded antiparallel beta-sheet "lid", disordered/open in
   the apo state, becomes ordered and closes over the bound ligand.
3. A larger domain rotation is seen in full-length cryo-EM structures; the
   isolated CBD crystal structures capture the local open-lid to closed-lid
   transition, which is the part a soluble construct can model.
4. Closure releases the C-terminal tail and exposes an oligomerization interface
   downstream of the switch.

Key public structural papers (human STING CBD): Huang et al. 2012 (c-di-GMP);
Zhang et al. 2013 (2'3'-cGAMP, defines the lid); Shang et al. 2019 (full-length
cryo-EM); the GSK amidobenzimidazole agonist series (synthetic agonists in the
same pocket).

## 2. Verified public PDB structures (human STING CBD)

All map to UniProt Q86WV6. Resolved ranges parsed from public mmCIF.

| PDB | State | Ligand (CCD) | Method | Resolved range | Notes |
| --- | --- | --- | --- | --- | --- |
| 4KSY | closed / holo | `1SY` = 2'3'-cGAMP | X-ray 1.88 A | chain A 152-336 | Cleanest cGAMP-bound reference |
| 4LOH | closed / holo | `1SY` = 2'3'-cGAMP | X-ray | ~155-341 | Two-chain dimer in one file |
| 4EMT | closed / holo | `C2E` = c-di-GMP | X-ray | ~155-341 | Bacterial-CDN holo alternative |
| 5BQX | closed / holo | `4UR` = 3'2'-cGAMP | X-ray | CTD | Linkage-isomer alternative |
| 4F5E | apo / open | buffer only, no CDN | X-ray 2.6 A | chain A 151-336 | Best apo reference (open lid) |
| 6DXL / 6DXG | holo (synthetic) | linked / mono ABZI | X-ray | CTD | Synthetic-agonist pocket |

Note: 6NT5 is the full-length apo receptor (includes the transmembrane region) and
is too large for the soluble demo. One commonly mis-cited code is not STING at all
and should be dropped — verify the UniProt mapping for any candidate.

## 3. Verified public CCD ligand codes

These resolve directly as `ccd:CODE` because the cofolder ships the full wwPDB
chemical-component dictionary.

| Ligand | CCD code | In dictionary | In cofolder training window |
| --- | --- | --- | --- |
| 2'3'-cGAMP (physiological) | `1SY` | Yes | Yes (pre-cutoff complexes exist) |
| 3'3'-cGAMP (bacterial) | `4BW` | Yes | Yes |
| 3'2'-cGAMP | `4UR` | Yes | Yes |
| c-di-GMP | `C2E` | Yes | Yes |
| c-di-AMP | `2BA` | Yes | Yes |

Early guesses at the physiological-cGAMP code were wrong (several similar-looking
codes are unrelated small molecules). The verified physiological-cGAMP code is
`1SY` — confirm against the RCSB ligand record before use.

For diABZI (a synthetic STING agonist with no clean cGAMP-equivalent CCD use),
fall back to SMILES (PubChem CID 131986624):

```
CCN1C(=CC(=N1)C)C(=O)NC2=NC3=C(N2C/C=C/CN4C5=C(C=C(C=C5OCCCN6CCOCC6)C(=O)N)N=C4NC(=O)C7=CC(=NN7CC)C)C(=CC(=C3)C(=O)N)OC
```

## 4. Framing decision — lead with the de novo biosensor

Two options:

- **(A) De novo cGAMP biosensor** — design a small protein (no STING) that adopts
  two distinct confident conformations, apo versus 2'3'-cGAMP-bound, maximizing
  the distogram difference while making real protein-ligand contacts in the holo
  state. This is SwitchCraft's native, paper-demonstrated mode.
- **(B) Conditional binder to closed-state STING** — design a binder that engages
  the STING CBD only when cGAMP is bound. Requires the STING dimer as a target
  chain in both states and depends on the cofolder reproducing the lid-closure
  difference well enough to drive the switch.

Recommendation: lead with (A), keep (B) as a fallback. (A) is the cleaner showcase
because it has direct paper precedent (de novo SAM/cGMP/ATP biosensors with the
same loss stack), a self-contained signal (metrics on the designed protein alone,
no dependence on a second protein's modeled accuracy), a bounded in silico claim,
and a smaller graph (one protein plus one small ligand). (B) carries the
full ~150-residue STING dimer through every pass and tempts an over-claim, but it
ties more literally to STING biology, so it is worth one contrast arm.

## 5. Draft configs

Both were validated structurally against the repo's designer/loss builder and the
shipped task templates. Place under the repo's task directory and run from the
repo root, smoking at N=1 first.

### Primary — de novo two-state cGAMP biosensor (Option A)

```yaml
# De-novo 2'3'-cGAMP biosensor: a small protein that changes conformation on
# cGAMP binding. State 0 = apo; State 1 = holo (2'3'-cGAMP = ccd:1SY).
# A contact loss is auto-added to both states by default.
num_states: 2
motifs: []
length: 160          # paper biosensors used 150-200; also sweep 150/180/200
states:
  - []               # state 0: apo
  - ["ccd:1SY"]      # state 1: holo, 2'3'-cGAMP (verified CCD code)
losses:
  - type: LigandContactLoss     # promote protein<->cGAMP contact ONLY in holo
    state: 1
    strength: 10                # discriminating term, strong
  - type: ConfChangeLoss        # maximize apo<->holo distogram divergence (the switch)
    state: [0, 1]
    strength: 10                # discriminating term, strong
  - type: RadiusOfGyrationLoss  # keep folds compact (hygiene)
    state: 0
    strength: 1.0
  - type: RadiusOfGyrationLoss
    state: 1
    strength: 1.0
```

Strength rationale: the two terms that define the switch (ligand must bind in
holo; apo and holo must differ) get the strong weight that the shipped
discriminating tasks use; the auto contact loss and the soft radius-of-gyration
terms are hygiene that keep both states foldable and compact.

### Fallback — conditional binder to closed STING (Option B)

```yaml
# Conditional binder: engages STING CBD only when 2'3'-cGAMP is present.
# State 0 = STING apo (binder does not contact); State 1 = STING + cGAMP (binder contacts).
# Provide STING as a protein chain in BOTH states; add cGAMP only in state 1.
num_states: 2
motifs: []
length: 80           # the DESIGNED binder length (STING is a provided target)
states:
  # carve the human STING CBD sequence (UniProt Q86WV6, ~residues 152-336) from
  # public PDB 4KSY chain A: extract the resolved span, drop ligand/HETATM,
  # and paste the one-letter sequence into both protein strings.
  - ["protein:<STING_CBD_152_336_FROM_4KSY>"]
  - ["protein:<STING_CBD_152_336_FROM_4KSY>", "ccd:1SY"]
losses:
  - type: AntiLigandContactLoss   # do NOT touch STING when apo
    state: 0
    idx: 1
    strength: 10
  - type: LigandContactLoss       # DO touch STING when cGAMP present
    state: 1
    idx: 1
    strength: 10
  - type: ConfChangeLoss          # optional: encourage the binder to rearrange
    state: [0, 1]
    strength: 5
```

Schema caveat for the fallback: the contact-loss `idx` selects a chain by id. The
designed binder is chain 0; the first added non-designed chain is chain 1; cGAMP
added in state 1 becomes a further chain. The losses above target the STING
protein chain (`idx: 1`). Verify chain ordering on the N=1 smoke by inspecting the
output chain ids before scaling. The STING sequence is a public reference carved
from a deposited structure; use it only as a public structural reference.

## 6. Feasibility and caveats

Is cGAMP a realistic ligand for single-cofolder contact design?

- In-distribution: yes. 2'3'-cGAMP appears in dozens of deposited entries,
  including human STING complexes, all before the cofolder's training cutoff. The
  model has very likely seen cGAMP in a protein pocket, which is materially better
  odds than a brand-new chemotype.
- But it is a hard ligand: large (~674 Da), doubly anionic, flexible. Co-folding
  models place rigid, neutral, drug-like ligands best; large charged flexible
  nucleotides are noisier. The paper's biosensors used smaller, less-charged
  single nucleotides, so cGAMP is a reasonable but more ambitious extension —
  expect a per-design success rate at or below the paper's biosensor rate.
- The ligand-contact loss uses a generous contact cutoff, so a passing contact
  term means "ligand near the protein core," not "ligand correctly posed." Always
  spot-check holo poses visually.

Compute posture: each design is one multistate gradient-design trajectory plus a
few final structure predictions per state. The paper's biosensor campaign ran far
more designs than a demo needs; a demo needs only a smoke at N=1 and then roughly
50-100 designs to expect a handful of switch-worthy hits. This needs a GPU cloud
adapter (A100/H100-class); no warm cache should be assumed, and first-boot setup
includes the pinned cofolder install and a weight/dictionary download. Calibrate
the real per-design wall-clock on the N=1 smoke before quoting any figure, and
validate the output count at each stage before declaring it complete.

The load-bearing caveat: SwitchCraft validates with a single cofolder. A "sensor"
here is a single-model hypothesis — a sequence that one cofolder predicts adopts
two distinct, confident, ligand-dependent conformations. There is no orthogonal
cofolder check or MD in the loop, so independent confirmation would minimally
require re-folding both states in a different model and confirming the cross-state
difference and holo binding survive — and even that is model-versus-model
agreement. The result boundary is a single-cofolder `computational_candidate`
("designs that one cofolder scores as cGAMP-responsive conformational switches"),
not a validated sensor.

Net verdict: Option A is a green-light design-time demo — native to SwitchCraft,
in the cofolder's training distribution, self-contained signal, modest compute.
Caveat it as a single-cofolder hypothesis, temper the expected hit rate for
cGAMP's size and charge, and visually QC holo poses. Option B is a viable but
riskier fallback that ties more literally to STING biology.

## 7. Concrete next actions

1. Install the SwitchCraft framework from source (pinned cofolder, sequence model,
   weights, and chemical-component dictionary download) on a GPU cloud adapter.
2. Drop in the Section 5 primary biosensor config.
3. Smoke at N=1 on `ccd:1SY`: assert the per-state output files exist, parse one
   structure, and confirm the ligand is resolved in the holo prediction. Only then
   scale to ~50-100, validating output count at each stage.
4. Rank by a cross-state backbone difference, a strong holo ligand-interface
   score, low within-state deviation in both states, high per-residue confidence,
   and a compact radius of gyration. The top design is the demo artifact.
5. Optionally run the Option B contrast after carving the full public STING
   sequence; verify chain ordering on its own N=1 before scaling.

Route every artifact through the [cofold scoring stack](../cofold-scoring-stack.md)
for the orthogonal switch check, and keep all results at `computational_candidate`.
