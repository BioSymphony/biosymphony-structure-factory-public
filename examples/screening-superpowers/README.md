# Screening Superpowers Fixture

The screening-first control plane in a public, local-only fixture. It produces the same artifact shapes a real provider-backed screening campaign would, with deterministic fixture scores so an agent can verify the schema, ranking, failure handling, and candidate-promotion logic.

## Hand A Mission To An Agent

```text
Use the BioSymphony Structure Factory skill. Run the screening-superpowers fixture locally. Explain the consensus ranking, the failure report, the method summary, the candidate reports, and how this same shape would scale to a real provider-backed campaign across RunPod, AWS Batch, or neocloud GPU pods.
```

## Run It Yourself

```bash
make screening-check
```

Outputs are written under `.runtime/screening-superpowers-fixture/`:

- `consensus_ranking.csv`. Ranked candidate list.
- `failure_report.json`. Negative rows and reasons.
- `method_summary.json`. What each method contributed.
- `candidate_reports/`. One report per promoted candidate.

Fixture scores are deterministic and intended for schema, ranking, and candidate-promotion checks. Real screening hits are produced by provider-backed runs and capped at `computational_candidate` until independent validation arrives.

## Provider Adapter Dry-Run

The fixture also demonstrates how local, RunPod, AWS Batch, and neocloud-style providers map to the same screening contract:

```bash
make provider-adapter-dry-run-check
```

Output under `.runtime/provider-adapter-dry-run/` includes the inert launch packet, required artifact list, closeout requirements, and lifecycle states for each provider. These packets are review artifacts. Real provider execution adds an operator-gated launcher, budget cap, artifact export, cost report, cleanup proof, and validation review on top of the same contract.

## Result Vocabulary Note

Some screening schemas use legacy internal values such as `candidate` and `processed`. The public result states for this fixture are `public_synthetic_demo` for fixture output and `computational_candidate` for any real provider-backed hit summary.
