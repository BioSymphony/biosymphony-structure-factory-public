#!/usr/bin/env python3
"""Validate a Structure Factory Linear issue draft."""

from __future__ import annotations

import argparse
import json
import re
from pathlib import Path


REQUIRED_HEADINGS = [
    "## Summary",
    "## Inputs",
    "## Expected Artifacts",
    "## Provider / Execution Profile",
    "## Acceptance Criteria",
    "## Validation Commands",
    "## Touched Areas",
    "## Dependencies",
    "## Risk Notes",
    "## Complexity",
]

VALID_COMPLEXITY = {"small", "medium", "large"}
VALID_TARGET_STATES = {"Todo", "Backlog", "In Review", "Blocked"}
VALID_PROVIDERS = {"runpod", "local", "ssh-hpc", "generic-cloud", "neocloud", "aws", "provider-neutral"}
VALID_EXECUTION_PROFILES = {
    "no-download-smoke",
    "raw-subset-open",
    "raw-subset-gated",
    "map-model-report",
    # Screening Superpowers profiles
    "screening-no-download-smoke",
    "screening-wide-docking",
    "screening-focused-cofolding",
    "screening-gated-ml-docking",
    "protein-rna-fit",
    # AI design lane profiles (Boltz + Genie 3)
    "genie3-no-download-toolcheck",
    "genie3-public-design-canary",
    "genie3-boltz-design-ranking",
    "other",
}
VALID_ROUTING_LABELS = {
    "sym:structure-factory",
}
VALID_TOOL_POSTURES = {"open-default", "review-required", "runtime-gated", "internal-only", "mixed"}
REPO_REFERENCE_PREFIXES = (
    "AGENTS.md",
    "Makefile",
    "README.md",
    "campaigns/",
    "containers/",
    "docs/",
    "examples/",
    "internal/templates/",
    "modules/",
    "references/",
    "runpod/",
    "scripts/",
    "templates/",
    "tests/",
)
VALIDATION_REFERENCE_PREFIXES = (
    "campaigns/",
    "containers/",
    "docs/",
    "examples/",
    "internal/templates/",
    "modules/",
    "references/",
    "runpod/bridge-manifests/",
    "runpod/launch-manifests/",
    "runpod/stage-contracts/",
    "scripts/",
    "templates/",
    "tests/",
)
RUNTIME_REFERENCE_PREFIXES = (
    ".runtime/",
    "artifacts/",
    "outputs/",
    "runpod-execution/",
    "scratch/",
)


def markdown_sections(text: str) -> dict[str, str]:
    sections: dict[str, list[str]] = {}
    current_heading: str | None = None
    current_lines: list[str] = []
    for line in text.splitlines():
        if line.startswith("## "):
            if current_heading is not None:
                sections[current_heading] = current_lines
            current_heading = line.strip()
            current_lines = []
        elif current_heading is not None:
            current_lines.append(line)
    if current_heading is not None:
        sections[current_heading] = current_lines
    return {heading: "\n".join(lines) for heading, lines in sections.items()}


def normalize_reference(raw: str) -> str | None:
    ref = raw.strip().strip("`'\"")
    ref = ref.rstrip(".,;:)")
    if " " in ref or not ref:
        return None
    if ref in {"n/a", "none"}:
        return None
    if ref.startswith(("http://", "https://", "s3://", "gs://")):
        return None
    if ref.startswith(("/", "~")):
        return None
    if "$" in ref or "{" in ref or "}" in ref or "<" in ref or ">" in ref:
        return None
    if ref.startswith(RUNTIME_REFERENCE_PREFIXES):
        return None
    if ref.startswith("./"):
        ref = ref[2:]
    return ref


def is_repo_reference(ref: str, prefixes: tuple[str, ...] = REPO_REFERENCE_PREFIXES) -> bool:
    return any(ref == prefix.rstrip("/") or ref.startswith(prefix) for prefix in prefixes)


def references_from_code_spans(text: str, prefixes: tuple[str, ...]) -> set[str]:
    refs: set[str] = set()
    for match in re.finditer(r"`([^`]+)`", text):
        ref = normalize_reference(match.group(1))
        if ref and is_repo_reference(ref, prefixes):
            refs.add(ref)
    return refs


def touched_area_references(text: str) -> set[str]:
    refs = references_from_code_spans(text, REPO_REFERENCE_PREFIXES)
    for line in text.splitlines():
        stripped = line.strip()
        if not stripped.startswith("-"):
            continue
        candidate = stripped[1:].strip()
        candidate = candidate.split(" - ", 1)[0].strip()
        ref = normalize_reference(candidate)
        if ref and is_repo_reference(ref):
            refs.add(ref)
    return refs


