# FreeBindCraft

## Purpose

Use FreeBindCraft for a BindCraft-family trajectory and ProteinMPNN funnel
without a required PyRosetta step.

## Public Status

The upstream repository uses MIT for its code and makes PyRosetta optional.
Its setup also downloads AlphaFold2 parameters, so record the parameter source
and terms for the selected runtime. `--no-pyrosetta` removes the PyRosetta gate;
it does not remove the separate AlphaFold2 parameter review.

## Run Shape

Supply a target settings file, filter profile, advanced profile, output path,
and `--no-pyrosetta`. A local container, GPU VM, pod, serverless job, or hosted
service can implement the same adapter contract.

Preserve poses, FASTA files, per-design statistics, the filter configuration,
seed, target and hotspot hashes, output counts, and artifact hashes. Treat a
negative design result as a completed tool run when the expected artifacts are
valid; biological quality and runtime readiness are separate fields.

## References

- Upstream repository: https://github.com/cytokineking/FreeBindCraft
- Standard BindCraft card: [BindCraft](bindcraft.md)
- Common screen: [Cofold scoring stack](cofold-scoring-stack.md)
