"""Build public-safe binder control indexes and calibration records."""

from __future__ import annotations

import copy
import hashlib
import math
import re
from typing import Any


PANEL_SCHEMA = "structure-factory-binder-control-panel-v1"
CALIBRATION_SCHEMA = "structure-factory-binder-control-calibration-v1"
ADOPTION_SCHEMA = "structure-factory-binder-control-adoption-v1"
SAFE_ID_RE = re.compile(r"^[a-z0-9][a-z0-9._-]{0,95}$")
SHA256_RE = re.compile(r"^[0-9a-f]{64}$")
DIRECTIONS = {"higher_is_better": ">=", "lower_is_better": "<="}
CONTROL_CLASSES = {"positive", "negative"}


class BinderControlError(ValueError):
    """A control record cannot support the requested calibration operation."""


def sha256_bytes(payload: bytes) -> str:
    """Return the SHA-256 digest of complete bytes."""
    return hashlib.sha256(payload).hexdigest()


def _exact_keys(value: dict[str, Any], expected: set[str], label: str) -> None:
    observed = set(value)
    if observed != expected:
        missing = sorted(expected - observed)
        extra = sorted(observed - expected)
        details: list[str] = []
        if missing:
            details.append("missing " + ", ".join(missing))
        if extra:
            details.append("unexpected " + ", ".join(extra))
        raise BinderControlError(f"{label} fields are invalid: {'; '.join(details)}")


def _safe_id(value: Any, label: str) -> str:
    if not isinstance(value, str) or SAFE_ID_RE.fullmatch(value) is None:
        raise BinderControlError(f"{label} must be a lowercase public-safe ID")
    return value


def _finite(value: Any, label: str) -> float:
    if isinstance(value, bool) or not isinstance(value, (int, float)):
        raise BinderControlError(f"{label} must be numeric")
    number = float(value)
    if not math.isfinite(number):
        raise BinderControlError(f"{label} must be finite")
    return number


