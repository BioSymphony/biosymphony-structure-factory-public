"""Dependency-free public validator for Structure Factory repos."""

from __future__ import annotations

import argparse
import json
import os
import re
import sys
from dataclasses import dataclass
from pathlib import Path
from typing import Any

from . import (
    binder_controller,
    binder_controls,
    binder_execution_prep,
    binder_executor,
    binder_lane,
    binder_receipts,
    remediation,
    remote_tool_contract,
    target_verifier,
)


ALLOWED_RESULT_BOUNDARIES = {
    "planning",
    "public_demo",
    "public_synthetic_demo",
    "computational_candidate",
    "candidate",
    "blocked",
    "insufficient_evidence",
    "insufficient_support",
}

PUBLIC_CAMPAIGN_RESULT_BOUNDARIES = ALLOWED_RESULT_BOUNDARIES - {"candidate", "insufficient_evidence"}

LEGACY_RESULT_BOUNDARY_ALIASES = {
    "insufficient_evidence": "insufficient_support",
}

ALLOWED_SOURCE_POSTURES = {
    "synthetic_demo",
    "public_data",
    "generated_candidate",
    "blocked",
    "insufficient_support",
    "insufficient_evidence",
    "report_only",
    "provider_native",
    "derived",
}

MODE_ALIASES = {
    "model-comparison": "model-comparison",
    "structure-report": "structure-mapping",
}

CAMPAIGN_MODES = [
    "binder-design",
    "model-comparison",
    "structure-mapping",
    "screening",
    # Backward-compatible aliases for older generated manifests and scripts.
    "model-comparison",
    "structure-report",
]

ALLOWED_PRIVACY = {
    "public_only",
    "public_or_synthetic_only",
    "synthetic_demo",
}

SKIP_DIRS = {
    ".git",
    ".hg",
    ".svn",
    ".runtime",
    ".venv",
    "venv",
    "__pycache__",
    ".pytest_cache",
    ".mypy_cache",
    ".ruff_cache",
    "build",
    "dist",
}

FORBIDDEN_EXACT_NAME_PARTS = {
    ".codex",
    ".env",
    ".env.local",
    "_book",
    "secrets",
    "pod_id",
    "delivered",
    "logs",
    "provider-artifacts",
    "receipts",
    "runpod_resource_record",
    "runpod_cleanup_record",
    "execution-packets",
    "measurements",
    "packets",
    "provider-logs",
    "telemetry",
}

FORBIDDEN_NAME_SUBSTRINGS = {
    "secret",
    "token",
    "billing",
}

FORBIDDEN_PATH_PREFIXES = {
    ".wave",
    "artifacts/",
    "internal/private/",
    "internal/run-notes/",
    "internal/secrets/",
    "output/",
    "outputs/",
    "runpod-runs/",
    "packets/",
    "scratch/",
    ".playwright",
    "delivered/",
    "logs/",
    "provider-artifacts/",
    "receipts/",
}

FORBIDDEN_SUFFIXES = {
    ".ali",
    ".arrow",
    ".bcif",
    ".ckpt",
    ".pdb",
    ".cif",
    ".cs",
    ".db",
    ".dm4",
    ".duckdb",
    ".eer",
    ".fa",
    ".faa",
    ".fasta",
    ".feather",
    ".fastq",
    ".fna",
    ".fq",
    ".gif",
    ".html",
    ".htm",
    ".h5",
    ".hdf",
    ".hdf5",
    ".map",
    ".mol2",
    ".mmcif",
    ".mrc",
    ".mrcs",
    ".mdoc",
    ".npy",
    ".npz",
    ".onnx",
    ".parquet",
    ".pem",
    ".pkl",
    ".pickle",
    ".pml",
    ".rawtlt",
    ".rec",
    ".st",
    ".trb",
    ".key",
    ".joblib",
    ".pt",
    ".pth",
    ".safetensors",
    ".sdf",
    ".sqlite",
    ".sqlite3",
    ".tar",
    ".gz",
    ".xz",
    ".zst",
    ".css",
    ".js",
    ".jsx",
    ".ts",
    ".tsx",
    ".7z",
    ".bz2",
    ".rar",
    ".zip",
    ".mp4",
    ".mov",
    ".wav",
    ".webm",
    ".mkv",
    ".avi",
    ".mp3",
    ".flac",
    ".ipynb",
}

TEXT_SUFFIXES = {
    "",
    ".cfg",
    ".cff",
    ".csv",
    ".in",
    ".ini",
    ".json",
    ".jsonl",
    ".md",
    ".py",
    ".qmd",
    ".sh",
    ".svg",
    ".toml",
    ".tsv",
    ".txt",
    ".yaml",
    ".yml",
}

REQUIRED_HARNESS_FILES = [
    "README.md",
    "AGENTS.md",
    "BIOSAFETY.md",
    "CHANGELOG.md",
    "NON_CLAIMS.md",
    "PUBLIC_RELEASE.md",
    "SECURITY.md",
    "CODE_OF_CONDUCT.md",
    "CITATION.cff",
    "SUPPORT.md",
    "MANIFEST.in",
    ".github/pull_request_template.md",
    ".github/ISSUE_TEMPLATE/bug-report.yml",
    ".github/ISSUE_TEMPLATE/campaign-request.yml",
    ".github/ISSUE_TEMPLATE/config.yml",
    "docs/agentic-biology-harness.md",
    "docs/agent-recipes.md",
    "docs/assets/README.md",
    "docs/capabilities.md",
    "docs/cli-reference.md",
    "docs/result-boundaries.md",
    "docs/workflow-map.md",
    "docs/use-cases.md",
    "docs/faq.md",
    "docs/glossary.md",
    "docs/skill-install.md",
    "docs/standalone-agent-workflow.md",
    "docs/privacy-and-security-model.md",
    "docs/quickstart-tour.md",
    "docs/public-export-shape.md",
    "docs/public-switch-checklist.md",
    "docs/tool-and-skill-radar.md",
    "docs/linear-orchestration.md",
    "docs/compute-backends.md",
    "docs/binder-lane-round.md",
    "docs/runpod-stack.md",
    "docs/tooling-and-licensing.md",
    "packs/task-packs/binder-design-fast-path-v0/pack.yaml",
    "packs/README.md",
    "references/agent-handoff.md",
    "references/binder-lane-capability-ledger.json",
    "references/published-binder-comparison-workflow.json",
    "runpod/README.md",
    "schemas/README.md",
    "schemas/binder-api-adapter-contract.schema.json",
    "schemas/binder-capability-ledger.schema.json",
    "schemas/binder-failure-record.schema.json",
    "schemas/binder-metric-provenance.schema.json",
    "schemas/binder-remote-tool-receipt.schema.json",
    "schemas/binder-remote-tool-request.schema.json",
    "schemas/binder-round-plan.schema.json",
    "schemas/binder-round-report.schema.json",
    "schemas/binder-round-request.schema.json",
    "schemas/binder-target-verification-report.schema.json",
    "modules/schemas/binder-execution-handoff.v1.schema.json",
    "modules/schemas/binder-round-contract.v1.schema.json",
    "skills/biosymphony-structure-factory/SKILL.md",
    "skills/binder-lane-round/SKILL.md",
    "skills/README.md",
    "templates/github-issue.md",
    "templates/operator-wave-runbook.md",
    "templates/binder-api-adapter-contract.json",
    "tools/README.md",
    "recipes/README.md",
    "docs/assets/structure-factory-loop.svg",
    "docs/assets/newcomer-paths.svg",
    "docs/assets/workflow-ladder.svg",
    "examples/orchestration-fixtures/README.md",
    "examples/pd-l1-binder-design-public/binder-round-request.json",
]

HARNESS_TEXT_REQUIREMENTS = {
    "README.md": [
        "BioSymphony",
        "Symphony",
        "RunPod",
        "skill",
        "candidate ranking",
        "How To Use This",
        "Start Here",
        "Hand A Mission To An Agent",
        "Workflow Stages",
        "When To Use This",
        "What Users And Their Agents Can Run",
        "Works With Your Stack",
        "Newcomer Resources",
        "docs/capabilities.md",
        "docs/workflow-map.md",
        "docs/faq.md",
        "docs/glossary.md",
        "bsf scaffold-campaign",
        "bsf doctor",
        "BIOSAFETY.md",
    ],
    "AGENTS.md": [
        "BioSymphony Structure Factory Agent Guide",
        "public_synthetic_demo",
        "computational_candidate",
        "Closeout requires artifacts, hashes, and validation notes",
    ],
    "BIOSAFETY.md": [
        "Biosafety",
        "does not authorize wet-lab work",
        "Public examples must avoid",
        "NON_CLAIMS.md",
    ],
    "docs/use-cases.md": [
        "Copyable Agent Prompts",
        "Binder-Design Triage",
        "Provider Preparation And Authorized Start",
        "Public-Release Review",
    ],
    "docs/faq.md": [
        "Do I need a GPU?",
        "Do I have to run the CLI commands myself?",
        "Which agents work with this?",
        "Can I use this without Linear or any tracker?",
        "How do I add my own tool, provider, or campaign mode?",
    ],
    "docs/glossary.md": [
        "Glossary",
        "Campaign manifest",
        "Result boundary",
        "Source posture",
        "pLDDT",
        "iPTM",
        "Stage contract",
        "BioSymphony",
        "CryoCore",
    ],
    "PUBLIC_RELEASE.md": [
        "make release-check",
        "make public-switch-check",
        "make secret-scan",
        "A skipped scan leaves this gate incomplete",
        "reviewer confirms its Git history and remote target",
    ],
    "SECURITY.md": [
        "Private vulnerability reporting",
        "Do not open public issues",
        "make public-switch-check",
    ],
    "docs/agent-recipes.md": [
        "Agent Recipes",
        "docs/use-cases.md",
        "Exact Result Values",
        "computational_candidate",
        "bsf scaffold-campaign",
        "operator gate",
    ],
    "docs/capabilities.md": [
        "Capabilities",
        "Binder-design campaign",
        "GPCR or multimer state atlas",
        "Screening and active learning",
        "Cloud/GPU execution prep",
        "bsf scaffold-campaign",
    ],
    "docs/assets/README.md": [
        "Visual Asset Notes",
        "structure-factory-loop.svg",
        "newcomer-paths.svg",
        "Text equivalent",
    ],
    "docs/skill-install.md": [
        "Install The Structure Factory Skill",
        "make harness-check",
    ],
    "docs/standalone-agent-workflow.md": [
        "Standalone Agent Workflow",
        "Copyable Agent Prompt",
        "bsf scaffold-campaign",
        "templates/github-issue.md",
    ],
    "docs/cli-reference.md": [
        "bsf scaffold-campaign",
        "bsf validate",
        "bsf audit",
        "bsf harness-check",
        "bsf doctor",
    ],
    "docs/result-boundaries.md": [
        "Result Boundaries And Source Posture",
        "computational_candidate",
        "Source Posture",
        "Legacy Schema Values",
        "Provider state is not source posture",
    ],
    "docs/privacy-and-security-model.md": [
        "Privacy And Security Model",
        "public release",
        "Never commit",
        "Launch templates",
    ],
    "docs/quickstart-tour.md": [
        "Quickstart Tour",
        "Three ways to start",
        "Use It With An Agent",
        "bsf scaffold-campaign",
        "make public-switch-check",
        "validated campaign scaffold",
    ],
    "recipes/README.md": [
        "Recipes",
        "PD-L1 binder-design fast path",
        "RunPod no-download smoke",
    ],
    "docs/public-switch-checklist.md": [
        "make public-switch-check",
        "reviewed public root commit",
        "Tracked RunPod templates",
        "Remote Gate",
    ],
    "docs/tool-and-skill-radar.md": [
        "planning snapshot",
        "Runtime Gated",
        "Review Required",
        "Export Priorities",
    ],
    "tools/README.md": [
        "Tool Cards",
        "Public docs",
        "Runtime use needs current primary-source review",
        "License-gated tools",
    ],
    "docs/agentic-biology-harness.md": [
        "Symphony",
        "Linear",
        "RunPod",
        "Optional review workers",
        "stage contract",
        "candidate ranking",
        "agent lanes",
    ],
    "skills/biosymphony-structure-factory/SKILL.md": [
        "sym:structure-factory",
        "RunPod",
        "Symphony",
        "Linear",
        "make harness-check",
    ],
    "templates/operator-wave-runbook.md": [
        "sym:structure-factory",
        "RunPod",
        "Operator authorization",
        "cleanup proof",
        "result boundary",
    ],
}

