# Screening Superpowers Local Fixture

Use this when you want to exercise the screening contracts without cloud execution or private data.

## Prerequisites

- local Python runtime
- no provider account or GPU required
- fixture inputs only from `examples/screening-superpowers`

## Copyable Agent Prompt

```text
Use the BioSymphony Structure Factory skill. Run the public screening-superpowers local fixture checks, summarize the fanout estimate and result schema, and explain which steps would require an operator gate before any real screening run.
```

## Commands

```bash
make screening-manifest-check
make screening-fanout-estimate
make screening-fixture-run
make screening-active-learning
make screening-results-check
```

Expected success:

- each command exits successfully
- fixture outputs are written under `.runtime/screening-superpowers-fixture`
- result and active-learning checks report valid synthetic fixture outputs

## Files To Inspect

- `examples/screening-superpowers/screening-manifest.json`
- `examples/screening-superpowers/receptor-ensemble.json`
- `examples/screening-superpowers/ligand-library.json`
- `examples/screening-superpowers/provider-run-spec.json`

## Done Criteria

- fanout estimate is clear before any provider discussion
- output summaries state `public_synthetic_demo`
- real-data adaptation lists receptor source, ligand source, budget, cleanup, and operator authorization gates

## Blocked Or Degraded Criteria

Mark the run blocked or degraded if fixture checks fail, schema output is missing, a real provider launch is requested without authorization, or any private data would enter git.

Outputs are written under `.runtime/` and ignored by git. Treat them as `public_synthetic_demo` outputs, not biological proof.

Before adapting the recipe to real data, declare:

- receptor ensemble source and privacy posture
- ligand library source and allowed use
- shard fanout estimate
- expected result schema
- budget and cleanup policy for any remote execution
