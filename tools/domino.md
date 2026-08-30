# DOMINO

## Purpose

Plan multidomain construct-assembly lanes for fusion designs that sit
*downstream* of an already-validated binder or effector. DOMINO (Westlake,
bioRxiv 2026-05) is a two-stage framework that learns how protein domains
co-occur in nature and uses that prior to score, retrieve, and assemble
multidomain proteins. It is an adjacent tool, **not** a binder designer: it does
not generate a binder against a target. Use it to decide which natural effector
to fuse to a validated module, in which N-to-C order, and to propose a junction —
then prove the assembly with the cofold scoring stack.

## Public-Safe Status

Public scaffold: yes, with a license caveat. The GitHub repo ships no `LICENSE`,
the Hugging Face model card is empty, and the preprint posts under a no-reuse
license at the time of review. Treat reuse, image inclusion, and redistribution
terms as **unresolved** until the upstream authors publish them. Store weights
and generated sequences under ignored runtime storage or in a user-selected
artifact store.

## When To Use

- Pick a natural effector to fuse to a validated binder, and the N-to-C order
  (directional compatibility score).
- Triage a library of fusion partners cheaply before spending cofold cycles.
- Score how "natural" an engineered architecture is (architecture likelihood).
- Propose a linker/junction as a hypothesis to graft onto fixed, validated
  domain sequences.
- Not for de novo binder design — use RFdiffusion3, Genie3, or the peptide arms
  for that.

## The Two Stages And Four Primitives

DOMINO exposes two models. **DOMIN** is a contrastive retriever/scorer built on a
structure-aware protein language model: it embeds a domain and scores partner
domains by learned co-occurrence (not fold homology). **DOMO** is a conditional
generator that emits a full-length multidomain sequence including the linker and
flanking context.

| Primitive | What it gives you | Out of the box |
| --- | --- | --- |
| P1 | Directional domain-compatibility score for two domains | Yes (needs structure-aware tokens) |
| P2 | Partner retrieval over a pool | Build the pool yourself; not shipped |
| P3 | Conditional generation with a learned junction | Yes |
| P4 | Architecture likelihood / perplexity | Small code change to expose |

P1 is the evidence-backed primitive. The rest are useful but less validated.

## Hand A Mission To An Agent

```text
Use the BioSymphony Structure Factory skill with the DOMINO tool card. For a
validated binder module and a candidate natural effector, plan a P1
compatibility-scoring lane to choose the N-to-C order, then a cofold lane that
proves both modules fold, surfaces stay accessible, and the paratope is
preserved. Record the unresolved upstream license as a gate; do not download
weights, bake an image, or run paid compute until terms and operator budget are
recorded.
```

## Typical Inputs

- Two domain sequences (the validated binder and a natural effector), each with a
  predicted or deposited structure for structure-aware tokenization.
- For retrieval (P2): a precomputed embedding pool of candidate partner domains.
- For generation (P3): the input domain sequences to condition on.

## Typical Outputs

- Directional compatibility scores per domain pair and suggested N-to-C order.
- A generated multidomain sequence whose inter-domain linker is treated as a
  hypothesis, not a designed linker.
- Optional architecture-perplexity scores for engineered fusions.
- A handoff manifest into the cofold scoring stack for the assembly proof.

## Repo And References

- Repo: https://github.com/westlake-repl/DOMINO
- Weights: https://huggingface.co/westlake-repl/DOMINO (model card empty at review)
- Paper: Dai, Su, Tan, Yang, Zhou, Yuan. *DOMINO: Learning Domain Co-occurrence
  for Multidomain Protein Design.* bioRxiv 2026.
- Training data (TED, The Encyclopedia of Domains): bioRxiv 2024.
- Backbone model (SaProt): https://github.com/westlake-repl/SaProt

## Key Knobs

| Knob | Recommendation | Why |
| --- | --- | --- |
| Primitive | Start with P1 (pairwise scoring) | Cheapest and the only evidence-backed use; no pool or generation quality needed. |
| Tokenization | Structure-aware (3Di) tokens, not plain residues | DOMIN consumes structure-aware tokens; predict structure first, then tokenize. |
| Domain order | Score both orders, keep the higher | The score is directional; it suggests the N-to-C arrangement. |
| Retrieval pool | Only for P2 | The natural-domain embedding pool is not shipped; build it before "search all of nature." |
| Linker handling | Graft, do not ship | DOMO regenerates whole domains; extract only the proposed junction and graft onto your exact validated sequences. |

## Gotchas

- A de novo binder is out of distribution. DOMIN is trained on natural domains,
  so trust its score for the effector side and for ordering, and let cofold be
  the real gate on the binder side.
- DOMO is not a fixed-domain linker infiller out of the box: it autoregresses the
  whole sequence from domain conditioning. Use it as a junction proposer, then
  graft the linker between your validated binder and effector sequences.
- DOMIN requires structure-aware tokens, which means a structure-prediction and
  tokenization step is part of the input pipeline.
- All upstream "designability" evidence bottoms out in a single cofolder's
  self-confidence, with no reported inter-domain interface metric. Coherent
  multidomain geometry remains a cofold/PAE job here, not something DOMINO proves.

## Gates

- Treat the upstream license as unresolved: mention and scaffold publicly, but do
  not bake into an image, redistribute, or run paid compute until terms are
  published and recorded.
- Store weights and generated sequences under ignored runtime storage or in a
  user-selected artifact store.
- The supported claim is "both modules fold, surfaces accessible, paratope
  preserved" — architecture, not cellular activity. Cap every fusion candidate at
  `computational_candidate` until independent validation exists.
- Wet-lab confirmation lives downstream of this card.
- Run a currency check before any paid GPU dispatch: upstream repo HEAD, Hugging
  Face model revision and license/model-card state, and recent preprints on
  multidomain or fusion design. Record the version pin and the date of the check.
