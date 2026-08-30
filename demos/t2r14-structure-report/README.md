# T2R14 Open Structure Report Demo

A small, real, no-license Structure Factory demo using public RCSB and EMDB metadata.

- PDB: `9W0Q`
- EMDB: `EMD-65512`
- target: bitter taste receptor T2R14 ligand and G-protein cryo-EM complex
- runtime: CPU-only, intended under one hour on RunPod

The demo uses public mmCIF and RCSB metadata, computes chain and ligand-neighborhood summaries, emits SVG figures, and writes a compact report packet with provenance and explicit result limits.

## Hand A Mission To An Agent

```text
Use the BioSymphony Structure Factory skill. Run the T2R14 open structure report demo locally, then prepare the RunPod bridge packet. Explain the chain and ligand-neighborhood summaries, the SVG figure outputs, the provenance, and what would be needed for an operator-gated RunPod launch.
```

## Run Locally

```bash
python3 scripts/structure_factory/t2r14_structure_report.py \
  --out .runtime/t2r14-structure-report-local/runpod-execution \
  --json
```

## Prepare The RunPod Bridge Packet

```bash
make demo-t2r14-report-check
```

Or run the bridge steps directly:

```bash
python3 scripts/structure_factory/build_t2r14_report_bridge_manifest.py
PROVIDER_BRIDGE_CLI=${PROVIDER_BRIDGE_CLI:-symphony-neocloud-bridge}
$PROVIDER_BRIDGE_CLI validate-manifest \
  .runtime/bridge-manifests/t2r14-structure-report.json \
  --json
$PROVIDER_BRIDGE_CLI prepare \
  .runtime/bridge-manifests/t2r14-structure-report.json \
  --out-dir .runtime/t2r14-structure-report-packet \
  --json
# Paid pod creation runs from an operator-gated execution packet under .runtime/ after approval.
```

A RunPod launch uses an ignored runtime packet. The packet records authorization, budget, cleanup policy, immutable source reference, runtime-secret references, expected artifacts, and closeout checks.

## Scope

This demo uses public deposited evidence. CryoSPARC, Phenix, ChimeraX, MotionCor, Rosetta, AlphaFold 3, raw movies, private data, and persistent storage are outside the scope of this demo.
