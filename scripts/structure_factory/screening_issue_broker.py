#!/usr/bin/env python3
"""Emit dry-run Linear issue drafts for the screening uplift campaign.

The broker writes Markdown only. It does not call Linear or any provider API.
Existing files are left untouched unless --force is supplied.
"""

from __future__ import annotations

import argparse
import json
from dataclasses import dataclass
from pathlib import Path
from typing import Any

try:  # Support direct script execution and package-style imports.
    from structure_intent_compile import compact_ws, compile_prompt, slugify
except ImportError:  # pragma: no cover - used only when imported as package.
    from scripts.structure_factory.structure_intent_compile import compact_ws, compile_prompt, slugify


@dataclass(frozen=True)
class IssueDraft:
    wave: str
    slug: str
    target_state: str
    summary: str
    wave_input: tuple[str, str]
    expected_artifacts: list[tuple[str, str]]
    stage_contract: str
    artifact_granularity: str
    progress_ledger: str
    resume_command: str
    partial_success_policy: str
    provider: str
    execution_profile: str
    setup_posture: str
    writable_volume_env: str
    operator_gate_required: str
    tools: str
    posture: str
    image_runtime_action: str
    operator_action_required: str
    acceptance_criteria: list[str]
    validation_commands: list[str]
    success_requires: str
    touched_areas: list[tuple[str, str]]
    dependencies: str
    risk_notes: list[str]
    complexity: str = "medium"


def inline(value: Any) -> str:
    return compact_ws(str(value)).replace("`", "'")


def prompt_excerpt(value: str, limit: int = 180) -> str:
    text = inline(value)
    return text if len(text) <= limit else text[: limit - 3].rstrip() + "..."


def load_manifest(args: argparse.Namespace) -> tuple[dict[str, Any], str]:
    if args.intent_manifest:
        return json.loads(args.intent_manifest.read_text()), str(args.intent_manifest)
    return compile_prompt(args.prompt), "compiled from --prompt"


def intent_context(manifest: dict[str, Any], source: str) -> dict[str, Any]:
    intent = manifest.get("intent", {})
    budget = manifest.get("budget", {})
    provider_plan = manifest.get("provider_plan", {})
    providers = provider_plan.get("priority", [])
    blockers = manifest.get("tool_blockers", [])
    return {
        "source": source,
        "campaign_id": manifest.get("campaign_id", "screening-superpowers"),
        "mode": intent.get("mode", "screen"),
        "goal": intent.get("natural_language_goal", "screening-superpowers dry-run campaign"),
        "target": intent.get("target_hint", manifest.get("target", {}).get("name", "compiled screening target")),
        "providers": ", ".join(providers) if providers else "runpod, aws_batch, neocloud_gpu_pod",
        "max_spend": budget.get("max_spend_usd", 0),
        "max_runtime": budget.get("max_runtime_minutes", 10),
        "max_ligands": budget.get("max_ligands", 5),
        "tool_blockers": ", ".join(blocker.get("tool", "unknown") for blocker in blockers) or "none",
    }


def common_inputs(context: dict[str, Any], routing_label: str) -> list[tuple[str, str]]:
    return [
        ("intent source", context["source"]),
        ("campaign ID", context["campaign_id"]),
        ("routing label", routing_label),
        ("intent mode", context["mode"]),
        ("natural-language goal", prompt_excerpt(context["goal"])),
        ("target hint", context["target"]),
        (
            "budget/provider extraction",
            (
                f"providers: {context['providers']}; max_spend_usd: {context['max_spend']}; "
                f"max_runtime_minutes: {context['max_runtime']}; max_ligands: {context['max_ligands']}"
            ),
        ),
        ("gated-tool blockers", context["tool_blockers"]),
    ]


