# SimpleFold

## Purpose

Use Apple SimpleFold to predict one protein's structure or sample alternate
conformations from its amino-acid sequence. In a binder campaign, SimpleFold
can review an isolated candidate's fold or conformational spread. Use a cofold
predictor and interface scorer for target-binder evaluation.

## Public-Safe Status

Public documentation and campaign scaffolding are available. The binder
capability ledger lists SimpleFold as a predictor, and the execution registry
defines its input and output boundary. The repository does not bundle an
installed SimpleFold command.

Apple publishes the source code under MIT terms. The released models use the
separate Apple Machine Learning Research Model License, which limits them and
their derivatives to the research purposes defined in that license. Record the
use context before a runtime downloads or uses model assets. Keep checkpoints,
caches, inputs, and generated structures outside public git.

## When To Use

- Predict the monomer fold of a generated candidate.
- Sample several conformers for a public or operator-approved sequence.
- Compare monomer structure or ensemble spread across model sizes, seeds,
  sampling steps, or `tau` values.
- Add an independent monomer check beside an interface-focused cofold stack.

## Model And Runtime Choices

The upstream CLI exposes these model names:

- `simplefold_100M`
- `simplefold_360M`
- `simplefold_700M`
- `simplefold_1.1B`
- `simplefold_1.6B`
- `simplefold_3B`

The public binder registry maps them to the lowercase variant IDs
`simplefold-100m` through `simplefold-3b`. The CLI supports PyTorch and MLX;
Apple recommends MLX for Apple hardware. Select the backend and model size from
the available memory, runtime, and budget. Verify that choice with one public
canary before a batch.

## Hand A Mission To An Agent

```text
Use the BioSymphony Structure Factory binder lane with SimpleFold as a monomer
predictor. Select the model size, PyTorch or MLX backend, sample count, steps,
tau, pLDDT setting, output format, seed, execution route, budget, and stop rule.
Record the Apple model-license use context before model acquisition. Dry-run a
validated adapter, run one public canary, then preserve output counts, model and
asset identities, hashes, validation notes, and cleanup evidence.
```

## Typical Inputs

- FASTA file or directory containing public, synthetic, or operator-approved
  protein sequences.
- Model size and PyTorch or MLX backend.
- Sampling steps, `tau`, samples per protein, seed, and PDB or mmCIF output.
- Optional pLDDT calculation.
- Runtime model and dependency cache outside the repository.

## Typical Outputs

- One or more PDB or mmCIF structures per input sequence.
- `sample_manifest.json` with input hashes, output counts, model size, backend,
  steps, `tau`, sample count, seed, output format, and pLDDT setting.
- `versions.json` and `asset_manifest.json` with the source revision and model,
  ESM2, CCD, and optional pLDDT-asset identities and hashes.
- `validation_notes.md` with parse checks and failed-input rows.

## Execution Routes

The shipped record is `adapter_required`: it describes the selections,
bindings, and expected output directory but contains no executable command.
Supply a validated runtime adapter for an installed local command, a container,
a scheduler, a cloud client, or a hosted wrapper. A platform skill can execute
the same stage contract and close it with `bsf binder-lane closeout` without an
adapter record.

This status records the repository's command inventory. It does not prohibit a
local, FAL, Modal, RunPod, Lambda Cloud, AWS, neocloud, cloud-VM, or SSH/HPC
route. The selected route still records its own compute, network, storage,
budget, artifact, and cleanup contract.

## Upstream Sources

- Repository and inference instructions: https://github.com/apple/ml-simplefold
- Source-code license: https://github.com/apple/ml-simplefold/blob/main/LICENSE
- Released-model license:
  https://github.com/apple/ml-simplefold/blob/main/LICENSE_MODEL
- Paper: https://arxiv.org/abs/2509.18480

## Limits And Gates

- The upstream FASTA parser models protein chain `A`; treat the released CLI as
  a single-protein lane.
- SimpleFold output does not measure a target-binder interface. Join it with a
  cofold predictor and interface scorer before ranking binder interactions.
- Enable pLDDT explicitly when the campaign needs it. Do not interpret an
  unlabeled structure field as confidence.
- Record checkpoint and dependency-asset hashes. The upstream source revision
  alone does not identify downloaded assets.
- Use public accessions, synthetic fixtures, or operator-approved runtime
  inputs. Keep private sequences and generated structures in the selected
  private artifact store.
- Treat every structure as `computational_candidate` evidence. Experimental
  binding, function, safety, and therapeutic claims require separate evidence.