CONTENT_PATTERNS = [
    ("private-never-publish-sentinel", re.compile("BSF-" + "PRIVATE-" + "NEVER-" + "PUBLISH")),
    ("private-only-document", re.compile(r"\b(biosymphony-writing-" + r"brief|cinematic-video-" + r"playbook)\.md\b", re.I)),
    ("private-workstation-path", re.compile(r"(/" + r"Users/|/" + r"Volumes/|C:\\Users\\)")),
    ("local-user-or-private-root", re.compile(r"\b(github_[0-9]+|SSK_[A-Za-z0-9_]+)\b", re.I)),
    ("assigned-api-key", re.compile(r"\b([A-Z0-9_]*(API_KEY|SECRET|PASSWORD|ACCESS_TOKEN|AUTH_TOKEN|BEARER_TOKEN)[A-Z0-9_]*)\s*[:=]\s*['\"]?[A-Za-z0-9_\-]{8,}", re.I)),
    ("openai-style-token", re.compile(r"\bsk-[A-Za-z0-9_\-]{20,}\b")),
    ("github-token", re.compile(r"\bgh[pousr]_[A-Za-z0-9_]{20,}\b")),
    ("slack-token", re.compile(r"\bxox[baprs]-[A-Za-z0-9\-]{20,}\b")),
    ("aws-access-key-id", re.compile(r"\b(?:AKIA|ASIA)[A-Z0-9]{16}\b")),
    ("literal-runpod-resource-id", re.compile(r'"?(pod_id|volumeId|volume_id|networkVolumeId|network_volume_id)"?\s*[:=]\s*"?[a-z0-9]{8,}"?')),
    ("private-tracker-id", re.compile(r"\bVOG-[A-Za-z0-9][A-Za-z0-9-]*\b")),
    ("private-linear-url", re.compile(r"https?://linear\.app/[^\s)>\"]+", re.I)),
    ("provider-deployment-endpoint", re.compile(r"https?://[a-z0-9-]+(?:--[a-z0-9-]+)?\.(?:modal\.run|fal\.run|runpod\.net)\b", re.I)),
    ("runpod-serverless-endpoint", re.compile(r"https?://api\.runpod\.ai/v2/[A-Za-z0-9_-]{6,}\b", re.I)),
    ("private-run-checkpoint", re.compile(r"\bCHECKPOINT-\d{4}-\d{2}-\d{2}\b")),
    ("provider-incident-cost-ledger", re.compile(r"\b(dead[- ]" + r"pods?|pod " + r"fires|burned on dead " + r"pods)\b", re.I)),
    ("signed-url-parameters", re.compile(r"\b(X-Amz-(?:Signature|Credential)|X-Goog-Signature|GoogleAccessId|AWSAccessKeyId)\s*=\s*[A-Za-z0-9%+/_@.\-]{12,}", re.I)),
    ("one-time-transfer-link", re.compile(r"https?://(?:we\.tl|wetransfer\.com)/\S+", re.I)),
    ("harness-worktree-path", re.compile(r"\." + "bsf-agent-worktrees" + r"\b")),
    ("generated-candidate-sequence", re.compile(r'"(mpnn_sequence|binder_sequence)"\s*:\s*"[ACDEFGHIKLMNPQRSTVWY]{20,}"')),
    ("git-lfs-pointer", re.compile(r"^version https://git-lfs\.github\.com/spec/v1$", re.M)),
]


@dataclass
class Finding:
    severity: str
    check_id: str
    path: str
    message: str

    def to_dict(self) -> dict[str, str]:
        return {
            "severity": self.severity,
            "check_id": self.check_id,
            "path": self.path,
            "message": self.message,
        }


def read_json(path: Path) -> Any:
    with path.open("r", encoding="utf-8") as handle:
        return json.load(handle)


def write_json(data: Any) -> None:
    print(json.dumps(data, indent=2, sort_keys=True))


def reject_public_unsafe_input(name: str, value: str) -> None:
    for check_id, pattern in CONTENT_PATTERNS:
        if check_id == "generated-candidate-sequence":
            continue
        match = pattern.search(value)
        if match:
            raise ValueError(f"{name} contains release-blocking marker {check_id}")


def normalize_mode(mode: str) -> str:
    return MODE_ALIASES.get(mode, mode)


def normalize_result_boundary(value: Any) -> Any:
    if isinstance(value, str):
        return LEGACY_RESULT_BOUNDARY_ALIASES.get(value, value)
    return value


def get_result_boundary(mapping: dict[str, Any], legacy_key: str = "claim_level") -> Any:
    return normalize_result_boundary(mapping.get("result_boundary", mapping.get(legacy_key)))


def get_source_posture(mapping: dict[str, Any]) -> Any:
    return mapping.get("source_posture", mapping.get("evidence_mode"))


PUBLIC_TEXT_REPLACEMENTS = (
    ("public", "public"),
    ("candidate_ranking_top32", "candidate_ranking_top32"),
    ("candidate_ranking", "candidate_ranking"),
    ("validation_ledger", "validation_ledger"),
    ("validation ledger", "validation ledger"),
    ("result review", "validation review"),
    ("validation_review", "validation_review"),
    ("Result boundary", "Result boundary"),
    ("result boundary", "result boundary"),
    ("Claim Level", "Result Boundary"),
    ("claim ceiling", "result boundary"),
    ("claim_ceiling", "result_boundary"),
    ("claims", "conclusions"),
    ("Claims", "Conclusions"),
    ("claim", "statement"),
    ("Claim", "Statement"),
    ("evidence mode", "source posture"),
    ("Evidence mode", "Source posture"),
    ("evidence", "support"),
    ("Evidence", "Support"),
    ("insufficient_evidence", "insufficient_support"),
    ("model-comparison", "model-comparison"),
    ("method-ranking", "method-comparison"),
    ("ranking_synthesis", "ranking_synthesis"),
    ("ranking", "ranking"),
    ("Ranking", "Ranking"),
    ("candidate reports", "candidate reports"),
    ("candidate_reports", "candidate_reports"),
    ("reports", "reports"),
    ("Reports", "Reports"),
    ("report", "report"),
    ("Report", "Report"),
)


def public_text(value: Any) -> Any:
    if not isinstance(value, str):
        return value
    text = value
    for old, new in PUBLIC_TEXT_REPLACEMENTS:
        text = text.replace(old, new)
    return text


def validate_campaign_id(campaign_id: str) -> None:
    if not re.fullmatch(r"[a-z0-9][a-z0-9-]{2,79}", campaign_id):
        raise ValueError("campaign_id must be 3-80 chars of lowercase letters, numbers, and hyphens")
    risky_parts = {"secret", "token", "private", "internal"}
    if any(part in campaign_id for part in risky_parts):
        raise ValueError("campaign_id should not include private/security-sensitive words")


def scaffold_lanes(mode: str) -> list[dict[str, Any]]:
    shared = {
        "result_boundary": "computational_candidate",
        "runtime_gate": "operator_required_before_gpu_or_license_gated_execution",
    }
    if mode == "binder-design":
        return [
            {
                "id": "target-window-contract",
                "kind": "planning",
                "description": "Public accession, residue window, hotspots, and run boundaries.",
                **shared,
            },
            {
                "id": "generation-readiness",
                "kind": "gpu_prep",
                "description": "Binder generation lane setup with runtime-gated models and no committed outputs.",
                **shared,
            },
            {
                "id": "cofold-ranking",
                "kind": "model_comparison",
                "description": "Cofold and scoring contract for ranked generated candidates.",
                **shared,
            },
        ]
    if mode == "model-comparison":
        return [
            {
                "id": "model-inputs",
                "kind": "planning",
                "description": "Public model or structure inputs, quality metrics, and run boundaries.",
                **shared,
            },
            {
                "id": "comparison-contract",
                "kind": "model_comparison",
                "description": "Cross-tool scoring, disagreement, failure, and provenance contract.",
                **shared,
            },
        ]
    if mode == "structure-mapping":
        return [
            {
                "id": "accession-contract",
                "kind": "planning",
                "description": "Public accession, validation target, and artifact expectations.",
                **shared,
            },
            {
                "id": "mapping-report",
                "kind": "structure_mapping",
                "description": "Structure mapping report with figures, provenance, and next-step checks.",
                **shared,
            },
        ]
    if mode == "screening":
        return [
            {
                "id": "screening-contract",
                "kind": "planning",
                "description": "Public receptor/ligand scope, fanout estimate, and result boundaries.",
                **shared,
            },
            {
                "id": "shard-plan",
                "kind": "gpu_prep",
                "description": "Provider-neutral shard plan with budget, cleanup, and result schema gates.",
                **shared,
            },
        ]
    raise ValueError(f"unsupported scaffold mode: {mode}")


def scaffold_campaign(
    out_dir: Path,
    *,
    campaign_id: str,
    target_label: str,
    public_accession: str,
    window: str,
    mode: str = "binder-design",
    force: bool = False,
) -> dict[str, Any]:
    validate_campaign_id(campaign_id)
    mode = normalize_mode(mode)
    for name, value in {
        "target_label": target_label,
        "public_accession": public_accession,
        "window": window,
        "mode": mode,
    }.items():
        reject_public_unsafe_input(name, value)

    if out_dir.exists() and any(out_dir.iterdir()) and not force:
        raise ValueError(f"output directory is not empty: {out_dir}")
    out_dir.mkdir(parents=True, exist_ok=True)

    campaign = {
        "schema_version": 1,
        "campaign_id": campaign_id,
        "title": f"{target_label} {mode} campaign",
        "mode": mode,
        "result_boundary": "planning",
        "system": {
            "privacy": "public_or_synthetic_only",
            "repo_role": "control_plane",
        },
        "target": {
            "label": target_label,
            "public_accession": public_accession,
            "window": window,
            "source_policy": "public accession or synthetic fixture only",
        },
        "lanes": scaffold_lanes(mode),
        "expected_artifacts": [
            "target-window.json",
            "validation-notes.md",
            "stage-contract.json",
            "candidate-ranking.example.json or run-summary.md after outputs exist",
        ],
        "wet_lab_execution": False,
        "therapeutic_conclusions": False,
        "operator_gate_required_before_execution": True,
    }

    stage_contract = {
        "schema_version": 1,
        "campaign_id": campaign_id,
        "result_boundary": "computational_candidate",
        "fail_closed": True,
        "privacy": "public_or_synthetic_only",
        "operator_gate_required": True,
        "progress_ledger": "stage-progress.jsonl",
        "partial_success_policy": "Missing, partial, or unverifiable outputs must close as blocked or insufficient_support.",
        "stages": [
            {
                "id": lane["id"],
                "mode": lane["kind"],
                "required_artifacts": [],
                "success_support": "declared artifacts, hashes, validation output, and result boundary",
            }
            for lane in campaign["lanes"]
        ],
    }

    target_window = {
        "schema_version": 1,
        "campaign_id": campaign_id,
        "target_label": target_label,
        "public_accession": public_accession,
        "window": window,
        "privacy": "public_or_synthetic_only",
        "hotspots_or_regions": [],
        "source_notes": [
            "Add public-source citations, residue numbering notes, and uncertainty here.",
            "Do not add unpublished sequences, private structures, or generated candidate coordinates.",
        ],
    }

    readme = f"""# {target_label} Structure Factory Campaign

Campaign ID: `{campaign_id}`

This is a Structure Factory scaffold for `{mode}` work. It is a planning starter: manifests, stage contracts, run boundaries, and expected artifacts only.

## Public Inputs

- target: `{target_label}`
- public accession: `{public_accession}`
- window: `{window}`

## Result Boundary

Planning or computational-candidate outputs only. This scaffold does not establish binding, inhibition, selectivity, safety, efficacy, clinical relevance, or therapeutic value.

## Next Local Checks

```bash
bsf validate {out_dir.as_posix()}
bsf audit .
```

## Before Any GPU Or Provider Run

- replace placeholders with reviewed public-accession metadata
- declare expected artifacts and hashes
- confirm tool/license use context
- set budget, runtime cap, and cleanup policy
- keep credentials, provider IDs, private paths, generated structures, and logs outside git
"""

    validation_notes = f"""# Validation Notes

Campaign ID: `{campaign_id}`

| Statement | Status | Source Posture | Notes |
| --- | --- | --- | --- |
| Target/window selected for planning | draft | public_or_synthetic_only | Back this with public accession notes before execution. |
| Generated candidates bind or modulate target | not stated | insufficient_support | Requires downstream computational checks and experimental validation. |
| Therapeutic, safety, efficacy, or clinical value | not stated | insufficient_support | Out of scope for this repo. |
"""

    files = {
        "campaign-manifest.json": json.dumps(campaign, indent=2, sort_keys=True) + "\n",
        "stage-contract.json": json.dumps(stage_contract, indent=2, sort_keys=True) + "\n",
        "target-window.json": json.dumps(target_window, indent=2, sort_keys=True) + "\n",
        "README.md": readme,
        "validation-notes.md": validation_notes,
    }
    written: list[str] = []
    for name, content in files.items():
        path = out_dir / name
        path.write_text(content, encoding="utf-8")
        written.append(path.as_posix())

    ok, findings = validate_campaign(out_dir)
    return {
        "ok": ok,
        "campaign_dir": out_dir.as_posix(),
        "files": written,
        "findings": [finding.to_dict() for finding in findings],
    }


