# Cryo-EM Raw To Atomic Report Issue DAG

## First Active Wave

```mermaid
flowchart LR
  W00["W00 repo/GitHub readiness"] --> W03["W03 launch manifest generator"]
  W01["W01 RunPod template readiness"] --> W03
  W02["W02 software registry audit"] --> W03
  W03 --> W04["W04 no-download smoke contract"]
  W04 --> GATE["W04A human/operator authorization gate"]
```

## Backlog Waves

```mermaid
flowchart LR
  GATE["W04A authorization gate"] --> W05["W05 cryo-EM tool ranking"]
  GATE --> W08["W08 license-gated scaffolding"]
  W08 --> W09["W09 raw subset open demo"]
  W09 --> W10["W10 gated CryoSPARC activation"]
  W08 --> W11["W11 map/model report demo"]
  W09 --> W12["W12 contract self-check hardening"]
  W11 --> W12
  W12 --> W13["W13 provider adapter contracts"]
  W05 --> W06["W06 model build and validation"]
  W06 --> W07["W07 publishable figure report and result review"]
```

Only W00-W04 should start in `Todo` for the first Symphony test. W04A is a non-terminal human/operator gate and must stay out of Symphony active states. W05-W07 stay blocked until W04A is manually approved.

W08-W13 are the RunPod demo and provider-contract hardening wave. W08 is prep-only and can run without licenses. W09 is cost-bearing and raw-download-bearing. W10 requires runtime CryoSPARC/MotionCor3 access. W11 is map/model-only and should not download raw movies. W12 prevents false success by joining inputs, materialized files, executed commands, artifacts, and result boundaries before any run closes as successful. W13 keeps RunPod as the default reviewed path while making local, SSH/HPC, cloud VM, and neocloud adapters explicit.
