# GCGR Target Prep

## Purpose

Show the target-prep card pattern for a public class-B GPCR target: select deposited structures, define chains and residue windows, separate target-site modes, derive public hotspots, and emit a manifest for downstream design lanes.

## Public-Safe Status

Public scaffold: yes. Use public deposited structures, public sequence metadata, and public literature context only. Do not commit extracted coordinate subsets, generated peptides, designed sequences, provider logs, or private run notes.

## When To Use

- You need a worked example of turning a public receptor target into a design-ready target window.
- You are preparing peptide, cyclic-peptide, or miniprotein binder lanes against a GPCR-style target.
- You need to teach an agent the difference between "binds this surface" and "stabilizes this functional receptor state."
- You want a reusable pattern for positive controls, negative controls, chain identity checks, and hotspot derivation.

## Hand A Mission To An Agent

```text
Use the BioSymphony Structure Factory skill with the GCGR Target Prep tool card. Using public PDB structures of the glucagon receptor, build a target-window file with chain mapping, residue numbering, hotspot derivation, positive and negative controls, and the downstream design and cofold handoff.
```

## Typical Inputs

- Public PDB or EMDB accessions.
- Target chain and residue numbering.
- Ligand or interface contact context.
- Desired design mode: ECD-side binding, orthosteric-pocket binding, state-selective/agonist-like stabilization, or exploratory blind search.
- Exclusion list for private or unpublished data.

## Typical Outputs

- Target-window file.
- Hotspot and extended residue lists.
- Structure subset instructions.
- Positive and negative control definitions.
- Validation notes stating that target prep is not binding, activity, or functional validation.

## Public Target Pattern

GCGR is useful as a public worked example because it has multiple deposited receptor states and peptide-bound complexes. The same pattern applies to other receptors:

1. **Choose the biology mode before choosing the structure.**
   ECD-side blocking, orthosteric-pocket binding, and agonist-like state stabilization are different tasks. They need different residue windows, controls, and scoring gates.

2. **Pin chain identity and numbering.**
   Record the PDB accession, model, chain identifiers, UniProt accession, resolved residue range, and whether residue numbering is author numbering or UniProt numbering. Use SIFTS or another mapping source; do not infer from chain labels alone.

3. **Verify resolved domains.**
   A high-resolution deposited structure may omit the domain you intend to design against. If the ECD, stalk, loop, or pocket residues are unresolved, mark the run blocked or choose a different public structure.

4. **Derive hotspots from the specific structure.**
   Literature hotspots are sanity references. For a real run, recompute contacts from the chosen receptor and ligand chains, then record the cutoff, atom selection, and post-filtering rule.

5. **Separate controls from candidates.**
   Positive controls are known public ligands or deposited complexes used to verify plumbing. Negative controls can include scrambled or off-target peptides. Controls help calibrate the scoring stack; they are not new candidate claims.

6. **Route the designer arm by binder length and topology.**
   Short cyclic peptides, short linear peptides, helical peptides, and miniproteins have different tools and failure modes. Do not compare arms until each arm has passed a one-design smoke on the exact target window.

7. **Gate functional-state claims separately.**
   A candidate that contacts the receptor is not automatically an agonist, antagonist, or state-selective binder. Functional-state work needs state geometry checks in addition to interface confidence.

## Example Public Accessions

Treat this table as a starting map, not a source of truth. Re-check RCSB, PDBe/SIFTS, and current literature before any paid dispatch.

| Use | Examples | Notes |
| --- | --- | --- |
| Active peptide-bound receptor state | `6LMK`, `8JIQ`, `7V35`, related public GCGR peptide complexes | Useful for contact derivation, positive-control cofolds, and active-state geometry. Verify chain IDs and resolved ranges in the exact downloaded file. |
| Inactive/reference receptor state | `5XEZ` and other public inactive/reference entries | Useful for state comparison and visual sanity checks. Check for engineered fusions, stabilizing mutations, missing loops, and numbering offsets. |
| Related-receptor selectivity context | public GLP-1R and GIPR peptide-bound structures | Useful for selectivity planning. Do not call a GCGR-only pass selectivity-aware without parallel off-target checks. |

