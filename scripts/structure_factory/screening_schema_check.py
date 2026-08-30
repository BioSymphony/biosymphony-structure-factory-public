#!/usr/bin/env python3
"""Validate Structure Factory screening JSON contracts with stdlib only."""

from __future__ import annotations

import argparse
import json
import re
from pathlib import Path
from typing import Any


SCHEMA_FILES = {
    "active-learning": "active-learning.v1.schema.json",
    "active-learning-tranches": "active-learning-tranches.v1.schema.json",
    "affinity-record": "affinity-record.v1.schema.json",
    "artifact-pull-report": "artifact-pull-report.v1.schema.json",
    "artifact-index": "artifact-index.v1.schema.json",
    "benchmark": "benchmark.v1.schema.json",
    "benchmark-set": "benchmark-set.v1.schema.json",
    "calibration-summary": "calibration-summary.v1.schema.json",
    "candidate-report": "candidate-report.v1.schema.json",
    "validation-ledger": "validation-ledger.v1.schema.json",
    "cleanup-proof": "cleanup-proof.v1.schema.json",
    "cloud-shard-ledger": "cloud-shard-ledger.v1.schema.json",
    "cost-report": "cost-report.v1.schema.json",
    "design-tranche": "design-tranche.v1.schema.json",
    "evidence-graph": "evidence-graph.v1.schema.json",
    "ligand-library": "ligand-library.v1.schema.json",
    "method-adapter": "method-adapter.v1.schema.json",
    "pose-record": "pose-record.v1.schema.json",
    "protein-binder-design-manifest": "protein-binder-design-manifest.v1.schema.json",
    "protein-rna-fit-manifest": "protein-rna-fit-manifest.v1.schema.json",
    "provider-run": "provider-run.v1.schema.json",
    "receptor-ensemble": "receptor-ensemble.v1.schema.json",
    "receptor-state-registry": "receptor-state-registry.v1.schema.json",
    "screening-manifest": "screening-manifest.v1.schema.json",
    "screening-results": "screening-results.v1.schema.json",
    "scientific-memory": "scientific-memory.v1.schema.json",
    "shard-spec": "shard-spec.v1.schema.json",
    "stage-progress": "stage-progress.v1.schema.json",
}

DEFAULT_EXAMPLE_DIR = Path("examples/screening-superpowers")
DEFAULT_FIXTURE_ROOT = Path(".runtime/screening-superpowers-fixture")
DEFAULT_SCHEMA_DIR = Path("modules/schemas")
DEFAULT_ORCHESTRATION_FIXTURES_DIR = Path("examples/orchestration-fixtures")


def load_json(path: Path) -> Any:
    return json.loads(path.read_text())


def json_type_name(value: Any) -> str:
    if value is None:
        return "null"
    if isinstance(value, bool):
        return "boolean"
    if isinstance(value, dict):
        return "object"
    if isinstance(value, list):
        return "array"
    if isinstance(value, str):
        return "string"
    if isinstance(value, int):
        return "integer"
    if isinstance(value, float):
        return "number"
    return type(value).__name__


def path_child(path: str, key: str | int) -> str:
    if isinstance(key, int):
        return f"{path}[{key}]"
    if re.match(r"^[A-Za-z_][A-Za-z0-9_]*$", key):
        return f"{path}.{key}"
    return f"{path}[{json.dumps(key)}]"


def expected_type_label(expected: str | list[str]) -> str:
    if isinstance(expected, list):
        return " or ".join(expected)
    return expected


