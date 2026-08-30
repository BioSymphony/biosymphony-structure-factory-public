#!/usr/bin/env python3
"""Lightweight Structure Factory repo preflight."""

from __future__ import annotations

import argparse
import fnmatch
import json
import subprocess
from pathlib import Path


FORBIDDEN_PATTERNS = [
    "*.mrc",
    "*.mrcs",
    "*.eer",
    "*.tif",
    "*.tiff",
    "*.map",
    "*.pdb",
    "*.cif",
    "*.mmcif",
    "*.fasta",
    "*.fa",
    "*.fastq",
    "*.fastq.gz",
    "*.fq",
    "*.fq.gz",
]

REQUIRED_PATHS = [
    "AGENTS.md",
    "README.md",
    "campaigns",
    "containers",
    "docs",
    "docs/compute-backends.md",
    "examples",
    "modules/campaigns/cryoem-raw-to-atomic-no-download.v1.json",
    "modules/provider-profiles/local/workstation-no-download.v1.json",
    "modules/provider-profiles/runpod/pod-no-download.v1.json",
    "references/software-registry.yaml",
    "runpod/launch-manifests/no-download-smoke.json",
    "runpod/pod-env.schema.json",
    "templates/linear-issue.md",
]


def is_ignored_area(path: Path) -> bool:
    return any(part in {".git", ".runtime", "artifacts", "outputs", "raw-data", "model-weights"} for part in path.parts)


def candidate_paths(root: Path) -> list[Path]:
    """Return tracked plus nonignored untracked files when inside a git repo."""
    try:
        result = subprocess.run(
            ["git", "ls-files", "--cached", "--others", "--exclude-standard"],
            cwd=root,
            check=True,
            text=True,
            capture_output=True,
        )
    except (OSError, subprocess.CalledProcessError):
        return [path for path in root.rglob("*") if path.is_file() and not is_ignored_area(path.relative_to(root))]
    return [root / rel for rel in result.stdout.splitlines() if rel.strip()]


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--repo-root", default=".", help="Structure Factory repo root")
    parser.add_argument("--json", action="store_true", help="Emit JSON summary")
    args = parser.parse_args()

    root = Path(args.repo_root).resolve()
    missing = [rel for rel in REQUIRED_PATHS if not (root / rel).exists()]
    forbidden = []

    for path in candidate_paths(root):
        rel = path.relative_to(root)
        if is_ignored_area(rel) or not path.is_file():
            continue
        name = path.name
        if any(fnmatch.fnmatch(name, pattern) for pattern in FORBIDDEN_PATTERNS):
            forbidden.append(str(rel))

    ok = not missing and not forbidden
    summary = {
        "ok": ok,
        "repo_root": str(root),
        "missing_required_paths": missing,
        "forbidden_tracked_candidate_files": forbidden,
    }

    if args.json:
        print(json.dumps(summary, indent=2, sort_keys=True))
    else:
        print(f"ok: {ok}")
        if missing:
            print("missing required paths:")
            for item in missing:
                print(f"  - {item}")
        if forbidden:
            print("forbidden file candidates:")
            for item in forbidden:
                print(f"  - {item}")

    return 0 if ok else 1


if __name__ == "__main__":
    raise SystemExit(main())
