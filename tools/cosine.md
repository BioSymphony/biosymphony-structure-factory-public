# CoSiNE

CoSiNE models antibody-sequence evolution with a neural continuous-time Markov
chain (CTMC). It generates substitution variants, ranks variants with a
sequence-based variant-effect prediction (VEP) score, and can guide evolution
with an external oracle. It does not predict structures.

## Public source and result boundary

- **Source posture:** The upstream implementation and paper are public. This
  card describes the public interface and does not certify a runtime,
  checkpoint, dataset, or external oracle.
- **License posture:** The upstream repository labels its code MIT. Confirm the
  license, model terms, and dataset terms at the version you use.
- **Result boundary:** Generated sequences and VEP scores are computational
  outputs. They do not establish binding, function, safety, or therapeutic
  value.
- **Public examples:** Use public accessions or synthetic sequences. Keep
  runtime sequences and generated artifacts outside the public repository.

## Capabilities

- Simulate antibody maturation trajectories from a starting sequence.
- Rank substitution variants with a selection-oriented VEP score.
- Guide sequence evolution with an oracle that estimates a target property.
- Limit mutations to an AHO-numbered CDR or framework region and set a mutation
  ceiling.

## Inputs

- An antibody sequence or a set of single-substitution variants.
- AHO alignment and region labels. The released model handles substitutions;
  it does not model insertions or deletions.
- An evolution configuration: branch length, sample count, mutation scope, and
  mutation ceiling.
- For VEP, a reference sequence and the variant table to score.
- For guided evolution, an oracle adapter that returns a per-sequence mean and
  uncertainty. Gradient-based guidance also requires a differentiable oracle.

## Outputs

- A variant table with sequence identifiers, substitutions, and sampling or
  scoring metadata.
- A VEP table with a score for each declared variant.
- For guided evolution, oracle values and guidance parameters for each declared
  output.
- A run record that declares output files, counts, relative artifact paths, and
  hashes. The record must not include sequence payloads.

## Adapter shape

Use a narrow adapter request that declares the operation, input class, limits,
and expected outputs. The adapter owns translation to the upstream interface.

```json
{
  "tool_id": "cosine",
  "operation": "evolve | guided_evolve | vep",
  "inputs": {
    "sequence_artifact": "runtime sequence artifact",
    "alignment": "AHO",
    "substitutions_only": true,
    "mutation_scope": "CDR3 | framework | full_sequence"
  },
  "parameters": {
    "branch_length": 2.0,
    "sample_count": 100,
    "max_mutations": 5
  },
  "guidance": {
    "oracle_adapter": "declared external oracle",
    "requires_gradient": true
  },
  "outputs": {
    "variants": "variants.csv",
    "scores": "scores.csv",
    "metadata": "metadata.json"
  }
}
```

For `evolve`, omit `guidance`. For `vep`, provide the declared variant table
instead of requesting sampled trajectories. The adapter must reject an output
that is missing, extra, outside the run root, or inconsistent with its hash
ledger.

## Technical constraints

- CoSiNE is sequence-only. A structural claim needs a separate structure
  prediction and scoring stage.
- The CTMC model expects aligned antibody sequences and substitution variants.
  It cannot represent indels in the released workflow.
- The upstream project uses a model checkpoint and accelerator-oriented
  dependencies. Treat runtime availability as a separate provider and
  dependency check.
- Guidance changes the sampling distribution toward the oracle signal. The
  oracle score is not an independent validation result.

## Independent structural validation

Route generated or guided variants through the
[cofold scoring stack](cofold-scoring-stack.md). Use a structural validator
that is independent of the guidance oracle, retain the required confidence
sidecars, and record the resulting artifact hashes. Keep the result boundary at
`computational_candidate` unless downstream work establishes a stronger result.

## Sources

- [CoSiNE upstream repository](https://github.com/songlab-cal/cosine)
- [CoSiNE paper on arXiv](https://arxiv.org/abs/2602.18982)
