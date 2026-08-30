#!/usr/bin/env python3
"""Validate the lightweight Structure Factory software registry.

This intentionally avoids third-party YAML dependencies. It checks the simple
registry shape used by references/software-registry.yaml.
"""

from __future__ import annotations

import argparse
import json
import re
from pathlib import Path


REQUIRED_FIELDS = {
    "role",
    "image_family",
    "install_method",
    "license_class",
    "license_gate",
    "runpod_fit",
    "gpu_class",
    "smoke_command",
    "runtime_artifacts",
    "citation_notes",
    "status",
    "notes",
}


def parse_registry(path: Path) -> dict[str, set[str]]:
    entries: dict[str, set[str]] = {}
    current: str | None = None

    for raw_line in path.read_text().splitlines():
        line = raw_line.rstrip()
        if not line or line.lstrip().startswith("#") or line == "software:":
            continue

        entry_match = re.match(r"^  ([a-zA-Z0-9][a-zA-Z0-9_-]*):\s*$", line)
        if entry_match:
            current = entry_match.group(1)
            entries[current] = set()
            continue

        field_match = re.match(r"^    ([a-zA-Z0-9_]+):\s*(.*)$", line)
        if field_match and current:
            entries[current].add(field_match.group(1))

    return entries


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("registry", type=Path)
    parser.add_argument("--json", action="store_true")
    args = parser.parse_args()

    entries = parse_registry(args.registry)
    missing = {
        name: sorted(REQUIRED_FIELDS - fields)
        for name, fields in entries.items()
        if REQUIRED_FIELDS - fields
    }
    ok = bool(entries) and not missing

    summary = {
        "ok": ok,
        "registry": str(args.registry.resolve()),
        "entry_count": len(entries),
        "entry_ids": sorted(entries),
        "missing_fields": missing,
    }

    if args.json:
        print(json.dumps(summary, indent=2, sort_keys=True))
    else:
        print(f"ok: {ok}")
        print(f"entry_count: {len(entries)}")
        if missing:
            print("missing fields:")
            for name, fields in missing.items():
                print(f"  - {name}: {', '.join(fields)}")

    return 0 if ok else 1


if __name__ == "__main__":
    raise SystemExit(main())
