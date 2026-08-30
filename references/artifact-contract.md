# Structure Factory Artifact Contract

Serious Structure Factory campaigns must produce a report that can be reviewed without relying on chat history.

## Required Files

```text
structure-report/
  report_manifest.json
  run_manifest.json
  provenance.md
  validation_ledger.md
  methods.md
  validation/summary.md
  figures/README.md
```

## Manifest Requirements

The manifest should record:

- campaign ID
- source accessions or secure local references
- software versions
- execution backend
- GPU type and container image digest when remote
- input artifact references and hashes where practical
- output artifact paths and hashes
- validation commands and status
- license/citation notes

## Claim Ledger Requirements

Every biological or structural claim must include:

- claim text
- evidence artifact
- confidence level
- caveat
- reviewer/auditor status

Claims about density, ligands, affinity, conformational states, or mechanism require explicit validation evidence.

## No-Download Smoke Report

The first RunPod prep run emits a minimal report shape without biological data:

```text
structure-report/
  report_manifest.json
  run_manifest.json
  validation/toolcheck.json
  validation/gpu.json
  validation/storage.json
  provenance.md
```

This verifies orchestration, storage, and artifact contracts before spending GPU time on real cryo-EM processing.
