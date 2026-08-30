#!/usr/bin/env python3
"""Validate a local Structure Factory campaign DAG and import plan.

This checker is intentionally local-only. It reads JSON and Markdown files,
but it does not call Linear, providers, registries, or network services.
"""

from __future__ import annotations

import argparse
import json
import re
from pathlib import Path
from typing import Any


VALID_STATES = {"Todo", "Backlog", "Blocked", "In Review"}
VALID_OPERATOR_GATE = {"yes", "no"}
VALID_COMPLEXITY = {"small", "medium", "large"}
SECRET_PATTERNS = (
    re.compile(r"RUNPOD_API_KEY", re.IGNORECASE),
    re.compile(r"HUGGINGFACE_TOKEN", re.IGNORECASE),
    re.compile(r"\bhf_[A-Za-z0-9]{20,}\b"),
    re.compile(r"\bghp_[A-Za-z0-9]{20,}\b"),
    re.compile(r"\bsk-[A-Za-z0-9]{20,}\b"),
)


def load_json(path: Path) -> dict[str, Any]:
    return json.loads(path.read_text())


def path_texts(paths: list[Path]) -> list[tuple[str, str]]:
    texts: list[tuple[str, str]] = []
    for path in paths:
        if path.exists() and path.is_file():
            texts.append((str(path), path.read_text(errors="replace")))
    return texts


def issue_filename(issue: dict[str, Any]) -> str:
    if issue.get("file"):
        return str(issue["file"])
    safe = re.sub(r"[^A-Za-z0-9]+", "-", issue["issue_id"].upper()).strip("-")
    return f"{safe}.md"


def validate_dag(dag: dict[str, Any]) -> tuple[list[str], list[str]]:
    errors: list[str] = []
    warnings: list[str] = []
    for key in ["campaign_id", "routing_label", "issues"]:
        if key not in dag:
            errors.append(f"missing top-level field: {key}")
    if dag.get("routing_label") != "sym:structure-factory":
        errors.append("routing_label must be sym:structure-factory")
    if not isinstance(dag.get("issues"), list) or not dag.get("issues"):
        errors.append("issues must be a non-empty list")
        return errors, warnings

    issue_ids: set[str] = set()
    waves: set[str] = set()
    active_count = 0
    campaign_prefix = f"campaigns/{dag.get('campaign_id', '')}/"
    allowed_touched_prefixes = tuple(
        dag.get(
            "allowed_touched_prefixes",
            [
                campaign_prefix,
                "scripts/structure_factory/campaign_issue_broker.py",
                "scripts/structure_factory/linear_plan_check.py",
            ],
        )
    )

    for index, issue in enumerate(dag["issues"]):
        context = issue.get("issue_id", f"issues[{index}]")
        for key in [
            "issue_id",
            "wave",
            "title",
            "target_state",
            "summary",
            "inputs",
            "expected_artifacts",
            "provider",
            "execution_profile",
            "operator_gate_required",
            "acceptance_criteria",
            "validation_commands",
            "touched_areas",
        ]:
            if key not in issue:
                errors.append(f"{context}: missing field {key}")
        issue_id = issue.get("issue_id")
        wave = issue.get("wave")
        if issue_id in issue_ids:
            errors.append(f"duplicate issue_id: {issue_id}")
        if wave in waves:
            errors.append(f"duplicate wave: {wave}")
        if issue_id:
            issue_ids.add(issue_id)
        if wave:
            waves.add(wave)

        state = issue.get("target_state")
        if state not in VALID_STATES:
            errors.append(f"{context}: invalid target_state {state}")
        if state == "Todo":
            active_count += 1
        if issue.get("operator_gate_required") not in VALID_OPERATOR_GATE:
            errors.append(f"{context}: operator_gate_required must be yes or no")
        if issue.get("complexity", "medium") not in VALID_COMPLEXITY:
            errors.append(f"{context}: invalid complexity {issue.get('complexity')}")
        if issue.get("validation_commands") == []:
            errors.append(f"{context}: validation_commands must not be empty")
        if issue.get("acceptance_criteria") == []:
            errors.append(f"{context}: acceptance_criteria must not be empty")

        for area in issue.get("touched_areas", []):
            touched_path = area.get("path", "")
            if not touched_path.startswith(allowed_touched_prefixes):
                errors.append(f"{context}: touched area outside declared ownership: {touched_path}")

    for issue in dag["issues"]:
        for dependency in issue.get("dependencies", []):
            if dependency not in issue_ids:
                errors.append(f"{issue['issue_id']}: unknown dependency {dependency}")

    first_active_limit = dag.get("dispatch", {}).get("first_active_limit", 1)
    if active_count > first_active_limit:
        errors.append(f"too many Todo issues: {active_count} > {first_active_limit}")
    if active_count == 0:
        warnings.append("no Todo issue declared")

    return errors, warnings


