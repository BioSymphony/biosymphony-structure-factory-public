#!/usr/bin/env python3
"""Compile natural-language structure requests into conservative manifests.

The compiler is intentionally local and conservative. It extracts only simple
operator intent from the prompt, then records everything else as a gate or a
planning assumption instead of silently enabling data downloads, paid compute,
or restricted tools.
"""

from __future__ import annotations

import argparse
import json
import re
from pathlib import Path
from typing import Any


DEFAULT_PROVIDER_PRIORITY = ["runpod", "aws_batch", "neocloud_gpu_pod"]
GATED_TOOL_POSTURES = {
    "alphafold3": {
        "aliases": ["alphafold3", "alphafold 3", "alpha fold 3", "af3"],
        "posture": "runtime-gated",
        "blocker": "AlphaFold 3 requires explicit terms/use-context review and runtime access before execution",
    },
    "phenix": {
        "aliases": ["phenix"],
        "posture": "runtime-gated",
        "blocker": "Phenix requires license/use-context confirmation before execution",
    },
    "chimerax": {
        "aliases": ["chimerax", "chimera x", "isolde"],
        "posture": "runtime-gated",
        "blocker": "ChimeraX/ISOLDE requires operator-confirmed runtime access before execution",
    },
    "cryosparc": {
        "aliases": ["cryosparc", "cryo-sparc"],
        "posture": "runtime-gated",
        "blocker": "CryoSPARC requires an operator-owned license and runtime configuration before execution",
    },
    "rosetta": {
        "aliases": ["rosetta", "pyrosetta"],
        "posture": "runtime-gated",
        "blocker": "Rosetta/PyRosetta requires license/use-context confirmation before execution",
    },
    "motioncor2": {
        "aliases": ["motioncor2"],
        "posture": "runtime-gated",
        "blocker": "MotionCor2 binary use requires current UCSF terms and runtime access confirmation",
    },
    "gnina": {
        "aliases": ["gnina"],
        "posture": "review-required",
        "blocker": "GNINA remains review-required until the exact build/dependency license posture is recorded",
    },
    "diffdock": {
        "aliases": ["diffdock", "diff dock"],
        "posture": "review-required",
        "blocker": "DiffDock requires current code/model/dependency terms review before execution",
    },
    "chai": {
        "aliases": ["chai", "chai-1", "chai1"],
        "posture": "review-required",
        "blocker": "Chai requires current repository and weight terms review for the intended use context",
    },
}

OPEN_METHOD_ALIASES = {
    "rdkit": ["rdkit"],
    "autodock_vina": ["vina", "autodock vina", "autodock-vina"],
    "boltz": ["boltz", "boltz-2", "boltz2"],
}


def compact_ws(value: str) -> str:
    return re.sub(r"\s+", " ", value).strip()


def slugify(value: str, fallback: str = "intent", max_len: int = 54) -> str:
    slug = re.sub(r"[^a-z0-9]+", "-", value.lower()).strip("-")
    if not slug:
        slug = fallback
    return slug[:max_len].strip("-") or fallback


def display_number(value: float) -> int | float:
    return int(value) if value.is_integer() else value


def first_number(patterns: list[str], text: str) -> tuple[float | None, str | None]:
    for pattern in patterns:
        match = re.search(pattern, text, flags=re.IGNORECASE)
        if match:
            return float(match.group(1)), match.group(0)
    return None, None


