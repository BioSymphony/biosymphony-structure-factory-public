# Screening Superpowers Campaign

## Scientific Objective

Build a reusable high-throughput structure-based screening workflow that accepts minimal inputs, produces compact ranked ledgers, and promotes only selected candidates to reports.

The campaign is deliberately screening-first: a run should answer "what should a reviewer look at next?" before it tries to create publication-style figures or per-ligand reports. The default closeout artifact is the ledger bundle, not a folder of thousands of reports.

## Scope

- OpenBind-style calibration shape: redocking, cross-docking, cofolding, affinity baselines, and method disagreement.
- Public-safe fixture and no-download validation.
- Provider-neutral fanout with RunPod first, AWS Batch second, and neocloud GPU pods third.
- Natural-language direction for screening and protein+RNA map-fitting requests.

## Non-Scope

- No paid RunPod, AWS, or neocloud launch without an explicit operator gate.
- No private structures, unpublished sequences, raw movies, model weights, secrets, or large data in git.
- No `validated` or `publishable` claims from prediction-only or fixture evidence.

## Example Inputs

- `examples/screening-superpowers/screening-manifest.json`
- `examples/screening-superpowers/ligand-library.json`
- `examples/screening-superpowers/receptor-ensemble.json`
- `modules/campaigns/screening-superpowers.v1.json`

The fixture manifest declares:

- campaign ID: `screening-superpowers`
- run ID: `screening-superpowers-fixture`
- target: `fixture-protease-pocket`
- ligand set: five fixture ligands, including active-like controls, a fragment control, a decoy, and one invalid-SMILES negative control
- receptor ensemble: holo, apo, and fragment-context receptor members
- provider posture: no-download fixture with `max_spend_usd: 0`, `expected_download_bytes: 0`, and paid compute gate required for any provider run

## Expected Artifacts

- `consensus_ranking.csv`
- `ligand_prep.jsonl`
- `pose_predictions.jsonl`
- `affinity_predictions.jsonl`
- `metrics.json`
- `method_summary.json`
- `failure_report.json`
- `validation_ledger.json`
- `candidate_reports/`
- `method_disagreement.jsonl`
- `scaffold_atlas.json`
- `active_learning_tranches.json`
- `rescue_queue.json`
- `evidence_graph.json`
- `selection_rationale.md`

The closeout contract for the no-download fixture also expects validation and provenance sidecars such as `validation/input-audit.json`, `stage-progress.jsonl`, `executed-commands.jsonl`, and `provenance.md`. These stay under ignored runtime paths such as `.runtime/screening-superpowers-fixture/` or provider artifact roots, not in git.

## What Candidate Reports Are For

Candidate reports are selective review packets. Promote them for:

- top-ranked hits
- known controls
- representative scaffolds
- method-disagreement cases
- failures that explain a pipeline or input problem

A candidate report should join the selected candidate back to the screening manifest, source scores, pose summary, method disagreement, validation ledger, and provenance. It is not required for every ligand, and it does not upgrade a docking, cofolding, or fixture score into an affinity, mechanism, or publishability claim.

## Dispatch Model

Symphony/Linear dispatch treats each issue as the durable scientific contract. Workers consume the issue body and workflow metadata, not the operator chat. Every issue must include:

- subgroup: `structure-factory`
- campaign ID: `screening-superpowers`
- routing label: `sym:structure-factory`
- exact inputs and expected artifacts
- acceptance criteria and validation commands
- owned paths and dependencies
- license, capability, provider, and claim-level caveats
- a `<!-- symphony:schema -->` block

Current dispatch posture: W00 is the committed campaign-contract draft under `linear-issues/`. Later wave drafts are generated from `scripts/structure_factory/screening_issue_broker.py`; do not hand-edit broker-generated bodies in place.

Only W00 should be `Todo` at initial dispatch. W01-W03 stay in `Backlog` until W00 records that the repo, examples, module references, and no-download gates are coherent.

## No-Paid Gate

The no-paid lane is limited to fixture, schema, planning, and local dry-run artifacts:

- provider: `provider-neutral` or `local`
- execution profile: `screening-no-download-smoke`
- max spend: `$0`
- expected download bytes: `0`
- allowed data: repo fixtures and public accession metadata only
- forbidden actions: RunPod/AWS/neocloud pod creation, public raw-data download, private data use, restricted tool install, model-weight download, registry-auth mutation, and secret handling
- claim ceiling: `fixture_or_demo` evidence and `candidate` scientific claims at most

No-paid success means the ledger and candidate-report contracts are internally coherent. It does not mean real docking, real affinity prediction, biological binding, or mechanism evidence exists.

## Paid Gate

Any paid, heavy, provider-backed, raw-data, private-data, model-weight, or license-gated execution requires an explicit operator gate before launch. The gate must record:

- provider and setup posture
- max spend and max runtime
- immutable repo ref or approved snapshot delivery path
- stage contract and progress ledger path
- fanout estimate, and one-provider canary before scaled fanout
- expected artifacts, artifact pull path, hash checks, and cleanup policy
- Structure Factory-owned writable volume policy for RunPod
- runtime registry auth reference when private images are selected
- license/use-context review for gated tools
- final `<!-- symphony-outcome -->` closeout requirements

Provider state alone is never success. A paid issue closes only after declared artifacts are fetched, validated, hashed, scanned for fixture/secret-like markers, joined to the validation ledger, and cleanup or retained-resource authorization is recorded.

## Validation Commands

```bash
make screening-check
make provider-check
make runpod-scope-check
make stage-contract-check
```

## License And Capability Caveats

RDKit, AutoDock Vina, and Boltz are the intended open-default lanes after current terms are recorded. GNINA and DiffDock are review-required. AlphaFold 3, Phenix, ChimeraX, and CryoSPARC remain runtime-gated or use-context-gated.

## Final Shape

The main campaign output is a screening ledger. Candidate reports are downstream review artifacts for selected hits, controls, disagreement cases, and failures.

Acceptance for the bounded W00-W13 uplift:

- users can identify the fixture inputs and expected output bundle without reading scripts
- dispatch state, routing label, and broker/static issue posture are explicit
- no-paid and paid gates are stated as separate contracts
- W00-W13 issue drafts can be copied into Linear without inventing missing fields
- all public text remains free of secrets, private data, heavy artifacts, and unsupported scientific claims
