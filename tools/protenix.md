# Protenix

## Purpose

Use Protenix for biomolecular complex prediction and confidence scoring.
Protenix-v2 is the exact Protenix variant in the published binder-study score
stack.

## Public Status

The upstream project states that Apache-2.0 covers its code and model
parameters. The public repository imposes no additional license gate on that
route. Runtime readiness still depends on the selected package or source
revision, model download, MSA path, GPU, and adapter.

## Routes

- Install the upstream package and run its CLI locally or in a reviewed GPU
  container.
- Bind the same CLI to a GPU VM, pod, serverless function, HPC job, or hosted
  service.
- Use `protenix-v2` for an exact published-stack arm. Record another model name
  as a deliberate variant or swap.

The upstream command shape is `protenix pred -i <input.json> -o <output> -n
protenix-v2`. Check the installed version's help before execution because the
package and model catalog can change.

## Inputs And Outputs

Record the input assembly, chain and entity types, template policy, MSA route,
model identity, seed set, and source revision. Preserve predicted structures,
confidence JSON, PAE data when available, logs, output counts, and hashes.

Use ipSAE and scDockQ as separate interface-scoring operations. Do not merge a
Protenix confidence field and a derived interface score under one metric name.

## References

- Upstream repository: https://github.com/bytedance/Protenix
- Public workflow identity:
  [`published-binder-comparison-workflow.json`](../references/published-binder-comparison-workflow.json)
