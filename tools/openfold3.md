# OpenFold3 And OpenBind v0

## Purpose

Use OpenFold3 for all-atom structure prediction across proteins, RNA, DNA,
and non-covalent ligands. OpenFold3 v0.5.0 introduced OpenBind v0, whose
`openbind-2025-06-30-174k` parameters are the default for OpenFold3 releases
from v0.5.0 onward.

OpenBind v0 predicts plausible three-dimensional complexes and associated
confidence outputs. It does not predict binding affinity, potency, or
experimental binding.

## Public-Safe Status

Public documentation and campaign scaffolding are available. The binder
capability ledger lists OpenFold3 as a documented predictor, but the public
execution registry does not ship an executable adapter for it.

The upstream OpenFold3 repository and the released OpenBind v0 parameters are
recorded as Apache-2.0 with no repository license gate. Runtime readiness still
requires a pinned source revision, the exact parameter file, compatible
dependencies, sufficient accelerator memory, a cache outside the repository,
and a validated adapter.

## When To Use

- Generate a protein-ligand complex structure hypothesis.
- Compare protein, RNA, DNA, or ligand-containing predictions with another
  cofold method.
- Add an independent structural vote to a multi-predictor review.
- Test a supported pocket constraint after pinning the exact released input
  schema and inference configuration.

## Hand A Mission To An Agent

```text
Use the BioSymphony Structure Factory binder lane with OpenFold3 v0.5.0 and
the OpenBind v0 checkpoint openbind-2025-06-30-174k as a structure predictor.
Record the exact source commit, checkpoint filename and hash, query JSON,
MSA and template policy, seeds, samples, runtime route, budget, and stop rule.
Dry-run a validated adapter, run one public canary, and preserve the mmCIF,
confidence JSON, timing, manifest, validation, and cleanup evidence.
Do not interpret the result as a binding-affinity prediction.
```

## Typical Inputs

- OpenFold3 query JSON describing protein, RNA, DNA, and supported ligand
  entities.
- An explicit MSA and template policy.
- Seeds, diffusion samples, and any supported pocket constraints.
- The `of3-ob-2025-06-30-174k.pt` parameter file in a runtime cache outside
  the repository.

## Typical Outputs

- Predicted mmCIF structures.
- Detailed and aggregated confidence JSON, including the metrics emitted by
  the selected OpenFold3 release.
- Timing information and a manifest that joins inputs, configuration, source
  revision, parameter identity, and output hashes.
- Validation notes for parsing, completeness, and failed inputs.

## Execution Routes

The shipped record is `adapter_required`: it documents the expected boundary
but contains no executable command. Supply a validated runtime adapter for the
official `run_openfold predict` command or an equivalent service wrapper.
Keep parameter files, caches, query data, and generated structures outside
public git.

## Upstream Sources

- v0.5.0 OpenBind model release:
  https://github.com/aqlaboratory/openfold-3/releases/tag/v0.5.0
- Repository and Apache-2.0 license:
  https://github.com/aqlaboratory/openfold-3
- Parameter reference:
  https://openfold-3.readthedocs.io/en/latest/parameters_reference.html
- Inference and output reference:
  https://openfold-3.readthedocs.io/en/stable/inference.html

## Limits And Gates

- OpenBind v0 is a parameter set for OpenFold3. It is distinct from the
  OpenBind Consortium structure-affinity benchmark dataset listed separately
  in the software registry.
- A predicted pose and model confidence do not establish binding affinity,
  potency, selectivity, function, safety, or therapeutic value.
- Record the exact checkpoint name, filename, and hash; `OpenBind v0` alone is
  not enough to reproduce a run.
- Record whether MSAs, templates, and pocket constraints were used, together
  with every seed and sample count.
- Use public accessions, synthetic fixtures, or operator-approved runtime
  inputs. Treat every output as `computational_candidate` evidence.
