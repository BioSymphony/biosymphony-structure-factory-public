# Schemas

Canonical JSON schemas live under `modules/schemas/`.

Use them to validate public campaign and artifact surfaces such as:

- active-learning tranches
- artifact indexes
- candidate reports
- validation ledgers
- cloud shard ledgers
- provider runs
- receptor ensembles
- screening manifests and results
- stage progress

The root `schemas/` directory holds CLI-facing request, plan, report, discovery,
remote-tool, target-verification, metric-provenance, and failure-record schemas.
Canonical execution and artifact schemas live under `modules/schemas/`.

The remote request and receipt schemas describe provider-neutral envelopes. They
do not prove a provider account, tool installation, service route, or compute
readiness. Runtime validators enforce the additional safety and identity-join
checks before a stage can close.

Binder control records use:

- `binder-control-panel.schema.json` for declared predictors, seeds, metrics, and required or optional controls
- `binder-control-adoption.schema.json` for a reviewed external gate set
- `binder-control-calibration.schema.json` for derived or adopted readiness, diagnostics, and gates

Some compatibility schemas include older machine values such as `candidate`, `processed`, `fixture_or_demo`, `validated`, or `publishable`. Public docs and closeouts should translate those through [`../docs/result-boundaries.md`](../docs/result-boundaries.md).
