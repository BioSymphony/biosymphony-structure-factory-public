# Screening Superpowers

`screening-superpowers` makes screening a first-class Structure Factory mode. The default output is a compact, auditable ledger: prepared ligands, pose predictions, affinity or baseline predictions, consensus ranking, failures, method summary, provenance, and validation notes.

The campaign imports the main lesson from OpenBind-style releases such as the [EV-A71/CVA16 2A protease structure-affinity benchmark](https://openbind.uk/news/blog-openbinds-first-release-a-structure-affinity-dataset-for-structure-based-ai/): separate redocking, cross-docking, cofolding, and affinity prediction; keep simple baselines in the ledger; and record method disagreement instead of treating one model score as truth.

Candidate reports are selective promotion artifacts for top hits, known controls, representative scaffolds, method-disagreement cases, and failures worth debugging. They are not the unit of throughput.

## User Promise

A user should be able to start with a plain request such as "screen this public target against this ligand list" and receive a bounded, auditable packet:

- what inputs were accepted or rejected
- which ligand/receptor states were scored
- which methods produced candidate scores
- which ligands failed and why
- which methods disagreed
- which candidates deserve a human report
- what result boundary is allowed by the evidence

For the no-download fixture, every score is deterministic fixture support. For real provider runs, the same artifact names are reused, but success requires provider logs, pulled artifacts, hashes, cleanup proof, and validation review.

## Operating Model

Minimal inputs:

- natural-language goal
- target hint or public accession
- ligand library or source
- pocket/site definition, or an explicit blind-mode declaration
- budget and provider posture
- use context for gated tools

Default method comparison:

- stdlib/RDKit-style descriptor baselines and simple affinity baselines
- AutoDock Vina as the open wide-screen docking lane
- Boltz-2 as the focused cofolding/affinity-aware lane
- MolPAL-style active-learning tranche planning after a score-provider contract
  exists
- PoseBusters-style pose plausibility checks after a pose-producing lane emits
  files
- GNINA, DiffDock, AlphaFold 3, Chai, Phenix, ChimeraX, and CryoSPARC as gated or review-required lanes until current terms and runtime access are recorded

Provider order:

1. RunPod for the reference GPU pod path.
2. AWS Batch for scalable cloud fanout.
3. neocloud GPU pods for RunPod-like pod capacity.

Every paid run still requires an operator gate, budget cap, runtime cap, artifact pull/hashes, and cleanup proof.

## Concrete Fixture Inputs

The current public fixture lives in `examples/screening-superpowers/`:

- `screening-manifest.json` declares the `screening-superpowers-fixture` run, `fixture-protease-pocket` target, no-download policy, provider priority, and `candidate` result boundary.
- `ligand-library.json` contains five fixture ligands: two active-like controls, one fragment control, one decoy control, and one invalid-SMILES negative control.
- `receptor-ensemble.json` contains holo, apo, and fragment-context receptor entries plus a reference-ligand pocket box.
- `modules/campaigns/screening-superpowers.v1.json` joins the data modules, image modules, lane modules, smoke suite, artifact contract, and campaign policies.

The fixture is intentionally small and synthetic. It is sized for contract checks rather than biological inference.

## Concrete Output Bundle

The screening result contract expects these core outputs:

- `ligand_prep.jsonl` for normalized ligand records and preparation status
- `pose_predictions.jsonl` for docking or cofolding pose-like records
- `affinity_predictions.jsonl` for method scores and simple baseline records
- `consensus_ranking.csv` for final sortable hit ranking
- `metrics.json` for run-level counts and summary metrics
- `method_summary.json` for method coverage, calibration scope, and disagreement
- `failure_report.json` for invalid ligands, missing inputs, tool failures, and blocked lanes
- `validation_ledger.json` for source posture and result boundary
- `candidate_reports/` for selected human-review packets
- `method_disagreement.jsonl` for cases where method proxies diverge
- `scaffold_atlas.json` for coarse scaffold/diversity buckets
- `active_learning_tranches.json` for top-hit, control, disagreement, and rescue follow-up groups
- `rescue_queue.json` for invalid inputs, high-disagreement cases, and recovery actions
- `support_graph.json` for manifest-to-ledger-to-result traceability
- `provenance.md` and `executed-commands.jsonl` for reproducibility

Provider-backed canaries add `validation/fanout-estimate.json`, `validation/artifact-pull-report.json`, `validation/contract-self-check.json`, `cost_report.json`, `cleanup_proof.json`, and the provider `stage-progress.jsonl`.

## Candidate Reports

Candidate reports exist to help a scientist review a small number of important cases. They should be generated for top-ranked hits, known controls, representative scaffolds, method-disagreement cases, and failures worth debugging.

Each report should include:

- `candidate_report_manifest.json`
- `screening_manifest_ref.json`
- `candidate_evidence.json`
- `pose_summary.json`
- `method_disagreement.json`
- `validation_ledger.json`
- `provenance.md`

A report is not an assertion that a ligand binds. It is a compact review packet that inherits the weakest source posture in its sources. Fixture reports remain `fixture_or_demo`; prediction-only or docking-only reports remain candidate evidence.

## Symphony And Linear Dispatch

The campaign is dispatched as bounded Linear issues with routing label `sym:structure-factory`. Each issue body is the contract workers follow. Important operator comments should be copied into the issue if they must affect execution, because workers consume the issue and workflow metadata rather than the live chat.

Initial state:

- W00 is the only `Todo` issue.
- W01-W08 are `Backlog`.
- W09 is `Blocked` until explicit license, private-data, or advanced-tool gates exist.

The committed W00 task draft lives under `campaigns/screening-superpowers/linear-issues/`. Later wave drafts are generated by `scripts/structure_factory/screening_issue_broker.py` and should be regenerated instead of hand-edited.

Worker closeout must include a parseable `<!-- symphony-outcome -->` block. Provider-backed closeout must also include workload status, validation summary, artifact hashes or artifact packet path, cleanup status, result boundary, and any partial/degraded fallback.

## No-Paid Gate

No-paid work is allowed only for docs, contracts, fixtures, schemas, local dry-run artifacts, and validation. The required posture is:

- max spend: `$0`
- expected download bytes: `0`
- provider mutation: forbidden
- allowed inputs: repo fixtures and public accession metadata
- forbidden inputs: private structures, unpublished sequences, private ligand libraries, raw movies, model weights, secrets, and large datasets
- forbidden actions: RunPod/AWS/neocloud launch, restricted install, license-gated runtime activation, model-weight download, registry-auth mutation, and public raw-data download
- result boundary: `public_synthetic_demo` for fixture outputs and `computational_candidate` for real provider-backed hit summaries

Passing no-paid checks means the control plane is coherent. It does not establish real docking accuracy, affinity, pose recovery, mechanism, pharmacology, or publishability.

## Paid Gate

Paid or provider-backed work requires an explicit operator gate issue before launch. That gate must state:

- provider: RunPod, AWS Batch, neocloud, local high-resource workstation, SSH/HPC, or generic cloud
- setup posture: public image, private image, runtime bootstrap, Structure Factory Network Volume bootstrap, local install, HPC module, or neocloud volume
- max spend and max runtime
- immutable code delivery path or approved clean snapshot
- stage contract, progress ledger, resume command, and partial-success policy
- fanout estimate and one canary before scaled fanout
- expected artifacts and validation commands
- artifact pull, hash verification, secret/fixture marker scan, and cleanup proof
- license/use-context posture for gated tools

For RunPod, the writable volume must be Structure Factory-owned and public docs/templates should use `STRUCTURE_FACTORY_RUNPOD_NETWORK_VOLUME_ID`. Private images require a runtime registry-auth reference before launch. A provider state such as `RUNNING` is only intent; it is not workload or scientific success.

## Acceptance Criteria

The campaign is concrete enough for user-facing dispatch when:

- a user can identify the exact fixture inputs and expected output files
- the report promotion policy is clear and selective
- no-paid and paid gates are separate and testable
- Linear issue states and routing are explicit
- W00-W03 tasks name owned paths, dependencies, validation commands, and result-boundary caveats
- fixture, prediction-only, docking-only, and provider-backed result boundarys are not conflated
- public docs contain no secrets, private data, heavy artifacts, or unsupported biological conclusions

## Local Fixture

Run:

```bash
make screening-check
```

This validates the campaign module, AWS and neocloud profiles, screening manifest, fanout estimate, no-download fixture runner, active-learning outputs, schema contracts, provider adapter dry-run packets, and the natural-language intent compiler.

The fixture writes ignored artifacts under `.runtime/screening-superpowers-fixture/`. These are fixture outputs only and cannot support biological binding, affinity, pose, or mechanism conclusions.

## Natural-Language Direction

The compiler supports minimal prompts:

```bash
python3 scripts/structure_factory/structure_intent_compile.py \
  --prompt "screen TERT inhibitors" \
  --out .runtime/screening-superpowers-fixture/tert-screen.json \
  --json
```

For method-disagreement-style requests:

```bash
python3 scripts/structure_factory/structure_intent_compile.py \
  --prompt "compare AlphaFold3 and Boltz predictions where they disagree" \
  --out .runtime/screening-superpowers-fixture/disagreement-intent.json \
  --json
```

Each mode (`screen`, `openbind_calibration`, `method_disagreement`) expands to
public-accession planning, conservative `candidate` result boundary, and a
`tool_blockers` list for any requested gated tool. The compiler does not launch
compute or download heavy data.