def iter_public_files(root: Path) -> list[Path]:
    files: list[Path] = []
    for current, dirs, names in os.walk(root):
        current_path = Path(current)
        kept_dirs: list[str] = []
        for name in dirs:
            path = current_path / name
            if path.is_symlink():
                files.append(path)
            elif name not in SKIP_DIRS:
                kept_dirs.append(name)
        dirs[:] = kept_dirs
        for name in names:
            path = current_path / name
            if path.is_symlink():
                files.append(path)
                continue
            if name in SKIP_DIRS or name == ".git":
                continue
            if path.is_file():
                files.append(path)
    return sorted(files)


def audit_tree(root: Path) -> tuple[bool, list[Finding]]:
    findings: list[Finding] = []
    for path in iter_public_files(root):
        rel = path.relative_to(root).as_posix()
        lowered_parts = [part.lower() for part in path.relative_to(root).parts]
        if path.is_symlink():
            findings.append(Finding("error", "symlink", rel, "symlinks are not allowed in the public export"))
            continue
        if any(rel.lower().startswith(prefix) for prefix in FORBIDDEN_PATH_PREFIXES):
            findings.append(Finding("error", "private-or-runtime-path", rel, "operator, runtime, or private work paths are not public artifacts"))
        if path.name.lower().endswith(".local.json"):
            findings.append(Finding("error", "local-artifact-file", rel, "local runtime JSON files are not public-release artifacts"))
        for part in lowered_parts:
            if part in FORBIDDEN_EXACT_NAME_PARTS or any(marker in part for marker in FORBIDDEN_NAME_SUBSTRINGS):
                findings.append(Finding("error", "forbidden-name", rel, f"forbidden public filename component: {part}"))
                break
        if path.suffix.lower() in FORBIDDEN_SUFFIXES:
            findings.append(Finding("error", "forbidden-generated-artifact", rel, f"generated/heavy artifact suffix is not public by default: {path.suffix}"))
        size = path.stat().st_size
        if size > 25_000_000:
            findings.append(Finding("error", "large-file", rel, f"file is too large for the public control-plane repo: {size} bytes"))
        if path.suffix.lower() not in TEXT_SUFFIXES:
            continue
        try:
            text = path.read_text(encoding="utf-8")
        except UnicodeDecodeError:
            findings.append(Finding("error", "non-text-file", rel, "file is not valid UTF-8 text"))
            continue
        for check_id, pattern in CONTENT_PATTERNS:
            match = pattern.search(text)
            if match:
                findings.append(Finding("error", check_id, rel, "matched a release-blocking pattern; value redacted"))
        if rel.startswith("runpod/bridge-manifests/"):
            for marker in ["base64 -d", "gunzip", "xz -d", '"approved_at": "20', "US-KS-"]:
                if marker in text:
                    findings.append(Finding("error", "launch-payload-or-approval", rel, f"public bridge manifest contains launch-only marker: {marker}"))
    ok = not any(finding.severity == "error" for finding in findings)
    return ok, findings


def validate_campaign(campaign_dir: Path) -> tuple[bool, list[Finding]]:
    findings: list[Finding] = []
    manifest_path = campaign_dir / "campaign-manifest.json"
    if not manifest_path.exists():
        return False, [Finding("error", "missing-manifest", str(manifest_path), "campaign-manifest.json is required")]
    try:
        manifest = read_json(manifest_path)
    except json.JSONDecodeError as exc:
        return False, [Finding("error", "invalid-json", str(manifest_path), str(exc))]

    rel_manifest = manifest_path.as_posix()
    campaign_id = manifest.get("campaign_id")
    if not isinstance(campaign_id, str) or not campaign_id:
        findings.append(Finding("error", "campaign-id", rel_manifest, "campaign_id must be a non-empty string"))
    result_boundary = get_result_boundary(manifest)
    if result_boundary not in PUBLIC_CAMPAIGN_RESULT_BOUNDARIES:
        findings.append(Finding("error", "result-boundary", rel_manifest, f"result_boundary must be one of {sorted(PUBLIC_CAMPAIGN_RESULT_BOUNDARIES)}"))
    privacy = manifest.get("system", {}).get("privacy")
    if privacy not in ALLOWED_PRIVACY:
        findings.append(Finding("error", "privacy", rel_manifest, f"system.privacy must be one of {sorted(ALLOWED_PRIVACY)}"))
    if manifest.get("wet_lab_execution") is not False:
        findings.append(Finding("error", "wet-lab-boundary", rel_manifest, "wet_lab_execution must be false in public examples"))
    if manifest.get("therapeutic_conclusions", manifest.get("therapeutic_claims")) is not False:
        findings.append(Finding("error", "therapeutic-boundary", rel_manifest, "therapeutic_conclusions must be false in public examples"))

    target = manifest.get("target", {})
    if not target.get("public_accession"):
        findings.append(Finding("error", "target-accession", rel_manifest, "target.public_accession is required"))
    if not target.get("window"):
        findings.append(Finding("error", "target-window", rel_manifest, "target.window is required"))

    lanes = manifest.get("lanes")
    if not isinstance(lanes, list) or not lanes:
        findings.append(Finding("error", "lanes", rel_manifest, "lanes[] must declare at least one planned lane"))
    else:
        for lane in lanes:
            lane_boundary = get_result_boundary(lane, legacy_key="claim_ceiling")
            if not lane_boundary:
                findings.append(Finding("error", "lane-result-boundary", rel_manifest, f"lane {lane.get('id', '<missing>')} needs result_boundary"))
            elif lane_boundary not in PUBLIC_CAMPAIGN_RESULT_BOUNDARIES:
                findings.append(Finding("error", "lane-result-boundary", rel_manifest, f"lane {lane.get('id', '<missing>')} result_boundary must be one of {sorted(PUBLIC_CAMPAIGN_RESULT_BOUNDARIES)}"))

    expected = manifest.get("expected_artifacts")
    if not isinstance(expected, list) or not expected:
        findings.append(Finding("error", "expected-artifacts", rel_manifest, "expected_artifacts[] is required"))

    stage_path = campaign_dir / "stage-contract.json"
    if stage_path.exists():
        try:
            stage_contract = read_json(stage_path)
            if stage_contract.get("fail_closed") is not True:
                findings.append(Finding("error", "stage-fail-closed", stage_path.as_posix(), "stage contract must declare fail_closed: true"))
            if not stage_contract.get("stages"):
                findings.append(Finding("error", "stage-list", stage_path.as_posix(), "stage contract must include stages[]"))
        except json.JSONDecodeError as exc:
            findings.append(Finding("error", "invalid-stage-json", stage_path.as_posix(), str(exc)))
    else:
        findings.append(Finding("warning", "missing-stage-contract", stage_path.as_posix(), "stage-contract.json is advised for GPU or long-running campaigns"))

    ranking_path = campaign_dir / "candidate-ranking.example.json"
    legacy_ranking_path = campaign_dir / "candidate-ranking.example.json"
    ranking_check_path = ranking_path if ranking_path.exists() else legacy_ranking_path
    if ranking_check_path.exists():
        try:
            ranking = read_json(ranking_check_path)
            candidates = ranking.get("candidates")
            if not isinstance(candidates, list):
                findings.append(Finding("error", "ranking-candidates", ranking_check_path.as_posix(), "candidate ranking must include candidates[]"))
            else:
                for candidate in candidates:
                    candidate_boundary = get_result_boundary(candidate)
                    if candidate_boundary not in PUBLIC_CAMPAIGN_RESULT_BOUNDARIES:
                        findings.append(Finding("error", "ranking-result-boundary", ranking_check_path.as_posix(), f"candidate {candidate.get('id')} has invalid result_boundary"))
                    if get_source_posture(candidate) not in ALLOWED_SOURCE_POSTURES:
                        findings.append(Finding("error", "ranking-source-posture", ranking_check_path.as_posix(), f"candidate {candidate.get('id')} needs valid source_posture"))
        except json.JSONDecodeError as exc:
            findings.append(Finding("error", "invalid-ranking-json", ranking_check_path.as_posix(), str(exc)))

    ok = not any(finding.severity == "error" for finding in findings)
    return ok, findings


def harness_check(root: Path) -> tuple[bool, list[Finding]]:
    findings: list[Finding] = []
    for rel in REQUIRED_HARNESS_FILES:
        path = root / rel
        if not path.exists():
            findings.append(Finding("error", "missing-harness-file", rel, "required public harness file is missing"))
        elif not path.is_file():
            findings.append(Finding("error", "harness-path-not-file", rel, "required public harness path is not a file"))

    for rel, needles in HARNESS_TEXT_REQUIREMENTS.items():
        path = root / rel
        if not path.exists() or not path.is_file():
            continue
        text = path.read_text(encoding="utf-8")
        for needle in needles:
            if needle not in text:
                findings.append(Finding("error", "missing-harness-language", rel, f"expected public harness language: {needle}"))

    for rel in [
        "skills/biosymphony-structure-factory/SKILL.md",
    ]:
        path = root / rel
        if not path.exists():
            continue
        text = path.read_text(encoding="utf-8")
        for match in re.finditer(r"`([^`]+\.md)`", text):
            target = match.group(1)
            if "://" in target or target.startswith("#"):
                continue
            candidate = path.parent / target if target.startswith("references/") else root / target
            if not candidate.exists():
                findings.append(Finding("error", "stale-skill-reference", rel, f"skill references missing markdown file: {target}"))

    pack_path = root / "packs/task-packs/binder-design-fast-path-v0/pack.yaml"
    if pack_path.exists():
        text = pack_path.read_text(encoding="utf-8")
        for needle in ["routing_label: sym:structure-factory", "result_boundary: computational_candidate", "issues:"]:
            if needle not in text:
                findings.append(Finding("error", "task-pack-contract", pack_path.relative_to(root).as_posix(), f"task pack missing: {needle}"))

    ok = not any(finding.severity == "error" for finding in findings)
    return ok, findings


def _relative_to(root: Path, path: Path) -> str:
    try:
        return path.relative_to(root).as_posix()
    except ValueError:
        return path.as_posix()


def _read_json_finding(path: Path, root: Path, findings: list[Finding]) -> Any | None:
    try:
        return read_json(path)
    except json.JSONDecodeError as exc:
        findings.append(Finding("error", "invalid-json", _relative_to(root, path), str(exc)))
    except OSError as exc:
        findings.append(Finding("error", "unreadable-file", _relative_to(root, path), str(exc)))
    return None


