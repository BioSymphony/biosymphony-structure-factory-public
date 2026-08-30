# Public Release Readiness

Last reviewed: 2026-08-30

Publish a tree only after the checks in this document pass and a reviewer confirms its Git history and remote target.

## Release Boundary

The public tree contains campaign contracts, task packs, provider templates, validators, and compact public or synthetic examples. Keep private data, unpublished or generated candidate sequences and structures, live provider identifiers, run records, credentials, model weights, and large outputs outside the repository. [`NON_CLAIMS.md`](NON_CLAIMS.md) and [`BIOSAFETY.md`](BIOSAFETY.md) define the scientific boundary.

## Release Gates

Run these from the repository root before publishing:

```bash
make public-switch-check
make clean
```

Recommended independent checks:

```bash
find . -type f -size +25M -not -path './.git/*' -print
git status --short --branch
```

Expected release state:

- `make public-switch-check` passes locally.
- `make release-check`, including `make binder-lane-check`, passes as part of the public-switch gate.
- `make secret-scan` runs with gitleaks installed and reports no leaks. A skipped scan leaves this gate incomplete.
- `make harness-check` reports zero findings.
- `make clean` removes `.runtime/`, caches, and other generated local outputs before review.
- `skills/biosymphony-structure-factory/SKILL.md` is present and linked from public docs.
- `templates/operator-wave-runbook.md` is present for paid, cloud, raw-download, and multi-agent wave gates.
- No private workstation paths, private tracker IDs, concrete provider IDs, or local-only doc references appear.
- No signed provider URLs, one-time transfer links, provider logs, runtime packets, or telemetry outputs are tracked.
- No raw or generated structure files, archives, videos, model weights, or large files are tracked.
- No `.local.json` runtime summaries, Quarto `_book` outputs, generated report HTML, candidate sequences, or candidate render batches are tracked.
- Small curated public demo figures may remain only when they are referenced by public docs and contain no generated candidate sequences, private data, provider metadata, or raw structural files.
- Tracked `runpod/bridge-manifests/*.json` files remain templates. They contain no per-campaign provider bindings, embedded payloads, concrete placement, approvals, run logs, or prior-run volume assumptions. Materialize executable packets under ignored `.runtime/` paths.
- A reviewer inspected every reachable commit intended for the public remote, or the export uses a reviewed public root commit.

See [`docs/public-switch-checklist.md`](docs/public-switch-checklist.md) for the local switch gate, privacy/security checks, history review, and remote-push gate.

## Remote Check

Inspect the configured remote and branch before any push:

```bash
git remote -v
git status --short --branch
git log --oneline --decorate --all
```

Do not push until the owner confirms the organization, repository, visibility, branch, and reviewed commit range.

## Agent Handoff

Read [`AGENTS.md`](AGENTS.md) and use [`skills/biosymphony-structure-factory/SKILL.md`](skills/biosymphony-structure-factory/SKILL.md). Run `make public-switch-check` before describing a tree as release-ready.

## Known Status

This pre-alpha harness checks planning, task generation, provider contracts, fixtures, and public-release rules. Provider-backed biological results require separate execution records, artifact hashes, cleanup proof, and scientist review.