class JsonSchemaSubsetValidator:
    """Small JSON Schema validator for the schemas in modules/schemas.

    It intentionally supports only the keywords used by this repository's
    screening contracts. Unknown keywords are ignored, matching JSON Schema's
    extension behavior and keeping the checker dependency-free.
    """

    def __init__(self, schemas: dict[str, Any]):
        self.schemas = schemas

    def validate(self, instance: Any, schema: Any, path: str = "$") -> list[str]:
        if schema is True:
            return []
        if schema is False:
            return [f"{path}: schema is false"]
        if not isinstance(schema, dict):
            return [f"{path}: invalid schema node {json_type_name(schema)}"]

        if "$ref" in schema:
            resolved = self.resolve_ref(schema["$ref"])
            return self.validate(instance, resolved, path)

        errors: list[str] = []

        if "allOf" in schema:
            for index, subschema in enumerate(schema["allOf"]):
                errors.extend(self.validate(instance, subschema, f"{path} allOf[{index}]"))

        if "anyOf" in schema:
            any_errors = [self.validate(instance, subschema, path) for subschema in schema["anyOf"]]
            if not any(not branch_errors for branch_errors in any_errors):
                errors.append(f"{path}: does not match anyOf")

        if "oneOf" in schema:
            one_errors = [self.validate(instance, subschema, path) for subschema in schema["oneOf"]]
            matches = sum(1 for branch_errors in one_errors if not branch_errors)
            if matches != 1:
                errors.append(f"{path}: matches {matches} oneOf branches, expected exactly 1")

        if "const" in schema and instance != schema["const"]:
            errors.append(f"{path}: expected const {schema['const']!r}, got {instance!r}")

        if "enum" in schema and instance not in schema["enum"]:
            errors.append(f"{path}: expected one of {schema['enum']!r}, got {instance!r}")

        expected_type = schema.get("type")
        if expected_type is not None and not self.instance_matches_type(instance, expected_type):
            errors.append(
                f"{path}: expected type {expected_type_label(expected_type)}, got {json_type_name(instance)}"
            )
            return errors

        if isinstance(instance, dict):
            errors.extend(self.validate_object(instance, schema, path))
        elif isinstance(instance, list):
            errors.extend(self.validate_array(instance, schema, path))
        elif isinstance(instance, str):
            errors.extend(self.validate_string(instance, schema, path))

        if self.is_number(instance):
            errors.extend(self.validate_number(instance, schema, path))

        return errors

    def resolve_ref(self, ref: str) -> Any:
        if not ref.startswith("#/$defs/"):
            raise ValueError(f"unsupported $ref: {ref}")
        name = ref.split("/", 2)[2]
        defs = self.schemas.get("$current", {}).get("$defs", {})
        if name not in defs:
            raise ValueError(f"unknown $ref: {ref}")
        return defs[name]

    def instance_matches_type(self, instance: Any, expected: str | list[str]) -> bool:
        if isinstance(expected, list):
            return any(self.instance_matches_type(instance, item) for item in expected)
        if expected == "object":
            return isinstance(instance, dict)
        if expected == "array":
            return isinstance(instance, list)
        if expected == "string":
            return isinstance(instance, str)
        if expected == "boolean":
            return isinstance(instance, bool)
        if expected == "null":
            return instance is None
        if expected == "integer":
            return isinstance(instance, int) and not isinstance(instance, bool)
        if expected == "number":
            return self.is_number(instance)
        return True

    def is_number(self, instance: Any) -> bool:
        return isinstance(instance, (int, float)) and not isinstance(instance, bool)

    def validate_object(self, instance: dict[str, Any], schema: dict[str, Any], path: str) -> list[str]:
        errors: list[str] = []
        properties = schema.get("properties", {})
        for key in schema.get("required", []):
            if key not in instance:
                errors.append(f"{path}: missing required property {key!r}")

        if isinstance(properties, dict):
            for key, subschema in properties.items():
                if key in instance:
                    errors.extend(self.validate(instance[key], subschema, path_child(path, key)))

        additional = schema.get("additionalProperties", True)
        if additional is False and isinstance(properties, dict):
            for key in instance:
                if key not in properties:
                    errors.append(f"{path}: additional property {key!r} is not allowed")
        elif isinstance(additional, dict) and isinstance(properties, dict):
            for key, value in instance.items():
                if key not in properties:
                    errors.extend(self.validate(value, additional, path_child(path, key)))

        return errors

    def validate_array(self, instance: list[Any], schema: dict[str, Any], path: str) -> list[str]:
        errors: list[str] = []
        min_items = schema.get("minItems")
        max_items = schema.get("maxItems")
        if isinstance(min_items, int) and len(instance) < min_items:
            errors.append(f"{path}: expected at least {min_items} items, got {len(instance)}")
        if isinstance(max_items, int) and len(instance) > max_items:
            errors.append(f"{path}: expected at most {max_items} items, got {len(instance)}")
        if schema.get("uniqueItems") is True:
            seen: set[str] = set()
            for index, item in enumerate(instance):
                marker = json.dumps(item, sort_keys=True)
                if marker in seen:
                    errors.append(f"{path}[{index}]: duplicate array item")
                seen.add(marker)
        items = schema.get("items")
        if isinstance(items, dict) or isinstance(items, bool):
            for index, item in enumerate(instance):
                errors.extend(self.validate(item, items, path_child(path, index)))
        return errors

    def validate_string(self, instance: str, schema: dict[str, Any], path: str) -> list[str]:
        errors: list[str] = []
        min_length = schema.get("minLength")
        max_length = schema.get("maxLength")
        if isinstance(min_length, int) and len(instance) < min_length:
            errors.append(f"{path}: expected string length >= {min_length}, got {len(instance)}")
        if isinstance(max_length, int) and len(instance) > max_length:
            errors.append(f"{path}: expected string length <= {max_length}, got {len(instance)}")
        pattern = schema.get("pattern")
        if isinstance(pattern, str) and re.search(pattern, instance) is None:
            errors.append(f"{path}: string does not match pattern {pattern!r}")
        return errors

    def validate_number(self, instance: int | float, schema: dict[str, Any], path: str) -> list[str]:
        errors: list[str] = []
        minimum = schema.get("minimum")
        maximum = schema.get("maximum")
        if isinstance(minimum, (int, float)) and instance < minimum:
            errors.append(f"{path}: expected value >= {minimum}, got {instance}")
        if isinstance(maximum, (int, float)) and instance > maximum:
            errors.append(f"{path}: expected value <= {maximum}, got {instance}")
        return errors


