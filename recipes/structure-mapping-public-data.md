# PDB/EMDB Structure Mapping Public Data

Use this for a public PDB/EMDB structure-mapping plan.

## Prerequisites

- public accession only
- local scaffold path under `.runtime/`
- no raw movie, large map, or generated model committed to git

## Copyable Agent Prompt

```text
Use the BioSymphony Structure Factory skill. Create a public PDB/EMDB structure-mapping report plan from a deposited accession. Include provenance, expected artifacts, validation commands, figure/report outline, downgrade criteria, and result boundaries. If raw cryo-EM processing is requested, create a CryoCore handoff contract instead. Do not download raw data or launch remote compute.
```

## Commands

```bash
bsf scaffold-campaign .runtime/map-model-demo \
  --campaign-id map-model-demo \
  --target-label "Public PDB/EMDB structure target" \
  --public-accession "PDB:9ASJ / EMD-43816" \
  --window "public deposited structure validation scope" \
  --mode structure-mapping

bsf validate .runtime/map-model-demo
bsf audit .
```

Expected success:

- scaffold command writes a campaign manifest, target report, stage contract, validation notes, and README
- validation returns `"ok": true`
- audit reports zero findings

## Files To Inspect

- `.runtime/map-model-demo/campaign-manifest.json`
- `.runtime/map-model-demo/target-window.json`
- `.runtime/map-model-demo/stage-contract.json`
- `.runtime/map-model-demo/validation-notes.md`

The report should separate:

- public accession metadata
- downloaded public files and hashes
- derived summaries
- validation limitations
- optional renderer/tool gates
- validation notes

## Done Criteria

- result boundary is `public_demo` or lower until validation outputs exist
- expected artifacts distinguish metadata, public downloaded files, derived summaries, and validation notes
- optional renderer or model-building tools remain gated until runtime context is reviewed

## Blocked Or Degraded Criteria

Mark the run blocked or degraded if accessions are ambiguous, files are too large for git, validation artifacts are missing, or a user asks for unsupported density interpretation as a fact.

Do not store raw movies, large map files, private structures, or validation PDFs in git.
