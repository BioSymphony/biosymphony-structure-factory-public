# Validation Notes

## Allowed Statements

- This is a campaign scaffold for PD-L1 binder-design triage.
- The target context is derived from public PDB accession `4ZQK`.
- The example candidate ranking is synthetic and demonstrates schema shape.
- A real run would need GPU execution, artifact hashes, and scientist review before interpreting candidates.

## Disallowed Statements

- A candidate binds PD-L1.
- A candidate blocks PD-1.
- A candidate is selective.
- A candidate is safe.
- A candidate is therapeutic.
- A candidate should be synthesized or tested without separate expert review and authorization.

## Closeout Rule

If target intake, runtime gate, generation, cofold ranking, artifact hashing, or report review fails, close as `blocked`, `partial`, or `insufficient_support`. Do not mark the campaign successful because infrastructure started.