def extract_budget(prompt: str) -> dict[str, Any]:
    text = prompt.lower()
    no_paid = bool(
        re.search(
            r"\b(no paid|zero spend|no spend|free only|local only|dry[- ]run|no[- ]download|no download|\$0)\b",
            text,
        )
    )
    spend, spend_phrase = first_number(
        [
            r"\$\s*(\d+(?:\.\d+)?)",
            r"(?:budget|max spend|spend cap|cost cap)\s*(?:of|is|:)?\s*(?:usd\s*)?(\d+(?:\.\d+)?)\s*(?:usd|dollars?)",
            r"(?:under|less than|up to)\s*(?:usd\s*)?(\d+(?:\.\d+)?)\s*(?:usd|dollars?)",
            r"(\d+(?:\.\d+)?)\s*(?:usd|dollars?)",
        ],
        prompt,
    )
    if no_paid:
        spend = 0.0
    elif spend is None:
        spend = 0.0

    ligand_k, ligand_k_phrase = first_number(
        [r"\b(\d+(?:\.\d+)?)\s*k\s*(?:ligands|compounds|molecules|fragments)\b"],
        prompt,
    )
    ligand_count, ligand_phrase = first_number(
        [
            r"\b(?:max|up to|under|limit(?:ed)? to|screen)\s+(\d+)\s*(?:ligands|compounds|molecules|fragments)\b",
            r"\b(\d+)\s*(?:ligands|compounds|molecules|fragments)\b",
        ],
        prompt,
    )
    if ligand_k is not None:
        max_ligands = max(1, int(ligand_k * 1000))
        ligand_source = ligand_k_phrase
    elif ligand_count is not None:
        max_ligands = max(1, int(ligand_count))
        ligand_source = ligand_phrase
    else:
        max_ligands = 5
        ligand_source = "default no-download fixture cap"

    hours, hours_phrase = first_number([r"\b(\d+(?:\.\d+)?)\s*(?:hours?|hrs?|hr|h)\b"], prompt)
    minutes, minutes_phrase = first_number([r"\b(\d+(?:\.\d+)?)\s*(?:minutes?|mins?|min)\b"], prompt)
    if hours is not None:
        max_runtime_minutes = max(1, int(hours * 60))
        runtime_source = hours_phrase
    elif minutes is not None:
        max_runtime_minutes = max(1, int(minutes))
        runtime_source = minutes_phrase
    else:
        max_runtime_minutes = 10
        runtime_source = "default no-download fixture cap"

    top_n, top_n_phrase = first_number([r"\btop\s+(\d+)\b", r"\bpromote\s+(\d+)\b"], prompt)

    return {
        "max_ligands": max_ligands,
        "max_spend_usd": display_number(spend),
        "max_runtime_minutes": max_runtime_minutes,
        "scale_soon_after_canaries": spend > 0,
        "promote_top_n": int(top_n) if top_n is not None else 2,
        "requested_paid_compute": spend > 0,
        "extracted_phrases": {
            "spend": spend_phrase or ("explicit zero-spend phrase" if no_paid else "default zero-spend fixture"),
            "ligands": ligand_source,
            "runtime": runtime_source,
            "top_n": top_n_phrase or "default top-N report cap",
        },
    }


def extract_provider_plan(prompt: str, budget: dict[str, Any]) -> dict[str, Any]:
    text = prompt.lower()
    providers: list[str] = []
    provider_phrases: dict[str, str] = {}
    provider_patterns = [
        ("runpod", r"\brunpod\b"),
        ("aws_batch", r"\baws(?: batch)?\b"),
        ("neocloud_gpu_pod", r"\bneo[- ]?cloud\b"),
        ("local_workstation", r"\b(local|workstation|laptop|cpu only|cpu-only)\b"),
        ("ssh_hpc", r"\b(ssh|hpc|slurm)\b"),
        ("generic_cloud_vm", r"\b(generic cloud|cloud vm|gpu vm|vm)\b"),
    ]
    for provider, pattern in provider_patterns:
        match = re.search(pattern, text)
        if match:
            providers.append(provider)
            provider_phrases[provider] = match.group(0)

    if "local_workstation" in providers and len(providers) == 1:
        priority = ["local_workstation"]
    elif providers:
        priority = providers + [provider for provider in DEFAULT_PROVIDER_PRIORITY if provider not in providers]
    else:
        priority = list(DEFAULT_PROVIDER_PRIORITY)

    requested_paid_provider = any(
        provider in providers
        for provider in {"runpod", "aws_batch", "neocloud_gpu_pod", "generic_cloud_vm"}
    )
    return {
        "priority": priority,
        "selected_provider_hint": priority[0],
        "provider_mentions": provider_phrases,
        "operator_gate_required_for_paid_compute": bool(
            budget["requested_paid_compute"] or requested_paid_provider
        ),
        "requested_paid_provider": requested_paid_provider,
    }


def extract_tool_blockers(prompt: str) -> list[dict[str, str]]:
    text = prompt.lower()
    blockers: list[dict[str, str]] = []
    for tool, spec in GATED_TOOL_POSTURES.items():
        aliases = spec["aliases"]
        for alias in aliases:
            if re.search(rf"(?<![a-z0-9]){re.escape(alias)}(?![a-z0-9])", text):
                blockers.append(
                    {
                        "tool": tool,
                        "matched_phrase": alias,
                        "posture": spec["posture"],
                        "status": "blocked_until_operator_review",
                        "blocker": spec["blocker"],
                    }
                )
                break
    return blockers


def extract_open_methods(prompt: str) -> list[str]:
    text = prompt.lower()
    requested: list[str] = []
    for method, aliases in OPEN_METHOD_ALIASES.items():
        if any(alias in text for alias in aliases):
            requested.append(method)
    return requested