def validate_panel(payload: Any) -> dict[str, Any]:
    """Validate and normalize one control-panel contract."""
    if not isinstance(payload, dict):
        raise BinderControlError("control panel must be a JSON object")
    _exact_keys(
        payload,
        {
            "schema_version",
            "scope_id",
            "selected_metric_id",
            "minimum_controls_per_class",
            "required_predictors",
            "required_seeds",
            "metrics",
            "controls",
            "source_posture",
            "result_boundary",
        },
        "control panel",
    )
    if payload.get("schema_version") != PANEL_SCHEMA:
        raise BinderControlError(f"control panel schema_version must be {PANEL_SCHEMA}")
    scope_id = _safe_id(payload.get("scope_id"), "control panel scope_id")
    minimum = payload.get("minimum_controls_per_class")
    if not isinstance(minimum, int) or isinstance(minimum, bool) or not 1 <= minimum <= 100:
        raise BinderControlError("minimum_controls_per_class must be between 1 and 100")
    predictors = payload.get("required_predictors")
    if not isinstance(predictors, list) or not predictors:
        raise BinderControlError("required_predictors must be a non-empty list")
    normalized_predictors = [_safe_id(item, "required predictor") for item in predictors]
    if len(normalized_predictors) != len(set(normalized_predictors)):
        raise BinderControlError("required_predictors contains a duplicate")
    seeds = payload.get("required_seeds")
    if (
        not isinstance(seeds, list)
        or not seeds
        or any(not isinstance(seed, int) or isinstance(seed, bool) or seed < 0 for seed in seeds)
        or len(seeds) != len(set(seeds))
    ):
        raise BinderControlError("required_seeds must contain unique non-negative integers")

    raw_controls = payload.get("controls")
    if not isinstance(raw_controls, list) or not raw_controls:
        raise BinderControlError("controls must be a non-empty list")
    controls: list[dict[str, str]] = []
    control_ids: set[str] = set()
    source_ids: set[str] = set()
    for index, item in enumerate(raw_controls):
        if not isinstance(item, dict):
            raise BinderControlError(f"control {index} must be an object")
        _exact_keys(item, {"id", "class", "requirement", "source_posture", "source_id"}, f"control {index}")
        control_id = _safe_id(item.get("id"), f"control {index} id")
        if control_id in control_ids:
            raise BinderControlError(f"control panel repeats control {control_id}")
        control_ids.add(control_id)
        control_class = item.get("class")
        if control_class not in CONTROL_CLASSES:
            raise BinderControlError(f"control {control_id} class must be positive or negative")
        requirement = item.get("requirement")
        if requirement not in {"required", "optional"}:
            raise BinderControlError(f"control {control_id} requirement must be required or optional")
        source_posture = item.get("source_posture")
        if source_posture not in {"public_data", "synthetic_demo"}:
            raise BinderControlError(f"control {control_id} source_posture must be public_data or synthetic_demo")
        source_id = _safe_id(item.get("source_id"), f"control {control_id} source_id")
        if source_id in source_ids:
            raise BinderControlError(f"control panel repeats source_id {source_id}")
        source_ids.add(source_id)
        controls.append(
            {
                "id": control_id,
                "class": str(control_class),
                "requirement": str(requirement),
                "source_posture": str(source_posture),
                "source_id": source_id,
            }
        )

    raw_metrics = payload.get("metrics")
    if not isinstance(raw_metrics, list) or not raw_metrics:
        raise BinderControlError("metrics must be a non-empty list")
    metrics: list[dict[str, Any]] = []
    metric_ids: set[str] = set()
    for index, item in enumerate(raw_metrics):
        if not isinstance(item, dict):
            raise BinderControlError(f"metric {index} must be an object")
        _exact_keys(item, {"id", "direction", "unit", "required_control_ids"}, f"metric {index}")
        metric_id = _safe_id(item.get("id"), f"metric {index} id")
        if metric_id in metric_ids:
            raise BinderControlError(f"control panel repeats metric {metric_id}")
        metric_ids.add(metric_id)
        direction = item.get("direction")
        if direction not in DIRECTIONS:
            raise BinderControlError(f"metric {metric_id} direction is not supported")
        unit = item.get("unit")
        if not isinstance(unit, str) or not unit.strip() or len(unit) > 80:
            raise BinderControlError(f"metric {metric_id} unit must be a short string")
        required_ids = item.get("required_control_ids")
        if (
            not isinstance(required_ids, list)
            or any(not isinstance(control_id, str) or control_id not in control_ids for control_id in required_ids)
            or len(required_ids) != len(set(required_ids))
        ):
            raise BinderControlError(f"metric {metric_id} required_control_ids are invalid")
        metrics.append(
            {
                "id": metric_id,
                "direction": str(direction),
                "unit": unit.strip(),
                "required_control_ids": list(required_ids),
            }
        )
    selected_metric_id = payload.get("selected_metric_id")
    if selected_metric_id not in metric_ids:
        raise BinderControlError("selected_metric_id must name a declared metric")
    if payload.get("source_posture") not in {"public_data", "synthetic_demo", "mixed"}:
        raise BinderControlError("control panel source_posture is not supported")
    if payload.get("result_boundary") != "planning":
        raise BinderControlError("control panel result_boundary must be planning")
    return {
        "schema_version": PANEL_SCHEMA,
        "scope_id": scope_id,
        "selected_metric_id": selected_metric_id,
        "minimum_controls_per_class": minimum,
        "required_predictors": normalized_predictors,
        "required_seeds": sorted(seeds),
        "metrics": metrics,
        "controls": controls,
        "source_posture": payload["source_posture"],
        "result_boundary": "planning",
    }


def _selected_metric(panel: dict[str, Any]) -> dict[str, Any]:
    return next(metric for metric in panel["metrics"] if metric["id"] == panel["selected_metric_id"])


def _required_control_ids(panel: dict[str, Any]) -> set[str]:
    required = {control["id"] for control in panel["controls"] if control["requirement"] == "required"}
    required.update(_selected_metric(panel)["required_control_ids"])
    return required


