# EMPIAR-10204 Smoke Campaign

A metadata-only public handoff example. It shows how Structure Factory records a raw-data request, the operator gates around it, and the downstream structure-mapping expectations that will be picked up by BioSymphony CryoCore.

Raw cryo-EM intake, EMPIAR processing, RELION or CryoSPARC reconstruction, and map-to-model build are owned by CryoCore. Structure Factory keeps the public metadata, handoff contract, and downstream review.

## Use It For

- metadata-only CryoCore handoff planning
- public accession and expected-artifact contracts
- agent task planning without raw-data download
- result-boundary practice for `public_demo`

## Hand A Mission To An Agent

```text
Use the BioSymphony Structure Factory skill. Review examples/empiar-10204-v0 as a metadata-only CryoCore handoff example. Keep it public, do not download raw movies or maps, and identify the downstream structure-mapping artifacts and operator gates that would be needed before any CryoCore-owned execution.
```

## Run It Yourself

```bash
bsf validate examples/empiar-10204-v0
bsf audit .
```

## What This Folder Contains

- `campaign-manifest.json`. Accession IDs, data ledger, expected artifact list.
- `stage-contract.json`. The fail-closed handoff stages.

Raw movies, extracted particles, maps, and built models live in CryoCore's infrastructure outside the public repo.
