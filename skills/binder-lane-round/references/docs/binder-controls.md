# Binder Control Calibration

The control layer builds a machine-readable readiness and calibration record from a declared panel and prediction observations. It calls no predictor, scorer, provider, or external service.

## Control Panel

[`binder-control-panel.schema.json`](../schemas/binder-control-panel.schema.json) records:

- one calibration scope and selected metric
- required predictors and seeds
- metric direction, unit, and metric-specific control requirements
- positive and negative controls with `required` or `optional` status
- a public-data or synthetic source ID for each control

Every control uses a distinct `source_id`. The panel sets `minimum_controls_per_class`; a value of three requires three complete positive controls and three complete negative controls for each predictor.

The selected metric can name an optional control in `required_control_ids`. The control then becomes required for that metric. A missing optional control otherwise produces `ready_with_optional_gaps` when the required panel still supports derivation.

## Prediction Index

Each observation contains exactly five fields:

```json
{
  "control_id": "positive-1",
  "predictor_id": "predictor-a",
  "seed": 0,
  "status": "scored",
  "metrics": {
    "interface_score": 0.8
  }
}
```

`index_predictions` calculates the expected matrix from controls, predictors, and seeds. It reports duplicate rows, missing rows, failed rows, and missing selected-metric values. The index separates required gaps from optional gaps.

For multiple seeds, the reducer selects the best selected-metric value in the declared direction. The lowest seed resolves a tie. All diagnostic metrics come from that selected row, so the record preserves the metric and seed pairing.

## Derivation

`derive_calibration` keeps predictors separate. For each predictor and metric, it records positive and negative ranges, the direction, boundary values, and the strict gap.

For a higher-is-better metric:

```text
gap = minimum positive - maximum negative
```

For a lower-is-better metric:

```text
gap = minimum negative - maximum positive
```

A positive gap produces a midpoint gate. The selected metric must separate for every required predictor, and both classes must meet `minimum_controls_per_class`. Predictor values are not averaged.

The record has one of three readiness states:

- `ready`: the selected metric has a gate for every required predictor.
- `ready_with_optional_gaps`: derivation is ready and the record names missing optional observations.
- `blocked`: required observations, class counts, or strict separation are missing.

## Adoption

`adopt_calibration` accepts the contract in [`binder-control-adoption.schema.json`](../schemas/binder-control-adoption.schema.json). The record names the source scope, source artifact SHA-256, metric, one gate per required predictor, and the adoption reason.

The function rejects a missing predictor, metric mismatch, operator mismatch, non-finite threshold, or invalid digest. An adopted record uses `calibration_state: borrowed`; a derived record uses `calibration_state: calibrated`.

## Round Decisions

`round-decision --calibration` joins a ready calibration to measured round-history rows. It checks that the plan primary metric matches the calibration, rejects synthetic metric rows, and records the calibration state, scope, and artifact SHA-256 in each metric-provenance record.

The CLI can derive the record and bind it to a round decision:

```bash
bsf binder-lane calibrate-controls examples/binder-controls-synthetic/control-panel.json \
  --workspace . \
  --observations examples/binder-controls-synthetic/control-observations.jsonl \
  --out .runtime/binder-controls/calibration.json
bsf binder-lane round-decision .runtime/my-round/plan.json \
  --workspace . \
  --history .runtime/my-round/round-history.json \
  --calibration .runtime/binder-controls/calibration.json \
  --out .runtime/my-round/round-decision.json
```

The second command assumes that `plan.json` uses `interface_score`, the fixture's selected metric. Use `--adopt` instead of `--observations` to apply a reviewed adoption record. The calibration command makes no provider calls. Use its `ok`, `status`, and `readiness` fields to determine whether the selected metric is ready; a diagnostic can finish with `readiness: blocked`.

The calibration record supports computational stopping decisions only. Control separation does not establish binding, function, selectivity, safety, or experimental transfer accuracy.

## Synthetic Fixture

[`binder-controls-synthetic`](../examples/binder-controls-synthetic/) contains a two-predictor 3-by-3 panel with constructed values. The fixture omits two optional controls to exercise `ready_with_optional_gaps` without weakening the selected-metric gate.
