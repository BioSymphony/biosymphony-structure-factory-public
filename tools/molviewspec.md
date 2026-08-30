# MolViewSpec

## Purpose

Plan declarative molecular visualization states for review packets, static
dossiers, and reproducible handoff scenes. MolViewSpec records what to load,
select, color, annotate, and view without committing heavyweight render outputs.

## Public-Safe Status

Public scaffold: yes. The upstream repo reports an MIT license. Runtime use
still needs current package/source review and a clear policy for the structures
referenced by each scene.

## When To Use

- Package a compact molecular-view state with a candidate report.
- Preserve camera, selection, coloring, and annotation decisions across agents.
- Hand a scene to a MolViewSpec-compatible Mol* viewer without storing a video or
  large rendered asset.

## Hand A Mission To An Agent

```text
Use the BioSymphony Structure Factory skill with the MolViewSpec tool card. For
candidate report <path>, create compact MolViewSpec scene states that reference
approved public or runtime-local structures, include camera and annotation
metadata, and avoid embedding heavy generated structure bundles in git.
```

## Typical Inputs

- Public structure accession, approved runtime-local structure pointer, or
  candidate-report structure pointer.
- Selections, colors, labels, camera state, and annotation rows.

## Typical Outputs

- `scene.mvsj` or `scene.mvsx`.
- `structure_view_manifest.json` with source structures, annotations, schema
  version, and renderer notes.

## Repo And References

- Repo: https://github.com/molstar/mol-view-spec

## Gotchas

- A scene state is not a renderer by itself. It is a portable description for a
  compatible viewer.
- Keep scene files compact. Do not embed large generated structures, maps,
  trajectories, videos, or private paths.

## Gates

- Referenced structures must be public, synthetic, or operator-approved runtime
  artifacts.
- Public reports should carry source accession, checksum, and result-boundary
  notes.
