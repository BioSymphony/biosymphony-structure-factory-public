# Structure Factory Modules

This directory is the sidecar contract surface. A campaign should be built from reusable modules instead of hard-coding one provider, dataset, or tool stack.

```text
campaigns/          provider-neutral campaign manifests
data-modules/       EMPIAR/EMDB/PDB/local-secure-store inputs
image-modules/      logical image families
lane-modules/       tool lanes and license gates
smoke-checks/       reusable readiness checks
artifact-contracts/ report and result contracts
provider-profiles/  RunPod/local/HPC provider overlays
```

The first RunPod smoke bundle resolves these modules into a concrete provider launch manifest under ignored `.runtime/`.