def index_predictions(panel_payload: Any, rows: Any) -> dict[str, Any]:
    """Index the declared prediction matrix and report required and optional gaps."""
    panel = validate_panel(panel_payload)
    if not isinstance(rows, list):
        raise BinderControlError("control observations must be a JSON list")
    controls = {control["id"]: control for control in panel["controls"]}
    metrics = {metric["id"]: metric for metric in panel["metrics"]}
    required_ids = _required_control_ids(panel)
    indexed: dict[tuple[str, str, int], dict[str, Any]] = {}
    errors: list[str] = []
    for number, row in enumerate(rows, start=1):
        if not isinstance(row, dict):
            errors.append(f"observation {number} must be an object")
            continue
        expected = {"control_id", "predictor_id", "seed", "status", "metrics"}
        if set(row) != expected:
            errors.append(f"observation {number} fields do not match the observation contract")
            continue
        control_id = row.get("control_id")
        predictor_id = row.get("predictor_id")
        seed = row.get("seed")
        if (
            control_id not in controls
            or predictor_id not in panel["required_predictors"]
            or not isinstance(seed, int)
            or isinstance(seed, bool)
            or seed not in panel["required_seeds"]
        ):
            errors.append(f"observation {number} names an undeclared control, predictor, or seed")
            continue
        key = (str(control_id), str(predictor_id), int(seed))
        if key in indexed:
            errors.append(f"duplicate observation for control={control_id} predictor={predictor_id} seed={seed}")
            continue
        status = row.get("status")
        if status not in {"scored", "failed"}:
            errors.append(f"observation {number} status must be scored or failed")
            continue
        raw_metrics = row.get("metrics")
        if not isinstance(raw_metrics, dict) or any(metric_id not in metrics for metric_id in raw_metrics):
            errors.append(f"observation {number} metrics are invalid")
            continue
        normalized_metrics: dict[str, float] = {}
        try:
            for metric_id, value in raw_metrics.items():
                normalized_metrics[metric_id] = _finite(value, f"observation {number} {metric_id}")
        except BinderControlError as exc:
            errors.append(str(exc))
            continue
        indexed[key] = {
            "control_id": control_id,
            "predictor_id": predictor_id,
            "seed": seed,
            "status": status,
            "metrics": normalized_metrics,
        }

    required_gaps: list[str] = []
    optional_gaps: list[str] = []
    complete_controls: list[str] = []
    selected_metric_id = panel["selected_metric_id"]
    for control_id in controls:
        gaps: list[str] = []
        for predictor_id in panel["required_predictors"]:
            for seed in panel["required_seeds"]:
                row = indexed.get((control_id, predictor_id, seed))
                if row is None:
                    gaps.append(f"missing predictor={predictor_id} seed={seed}")
                elif row["status"] != "scored":
                    gaps.append(f"failed predictor={predictor_id} seed={seed}")
                elif selected_metric_id not in row["metrics"]:
                    gaps.append(f"missing {selected_metric_id} predictor={predictor_id} seed={seed}")
        if gaps:
            target = required_gaps if control_id in required_ids else optional_gaps
            target.append(f"control {control_id}: " + "; ".join(gaps))
        else:
            complete_controls.append(control_id)
    if errors:
        required_gaps.extend(errors)
    expected_required = len(required_ids) * len(panel["required_predictors"]) * len(panel["required_seeds"])
    expected_all = len(controls) * len(panel["required_predictors"]) * len(panel["required_seeds"])
    return {
        "expected_observation_count": expected_all,
        "expected_required_observation_count": expected_required,
        "observed_unique_count": len(indexed),
        "required_control_ids": sorted(required_ids),
        "complete_control_ids": sorted(complete_controls),
        "required_gaps": required_gaps,
        "optional_gaps": optional_gaps,
        "indexed_rows": [indexed[key] for key in sorted(indexed)],
    }