def wave_drafts(context: dict[str, Any]) -> list[IssueDraft]:
    return [
        IssueDraft(
            wave="W00",
            slug="CAMPAIGN-READINESS",
            target_state="Todo",
            summary="Dry-run dispatch readiness for the screening-superpowers uplift. Establish the campaign contract, no-download posture, and blocker ledger before any worker starts implementation.",
            wave_input=("wave scope", "campaign kickoff, dispatch posture, and no-external-services guardrails"),
            expected_artifacts=[
                ("campaign DAG", "campaigns/screening-superpowers/issue-dag.md"),
                ("compiler dry-run manifest", ".runtime/screening-superpowers-fixture/tert-screen-intent-manifest.json"),
                ("broker dry-run issues", ".runtime/screening-superpowers-issues/"),
            ],
            stage_contract="n/a",
            artifact_granularity="per-campaign",
            progress_ledger="n/a",
            resume_command="python3 scripts/structure_factory/screening_issue_broker.py --prompt \"screen TERT inhibitors\" --out-dir .runtime/screening-superpowers-issues --force --json",
            partial_success_policy="prep-only issue generation may close partial if any generated draft fails issue_check",
            provider="provider-neutral",
            execution_profile="screening-no-download-smoke",
            setup_posture="n/a",
            writable_volume_env="n/a",
            operator_gate_required="no",
            tools="structure_intent_compile.py, screening_issue_broker.py, issue_check.py",
            posture="open-default",
            image_runtime_action="scaffold",
            operator_action_required="none for dry-run issue generation",
            acceptance_criteria=[
                "W00-W13 issue drafts are generated under an ignored output directory without contacting Linear.",
                "Generated drafts include Structure Factory provider, stage, tooling, acceptance, validation, touched-area, dependency, risk, and symphony schema fields.",
                "Only W00 is active; cost-bearing or gated waves remain Backlog or Blocked.",
            ],
            validation_commands=[
                "python3 scripts/structure_factory/structure_intent_compile.py --prompt \"screen TERT inhibitors\" --out .runtime/screening-superpowers-fixture/tert-screen-intent-manifest.json --json",
                "python3 scripts/structure_factory/screening_issue_broker.py --prompt \"screen TERT inhibitors\" --out-dir .runtime/screening-superpowers-issues --force --json",
                "python3 scripts/structure_factory/issue_check.py .runtime/screening-superpowers-issues --json",
            ],
            success_requires="all generated drafts pass issue_check and no external service is called",
            touched_areas=[
                ("campaigns/screening-superpowers/", "campaign DAG and dispatch posture"),
                ("scripts/structure_factory/", "compiler, broker, and issue validation scripts"),
                ("templates/", "Linear issue contract style"),
            ],
            dependencies="none",
            risk_notes=[
                "This issue does not authorize paid compute, raw data downloads, private data, or gated tools.",
                "Keep generated dry-run files in ignored runtime or operator-selected output directories until reviewed.",
            ],
        ),
        IssueDraft(
            wave="W01",
            slug="CONTRACTS-AND-MODULES",
            target_state="Backlog",
            summary="Refresh screening campaign contracts for ligand libraries, receptor ensembles, provider profiles, result ledgers, and candidate reports.",
            wave_input=("wave scope", "screening module and artifact contract validation"),
            expected_artifacts=[
                ("campaign module", "modules/campaigns/screening-superpowers.v1.json"),
                ("screening result contract", "modules/artifact-contracts/screening-results.v1.json"),
                ("candidate report contract", "modules/artifact-contracts/candidate-report.v1.json"),
            ],
            stage_contract="n/a",
            artifact_granularity="per-campaign",
            progress_ledger="n/a",
            resume_command="make screening-module-check",
            partial_success_policy="close partial if optional provider contracts are present but not execution-ready",
            provider="provider-neutral",
            execution_profile="screening-no-download-smoke",
            setup_posture="n/a",
            writable_volume_env="n/a",
            operator_gate_required="no",
            tools="module_manifest_check.py, provider_profile_check.py",
            posture="open-default",
            image_runtime_action="scaffold",
            operator_action_required="none",
            acceptance_criteria=[
                "Screening campaign, data, lane, provider, and artifact modules validate together.",
                "Contracts keep ligand libraries and receptor ensembles public and small by default.",
                "Provider profiles do not imply execution readiness or registry credentials.",
            ],
            validation_commands=[
                "python3 scripts/structure_factory/module_manifest_check.py modules/campaigns/screening-superpowers.v1.json --check-all --json",
                "make provider-check",
            ],
            success_requires="module and provider checks pass without broadening execution authorization",
            touched_areas=[
                ("modules/campaigns/", "screening campaign contract"),
                ("modules/artifact-contracts/", "screening result and candidate-report outputs"),
                ("modules/provider-profiles/", "provider-neutral adapter declarations"),
            ],
            dependencies="BSF-SCREENING-W00",
            risk_notes=[
                "Do not put ligand libraries, model weights, private structures, or large datasets in git.",
                "Provider contracts are planning inputs, not launch authorization.",
            ],
        ),
        IssueDraft(
            wave="W02",
            slug="LOCAL-NO-DOWNLOAD-FIXTURE",
            target_state="Backlog",
            summary="Keep the local no-download screening fixture healthy as the first runnable evidence lane for the campaign.",
            wave_input=("wave scope", "manifest checks, fanout estimate, fixture scoring, and result validation"),
            expected_artifacts=[
                ("fixture run directory", ".runtime/screening-superpowers-fixture/"),
                ("screening manifest validation", ".runtime/screening-superpowers-fixture/validation/screening-manifest-check.json"),
                ("screening result validation", ".runtime/screening-superpowers-fixture/validation/screening-results-check.json"),
            ],
            stage_contract="runpod/stage-contracts/screening-superpowers.stage-contract.json",
            artifact_granularity="per-campaign",
            progress_ledger=".runtime/screening-superpowers-fixture/stage-progress.jsonl",
            resume_command="make screening-check",
            partial_success_policy="fixture evidence remains fixture_or_demo and cannot support biological claims",
            provider="local",
            execution_profile="screening-no-download-smoke",
            setup_posture="local install",
            writable_volume_env=".runtime/screening-superpowers-fixture",
            operator_gate_required="no",
            tools="screening_manifest_check.py, screening_fanout_estimator.py, screening_fixture_run.py, screening_results_check.py",
            posture="open-default",
            image_runtime_action="run",
            operator_action_required="none",
            acceptance_criteria=[
                "Fixture manifest validates with zero expected download bytes.",
                "Fixture runner emits ranking, failure ledger, provenance, and validation ledger artifacts.",
                "Result checker classifies outputs as fixture_or_demo only.",
            ],
            validation_commands=["make screening-check"],
            success_requires="screening-check passes locally and writes only ignored runtime artifacts",
            touched_areas=[
                ("examples/screening-superpowers/", "public fixture inputs"),
                ("scripts/structure_factory/", "local screening validation and fixture runner"),
                ("runpod/stage-contracts/", "stage contract reused by provider dry-runs"),
            ],
            dependencies="BSF-SCREENING-W01",
            risk_notes=[
                "Fixture scores are not affinity, pose, or mechanism evidence.",
                "Do not silently promote fixture_or_demo results to candidate biological claims.",
            ],
        ),
        IssueDraft(
            wave="W03",
            slug="OPENBIND-CALIBRATION",
            target_state="Backlog",
            summary="Add OpenBind-style calibration planning for redocking, cross-docking, cofolding, affinity prediction, baselines, and disagreement reporting.",
            wave_input=("wave scope", "calibration intent and benchmark ledger planning"),
            expected_artifacts=[
                ("calibration intent manifest", ".runtime/screening-superpowers-fixture/openbind-calibration-intent.json"),
                ("screening docs", "docs/screening-superpowers.md"),
                ("result contract", "modules/artifact-contracts/screening-results.v1.json"),
            ],
            stage_contract="n/a",
            artifact_granularity="per-campaign",
            progress_ledger="n/a",
            resume_command="python3 scripts/structure_factory/structure_intent_compile.py --prompt \"OpenBind-style calibration for TERT screening with redocking and cross-docking\" --out .runtime/screening-superpowers-fixture/openbind-calibration-intent.json --json",
            partial_success_policy="close partial if calibration inputs are absent; emit planned slices and missing-control ledger",
            provider="provider-neutral",
            execution_profile="screening-no-download-smoke",
            setup_posture="n/a",
            writable_volume_env="n/a",
            operator_gate_required="no",
            tools="structure_intent_compile.py, screening_results_check.py",
            posture="open-default",
            image_runtime_action="scaffold",
            operator_action_required="none",
            acceptance_criteria=[
                "Compiler recognizes OpenBind-style calibration language and records calibration slices.",
                "Calibration plan separates redocking, cross-docking, cofolding, and affinity prediction.",
                "Simple baselines and method disagreement remain first-class report fields.",
            ],
            validation_commands=[
                "python3 scripts/structure_factory/structure_intent_compile.py --prompt \"OpenBind-style calibration for TERT screening with redocking and cross-docking\" --out .runtime/screening-superpowers-fixture/openbind-calibration-intent.json --json"
            ],
            success_requires="compiled manifest contains an openbind_calibration intent and calibration section",
            touched_areas=[
                ("scripts/structure_factory/", "natural-language compiler"),
                ("docs/", "screening campaign guidance"),
                ("modules/artifact-contracts/", "calibration result fields"),
            ],
            dependencies="BSF-SCREENING-W02",
            risk_notes=[
                "OpenBind-style calibration is a method-quality check, not proof of new binder activity.",
                "Do not claim benchmark parity without materialized controls and provenance.",
            ],
        ),
        IssueDraft(
            wave="W04",
            slug="METHOD-DISAGREEMENT-LEDGER",
            target_state="Backlog",
            summary="Build method-disagreement query support so the campaign can promote top hits, uncertainty cases, and failures separately.",
            wave_input=("wave scope", "method disagreement intent and reporting ledger"),
            expected_artifacts=[
                ("disagreement intent manifest", ".runtime/screening-superpowers-fixture/method-disagreement-intent.json"),
                ("screening result contract", "modules/artifact-contracts/screening-results.v1.json"),
            ],
            stage_contract="n/a",
            artifact_granularity="per-campaign",
            progress_ledger="n/a",
            resume_command="python3 scripts/structure_factory/structure_intent_compile.py --prompt \"find method disagreement in TERT docking consensus\" --out .runtime/screening-superpowers-fixture/method-disagreement-intent.json --json",
            partial_success_policy="close partial if only open-method scores are available; gated methods remain blocked until reviewed",
            provider="provider-neutral",
            execution_profile="screening-wide-docking",
            setup_posture="n/a",
            writable_volume_env="n/a",
            operator_gate_required="no",
            tools="structure_intent_compile.py, screening_results_check.py",
            posture="open-default",
            image_runtime_action="scaffold",
            operator_action_required="none",
            acceptance_criteria=[
                "Compiler recognizes disagreement, discordance, consensus, and method-comparison prompts.",
                "Manifest records a disagreement query with compared methods and minimum report columns.",
                "Single-model scores are explicitly barred from becoming truth labels.",
            ],
            validation_commands=[
                "python3 scripts/structure_factory/structure_intent_compile.py --prompt \"find method disagreement in TERT docking consensus\" --out .runtime/screening-superpowers-fixture/method-disagreement-intent.json --json"
            ],
            success_requires="compiled manifest contains method_disagreement_review intent and disagreement_query block",
            touched_areas=[
                ("scripts/structure_factory/", "natural-language compiler"),
                ("modules/artifact-contracts/", "disagreement report fields"),
            ],
            dependencies="BSF-SCREENING-W03",
            risk_notes=[
                "Disagreement is a triage signal, not evidence that any method is correct.",
                "Do not hide method failures or missing scores when ranking candidates.",
            ],
        ),
        IssueDraft(
            wave="W05",
            slug="BUDGET-PROVIDER-PLANNER",
            target_state="Backlog",
            summary="Turn extracted budget and provider phrases into bounded fanout plans before any cost-bearing screening work.",
            wave_input=("wave scope", "budget/provider extraction, fanout estimate, and operator-gate readiness"),
            expected_artifacts=[
                ("fanout estimate", ".runtime/screening-superpowers-fixture/validation/fanout-estimate.json"),
                ("compiled intent manifest", ".runtime/screening-superpowers-fixture/budget-provider-intent.json"),
            ],
            stage_contract="runpod/stage-contracts/screening-superpowers.stage-contract.json",
            artifact_granularity="per-wave",
            progress_ledger=".runtime/screening-superpowers-fixture/stage-progress.jsonl",
            resume_command="python3 scripts/structure_factory/screening_fanout_estimator.py --manifest examples/screening-superpowers/screening-manifest.json --out .runtime/screening-superpowers-fixture/validation/fanout-estimate.json --json",
            partial_success_policy="close blocked if requested budget/provider posture lacks explicit operator authorization",
            provider="provider-neutral",
            execution_profile="screening-no-download-smoke",
            setup_posture="provider-declared: local, RunPod, AWS Batch, neocloud, or n/a",
            writable_volume_env="provider-specific; RunPod uses STRUCTURE_FACTORY_RUNPOD_NETWORK_VOLUME_ID",
            operator_gate_required="no",
            tools="structure_intent_compile.py, screening_fanout_estimator.py",
            posture="open-default",
            image_runtime_action="scaffold",
            operator_action_required="operator approval only before paid execution",
            acceptance_criteria=[
                "Compiler extracts max spend, runtime, ligand count, top-N, and provider mentions from simple prompts.",
                "Fanout estimate runs before expensive transfer, docking, cofolding, or report promotion.",
                "Paid provider requests remain blocked until operator gate details are present.",
            ],
            validation_commands=[
                "python3 scripts/structure_factory/structure_intent_compile.py --prompt \"screen 100 ligands against TERT on RunPod under $10 for 2 hours\" --out .runtime/screening-superpowers-fixture/budget-provider-intent.json --json",
                "python3 scripts/structure_factory/screening_fanout_estimator.py --manifest examples/screening-superpowers/screening-manifest.json --out .runtime/screening-superpowers-fixture/validation/fanout-estimate.json --json",
            ],
            success_requires="intent extraction records budget/provider constraints and fanout estimate completes",
            touched_areas=[
                ("scripts/structure_factory/", "intent compiler and fanout estimator"),
                ("examples/screening-superpowers/", "fixture manifest used for estimates"),
                ("runpod/stage-contracts/", "provider stage contract reference"),
            ],
            dependencies="BSF-SCREENING-W02",
            risk_notes=[
                "A prompt with a budget is not operator authorization to launch paid infrastructure.",
                "Provider priority is intent only until launch contracts, artifact pulls, hashes, and cleanup policy exist.",
            ],
        ),
        IssueDraft(
            wave="W06",
            slug="RUNPOD-NO-DOWNLOAD-CANARY",
            target_state="Backlog",
            summary="Prepare the RunPod no-download screening canary path while keeping pod creation behind trusted operator gates.",
            wave_input=("wave scope", "RunPod stage contract and no-download packet readiness"),
            expected_artifacts=[
                ("stage contract", "runpod/stage-contracts/screening-superpowers.stage-contract.json"),
                ("launch manifest", "runpod/launch-manifests/no-download-smoke.json"),
                ("launch bundle", ".runtime/structure-factory-no-download-smoke/"),
            ],
            stage_contract="runpod/stage-contracts/screening-superpowers.stage-contract.json",
            artifact_granularity="per-wave",
            progress_ledger="/workspace/structure-factory/runs/<run-id>/stage-progress.jsonl",
            resume_command="make stage-contract-check && make launch-bundle",
            partial_success_policy="prep can close In Review; actual pod create remains blocked without operator gate",
            provider="runpod",
            execution_profile="screening-no-download-smoke",
            setup_posture="public image plus runtime bootstrap or RunPod network volume bootstrap",
            writable_volume_env="STRUCTURE_FACTORY_RUNPOD_NETWORK_VOLUME_ID",
            operator_gate_required="yes",
            tools="stage_contract_check.py, runpod_launch_bundle.py, runpod_scope_check.py",
            posture="mixed",
            image_runtime_action="scaffold",
            operator_action_required="explicit RunPod launch approval before create_verify_cleanup",
            acceptance_criteria=[
                "Stage contract validates and declares progress ledger, checkpoint, done marker, and resume command.",
                "RunPod scope checks prevent sibling campaign resource mutation.",
                "No pod is launched by the worker issue.",
            ],
            validation_commands=[
                "python3 scripts/structure_factory/stage_contract_check.py --stage-contract runpod/stage-contracts/screening-superpowers.stage-contract.json --json",
                "make runpod-scope-check",
                "make launch-bundle",
            ],
            success_requires="stage contract, scope check, and launch bundle prep pass without creating a pod",
            touched_areas=[
                ("runpod/stage-contracts/", "screening stage contract"),
                ("runpod/launch-manifests/", "no-download provider manifest"),
                ("scripts/structure_factory/", "RunPod prep validators"),
            ],
            dependencies="BSF-SCREENING-W05",
            risk_notes=[
                "RunPod desiredStatus is provider intent only and cannot be counted as workload progress.",
                "Do not create pods, mutate volumes, or use registry auth from this dry-run issue.",
            ],
        ),
        IssueDraft(
            wave="W07",
            slug="PROVIDER-ADAPTER-PARITY",
            target_state="Backlog",
            summary="Keep AWS Batch, neocloud, local, SSH/HPC, and generic-cloud profiles aligned with the screening evidence contract.",
            wave_input=("wave scope", "provider profile parity and no-false-success gates"),
            expected_artifacts=[
                ("provider profiles", "modules/provider-profiles/"),
                ("compute backend docs", "docs/compute-backends.md"),
            ],
            stage_contract="n/a",
            artifact_granularity="per-wave",
            progress_ledger="provider-specific or n/a",
            resume_command="make provider-check",
            partial_success_policy="close partial if an adapter validates as prep-only but lacks execution authorization",
            provider="provider-neutral",
            execution_profile="screening-no-download-smoke",
            setup_posture="provider-declared",
            writable_volume_env="provider-specific or n/a",
            operator_gate_required="no",
            tools="provider_profile_check.py, aws_profile_check.py, neocloud_scope_check.py",
            posture="mixed",
            image_runtime_action="scaffold",
            operator_action_required="provider-specific approval before execution",
            acceptance_criteria=[
                "All provider profiles require input audit and contract self-check gates.",
                "AWS and neocloud profiles remain adapter contracts until credentials and budgets are authorized.",
                "Fallback provider routes close partial/degraded unless explicitly reapproved.",
            ],
            validation_commands=[
                "make provider-check",
                "make aws-profile-check",
                "make neocloud-scope-check",
            ],
            success_requires="provider checks pass while preserving prep-only status",
            touched_areas=[
                ("modules/provider-profiles/", "provider adapter profiles"),
                ("docs/", "compute backend and no-false-success guidance"),
                ("scripts/structure_factory/", "provider validators"),
            ],
            dependencies="BSF-SCREENING-W05",
            risk_notes=[
                "Cloud profile validity is not permission to launch workloads.",
                "Keep credentials, account IDs, and private provider details out of git and Linear.",
            ],
        ),
        IssueDraft(
            wave="W08",
            slug="OPEN-WIDE-DOCKING",
            target_state="Backlog",
            summary="Prepare the open wide-screen lane using descriptor baselines, RDKit-style preparation, and AutoDock Vina-style docking.",
            wave_input=("wave scope", "open wide-pass screening lane"),
            expected_artifacts=[
                ("ligand fixture", "examples/screening-superpowers/ligand-library.json"),
                ("receptor fixture", "examples/screening-superpowers/receptor-ensemble.json"),
                ("wide-pass lane modules", "modules/lane-modules/"),
            ],
            stage_contract="runpod/stage-contracts/screening-superpowers.stage-contract.json",
            artifact_granularity="per-shard",
            progress_ledger="/workspace/structure-factory/runs/<run-id>/stage-progress.jsonl",
            resume_command="make screening-results-check",
            partial_success_policy="close partial if only descriptor baselines run; failed docking rows must remain in failure ledger",
            provider="provider-neutral",
            execution_profile="screening-wide-docking",
            setup_posture="public image or local install",
            writable_volume_env="provider-specific or .runtime",
            operator_gate_required="yes",
            tools="RDKit-style descriptors, AutoDock Vina-style docking, screening_fixture_run.py",
            posture="open-default",
            image_runtime_action="scaffold",
            operator_action_required="approval before any non-fixture provider run",
            acceptance_criteria=[
                "Wide-pass lane records prepared ligands, receptor/site provenance, scores, and failures.",
                "Open tools are preferred before gated ML docking lanes.",
                "Failure rows remain visible and do not vanish from ranking ledgers.",
            ],
            validation_commands=[
                "python3 scripts/structure_factory/screening_manifest_check.py examples/screening-superpowers/screening-manifest.json --json",
                "make screening-results-check",
            ],
            success_requires="fixture wide-pass outputs validate with visible failures and provenance",
            touched_areas=[
                ("examples/screening-superpowers/", "fixture ligand and receptor inputs"),
                ("modules/lane-modules/", "wide-pass lane contracts"),
                ("scripts/structure_factory/", "fixture run and result validation"),
            ],
            dependencies="BSF-SCREENING-W06",
            risk_notes=[
                "Docking scores are triage features, not measured affinity.",
                "Do not ingest large ligand collections without fanout and budget gates.",
            ],
        ),
        IssueDraft(
            wave="W09",
            slug="FOCUSED-COFOLDING",
            target_state="Backlog",
            summary="Prepare the focused cofolding and affinity-aware tranche, defaulting to open/reviewed lanes and preserving candidate-only claims.",
            wave_input=("wave scope", "focused Boltz-style tranche after wide-pass canaries"),
            expected_artifacts=[
                ("focused lane module", "modules/lane-modules/boltz.focused-screen.v1.json"),
                ("screening result validation", ".runtime/screening-superpowers-fixture/validation/screening-results-check.json"),
            ],
            stage_contract="runpod/stage-contracts/screening-superpowers.stage-contract.json",
            artifact_granularity="per-shard",
            progress_ledger="/workspace/structure-factory/runs/<run-id>/stage-progress.jsonl",
            resume_command="make screening-results-check",
            partial_success_policy="close partial if focused lane is skipped or missing optional model assets",
            provider="provider-neutral",
            execution_profile="screening-focused-cofolding",
            setup_posture="public image plus runtime cache or provider bootstrap",
            writable_volume_env="provider-specific or .runtime",
            operator_gate_required="yes",
            tools="Boltz-style focused cofolding, simple baselines, result checker",
            posture="mixed",
            image_runtime_action="scaffold",
            operator_action_required="approval before any GPU run or model cache materialization",
            acceptance_criteria=[
                "Focused tranche runs only after wide-pass canary artifacts exist.",
                "Candidate claim ceiling is preserved for prediction-only outputs.",
                "Missing optional model assets close skipped or partial, not success.",
            ],
            validation_commands=["make screening-results-check"],
            success_requires="focused-lane fixture or skip ledger validates without overclaiming",
            touched_areas=[
                ("modules/lane-modules/", "focused lane contract"),
                ("scripts/structure_factory/", "result validation and validation ledger handling"),
                ("runpod/stage-contracts/", "stage progress contract"),
            ],
            dependencies="BSF-SCREENING-W08",
            risk_notes=[
                "Predicted complex confidence is not experimental binding evidence.",
                "Large weights or caches must stay out of git and use runtime/provider storage.",
            ],
        ),
        IssueDraft(
            wave="W10",
            slug="CANDIDATE-REPORT-PROMOTION",
            target_state="Backlog",
            summary="Promote top hits, controls, scaffold-diverse cases, disagreement cases, and failures into compact candidate reports.",
            wave_input=("wave scope", "candidate report promotion and validation ledger"),
            expected_artifacts=[
                ("candidate report contract", "modules/artifact-contracts/candidate-report.v1.json"),
                ("screening results contract", "modules/artifact-contracts/screening-results.v1.json"),
                ("fixture report output", ".runtime/screening-superpowers-fixture/candidate_reports/"),
            ],
            stage_contract="runpod/stage-contracts/screening-superpowers.stage-contract.json",
            artifact_granularity="per-campaign",
            progress_ledger=".runtime/screening-superpowers-fixture/stage-progress.jsonl",
            resume_command="python3 scripts/structure_factory/screening_fixture_run.py --manifest examples/screening-superpowers/screening-manifest.json --out .runtime/screening-superpowers-fixture --json",
            partial_success_policy="close partial if only fixture reports exist or if candidate evidence is missing required provenance",
            provider="local",
            execution_profile="screening-no-download-smoke",
            setup_posture="local install",
            writable_volume_env=".runtime/screening-superpowers-fixture",
            operator_gate_required="no",
            tools="screening_fixture_run.py, screening_results_check.py",
            posture="open-default",
            image_runtime_action="run",
            operator_action_required="none for fixture report generation",
            acceptance_criteria=[
                "Reports include provenance, method summary, failure context, and result boundary.",
                "Top-N promotion uses extracted budget/promote constraints where supplied.",
                "Disagreement and representative failure cases are eligible for report promotion.",
            ],
            validation_commands=[
                "python3 scripts/structure_factory/screening_fixture_run.py --manifest examples/screening-superpowers/screening-manifest.json --out .runtime/screening-superpowers-fixture --json",
                "python3 scripts/structure_factory/screening_results_check.py --artifact-root .runtime/screening-superpowers-fixture --json",
            ],
            success_requires="fixture reports and screening result checks pass with candidate-only boundaries",
            touched_areas=[
                ("modules/artifact-contracts/", "candidate report contract"),
                ("examples/screening-superpowers/", "fixture input references"),
                ("scripts/structure_factory/", "fixture report generator and validator"),
            ],
            dependencies="BSF-SCREENING-W09",
            risk_notes=[
                "Candidate reports are ranking artifacts, not validated drug-discovery claims.",
                "Do not include private ligands or unpublished structures in Linear issue bodies.",
            ],
        ),
        IssueDraft(
            wave="W12",
            slug="GATED-TOOL-BLOCKERS",
            target_state="Blocked",
            summary="Keep AlphaFold 3, Phenix, ChimeraX, CryoSPARC, GNINA, DiffDock, Chai, and similar lanes blocked or review-required until runtime access and terms are recorded.",
            wave_input=("wave scope", "gated and review-required tool blockers"),
            expected_artifacts=[
                ("tooling posture docs", "docs/tooling-and-licensing.md"),
                ("software registry", "references/software-registry.yaml"),
                ("license gate report", ".runtime/structure-factory-toolcheck/license-gate-check.json"),
            ],
            stage_contract="n/a",
            artifact_granularity="per-wave",
            progress_ledger="n/a",
            resume_command="make license-gate-check",
            partial_success_policy="close blocked if any requested gated tool lacks current terms, use context, or runtime access",
            provider="provider-neutral",
            execution_profile="screening-gated-ml-docking",
            setup_posture="runtime bootstrap or operator-provided licensed runtime only",
            writable_volume_env="provider-specific secure runtime; never git",
            operator_gate_required="yes",
            tools="AlphaFold3, Phenix, ChimeraX, CryoSPARC, GNINA, DiffDock, Chai",
            posture="runtime-gated",
            image_runtime_action="scaffold",
            operator_action_required="record terms, use context, and runtime access before execution",
            acceptance_criteria=[
                "Compiler records requested gated or review-required tools as blockers.",
                "Missing optional gated tools report skipped or blocked, not failure or success.",
                "No secrets, license files, private installer URLs, private data, or weights enter git or Linear.",
            ],
            validation_commands=[
                "python3 scripts/structure_factory/structure_intent_compile.py --prompt \"screen TERT inhibitors with AlphaFold3, GNINA, Phenix, and ChimeraX under $50 on RunPod\" --out .runtime/screening-superpowers-fixture/gated-tool-intent.json --json",
                "make license-gate-check",
            ],
            success_requires="gated-tool prompt records blockers and license gate check remains fail-closed",
            touched_areas=[
                ("scripts/structure_factory/", "intent compiler and license gate checks"),
                ("docs/", "tooling posture guidance"),
                ("references/", "software registry"),
            ],
            dependencies="explicit operator/license gate after BSF-SCREENING-W11",
            risk_notes=[
                "This issue is intentionally Blocked until runtime access and terms are explicit.",
                "Do not bake restricted tools or model weights into public images.",
            ],
        ),
        IssueDraft(
            wave="W13",
            slug="DISPATCH-SELF-CHECK",
            target_state="Backlog",
            summary="Run the dry-run broker and issue checker as the final dispatch readiness gate for the W00-W13 campaign wave.",
            wave_input=("wave scope", "self-check generated issue drafts before dispatch"),
            expected_artifacts=[
                ("generated issue drafts", ".runtime/screening-superpowers-issues/"),
                ("issue-check summary", ".runtime/screening-superpowers-issues/issue-check-summary.json"),
            ],
            stage_contract="n/a",
            artifact_granularity="per-campaign",
            progress_ledger="n/a",
            resume_command="python3 scripts/structure_factory/screening_issue_broker.py --prompt \"screen TERT inhibitors with OpenBind-style calibration\" --out-dir .runtime/screening-superpowers-issues --force --json",
            partial_success_policy="close partial if broker emits drafts but issue_check or file-reference mode fails",
            provider="provider-neutral",
            execution_profile="screening-no-download-smoke",
            setup_posture="n/a",
            writable_volume_env="n/a",
            operator_gate_required="no",
            tools="screening_issue_broker.py, issue_check.py",
            posture="open-default",
            image_runtime_action="scaffold",
            operator_action_required="none",
            acceptance_criteria=[
                "Broker writes exactly W00-W13 Markdown drafts to the specified output directory.",
                "Generated drafts contain no template placeholders and pass issue_check.",
                "File-reference mode validates repo-controlled paths used by generated drafts.",
            ],
            validation_commands=[
                "python3 scripts/structure_factory/screening_issue_broker.py --prompt \"screen TERT inhibitors with OpenBind-style calibration\" --out-dir .runtime/screening-superpowers-issues --force --json",
                "python3 scripts/structure_factory/issue_check.py .runtime/screening-superpowers-issues --check-file-references --json",
            ],
            success_requires="broker generation and issue_check file-reference mode both pass",
            touched_areas=[
                ("scripts/structure_factory/", "broker and issue validation scripts"),
                ("templates/", "Linear issue style contract"),
                ("campaigns/screening-superpowers/", "campaign wave semantics"),
            ],
            dependencies="BSF-SCREENING-W12 remains blocked for gated execution; dry-run dispatch can still be reviewed",
            risk_notes=[
                "Dry-run issue generation does not create Linear issues.",
                "Do not dispatch Blocked gated-tool issues into active work without explicit operator gate.",
            ],
        ),
    ]