def _yaml_scalar(text: str, key: str) -> str | None:
    match = re.search(rf"(?m)^{re.escape(key)}:\s*(.+?)\s*$", text)
    if not match:
        return None
    value = match.group(1).strip()
    if value in {">", "|"}:
        return None
    return value.strip("\"'")


def _collect_issue_ids(text: str) -> list[str]:
    return sorted(set(re.findall(r"(?m)^\s*-\s+id:\s*([A-Za-z0-9_.-]+)\s*$", text)))


TASK_RECIPES: list[dict[str, Any]] = [
    {
        "task": "Create a Structure Factory campaign",
        "mode": "planning",
        "commands": [
            "bsf scaffold-campaign .runtime/my-demo --campaign-id my-demo --target-label '<public target>' --public-accession '<PDB:ID>' --window '<region>'",
            "bsf validate .runtime/my-demo",
        ],
        "outputs": [".runtime/my-demo/campaign-manifest.json", ".runtime/my-demo/stage-contract.json"],
        "remote_mutation": False,
    },
    {
        "task": "Render tracker-neutral Symphony or Linear task drafts",
        "mode": "planning",
        "commands": ["bsf issue-dry-run examples/pd-l1-binder-design-public --out .runtime/pd-l1-issues"],
        "outputs": [".runtime/pd-l1-issues/*.md"],
        "remote_mutation": False,
    },
    {
        "task": "Review the repo capability surface before assigning an agent",
        "mode": "review",
        "commands": ["bsf catalog . --format markdown", "make catalog-md"],
        "outputs": [".runtime/public-capability-catalog.md"],
        "remote_mutation": False,
    },
    {
        "task": "Translate a /goal request into an orchestrated work program",
        "mode": "orchestrator_companion",
        "commands": [
            "bsf catalog . --format markdown",
            "bsf scaffold-campaign .runtime/my-demo --campaign-id my-demo --target-label '<public target>' --public-accession '<PDB:ID>' --window '<region>'",
            "bsf issue-dry-run .runtime/my-demo --out .runtime/my-demo-issues",
        ],
        "outputs": ["campaign contract", "optional task drafts", "explicit assumptions and hard gates"],
        "remote_mutation": False,
    },
    {
        "task": "Run public-release checks without provider access",
        "mode": "release_review",
        "commands": ["make read-only-audit", "make public-switch-check"],
        "outputs": ["local validation logs", "ignored .runtime artifacts"],
        "remote_mutation": False,
    },
    {
        "task": "Prepare cloud or RunPod wave templates without launching",
        "mode": "cloud_prep",
        "commands": ["make runpod-public-template-check", "make launch-bundle"],
        "outputs": [".runtime/structure-factory-no-download-smoke"],
        "remote_mutation": False,
    },
]


def capability_catalog(root: Path) -> dict[str, Any]:
    """Build a machine-readable map of what this repo can help users do."""

    findings: list[Finding] = []
    root = root.resolve()

    campaign_modules: list[dict[str, Any]] = []
    for path in sorted((root / "modules" / "campaigns").glob("*.json")):
        data = _read_json_finding(path, root, findings)
        if not isinstance(data, dict):
            continue
        policies = data.get("policies") if isinstance(data.get("policies"), dict) else {}
        screening_defaults = data.get("screening_defaults") if isinstance(data.get("screening_defaults"), dict) else {}
        wave_plan = data.get("wave_plan") if isinstance(data.get("wave_plan"), dict) else {}
        providers = {
            str(item)
            for item in [
                *(screening_defaults.get("provider_priority") or []),
                *(wave.get("provider") for wave in wave_plan.values() if isinstance(wave, dict)),
            ]
            if item
        }
        if data.get("launch_manifests"):
            providers.add("runpod")
        campaign_modules.append(
            {
                "path": _relative_to(root, path),
                "campaign_id": data.get("campaign_id"),
                "family": public_text(data.get("campaign_family")),
                "run_profile": public_text(data.get("run_profile")),
                "objective": public_text(data.get("scientific_objective")),
                "lane_count": len(data.get("lane_modules") or []),
                "data_module_count": len(data.get("data_modules") or []),
                "stage_contract_count": len(data.get("stage_contracts") or []),
                "launch_manifest_count": len(data.get("launch_manifests") or []),
                "providers": sorted(providers),
                "result_boundary": public_text(
                    screening_defaults.get("result_boundary")
                    or policies.get("result_boundary")
                    or screening_defaults.get("claim_ceiling")
                    or policies.get("claim_ceiling")
                ),
                "operator_gate_signals": {
                    "allow_large_downloads": policies.get("allow_large_downloads"),
                    "allow_raw_cryoem_downloads": policies.get("allow_raw_cryoem_downloads"),
                    "allow_private_data": policies.get("allow_private_data"),
                    "license_gates": data.get("license_gates") or [],
                },
            }
        )

    example_campaigns: list[dict[str, Any]] = []
    examples_dir = root / "examples"
    if examples_dir.is_dir():
        for example_path in sorted(p for p in examples_dir.iterdir() if p.is_dir()):
            campaign_manifest = example_path / "campaign-manifest.json"
            screening_manifest = example_path / "screening-manifest.json"
            readme = example_path / "README.md"
            entry: dict[str, Any] = {
                "path": _relative_to(root, example_path),
                "campaign_id": example_path.name,
                "title": None,
                "mode": None,
                "result_boundary": None,
                "privacy": None,
                "target_label": None,
                "public_accession": None,
                "lane_count": 0,
                "expected_artifact_count": 0,
                "kind": "readme_only",
            }
            if campaign_manifest.exists():
                data = _read_json_finding(campaign_manifest, root, findings)
                if isinstance(data, dict):
                    system = data.get("system") if isinstance(data.get("system"), dict) else {}
                    target = data.get("target") if isinstance(data.get("target"), dict) else {}
                    entry.update(
                        {
                            "kind": "campaign_manifest",
                            "campaign_id": data.get("campaign_id") or example_path.name,
                            "title": public_text(data.get("title")),
                            "mode": public_text(data.get("mode")),
                            "result_boundary": public_text(get_result_boundary(data)),
                            "privacy": system.get("privacy"),
                            "target_label": public_text(target.get("label")),
                            "public_accession": target.get("public_accession"),
                            "lane_count": len(data.get("lanes") or []),
                            "expected_artifact_count": len(data.get("expected_artifacts") or []),
                        }
                    )
            elif screening_manifest.exists():
                data = _read_json_finding(screening_manifest, root, findings)
                if isinstance(data, dict):
                    intent = data.get("intent") if isinstance(data.get("intent"), dict) else {}
                    target = data.get("target") if isinstance(data.get("target"), dict) else {}
                    entry.update(
                        {
                            "kind": "screening_manifest",
                            "campaign_id": data.get("campaign_id") or example_path.name,
                            "title": public_text(intent.get("natural_language_goal") or target.get("name")),
                            "mode": public_text(intent.get("mode") or "screening"),
                            "result_boundary": public_text(intent.get("result_boundary") or intent.get("claim_ceiling")),
                            "target_label": public_text(target.get("name") or intent.get("target_hint")),
                        }
                    )
            if entry.get("title") is None and readme.exists():
                try:
                    for line in readme.read_text(encoding="utf-8").splitlines():
                        if line.startswith("# "):
                            entry["title"] = line[2:].strip()
                            break
                except OSError as exc:
                    findings.append(Finding("error", "unreadable-file", _relative_to(root, readme), str(exc)))
            example_campaigns.append(entry)

    stage_contracts: list[dict[str, Any]] = []
    for path in sorted((root / "runpod" / "stage-contracts").glob("*.json")):
        data = _read_json_finding(path, root, findings)
        if not isinstance(data, dict):
            continue
        stage_contracts.append(
            {
                "path": _relative_to(root, path),
                "contract_id": data.get("contract_id"),
                "manifest_id": data.get("manifest_id"),
                "execution_profile": public_text(data.get("execution_profile")),
                "stage_count": len(data.get("stages") or []),
                "fail_closed": data.get("fail_closed"),
                "success_summary": public_text(data.get("success_summary") or data.get("success_claim")),
            }
        )

    provider_profiles: list[dict[str, Any]] = []
    for path in sorted((root / "modules" / "provider-profiles").glob("**/*.json")):
        data = _read_json_finding(path, root, findings)
        if not isinstance(data, dict):
            continue
        provider_profiles.append(
            {
                "path": _relative_to(root, path),
                "provider": data.get("provider"),
                "profile_id": data.get("profile_id"),
                "maps_campaign_profile": data.get("maps_campaign_profile"),
                "operator_gate_required": data.get("operator_gate_required"),
                "execution_ready_requires": data.get("execution_ready_requires") or [],
            }
        )

    task_packs: list[dict[str, Any]] = []
    for path in sorted((root / "packs" / "task-packs").glob("*/pack.yaml")):
        try:
            text = path.read_text(encoding="utf-8")
        except OSError as exc:
            findings.append(Finding("error", "unreadable-file", _relative_to(root, path), str(exc)))
            continue
        task_packs.append(
            {
                "path": _relative_to(root, path),
                "pack_id": _yaml_scalar(text, "pack_id"),
                "title": _yaml_scalar(text, "title"),
                "routing_label": _yaml_scalar(text, "routing_label"),
                "result_boundary": _yaml_scalar(text, "result_boundary") or _yaml_scalar(text, "claim_ceiling"),
                "issue_count": len(_collect_issue_ids(text)),
                "issue_ids": _collect_issue_ids(text),
            }
        )

    recipes = [
        _relative_to(root, path)
        for path in sorted((root / "recipes").glob("*.md"))
        if path.name.lower() != "readme.md"
    ]

    checks = [
        {"id": "campaign-modules-present", "ok": bool(campaign_modules), "count": len(campaign_modules)},
        {"id": "examples-present", "ok": bool(example_campaigns), "count": len(example_campaigns)},
        {"id": "stage-contracts-present", "ok": bool(stage_contracts), "count": len(stage_contracts)},
        {"id": "provider-profiles-present", "ok": bool(provider_profiles), "count": len(provider_profiles)},
        {"id": "task-packs-present", "ok": bool(task_packs), "count": len(task_packs)},
        {"id": "recipes-present", "ok": bool(recipes), "count": len(recipes)},
    ]
    ok = not any(finding.severity == "error" for finding in findings) and all(check["ok"] for check in checks)

    return {
        "ok": ok,
        "root": root.as_posix(),
        "counts": {
            "campaign_modules": len(campaign_modules),
            "example_campaigns": len(example_campaigns),
            "stage_contracts": len(stage_contracts),
            "provider_profiles": len(provider_profiles),
            "task_packs": len(task_packs),
            "recipes": len(recipes),
            "task_recipes": len(TASK_RECIPES),
        },
        "checks": checks,
        "campaign_modules": campaign_modules,
        "example_campaigns": example_campaigns,
        "task_packs": task_packs,
        "stage_contracts": stage_contracts,
        "provider_profiles": provider_profiles,
        "recipes": recipes,
        "task_recipes": TASK_RECIPES,
        "entry_points": [
            "bsf catalog . --format markdown",
            "bsf scaffold-campaign .runtime/my-demo --campaign-id my-demo --target-label '<public target>' --public-accession '<PDB:ID>' --window '<region>'",
            "bsf issue-dry-run examples/pd-l1-binder-design-public --out .runtime/pd-l1-issues",
            "make runpod-public-template-check",
            "make public-switch-check",
        ],
        "findings": [finding.to_dict() for finding in findings],
    }


def _markdown_cell(value: Any) -> str:
    if value is None or value == "":
        return ""
    if isinstance(value, bool):
        text = "yes" if value else "no"
    elif isinstance(value, list):
        text = ", ".join(str(item) for item in value) if value else ""
    else:
        text = str(value)
    return text.replace("|", "\\|").replace("\n", " ")


def _markdown_table(headers: list[str], rows: list[list[Any]]) -> list[str]:
    if not rows:
        return ["_None found._"]
    lines = [
        "| " + " | ".join(headers) + " |",
        "| " + " | ".join("---" for _ in headers) + " |",
    ]
    for row in rows:
        lines.append("| " + " | ".join(_markdown_cell(value) for value in row) + " |")
    return lines


