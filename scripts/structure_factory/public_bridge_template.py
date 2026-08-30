"""Helpers for writing public bridge-manifest templates."""

from __future__ import annotations

from copy import deepcopy
from typing import Any


PUBLIC_TEMPLATE_STATUS = "tracked_public_template"
PUBLIC_TEMPLATE_NOTE = (
    "Tracked template. This file documents the expected provider bridge-manifest shape. "
    "Materialize an ignored runtime packet with the current license/use context, budget, "
    "placement, pinned public commit, provider credentials by reference, cleanup policy, "
    "and explicit human authorization before execution."
)
PUBLIC_STARTUP_COMMANDS = [
    "set -euo pipefail",
    "echo 'Tracked template has no runtime payload. Materialize an ignored runtime packet and obtain explicit human authorization before execution.'",
    "exit 64",
]


def make_public_bridge_template(manifest: dict[str, Any]) -> dict[str, Any]:
    """Return a tracked bridge template with live execution state removed."""
    public = deepcopy(manifest)
    public["remote_launch_allowed"] = False
    public["public_template_status"] = PUBLIC_TEMPLATE_STATUS
    public["public_template_note"] = PUBLIC_TEMPLATE_NOTE

    authorization = public.setdefault("launch_authorization", {})
    authorization["approved_at"] = "PENDING"
    authorization["approved_by"] = "PENDING-OPERATOR-GATE"
    authorization["linear_issue_url"] = "PENDING-TRACKER-ISSUE"
    authorization["source"] = "templates/operator-wave-runbook.md"
    authorization["scope"] = PUBLIC_TEMPLATE_NOTE

    startup = public.setdefault("startup", {})
    startup["commands"] = list(PUBLIC_STARTUP_COMMANDS)
    startup.setdefault("mode", "dockerStartCmd")
    inspection = startup.setdefault("inspection", {})
    inspection["hold_after_success_seconds"] = 0

    runpod = public.setdefault("runpod", {})
    runpod["imageDigestRequiredForReal"] = True
    if "dataCenterIds" in runpod:
        runpod["dataCenterIds"] = []
    if "networkVolumeId" in runpod and runpod["networkVolumeId"] not in {"", "STRUCTURE_FACTORY_RUNPOD_NETWORK_VOLUME_ID"}:
        runpod["networkVolumeId"] = "STRUCTURE_FACTORY_RUNPOD_NETWORK_VOLUME_ID"

    safety = public.setdefault("safety", {})
    safety["public_template_policy"] = (
        "No secrets, concrete provider resources, private volume assumptions, prior-run artifacts, "
        "accepted-license state, or live startup payloads are encoded in this tracked manifest."
    )

    repo = public.setdefault("repo", {})
    repo.setdefault(
        "commit_or_snapshot_pin_policy",
        "Execution-ready packets must pin an immutable public source ref outside public git.",
    )
    return public
