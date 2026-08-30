# Structure Factory Sidecar Architecture

Structure Factory should be reusable outside this repo as a BioSymphony sidecar: a modular scientific workflow kit that another Symphony installation can copy, mount, or vendor.

## Layers

1. **Provider-neutral campaign**
   - scientific objective
   - data modules
   - image modules
   - lane modules
   - smoke suites
   - artifact contract
   - no-download/private-data policies

2. **Reusable modules**
   - `modules/data-modules/`: EMPIAR, EMDB, PDB, secure local stores
   - `modules/image-modules/`: logical tool images such as `cryo-core`
   - `modules/lane-modules/`: RELION, CryoSPARC, Phenix, AlphaFold, etc. Raw reconstruction lanes are CryoCore handoff definitions here, not Structure Factory ownership.
   - `modules/smoke-checks/`: GPU, storage, artifact, license-gate probes
   - `modules/artifact-contracts/`: report and result shapes

3. **Provider overlays**
   - RunPod Pods
   - AWS Batch
   - local lite
   - SSH/HPC
   - generic cloud VM
   - neocloud GPU pod

RunPod is the default reviewed remote adapter, and AWS Batch is the reviewed cloud-scale adapter. Neither should own scientific intent.

## Swappability Rules

- Data modules are swappable without editing tool lanes.
- Image modules are swappable without editing campaign science.
- License-gated lanes are explicit optional modules with skip/fail policy.
- Smoke checks are reusable contracts with severity and expected artifacts.
- Provider profiles map logical requirements to concrete GPU, image, volume, and port settings.
- Provider profiles must preserve `input_audit` and `contract_self_check` requirements so local, RunPod, SSH/HPC, cloud VM, and neocloud adapters share the same evidence contract.