def detect_mode(prompt: str) -> str:
    text = prompt.lower()
    if re.search(r"\b(openbind|calibrat|redocking|re-docking|cross[- ]docking|affinity benchmark)\b", text):
        return "openbind_calibration"
    if re.search(r"\b(disagreement|disagree|discordant|discordance|method ranking|model ranking|consensus|compare methods)\b", text):
        return "method_disagreement"
    return "screen"


def extract_screening_target(prompt: str) -> dict[str, Any]:
    cleaned = compact_ws(
        re.sub(
            r"\b(?:under|less than|up to|max spend|budget|on runpod|via runpod|on aws|via aws|on neocloud|local only)\b.*$",
            "",
            prompt,
            flags=re.IGNORECASE,
        )
    )
    target = cleaned
    ligand_hint = "user-supplied or fixture ligand library"
    patterns = [
        r"\b(?:screen|dock|rank)\s+(?P<ligand>.+?)\s+(?:against|on|for)\s+(?P<target>.+)$",
        r"\b(?:against|on|for)\s+(?P<target>.+?)(?:\s+(?:with|using)\s+|$)",
        r"\bscreen\s+(?P<target>[A-Za-z][A-Za-z0-9_.+-]*)\s+(?P<ligand>inhibitors|agonists|antagonists|binders|ligands|fragments|compounds)\b",
        r"\b(?:against|on|for)\s+(?P<target>[A-Za-z0-9_.+ -]+)$",
    ]
    for pattern in patterns:
        match = re.search(pattern, cleaned, flags=re.IGNORECASE)
        if match:
            target = compact_ws(match.group("target"))
            ligand_hint = compact_ws(match.groupdict().get("ligand") or ligand_hint)
            break
    if target.lower().startswith(("screen ", "dock ", "rank ")):
        target = compact_ws(re.sub(r"^(screen|dock|rank)\s+", "", target, flags=re.IGNORECASE))
    target = compact_ws(
        re.sub(
            r"\s+\b(?:with|using)\b\s+(?:rdkit|vina|autodock(?:[- ]vina)?|boltz(?:-?2)?|gnina|diffdock|alphafold\s*3|af3|chai|phenix|chimerax|cryosparc).*$",
            "",
            target,
            flags=re.IGNORECASE,
        )
    )
    return {
        "target_hint": target or prompt,
        "ligand_hint": ligand_hint,
        "target_id": slugify(target or prompt, fallback="compiled-target", max_len=40),
    }


def blocked_until(tool_blockers: list[dict[str, str]], budget: dict[str, Any]) -> list[str]:
    gates = []
    if budget["requested_paid_compute"]:
        gates.append("explicit operator approval for paid compute, max spend, runtime cap, artifact pull, and cleanup policy")
    else:
        gates.append("operator gate for paid compute before any non-fixture provider run")
    gates.append("explicit input materialization plan before downloading public raw data or private data")
    gates.extend(blocker["blocker"] for blocker in tool_blockers)
    return gates


def base_constraints(prompt: str) -> dict[str, Any]:
    budget = extract_budget(prompt)
    provider_plan = extract_provider_plan(prompt, budget)
    tool_blockers = extract_tool_blockers(prompt)
    open_methods = extract_open_methods(prompt)
    return {
        "budget": budget,
        "provider_plan": provider_plan,
        "tool_blockers": tool_blockers,
        "requested_open_methods": open_methods,
        "blocked_until": blocked_until(tool_blockers, budget),
    }


