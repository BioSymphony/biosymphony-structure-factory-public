# cryosparc Image Plan

## Purpose

Prepare a CryoSPARC lane for academic/personal use where licensing permits. This lane is not part of the first no-download smoke image.

## Runtime Requirements

- CryoSPARC license provided as a runtime secret or environment variable.
- Persistent database and project storage under `/workspace/structure-factory/cryosparc/`.
- Exposed web UI port only when the RunPod template explicitly enables it.

## Smoke Command

For prep, only verify the license gate and storage layout. Do not install or launch CryoSPARC unless the issue explicitly authorizes it.
