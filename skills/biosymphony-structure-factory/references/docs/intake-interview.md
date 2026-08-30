# Intake Interview

Structure Factory should ask enough to understand the scientific job without turning every request into a meeting.

The default is a short, opt-out intake. Users can always say `skip intake`, `use defaults`, or `just go`, and the agent should proceed with stated assumptions unless the request would trigger a hard gate.

## When To Interview

Use intake when the request involves:

- a new campaign or workflow
- paid or remote compute
- raw data downloads
- private data, licenses, credentials, or unpublished biology
- ambiguous scientific success criteria
- multiple possible providers or execution profiles

Skip intake for:

- simple repo edits
- direct validation commands
- narrow bug fixes
- answering a conceptual question
- prep-only no-download checks with clear defaults

## First, Inspect Known Inputs

Before asking questions, read the relevant manifests, ledgers, issue body, and provider profile. If available, run:

```bash
python3 scripts/structure_factory/input_audit.py \
  --manifest runpod/launch-manifests/no-download-smoke.json \
  --json
```

Then ask only about explicit `missing_operator_items` or high-impact choices that cannot be inferred safely.

## Question Budget

Ask at most three questions in the first round.

Prefer these slots:

1. **Outcome** - What should the final artifact prove or show?
2. **Inputs** - Which accession, dataset, map/model, sequence, or secure reference should be used?
3. **Execution** - Which provider, budget/time cap, and license/data gates are authorized?

If more information is needed, proceed with defaults for non-destructive prep and leave unresolved items as blockers in the issue or audit report.

## Default Choices

When the user does not specify:

- provider: `runpod` for remote demos, `local` for prep/validation
- execution profile: `no-download-smoke` for readiness, `map-model-report` for a 4-hour public map/model demo, and CryoCore handoff for raw-subset work only after explicit authorization
- operator gate: `yes` for paid compute, raw downloads, cloud/neocloud launch, SSH/HPC submission, or license-gated tools
- artifact style: small report with figures, methods, provenance, validation notes, input audit, and contract self-check

## Hard Gates

Do not proceed without explicit authorization for:

- launching RunPod, cloud, neocloud, SSH/HPC, or local heavy jobs
- downloading raw EMPIAR movies or other large datasets
- using private biological data
- installing or activating license-gated tools
- storing secrets, license IDs, private installer URLs, or tokens

Never ask the user to paste secrets into chat or Linear. Ask for a secure runtime secret reference instead.

## Smart Phrasing

Good intake is concise and option-oriented:

```text
I can proceed with defaults: RunPod, 4-hour cap, PDB/EMDB structure-mapping report, no raw movies.
Before I set that up, confirm only these blockers:
1. Is RunPod launch authorized up to 4 hours?
2. Should the output prioritize visual story figures or validation tables?
3. Any license-gated tools allowed, or open tools only?
```

If the user says `skip and go`, record assumptions in the issue or run manifest and continue with non-destructive prep. Hard gates still require authorization.

## Demo Bias

For demos, optimize for a memorable scientific artifact, not just double-checking:

- structural story figures
- annotated density/model panels
- concise methods and provenance
- validation notes with conservative caveats
- clear next-experiment suggestions

Validation stays present, but it supports the story rather than becoming the story.