def catalog_markdown(catalog: dict[str, Any]) -> str:
    counts = catalog.get("counts") if isinstance(catalog.get("counts"), dict) else {}
    lines = [
        "# Structure Factory Capability Catalog",
        "",
        f"- status: `{'ok' if catalog.get('ok') else 'needs-attention'}`",
        f"- root: `{catalog.get('root', '')}`",
        f"- campaign modules: `{counts.get('campaign_modules', 0)}`",
        f"- public examples: `{counts.get('example_campaigns', 0)}`",
        f"- stage contracts: `{counts.get('stage_contracts', 0)}`",
        f"- provider profiles: `{counts.get('provider_profiles', 0)}`",
        f"- task packs: `{counts.get('task_packs', 0)}`",
        f"- recipes: `{counts.get('recipes', 0)}`",
        f"- task recipes: `{counts.get('task_recipes', 0)}`",
        "",
        "## Task Recipes",
        "",
    ]
    lines.extend(
        _markdown_table(
            ["Task", "Mode", "Commands", "Outputs", "Remote Mutation"],
            [
                [
                    item.get("task"),
                    item.get("mode"),
                    item.get("commands") or [],
                    item.get("outputs") or [],
                    item.get("remote_mutation"),
                ]
                for item in catalog.get("task_recipes", [])
                if isinstance(item, dict)
            ],
        )
    )
    lines.extend(
        [
            "",
            "## Campaign Modules",
            "",
        ]
    )
    lines.extend(
        _markdown_table(
            ["Campaign", "Family", "Providers", "Lanes", "Data Modules", "Launch Manifests", "Result Boundary", "Path"],
            [
                [
                    item.get("campaign_id"),
                    item.get("family"),
                    item.get("providers") or ["provider-neutral"],
                    item.get("lane_count"),
                    item.get("data_module_count"),
                    item.get("launch_manifest_count"),
                    item.get("result_boundary"),
                    item.get("path"),
                ]
                for item in catalog.get("campaign_modules", [])
                if isinstance(item, dict)
            ],
        )
    )
    lines.extend(["", "## Public Examples", ""])
    lines.extend(
        _markdown_table(
            ["Example", "Kind", "Mode", "Result Boundary", "Target Or Summary", "Path"],
            [
                [
                    item.get("campaign_id"),
                    item.get("kind"),
                    item.get("mode"),
                    item.get("result_boundary"),
                    item.get("target_label") or item.get("title"),
                    item.get("path"),
                ]
                for item in catalog.get("example_campaigns", [])
                if isinstance(item, dict)
            ],
        )
    )
    lines.extend(["", "## Task Packs", ""])
    lines.extend(
        _markdown_table(
            ["Pack", "Tasks", "Result Boundary", "Routing Label", "Path"],
            [
                [
                    item.get("pack_id"),
                    item.get("issue_count"),
                    item.get("result_boundary"),
                    item.get("routing_label"),
                    item.get("path"),
                ]
                for item in catalog.get("task_packs", [])
                if isinstance(item, dict)
            ],
        )
    )
    lines.extend(["", "## Stage Contracts", ""])
    lines.extend(
        _markdown_table(
            ["Contract", "Profile", "Stages", "Fail Closed", "Path"],
            [
                [
                    item.get("contract_id"),
                    item.get("execution_profile"),
                    item.get("stage_count"),
                    item.get("fail_closed"),
                    item.get("path"),
                ]
                for item in catalog.get("stage_contracts", [])
                if isinstance(item, dict)
            ],
        )
    )
    lines.extend(["", "## Provider Profiles", ""])
    lines.extend(
        _markdown_table(
            ["Provider", "Profile", "Operator Gate", "Execution Ready Requires", "Path"],
            [
                [
                    item.get("provider"),
                    item.get("profile_id"),
                    item.get("operator_gate_required"),
                    item.get("execution_ready_requires") or [],
                    item.get("path"),
                ]
                for item in catalog.get("provider_profiles", [])
                if isinstance(item, dict)
            ],
        )
    )
    lines.extend(["", "## Starter Commands", ""])
    entry_points = catalog.get("entry_points") if isinstance(catalog.get("entry_points"), list) else []
    if entry_points:
        lines.extend(f"- `{command}`" for command in entry_points)
    else:
        lines.append("_None found._")

    findings = catalog.get("findings") if isinstance(catalog.get("findings"), list) else []
    if findings:
        lines.extend(["", "## Findings", ""])
        lines.extend(
            f"- `{item.get('severity', 'unknown')}` `{item.get('check_id', 'unknown')}` "
            f"`{item.get('path', '')}`: {item.get('message', '')}"
            for item in findings
            if isinstance(item, dict)
        )

    return "\n".join(lines) + "\n"


def repo_relative(path: Path) -> str:
    try:
        return path.relative_to(Path.cwd().resolve()).as_posix()
    except ValueError:
        return path.as_posix()


def render_issue(
    campaign: dict[str, Any],
    issue_id: str,
    title: str,
    owned_paths: list[str],
    acceptance: list[str],
    campaign_path: str,
    dependency: str = "none",
) -> str:
    campaign_id = campaign["campaign_id"]
    target = campaign.get("target", {})
    artifacts = "\n".join(f"- `{campaign_path}/{item}`" for item in campaign.get("expected_artifacts", []))
    owned = "\n".join(f"- `{campaign_path}/{path}` - owned by this issue" for path in owned_paths)
    criteria = "\n".join(f"- [ ] {item}" for item in acceptance)
    schema_touched = "\n".join(f"  - {campaign_path}/{path}" for path in owned_paths)
    stage_contract = f"{campaign_path}/stage-contract.json"
    return f"""# {issue_id}: {title}

## Summary

Prepare one scoped slice of `{campaign_id}` for agent execution, review, or tracker import. This draft is provider-neutral until an operator explicitly authorizes local, cloud, or RunPod execution.

## Inputs

- campaign ID: `{campaign_id}`
- subgroup: `structure-factory`
- routing label: `sym:structure-factory`
- target: `{target.get("label", "unknown")}`
- public accession: `{target.get("public_accession", "unknown")}`
- target window: `{target.get("window", "unknown")}`
- result boundary: `computational_candidate`

## Expected Artifacts

{artifacts}

## Stage / Progress Contract

- stage contract: `{stage_contract}`
- artifact granularity: `per-campaign`
- progress ledger: `.runtime/{campaign_id}/{issue_id}/stage-progress.jsonl`
- resume command: `PYTHONPATH=src python3 -m biosymphony_structure_factory.cli validate {campaign_path}`
- partial success policy: blocked, failed, or incomplete lanes must close honestly instead of marking success.

## Provider / Execution Profile

- provider: `provider-neutral`
- execution profile: `other`
- setup posture: `n/a`
- writable volume/env: `n/a`
- operator gate required: `no`

## Tooling / License Posture

- tools: `Structure Factory public CLI`
- posture: `open-default`
- current primary source checked: `no external install required for this dry-run draft`
- intended use context: `public planning`
- image/runtime action: `n/a`
- operator action required: `none for planning; explicit authorization before paid cloud execution`

## Acceptance Criteria

{criteria}

## Validation Commands

```bash
PYTHONPATH=src python3 -m biosymphony_structure_factory.cli validate {campaign_path}
PYTHONPATH=src python3 -m biosymphony_structure_factory.cli audit .
```

## Final Outcome Contract

- worker lane: `codex`
- closeout state: `In Review`
- final comment must include: `<!-- symphony-outcome -->`
- source posture: `report_only`
- result boundary: `planning`
- artifact packet: `.runtime/{campaign_id}/{issue_id}`
- hash ledger: `n/a`
- cost report: `n/a`
- cleanup proof: `n/a`
- success requires: validation commands pass and any provider execution remains separately authorized.

## Touched Areas

{owned}

## Dependencies

Blocked by: {dependency}

## Risk Notes

- Computational candidate outputs only.
- No wet-lab, binding, therapeutic, safety, or clinical conclusions.
- GPU execution requires separate operator authorization, budget, cleanup policy, and runtime license/use-context review.

## Complexity

tier: medium

<!-- symphony:schema
schema_version: 1
subgroup: structure-factory
campaign_id: {campaign_id}
routing_label: sym:structure-factory
issue_id: {issue_id}
touched_areas:
{schema_touched}
complexity: medium
result_boundary: computational_candidate
-->
	"""


IssueSpec = tuple[str, str, list[str], list[str]]


def issue_plan_for_campaign(campaign: dict[str, Any]) -> list[IssueSpec]:
    mode = normalize_mode(campaign.get("mode", "binder-design"))
    if mode == "binder-design":
        return [
            (
                "BSF-BINDER-W00",
                "Target Window And Run Boundaries",
                ["campaign-manifest.json", "target-window.json", "validation-notes.md"],
                ["Target accession and residue window are explicit.", "Result boundary is computational candidate.", "No private data is referenced."],
            ),
            (
                "BSF-BINDER-W01",
                "Generation Lane Readiness",
                ["campaign-manifest.json", "stage-contract.json"],
                ["Generation lanes name runtime gates and use-context caveats.", "Operator-gated tools are marked before execution."],
            ),
            (
                "BSF-BINDER-W02",
                "Cofold Ranking Contract",
                ["candidate-ranking.example.json", "stage-contract.json"],
                ["Candidate ranking schema validates.", "Top-candidate ranking is not treated as binding proof."],
            ),
            (
                "BSF-BINDER-W03",
                "Report And Review",
                ["README.md", "validation-notes.md"],
                ["Public report stays inside the stated run boundary.", "Failed or partial lanes close honestly instead of marking success."],
            ),
        ]
    if mode == "model-comparison":
        return [
            (
                "BSF-MODEL-W00",
                "Model Input And Run Boundaries",
                ["campaign-manifest.json", "target-window.json", "validation-notes.md"],
                ["Compared models or structures are public or synthetic.", "Run boundaries are explicit."],
            ),
            (
                "BSF-MODEL-W01",
                "Method Disagreement And Failure Rows",
                ["stage-contract.json", "candidate-ranking.example.json"],
                ["Comparison rows preserve method disagreement.", "Failures and blocked rows are represented instead of dropped."],
            ),
            (
                "BSF-MODEL-W02",
                "Review Report",
                ["README.md", "validation-notes.md"],
                ["Report separates tool outputs from interpretation.", "Unsupported validation or binding statements are absent."],
            ),
        ]
    if mode == "structure-mapping":
        return [
            (
                "BSF-MAP-W00",
                "Accession And Structure Scope",
                ["campaign-manifest.json", "target-window.json", "validation-notes.md"],
                ["Public accession and entity/window are explicit.", "Raw-data or reconstruction work is handed off instead of owned here."],
            ),
            (
                "BSF-MAP-W01",
                "Validation And Figure Plan",
                ["stage-contract.json", "target-window.json"],
                ["Expected validation artifacts are listed.", "Figures are planned as report artifacts, not standalone proof."],
            ),
            (
                "BSF-MAP-W02",
                "Mapping Report And Review",
                ["README.md", "validation-notes.md"],
                ["Report states provenance and review conditions.", "Missing or partial outputs close as blocked or insufficient_support."],
            ),
        ]
    if mode == "screening":
        return [
            (
                "BSF-SCREEN-W00",
                "Scope Fanout And Run Boundaries",
                ["campaign-manifest.json", "target-window.json", "validation-notes.md"],
                ["Receptor/ligand scope is public or synthetic.", "Fanout and cost-bearing work require an operator gate."],
            ),
            (
                "BSF-SCREEN-W01",
                "Shard And Provider Prep Contract",
                ["stage-contract.json", "campaign-manifest.json"],
                ["Shard boundaries and expected ledgers are explicit.", "Provider prep remains non-launching until authorized."],
            ),
            (
                "BSF-SCREEN-W02",
                "Results Schema And Candidate Reports",
                ["stage-contract.json", "validation-notes.md"],
                ["Result tables preserve failures and method disagreement.", "Candidate reports stay computational_candidate or lower."],
            ),
            (
                "BSF-SCREEN-W03",
                "Active Learning And Closeout",
                ["README.md", "validation-notes.md"],
                ["Follow-on tranche criteria are stated.", "Partial, fixture, or dry-run outputs are labeled honestly."],
            ),
        ]
    raise ValueError(f"unsupported campaign mode for issue dry-run: {mode}")


