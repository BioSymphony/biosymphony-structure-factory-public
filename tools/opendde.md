# OpenDDE

## Purpose

Plan OpenDDE prediction and cofold lanes for biomolecular complexes. OpenDDE is
an AlphaFold-3-style, all-atom model that accepts proteins, DNA, RNA, ligands,
ions, modifications, and covalent-bond records. In Structure Factory it is best
used as an orthogonal cofold validator next to Boltz, Chai-1, AF2-Multimer, and
ESMFold2, not as a backbone or sequence generator.

## Public-Safe Status

Public scaffold: yes. Runtime use requires current source, Docker image,
checkpoint, common-runtime-file, and artifact-hash review before paid dispatch.

Observed on 2026-07-05:

- Repo: `aurekaresearch/OpenDDE`, commit `a72e9f655231660f8af0072dbdb8b2a54f3fbd3c`.
- Docker: `aurekaresearch/opendde:v1`, Linux/amd64, tag digest observed as
  `sha256:a9404f76df1cd965a80447ee30c9c440af48b199581d9bd44ee157c18109a9d6`.
- Hugging Face model repo commit: `eddd563ce96571f784012edd8f045181c8f8627d`.
- PyPI package route was not available at review time; use source install or
  the Docker image.

## When To Use

- Add an independent cofolder vote for public protein-protein or
  antibody-antigen candidate triage.
- Run the ABAG checkpoint as a focused antibody-antigen canary.
- Predict mixed biomolecular inputs containing proteins, RNA, DNA, CCD ligands,
  ligand files, SMILES, ions, modifications, or explicit covalent bonds.
- Exercise a four-GPU context-parallel path for larger complexes after a
  single-GPU or small-input canary passes.

## Hand A Mission To An Agent

```text
Use the BioSymphony Structure Factory skill with the OpenDDE tool card. For
target <PDB:ID> and candidate set <path>, prepare an OpenDDE cofold lane:
convert inputs to OpenDDE JSON, start with a no-search public canary, then run
predictions with --need_atom_confidence true for ranked candidates so PAE/PDE
sidecars are preserved. Declare checkpoint hashes, command ledger, output-count
checks, CIF outputs, confidence JSON, full_data JSON, and result boundary.
```

## Typical Inputs

- OpenDDE JSON: top-level list of jobs.
- `proteinChain`, `dnaSequence`, `rnaSequence`, `ligand`, or `ion` entities.
- Optional `pairedMsaPath`, `unpairedMsaPath`, and `templatesPath`.
- Optional `covalent_bonds`.
- Runtime data under `$OPENDDE_ROOT_DIR`: `checkpoint/`, `common/`, and
  `search_database/` when local template or RNA-MSA search is used.

## Typical Outputs

OpenDDE writes per-job and per-seed outputs under:

```text
<out_dir>/<job_name>/seed_<seed>/predictions/
```

Minimum outputs:

- `<job_name>_sample_<rank>.cif`
- `<job_name>_summary_confidence_sample_<rank>.json`

When `--need_atom_confidence true` is enabled:

- `<job_name>_full_data_sample_<rank>.json`

The summary JSON includes values such as `plddt`, `gpde`, `ptm`, `iptm`,
`chain_pair_iptm`, clash flags, and `ranking_score`. The full-data JSON includes
larger token-pair sidecars such as PAE/PDE/contact values that are required for
ipSAE-style rescoring.

## Repo And References

- Repo: https://github.com/aurekaresearch/OpenDDE
- Project site: https://aurekaresearch.github.io/OpenDDE-Website
- Model/data files: https://huggingface.co/aurekaresearch/OpenDDE
- Docker image: `aurekaresearch/opendde:v1`
- License: Apache-2.0 in the reviewed repository.

## Minimum-Viable Invocations

### Source install

The public package index did not expose an `opendde` distribution at review
time, so use a source checkout for non-Docker runs:

```bash
git clone https://github.com/aurekaresearch/OpenDDE.git
cd OpenDDE

uv venv --python 3.11
source .venv/bin/activate

# CPU/dev route.
uv pip install --torch-backend cpu -e '.[cpu]'

# Linux/CUDA route.
uv pip install --torch-backend cu126 -e '.[gpu]'

opendde doctor
```

### Runtime data

For the smallest no-search canary:

```bash
export OPENDDE_ROOT_DIR=/workspace/opendde_data

bash scripts/download_opendde_data.sh \
  --root "$OPENDDE_ROOT_DIR" \
  --skip-search-database
```

This still downloads or verifies the model checkpoint plus common files. Record
URL, ETag/Xet hash where available, byte size, and local SHA-256 before loading.

### Minimal no-search prediction

```bash
LAYERNORM_TYPE=torch opendde pred \
  -i tiny.json \
  -o output/opendde \
  -n opendde_v1 \
  --use_msa false \
  --use_template false \
  --use_rna_msa false \
  --triatt_kernel torch \
  --trimul_kernel torch \
  --dtype fp32 \
  --sample 1 \
  --step 200 \
  --cycle 10
```

### Sidecar-preserving ranking run

```bash
opendde pred \
  -i candidates.json \
  -o output/opendde \
  -n opendde_v1 \
  --use_msa false \
  --use_template false \
  --use_rna_msa false \
  --sample 3 \
  --step 200 \
  --cycle 10 \
  --need_atom_confidence true
```

Use this mode for ranked candidates when Structure Factory needs PAE/PDE
sidecars. Do not enable it blindly for broad fanout without an artifact-size
budget.

### ABAG checkpoint

```bash
opendde pred \
  -i abag_complex.json \
  -o output/opendde_abag \
  -n opendde_v1 \
  --load_checkpoint_path "$OPENDDE_ROOT_DIR/checkpoint/opendde_abag.pt" \
  --need_atom_confidence true
```

