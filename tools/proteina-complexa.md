# Proteina-Complexa

## Purpose

Use Proteina-Complexa for protein-binder, ligand-binder, or motif-binder
generation with sequence and structure outputs.

## Public Status

The upstream repository records Apache-2.0 for code and the NVIDIA Open Model
License Agreement for weights. Review the model terms for the user's intended
use before downloading or running the selected checkpoints.

Proteina-Complexa is not limited to the predefined demonstration targets. Its
inference guide documents custom protein and ligand target records with source
structure, chain ranges, hotspot residues, and binder-length bounds.

## Run Shape

1. Define or select a target record.
2. Validate the design configuration and checkpoint availability.
3. Run a one-sample generation canary.
4. Count and parse the sequence and structure outputs.
5. Continue through the declared inverse-folding and independent cofold score
   operations before scaling.

Record whether the run used a predefined task or a custom target. For custom
targets, preserve the target structure hash, chain and residue range, hotspot
list, binder-length range, checkpoint family, search algorithm, seed, and
sample count.

## References

- Upstream repository:
  https://github.com/NVIDIA-BioNeMo/Proteina-Complexa
- Common screen: [Cofold scoring stack](cofold-scoring-stack.md)