def _reduce_control(
    panel: dict[str, Any],
    prediction_index: dict[str, Any],
    control_id: str,
    predictor_id: str,
) -> dict[str, Any] | None:
    selected_metric = _selected_metric(panel)
    rows = [
        row
        for row in prediction_index["indexed_rows"]
        if row["control_id"] == control_id
        and row["predictor_id"] == predictor_id
        and row["status"] == "scored"
        and panel["selected_metric_id"] in row["metrics"]
    ]
    if len(rows) != len(panel["required_seeds"]):
        return None
    sign = 1.0 if selected_metric["direction"] == "higher_is_better" else -1.0
    selected = max(
        rows,
        key=lambda row: (sign * row["metrics"][panel["selected_metric_id"]], -row["seed"]),
    )
    return {
        "control_id": control_id,
        "predictor_id": predictor_id,
        "selected_seed": selected["seed"],
        "selection_metric_id": panel["selected_metric_id"],
        "selection_rule": f"best_{selected_metric['direction']}_then_lowest_seed",
        "metrics": dict(selected["metrics"]),
    }


def _metric_gap(positive: list[float], negative: list[float], direction: str) -> dict[str, Any]:
    if direction == "higher_is_better":
        positive_boundary = min(positive)
        negative_boundary = max(negative)
        gap = positive_boundary - negative_boundary
    else:
        positive_boundary = max(positive)
        negative_boundary = min(negative)
        gap = negative_boundary - positive_boundary
    return {
        "direction": direction,
        "positive_range": {"count": len(positive), "minimum": min(positive), "maximum": max(positive)},
        "negative_range": {"count": len(negative), "minimum": min(negative), "maximum": max(negative)},
        "positive_boundary": positive_boundary,
        "negative_boundary": negative_boundary,
        "gap": gap,
        "strictly_separating": gap > 0.0,
        "operator": DIRECTIONS[direction],
        "threshold": (positive_boundary + negative_boundary) / 2.0 if gap > 0.0 else None,
    }


