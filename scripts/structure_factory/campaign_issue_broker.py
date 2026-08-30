#!/usr/bin/env python3
"""Generate local Structure Factory Linear issue drafts from a campaign DAG.

The broker writes Markdown and a local import plan only. It does not call
Linear, providers, registries, or any external service.
"""

from __future__ import annotations

import argparse
import json
import re
from pathlib import Path
from typing import Any


REPO_ROOT = Path(__file__).resolve().parents[2]


def compact_ws(value: str) -> str:
    return " ".join(str(value).split())


def inline(value: Any) -> str:
    return compact_ws(str(value)).replace("`", "'")


def slugify(value: str) -> str:
    slug = re.sub(r"[^A-Za-z0-9]+", "-", value.upper()).strip("-")
    return slug or "ISSUE"


def relpath(path: Path) -> str:
    try:
        return str(path.resolve().relative_to(REPO_ROOT))
    except ValueError:
        return str(path)


def list_pairs(items: list[dict[str, Any]], name_key: str, value_key: str) -> str:
    lines: list[str] = []
    for item in items:
        lines.append(f"- `{inline(item[name_key])}` - {inline(item[value_key])}")
    return "\n".join(lines)


def bullet_checklist(items: list[str]) -> str:
    return "\n".join(f"- [ ] {inline(item)}" for item in items)


def command_block(commands: list[str]) -> str:
    body = "\n".join(commands)
    return f"```bash\n{body}\n```"


def schema_block(campaign_id: str, routing_label: str, issue: dict[str, Any]) -> str:
    touched = "\n".join(f"  - {inline(item['path'])}" for item in issue["touched_areas"])
    return (
        "<!-- symphony:schema\n"
        "schema_version: 1\n"
        "subgroup: structure-factory\n"
        f"routing_label: {routing_label}\n"
        f"campaign_id: {campaign_id}\n"
        f"wave: {inline(issue['wave'])}\n"
        f"target_state: {inline(issue['target_state'])}\n"
        "touched_areas:\n"
        f"{touched}\n"
        f"complexity: {inline(issue.get('complexity', 'medium'))}\n"
        "-->"
    )


def render_issue(dag: dict[str, Any], issue: dict[str, Any]) -> str:
    campaign_id = dag["campaign_id"]
    routing_label = dag["routing_label"]
    title = inline(issue["title"])
    risk_notes = list(issue.get("risk_notes", [])) + list(dag.get("common_risk_notes", []))
    touched = "\n".join(
        f"- `{inline(item['path'])}` - {inline(item['why'])}"
        for item in issue["touched_areas"]
    )
    dependencies = issue.get("dependencies", [])
    dependency_text = "none" if not dependencies else ", ".join(inline(dep) for dep in dependencies)
    labels = ", ".join([routing_label, *issue.get("labels", [])])

    return (
        f"## Summary\n\n"
        f"{inline(issue['summary'])}\n\n"
        f"Local issue id: `{inline(issue['issue_id'])}`\n\n"
        f"Dispatch title: `{title}`\n\n"
        f"Target Linear state: `{inline(issue['target_state'])}`\n\n"
        f"Routing labels: `{labels}`\n\n"
        f"## Inputs\n\n"
        f"{list_pairs(issue['inputs'], 'id', 'value')}\n\n"
        f"## Expected Artifacts\n\n"
        f"{list_pairs(issue['expected_artifacts'], 'id', 'value')}\n\n"
        f"## Stage / Progress Contract\n\n"
        f"- stage contract: `{inline(issue['stage_contract'])}`\n"
        f"- artifact granularity: `{inline(issue['artifact_granularity'])}`\n"
        f"- progress ledger: `{inline(issue['progress_ledger'])}`\n"
        f"- resume command: `{inline(issue['resume_command'])}`\n"
        f"- partial success policy: `{inline(issue['partial_success_policy'])}`\n\n"
        f"## Provider / Execution Profile\n\n"
        f"- provider: `{inline(issue['provider'])}`\n"
        f"- execution profile: `{inline(issue['execution_profile'])}`\n"
        f"- setup posture: `{inline(issue['setup_posture'])}`\n"
        f"- writable volume/env: `{inline(issue['writable_volume_env'])}`\n"
        f"- operator gate required: `{inline(issue['operator_gate_required'])}`\n\n"
        f"## Tooling / License Posture\n\n"
        f"- tools: `{inline(issue['tools'])}`\n"
        f"- posture: `{inline(issue['posture'])}`\n"
        f"- current primary source checked: `{inline(issue['current_primary_source_checked'])}`\n"
        f"- intended use context: `{inline(issue['intended_use_context'])}`\n"
        f"- image/runtime action: `{inline(issue['image_runtime_action'])}`\n"
        f"- operator action required: `{inline(issue['operator_action_required'])}`\n\n"
        f"## Acceptance Criteria\n\n"
        f"{bullet_checklist(issue['acceptance_criteria'])}\n\n"
        f"## Validation Commands\n\n"
        f"{command_block(issue['validation_commands'])}\n\n"
        f"## Final Outcome Contract\n\n"
        f"- worker lane: `{inline(issue['worker_lane'])}`\n"
        f"- closeout state: `{inline(issue['closeout_state'])}`\n"
        f"- final comment must include: `<!-- symphony-outcome -->`\n"
        f"- success requires: `{inline(issue['success_requires'])}`\n\n"
        f"## Touched Areas\n\n"
        f"{touched}\n\n"
        f"## Dependencies\n\n"
        f"Blocked by: {dependency_text}\n\n"
        f"## Risk Notes\n\n"
        f"{chr(10).join(f'- {inline(note)}' for note in risk_notes)}\n\n"
        f"## Complexity\n\n"
        f"tier: {inline(issue.get('complexity', 'medium'))}\n\n"
        f"{schema_block(campaign_id, routing_label, issue)}\n"
    )


