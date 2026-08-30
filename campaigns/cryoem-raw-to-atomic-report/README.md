# Cryo-EM Raw To Atomic Report

## Objective

Turn public raw cryo-EM data into a reproducible atomic-structure report package with maps, model, validation, publication-grade figures, methods notes, provenance, caveats, and next-experiment recommendations.

## Intended First Dataset

Use no-download metadata for the first smoke campaign, then use a deterministic `EMPIAR-13124` 50/100 raw-movie subset for the first honest raw-data demo. Store raw downloads only on RunPod scratch and record only accession IDs, ledgers, paths, hashes, and processing manifests.

## Wave Plan

1. Contract and dataset intake.
2. RunPod environment build and smoke test.
3. Raw movie download ledger and storage verification.
4. Motion correction and CTF QC.
5. Particle-picking comparison lane.
6. 2D classification and particle curation.
7. 3D reconstruction and refinement.
8. Heterogeneity and multimer/state analysis where applicable.
9. Atomic model building and chain assignment.
10. Real-space refinement and validation.
11. Figure report generation.
12. Result review, methods draft, and next-experiment plan.

## Linear Drafts

Issue drafts live in `linear-issues/`. The public export carries representative examples:

- `BSF-DEMO-01-T2R14-STRUCTURE-REPORT.md`. T2R14 coordinate-report demo.
- `BSF-DEMO-02-POLTHETA-MAP-MODEL-REPORT.md`. Pol theta map-model report demo.
- `BSF-DEMO-04-DUAL-STRUCTURE-COMPARISON.md`. Two-lane structure-comparison demo.
- `BSF-W13-PROVIDER-ADAPTER-CONTRACTS.md`. Provider-adapter contract example.

Use `bsf issue-dry-run` or the tracker templates to turn the wave plan into one tracker-neutral issue per wave. Store live tracker URLs and runtime records outside tracked files.

## Tool-Ranking Principle

Where practical, run competing lanes and compare outcomes rather than trusting one tool:

- RELION vs CryoSPARC vs Warp/M-supported processing
- Topaz vs crYOLO vs native pickers
- ModelAngelo vs Phenix-assisted model building
- CryoSPARC 3DVA vs cryoDRGN vs RELION classification
- ChimeraX vs PyMOL/Blender figure exports

Disagreement is a first-class artifact and should spawn review issues.

## No-False-Success Principle

Every run must pass an input audit before execution and a contract self-check before success is claimed. Flags such as `--analyze`, `--refine`, `--search`, or `--full-run` are intent only; artifact joins are the evidence.

## Provider Principle

RunPod is the default reviewed remote path for the first demos. Local, SSH/HPC, generic cloud, and neocloud profiles are supported as adapter contracts only when they preserve the same manifests, artifact roots, input audits, license gates, and final self-checks.
