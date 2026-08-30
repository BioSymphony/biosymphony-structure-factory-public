# Contributing

Thanks for helping improve `biosymphony-structure-factory`.

## Ground Rules

- Use only synthetic examples or examples based on public accessions.
- Do not add private biological data, unpublished sequences, generated candidate sequences or structures, provider logs, credentials, or operator notes.
- Record the result boundary and source posture for each example or result record.
- Keep validators dependency-free at runtime unless an optional adapter is clearly separated.
- Prefer compact ledgers and manifests over large generated artifacts.
- Run `make release-check` before opening a pull request.

## Adding A Campaign Example

1. Create `examples/<campaign-id>/`.
2. Add `campaign-manifest.json`.
3. Add a compact target-window or input file.
4. Add `stage-contract.json` if the example has long-running or GPU stages.
5. Add `candidate-ranking.example.json` only for constructed data with explicit result boundaries and source posture.
6. Add `README.md` describing scope, public data sources, and run boundaries.
7. Run `make release-check`.

## Adding A Task Pack

Task packs should stay tracker-neutral. Use IDs like `BSF-BINDER-W00` rather than private tracker IDs. A private workflow can map those IDs to Linear, GitHub Issues, or another system after public validation.

## Adding A Tool Card

1. Add `tools/<tool-or-lane>.md`.
2. Record public documentation sources, expected runtime requirements, and review caveats.
3. Date license claims and link their current primary sources.
4. Do not include accepted-license records, private installer URLs, credentials, binaries, or weights.
5. Run `make registry-check` and `make release-check`.

## Changing A Binder Lane Contract

- Update the applicable capability ledger, execution registry, schema, public fixture, and documentation together.
- Keep bundled execution records fixed-argument and typed. Keep credentials, service addresses, concrete provider resources, license-acceptance records, logs, receipts, and generated biology outside public Git.
- Put installation-specific adapter registries and runtime bindings under ignored `.runtime/` paths.
- Add focused tests, then run `make binder-lane-check` and `make release-check`.

## Changing Schemas Or Validators

- Keep `src/biosymphony_structure_factory` dependency-free.
- Add focused tests under `tests/`.
- Keep errors strict for release blockers and warnings for optional capability gaps.
- Update `docs/cli-reference.md` when CLI behavior changes.

## Pull Request Checks

Before opening a pull request, run:

```bash
make clean
make release-check
```

`make release-check` fails when `gitleaks` is unavailable or reports a leak. A successful local or CI scan is required before release.

## Style

- ASCII text by default.
- Stdlib-only runtime code.
- Small, deterministic tests.
- Warnings for guidance gaps, errors for release or structural blockers.