def schema_touched_area_references(text: str) -> set[str]:
    refs: set[str] = set()
    in_touched_areas = False
    in_schema = False
    for line in text.splitlines():
        stripped = line.strip()
        if stripped.startswith("<!-- symphony:schema"):
            in_schema = True
            continue
        if in_schema and stripped.startswith("-->"):
            break
        if not in_schema:
            continue
        if stripped == "touched_areas:":
            in_touched_areas = True
            continue
        if in_touched_areas:
            if not stripped.startswith("-"):
                if stripped and not line.startswith((" ", "\t")):
                    in_touched_areas = False
                continue
            ref = normalize_reference(stripped[1:].strip())
            if ref and is_repo_reference(ref):
                refs.add(ref)
    return refs


def stage_contract_references(text: str) -> set[str]:
    refs: set[str] = set()
    for match in re.finditer(r"^- stage contract:\s*`([^`]+)`\s*$", text, re.MULTILINE):
        ref = normalize_reference(match.group(1))
        if ref and is_repo_reference(ref):
            refs.add(ref)
    return refs


def validation_command_references(text: str) -> set[str]:
    refs: set[str] = references_from_code_spans(text, VALIDATION_REFERENCE_PREFIXES)
    token_pattern = re.compile(r"(?<![A-Za-z0-9_./-])([A-Za-z0-9_./*-]+(?:/[A-Za-z0-9_./*-]+)+)")
    for line in text.splitlines():
        stripped = line.strip()
        if not stripped or stripped.startswith("#"):
            continue
        # Validation commands often assert future runtime outputs with test -f.
        # The file-reference gate checks repo-controlled command inputs instead.
        if stripped.startswith(("test ", "[ ")):
            continue
        for match in token_pattern.finditer(stripped):
            ref = normalize_reference(match.group(1))
            if ref and is_repo_reference(ref, VALIDATION_REFERENCE_PREFIXES):
                refs.add(ref)
    return refs


def issue_file_references(text: str) -> set[str]:
    sections = markdown_sections(text)
    refs: set[str] = set()
    refs.update(touched_area_references(sections.get("## Touched Areas", "")))
    refs.update(schema_touched_area_references(text))
    refs.update(stage_contract_references(sections.get("## Stage / Progress Contract", "")))
    refs.update(validation_command_references(sections.get("## Validation Commands", "")))
    return refs


def reference_exists(repo_root: Path, ref: str) -> bool:
    if any(char in ref for char in "*?["):
        return any(repo_root.glob(ref))
    return (repo_root / ref).exists()