def load_schemas(schema_dir: Path) -> tuple[dict[str, Any], list[str]]:
    schemas: dict[str, Any] = {}
    errors: list[str] = []
    for schema_name, filename in sorted(SCHEMA_FILES.items()):
        path = schema_dir / filename
        if not path.is_file():
            errors.append(f"missing schema file: {path}")
            continue
        try:
            schemas[schema_name] = load_json(path)
        except Exception as exc:
            errors.append(f"could not load schema {path}: {type(exc).__name__}: {exc}")
    return schemas, errors


def validate_json_file(
    validator: JsonSchemaSubsetValidator,
    schemas: dict[str, Any],
    schema_name: str,
    path: Path,
    label: str,
) -> dict[str, Any]:
    result = {
        "label": label,
        "path": str(path),
        "schema": schema_name,
        "format": "json",
        "ok": False,
        "errors": [],
    }
    schema = schemas.get(schema_name)
    if schema is None:
        result["errors"].append(f"unknown schema: {schema_name}")
        return result
    if not path.is_file():
        result["errors"].append(f"missing file: {path}")
        return result
    try:
        data = load_json(path)
    except Exception as exc:
        result["errors"].append(f"invalid json: {type(exc).__name__}: {exc}")
        return result
    result["errors"].extend(validator.validate(data, schema))
    if schema_name == "calibration-summary" and isinstance(data, dict):
        result["errors"].extend(validate_calibration_authority(data))
    result["ok"] = not result["errors"]
    return result


def validate_calibration_authority(data: dict[str, Any]) -> list[str]:
    """Keep borrowed, fixture-only, and unverified records out of ranking gates."""

    if data.get("ranking_authority") is not True:
        return []

    errors: list[str] = []
    if data.get("calibration_state") != "target_matched":
        errors.append(
            "$.ranking_authority: true requires calibration_state 'target_matched'"
        )
    if data.get("target_id") != data.get("source_target_id"):
        errors.append(
            "$.ranking_authority: true requires target_id to match source_target_id"
        )
    return errors


