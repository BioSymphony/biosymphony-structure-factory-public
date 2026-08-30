# RunPod Launch Kit

This directory contains provider-facing prep artifacts for Structure Factory RunPod Pods. It is intentionally no-download by default.

## Files

- `pod-env.schema.json`: allowed runtime environment variables.
- `network-volume-layout.md`: required persistent volume layout.
- `templates/*.template.json`: image-family Pod template specs.
- `launch-manifests/no-download-smoke.json`: first smoke-run manifest.
- `launch-manifests/raw-subset-open.json`: EMPIAR-13124 100-movie open-tool subset plan.
- `launch-manifests/raw-subset-gated.json`: EMPIAR-13124 100-movie CryoSPARC/MotionCor3-gated subset plan.
- `launch-manifests/map-model-report.json`: EMDB/PDB-only report plan.
- `stage-contracts/*.stage-contract.json`: stage IDs, outputs, timeouts, checkpoints, resume commands, and fail-closed rules.
- `entrypoints/`: RunPod startup scripts for repo clone, tool checks, license gates, raw-subset scaffolding, and small-artifact export.
- `launch-manifests/*`: every profile must require `validation/input-audit.json`, `stage-progress.jsonl`, `validation/stage-contract-check.json`, and `validation/contract-self-check.json`.

## Setup Choices

RunPod launches do not require GHCR. Valid setup postures are:

- public/prebuilt image
- private image with runtime registry auth
- public base image plus runtime install
- public base image plus Structure Factory Network Volume bootstrap

Use the dedicated `STRUCTURE_FACTORY_RUNPOD_NETWORK_VOLUME_ID` for Structure Factory writable state in public docs/templates. Operator-gated bridge manifests may carry the resolved owned volume ID after scope validation. Do not point these manifests at sibling campaign volumes. If the selected posture is Network Volume bootstrap, tools live under `/workspace/structure-factory/software/` or `/workspace/software/` on a dedicated Structure Factory-only volume and must be installed from version-pinned scripts, then verified before scientific stages.

## Rules

- Use Pods, not Serverless, for first Structure Factory execution.
- Store durable outputs under `/workspace/structure-factory/`.
- Never include secrets, licenses, tokens, private data, raw maps, or model weights in manifests.
- Materialize a runtime packet under ignored `.runtime/` space before launch. The packet must carry the resolved bindings and explicit authorization for that run.
- Tracked bridge and launch manifests keep `remote_launch_allowed: false`, `public_template_status: tracked_public_template`, and pending launch authorization fields. The runtime materializer replaces those template values after validation and authorization.
- Use container/pod scratch for the raw-subset demo by default; do not persist raw movies after export.
- GHCR/Docker Hub are for software images only, never raw EMPIAR data.
- Private GHCR images are optional and require runtime registry auth references. A Pod trying to pull an unauthorized private image is not progress, even if RunPod desired status says `RUNNING`.
- Before launch, pin the image digest and repository commit, then run `runpod_launch_preflight.py --execution-ready`.
- Before a paid launch, run `make runpod-scope-check` for the materialized bridge manifest.
- Workers must monitor actual provider state plus `stage-progress.jsonl`; `desiredStatus` alone is never closeout evidence.
- Local mock runs must set `STRUCTURE_FACTORY_EXECUTION_MODE=prep`; real RunPod executions should use `real` and fail if mock evidence is present.
- Raw-download profiles require both `STRUCTURE_FACTORY_ALLOW_RAW_DOWNLOADS=1` and `STRUCTURE_FACTORY_OPERATOR_AUTHORIZED=1` at runtime.
  In tracked launch manifests these values remain `PENDING_OPERATOR_AUTHORIZATION`; resolved values belong only in ignored runtime state after explicit human authorization.