def check_issue(path: Path, repo_root: Path | None = None, check_file_references: bool = False) -> dict:
    text = path.read_text()
    missing_headings = [heading for heading in REQUIRED_HEADINGS if heading not in text]
    has_schema = "<!-- symphony:schema" in text and "subgroup: structure-factory" in text
    has_validation_block = "```bash" in text
    has_touched_area = "## Touched Areas" in text and "- `" in text
    provider_match = re.search(r"^- provider:\s*`([^`]+)`\s*$", text, re.MULTILINE)
    execution_profile_match = re.search(r"^- execution profile:\s*`([^`]+)`\s*$", text, re.MULTILINE)
    posture_match = re.search(r"^- posture:\s*`([^`]+)`\s*$", text, re.MULTILINE)
    has_provider_line = provider_match is not None
    has_execution_profile_line = execution_profile_match is not None
    has_operator_gate_line = re.search(r"^- operator gate required:\s*`(yes|no)`\s*$", text, re.MULTILINE) is not None
    errors: list[str] = []
    warnings: list[str] = []
    if missing_headings:
        errors.extend(f"missing heading: {heading}" for heading in missing_headings)
    if not has_schema:
        errors.append("missing structure-factory symphony schema")
    if not has_validation_block:
        errors.append("missing bash validation block")
    if not has_touched_area:
        errors.append("missing touched area entry")
    if path.name != "linear-issue.md":
        if not has_provider_line:
            errors.append("missing provider line")
        elif provider_match and provider_match.group(1) not in VALID_PROVIDERS:
            errors.append(f"invalid provider: {provider_match.group(1)}")
        if not has_execution_profile_line:
            errors.append("missing execution profile line")
        elif execution_profile_match and execution_profile_match.group(1) not in VALID_EXECUTION_PROFILES:
            errors.append(f"invalid execution profile: {execution_profile_match.group(1)}")
        if not has_operator_gate_line:
            errors.append("missing operator gate required line")
    if path.name != "linear-issue.md":
        # Read the routing label from the symphony:schema block; fall back to default.
        routing_label_match = re.search(r"^routing_label:\s*([\w:.-]+)\s*$", text, re.MULTILINE)
        declared_label = routing_label_match.group(1) if routing_label_match else "sym:structure-factory"
        if declared_label not in VALID_ROUTING_LABELS:
            errors.append(f"unknown routing label declared in schema: {declared_label}")
        elif declared_label not in text:
            errors.append(f"declared routing label {declared_label} not present in issue body")
    if path.name != "linear-issue.md" and ("<exact command" in text or "<path>" in text or "<input id>" in text):
        errors.append("contains template placeholder")
    if "## Stage / Progress Contract" not in text:
        warnings.append("missing Stage / Progress Contract section")
    if "## Tooling / License Posture" not in text:
        warnings.append("missing Tooling / License Posture section")
    elif posture_match and posture_match.group(1) not in VALID_TOOL_POSTURES and path.name != "linear-issue.md":
        warnings.append(f"unknown tooling posture: {posture_match.group(1)}")
    if "## Final Outcome Contract" not in text:
        warnings.append("missing Final Outcome Contract section")
    if "<!-- symphony-outcome" not in text and "final comment must include: `<!-- symphony-outcome -->`" not in text:
        warnings.append("missing explicit symphony-outcome closeout instruction")

    checked_file_references: list[str] = []
    missing_file_references: list[str] = []
    if check_file_references:
        root = (repo_root or Path.cwd()).resolve()
        checked_file_references = sorted(issue_file_references(text))
        missing_file_references = [ref for ref in checked_file_references if not reference_exists(root, ref)]
        errors.extend(f"missing referenced repo path: {ref}" for ref in missing_file_references)

    complexity_match = re.search(r"^tier:\s*([A-Za-z_-]+)\s*$", text, re.MULTILINE)
    schema_complexity_match = re.search(r"^complexity:\s*([A-Za-z_-]+)\s*$", text, re.MULTILINE)
    for label, match in [("human complexity", complexity_match), ("schema complexity", schema_complexity_match)]:
        if not match:
            errors.append(f"missing {label}")
        elif match.group(1) not in VALID_COMPLEXITY:
            errors.append(f"invalid {label}: {match.group(1)}")

    target_state_match = re.search(r"^target_state:\s*([A-Za-z ]+)\s*$", text, re.MULTILINE)
    if target_state_match and target_state_match.group(1) not in VALID_TARGET_STATES:
        errors.append(f"invalid target_state: {target_state_match.group(1)}")

    ok = not errors
    return {
        "ok": ok,
        "issue": str(path.resolve()),
        "missing_headings": missing_headings,
        "errors": errors,
        "warnings": warnings,
        "file_references_checked": checked_file_references,
        "missing_file_references": missing_file_references,
        "has_structure_factory_schema": has_schema,
        "has_validation_bash_block": has_validation_block,
        "has_touched_area_entry": has_touched_area,
    }


def issue_paths(path: Path) -> list[Path]:
    if path.is_dir():
        return sorted(p for p in path.glob("*.md") if p.is_file())
    return [path]


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("issue", type=Path, help="Issue markdown file or directory of issue markdown files")
    parser.add_argument("--json", action="store_true")
    parser.add_argument(
        "--check-file-references",
        action="store_true",
        help="Fail if repo-controlled paths referenced by the issue do not exist",
    )
    parser.add_argument(
        "--repo-root",
        type=Path,
        default=Path("."),
        help="Repository root used by --check-file-references",
    )
    args = parser.parse_args()

    repo_root = args.repo_root.resolve()
    results = [
        check_issue(path, repo_root=repo_root, check_file_references=args.check_file_references)
        for path in issue_paths(args.issue)
    ]
    empty_file_reference_scan = args.check_file_references and args.issue.is_dir() and not results
    ok = empty_file_reference_scan or (bool(results) and all(result["ok"] for result in results))
    summary = {
        "ok": ok,
        "checked": len(results),
        "empty_file_reference_scan": empty_file_reference_scan,
        "file_reference_mode": args.check_file_references,
        "file_references_checked": sum(len(result.get("file_references_checked", [])) for result in results),
        "missing_file_references": [
            {"issue": result["issue"], "path": ref}
            for result in results
            for ref in result.get("missing_file_references", [])
        ],
        "failures": [result for result in results if not result["ok"]],
        "warnings": [
            {"issue": result["issue"], "warning": warning}
            for result in results
            for warning in result.get("warnings", [])
        ],
    }

    if args.json:
        print(json.dumps(summary, indent=2, sort_keys=True))
    else:
        print(f"ok: {ok}")
        print(f"checked: {len(results)}")
        for result in summary["failures"]:
            print(f"failed: {result['issue']}")
            for error in result["errors"]:
                print(f"  {error}")
        for result in results:
            for warning in result.get("warnings", []):
                print(f"warning: {result['issue']}: {warning}")

    return 0 if ok else 1


if __name__ == "__main__":
    raise SystemExit(main())