def render_issue(issue: IssueDraft, context: dict[str, Any], routing_label: str) -> str:
    input_lines = common_inputs(context, routing_label)
    input_lines.append(issue.wave_input)
    lines: list[str] = []
    lines.append("## Summary")
    lines.append("")
    lines.append(issue.summary)
    lines.append("")
    lines.append("## Inputs")
    lines.append("")
    for key, value in input_lines:
        lines.append(f"- `{inline(key)}` - {inline(value)}")
    lines.append("")
    lines.append("## Expected Artifacts")
    lines.append("")
    for artifact, description in issue.expected_artifacts:
        lines.append(f"- `{inline(artifact)}` - {inline(description)}")
    lines.append("")
    lines.append("## Stage / Progress Contract")
    lines.append("")
    lines.append(f"- stage contract: `{inline(issue.stage_contract)}`")
    lines.append(f"- artifact granularity: `{inline(issue.artifact_granularity)}`")
    lines.append(f"- progress ledger: `{inline(issue.progress_ledger)}`")
    lines.append(f"- resume command: `{inline(issue.resume_command)}`")
    lines.append(f"- partial success policy: `{inline(issue.partial_success_policy)}`")
    lines.append("")
    lines.append("## Provider / Execution Profile")
    lines.append("")
    lines.append(f"- provider: `{inline(issue.provider)}`")
    lines.append(f"- execution profile: `{inline(issue.execution_profile)}`")
    lines.append(f"- setup posture: `{inline(issue.setup_posture)}`")
    lines.append(f"- writable volume/env: `{inline(issue.writable_volume_env)}`")
    lines.append(f"- operator gate required: `{inline(issue.operator_gate_required)}`")
    lines.append("")
    lines.append("## Tooling / License Posture")
    lines.append("")
    lines.append(f"- tools: `{inline(issue.tools)}`")
    lines.append(f"- posture: `{inline(issue.posture)}`")
    lines.append("- current primary source checked: `no; dry-run broker used local tooling docs and registry only; worker must verify current primary terms before install/run`")
    lines.append("- intended use context: `unknown until operator gate; dry-run prep only`")
    lines.append(f"- image/runtime action: `{inline(issue.image_runtime_action)}`")
    lines.append(f"- operator action required: `{inline(issue.operator_action_required)}`")
    lines.append("")
    lines.append("## Acceptance Criteria")
    lines.append("")
    for criterion in issue.acceptance_criteria:
        lines.append(f"- [ ] {inline(criterion)}")
    lines.append("")
    lines.append("## Validation Commands")
    lines.append("")
    lines.append("```bash")
    lines.extend(issue.validation_commands)
    lines.append("```")
    lines.append("")
    lines.append("## Final Outcome Contract")
    lines.append("")
    lines.append("- worker lane: `codex`")
    lines.append("- closeout state: `In Review`")
    lines.append("- final comment must include: `<!-- symphony-outcome -->`")
    lines.append(f"- success requires: `{inline(issue.success_requires)}`")
    lines.append("")
    lines.append("## Touched Areas")
    lines.append("")
    for path, reason in issue.touched_areas:
        lines.append(f"- `{inline(path)}` - {inline(reason)}")
    lines.append("")
    lines.append("## Dependencies")
    lines.append("")
    lines.append(f"Blocked by: {inline(issue.dependencies)}")
    lines.append("")
    lines.append("## Risk Notes")
    lines.append("")
    default_risks = [
        "Do not store secrets, raw cryo-EM movies, private structures, unpublished sequences, model weights, or large datasets in git or Linear.",
        "Record license constraints for CryoSPARC, Phenix, ChimeraX, MotionCor, Rosetta/PyRosetta, AlphaFold, or other restricted tools.",
        "RunPod, AWS, neocloud, local heavy jobs, and gated-tool execution require explicit operator approval before launch.",
    ]
    for note in [*default_risks, *issue.risk_notes]:
        lines.append(f"- {inline(note)}")
    lines.append("")
    lines.append("## Complexity")
    lines.append("")
    lines.append(f"tier: {inline(issue.complexity)}")
    lines.append("")
    lines.append("<!-- symphony:schema")
    lines.append("schema_version: 1")
    lines.append("subgroup: structure-factory")
    lines.append(f"routing_label: {routing_label}")
    lines.append(f"campaign_id: {context['campaign_id']}")
    lines.append(f"wave: {issue.wave}")
    lines.append(f"target_state: {issue.target_state}")
    lines.append("touched_areas:")
    for path, _reason in issue.touched_areas:
        lines.append(f"  - {path}")
    lines.append(f"complexity: {issue.complexity}")
    lines.append("-->")
    return "\n".join(lines) + "\n"