def validate_jsonl_file(
    validator: JsonSchemaSubsetValidator,
    schemas: dict[str, Any],
    schema_name: str,
    path: Path,
    label: str,
) -> dict[str, Any]:
    result = {
        "label": label,
        "path": str(path),
        "schema": schema_name,
        "format": "jsonl",
        "ok": False,
        "records": 0,
        "errors": [],
    }
    schema = schemas.get(schema_name)
    if schema is None:
        result["errors"].append(f"unknown schema: {schema_name}")
        return result
    if not path.is_file():
        result["errors"].append(f"missing file: {path}")
        return result

    for line_number, line in enumerate(path.read_text().splitlines(), start=1):
        if not line.strip():
            continue
        try:
            record = json.loads(line)
        except Exception as exc:
            result["errors"].append(f"line {line_number}: invalid json: {type(exc).__name__}: {exc}")
            continue
        result["records"] += 1
        for error in validator.validate(record, schema):
            result["errors"].append(f"line {line_number}: {error}")
    if result["records"] == 0:
        result["errors"].append("jsonl file has no records")
    result["ok"] = not result["errors"]
    return result


def default_jobs(
    example_dir: Path,
    fixture_root: Path,
    include_fixture: bool,
    orchestration_fixtures_dir: Path,
) -> tuple[list[dict[str, Any]], list[str]]:
    jobs: list[dict[str, Any]] = [
        {
            "path": example_dir / "screening-manifest.json",
            "schema": "screening-manifest",
            "format": "json",
            "label": "example screening manifest",
            "required": True,
        },
        {
            "path": example_dir / "ligand-library.json",
            "schema": "ligand-library",
            "format": "json",
            "label": "example ligand library",
            "required": True,
        },
        {
            "path": example_dir / "receptor-ensemble.json",
            "schema": "receptor-ensemble",
            "format": "json",
            "label": "example receptor ensemble",
            "required": True,
        },
        {
            "path": orchestration_fixtures_dir / "benchmark.json",
            "schema": "benchmark",
            "format": "json",
            "label": "orchestration fixture benchmark contract",
            "required": True,
        },
        {
            "path": orchestration_fixtures_dir / "benchmark-set.json",
            "schema": "benchmark-set",
            "format": "json",
            "label": "orchestration fixture benchmark set contract",
            "required": True,
        },
        {
            "path": orchestration_fixtures_dir / "method-adapter.json",
            "schema": "method-adapter",
            "format": "json",
            "label": "orchestration fixture method adapter registry",
            "required": True,
        },
        {
            "path": orchestration_fixtures_dir / "active-learning.json",
            "schema": "active-learning",
            "format": "json",
            "label": "orchestration fixture active learning plan",
            "required": True,
        },
        {
            "path": orchestration_fixtures_dir / "active-learning-tranches.json",
            "schema": "active-learning-tranches",
            "format": "json",
            "label": "orchestration fixture active learning tranches",
            "required": True,
        },
        {
            "path": orchestration_fixtures_dir / "design-tranche.json",
            "schema": "design-tranche",
            "format": "json",
            "label": "orchestration fixture design tranche",
            "required": True,
        },
        {
            "path": orchestration_fixtures_dir / "receptor-state-registry.json",
            "schema": "receptor-state-registry",
            "format": "json",
            "label": "orchestration fixture receptor state registry",
            "required": True,
        },
        {
            "path": orchestration_fixtures_dir / "calibration-summary.json",
            "schema": "calibration-summary",
            "format": "json",
            "label": "orchestration fixture calibration summary",
            "required": True,
        },
        {
            "path": orchestration_fixtures_dir / "cloud-shard-ledger.json",
            "schema": "cloud-shard-ledger",
            "format": "json",
            "label": "orchestration fixture cloud shard ledger",
            "required": True,
        },
        {
            "path": orchestration_fixtures_dir / "provider-run-fal-serverless.synthetic.json",
            "schema": "provider-run",
            "format": "json",
            "label": "orchestration fixture FAL serverless provider run",
            "required": True,
        },
        {
            "path": orchestration_fixtures_dir / "provider-run-modal-function.synthetic.json",
            "schema": "provider-run",
            "format": "json",
            "label": "orchestration fixture Modal function provider run",
            "required": True,
        },
        {
            "path": orchestration_fixtures_dir / "provider-run-lambda-cloud.synthetic.json",
            "schema": "provider-run",
            "format": "json",
            "label": "orchestration fixture Lambda Cloud provider run",
            "required": True,
        },
        {
            "path": orchestration_fixtures_dir / "evidence-graph.json",
            "schema": "evidence-graph",
            "format": "json",
            "label": "orchestration fixture evidence graph",
            "required": True,
        },
        {
            "path": orchestration_fixtures_dir / "artifact-index.json",
            "schema": "artifact-index",
            "format": "json",
            "label": "orchestration fixture artifact index",
            "required": True,
        },
        {
            "path": orchestration_fixtures_dir / "scientific-memory.json",
            "schema": "scientific-memory",
            "format": "json",
            "label": "orchestration fixture scientific memory",
            "required": True,
        },
        {
            "path": orchestration_fixtures_dir / "pd-l1-binder-design-manifest.json",
            "schema": "protein-binder-design-manifest",
            "format": "json",
            "label": "orchestration fixture protein binder design manifest",
            "required": True,
        },
    ]
    warnings: list[str] = []

    if not include_fixture:
        return jobs, warnings

    if not fixture_root.exists():
        warnings.append(f"fixture root does not exist, skipped fixture validation: {fixture_root}")
        return jobs, warnings

    fixture_candidates = [
        ("screening_manifest.json", "screening-manifest", "json", "fixture screening manifest"),
        ("receptor_ensemble_manifest.json", "receptor-ensemble", "json", "fixture receptor ensemble"),
        ("metrics.json", "screening-results", "json", "fixture screening results summary"),
        ("validation_ledger.json", "validation-ledger", "json", "fixture validation ledger"),
        ("stage-progress.jsonl", "stage-progress", "jsonl", "fixture stage progress"),
        ("provider_run.json", "provider-run", "json", "fixture provider run"),
        ("provider-run.json", "provider-run", "json", "fixture provider run"),
        ("shard_spec.json", "shard-spec", "json", "fixture shard spec"),
        ("shard-spec.json", "shard-spec", "json", "fixture shard spec"),
        ("cost_report.json", "cost-report", "json", "fixture cost report"),
        ("cost-report.json", "cost-report", "json", "fixture cost report"),
        ("artifact_pull_report.json", "artifact-pull-report", "json", "fixture artifact pull report"),
        ("artifact-pull-report.json", "artifact-pull-report", "json", "fixture artifact pull report"),
        ("validation/artifact-pull-report.json", "artifact-pull-report", "json", "fixture artifact pull report"),
        ("cleanup_proof.json", "cleanup-proof", "json", "fixture cleanup proof"),
        ("cleanup-proof.json", "cleanup-proof", "json", "fixture cleanup proof"),
        ("validation/cleanup-proof.json", "cleanup-proof", "json", "fixture cleanup proof"),
    ]
    for rel_path, schema_name, file_format, label in fixture_candidates:
        path = fixture_root / rel_path
        if path.exists():
            jobs.append({
                "path": path,
                "schema": schema_name,
                "format": file_format,
                "label": label,
                "required": False,
            })

    report_dir = fixture_root / "candidate_reports"
    if report_dir.is_dir():
        for path in sorted(report_dir.glob("*.json")):
            jobs.append({
                "path": path,
                "schema": "candidate-report",
                "format": "json",
                "label": "fixture candidate report",
                "required": False,
            })

    return jobs, warnings


