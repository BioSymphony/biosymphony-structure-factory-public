#!/usr/bin/env python3
"""Run the read-only public binder-lane source and contract checks."""

from __future__ import annotations

import argparse
import ast
import json
import sys
from pathlib import Path


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--repo-root", type=Path, default=Path("."))
    parser.add_argument("--json", action="store_true")
    args = parser.parse_args()

    root = args.repo_root.resolve()
    sys.path.insert(0, str(root / "src"))
    from biosymphony_structure_factory import binder_executor, binder_lane

    findings: list[str] = []
    ledger_path = root / "references" / "binder-lane-capability-ledger.json"
    request_path = root / "examples" / "pd-l1-binder-design-public" / "binder-round-request.json"
    fixture_path = root / "examples" / "pd-l1-binder-design-public" / "candidate-ranking.example.json"
    execution_registry_path = root / "references" / "binder-execution-adapters.json"
    schema_paths = [
        root / "schemas" / "binder-api-adapter-contract.schema.json",
        root / "schemas" / "binder-round-request.schema.json",
        root / "schemas" / "binder-capability-ledger.schema.json",
        root / "schemas" / "binder-round-plan.schema.json",
        root / "schemas" / "binder-round-decision.schema.json",
        root / "schemas" / "binder-round-report.schema.json",
        root / "schemas" / "binder-execution-adapters.schema.json",
        root / "modules" / "schemas" / "binder-round-contract.v1.schema.json",
        root / "modules" / "schemas" / "binder-execution-handoff.v1.schema.json",
    ]

    try:
        ledger = binder_lane.read_json(ledger_path)
        request = binder_lane.read_json(request_path)
        fixture = binder_lane.read_json(fixture_path)
        execution_registry = binder_lane.read_json(execution_registry_path)
        binder_lane.validate_ledger(ledger, root)
        binder_executor.validate_registry(execution_registry)
        plan = binder_lane.plan_request(
            request,
            ledger,
            root,
            request_ref=request_path.relative_to(root).as_posix(),
            ledger_ref=ledger_path.relative_to(root).as_posix(),
        )
        binder_lane.validate_plan(plan, root)
        plan_hash = binder_lane.sha256_json(plan)
        contract = binder_lane.round_contract(plan, plan_hash)
        handoff = binder_lane.execution_handoff(plan, plan_hash)
        decision = binder_lane.round_decision(
            plan,
            [
                {
                    "round_index": 1,
                    "primary_metric_value": 0.5,
                    "actual_spend_usd": 60,
                    "closeout_complete": True,
                    "metric_provenance": {
                        "metric_id": "cofold_confidence_proxy",
                        "metric_source": "synthetic_fixture",
                        "source_artifact_sha256": None,
                        "calibration_state": "not_applicable",
                        "calibration_scope_id": "synthetic-demo",
                        "calibration_artifact_sha256": None,
                    },
                }
            ],
        )
        binder_lane.validate_round_contract(contract, plan)
        binder_lane.validate_execution_handoff(handoff, plan)
        candidates = binder_lane._synthetic_candidates(fixture)
        expected_candidate_count = sum(arm["candidate_count"] for arm in plan["toolchains"])
        if len(candidates) != expected_candidate_count:
            findings.append("synthetic fixture count differs from the plan")
        if plan["execution"] != {
            "mode": "public_synthetic_only",
            "provider_calls": 0,
            "adapter_execution_supported": True,
            "adapter_execution_authorization": "explicit_runtime_authorization_required",
            "handoff_generation_supported": True,
        }:
            findings.append("plan execution boundary changed")
        if contract.get("provider_calls") != 0 or contract.get("execution_mode") != "public_synthetic_only":
            findings.append("round contract execution boundary changed")
        roles = {role for tool in ledger["tools"] for role in tool["roles"]}
        missing_roles = set(binder_lane.ROUND_ROLES) - roles
        if missing_roles:
            findings.append("capability ledger is missing round roles: " + ", ".join(sorted(missing_roles)))
        try:
            from jsonschema import Draft202012Validator
        except ImportError:
            Draft202012Validator = None
        if Draft202012Validator is not None:
            counts = {arm["id"]: arm["candidate_count"] for arm in plan["toolchains"]}
            report = binder_lane._synthetic_report(plan, candidates, counts)
            adapter = binder_lane.read_json(root / "templates" / "binder-api-adapter-contract.json")
            instances = {
                "binder-api-adapter-contract.schema.json": adapter,
                "binder-capability-ledger.schema.json": ledger,
                "binder-round-request.schema.json": request,
                "binder-round-plan.schema.json": plan,
                "binder-round-decision.schema.json": decision,
                "binder-round-report.schema.json": report,
                "binder-execution-adapters.schema.json": execution_registry,
                "binder-round-contract.v1.schema.json": contract,
                "binder-execution-handoff.v1.schema.json": handoff,
            }
            for schema_path in schema_paths:
                try:
                    schema = json.loads(schema_path.read_text(encoding="utf-8"))
                    Draft202012Validator.check_schema(schema)
                    Draft202012Validator(schema).validate(instances[schema_path.name])
                except Exception:
                    findings.append(f"JSON Schema validation failed: {schema_path.name}")
    except (binder_lane.BinderLaneError, OSError, KeyError, TypeError) as exc:
        findings.append(str(exc))

    for path in schema_paths:
        try:
            schema = json.loads(path.read_text(encoding="utf-8"))
        except (OSError, json.JSONDecodeError) as exc:
            findings.append(f"invalid or missing schema {path.name}: {exc}")
            continue
        if schema.get("additionalProperties") is not False:
            findings.append(f"schema must fail closed on unknown top-level fields: {path.name}")

    source_path = root / "src" / "biosymphony_structure_factory" / "binder_lane.py"
    try:
        tree = ast.parse(source_path.read_text(encoding="utf-8"))
        imported = {
            alias.name.split(".")[0]
            for node in ast.walk(tree)
            if isinstance(node, ast.Import)
            for alias in node.names
        }
        imported.update(
            node.module.split(".")[0]
            for node in ast.walk(tree)
            if isinstance(node, ast.ImportFrom) and node.module
        )
        forbidden_imports = imported.intersection({"boto3", "fal", "httpx", "requests", "socket", "subprocess", "urllib"})
        if forbidden_imports:
            findings.append("binder lane imports external execution modules: " + ", ".join(sorted(forbidden_imports)))
    except (OSError, SyntaxError) as exc:
        findings.append(f"cannot inspect binder lane source: {exc}")

    result = {
        "ok": not findings,
        "check": "public-binder-lane",
        "provider_calls": 0,
        "findings": findings,
    }
    if args.json:
        print(json.dumps(result, indent=2, sort_keys=True))
    else:
        print("public binder lane: " + ("ok" if result["ok"] else "blocked"))
        for finding in findings:
            print(f"- {finding}")
    return 0 if result["ok"] else 1


if __name__ == "__main__":
    raise SystemExit(main())