def issue_dry_run(campaign_dir: Path, out_dir: Path) -> dict[str, Any]:
    ok, findings = validate_campaign(campaign_dir)
    if not ok:
        return {"ok": False, "findings": [finding.to_dict() for finding in findings]}
    campaign = read_json(campaign_dir / "campaign-manifest.json")
    campaign_path = repo_relative(campaign_dir)
    out_dir.mkdir(parents=True, exist_ok=True)
    issues = issue_plan_for_campaign(campaign)
    written: list[str] = []
    previous_issue = "none"
    for issue_id, title, owned_paths, acceptance in issues:
        filename = f"{issue_id}-{title.lower().replace(' ', '-')}.md"
        path = out_dir / filename
        path.write_text(
            render_issue(campaign, issue_id, title, owned_paths, acceptance, campaign_path, previous_issue),
            encoding="utf-8",
        )
        written.append(path.as_posix())
        previous_issue = issue_id
    return {"ok": True, "issue_count": len(written), "issues": written}


def cmd_audit(args: argparse.Namespace) -> int:
    root = Path(args.root).resolve()
    ok, findings = audit_tree(root)
    write_json({"ok": ok, "root": root.as_posix(), "finding_count": len(findings), "findings": [finding.to_dict() for finding in findings]})
    return 0 if ok else 1


def cmd_validate(args: argparse.Namespace) -> int:
    campaign_dir = Path(args.campaign_dir).resolve()
    ok, findings = validate_campaign(campaign_dir)
    write_json({"ok": ok, "campaign_dir": campaign_dir.as_posix(), "finding_count": len(findings), "findings": [finding.to_dict() for finding in findings]})
    return 0 if ok else 1


def cmd_issue_dry_run(args: argparse.Namespace) -> int:
    result = issue_dry_run(Path(args.campaign_dir).resolve(), Path(args.out).resolve())
    write_json(result)
    return 0 if result.get("ok") else 1


def cmd_harness_check(args: argparse.Namespace) -> int:
    root = Path(args.root).resolve()
    ok, findings = harness_check(root)
    write_json({"ok": ok, "root": root.as_posix(), "finding_count": len(findings), "findings": [finding.to_dict() for finding in findings]})
    return 0 if ok else 1


