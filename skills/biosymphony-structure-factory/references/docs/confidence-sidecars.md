# Confidence Sidecars

Structure Factory fold and cofold lanes should keep the confidence data needed
for interface scoring and model comparison. A scalar score alone is not enough
to reproduce or inspect the score later.

## Rule

If a predicted structure will be scored, ranked, rendered, or used as an input
to a downstream gate, persist the confidence sidecars from the same model pass
that produced the structure:

- predicted aligned error or interface-error matrix, when the model exposes one
- per-residue confidence such as pLDDT
- model confidence JSON or equivalent structured metadata
- per-chain or chain-pair confidence values, when available
- command, version, input, and hash ledgers that join the sidecars to the
  structure file

Do this at fold time. Re-running a fold only to recover confidence arrays wastes
GPU time and can produce a different sample from the one being reviewed.

## Storage

Sidecars are run artifacts. Keep them under an ignored runtime or operator
artifact root unless they are tiny synthetic fixtures explicitly intended for a
public test.

Docs and manifests should declare the expected sidecar names, checksums, and
result boundaries. Do not commit real generated structures, private inputs,
unpublished sequences, provider logs, or large confidence arrays.

## What To Save

| Lane | Minimum sidecars |
| --- | --- |
| Boltz cofold | structure file, confidence JSON, full PAE matrix, per-residue pLDDT, hash ledger |
| Chai or AF2/ColabFold cofold | structure file, prediction confidence output, PAE-equivalent matrix, per-residue pLDDT, hash ledger |
| ESMFold2 wrappers | structure file plus compressed `pae` and `plddt` arrays when exposed by the model output |
| Backbone generators | no PAE is expected; the downstream cofold validator must produce the confidence sidecars |
| Render/report lanes | pLDDT-colored outputs should cite the exact confidence sidecar that supplied the values |

For Boltz, `--write_full_pae` is the load-bearing flag. For Python wrappers,
write compressed array sidecars such as `<stem>.confidence.npz` and keep arrays
out of JSON payloads.

Raw logits are normally not required. Save derived arrays that downstream
scorers consume, such as PAE and pLDDT, unless an issue explicitly asks for a
debug bundle.

## Scoring Status

Mark interface scoring incomplete when:

- only global pTM, iPTM, or complex pLDDT is available
- the structure exists but its confidence sidecar is missing
- the sidecar cannot be joined to the reviewed model by stem, manifest row, or
  hash
- an ipSAE, pDockQ2, LIS, or interface-confidence table was requested but the
  underlying PAE or pLDDT data was not saved

Record the structure as present, the interface score as incomplete, and the
missing sidecar names.
