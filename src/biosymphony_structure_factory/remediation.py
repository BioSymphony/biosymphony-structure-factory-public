"""Turn binder-lane refusals into stable, actionable public records."""

from __future__ import annotations

from typing import Any


def _record(check_id: str, category: str, summary: str, actions: list[tuple[str, str]]) -> dict[str, Any]:
    return {
        "check_id": check_id,
        "category": category,
        "summary": summary,
        "next_actions": [
            {"id": action_id, "description": description}
            for action_id, description in actions
        ],
    }


def failure_record(error: Exception) -> dict[str, Any]:
    """Classify one sanitized exception without echoing input values."""
    message = str(error)
    lowered = message.casefold()

    if "calibration" in lowered or "metric provenance" in lowered or "metric_source" in lowered:
        return _record(
            "metric-provenance",
            "metric_calibration",
            "The metric cannot support this comparison or stopping decision with its current provenance.",
            [
                ("join-metric", "Bind the metric value to the exact scored artifact SHA-256."),
                ("record-calibration", "Record a calibrated, borrowed, or user-defined threshold scope."),
                ("change-stopping-rule", "Use a stopping rule that does not interpret an uncalibrated threshold."),
            ],
        )
    if "target" in lowered or "required coordinate residues" in lowered or "sequence differs" in lowered:
        return _record(
            "target-verification",
            "target_identity",
            "The selected coordinates do not establish the requested target chain and site.",
            [
                ("inspect-target", "Inspect the chain, numbering basis, modeled coverage, and sequence source."),
                ("select-coordinates", "Select coordinates that contain the required site residues."),
                ("update-target", "Update the target definition only when the intended construct or site is different."),
            ],
        )
    if "explicit authorization" in lowered or "authorization" in lowered:
        return _record(
            "execution-authorization",
            "authorization",
            "The command is valid but the requested execution boundary has not been authorized.",
            [
                ("dry-run", "Run the same adapter in dry-run mode and inspect the resolved contract."),
                ("authorize-bounds", "Grant authorization for the named tool, route, data posture, budget, and runtime."),
                ("change-route", "Select another local, platform-skill, API, or self-hosted route."),
            ],
        )
    if "budget" in lowered or "spend" in lowered:
        return _record(
            "budget-boundary",
            "budget",
            "The requested round does not fit the declared spend boundary.",
            [
                ("reduce-work", "Reduce candidates, rounds, retries, or runtime."),
                ("change-route", "Select a route that fits the existing ceiling."),
                ("revise-budget", "Revise the budget only with the user's bounded approval."),
            ],
        )
    if "artifact" in lowered or "output" in lowered or "closeout" in lowered or "sha-256" in lowered:
        return _record(
            "artifact-closeout",
            "artifact_integrity",
            "The stage output does not satisfy its declared count, parse, hash, or cleanup contract.",
            [
                ("inspect-stage", "Inspect the stage receipt and declared output paths."),
                ("rerun-stage", "Rerun the failed stage without promoting partial outputs."),
                ("correct-contract", "Correct the declaration only when the intended output contract was wrong."),
            ],
        )
    if "program" in lowered or "environment" in lowered or "readiness" in lowered:
        return _record(
            "adapter-readiness",
            "runtime_readiness",
            "The selected adapter is not ready in this runtime.",
            [
                ("inspect-readiness", "Run the adapter readiness check and inspect missing names or programs."),
                ("prepare-runtime", "Install the selected tool and supply required runtime environment values."),
                ("select-adapter", "Select another validated adapter or platform-skill route."),
            ],
        )
    if "license" in lowered or "terms" in lowered or "retention" in lowered:
        return _record(
            "use-constraint",
            "terms_and_license",
            "The selected tool or service needs a use-context review before execution.",
            [
                ("review-terms", "Review the current code, weight, dependency, service, and data-handling terms."),
                ("change-tool", "Select a tool whose terms fit the intended use."),
                ("change-route", "Use a self-hosted or local route when it better fits the data boundary."),
            ],
        )
    if any(term in lowered for term in ("secret", "credential", "private", "machine-local", "outside", "path")):
        return _record(
            "public-safety-boundary",
            "data_and_path_safety",
            "The input crosses the repository's public data, credential, or path boundary.",
            [
                ("move-runtime-data", "Keep runtime data and provider state below ignored runtime storage."),
                ("use-reference", "Pass a relative artifact reference or environment-variable name instead of a value."),
                ("sanitize-input", "Remove private process text, credentials, account identifiers, and controller paths."),
            ],
        )
    if "remote" in error.__class__.__name__.casefold() or "receipt" in lowered or "request" in lowered:
        return _record(
            "remote-contract",
            "remote_contract",
            "The remote request or receipt does not match the fixed provider-neutral contract.",
            [
                ("validate-request", "Validate the fixed request before dispatch."),
                ("join-receipt", "Join the receipt to the same request and pinned identities."),
                ("select-operation", "Register the reviewed tool operation without adding command or credential fields."),
            ],
        )
    return _record(
        "binder-input",
        "invalid_input",
        "The binder-lane input does not satisfy its declared contract.",
        [
            ("inspect-error", "Correct the named field or contract mismatch."),
            ("run-preflight", "Rerun the relevant validation or preflight command."),
        ],
    )