### Docker GPU route

```bash
docker run --rm --gpus all --shm-size=4g \
  -e OPENDDE_ROOT_DIR=/opendde_data \
  -v "$OPENDDE_ROOT_DIR":/opendde_data:ro \
  -v "$PWD":/workspace \
  -v "$PWD/output":/output \
  aurekaresearch/opendde:v1 \
  opendde pred \
    -i /workspace/tiny.json \
    -o /output/opendde \
    -n opendde_v1 \
    --use_msa false \
    --use_template false \
    --use_rna_msa false \
    --sample 1 \
    --step 200 \
    --cycle 10
```

Pin the Docker digest in execution-ready provider manifests rather than relying
only on the mutable tag.

### Four-GPU Fold-CP route

```bash
CUDA_VISIBLE_DEVICES=0,1,2,3 torchrun --standalone --nproc_per_node 4 \
  -m runner.batch_inference pred \
  -i examples/protein_200.json \
  -o output/opendde_cp4 \
  -n opendde_v1 \
  --use_msa false \
  --use_template false \
  --use_rna_msa false \
  --sample 1 \
  --step 200 \
  --cycle 10 \
  --foldcp_mode distributed \
  --foldcp_size_dp 1 \
  --foldcp_size_cp 4 \
  --foldcp_metrics_jsonl output/opendde_cp4/foldcp_metrics.jsonl
```

## Key Knobs

| Flag or file | Recommendation | Why |
| --- | --- | --- |
| `--sample` | 1 for canary, 3+ for ranking | Multiple diffusion samples stabilize ranking. |
| `--step` | 200 for final, consider smaller only after calibration | Public defaults use 200. |
| `--cycle` | 10 | Public default for `opendde_v1`. |
| `--use_msa` | false for first canary, true when paths are supplied or service posture is approved | Public MMseqs2 is not private-sequence safe. |
| `--use_template` | false for first canary | Template path needs HMMER, Kalign, database/cache posture. |
| `--use_rna_msa` | false unless RNA MSA is explicitly needed | RNA databases are large. |
| `--need_atom_confidence` | true for ranked candidates | Saves PAE/PDE/contact sidecars for downstream scoring. |
| `--load_checkpoint_path` | required for `opendde_abag.pt` | ABAG checkpoint is not the default. |
| `--triatt_kernel`, `--trimul_kernel` | `torch` for compatibility, `auto` for production GPU after smoke | Keeps first canaries simple and debuggable. |
| `LAYERNORM_TYPE` | `torch` for compatibility | Avoids optional CUDA/JIT LayerNorm during first route proof. |
| `MMSEQS_SERVICE_HOST_URL` | self-hosted endpoint for private/batch work | Public ColabFold MMseqs2 is rate-limited and public-service routed. |

## Search And Prep Dependencies

- Protein MSA: public ColabFold-compatible MMseqs2 service by default, or a
  self-hosted `MMSEQS_SERVICE_HOST_URL`.
- Template search: `hmmbuild`, `hmmsearch`, and
  `$OPENDDE_ROOT_DIR/search_database/pdb_seqres_2022_09_28.fasta`.
- Template inference: `kalign` and template mmCIF cache or remote PDBe fetch.
- RNA MSA: `nhmmer`, `hmmalign`, `hmmbuild`, Rfam, NT-RNA, and RNAcentral
  databases. NT-RNA and RNAcentral are large enough to require explicit storage
  and budget planning.

## Gates

- Use only public accessions or synthetic/test sequences in public examples.
- Before any paid run, record current repo commit, Docker digest or source
  commit, checkpoint URL, remote ETag/Xet hash where available, local SHA-256,
  and byte size.
- Fail closed on missing CIF, missing summary JSON, empty output directories,
  or an `ERR/` directory containing per-job failures.
- Treat `summary_confidence`-only output as incomplete for ipSAE-style scoring.
  Add `--need_atom_confidence true` when interface-error sidecars are required.
- Do not send private sequences to the public MMseqs2 service. Use precomputed
  A3M files or a self-hosted service.
- The checkpoint and RDKit CCD cache are pickle/PyTorch-pickle loaded by the
  reviewed code path. Do not run unpinned or unverified artifacts in a trusted
  environment.

## Suggested Structure Factory Stages

1. `opendde_toolcheck`: source/Docker route, `opendde doctor`, no weight load.
2. `opendde_no_search_canary`: tiny public protein JSON with MSA/template/RNA
   disabled.
3. `opendde_sidecar_probe`: same canary with `--need_atom_confidence true`;
   verify PAE/PDE/contact sidecars are present and joinable to the CIF.
4. `opendde_abag_canary`: public antibody-antigen example with
   `opendde_abag.pt`.
5. `opendde_slate_vote`: run OpenDDE as an additional validator in the cofold
   scoring stack and aggregate `chain_pair_iptm`, `gpde`, clash flags, and
   any derived ipSAE-like score.

## Gotchas

- The docs mention `uv pip install 'opendde[...]'`, but no PyPI distribution was
  visible during the 2026-07-05 review. Prefer source install or Docker.
- Batch inference can log per-sample failures without making the CLI exit
  nonzero. A Structure Factory wrapper must inspect output counts and `ERR/`.
- Job-level `modelSeeds` behavior should be checked for multi-job JSONs; prefer
  explicit `--seeds` in controlled batch runs until this is fixed upstream.
- Full-data sidecars can be large because they include token-pair arrays.
- Search database downloads can dominate setup time and storage. Start with
  no-search canaries and promote to `msa`, `mt`, or `prep` only after the input
  class requires it.
