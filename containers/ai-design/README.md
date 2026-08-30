# ai-design Image Plan

## Purpose

Prediction, design, and model-comparison lanes that compare generated structures against experimental evidence.

## Candidate Contents

- Boltz/Boltz-2 pinned through `references/software-registry.yaml`
- Chai
- ProteinMPNN
- LigandMPNN
- Genie 3 gated source/weights lane
- RFdiffusion gated lane
- AlphaFold 3 gated lane
- Open-source model utilities

## Smoke Command

Verify Python, CUDA visibility, repo clone, and package import surface only. Do not download model weights during prep.

Run the repository readiness gate before claiming this image is usable:

```bash
make harness-check
```

On the actual GPU image or Network Volume runtime, run the strict gate:

```bash
make harness-check
```

## License Policy

Keep gated weights and restricted code outside the image unless terms explicitly allow inclusion.

Genie 3 remains deferred by default because upstream setup includes ColabFold,
AlphaFold2 multimer parameters, OpenFold/ESM, ProteinMPNN, IPSAE, FoldSeek,
TMscore/TMalign, DSSP helper, and MSA-server/privacy decisions. Enable it only
with `GENIE3_INSTALL=1`, `GENIE3_OPERATOR_GATE_ACK=dependency_and_weight_terms_reviewed`,
`GENIE3_ALLOW_COLABFOLD_PARAMS=1`, and a recorded dependency/weight review.