def derive_calibration(panel_payload: Any, rows: Any) -> dict[str, Any]:
    """Derive per-predictor metric gates from a complete measured-control matrix."""
    panel = validate_panel(panel_payload)
    prediction_index = index_predictions(panel, rows)
    controls = {control["id"]: control for control in panel["controls"]}
    complete_ids = set(prediction_index["complete_control_ids"])
    reductions = [
        reduced
        for control_id in sorted(complete_ids)
        for predictor_id in panel["required_predictors"]
        for reduced in [_reduce_control(panel, prediction_index, control_id, predictor_id)]
        if reduced is not None
    ]
    diagnostics: dict[str, Any] = {}
    gates: list[dict[str, Any]] = []
    blocking = list(prediction_index["required_gaps"])
    selected_metric_id = panel["selected_metric_id"]
    for predictor_id in panel["required_predictors"]:
        metric_reports: dict[str, Any] = {}
        for metric in panel["metrics"]:
            positive = [
                row["metrics"][metric["id"]]
                for row in reductions
                if row["predictor_id"] == predictor_id
                and controls[row["control_id"]]["class"] == "positive"
                and metric["id"] in row["metrics"]
            ]
            negative = [
                row["metrics"][metric["id"]]
                for row in reductions
                if row["predictor_id"] == predictor_id
                and controls[row["control_id"]]["class"] == "negative"
                and metric["id"] in row["metrics"]
            ]
            enough = (
                len(positive) >= panel["minimum_controls_per_class"]
                and len(negative) >= panel["minimum_controls_per_class"]
            )
            if enough:
                report = _metric_gap(positive, negative, metric["direction"])
            else:
                report = {
                    "direction": metric["direction"],
                    "positive_range": {"count": len(positive), "minimum": min(positive) if positive else None, "maximum": max(positive) if positive else None},
                    "negative_range": {"count": len(negative), "minimum": min(negative) if negative else None, "maximum": max(negative) if negative else None},
                    "positive_boundary": None,
                    "negative_boundary": None,
                    "gap": None,
                    "strictly_separating": False,
                    "operator": DIRECTIONS[metric["direction"]],
                    "threshold": None,
                }
            report["minimum_controls_per_class"] = panel["minimum_controls_per_class"]
            report["enough_controls"] = enough
            metric_reports[metric["id"]] = report
            if metric["id"] == selected_metric_id:
                if not enough:
                    blocking.append(
                        f"predictor {predictor_id} selected metric {selected_metric_id} needs "
                        f"{panel['minimum_controls_per_class']} complete controls per class"
                    )
                elif not report["strictly_separating"]:
                    blocking.append(
                        f"predictor {predictor_id} selected metric {selected_metric_id} has no strict control gap"
                    )
                else:
                    gates.append(
                        {
                            "predictor_id": predictor_id,
                            "metric_id": selected_metric_id,
                            "direction": metric["direction"],
                            "unit": metric["unit"],
                            "operator": report["operator"],
                            "threshold": report["threshold"],
                            "derivation": "midpoint_between_worst_positive_and_best_negative",
                        }
                    )
        diagnostics[predictor_id] = {"metrics": metric_reports}
    ready = not blocking and len(gates) == len(panel["required_predictors"])
    optional_gaps = prediction_index["optional_gaps"]
    state = "ready_with_optional_gaps" if ready and optional_gaps else "ready" if ready else "blocked"
    return {
        "schema_version": CALIBRATION_SCHEMA,
        "record_type": "binder-control-calibration",
        "scope_id": panel["scope_id"],
        "method": "derived",
        "status": state,
        "selected_metric_id": selected_metric_id,
        "calibration_state": "calibrated" if ready else "uncalibrated",
        "round_decision_ready": ready,
        "prediction_index": prediction_index,
        "selected_rows": reductions,
        "diagnostic": {"aggregation": "predictor_separated", "predictors": diagnostics},
        "gates": gates,
        "readiness": {
            "state": state,
            "blocking_reasons": blocking,
            "optional_gaps": optional_gaps,
            "next_actions": (
                ["supply_required_control_observations", "select_another_metric", "record_operator_defined_policy"]
                if blocking
                else (["supply_optional_control_observations"] if optional_gaps else [])
            ),
        },
        "source_posture": panel["source_posture"],
        "result_boundary": "planning",
        "provider_calls": 0,
        "interpretation_limit": "Control separation calibrates a computational metric. It does not establish experimental binding.",
    }