For any public target, prefer recording a machine-readable table with:

```json
{
  "accession": "PDB:<id>",
  "model": 1,
  "chain_id": "<label-or-auth-chain>",
  "uniprot": "<accession>",
  "resolved_range": "<start-end>",
  "numbering_source": "SIFTS|PDB-author|UniProt-renumbered",
  "retrieved_at": "YYYY-MM-DD",
  "intended_use": "positive_control|target_window|state_reference|off_target_control"
}
```

## Design-Mode Split

| Mode | Practical target window | Typical tools | Extra checks |
| --- | --- | --- | --- |
| ECD-side or surface binder | Resolved extracellular domain, stalk, or exposed groove | RFdiffusion3, Genie3, ProteinMPNN, PepGLAD for short peptides | Chain identity, hotspot contacts, cofold interface confidence, visual pocket sanity check |
| Short peptide or cyclic peptide | Public peptide-bound pocket or manually curated residue set | RFpeptides, PepGLAD, EvoBind, HelixDiff | Length/topology smoke, generated-sequence custody, cofold slate |
| Agonist-like or state-selective design | Active-state pocket plus state-comparison reference | EvoBind, motif scaffolding, specialist peptide tools | Pocket-distance, anchor-residue, receptor-state, and active/inactive geometry checks |
| Selectivity-aware design | Target plus related receptor structures | Same designer arms, run in parallel | Parallel off-target cofolds and matched score tables |

## Hotspot Derivation Pattern

A simple public-release pattern is contact-derived hotspot generation:

1. Fetch the public receptor-ligand structure outside git.
2. Map receptor residues to the target numbering scheme.
3. Compute receptor residues within a declared cutoff of the ligand or reference peptide.
4. Split contacts by region, for example ECD/stalk, orthosteric pocket, loops, and transmembrane bundle.
5. Manually review the residue patch in a viewer.
6. Save only the hotspot table and extraction recipe in git; keep coordinate subsets and rendered debug files outside git unless they are small, curated, and clearly public.

Minimal pseudocode:

```python
for ligand_atom in ligand_atoms:
    for receptor_atom in receptor_atoms_within_cutoff(ligand_atom, cutoff_angstrom):
        hits.add((receptor_chain, receptor_residue_number, receptor_residue_name))
```

## Control Set Pattern

- **Positive controls:** deposited public complexes or public peptide ligands expected to recover the known binding mode. Use them to prove that the cofold and scoring stack can reproduce an already-known interaction.
- **Negative controls:** scrambled peptides, off-target family ligands, or decoy sequences with the same rough length/composition. Use them to detect overconfident scoring.
- **State controls:** active and inactive receptor references when the campaign cares about functional state.

Controls should be stored as public accessions, sequence references, or synthetic rows. Do not commit generated candidate structures or new unpublished sequences.

## Gates

- Record exact accession, chain, residue numbering, and extraction rules.
- Do not store raw maps or generated structure subsets in git.
- Treat ambiguous residues or unresolved loops as risk notes, not hidden assumptions.
- Verify the deposited structure's resolved range against SIFTS and check recent depositions in the PDB for the same target. A newer entry may resolve a domain that was disordered in the deposition you started from.
- Before any paid design lane, verify the first 20 resolved residues of the intended receptor chain against the expected public sequence.
- Before RFdiffusion3-style hotspot conditioning, verify the required atoms exist on each hotspot residue in the actual PDB file.
- Before promoting any candidate ranking, check that the predicted binder is near the intended site, not merely near some receptor surface.
- Record the chosen accession, retrieval date, source posture, and result boundary in validation notes.
