# Structure Factory Public Issue

This template is a public campaign request, not a full Linear/Symphony worker contract. Use [`templates/linear-issue.md`](linear-issue.md) when an agent worker needs provider fields, stage/progress contracts, dependencies, and closeout validation.

## Summary

Describe the structural biology task using public or synthetic inputs.

## Campaign

- campaign ID:
- mode: `binder-design | model-comparison | structure-mapping | screening | provider-prep`
- routing label: `sym:structure-factory`
- result boundary: `planning | public_demo | computational_candidate`
- operator gate required before execution: `yes | no`

## Public Inputs

- target:
- public accession:
- target window or scope:
- privacy posture: `public_or_synthetic_only`

Do not include private sequences, unpublished structures, raw data, provider IDs, credentials, private paths, or private tracker URLs.

## Expected Artifacts

- `campaign-manifest.json`
- `target-window.json`
- `stage-contract.json`
- `validation-notes.md`

## Acceptance Criteria

- [ ] Inputs are public accessions or synthetic fixtures.
- [ ] Stage contract fails closed on missing or unverifiable artifacts.
- [ ] Output statements stay within the validation present.
- [ ] No wet-lab, clinical, therapeutic, safety, efficacy, or binding proof is presented as established.

## Validation Commands

```bash
bsf validate examples/<campaign-id>
bsf audit .
make release-check
```

## Risk Notes

- GPU, provider, license-gated, or cost-bearing work requires a separate operator gate.
- Tracked launch templates omit live execution state. Prepare an ignored runtime packet, pass readiness checks, and record bounded human authorization before a paid provider start or non-public upload.

<!-- symphony:schema
schema_version: 1
subgroup: structure-factory
routing_label: sym:structure-factory
-->