def adopt_calibration(panel_payload: Any, payload: Any) -> dict[str, Any]:
    """Adopt a complete external gate set for the selected metric."""
    panel = validate_panel(panel_payload)
    if not isinstance(payload, dict):
        raise BinderControlError("adopted calibration must be a JSON object")
    _exact_keys(
        payload,
        {"schema_version", "source_scope_id", "selected_metric_id", "source_artifact_sha256", "gates", "adoption_reason"},
        "adopted calibration",
    )
    if payload.get("schema_version") != ADOPTION_SCHEMA:
        raise BinderControlError(f"adopted calibration schema_version must be {ADOPTION_SCHEMA}")
    source_scope_id = _safe_id(payload.get("source_scope_id"), "adopted source_scope_id")
    if payload.get("selected_metric_id") != panel["selected_metric_id"]:
        raise BinderControlError("adopted calibration must name the panel selected metric")
    source_digest = payload.get("source_artifact_sha256")
    if not isinstance(source_digest, str) or SHA256_RE.fullmatch(source_digest) is None:
        raise BinderControlError("adopted calibration requires source_artifact_sha256")
    reason = payload.get("adoption_reason")
    if not isinstance(reason, str) or not reason.strip() or len(reason) > 500:
        raise BinderControlError("adopted calibration requires a concise adoption_reason")
    raw_gates = payload.get("gates")
    if not isinstance(raw_gates, list):
        raise BinderControlError("adopted calibration gates must be a list")
    selected = _selected_metric(panel)
    gates: list[dict[str, Any]] = []
    seen: set[str] = set()
    for index, gate in enumerate(raw_gates):
        if not isinstance(gate, dict):
            raise BinderControlError(f"adopted gate {index} must be an object")
        _exact_keys(gate, {"predictor_id", "metric_id", "operator", "threshold"}, f"adopted gate {index}")
        predictor_id = gate.get("predictor_id")
        if predictor_id not in panel["required_predictors"] or predictor_id in seen:
            raise BinderControlError("adopted gates must name every required predictor exactly once")
        seen.add(str(predictor_id))
        if gate.get("metric_id") != panel["selected_metric_id"] or gate.get("operator") != DIRECTIONS[selected["direction"]]:
            raise BinderControlError("adopted gate metric or operator differs from the panel")
        gates.append(
            {
                "predictor_id": predictor_id,
                "metric_id": panel["selected_metric_id"],
                "direction": selected["direction"],
                "unit": selected["unit"],
                "operator": gate["operator"],
                "threshold": _finite(gate.get("threshold"), f"adopted gate {index} threshold"),
                "derivation": "adopted_from_declared_source",
            }
        )
    if seen != set(panel["required_predictors"]):
        raise BinderControlError("adopted gates must cover every required predictor")
    return {
        "schema_version": CALIBRATION_SCHEMA,
        "record_type": "binder-control-calibration",
        "scope_id": panel["scope_id"],
        "method": "adopted",
        "status": "ready",
        "selected_metric_id": panel["selected_metric_id"],
        "calibration_state": "borrowed",
        "round_decision_ready": True,
        "source_calibration": {
            "scope_id": source_scope_id,
            "artifact_sha256": source_digest,
            "adoption_reason": reason.strip(),
        },
        "prediction_index": None,
        "selected_rows": [],
        "diagnostic": None,
        "gates": sorted(gates, key=lambda gate: gate["predictor_id"]),
        "readiness": {"state": "ready", "blocking_reasons": [], "optional_gaps": [], "next_actions": []},
        "source_posture": panel["source_posture"],
        "result_boundary": "planning",
        "provider_calls": 0,
        "interpretation_limit": "Adopted computational gates do not establish experimental binding or transfer accuracy.",
    }


def bind_round_history(
    plan: Any,
    history: Any,
    calibration: Any,
    calibration_artifact_sha256: str,
) -> list[dict[str, Any]]:
    """Bind a ready calibration record to measured round-history provenance."""
    if not isinstance(plan, dict) or not isinstance(plan.get("optimization_policy"), dict):
        raise BinderControlError("round plan has no optimization_policy")
    if not isinstance(calibration, dict) or calibration.get("schema_version") != CALIBRATION_SCHEMA:
        raise BinderControlError("round decision calibration record is invalid")
    if calibration.get("round_decision_ready") is not True or calibration.get("status") not in {
        "ready",
        "ready_with_optional_gaps",
    }:
        raise BinderControlError("round decision calibration is not ready")
    metric_id = plan["optimization_policy"].get("primary_metric_id")
    if metric_id != calibration.get("selected_metric_id"):
        raise BinderControlError("calibration selected metric differs from the plan primary metric")
    if not isinstance(calibration_artifact_sha256, str) or SHA256_RE.fullmatch(calibration_artifact_sha256) is None:
        raise BinderControlError("calibration artifact SHA-256 is invalid")
    if not isinstance(history, list):
        raise BinderControlError("round decision history must be a JSON list")
    bound = copy.deepcopy(history)
    for index, row in enumerate(bound, start=1):
        provenance = row.get("metric_provenance") if isinstance(row, dict) else None
        if not isinstance(provenance, dict) or provenance.get("metric_id") != metric_id:
            raise BinderControlError(f"round {index} metric provenance differs from the calibration metric")
        if provenance.get("metric_source") == "synthetic_fixture":
            raise BinderControlError("a measured calibration cannot bind synthetic fixture metrics")
        provenance["calibration_state"] = calibration["calibration_state"]
        provenance["calibration_scope_id"] = calibration["scope_id"]
        provenance["calibration_artifact_sha256"] = calibration_artifact_sha256
    return bound
