# Privacy And Security Model

Structure Factory is a public release control plane. It is useful because it keeps the plan, contracts, validation commands, and run boundaries in git while keeping sensitive runtime material out of git.

Run boundaries are part of the privacy and security model: generated, predicted, derived, or provider-backed outputs must be labeled according to what actually ran and what was validated.

## Public By Default

Public files may contain:

- public accession identifiers and source links
- synthetic fixtures
- compact JSON manifests and schemas
- issue templates and tracker-neutral task drafts
- stage contracts, expected artifact names, and validation commands
- placeholder environment variable names
- bounded reports and public demos

## Never Commit

Never commit:

- API keys, tokens, passwords, SSH keys, signed URLs, license files, or registry auth
- private structures, unpublished sequences, patient data, or customer data
- raw cryo-EM movies, raw maps, particle stacks, model weights, generated structures, or large archives
- provider pod IDs, volume IDs, account IDs, billing records, or raw provider logs
- local workstation paths, private tracker URLs, or internal operator notes
- accepted-license records for tools whose terms are user-specific

## Launch Templates

Public RunPod and cloud files are templates. They must not embed real launch payloads, concrete placement, provider IDs, private image auth, accepted-license state, or approval timestamps.

Launch templates are safe to publish when they omit credentials, live resource identifiers, accepted-license state, approval records, and embedded runtime payloads.

Live execution packets belong in one of these places instead:

- ignored `.runtime/` folders
- a secure operator store
- provider-managed secrets
- an institutional workflow system
- a private fork with its own secret scanning and access controls

## Threat Model

The main risks this repo guards against are:

- accidentally publishing private biological data
- leaking provider credentials or resource IDs
- shipping generated candidate structures or sequences as public fixtures
- presenting therapeutic or binding conclusions from computational prep
- letting a public template become launchable without authorization
- publishing dirty history after current-tree cleanup

## Required Local Checks

Run before sharing the current tree:

```bash
make public-switch-check
```

Run before a real public repository switch:

```bash
make clean
make public-switch-check
make secret-scan
```

Then publish from a reviewed root commit or recreated public repository so old restricted/generated artifacts are not recoverable from history.