def issue_filename(issue: dict[str, Any]) -> str:
    if issue.get("file"):
        return str(issue["file"])
    return f"{slugify(issue['issue_id'])}.md"


def import_plan(dag: dict[str, Any], issues_dir: Path) -> dict[str, Any]:
    issues: list[dict[str, Any]] = []
    for issue in dag["issues"]:
        issue_file = issues_dir / issue_filename(issue)
        issues.append(
            {
                "issue_id": issue["issue_id"],
                "wave": issue["wave"],
                "title": issue["title"],
                "target_state": issue["target_state"],
                "labels": [dag["routing_label"], *issue.get("labels", [])],
                "dependencies": issue.get("dependencies", []),
                "markdown_file": relpath(issue_file),
                "linear_mutation_authorized": False,
            }
        )
    return {
        "plan_version": 1,
        "campaign_id": dag["campaign_id"],
        "routing_label": dag["routing_label"],
        "mutation_mode": "no-paid-local-only",
        "linear_mutation_authorized": False,
        "provider_mutation_authorized": False,
        "instructions": [
            "Review generated Markdown locally before manual Linear import.",
            "Do not create or update Linear issues from this plan without explicit operator authorization.",
            "Keep only the declared first wave active; leave dependent and gated waves in Backlog or Blocked.",
        ],
        "issues": issues,
    }


def load_dag(path: Path) -> dict[str, Any]:
    return json.loads(path.read_text())


def write_text(path: Path, text: str, force: bool) -> bool:
    if path.exists() and not force:
        raise FileExistsError(f"{path} exists; pass --force to overwrite generated output")
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(text)
    return True


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("dag", type=Path, help="Path to campaign issue-dag.json")
    parser.add_argument("--out-dir", type=Path, help="Directory for generated issue Markdown")
    parser.add_argument("--import-plan", type=Path, help="Path for generated local import plan JSON")
    parser.add_argument("--force", action="store_true", help="Overwrite generated files")
    parser.add_argument("--json", action="store_true", help="Print JSON summary")
    args = parser.parse_args()

    dag_path = args.dag.resolve()
    dag = load_dag(dag_path)
    campaign_dir = dag_path.parent
    issues_dir = args.out_dir or campaign_dir / dag.get("linear_issue_dir", "linear-issues")
    import_plan_path = args.import_plan or campaign_dir / dag.get("import_plan_path", "linear-import-plan.json")

    written: list[str] = []
    for issue in dag["issues"]:
        issue_path = issues_dir / issue_filename(issue)
        write_text(issue_path, render_issue(dag, issue), args.force)
        written.append(relpath(issue_path))

    plan = import_plan(dag, issues_dir)
    write_text(import_plan_path, json.dumps(plan, indent=2) + "\n", args.force)
    written.append(relpath(import_plan_path))

    summary = {
        "campaign_id": dag["campaign_id"],
        "issue_count": len(dag["issues"]),
        "issues_dir": relpath(issues_dir),
        "import_plan": relpath(import_plan_path),
        "written": written,
        "linear_mutation_authorized": False,
        "provider_mutation_authorized": False,
    }
    if args.json:
        print(json.dumps(summary, indent=2))
    else:
        print(f"generated {summary['issue_count']} issue drafts under {summary['issues_dir']}")
        print(f"wrote import plan {summary['import_plan']}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
