# Public Switch Checklist

Last reviewed: 2026-08-27

Use this checklist before updating the public remote. It covers the current tree, reachable history, generated files, and provider templates.

## Local Release Gate

Run:

```bash
make public-switch-check
make clean
make harness-check
make public-audit
```

Expected state:

- The public harness, public audit, tests, module checks, provider profile checks, RunPod template checks, issue checks, screening fixture checks, and contract self-check pass.
- `make secret-scan` reports no leaks with `gitleaks` installed. A skipped scan is incomplete and does not satisfy this gate.
- `.runtime/`, cache folders, and generated local outputs are absent after `make clean`.
- `git ls-files` contains no raw structures, maps, archives, videos, model weights, `.local.json` summaries, generated report books, or private runtime outputs.

## Privacy And Security Gate

Before push, verify:

- No private workstation paths, private user names, private tracker URLs, concrete provider IDs, private registry names, or accepted-license records are present.
- No private-only document sentinel, private workshop filename, runtime-output path, or operator-only run-note path is present.
- Tracked RunPod templates omit embedded payloads, concrete placement, live approvals, raw-download authorization, and provider secrets. Materialize those values only in ignored runtime state.
- Public docs use environment variable names and placeholders only. Secrets, tokens, license files, signed URLs, installer links, and provider credentials are never committed.
- Raw cryo-EM movies, private structures, unpublished sequences, private ligand libraries, generated candidate structures, and large public datasets remain outside git.

## History Gate

The public switch should not publish non-public history. Use one of these paths:

- Create a reviewed public root commit from the audited working tree.
- Use a deliberate history rewrite or squash that removes private and generated artifacts from all reachable commits.
- Recreate the public repo from the cleaned tree and verify the first public commit contains only intended public material.

Staged deletions are not enough if old commits remain reachable on the future public remote.

## Remote Gate

Confirm the intended remote, branch state, and commits before any push:

```bash
git remote -v
git status --short --branch
git log --oneline --decorate -n 10
```

Do not push while the repo points at a placeholder or private remote, while the review branch is unapproved, or while any release gate is incomplete.

## Provider Gate

Local public readiness is not remote execution readiness. A real RunPod, AWS, HPC, or neocloud run still requires:

- a pushed public 40-character commit SHA
- digest-pinned or reviewed runtime image posture
- current license/use-context review for gated tools
- explicit operator authorization with budget, runtime cap, and cleanup policy
- expected artifacts, hash checks, progress ledger, and terminal closeout state
