# Published Binder Cohort

## Purpose

Use the tool identities reported by the Anthropic autonomous binder-design
study, or replace named stages while preserving the same comparison contract.
The machine-readable source of truth is
[`published-binder-comparison-workflow.json`](../references/published-binder-comparison-workflow.json).

## Published Identities

The public study records ten generators: BoltzDesign1, BoltzGen, FoldCraft,
FreeBindCraft, Genie3, PXDesign, Protein Hunter, Proteina-Complexa,
RFdiffusion, and RFdiffusion3. Its sequence-design identities are ProteinMPNN,
SolubleMPNN, Caliby, SolubleCaliby, and generator-native co-design.

The score stack uses ESMFold2-Fast, ESMFold2-full, and Protenix-v2. ipSAE and
scDockQ derive interface measurements from those predictions. Keep the family
and variant fields in every comparison record; `esmfold2-fast` and
`esmfold2-full` are variants of one predictor family.

Mosaic and HalluDesign appear in the public source but contributed no ordered
designs. Do not count either name as a generator arm in an exact cohort replay.

## Replay Or Swap

For an exact-stack arm, select the recorded tool and variant identities. For a
swap arm, replace one or more stage identities with tools that serve the same
roles. Record the source identity, replacement identity, reason, route, and
version in the round request.

An exact identity does not require the original provider. You can bind the same
tool to a platform skill, hosted API, local installation, container, or GPU
provider. The execution route belongs in the adapter and provider records, not
in the tool identity.

## Runtime Binding

The public execution-adapter registry supplies typed placeholders and expected
outputs for every cohort identity. Most records require a runtime adapter
because upstream installation layouts differ. `adapter_required` means that
the user or their agent must bind an installed program or service to the public
contract; it is not a policy prohibition.

Before a paid or networked run, the user and agent select:

1. Target structure, chain range, and site residues.
2. Exact replay, deliberate swap, or both as separate arms.
3. Tool route for each arm: platform skill, hosted API, or self-hosted runtime.
4. Provider, budget ceiling, candidate count, round limit, optimization metric,
   and stopping rule.
5. Output contract, artifact store, cleanup rule, and result boundary.

Run a one-candidate technical canary before a cohort. Count and parse the
declared outputs before scaling.

## References

- Anthropic public report:
  https://www-cdn.anthropic.com/30bf50e22a01388bb29bf077ee3f244531594b7a.pdf
- Anthropic public dataset:
  https://huggingface.co/datasets/Anthropic/claude-protein-binder-design
- Public capability ledger:
  [`binder-lane-capability-ledger.json`](../references/binder-lane-capability-ledger.json)
- Public adapter registry:
  [`binder-execution-adapters.json`](../references/binder-execution-adapters.json)