def run_jobs(
    validator: JsonSchemaSubsetValidator,
    schemas: dict[str, Any],
    jobs: list[dict[str, Any]],
) -> list[dict[str, Any]]:
    results = []
    seen: set[tuple[str, str, str]] = set()
    for job in jobs:
        marker = (str(job["path"]), job["schema"], job["format"])
        if marker in seen:
            continue
        seen.add(marker)
        if job["format"] == "jsonl":
            results.append(
                validate_jsonl_file(validator, schemas, job["schema"], job["path"], job["label"])
            )
        else:
            results.append(
                validate_json_file(validator, schemas, job["schema"], job["path"], job["label"])
            )
    return results


def summarize(
    schema_dir: Path,
    schemas: dict[str, Any],
    schema_errors: list[str],
    results: list[dict[str, Any]],
    warnings: list[str],
) -> dict[str, Any]:
    errors = list(schema_errors)
    for result in results:
        for error in result["errors"]:
            errors.append(f"{result['path']} ({result['schema']}): {error}")
    return {
        "ok": not errors,
        "check_type": "screening_schema_check",
        "schema_dir": str(schema_dir),
        "schemas_loaded": sorted(schemas),
        "validated_files": len(results),
        "validated_records": sum(int(result.get("records", 0)) for result in results),
        "validations": results,
        "errors": errors,
        "warnings": warnings,
    }


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser()
    parser.add_argument("--schema-dir", type=Path, default=DEFAULT_SCHEMA_DIR)
    parser.add_argument("--example-dir", type=Path, default=DEFAULT_EXAMPLE_DIR)
    parser.add_argument(
        "--orchestration-fixtures-dir",
        dest="orchestration_fixtures_dir",
        type=Path,
        default=DEFAULT_ORCHESTRATION_FIXTURES_DIR,
    )
    parser.add_argument("--fixture-root", type=Path, default=DEFAULT_FIXTURE_ROOT)
    parser.add_argument("--no-fixture", action="store_true")
    parser.add_argument("--file", type=Path, action="append", default=[])
    parser.add_argument("--jsonl-file", type=Path, action="append", default=[])
    parser.add_argument("--schema", choices=sorted(SCHEMA_FILES))
    parser.add_argument("--out", type=Path)
    parser.add_argument("--json", action="store_true")
    return parser.parse_args()


