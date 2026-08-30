#!/usr/bin/env python3
"""Verify every bridge manifest's repo.commit_or_snapshot is reachable on origin.

Catches the F16 class of failure: a pod manifest pinned to a 40-char SHA that
exists locally but was never pushed to the GitHub remote. The pod would clone
successfully but `git checkout <SHA>` would fail with "unable to read tree",
aborting the bootstrap.

Walks runpod/bridge-manifests/*.json. For each manifest:
  - Reads repo.commit_or_snapshot
  - Skips inline:/snapshot:/sha256: refs (not real git SHAs)
  - For real 40-char SHAs, runs `git fetch origin <sha>` to confirm reachability
  - Reports any unreachable SHA as a blocker

Exit codes:
  0  All real-SHA manifests reachable on origin (or only inline/snapshot refs).
  1  At least one manifest pinned to an unreachable SHA.
  2  Internal/usage error (no manifests, missing git, etc.).

Usage:
  python3 scripts/structure_factory/ls_remote_sha_check.py [--manifests-dir DIR] [--json]
"""
from __future__ import annotations

import argparse
import json
import re
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
DEFAULT_MANIFESTS_DIR = ROOT / "runpod" / "bridge-manifests"
SHA40 = re.compile(r"^[0-9a-f]{40}$")


def collect_shas(manifests_dir: Path) -> dict[str, list[Path]]:
    """Return {sha: [manifest_path, ...]} for real SHAs only."""
    sha_to_files: dict[str, list[Path]] = {}
    for path in sorted(manifests_dir.glob("*.json")):
        try:
            data = json.loads(path.read_text())
        except json.JSONDecodeError:
            continue
        ref = (data.get("repo") or {}).get("commit_or_snapshot") or ""
        if SHA40.match(ref):
            sha_to_files.setdefault(ref, []).append(path)
    return sha_to_files


def reachable(sha: str) -> tuple[bool, str]:
    """True if `git fetch origin <sha>` succeeds."""
    try:
        out = subprocess.run(
            ["git", "fetch", "origin", sha],
            cwd=ROOT,
            capture_output=True,
            text=True,
            timeout=30,
        )
        if out.returncode == 0:
            return True, ""
        return False, (out.stderr or out.stdout).strip()
    except Exception as exc:
        return False, str(exc)


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--manifests-dir", type=Path, default=DEFAULT_MANIFESTS_DIR)
    parser.add_argument("--json", action="store_true")
    args = parser.parse_args()

    if not args.manifests_dir.is_dir():
        print(f"error: {args.manifests_dir} not found", file=sys.stderr)
        return 2

    sha_to_files = collect_shas(args.manifests_dir)
    results: list[dict] = []
    bad = 0

    for sha, files in sorted(sha_to_files.items()):
        ok, err = reachable(sha)
        results.append({
            "sha": sha,
            "ok": ok,
            "error": err,
            "manifest_count": len(files),
            "manifests": [str(p.relative_to(ROOT)) for p in files],
        })
        if not ok:
            bad += 1

    summary = {
        "ok": bad == 0,
        "shas_checked": len(sha_to_files),
        "shas_unreachable": bad,
        "manifests_dir": str(args.manifests_dir.relative_to(ROOT)),
        "results": results,
    }

    if args.json:
        print(json.dumps(summary, indent=2, sort_keys=True))
    else:
        print(f"ls-remote-sha-check: {len(sha_to_files)} unique SHAs across manifests")
        for r in results:
            mark = "ok" if r["ok"] else "FAIL"
            print(f"  [{mark}] {r['sha']} ({r['manifest_count']} manifests)")
            if not r["ok"]:
                print(f"        {r['error']}")
        if bad == 0:
            print("ALL OK")
        else:
            print(f"FAIL: {bad} unreachable SHA(s); push the branch before paid launch")

    return 0 if bad == 0 else 1


if __name__ == "__main__":
    sys.exit(main())