def screening_manifest(prompt: str, mode: str = "screen") -> dict[str, Any]:
    constraints = base_constraints(prompt)
    budget = constraints["budget"]
    provider_plan = constraints["provider_plan"]
    target = extract_screening_target(prompt)
    execution_profile = {
        "screen": "screening-no-download-smoke",
        "openbind_calibration": "screening-no-download-smoke",
        "method_disagreement": "screening-wide-docking",
    }.get(mode, "screening-no-download-smoke")
    natural_mode = {
        "screen": "screen",
        "openbind_calibration": "openbind_calibration",
        "method_disagreement": "method_disagreement_review",
    }.get(mode, mode)
    methods = {
        "always": ["stdlib_descriptor_proxy", "simple_affinity_baselines"],
        "wide_pass": ["rdkit", "autodock_vina"],
        "focused": ["boltz"],
        "gated": ["gnina", "diffdock", "alphafold3", "chai", "phenix", "chimerax", "cryosparc"],
        "requested_open_methods": constraints["requested_open_methods"],
        "requested_gated_or_review_tools": [
            {"tool": blocker["tool"], "posture": blocker["posture"], "status": blocker["status"]}
            for blocker in constraints["tool_blockers"]
        ],
    }
    manifest: dict[str, Any] = {
        "schema_version": 1,
        "manifest_type": "screening_manifest",
        "campaign_id": "screening-superpowers",
        "run_id": f"compiled-{slugify(target['target_hint'], fallback='screening')}-{natural_mode}",
        "intent": {
            "mode": natural_mode,
            "natural_language_goal": prompt,
            "target_hint": target["target_hint"],
            "ligand_hint": target["ligand_hint"],
            "claim_ceiling": "candidate",
        },
        "target": {
            "target_id": target["target_id"],
            "name": target["target_hint"],
            "allowed_sources": ["public_accessions", "user_supplied_public_safe_manifest"],
            "private_data_allowed": False,
        },
        "ligand_library": {
            "path": "examples/screening-superpowers/ligand-library.json",
            "stable_id_field": "ligand_id",
            "format": "json",
            "placeholder_until_user_library_supplied": True,
        },
        "receptor_ensemble": {
            "path": "examples/screening-superpowers/receptor-ensemble.json",
            "site_definition_required": True,
            "placeholder_until_target_materialized": True,
        },
        "methods": methods,
        "provider_plan": {
            **provider_plan,
            "execution_profile": execution_profile,
            "operator_gate_for_gated_tools": False,
            "current_run_is_no_download_fixture": not budget["requested_paid_compute"],
        },
        "budget": {
            "max_ligands": budget["max_ligands"],
            "max_spend_usd": budget["max_spend_usd"],
            "max_runtime_minutes": budget["max_runtime_minutes"],
            "scale_soon_after_canaries": budget["scale_soon_after_canaries"],
        },
        "outputs": {
            "artifact_contract": "modules/artifact-contracts/screening-results.v1.json",
            "candidate_report_contract": "modules/artifact-contracts/candidate-report.v1.json",
            "promote_top_n": budget["promote_top_n"],
        },
        "policies": {
            "allow_private_data": False,
            "allow_large_downloads": False,
            "allow_raw_cryoem_downloads": False,
            "expected_download_bytes": 0,
            "prediction_only_claim_level": "candidate",
        },
        "blocked_until": constraints["blocked_until"],
        "tool_blockers": constraints["tool_blockers"],
        "extracted_constraints": constraints,
    }
    if mode == "openbind_calibration":
        manifest["calibration"] = {
            "style": "OpenBind-inspired",
            "purpose": "calibrate structure-based ranking before scale-up; not a binding claim",
            "slices": ["redocking", "cross_docking", "cofolding", "affinity_prediction"],
            "required_controls": ["known actives", "known inactives or decoys", "held-out structures when available"],
            "reporting": [
                "simple baseline comparison",
                "per-slice rank correlation",
                "method disagreement ledger",
                "failure and missing-evidence ledger",
            ],
        }
    elif mode == "method_disagreement":
        manifest["disagreement_query"] = {
            "purpose": "surface candidates where methods disagree enough to require review",
            "compare_methods": ["descriptor_proxy", "simple_affinity_baselines", "autodock_vina", "boltz"],
            "selection_policy": "promote top hits, low-confidence hits, and high-disagreement cases separately",
            "do_not_treat_single_model_score_as_truth": True,
            "minimum_report_columns": [
                "ligand_id",
                "method_scores",
                "rank_delta",
                "pose_or_confidence_flags",
                "recommended_follow_up",
            ],
        }
    return manifest


def compile_prompt(prompt: str) -> dict[str, Any]:
    mode = detect_mode(prompt)
    return screening_manifest(prompt, mode=mode)


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--prompt", required=True)
    parser.add_argument("--out", type=Path, required=True)
    parser.add_argument("--json", action="store_true")
    args = parser.parse_args()

    manifest = compile_prompt(args.prompt)
    args.out.parent.mkdir(parents=True, exist_ok=True)
    args.out.write_text(json.dumps(manifest, indent=2, sort_keys=True) + "\n")
    summary = {
        "ok": True,
        "out": str(args.out.resolve()),
        "manifest_type": manifest["manifest_type"],
        "mode": manifest["intent"]["mode"],
        "claim_ceiling": manifest["intent"]["claim_ceiling"],
        "provider_priority": manifest.get("provider_plan", {}).get("priority", []),
        "tool_blockers": len(manifest.get("tool_blockers", [])),
    }
    if args.json:
        print(json.dumps(summary, indent=2, sort_keys=True))
    else:
        print(f"ok: {summary['ok']}")
        print(f"out: {summary['out']}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
