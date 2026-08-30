# AI Design Runtime Readiness

This note defines runtime checks for Boltz, Genie 3, and ESMFold2 lanes. The science contract is provider-neutral. The user can route a lane through local, FAL, Modal, RunPod, Lambda Cloud, AWS Batch, neocloud, generic cloud, or SSH/HPC compute when a validated adapter satisfies the same output contract.

## Upstream Facts Checked

- This repository pins Boltz 2.2.1. Upstream recommends a fresh Python environment and `pip install boltz[cuda] -U`; PyPI records Python `>=3.10,<3.13` and the `cuda` extra. See [Boltz README](https://github.com/jwohlwend/boltz) and [Boltz PyPI](https://pypi.org/project/boltz/).
- Use YAML for Boltz prediction input. Upstream accepts FASTA, but the prediction docs mark FASTA deprecated. Runtime cofold lanes write `target.yaml`; per-variant model-comparison lanes write `variant.yaml`. See [Boltz prediction docs](https://github.com/jwohlwend/boltz/blob/main/docs/prediction.md).
- Boltz `--cache` defaults to `~/.boltz` and respects `BOLTZ_CACHE`; Structure Factory passes `--cache` to the declared weights/cache directory so first-run downloads are visible in the artifact ledger.
- Boltz `--use_msa_server` calls the mmseqs2/ColabFold service. Use it only for public sequences or an issue that explicitly permits external MSA service use. For private targets, set `STRUCTURE_FACTORY_BOLTZ_USE_MSA_SERVER=0`, accept lower-accuracy single-sequence mode, or provide precomputed MSAs.
- Boltz affinity outputs are small-molecule/protein oriented. Upstream cautions that affinity predictions involving RNA/DNA targets are unreliable. For binder campaigns against RNP or nucleic-acid-containing targets, treat Boltz as a structure/interface comparison first; affinity statements stay capped at `computational_candidate`.
- Genie 3 upstream setup creates a `genie3` conda environment and installs ColabFold into that environment. See [Genie 3 setup docs](https://github.com/aqlaboratory/genie3).
- Genie 3 upstream download defaults fetch both pretrained weights and training data; Structure Factory blocks training data by default and pins HF downloads by revision when enabled.
- Genie 3 binder design supports single-node multi-device, multi-node sharding, beam search, iterative design, and `genie3 status`. Its evaluator writes `info.csv`, `success_info.csv`, successful binders, and successful complexes. Use these files as cloud shard and reduce artifacts.
- Biohub's ESM README describes two execution paths: the Biohub Platform API and local Hugging Face weights. This repository records both. Use Hugging Face weights for the first cloud canary to avoid API-token and API-cost uncertainty.
- Track the native `biohub/ESMFold2` and `biohub/ESMFold2-Fast` checkpoints plus the official Transformers-native `biohub/ESMFold2-hf` full-model checkpoint. The bundled wrapper uses the pinned Biohub `esm` source. A user can bind the Transformers route through another validated adapter.
- Hugging Face metadata checked on 2026-08-28 reported `biohub/ESMFold2-Fast` revision `0438ea0d932a314950665e0b4d0af4322ae88250`, `biohub/ESMFold2` revision `e1e189d0f5fb70c2693da2332eca4443c0ccccd6`, `biohub/ESMC-6B` revision `89c554c46a44d825fbfbe3ce2a6bdc539770bdaa`, and `biohub/ESMFold2-hf` revision `bce015efb23b5dc604842d0ab5c2bbb02c7bd3ee`. The official Transformers docs state that ESMFold2 support was contributed on 2026-08-19, that the checkpoint bundles ESMC, and that the `main` documentation requires a source install until the feature reaches a stable release.
- Biohub ESM source HEAD checked on 2026-05-28 differed from the short install ref in the public README. Operator packets must pin a full source commit SHA deliberately rather than following a floating branch.

## Repo Guardrails

- `make harness-check` is the no-download control-plane check. It validates registry pins, lane modules, binder-manifest posture, bootstrap gates, provider posture, and stage contracts.
- A lane-specific canary is the runtime check. Run it only inside a real GPU runtime or a local workstation that has the selected tool, framework, weights, and GPU visibility.
- RunPod entrypoints look for Network Volume installs under `/workspace/software/envs/...` before installing anything into the image runtime.
- The Genie 3 bootstrap starts only when `GENIE3_INSTALL=1`, `GENIE3_OPERATOR_GATE_ACK=dependency_and_weight_terms_reviewed`, and `GENIE3_ALLOW_COLABFOLD_PARAMS=1` are all set.
- Genie 3 pretrained weights require `GENIE3_DOWNLOAD_WEIGHTS=1`; training data additionally requires `GENIE3_DOWNLOAD_TRAINING_DATA=1` and `GENIE3_ALLOW_TRAINING_DATA=1`.

## Provider Posture

- Provider profiles cover local, FAL, Modal, RunPod, Lambda Cloud, AWS Batch, neocloud, generic cloud, and SSH/HPC routes.
- A selected profile defines the provider contract. A validated platform skill, hosted-API client, or self-hosted adapter supplies the stage execution.
- Local runs declare materialization paths, data-retention posture, and cleanup.
- Closeout evidence: artifact hashes, stage progress, and contract self-check. Provider launch, a pod ID, or a zero exit code does not complete a scientific stage.

## ESMFold2 Cloud Readiness

ESMFold2 enters Structure Factory as a staged prediction/foldability lane:

1. Provider lifecycle smoke with no ESM install, no model weights, no API call,
   and no biological input.
2. `esmfold2-no-download-toolcheck`: source/package/import probes and
   Hugging Face metadata checks only.
3. Hugging Face weights fast canary on one public sequence using
   `biohub/ESMFold2-Fast`.
4. Gallery, binder foldability crosscheck, RNP/complex canary, or Atlas scout
   only after the fast canary has fetched, hashed, and validated artifacts.

The Biohub API route can run through a user-supplied hosted-API adapter. This
repository does not bundle the service client or account binding. API execution
requires runtime-only authentication, terms review, a spend ceiling, a
request-and-response artifact policy, and a closeout that records the API route.

For RunPod, use the standard Structure Factory sequence: tracked template,
ignored runtime packet, launch preflight, explicit human authorization,
validated adapter, paid create, and artifact, hash, and cleanup closeout. The tracked template for this lane is
`runpod/bridge-manifests/esmfold2-no-download-toolcheck.json`; materialize its
live bindings under ignored `.runtime/` space before execution.

Lambda Cloud GPU VMs and Modal serverless GPU functions are reviewed neocloud
paths with their own provider profiles; other bring-your-own cloud VMs stay
under `generic_cloud` until a profile exists. For Lambda Cloud, use one
short-lived GPU VM without a persistent file system for the first canary.
Bootstrap Python 3.12, recheck Torch and CUDA, archive only declared artifacts,
hash the fetched archive, terminate the VM, and verify cleanup. For Modal, set
`max_containers` and a timeout, commit and fetch the Volume artifacts with
hashes, capture a tag-scoped cost report, and record app-stop cleanup.

Minimum ESMFold2 artifact contract:

- `status.json`
- `stage-progress.jsonl`
- `executed-commands.jsonl`
- `validation/host_probe.json`
- `validation/source_install.json`
- `validation/package_probe.json`
- `validation/model_metadata_probe.json`
- `validation/weights_manifest.json` when weights are materialized
- `esmfold2/prediction.cif` for real prediction runs
- `esmfold2/confidence_summary.json`
- `validation/structure_validation.json`
- `methods.md`, `provenance.md`, `claim_ledger.json`, and `artifact_index.json`

What an ESMFold2 canary proves:

- the selected provider can bootstrap the runtime
- the selected model revisions can be materialized or found in cache
- the run emits parseable structure and confidence artifacts
- the artifact egress and cleanup path works

What it does not prove:

- binding, function, mechanism, stability, expression, specificity, safety, or
  therapeutic value
- broad support for every protein/RNA/DNA/ligand input class
- readiness for fanout before a one-sequence canary has closed cleanly

## Binder Demo Implications

- Use public deposited structures for early demos and keep external MSA server use public-only.
- Generate binders with Genie 3 against declared target windows, then use Boltz to re-predict target/binder complexes and score interface plausibility.
- Treat Boltz small-molecule affinity fields as out of scope for protein/RNP binder ranking unless a future validated protocol proves otherwise.
- Close every demo with `computational_candidate` or lower result boundary until experimental or orthogonal computational validation exists.

## Genie 3 No-Download Toolcheck

The bundled RunPod path uses one GPU-pod toolcheck to verify the Genie 3 source, installation, and CLI before a design run. Another provider or local route can use its own adapter when it performs the same source, dependency, command, weight, output, and closeout checks. The no-download toolcheck starts no generation, weight download, ColabFold call, or design output.

Toolcheck files:

- `runpod/bridge-manifests/public-runtime-template.json` - tracked RunPod bridge template that omits credentials, live provider IDs, and authorization. Build the Genie3, Boltz, or RFdiffusion runtime packet under ignored `.runtime/` space, validate it, and obtain explicit human authorization before execution.
- `runpod/stage-contracts/genie3-no-download-toolcheck.stage-contract.json` - 7 fail-closed stages: host_probe, source_download, dependency_review, pip_install, smoke_commands, hf_weights_probe, emit_artifacts.
- `scripts/structure_factory/genie3_toolcheck.py` - single-file runner, embedded in `dockerStartCmd` by the manifest builder.
- `scripts/structure_factory/build_genie3_toolcheck_bridge_manifest.py` - manifest builder.
- Use the binder-design fast-path task pack under `packs/` for an operator-gate Linear task draft.

Pinned public references:

- Source archive at lane-pinned commit `5214459c...0815115` is 12.87 MB; sha256 `5530ad4372f84f4f64b4b17e429d5c2cd05e4c8e07ada07762da40a3c0de6d02`.
- `setup.py` and `README.md` resolve in the extracted source tree.
- Hugging Face revision `9ae31ebb...2a03a2` for `yeqinglin/genie3` resolves with 8 sibling files including pretrained legacy + v1 checkpoints, configs, and gated training-data CSVs.

Make targets:

```bash
make demo-genie3-toolcheck-manifest
make demo-genie3-toolcheck-bridge-validate
make demo-genie3-toolcheck-bridge-prepare
make demo-genie3-toolcheck-execution-packet
make demo-genie3-toolcheck-prep-check
```

What a passing toolcheck proves:

- Genie 3 source archive at the lane-pinned SHA fetches cleanly into the chosen GPU image.
- `pip install -e .` resolves the upstream dependency tree on `pytorch/pytorch:2.4.0-cuda12.4-cudnn9-runtime` without an image rebuild.
- At least one of `genie3 --help`, `python -m genie3.cli --help`, or `import genie3` exits 0.
- The pinned Hugging Face weights revision resolves through a HEAD probe without downloading the response body.

What a passing toolcheck does NOT prove:

- Weights load on the chosen GPU.
- Inference completes.
- Designs are biologically plausible.
- The lane is ready for any specific receptor target.

Test each claim in a separate, scoped run: authorize the weights download with `GENIE3_DOWNLOAD_WEIGHTS=1`, run `genie3-public-design-canary`, then run `genie3-boltz-design-ranking` against a real target window.

## Minimum-Viable Demo Pattern (No-GPU Baseline)

A no-GPU baseline can complete before GPU or provider readiness. It produces a no-download window report from public accession metadata. Genie 3 generation and a Boltz cross-check require the relevant toolcheck and explicit human authorization.