def main() -> int:
    args = parse_args()
    schemas, schema_errors = load_schemas(args.schema_dir)
    validator = JsonSchemaSubsetValidator(schemas)

    warnings: list[str] = []
    if args.file or args.jsonl_file:
        if not args.schema:
            schema_errors.append("--schema is required when --file or --jsonl-file is used")
        jobs = [
            {
                "path": path,
                "schema": args.schema,
                "format": "json",
                "label": "explicit json file",
                "required": True,
            }
            for path in args.file
        ]
        jobs.extend(
            {
                "path": path,
                "schema": args.schema,
                "format": "jsonl",
                "label": "explicit jsonl file",
                "required": True,
            }
            for path in args.jsonl_file
        )
    else:
        jobs, warnings = default_jobs(
            args.example_dir,
            args.fixture_root,
            not args.no_fixture,
            args.orchestration_fixtures_dir,
        )

    results = run_jobs(validator, schemas, jobs) if not schema_errors else []
    summary = summarize(args.schema_dir, schemas, schema_errors, results, warnings)

    if args.out:
        args.out.parent.mkdir(parents=True, exist_ok=True)
        args.out.write_text(json.dumps(summary, indent=2, sort_keys=True) + "\n")
        summary["report_path"] = str(args.out.resolve())

    if args.json:
        print(json.dumps(summary, indent=2, sort_keys=True))
    else:
        print(f"ok: {summary['ok']}")
        print(f"schemas_loaded: {len(summary['schemas_loaded'])}")
        print(f"validated_files: {summary['validated_files']}")
        if summary["validated_records"]:
            print(f"validated_records: {summary['validated_records']}")
        for warning in summary["warnings"]:
            print(f"warning: {warning}")
        for error in summary["errors"]:
            print(f"error: {error}")

    return 0 if summary["ok"] else 1


if __name__ == "__main__":
    raise SystemExit(main())
