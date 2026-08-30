# Standalone Local Binder-Design Example

The no-private-infrastructure starter path. Use `bsf scaffold-campaign` to create a campaign skeleton, validate it, and generate task drafts on a laptop with no RunPod, Linear, private images, model weights, or credentials.

## Hand A Mission To An Agent

```text
Use the BioSymphony Structure Factory skill. Build a standalone local binder-design campaign for a public GPCR target (PDB 5G53, TM6 activation microswitch). Scaffold it under .runtime/, validate it, generate tracker-neutral task drafts, and explain what each artifact is for.
```

## Run It Yourself

```bash
bsf scaffold-campaign .runtime/standalone-local-binder-design \
  --campaign-id standalone-local-binder-design \
  --target-label "A2A receptor" \
  --public-accession "PDB:5G53" \
  --window "TM6 activation microswitch"

bsf validate .runtime/standalone-local-binder-design
bsf issue-dry-run .runtime/standalone-local-binder-design \
  --out .runtime/standalone-local-binder-design-issues
bsf audit .
```

When the scaffold is reviewed, has reviewed public accession notes, and preserves the result boundary, it can move under `examples/` as a new public example.