def cmd_catalog(args: argparse.Namespace) -> int:
    result = capability_catalog(Path(args.root).resolve())
    if args.format == "markdown":
        rendered = catalog_markdown(result)
        if args.out:
            out = Path(args.out).resolve()
            out.parent.mkdir(parents=True, exist_ok=True)
            out.write_text(rendered, encoding="utf-8")
        print(rendered, end="")
        return 0 if result.get("ok") else 1

    if args.out:
        out = Path(args.out).resolve()
        out.parent.mkdir(parents=True, exist_ok=True)
        out.write_text(json.dumps(result, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    write_json(result)
    return 0 if result.get("ok") else 1


def cmd_scaffold_campaign(args: argparse.Namespace) -> int:
    try:
        result = scaffold_campaign(
            Path(args.out_dir).resolve(),
            campaign_id=args.campaign_id,
            target_label=args.target_label,
            public_accession=args.public_accession,
            window=args.window,
            mode=args.mode,
            force=args.force,
        )
    except ValueError as exc:
        write_json({"ok": False, "error": str(exc)})
        return 2
    write_json(result)
    return 0 if result.get("ok") else 1


def cmd_doctor(args: argparse.Namespace) -> int:
    root = Path(args.root).resolve()
    example = (root / args.example).resolve()
    checks: list[dict[str, Any]] = []

    harness_ok, harness_findings = harness_check(root)
    checks.append(
        {
            "id": "harness-check",
            "ok": harness_ok,
            "finding_count": len(harness_findings),
            "findings": [finding.to_dict() for finding in harness_findings],
        }
    )

    audit_ok, audit_findings = audit_tree(root)
    checks.append(
        {
            "id": "public-audit",
            "ok": audit_ok,
            "finding_count": len(audit_findings),
            "findings": [finding.to_dict() for finding in audit_findings],
        }
    )

    validate_ok, validate_findings = validate_campaign(example)
    checks.append(
        {
            "id": "example-validate",
            "ok": validate_ok,
            "campaign_dir": example.as_posix(),
            "finding_count": len(validate_findings),
            "findings": [finding.to_dict() for finding in validate_findings],
        }
    )

    ok = all(check["ok"] for check in checks)
    write_json(
        {
            "ok": ok,
            "root": root.as_posix(),
            "example": example.as_posix(),
            "checks": checks,
            "next_commands": [
                "bsf catalog .",
                "bsf catalog . --format markdown",
                "bsf scaffold-campaign .runtime/my-target-demo --campaign-id my-target-demo --target-label '<public target>' --public-accession '<PDB:ID>' --window '<residue window>'",
                "bsf issue-dry-run examples/pd-l1-binder-design-public --out .runtime/pd-l1-issues",
                "make public-switch-check",
            ],
        }
    )
    return 0 if ok else 1


def _binder_workspace(args: argparse.Namespace) -> Path:
    return Path(getattr(args, "workspace", ".")).resolve()


def _binder_input(workspace: Path, value: str, label: str) -> Path:
    return binder_lane.contained_path(workspace, value, label, must_exist=True)


def _binder_command(callable_: Any) -> int:
    try:
        result = callable_()
    except (
        binder_controller.BinderControllerError,
        binder_lane.BinderLaneError,
        binder_controls.BinderControlError,
        binder_execution_prep.BinderExecutionPreparationError,
        binder_executor.BinderExecutorError,
        binder_receipts.BinderReceiptError,
        remote_tool_contract.RemoteToolContractError,
        target_verifier.TargetVerificationError,
    ) as exc:
        write_json(
            {
                "ok": False,
                "error": str(exc),
                "failure": remediation.failure_record(exc),
                "provider_calls": 0,
            }
        )
        return 2
    except OSError as exc:
        sanitized = OSError("local file operation failed")
        write_json(
            {
                "ok": False,
                "error": str(sanitized),
                "failure": remediation.failure_record(sanitized),
                "provider_calls": 0,
            }
        )
        return 2
    except Exception as exc:
        sanitized = ValueError("invalid binder-lane input")
        write_json(
            {
                "ok": False,
                "error": str(sanitized),
                "failure": remediation.failure_record(sanitized),
                "provider_calls": 0,
            }
        )
        return 2
    write_json(result)
    return 0 if result.get("ok", True) else 1


def cmd_binder_lane_menu(args: argparse.Namespace) -> int:
    def operation() -> dict[str, Any]:
        workspace = _binder_workspace(args)
        ledger = binder_lane.read_json(_binder_input(workspace, args.ledger, "capability ledger"))
        return {"ok": True, **binder_lane.menu(ledger, workspace)}

    return _binder_command(operation)


def cmd_binder_lane_plan_request(args: argparse.Namespace) -> int:
    def operation() -> dict[str, Any]:
        workspace = _binder_workspace(args)
        request = binder_lane.read_json(_binder_input(workspace, args.request, "request"))
        ledger = binder_lane.read_json(_binder_input(workspace, args.ledger, "capability ledger"))
        result = binder_lane.plan_request(
            request,
            ledger,
            workspace,
            request_ref=args.request,
            ledger_ref=args.ledger,
        )
        if args.out:
            out = binder_lane.runtime_path(workspace, args.out, "plan output")
            binder_lane.write_json(out, result)
        return {"ok": True, **result}

    return _binder_command(operation)


def cmd_binder_lane_plan(args: argparse.Namespace) -> int:
    def operation() -> dict[str, Any]:
        workspace = _binder_workspace(args)
        plan = binder_lane.read_json(_binder_input(workspace, args.plan, "plan"))
        run_root = binder_lane.runtime_path(workspace, args.out, "run root")
        result = binder_lane.materialize_plan(plan, run_root, workspace)
        return {**result, "run_root": Path(args.out).as_posix()}

    return _binder_command(operation)


def cmd_binder_lane_preflight(args: argparse.Namespace) -> int:
    def operation() -> dict[str, Any]:
        workspace = _binder_workspace(args)
        run_root = binder_lane.runtime_path(workspace, args.run_root, "run root", must_exist=True)
        return binder_lane.preflight(run_root, workspace)

    return _binder_command(operation)


def cmd_binder_lane_run(args: argparse.Namespace) -> int:
    def operation() -> dict[str, Any]:
        workspace = _binder_workspace(args)
        run_root = binder_lane.runtime_path(workspace, args.run_root, "run root", must_exist=True)
        report = binder_lane.run_synthetic(run_root, workspace)
        return {
            "ok": True,
            "round_id": report["round_id"],
            "result_boundary": report["result_boundary"],
            "candidate_count": report["candidate_count"],
            "provider_calls": 0,
            "report": (Path(args.run_root) / "round-report.json").as_posix(),
        }

    return _binder_command(operation)


def cmd_binder_lane_report(args: argparse.Namespace) -> int:
    def operation() -> dict[str, Any]:
        workspace = _binder_workspace(args)
        run_root = binder_lane.runtime_path(workspace, args.run_root, "run root", must_exist=True)
        return binder_lane.report_summary(run_root, workspace)

    return _binder_command(operation)


def cmd_binder_lane_round_decision(args: argparse.Namespace) -> int:
    def operation() -> dict[str, Any]:
        workspace = _binder_workspace(args)
        plan = binder_lane.read_json(_binder_input(workspace, args.plan, "plan"))
        history_path = binder_lane.runtime_path(
            workspace,
            args.history,
            "round closeout history",
            must_exist=True,
        )
        history = binder_lane.read_json(history_path)
        if args.calibration:
            calibration_path = _binder_input(workspace, args.calibration, "control calibration")
            calibration_bytes = calibration_path.read_bytes()
            calibration = json.loads(calibration_bytes)
            history = binder_controls.bind_round_history(
                plan,
                history,
                calibration,
                binder_controls.sha256_bytes(calibration_bytes),
            )
        result = binder_lane.round_decision(plan, history)
        if args.out:
            out = binder_lane.runtime_path(workspace, args.out, "round decision output")
            binder_lane.write_json(out, result)
        return {"ok": True, **result}

    return _binder_command(operation)


def _control_observations(path: Path) -> list[dict[str, Any]]:
    """Load control observations from a JSON list or JSONL file."""
    if path.suffix == ".jsonl":
        rows: list[dict[str, Any]] = []
        for number, line in enumerate(path.read_text(encoding="utf-8").splitlines(), start=1):
            if not line.strip():
                continue
            value = json.loads(line)
            if not isinstance(value, dict):
                raise binder_controls.BinderControlError(
                    f"control observations line {number} must be an object"
                )
            rows.append(value)
        return rows
    value = binder_lane.read_json(path)
    if not isinstance(value, list):
        raise binder_controls.BinderControlError(
            "control observations must be a JSON list or JSONL object rows"
        )
    return value


def cmd_binder_lane_calibrate_controls(args: argparse.Namespace) -> int:
    def operation() -> dict[str, Any]:
        workspace = _binder_workspace(args)
        panel = binder_lane.read_json(_binder_input(workspace, args.panel, "control panel"))
        if args.adopt:
            adopted = binder_lane.read_json(_binder_input(workspace, args.adopt, "adopted calibration"))
            result = binder_controls.adopt_calibration(panel, adopted)
        else:
            observations_path = _binder_input(workspace, args.observations, "control observations")
            result = binder_controls.derive_calibration(
                panel,
                _control_observations(observations_path),
            )
        out = binder_lane.runtime_path(workspace, args.out, "control calibration output")
        binder_lane.write_json(out, result)
        artifact_sha256 = binder_controls.sha256_bytes(out.read_bytes())
        return {
            "ok": result["round_decision_ready"],
            "status": result["status"],
            "scope_id": result["scope_id"],
            "selected_metric_id": result["selected_metric_id"],
            "calibration_state": result["calibration_state"],
            "calibration_artifact": out.relative_to(workspace).as_posix(),
            "calibration_artifact_sha256": artifact_sha256,
            "readiness": result["readiness"],
            "provider_calls": 0,
        }

    return _binder_command(operation)


def cmd_binder_lane_adapters(args: argparse.Namespace) -> int:
    def operation() -> dict[str, Any]:
        workspace = _binder_workspace(args)
        registry = binder_lane.read_json(_binder_input(workspace, args.registry, "adapter registry"))
        validated = binder_executor.validate_registry(registry)
        adapters = []
        for adapter in validated["adapters"]:
            adapters.append(
                {
                    "id": adapter["id"],
                    "tool_id": adapter["tool_id"],
                    "roles": adapter["roles"],
                    "implementation_status": adapter["implementation_status"],
                    "execution_kind": adapter["execution_kind"],
                    "program": adapter["program"],
                    "network_policy": adapter["network_policy"],
                    "license_gate": adapter["license_gate"],
                    "required_environment_names": adapter["required_environment_names"],
                    "placeholders": adapter["placeholders"],
                    "expected_outputs": adapter["expected_outputs"],
                }
            )
        return {
            "ok": True,
            "registry": Path(args.registry).as_posix(),
            "adapter_count": len(adapters),
            "adapters": adapters,
            "runtime_extensions": ".runtime adapter registries may add or replace safe local argv adapters",
            "provider_calls": 0,
        }

    return _binder_command(operation)


def cmd_binder_lane_prepare_execution(args: argparse.Namespace) -> int:
    def operation() -> dict[str, Any]:
        workspace = _binder_workspace(args)
        plan_path = _binder_input(workspace, args.plan, "binder plan")
        plan = binder_lane.validate_plan(binder_lane.read_json(plan_path), workspace)
        target_path = binder_lane.runtime_path(
            workspace,
            args.target_report,
            "target verification report",
            must_exist=True,
        )
        target = binder_lane.read_json(target_path)
        registry = binder_lane.read_json(_binder_input(workspace, args.registry, "adapter registry"))
        settings: dict[str, Any] = {}
        if args.stage_settings:
            settings_path = binder_lane.runtime_path(
                workspace,
                args.stage_settings,
                "execution stage settings",
                must_exist=True,
            )
            settings_payload = binder_lane.read_json(settings_path)
            if not isinstance(settings_payload, dict):
                raise binder_execution_prep.BinderExecutionPreparationError(
                    "execution stage settings must be a JSON object"
                )
            settings = settings_payload
        stages = args.stages.split(",") if args.stages else None
        result, request = binder_execution_prep.prepare_execution(
            plan,
            target,
            registry,
            plan_sha256=binder_lane.sha256_path(plan_path),
            target_report_sha256=binder_lane.sha256_path(target_path),
            selected_stages=stages,
            stage_settings=settings,
        )
        request_path = None
        if request is not None:
            output = binder_lane.runtime_path(workspace, args.out, "controller request")
            binder_lane.write_json(output, request)
            request_path = output.relative_to(workspace).as_posix()
        readiness_path = None
        if args.readiness_out:
            output = binder_lane.runtime_path(
                workspace,
                args.readiness_out,
                "execution readiness result",
            )
            binder_lane.write_json(output, {**result, "controller_request": request_path})
            readiness_path = output.relative_to(workspace).as_posix()
        return {
            **result,
            "controller_request": request_path,
            "readiness_result": readiness_path,
        }

    return _binder_command(operation)


def cmd_binder_lane_adapter(args: argparse.Namespace) -> int:
    def operation() -> dict[str, Any]:
        workspace = _binder_workspace(args)
        registry = binder_lane.read_json(_binder_input(workspace, args.registry, "adapter registry"))
        bindings: dict[str, Any] = {}
        if args.bindings:
            bindings_path = binder_lane.runtime_path(workspace, args.bindings, "adapter bindings", must_exist=True)
            bindings_payload = binder_lane.read_json(bindings_path)
            if not isinstance(bindings_payload, dict):
                raise binder_executor.BinderExecutorError("adapter bindings must be a JSON object")
            bindings = bindings_payload
        run_root = binder_lane.runtime_path(workspace, args.run_root, "adapter run root")
        authorization = (
            binder_executor.LOCAL_EXECUTION_AUTHORIZATION if args.authorize_local_execution else None
        )
        return binder_executor.run_adapter(
            registry,
            args.adapter_id,
            workspace_root=workspace,
            runtime_root=run_root,
            bindings=bindings,
            operation=args.operation,
            authorization=authorization,
            dry_run=args.dry_run,
            timeout_seconds=args.timeout_seconds,
        )

    return _binder_command(operation)


def cmd_binder_lane_execute(args: argparse.Namespace) -> int:
    def operation() -> dict[str, Any]:
        workspace = _binder_workspace(args)
        request = binder_lane.read_json(_binder_input(workspace, args.request, "controller request"))
        registry = binder_lane.read_json(_binder_input(workspace, args.registry, "adapter registry"))
        plan = _binder_input(workspace, args.plan, "binder plan")
        binder_lane.validate_plan(binder_lane.read_json(plan), workspace)
        run_root = binder_lane.runtime_path(workspace, args.run_root, "controller run root")
        return binder_controller.run_controller(
            request,
            registry,
            workspace_root=workspace,
            runtime_root=run_root,
            plan_sha256=binder_lane.sha256_path(plan),
            authorization=(binder_controller.AUTHORIZATION if args.authorize_local_execution else None),
            authorize_network=args.authorize_network,
            authorize_license_gates=args.authorize_license_gates,
            dry_run=args.dry_run,
        )

    return _binder_command(operation)


def cmd_binder_lane_closeout(args: argparse.Namespace) -> int:
    def operation() -> dict[str, Any]:
        workspace = _binder_workspace(args)
        run_root = binder_lane.runtime_path(workspace, args.run_root, "stage run root", must_exist=True)
        declarations_path = binder_lane.runtime_path(
            workspace, args.declarations, "artifact declarations", must_exist=True
        )
        declarations = binder_lane.read_json(declarations_path)
        if not isinstance(declarations, list):
            raise binder_receipts.BinderReceiptError("artifact declarations must be a JSON list")
        ledger = binder_receipts.create_artifact_ledger(
            run_root,
            args.stage_id,
            args.artifact_root,
            declarations,
        )
        ledger_path = binder_receipts.write_artifact_ledger(run_root, args.ledger_path, ledger)
        receipt = binder_receipts.create_stage_receipt(
            run_root,
            args.stage_id,
            args.result_boundary,
            args.exit_code,
            ledger,
            requested_state=args.requested_state,
        )
        receipt_path = binder_receipts.write_stage_receipt(run_root, args.receipt_path, receipt)
        return {
            "ok": receipt["execution_state"] == "completed",
            "stage_id": receipt["stage_id"],
            "execution_state": receipt["execution_state"],
            "result_boundary": receipt["result_boundary"],
            "expected_output_count": receipt["expected_output_count"],
            "found_output_count": receipt["found_output_count"],
            "ledger": ledger_path.relative_to(workspace).as_posix(),
            "receipt": receipt_path.relative_to(workspace).as_posix(),
            "provider_calls": 0,
        }

    return _binder_command(operation)


def _remote_tool_operations(workspace: Path, operations_path: str | None) -> dict[str, Any] | None:
    if operations_path is None:
        return None
    payload = binder_lane.read_json(_binder_input(workspace, operations_path, "remote operation registry"))
    if not isinstance(payload, dict):
        raise remote_tool_contract.RemoteToolContractError("remote operation registry must be a JSON object")
    return payload


def cmd_binder_lane_remote_request(args: argparse.Namespace) -> int:
    def operation() -> dict[str, Any]:
        workspace = _binder_workspace(args)
        request = binder_lane.read_json(_binder_input(workspace, args.request, "remote tool request"))
        registry = _remote_tool_operations(workspace, args.operations)
        validated = remote_tool_contract.validate_request(request, tool_operations=registry)
        if args.out:
            output = binder_lane.runtime_path(workspace, args.out, "validated remote request")
            binder_lane.write_json(output, validated)
        return {
            "ok": True,
            "contract_id": validated["contract_id"],
            "request_id": validated["request_id"],
            "provider_id": validated["provider_id"],
            "tool_id": validated["tool_id"],
            "operation": validated["operation"],
            "validated_request": args.out,
            "provider_calls": 0,
        }

    return _binder_command(operation)


def cmd_binder_lane_remote_receipt(args: argparse.Namespace) -> int:
    def operation() -> dict[str, Any]:
        workspace = _binder_workspace(args)
        request = binder_lane.read_json(_binder_input(workspace, args.request, "remote tool request"))
        receipt = binder_lane.read_json(_binder_input(workspace, args.receipt, "remote tool receipt"))
        registry = _remote_tool_operations(workspace, args.operations)
        validated = remote_tool_contract.validate_receipt(receipt, request, tool_operations=registry)
        if args.out:
            output = binder_lane.runtime_path(workspace, args.out, "validated remote receipt")
            binder_lane.write_json(output, validated)
        return {
            "ok": True,
            "contract_id": validated["contract_id"],
            "request_id": validated["request_id"],
            "status": validated["status"],
            "artifact_count": len(validated["artifacts"]),
            "cleanup_verified": validated["cleanup"]["verified"],
            "validated_receipt": args.out,
            "provider_calls": 0,
        }

    return _binder_command(operation)


def cmd_binder_lane_target_check(args: argparse.Namespace) -> int:
    def operation() -> dict[str, Any]:
        workspace = _binder_workspace(args)
        plan_path = _binder_input(workspace, args.plan, "binder plan")
        plan = binder_lane.validate_plan(binder_lane.read_json(plan_path), workspace)
        site = plan["target"]["site"]
        if args.chain is not None and args.chain != site["chain_id"]:
            raise target_verifier.TargetVerificationError(
                "--chain differs from plan target.site.chain_id; use the exact plan site"
            )
        if args.required_residues is not None:
            selected = target_verifier.parse_residue_selections(args.required_residues)
            planned = target_verifier.parse_residue_selections(
                ",".join(site["required_residues"])
            )
            if selected != planned:
                raise target_verifier.TargetVerificationError(
                    "--required-residues differs from plan target.site.required_residues; use the exact plan site"
                )
        structure = _binder_input(workspace, args.structure, "target structure")
        expected_sequence = None
        if args.expected_sequence_file:
            sequence_path = _binder_input(workspace, args.expected_sequence_file, "expected sequence")
            expected_sequence = sequence_path.read_text(encoding="utf-8")
        result = target_verifier.verify_target(
            structure,
            target_contract=plan["target"],
            plan_sha256=binder_lane.sha256_path(plan_path),
            expected_sequence=expected_sequence,
            sequence_basis=args.sequence_basis,
        )
        if args.out:
            output = binder_lane.runtime_path(workspace, args.out, "target verification report")
            binder_lane.write_json(output, result)
        return {**result, "report": args.out}

    return _binder_command(operation)


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(prog="bsf", description="BioSymphony Structure Factory public validator")
    subparsers = parser.add_subparsers(dest="command", required=True)

    audit = subparsers.add_parser("audit", help="scan a repo tree for release blockers")
    audit.add_argument("root", nargs="?", default=".")
    audit.set_defaults(func=cmd_audit)

    validate = subparsers.add_parser("validate", help="validate a public Structure Factory campaign example")
    validate.add_argument("campaign_dir")
    validate.set_defaults(func=cmd_validate)

    dry_run = subparsers.add_parser("issue-dry-run", help="render tracker-neutral Symphony/Linear task drafts")
    dry_run.add_argument("campaign_dir")
    dry_run.add_argument("--out", required=True)
    dry_run.set_defaults(func=cmd_issue_dry_run)

    harness = subparsers.add_parser("harness-check", help="verify public BioSymphony agentic harness entry points")
    harness.add_argument("root", nargs="?", default=".")
    harness.set_defaults(func=cmd_harness_check)

    catalog = subparsers.add_parser("catalog", help="summarize available campaigns, examples, task templates, and provider contracts")
    catalog.add_argument("root", nargs="?", default=".")
    catalog.add_argument("--format", choices=["json", "markdown"], default="json", help="output format")
    catalog.add_argument("--out", help="optional path to also write the rendered catalog")
    catalog.set_defaults(func=cmd_catalog)

    scaffold = subparsers.add_parser("scaffold-campaign", help="create a starter campaign skeleton")
    scaffold.add_argument("out_dir")
    scaffold.add_argument("--campaign-id", required=True, help="lowercase slug, e.g. pd-l1-binder-public")
    scaffold.add_argument("--target-label", required=True, help="human-readable target label")
    scaffold.add_argument("--public-accession", required=True, help="public accession or synthetic fixture label")
    scaffold.add_argument("--window", required=True, help="residue/window/region description")
    scaffold.add_argument(
        "--mode",
        choices=CAMPAIGN_MODES,
        default="binder-design",
    )
    scaffold.add_argument("--force", action="store_true", help="allow writing into a non-empty output directory")
    scaffold.set_defaults(func=cmd_scaffold_campaign)

    doctor = subparsers.add_parser("doctor", help="run local public harness, audit, and example validation checks")
    doctor.add_argument("root", nargs="?", default=".")
    doctor.add_argument("--example", default="examples/pd-l1-binder-design-public", help="repo-relative campaign example to validate")
    doctor.set_defaults(func=cmd_doctor)

    binder = subparsers.add_parser(
        "binder-lane",
        help="plan, run, and close a provider-neutral binder round",
    )
    binder_commands = binder.add_subparsers(dest="binder_command", required=True)

    binder_menu = binder_commands.add_parser("menu", help="show public binder-lane choices and evidence levels")
    binder_menu.add_argument("--workspace", default=".")
    binder_menu.add_argument("--ledger", default="references/binder-lane-capability-ledger.json")
    binder_menu.set_defaults(func=cmd_binder_lane_menu)

    binder_request = binder_commands.add_parser("plan-request", help="validate a public request and resolve its tool choices")
    binder_request.add_argument("request")
    binder_request.add_argument("--workspace", default=".")
    binder_request.add_argument("--ledger", default="references/binder-lane-capability-ledger.json")
    binder_request.add_argument("--out")
    binder_request.set_defaults(func=cmd_binder_lane_plan_request)

    binder_plan = binder_commands.add_parser("plan", help="materialize a public round contract")
    binder_plan.add_argument("plan")
    binder_plan.add_argument("--workspace", default=".")
    binder_plan.add_argument("--out", required=True, help="workspace-relative run directory")
    binder_plan.set_defaults(func=cmd_binder_lane_plan)

    binder_preflight = binder_commands.add_parser("preflight", help="check a materialized round without provider calls")
    binder_preflight.add_argument("--workspace", default=".")
    binder_preflight.add_argument("run_root", help="workspace-relative run directory")
    binder_preflight.set_defaults(func=cmd_binder_lane_preflight)

    binder_run = binder_commands.add_parser(
        "run",
        help="write synthetic stage files, a report, and hashes; makes no provider calls",
    )
    binder_run.add_argument("--workspace", default=".")
    binder_run.add_argument("run_root", help="workspace-relative run directory")
    binder_run.set_defaults(func=cmd_binder_lane_run)

    binder_report = binder_commands.add_parser("report", help="verify hashes and print the small public round summary")
    binder_report.add_argument("--workspace", default=".")
    binder_report.add_argument("run_root", help="workspace-relative run directory")
    binder_report.set_defaults(func=cmd_binder_lane_report)

    binder_decision = binder_commands.add_parser(
        "round-decision",
        help="evaluate a closed round against its metric, budget, stopping rule, and round limit",
    )
    binder_decision.add_argument("plan")
    binder_decision.add_argument("--workspace", default=".")
    binder_decision.add_argument(
        "--history",
        required=True,
        help="workspace-relative JSON history below .runtime/",
    )
    binder_decision.add_argument(
        "--calibration",
        help="workspace-relative ready control calibration to bind to measured metric provenance",
    )
    binder_decision.add_argument("--out", help="workspace-relative decision JSON below .runtime/")
    binder_decision.set_defaults(func=cmd_binder_lane_round_decision)

    binder_calibration = binder_commands.add_parser(
        "calibrate-controls",
        help="derive or adopt measured-control gates without provider calls",
    )
    binder_calibration.add_argument("panel")
    binder_calibration.add_argument("--workspace", default=".")
    calibration_source = binder_calibration.add_mutually_exclusive_group(required=True)
    calibration_source.add_argument(
        "--observations",
        help="workspace-relative JSON or JSONL control observations",
    )
    calibration_source.add_argument(
        "--adopt",
        help="workspace-relative adopted gate record",
    )
    binder_calibration.add_argument(
        "--out",
        required=True,
        help="workspace-relative calibration JSON below .runtime/",
    )
    binder_calibration.set_defaults(func=cmd_binder_lane_calibrate_controls)

    binder_adapters = binder_commands.add_parser(
        "adapters",
        help="validate and list bundled or runtime binder adapters",
    )
    binder_adapters.add_argument("--workspace", default=".")
    binder_adapters.add_argument("--registry", default="references/binder-execution-adapters.json")
    binder_adapters.set_defaults(func=cmd_binder_lane_adapters)

    binder_prepare = binder_commands.add_parser(
        "prepare-execution",
        help="map selected plan stages to runnable adapters and write a controller request",
    )
    binder_prepare.add_argument("plan", help="workspace-relative validated binder plan")
    binder_prepare.add_argument(
        "--target-report",
        required=True,
        help="workspace-relative target verification report below .runtime/",
    )
    binder_prepare.add_argument("--workspace", default=".")
    binder_prepare.add_argument(
        "--registry",
        default="references/binder-execution-adapters.json",
    )
    binder_prepare.add_argument(
        "--stage-settings",
        help="optional selector-to-adapter settings JSON below .runtime/",
    )
    binder_prepare.add_argument(
        "--stages",
        help="optional comma-separated stage subset in plan order",
    )
    binder_prepare.add_argument(
        "--out",
        required=True,
        help="controller request path below .runtime/; written only when ready",
    )
    binder_prepare.add_argument(
        "--readiness-out",
        help="optional readiness-result path below .runtime/",
    )
    binder_prepare.set_defaults(func=cmd_binder_lane_prepare_execution)

    binder_adapter = binder_commands.add_parser(
        "adapter",
        help="check or run one local adapter through the fixed-argument executor",
    )
    binder_adapter.add_argument("adapter_id")
    binder_adapter.add_argument("--workspace", default=".")
    binder_adapter.add_argument("--registry", default="references/binder-execution-adapters.json")
    binder_adapter.add_argument("--run-root", required=True, help="workspace-relative directory below .runtime/")
    binder_adapter.add_argument("--bindings", help="workspace-relative JSON object below .runtime/")
    binder_adapter.add_argument("--operation", choices=["readiness", "run"], default="run")
    binder_adapter.add_argument("--dry-run", action="store_true", help="validate and write a receipt without starting a process")
    binder_adapter.add_argument(
        "--authorize-local-execution",
        action="store_true",
        help="grant this command permission to start the selected local program",
    )
    binder_adapter.add_argument("--timeout-seconds", type=int, default=300)
    binder_adapter.set_defaults(func=cmd_binder_lane_adapter)

    binder_execute = binder_commands.add_parser(
        "execute",
        help="run a hash-bound local adapter stage graph and write a controller receipt",
    )
    binder_execute.add_argument("request", help="workspace-relative controller request JSON")
    binder_execute.add_argument("--plan", required=True, help="workspace-relative hash-bound binder plan")
    binder_execute.add_argument("--workspace", default=".")
    binder_execute.add_argument("--registry", default="references/binder-execution-adapters.json")
    binder_execute.add_argument("--run-root", required=True, help="workspace-relative directory below .runtime/")
    binder_execute.add_argument("--dry-run", action="store_true", help="write readiness receipts without starting a process")
    binder_execute.add_argument(
        "--authorize-local-execution",
        action="store_true",
        help="grant this command permission to start every declared local adapter",
    )
    binder_execute.add_argument(
        "--authorize-network",
        action="store_true",
        help="grant network access to adapters whose contract requires runtime review",
    )
    binder_execute.add_argument(
        "--authorize-license-gates",
        action="store_true",
        help="confirm that the declared use passed its required license and terms review",
    )
    binder_execute.set_defaults(func=cmd_binder_lane_execute)

    binder_closeout = binder_commands.add_parser(
        "closeout",
        help="count and hash declared stage outputs, then write a sanitized receipt",
    )
    binder_closeout.add_argument("--workspace", default=".")
    binder_closeout.add_argument("run_root", help="workspace-relative directory below .runtime/")
    binder_closeout.add_argument("--stage-id", required=True)
    binder_closeout.add_argument("--artifact-root", required=True, help="run-root-relative output directory")
    binder_closeout.add_argument("--declarations", required=True, help="workspace-relative JSON list below .runtime/")
    binder_closeout.add_argument("--exit-code", type=int, required=True)
    binder_closeout.add_argument(
        "--result-boundary",
        choices=sorted(binder_receipts.RESULT_BOUNDARIES),
        default="computational_candidate",
    )
    binder_closeout.add_argument(
        "--requested-state",
        choices=sorted(binder_receipts.EXECUTION_STATES),
        default="completed",
    )
    binder_closeout.add_argument("--ledger-path", default="receipts/artifact-ledger.json")
    binder_closeout.add_argument("--receipt-path", default="receipts/stage-receipt.json")
    binder_closeout.set_defaults(func=cmd_binder_lane_closeout)

    binder_remote_request = binder_commands.add_parser(
        "remote-request",
        help="validate a fixed provider-neutral tool request without starting a provider job",
    )
    binder_remote_request.add_argument("request", help="workspace-relative request JSON")
    binder_remote_request.add_argument("--workspace", default=".")
    binder_remote_request.add_argument(
        "--operations",
        help="optional workspace-relative tool-to-operation registry JSON",
    )
    binder_remote_request.add_argument("--out", help="optional normalized request path below .runtime/")
    binder_remote_request.set_defaults(func=cmd_binder_lane_remote_request)

    binder_remote_receipt = binder_commands.add_parser(
        "remote-receipt",
        help="validate and join a sanitized provider receipt to its exact request",
    )
    binder_remote_receipt.add_argument("receipt", help="workspace-relative receipt JSON")
    binder_remote_receipt.add_argument("--request", required=True, help="workspace-relative request JSON")
    binder_remote_receipt.add_argument("--workspace", default=".")
    binder_remote_receipt.add_argument(
        "--operations",
        help="optional workspace-relative tool-to-operation registry JSON",
    )
    binder_remote_receipt.add_argument("--out", help="optional normalized receipt path below .runtime/")
    binder_remote_receipt.set_defaults(func=cmd_binder_lane_remote_receipt)

    binder_target_check = binder_commands.add_parser(
        "target-check",
        help="verify a PDB or mmCIF against the exact plan target and site",
    )
    binder_target_check.add_argument("structure", help="workspace-relative PDB or mmCIF file")
    binder_target_check.add_argument(
        "--plan",
        required=True,
        help="workspace-relative validated binder plan that declares target.site",
    )
    binder_target_check.add_argument("--workspace", default=".")
    binder_target_check.add_argument(
        "--chain",
        help="optional consistency check against plan target.site.chain_id",
    )
    binder_target_check.add_argument(
        "--required-residues",
        help="optional consistency check against the plan site, for example 19-127,130A",
    )
    binder_target_check.add_argument(
        "--expected-sequence-file",
        help="optional workspace-relative one-letter sequence file",
    )
    binder_target_check.add_argument(
        "--sequence-basis",
        choices=["coordinates", "entity"],
        default="coordinates",
        help="compare the expected sequence with modeled coordinates or the deposited entity record",
    )
    binder_target_check.add_argument("--out", help="optional verification report path below .runtime/")
    binder_target_check.set_defaults(func=cmd_binder_lane_target_check)

    return parser


def main(argv: list[str] | None = None) -> int:
    parser = build_parser()
    args = parser.parse_args(argv)
    return int(args.func(args))


if __name__ == "__main__":
    raise SystemExit(main())
