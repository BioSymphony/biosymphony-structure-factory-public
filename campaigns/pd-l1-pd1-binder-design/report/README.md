# PD-L1 Report Output

Generated runtime reports are intentionally not tracked in the public export.

The prior generated report included runtime-only artifact links, generated
candidate structures, generated binder sequences, and provider-run narrative
details. Keep those files under ignored runtime/report output unless they have
gone through a public-release redaction pass.

Public-safe summaries live in `../rankings/*.public-summary.json`. They retain
candidate IDs, high-level metrics, and claim ceilings while redacting generated
sequences and runtime artifact paths.
