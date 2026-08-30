# Dual Public Structure Comparison Demo

A small, real, no-license Structure Factory campaign that runs two public deposited-structure lanes and joins them into one comparison report.

- T2R14 receptor complex: PDB `9W0Q`, EMDB `EMD-65512`
- Pol theta helicase map/model: PDB `9ASJ`, EMDB `EMD-43816`

The campaign uses public deposited coordinates, public EMDB map, model, and validation files for the pol theta lane, and public RCSB metadata.

## Hand A Mission To An Agent

```text
Use the BioSymphony Structure Factory skill. Walk through the dual public structure comparison demo. Explain how two independent deposited-structure lanes (T2R14 and pol theta) are joined into one reviewed report, what artifacts each lane produces, and what the RunPod bridge packet looks like before any operator-gated launch.
```

## Prep The RunPod Bridge Packet

```bash
make demo-structure-comparison-prep-check
```

A RunPod launch uses an ignored runtime packet. The packet records authorization, budget, cleanup policy, runtime-secret references, immutable source reference, expected artifacts, and closeout checks.

## Closeout

Closeout requires fetched and hashed artifacts plus verified pod cleanup. Pod creation, `RUNNING` state, or command exit alone do not close the work.

## Scope

This demo uses public deposited evidence. Raw movies, particle stacks, license-gated tools, and private data are outside the scope of this demo.