def issue_filename(issue: IssueDraft) -> str:
    return f"BSF-SCREENING-{issue.wave}-{slugify(issue.slug, fallback=issue.wave).upper()}.md"


def write_issues(
    *,
    out_dir: Path,
    issues: list[IssueDraft],
    context: dict[str, Any],
    routing_label: str,
    force: bool,
) -> dict[str, Any]:
    out_dir.mkdir(parents=True, exist_ok=True)
    outputs = [(out_dir / issue_filename(issue), issue) for issue in issues]
    collisions = [str(path) for path, _issue in outputs if path.exists() and not force]
    if collisions:
        return {
            "ok": False,
            "out_dir": str(out_dir.resolve()),
            "written": [],
            "collisions": collisions,
            "error": "refusing to overwrite existing issue drafts without --force",
        }

    written: list[str] = []
    for path, issue in outputs:
        path.write_text(render_issue(issue, context, routing_label))
        written.append(str(path.resolve()))

    return {
        "ok": True,
        "out_dir": str(out_dir.resolve()),
        "campaign_id": context["campaign_id"],
        "routing_label": routing_label,
        "checked_external_services": False,
        "written_count": len(written),
        "written": written,
        "waves": [issue.wave for issue in issues],
    }


def main() -> int:
    parser = argparse.ArgumentParser()
    source = parser.add_mutually_exclusive_group(required=True)
    source.add_argument("--prompt", help="Natural-language screening or structure intent to compile before brokering")
    source.add_argument("--intent-manifest", type=Path, help="Compiled intent manifest JSON")
    parser.add_argument("--out-dir", type=Path, required=True)
    parser.add_argument("--routing-label", default="sym:structure-factory")
    parser.add_argument(
        "--waves",
        help="Optional comma-separated wave IDs to write, e.g. W04,W05,W06. Defaults to all W00-W13.",
    )
    parser.add_argument("--force", action="store_true", help="Overwrite existing drafts in --out-dir")
    parser.add_argument("--json", action="store_true")
    args = parser.parse_args()

    manifest, source_note = load_manifest(args)
    context = intent_context(manifest, source_note)
    issues = wave_drafts(context)
    if args.waves:
        requested = {wave.strip().upper() for wave in args.waves.split(",") if wave.strip()}
        available = {issue.wave for issue in issues}
        missing = sorted(requested - available)
        if missing:
            summary = {
                "ok": False,
                "out_dir": str(args.out_dir.resolve()),
                "written": [],
                "collisions": [],
                "error": f"unknown requested waves: {missing}",
            }
            if args.json:
                print(json.dumps(summary, indent=2, sort_keys=True))
            else:
                print("ok: False")
                print(summary["error"])
            return 1
        issues = [issue for issue in issues if issue.wave in requested]
    summary = write_issues(
        out_dir=args.out_dir,
        issues=issues,
        context=context,
        routing_label=args.routing_label,
        force=args.force,
    )
    if args.json:
        print(json.dumps(summary, indent=2, sort_keys=True))
    else:
        print(f"ok: {summary['ok']}")
        print(f"out_dir: {summary['out_dir']}")
        if summary["ok"]:
            print(f"written_count: {summary['written_count']}")
        else:
            print(summary["error"])
    return 0 if summary["ok"] else 1


if __name__ == "__main__":
    raise SystemExit(main())
