# PD-L1 Binder-Design Fast Path

Use this when you want a binder-design campaign scaffold from a deposited structure or public target window.

## Prerequisites

- local install completed with `python -m pip install -e .`
- public target metadata only
- no generated coordinates, sequences, provider logs, or credentials in git

## Copyable Agent Prompt

```text
Use the BioSymphony Structure Factory skill. Review examples/pd-l1-binder-design-public as a public PD-L1 binder-design fast path. Check the target-window file, stage contract, candidate ranking example, task plan, and validation notes. Keep the result boundary at computational_candidate and do not launch remote compute.
```

## Commands

```bash
bsf validate examples/pd-l1-binder-design-public
bsf issue-dry-run examples/pd-l1-binder-design-public --out .runtime/pd-l1-issues
bsf audit .
```

Expected success:

- validation returns `"ok": true`
- `.runtime/pd-l1-issues/` contains tracker-neutral task drafts
- `bsf audit .` reports zero findings

## Files To Inspect

- `examples/pd-l1-binder-design-public/campaign-manifest.json`
- `examples/pd-l1-binder-design-public/target-window.json`
- `examples/pd-l1-binder-design-public/stage-contract.json`
- `examples/pd-l1-binder-design-public/candidate-ranking.example.json`
- `examples/pd-l1-binder-design-public/validation-notes.md`

Review:

- target accession and residue window
- hotspot rationale and uncertainty
- generation lane runtime gates
- cofold/model-comparison expected artifacts
- candidate ranking result boundary
- result boundaries in `validation-notes.md`

## Done Criteria

- task drafts name owned paths, acceptance criteria, validation commands, and result boundaries
- every candidate remains `computational_candidate`
- any missing optional output is marked blocked or insufficiently supported

## Blocked Or Degraded Criteria

Mark the run blocked or degraded if inputs are not public, target-window support is unclear, a tool lane requires unapproved licensing/runtime access, or the audit reports any finding.

Do not commit generated coordinates, generated sequences, private notes, provider logs, or model weights. Keep every candidate at computational-candidate status until external validation exists.
