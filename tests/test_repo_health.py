from __future__ import annotations

import json
import os
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]


class RepoHealthTests(unittest.TestCase):
    def run_json(self, *args: str) -> dict:
        result = subprocess.run(
            [sys.executable, *args],
            cwd=ROOT,
            check=True,
            text=True,
            capture_output=True,
        )
        return json.loads(result.stdout)

    def run_json_with_env(self, *args: str, env: dict[str, str] | None = None, check: bool = True) -> tuple[int, dict]:
        merged = os.environ.copy()
        if env:
            merged.update(env)
        result = subprocess.run(
            [sys.executable, *args],
            cwd=ROOT,
            check=check,
            text=True,
            capture_output=True,
            env=merged,
        )
        return result.returncode, json.loads(result.stdout)

    def test_public_export_has_no_browser_surface(self) -> None:
        forbidden_suffixes = {".html", ".htm", ".css", ".js", ".jsx", ".ts", ".tsx"}
        forbidden_names = {"package.json", "vite.config.js", "vite.config.ts", "next.config.js", "next.config.ts"}
        forbidden_terms = [
            "http.server",
            "localhost",
            "127.0.0.1",
            "artifact browser",
            "static dashboard",
            "screening_dashboard",
            "report.html",
            "index.html",
        ]
        bad_files: list[str] = []
        bad_terms: list[str] = []
        this_file = Path(__file__).resolve()
        for path in ROOT.rglob("*"):
            if ".git" in path.parts or not path.is_file() or path.resolve() == this_file:
                continue
            rel = path.relative_to(ROOT).as_posix()
            if path.suffix.lower() in forbidden_suffixes or path.name in forbidden_names:
                bad_files.append(rel)
                continue
            try:
                text = path.read_text(encoding="utf-8").lower()
            except UnicodeDecodeError:
                continue
            for term in forbidden_terms:
                if term in text:
                    bad_terms.append(f"{rel}: {term}")
        self.assertEqual([], bad_files)
        self.assertEqual([], bad_terms)

    def test_preflight_passes(self) -> None:
        summary = self.run_json("scripts/structure_factory/preflight.py", "--repo-root", ".", "--json")
        self.assertTrue(summary["ok"], summary)

    def test_software_registry_passes(self) -> None:
        summary = self.run_json(
            "scripts/structure_factory/software_registry_check.py",
            "references/software-registry.yaml",
            "--json",
        )
        self.assertTrue(summary["ok"], summary)
        self.assertEqual(87, summary["entry_count"])
        self.assertTrue(
            {"esmfold2-fast", "proteina-complexa", "alphafold2_multimer_v3", "rosettafold3"}.issubset(
                summary["entry_ids"]
            )
        )

    def test_module_manifest_passes(self) -> None:
        summary = self.run_json(
            "scripts/structure_factory/module_manifest_check.py",
            "modules/campaigns/cryoem-raw-to-atomic-no-download.v1.json",
            "--check-all",
            "--json",
        )
        self.assertTrue(summary["ok"], summary)
        self.assertGreaterEqual(summary["referenced_modules_checked"], 10)

    def test_structure_intent_compiler_handles_minimal_screening_prompts(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            out = Path(tmp) / "tert-budget-intent.json"
            summary = self.run_json(
                "scripts/structure_factory/structure_intent_compile.py",
                "--prompt",
                "screen 100 ligands against TERT on RunPod under $10 for 2 hours with AlphaFold3 and GNINA",
                "--out",
                str(out),
                "--json",
            )
            manifest = json.loads(out.read_text())

        self.assertTrue(summary["ok"], summary)
        self.assertEqual(manifest["intent"]["mode"], "screen")
        self.assertEqual(manifest["intent"]["target_hint"], "TERT")
        self.assertEqual(manifest["intent"]["ligand_hint"], "100 ligands")
        self.assertEqual(manifest["budget"]["max_spend_usd"], 10)
        self.assertEqual(manifest["budget"]["max_runtime_minutes"], 120)
        self.assertEqual(manifest["budget"]["max_ligands"], 100)
        self.assertEqual(manifest["provider_plan"]["priority"][0], "runpod")
        blockers = {blocker["tool"] for blocker in manifest["tool_blockers"]}
        self.assertTrue({"alphafold3", "gnina"}.issubset(blockers), manifest)

    def test_provider_profiles_pass(self) -> None:
        summary = self.run_json(
            "scripts/structure_factory/provider_profile_check.py",
            "modules/provider-profiles",
            "--json",
        )
        self.assertTrue(summary["ok"], summary)
        providers = {profile["provider"] for profile in summary["profiles"]}
        self.assertTrue({"runpod", "local", "ssh_hpc", "generic_cloud", "neocloud", "fal"}.issubset(providers))

    def test_provider_profile_requires_self_check_gates(self) -> None:
        profile = json.loads((ROOT / "modules" / "provider-profiles" / "local" / "workstation-no-download.v1.json").read_text())
        profile["execution_ready_requires"] = ["repo_checkout"]
        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp) / "invalid-provider.json"
            path.write_text(json.dumps(profile))
            result = subprocess.run(
                [
                    sys.executable,
                    "scripts/structure_factory/provider_profile_check.py",
                    str(path),
                    "--json",
                ],
                cwd=ROOT,
                text=True,
                capture_output=True,
            )
        self.assertNotEqual(result.returncode, 0)
        summary = json.loads(result.stdout)
        errors = summary["failures"][0]["errors"]
        self.assertIn("execution_ready_requires missing input_audit", errors)
        self.assertIn("execution_ready_requires missing contract_self_check", errors)

    def test_materialize_rejects_non_runpod_profiles(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            result = subprocess.run(
                [
                    sys.executable,
                    "scripts/structure_factory/sidecar_materialize.py",
                    "--campaign",
                    "modules/campaigns/cryoem-raw-to-atomic-no-download.v1.json",
                    "--provider-profile",
                    "modules/provider-profiles/local/workstation-no-download.v1.json",
                    "--out",
                    str(Path(tmp) / "local.json"),
                ],
                cwd=ROOT,
                text=True,
                capture_output=True,
            )
        self.assertNotEqual(result.returncode, 0)
        self.assertIn("RunPod launch manifests only", result.stderr)

    def test_runpod_manifest_passes(self) -> None:
        for manifest in sorted((ROOT / "runpod" / "launch-manifests").glob("*.json")):
            summary = self.run_json(
                "scripts/structure_factory/runpod_manifest_check.py",
                str(manifest.relative_to(ROOT)),
                "--json",
            )
            self.assertTrue(summary["ok"], summary)

    def test_runpod_scope_check_passes_for_bridge_manifests(self) -> None:
        summary = self.run_json(
            "scripts/structure_factory/runpod_scope_check.py",
            "runpod/bridge-manifests",
            "--json",
        )
        self.assertTrue(summary["ok"], summary)
        self.assertGreaterEqual(summary["checked"], 1)

    def test_runpod_scope_check_blocks_sibling_campaign_volume(self) -> None:
        manifest = json.loads((ROOT / "runpod" / "bridge-manifests" / "public-runtime-template.json").read_text())
        manifest["runpod"]["networkVolumeId"] = "PENDING-set-at-launch-from-GENECLUSTER_RUNPOD_NETWORK_VOLUME_ID"
        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp) / "bad-scope.json"
            path.write_text(json.dumps(manifest))
            result = subprocess.run(
                [
                    sys.executable,
                    "scripts/structure_factory/runpod_scope_check.py",
                    str(path),
                    "--json",
                ],
                cwd=ROOT,
                text=True,
                capture_output=True,
            )
        self.assertNotEqual(result.returncode, 0)
        summary = json.loads(result.stdout)
        self.assertFalse(summary["ok"], summary)
        errors = summary["failures"][0]["errors"]
        self.assertTrue(any("GENECLUSTER" in error for error in errors), summary)

    def test_runpod_scope_source_ready_accepts_fetchable_local_commit(self) -> None:
        manifest = json.loads((ROOT / "runpod" / "bridge-manifests" / "public-runtime-template.json").read_text())
        head = subprocess.run(
            ["git", "rev-parse", "HEAD"],
            cwd=ROOT,
            check=True,
            text=True,
            capture_output=True,
        ).stdout.strip()
        manifest["repo"]["url_or_path"] = str(ROOT)
        manifest["repo"]["commit_or_snapshot"] = head
        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp) / "source-ready.json"
            path.write_text(json.dumps(manifest))
            result = subprocess.run(
                [
                    sys.executable,
                    "scripts/structure_factory/runpod_scope_check.py",
                    str(path),
                    "--source-ready",
                    "--json",
                ],
                cwd=ROOT,
                text=True,
                capture_output=True,
            )
        self.assertEqual(result.returncode, 0, result.stdout + result.stderr)
        self.assertTrue(json.loads(result.stdout)["ok"])

    def test_runpod_scope_source_ready_blocks_unfetchable_commit(self) -> None:
        manifest = json.loads((ROOT / "runpod" / "bridge-manifests" / "public-runtime-template.json").read_text())
        manifest["repo"]["url_or_path"] = str(ROOT)
        manifest["repo"]["commit_or_snapshot"] = "0" * 40
        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp) / "source-blocked.json"
            path.write_text(json.dumps(manifest))
            result = subprocess.run(
                [
                    sys.executable,
                    "scripts/structure_factory/runpod_scope_check.py",
                    str(path),
                    "--source-ready",
                    "--json",
                ],
                cwd=ROOT,
                text=True,
                capture_output=True,
            )
        self.assertNotEqual(result.returncode, 0)
        summary = json.loads(result.stdout)
        self.assertFalse(summary["ok"], summary)
        errors = summary["failures"][0]["errors"]
        self.assertTrue(any("commit is not fetchable" in error for error in errors), summary)

    def test_fanout_estimator_raw_subset_passes(self) -> None:
        summary = self.run_json(
            "scripts/structure_factory/fanout_estimator.py",
            "--manifest",
            "runpod/launch-manifests/raw-subset-open.json",
            "--json",
        )
        self.assertTrue(summary["ok"], summary)
        self.assertEqual(summary["execution_profile"], "raw-subset-open")
        self.assertEqual(summary["estimates"]["raw_movie_files"], 100)
        self.assertEqual(summary["estimates"]["motion_frames"], 5000)
        self.assertTrue(summary["success_policy"]["raw_tool_outputs_must_be_normalized"])

    def test_fanout_estimator_blocks_exploding_context_lane(self) -> None:
        manifest = json.loads((ROOT / "runpod" / "launch-manifests" / "raw-subset-open.json").read_text())
        manifest["fanout_policy"]["max_context_micrographs"] = 10
        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp) / "fanout-blocked.json"
            path.write_text(json.dumps(manifest))
            result = subprocess.run(
                [
                    sys.executable,
                    "scripts/structure_factory/fanout_estimator.py",
                    "--manifest",
                    str(path),
                    "--json",
                ],
                cwd=ROOT,
                text=True,
                capture_output=True,
            )
        self.assertNotEqual(result.returncode, 0)
        summary = json.loads(result.stdout)
        self.assertFalse(summary["ok"], summary)
        self.assertTrue(any("context_micrographs exceeds" in blocker for blocker in summary["blockers"]))

    def test_input_audit_passes_for_no_download(self) -> None:
        summary = self.run_json(
            "scripts/structure_factory/input_audit.py",
            "--manifest",
            "runpod/launch-manifests/no-download-smoke.json",
            "--json",
        )
        self.assertTrue(summary["ok"], summary)
        self.assertEqual(summary["execution_profile"], "no-download-smoke")
        self.assertEqual(summary["missing_operator_items"], [])
        self.assertGreaterEqual(len(summary["known_inputs"]), 2)

    def test_input_audit_raw_subset_requires_operator_authorization(self) -> None:
        summary = self.run_json(
            "scripts/structure_factory/input_audit.py",
            "--manifest",
            "runpod/launch-manifests/raw-subset-open.json",
            "--json",
        )
        self.assertTrue(summary["ok"], summary)
        self.assertEqual(summary["execution_profile"], "raw-subset-open")
        self.assertEqual(summary["missing_operator_items"][0]["id"], "operator_authorization_for_raw_download")

    def write_minimal_smoke_artifacts(self, root: Path, mock_gpu: bool) -> None:
        (root / "validation").mkdir(parents=True, exist_ok=True)
        (root / "run-manifest.json").write_text(
            json.dumps(
                {
                    "schema_version": 1,
                    "run_id": "structure-factory-no-download-smoke",
                    "dry_run": mock_gpu,
                    "mock_tools": mock_gpu,
                    "gpu_ok": True,
                    "storage_ok": True,
                }
            )
        )
        (root / "validation" / "toolcheck.json").write_text(json.dumps({"ok": True, "mock_tools": mock_gpu}))
        (root / "validation" / "gpu.json").write_text(json.dumps({"ok": True, "mock_gpu": mock_gpu}))
        (root / "validation" / "storage.json").write_text(json.dumps({"ok": True}))
        (root / "validation" / "license-gates.json").write_text(json.dumps({"ok": True}))
        (root / "validation" / "input-audit.json").write_text(json.dumps({"ok": True, "missing_operator_items": []}))
        (root / "stage-progress.jsonl").write_text(
            json.dumps(
                {
                    "schema_version": 1,
                    "timestamp": "2026-04-30T00:00:00+00:00",
                    "stage_id": "toolcheck",
                    "status": "completed",
                    "message": "test fixture progress",
                }
            )
            + "\n"
        )
        (root / "validation" / "stage-contract-check.json").write_text(
            json.dumps(
                {
                    "ok": True,
                    "require_terminal": False,
                    "terminal_by_stage": {"toolcheck": "completed"},
                    "errors": [],
                    "warnings": [],
                }
            )
        )
        (root / "provenance.md").write_text("# provenance\n")

    def test_contract_self_check_allows_labeled_prep_mock(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            self.write_minimal_smoke_artifacts(root, mock_gpu=True)
            summary = self.run_json(
                "scripts/structure_factory/contract_self_check.py",
                "--manifest",
                "runpod/launch-manifests/no-download-smoke.json",
                "--artifact-root",
                str(root),
                "--execution-mode",
                "prep",
                "--json",
            )
        self.assertTrue(summary["ok"], summary)
        self.assertTrue(summary["warnings"], summary)

    def test_contract_self_check_blocks_mock_real_run(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            self.write_minimal_smoke_artifacts(root, mock_gpu=True)
            result = subprocess.run(
                [
                    sys.executable,
                    "scripts/structure_factory/contract_self_check.py",
                    "--manifest",
                    "runpod/launch-manifests/no-download-smoke.json",
                    "--artifact-root",
                    str(root),
                    "--execution-mode",
                    "real",
                    "--json",
                ],
                cwd=ROOT,
                text=True,
                capture_output=True,
            )
        self.assertNotEqual(result.returncode, 0)
        summary = json.loads(result.stdout)
        self.assertFalse(summary["ok"], summary)
        self.assertIn("real execution cannot pass with mock_gpu/mock_tools/dry_run markers", summary["errors"])

    def test_license_gates_absent_skip_optional(self) -> None:
        _, summary = self.run_json_with_env(
            "scripts/structure_factory/license_gate_check.py",
            "--manifest",
            "runpod/launch-manifests/no-download-smoke.json",
            "--json",
            env={
                "CRYOSPARC_LICENSE_ID": "",
                "PHENIX_ACCESS_REF": "",
                "CHIMERAX_ACCESS_REF": "",
            },
        )
        self.assertTrue(summary["ok"], summary)
        self.assertEqual(summary["gates"]["cryosparc"]["status"], "skipped")

    def test_enabled_invalid_license_gate_blocks(self) -> None:
        code, summary = self.run_json_with_env(
            "scripts/structure_factory/license_gate_check.py",
            "--manifest",
            "runpod/launch-manifests/raw-subset-gated.json",
            "--json",
            env={
                "STRUCTURE_FACTORY_ENABLE_CRYOSPARC": "1",
                "CRYOSPARC_LICENSE_ID": "example-license",
            },
            check=False,
        )
        self.assertNotEqual(code, 0)
        self.assertFalse(summary["ok"], summary)
        self.assertEqual(summary["gates"]["cryosparc"]["status"], "blocked")

    def test_raw_manifest_rejects_unbounded_downloads(self) -> None:
        manifest = json.loads((ROOT / "runpod" / "launch-manifests" / "raw-subset-open.json").read_text())
        manifest["download_plan"].pop("deterministic_rule")
        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp) / "invalid-raw.json"
            path.write_text(json.dumps(manifest))
            result = subprocess.run(
                [
                    sys.executable,
                    "scripts/structure_factory/runpod_manifest_check.py",
                    str(path),
                    "--json",
                ],
                cwd=ROOT,
                text=True,
                capture_output=True,
            )
        self.assertNotEqual(result.returncode, 0)
        summary = json.loads(result.stdout)
        self.assertIn("download_plan.deterministic_rule is required", summary["errors"])

    def test_raw_manifest_requires_fanout_policy(self) -> None:
        manifest = json.loads((ROOT / "runpod" / "launch-manifests" / "raw-subset-open.json").read_text())
        manifest.pop("fanout_policy")
        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp) / "missing-fanout.json"
            path.write_text(json.dumps(manifest))
            result = subprocess.run(
                [
                    sys.executable,
                    "scripts/structure_factory/runpod_manifest_check.py",
                    str(path),
                    "--json",
                ],
                cwd=ROOT,
                text=True,
                capture_output=True,
            )
        self.assertNotEqual(result.returncode, 0)
        summary = json.loads(result.stdout)
        self.assertIn("raw download profile requires fanout_policy", summary["errors"])

    def test_private_registry_manifest_requires_auth_refs(self) -> None:
        manifest = json.loads((ROOT / "runpod" / "launch-manifests" / "no-download-smoke.json").read_text())
        manifest["runpod"].pop("registry_auth")
        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp) / "invalid-private-image.json"
            path.write_text(json.dumps(manifest))
            result = subprocess.run(
                [
                    sys.executable,
                    "scripts/structure_factory/runpod_manifest_check.py",
                    str(path),
                    "--json",
                ],
                cwd=ROOT,
                text=True,
                capture_output=True,
            )
        self.assertNotEqual(result.returncode, 0)
        summary = json.loads(result.stdout)
        self.assertIn("missing runpod key: registry_auth", summary["errors"])

    def test_launch_preflight_execution_ready_blocks_public_template_without_digest_and_pinned_commit(self) -> None:
        code, summary = self.run_json_with_env(
            "scripts/structure_factory/runpod_launch_preflight.py",
            "--manifest",
            "runpod/launch-manifests/no-download-smoke.json",
            "--execution-ready",
            "--json",
            env={
                "RUNPOD_GHCR_REGISTRY_AUTH_ID": "",
                "RUNPOD_GHCR_USERNAME": "",
                "RUNPOD_GHCR_TOKEN": "",
                "STRUCTURE_FACTORY_REMOTE_LAUNCH_ALLOWED": "",
            },
            check=False,
        )
        self.assertNotEqual(code, 0)
        self.assertFalse(summary["ok"], summary)
        self.assertFalse(summary["registry_auth"]["required"], summary)
        self.assertTrue(any("image is not digest-pinned" in blocker for blocker in summary["blockers"]))
        self.assertTrue(any("repo.git_ref is not a 40-character commit SHA" in blocker for blocker in summary["blockers"]))
        self.assertTrue(any("STRUCTURE_FACTORY_REMOTE_LAUNCH_ALLOWED" in blocker for blocker in summary["blockers"]))

    def test_stage_contract_progress_requires_terminal_for_real_runs(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            progress = Path(tmp) / "stage-progress.jsonl"
            progress.write_text(
                json.dumps(
                    {
                        "schema_version": 1,
                        "timestamp": "2026-04-30T00:00:00+00:00",
                        "stage_id": "manifest_preflight",
                        "status": "completed",
                    }
                )
                + "\n"
            )
            result = subprocess.run(
                [
                    sys.executable,
                    "scripts/structure_factory/stage_contract_check.py",
                    "--stage-contract",
                    "runpod/stage-contracts/no-download-smoke.stage-contract.json",
                    "--progress-jsonl",
                    str(progress),
                    "--require-terminal",
                    "--json",
                ],
                cwd=ROOT,
                text=True,
                capture_output=True,
            )
        self.assertNotEqual(result.returncode, 0)
        summary = json.loads(result.stdout)
        self.assertIn("required stage has no terminal progress event: input_audit", summary["errors"])

    def test_stage_contract_requires_partial_summary_policy(self) -> None:
        contract = json.loads((ROOT / "runpod" / "stage-contracts" / "no-download-smoke.stage-contract.json").read_text())
        contract.pop("partial_summary")
        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp) / "missing-partial-policy.json"
            path.write_text(json.dumps(contract))
            result = subprocess.run(
                [
                    sys.executable,
                    "scripts/structure_factory/stage_contract_check.py",
                    "--stage-contract",
                    str(path),
                    "--json",
                ],
                cwd=ROOT,
                text=True,
                capture_output=True,
            )
        self.assertNotEqual(result.returncode, 0)
        summary = json.loads(result.stdout)
        self.assertIn("partial_summary policy is required", summary["errors"])

    def test_completed_stage_requires_validated_output_count(self) -> None:
        contract = json.loads((ROOT / "runpod" / "stage-contracts" / "no-download-smoke.stage-contract.json").read_text())
        events = []
        for stage in contract["stages"]:
            events.append(
                {
                    "schema_version": 1,
                    "timestamp": "2026-08-27T00:00:00+00:00",
                    "stage_id": stage["stage_id"],
                    "status": "completed",
                    "observed_output_count": len(stage["expected_outputs"]),
                }
            )

        events[0]["observed_output_count"] = 0
        with tempfile.TemporaryDirectory() as tmp:
            progress = Path(tmp) / "stage-progress.jsonl"
            progress.write_text("\n".join(json.dumps(event) for event in events) + "\n")
            result = subprocess.run(
                [
                    sys.executable,
                    "scripts/structure_factory/stage_contract_check.py",
                    "--stage-contract",
                    "runpod/stage-contracts/no-download-smoke.stage-contract.json",
                    "--progress-jsonl",
                    str(progress),
                    "--require-terminal",
                    "--json",
                ],
                cwd=ROOT,
                text=True,
                capture_output=True,
            )
        self.assertNotEqual(result.returncode, 0)
        summary = json.loads(result.stdout)
        self.assertTrue(
            any("observed_output_count=0" in error for error in summary["errors"]),
            summary,
        )

    def test_stage_progress_helper_validates_paths_before_completion(self) -> None:
        helper = ROOT / "runpod" / "entrypoints" / "stage-progress.sh"
        contract = ROOT / "runpod" / "stage-contracts" / "no-download-smoke.stage-contract.json"
        with tempfile.TemporaryDirectory() as tmp:
            run_root = Path(tmp)
            output = run_root / "validation" / "runpod-manifest-check.json"
            output.parent.mkdir()
            output.write_text("{}\n")
            progress = run_root / "stage-progress.jsonl"
            env = os.environ.copy()
            env.update(
                {
                    "STAGE_CONTRACT": str(contract),
                    "RUN_ROOT": str(run_root),
                    "STRUCTURE_FACTORY_STAGE_PROGRESS": str(progress),
                }
            )
            result = subprocess.run(
                [
                    "bash",
                    "-c",
                    'source "$1"; sf_stage_complete manifest_preflight "validated"',
                    "stage-progress-test",
                    str(helper),
                ],
                cwd=ROOT,
                env=env,
                text=True,
                capture_output=True,
            )
            event = json.loads(progress.read_text())

        self.assertEqual(0, result.returncode, result.stderr)
        self.assertEqual("completed", event["status"])
        self.assertEqual(1, event["observed_output_count"])

    def test_contract_self_check_blocks_undegraded_fallback(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            self.write_minimal_smoke_artifacts(root, mock_gpu=False)
            run_manifest = json.loads((root / "run-manifest.json").read_text())
            run_manifest["fallback_used"] = True
            run_manifest["final_status"] = "success"
            (root / "run-manifest.json").write_text(json.dumps(run_manifest))
            result = subprocess.run(
                [
                    sys.executable,
                    "scripts/structure_factory/contract_self_check.py",
                    "--manifest",
                    "runpod/launch-manifests/no-download-smoke.json",
                    "--artifact-root",
                    str(root),
                    "--execution-mode",
                    "prep",
                    "--json",
                ],
                cwd=ROOT,
                text=True,
                capture_output=True,
            )
        self.assertNotEqual(result.returncode, 0)
        summary = json.loads(result.stdout)
        self.assertIn("fallback was used but final status was not partial/degraded/blocked/failed", summary["errors"])

    def test_issue_template_passes(self) -> None:
        summary = self.run_json(
            "scripts/structure_factory/issue_check.py",
            "templates/linear-issue.md",
            "--json",
        )
        self.assertTrue(summary["ok"], summary)

    def test_campaign_issue_drafts_pass(self) -> None:
        summary = self.run_json(
            "scripts/structure_factory/issue_check.py",
            "campaigns/cryoem-raw-to-atomic-report/linear-issues",
            "--json",
        )
        self.assertTrue(summary["ok"], summary)
        self.assertGreaterEqual(summary["checked"], 1)

    def test_issue_file_reference_mode_detects_missing_repo_path(self) -> None:
        issue = (ROOT / "campaigns" / "cryoem-raw-to-atomic-report" / "linear-issues" / "BSF-W13-PROVIDER-ADAPTER-CONTRACTS.md").read_text()
        issue = issue.replace(
            "## Dependencies",
            "- `scripts/structure_factory/does_not_exist_chimerax_render.py` - deliberate missing path fixture\n\n## Dependencies",
            1,
        )
        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp) / "missing-reference.md"
            path.write_text(issue)
            result = subprocess.run(
                [
                    sys.executable,
                    "scripts/structure_factory/issue_check.py",
                    str(path),
                    "--check-file-references",
                    "--json",
                ],
                cwd=ROOT,
                text=True,
                capture_output=True,
            )
        self.assertNotEqual(result.returncode, 0)
        summary = json.loads(result.stdout)
        self.assertIn(
            {
                "issue": str(path.resolve()),
                "path": "scripts/structure_factory/does_not_exist_chimerax_render.py",
            },
            summary["missing_file_references"],
        )

    def test_issue_check_requires_provider_section(self) -> None:
        issue = (ROOT / "campaigns" / "cryoem-raw-to-atomic-report" / "linear-issues" / "BSF-W13-PROVIDER-ADAPTER-CONTRACTS.md").read_text()
        start = issue.index("## Provider / Execution Profile")
        end = issue.index("## Acceptance Criteria")
        issue = issue[:start] + issue[end:]
        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp) / "missing-provider.md"
            path.write_text(issue)
            result = subprocess.run(
                [
                    sys.executable,
                    "scripts/structure_factory/issue_check.py",
                    str(path),
                    "--json",
                ],
                cwd=ROOT,
                text=True,
                capture_output=True,
            )
        self.assertNotEqual(result.returncode, 0)
        summary = json.loads(result.stdout)
        errors = summary["failures"][0]["errors"]
        self.assertIn("missing heading: ## Provider / Execution Profile", errors)
        self.assertIn("missing provider line", errors)

    def test_launch_bundle_carries_self_check_contracts(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            out = Path(tmp) / "bundle"
            summary = self.run_json(
                "scripts/structure_factory/runpod_launch_bundle.py",
                "--manifest",
                "runpod/launch-manifests/no-download-smoke.json",
                "--out",
                str(out),
            )
            self.assertTrue(summary["ok"], summary)
            for rel in [
                "remote/input_audit.py",
                "remote/fanout_estimator.py",
                "remote/stage_contract_check.py",
                "remote/contract_self_check.py",
                "stage-contract.json",
                "modules/artifact-contracts/structure-report.v1.json",
            ]:
                self.assertTrue((out / rel).exists(), rel)
            audit = subprocess.run(
                [
                    sys.executable,
                    str(out / "remote" / "input_audit.py"),
                    "--manifest",
                    str(out / "launch-manifest.json"),
                    "--json",
                ],
                cwd=ROOT,
                check=True,
                text=True,
                capture_output=True,
            )
            self.assertTrue(json.loads(audit.stdout)["ok"])
            artifact_root = Path(tmp) / "artifact-root"
            self.write_minimal_smoke_artifacts(artifact_root, mock_gpu=True)
            self_check = subprocess.run(
                [
                    sys.executable,
                    str(out / "remote" / "contract_self_check.py"),
                    "--manifest",
                    str(out / "launch-manifest.json"),
                    "--artifact-root",
                    str(artifact_root),
                    "--execution-mode",
                    "prep",
                    "--json",
                ],
                cwd=ROOT,
                check=True,
                text=True,
                capture_output=True,
            )
            self.assertTrue(json.loads(self_check.stdout)["ok"])

    def test_runpod_entrypoints_are_parseable(self) -> None:
        for script in sorted((ROOT / "runpod" / "entrypoints").glob("*.sh")):
            subprocess.run(["bash", "-n", str(script)], cwd=ROOT, check=True)

    def test_runpod_bootstrap_scripts_are_parseable(self) -> None:
        for script in sorted((ROOT / "scripts" / "runpod").glob("*.sh")):
            subprocess.run(["bash", "-n", str(script)], cwd=ROOT, check=True)

    def test_network_volume_bootstrap_has_s1_safety_gates(self) -> None:
        script = (ROOT / "scripts" / "runpod" / "bootstrap_structure_factory_nv.sh").read_text()
        self.assertNotIn("fc36c7c61eed1fae0acb9bbe3e07db61b66ba01a", script)
        for marker in [
            "PROTEINMPNN_REF",
            "PROTEINMPNN_ACTUAL_COMMIT",
            "BOOTSTRAP_HEARTBEAT_SECONDS",
            "BOOTSTRAP_MAX_RUNTIME_SECONDS",
            "INSTALL_CHIMERAX",
            "CHIMERAX_DEB_URL",
            "chimerax.${CHIMERAX_VERSION}.deferred",
        ]:
            self.assertIn(marker, script)

    def test_bridge_manifests_record_actual_runpod_cost_fields(self) -> None:
        for manifest_path in sorted((ROOT / "runpod" / "bridge-manifests").glob("*.json")):
            manifest = json.loads(manifest_path.read_text())
            fields = manifest.get("monitoring", {}).get("record_pod_fields", [])
            self.assertIn("costPerHr", fields, manifest_path.name)
            self.assertIn("adjustedCostPerHr", fields, manifest_path.name)
            self.assertIn("desiredStatus", fields, manifest_path.name)


if __name__ == "__main__":
    unittest.main()
