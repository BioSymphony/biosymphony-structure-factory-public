# PD-L1 Structure Inputs

This directory intentionally does not track coordinate files. The PD-L1 lanes
materialize the public 4ZQK chain A 19-127 slice at runtime from RCSB and record
the resulting SHA256 in each run's input-audit artifact.

Coordinate files such as `*.pdb`, `*.cif`, and `*.mmcif` are ignored by repo
policy so local or RunPod-derived structures do not become durable git state.
