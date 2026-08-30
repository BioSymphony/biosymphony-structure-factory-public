# Screening Superpowers Fixture Summary

CLI-first review path for the Screening Superpowers fixture. It ships Markdown and command-line summary output only. After the fixture runs, use the summary helper to review consensus rankings, failure rows, method summaries, and candidate reports.

## Hand A Mission To An Agent

```text
Run the screening-superpowers fixture and summarize the consensus ranking, failure report, method summary, and candidate reports. Explain how the same artifact shape applies to a real provider-backed screening campaign.
```

## Run It Yourself

Generate fixture artifacts:

```bash
make screening-check
```

Print the parsed artifact summary:

```bash
python3 scripts/structure_factory/screening_summary.py \
  --artifact-root .runtime/screening-superpowers-fixture \
  --json
```

## Validation

The summary helper performs no provider calls, downloads, build step, browser launch, or external JavaScript work:

```bash
python3 scripts/structure_factory/screening_summary.py \
  --artifact-root .runtime/screening-superpowers-fixture \
  --json
```

Fixture scores are `fixture_or_demo` evidence intended for schema, ranking, and report-promotion review. Real screening hits come from provider-backed runs and stay at `computational_candidate` until independent validation arrives.