def validate_generated(
    dag: dict[str, Any],
    issues_dir: Path | None,
    import_plan_path: Path | None,
) -> tuple[list[str], list[str], list[str]]:
    errors: list[str] = []
    warnings: list[str] = []
    checked_files: list[str] = []

    if issues_dir:
        for issue in dag["issues"]:
            issue_path = issues_dir / issue_filename(issue)
            checked_files.append(str(issue_path))
            if not issue_path.exists():
                errors.append(f"missing generated issue file: {issue_path}")
                continue
            text = issue_path.read_text(errors="replace")
            if issue["issue_id"] not in text:
                warnings.append(f"{issue_path}: issue_id not present verbatim in body")
            if dag["campaign_id"] not in text:
                errors.append(f"{issue_path}: campaign_id missing")
            if dag["routing_label"] not in text:
                errors.append(f"{issue_path}: routing_label missing")
            if "<!-- symphony:schema" not in text:
                errors.append(f"{issue_path}: missing symphony schema block")

    if import_plan_path:
        checked_files.append(str(import_plan_path))
        if not import_plan_path.exists():
            errors.append(f"missing import plan: {import_plan_path}")
        else:
            plan = load_json(import_plan_path)
            if plan.get("campaign_id") != dag.get("campaign_id"):
                errors.append("import plan campaign_id does not match DAG")
            if plan.get("linear_mutation_authorized") is not False:
                errors.append("import plan must set linear_mutation_authorized false")
            if plan.get("provider_mutation_authorized") is not False:
                errors.append("import plan must set provider_mutation_authorized false")
            planned = {item.get("issue_id") for item in plan.get("issues", [])}
            expected = {item.get("issue_id") for item in dag.get("issues", [])}
            if planned != expected:
                errors.append("import plan issue_id set does not match DAG")

    texts = [(str(Path("<dag-json>")), json.dumps(dag))]
    generated_paths: list[Path] = []
    if issues_dir:
        generated_paths.extend((issues_dir / issue_filename(issue)) for issue in dag["issues"])
    if import_plan_path:
        generated_paths.append(import_plan_path)
    texts.extend(path_texts(generated_paths))
    for source, text in texts:
        for pattern in SECRET_PATTERNS:
            if pattern.search(text):
                errors.append(f"{source}: contains secret-like marker matching {pattern.pattern}")

    return errors, warnings, checked_files


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("dag", type=Path, help="Path to campaign issue-dag.json")
    parser.add_argument("--issues-dir", type=Path, help="Generated issue Markdown directory to check")
    parser.add_argument("--import-plan", type=Path, help="Generated import plan JSON to check")
    parser.add_argument("--json", action="store_true", help="Print JSON summary")
    args = parser.parse_args()

    dag = load_json(args.dag)
    errors, warnings = validate_dag(dag)
    generated_errors, generated_warnings, checked_files = validate_generated(
        dag,
        args.issues_dir,
        args.import_plan,
    )
    errors.extend(generated_errors)
    warnings.extend(generated_warnings)

    summary = {
        "ok": not errors,
        "dag": str(args.dag),
        "campaign_id": dag.get("campaign_id"),
        "issue_count": len(dag.get("issues", [])),
        "checked_files": checked_files,
        "errors": errors,
        "warnings": warnings,
    }
    if args.json:
        print(json.dumps(summary, indent=2))
    else:
        print(json.dumps(summary, indent=2))
    return 0 if not errors else 1


if __name__ == "__main__":
    raise SystemExit(main())
