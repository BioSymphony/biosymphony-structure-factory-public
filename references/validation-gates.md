# Validation Gates

Structure Factory campaigns should move through explicit gates.

Raw cryo-EM movie intake, EMPIAR subset execution, reconstruction, and map-to-model build execution are CryoCore-owned. When this document mentions raw-subset gates, read them as handoff and closeout requirements that Structure Factory can validate around a CryoCore-owned execution path.

## No-False-Success Rule

Runner flags are intent, not proof. A Structure Factory run is successful only when the final contract self-check joins declared inputs, materialized data, executed commands/results, and final reported conclusions.

Live readiness is exact-route readiness. A package import, image tag, pod launch,
or broad runner flag does not prove the stage can execute. The readiness record
must name the exact executable, command, or Python entrypoint that the stage will
call, and live closeout must show that same route in the executed-command
ledger.

Every execution profile should emit:

- `validation/input-audit.json` before operator questions or remote execution.
- CryoCore raw-subset handoff profiles: `validation/fanout-estimate.json` before raw downloads or context lanes.
- `stage-progress.jsonl` while the provider job is actually doing work.
- `validation/stage-contract-check.json` before closeout for long or provider-backed runs.
- `validation/contract-self-check.json` before a Symphony issue can close as successful.

Mock and dry-run artifacts must be labeled with `mock_tools`, `mock_gpu`, or `dry_run` markers. Real execution profiles fail if those markers are present in required evidence.

Placeholder, fixture, provider-search, reference-only, and generic target
outputs are mock-class evidence. They may support planning, but they cannot
satisfy a real Structure Factory closeout unless the final status is explicitly
downgraded.

Provider state is not evidence by itself. RunPod `desiredStatus`, pod creation, image tags, worker launch, or command-line flags only prove intent. Real progress requires workload-written progress events, terminal stage status, and output artifacts that join back to declared inputs.

Silent fallback is forbidden. If the run falls back to a different provider, worker route, mock data, reference-only evidence, rescue route, or install-at-boot image, the final closeout must be downgraded to `partial`, `degraded`, `blocked`, or `failed`.

Primary evidence and context evidence are separate success levels. A CryoCore raw-subset
run can produce real intake, motion, and CTF evidence while later picking,
classification, model-building, or figure context lanes time out. That is a
partial closeout with a resume path, not a full failure and not a full success.

## Maturity Ladder

- L0 `plan_exists` - issue, manifest, and artifact contract exist.
- L1 `tools_ready` - environment/tool/license checks pass.
- L2 `inputs_materialized` - data ledgers join declared inputs to concrete files or accessions.
- L3 `execution_performed` - commands ran and emitted expected result artifacts.
- L4 `evidence_joined` - results join back to inputs, tool versions, and processing ledgers.
- L5 `validation_reviewed_report` - outputs are assigned evidence, confidence, caveats, and reviewer status.

## Gate 0: Contract

- Issue body conforms to template.
- Inputs are public accessions or secure path references.
- Raw/private data is not copied into git or Linear.
- Expected artifacts and validation commands are exact.

## Gate 1: Environment

- Tool versions recorded.
- GPU and driver compatibility recorded.
- License constraints recorded.
- Smoke commands pass.
- Exact executable route recorded for every stage command, such as
  `relion_refine`, `phenix.real_space_refine`, `ChimeraX`, or the repo-local
  Python entrypoint. Warning-only package checks are not live readiness.
- Repository clone URL and pinned commit recorded.
- Registry auth reference recorded when the image requires one.
- Digest-pinned image required before real remote launch.
- Stage contract and progress ledger paths recorded.
- Network volume read/write check passes under `/workspace`.

## Gate 2: Data Intake

- Dataset accession, source, expected size, and download method recorded.
- Checksums or file counts recorded where practical.
- Storage path is outside git.
- `input_audit.py` output records known inputs and explicit `missing_operator_items`.
- CryoCore raw-subset handoff plans run `fanout_estimator.py` to bound movie count, expected bytes, frame count, and context-lane work before transfer.

## Gate 3: Processing

- For CryoCore-owned execution closeouts, motion correction, CTF, picking, classification, refinement, or equivalent outputs recorded.
- QC plots or numeric summaries emitted.
- Failed branches are recorded, not hidden.
- Executed-command ledger joins stage IDs to concrete command strings, exit
  codes, start/end timestamps, and result paths.
- Raw tool outputs are intermediate evidence only. Deliverables need normalized ledgers with provenance, input joins, evidence class, and review status.

## Gate 4: Model And Map

- Model, map, half-map, mask, and validation artifacts recorded.
- Chain assignment and biological assembly assumptions recorded.
- Map/model agreement metrics emitted.

## Gate 5: Figure Report

- Figures are nonblank, labeled, reproducible, and backed by scripts/sessions.
- Captions include contour levels, accessions, software, and caveats.

## Gate 6: Result Review

- Every reported conclusion maps to supporting artifacts.
- Unresolved weaknesses are listed.
- Next experiments are proposed when support is incomplete.
- Result boundaries are explicit: `planning`, `public_demo`, `public_synthetic_demo`, `computational_candidate`, `insufficient_support`, or `blocked`.

## Cryo-EM Evidence Requirements

- Resolution claims require half-map provenance, FSC curve, and mask provenance.
- Map/model claims require map-model correlation, local resolution, and geometry validation.
- Pixel-size and handedness checks are required before final model orientation claims.
- Figures require source accessions, software versions, contour levels, and camera/session state.
- Screenshots alone cannot establish final resolution, handedness, ligand fit, or publishability.
