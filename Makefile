PYTHON ?= python3
EXAMPLE ?= examples/pd-l1-binder-design-public
SMOKE_MANIFEST ?= runpod/launch-manifests/no-download-smoke.json
SCREENING_MANIFEST ?= examples/screening-superpowers/screening-manifest.json
SCREENING_RUNTIME ?= .runtime/screening-superpowers-fixture
TOOLCHECK_RUNTIME ?= .runtime/structure-factory-toolcheck
PROVIDER_ARTIFACT_ROOT ?= .runtime/provider-artifacts/example-run
PROVIDER_BRIDGE_CLI ?= symphony-neocloud-bridge

.PHONY: help list test catalog catalog-md read-only-audit validate validate-examples issue-dry-run issue-dry-run-check scaffold-check harness-check public-audit secret-scan docs-reference-check binder-lane-check \
	release-check public-switch-check public-contract-check preflight registry-check \
	module-check provider-check aws-profile-check neocloud-scope-check runpod-check \
	runpod-scope-check runpod-public-template-check stage-contract-check launch-preflight license-gate-check \
	input-audit toolcheck contract-self-check \
	provider-closeout-check \
	screening-module-check screening-manifest-check \
	screening-schema-check screening-fanout-estimate screening-fixture-run \
	screening-active-learning screening-results-check screening-check \
	provider-adapter-dry-run-check issue-check issue-file-check demo-t2r14-check demo-t2r14-report-check \
	demo-poltheta-prep-check demo-poltheta-report-prep-check demo-structure-ranking-prep-check demo-structure-comparison-prep-check \
	launch-bundle \
	demo-genie3-toolcheck-manifest demo-genie3-toolcheck-bridge-validate \
	demo-genie3-toolcheck-bridge-prepare demo-genie3-toolcheck-execution-packet \
	demo-genie3-toolcheck-prep-check \
	ls-remote-sha-check runpod-source-check mainline-readiness-check clean

help:
	@echo "Safe local:"
	@echo "  make validate                 Validate the default public example"
	@echo "  make validate-examples        Validate every example campaign manifest"
	@echo "  make catalog                  Write a JSON map of campaigns/examples/contracts"
	@echo "  make catalog-md               Write a Markdown map for human review"
	@echo "  make read-only-audit          Run reviewer checks without writing .runtime/"
	@echo "  make issue-dry-run            Write tracker-neutral drafts under .runtime/"
	@echo "  make issue-dry-run-check      Validate the generated .runtime issue drafts"
	@echo "  make harness-check            Check public agent/skill/docs surface"
	@echo "  make binder-lane-check        Check binder planning, adapter, and closeout contracts"
	@echo "  make release-check            Run public local release gates"
	@echo "  make public-switch-check      Run the full local public-readiness gate"
	@echo ""
	@echo "Cloud/provider prep without launch:"
	@echo "  make runpod-public-template-check  Validate tracked RunPod templates"
	@echo "  make runpod-scope-check            Check RunPod resource scoping placeholders"
	@echo "  make launch-preflight              Run no-launch manifest preflight"
	@echo "  make launch-bundle                 Build ignored review bundle under .runtime/"
	@echo "  make provider-closeout-check       Validate a pulled provider artifact root"
	@echo ""
	@echo "Writes ignored operator packet only:"
	@echo "  make demo-genie3-toolcheck-execution-packet"
	@echo ""
	@echo "Private/operator launcher required:"
	@echo "  Any paid pod/job creation, provider mutation, artifact pull, and cleanup proof"

list:
	find campaigns containers docs examples modules packs references runpod scripts skills src templates tests tools -maxdepth 4 -type f 2>/dev/null | sort

test:
	PYTHONPATH=src $(PYTHON) -m unittest discover -s tests

catalog:
	PYTHONPATH=src $(PYTHON) -m biosymphony_structure_factory.cli catalog . --out .runtime/public-capability-catalog.json

catalog-md:
	PYTHONPATH=src $(PYTHON) -m biosymphony_structure_factory.cli catalog . --format markdown --out .runtime/public-capability-catalog.md

read-only-audit:
	PYTHONDONTWRITEBYTECODE=1 PYTHONPATH=src $(PYTHON) -m biosymphony_structure_factory.cli doctor .
	PYTHONDONTWRITEBYTECODE=1 $(PYTHON) scripts/structure_factory/public_doc_reference_check.py --repo-root . --json
	PYTHONDONTWRITEBYTECODE=1 $(PYTHON) scripts/structure_factory/runpod_public_template_check.py runpod/bridge-manifests --json
	PYTHONDONTWRITEBYTECODE=1 $(PYTHON) scripts/structure_factory/runpod_public_template_check.py runpod/launch-manifests --json

validate:
	PYTHONPATH=src $(PYTHON) -m biosymphony_structure_factory.cli validate $(EXAMPLE)

validate-examples:
	for manifest in examples/*/campaign-manifest.json; do \
		PYTHONPATH=src $(PYTHON) -m biosymphony_structure_factory.cli validate "$$(dirname "$$manifest")" || exit 1; \
	done

issue-dry-run:
	PYTHONPATH=src $(PYTHON) -m biosymphony_structure_factory.cli issue-dry-run $(EXAMPLE) --out .runtime/pd-l1-issues

issue-dry-run-check: issue-dry-run
	$(PYTHON) scripts/structure_factory/issue_check.py .runtime/pd-l1-issues --json

scaffold-check:
	rm -rf .runtime/scaffold-demo
	PYTHONPATH=src $(PYTHON) -m biosymphony_structure_factory.cli scaffold-campaign .runtime/scaffold-demo \
		--campaign-id scaffold-demo \
		--target-label "A2A receptor" \
		--public-accession "PDB:5G53" \
		--window "TM6 activation microswitch"
	PYTHONPATH=src $(PYTHON) -m biosymphony_structure_factory.cli validate .runtime/scaffold-demo

harness-check:
	PYTHONPATH=src $(PYTHON) -m biosymphony_structure_factory.cli harness-check .

public-audit:
	PYTHONPATH=src $(PYTHON) -m biosymphony_structure_factory.cli audit .

docs-reference-check:
	$(PYTHON) scripts/structure_factory/public_doc_reference_check.py --repo-root . --json

binder-lane-check:
	PYTHONDONTWRITEBYTECODE=1 PYTHONPATH=src $(PYTHON) scripts/structure_factory/binder_lane_check.py --repo-root . --json

secret-scan:
	@if command -v gitleaks >/dev/null 2>&1; then \
		gitleaks detect --source . --no-banner --redact --verbose; \
		gitleaks dir . --no-banner --redact --verbose; \
	else \
		echo "gitleaks not installed; secret scan is required."; \
		exit 1; \
	fi

preflight:
	$(PYTHON) scripts/structure_factory/preflight.py --repo-root . --json

registry-check:
	$(PYTHON) scripts/structure_factory/software_registry_check.py references/software-registry.yaml --json

module-check:
	for manifest in modules/campaigns/*.json; do \
		$(PYTHON) scripts/structure_factory/module_manifest_check.py "$$manifest" --check-all --json || exit 1; \
	done

provider-check:
	$(PYTHON) scripts/structure_factory/provider_profile_check.py modules/provider-profiles --json

aws-profile-check:
	$(PYTHON) scripts/structure_factory/aws_profile_check.py modules/provider-profiles/aws --json

neocloud-scope-check:
	$(PYTHON) scripts/structure_factory/neocloud_scope_check.py modules/provider-profiles/neocloud --json

runpod-check:
	for manifest in runpod/launch-manifests/*.json; do \
		$(PYTHON) scripts/structure_factory/runpod_manifest_check.py "$$manifest" --json || exit 1; \
	done

runpod-scope-check:
	$(PYTHON) scripts/structure_factory/runpod_scope_check.py runpod/bridge-manifests --json

runpod-public-template-check:
	$(PYTHON) scripts/structure_factory/runpod_public_template_check.py runpod/bridge-manifests --json
	$(PYTHON) scripts/structure_factory/runpod_public_template_check.py runpod/launch-manifests --json

ls-remote-sha-check:
	$(PYTHON) scripts/structure_factory/ls_remote_sha_check.py --json

runpod-source-check: runpod-public-template-check ls-remote-sha-check

stage-contract-check:
	for contract in runpod/stage-contracts/*.stage-contract.json; do \
		$(PYTHON) scripts/structure_factory/stage_contract_check.py --stage-contract "$$contract" --json || exit 1; \
	done

launch-preflight:
	$(PYTHON) scripts/structure_factory/runpod_launch_preflight.py --manifest $(SMOKE_MANIFEST) --json

license-gate-check:
	$(PYTHON) scripts/structure_factory/license_gate_check.py --manifest $(SMOKE_MANIFEST) --json

input-audit:
	mkdir -p $(TOOLCHECK_RUNTIME)/validation
	$(PYTHON) scripts/structure_factory/input_audit.py --manifest $(SMOKE_MANIFEST) --out $(TOOLCHECK_RUNTIME)/validation/input-audit.json --json

toolcheck:
	$(PYTHON) scripts/structure_factory/toolcheck_runner.py --manifest $(SMOKE_MANIFEST) --out $(TOOLCHECK_RUNTIME) --mock-gpu

contract-self-check: input-audit toolcheck
	$(PYTHON) scripts/structure_factory/contract_self_check.py --manifest $(SMOKE_MANIFEST) --artifact-root $(TOOLCHECK_RUNTIME) --execution-mode prep --json

provider-closeout-check:
	$(PYTHON) scripts/structure_factory/provider_closeout_check.py --artifact-root $(PROVIDER_ARTIFACT_ROOT) --execution-mode prep --json


screening-module-check:
	$(PYTHON) scripts/structure_factory/module_manifest_check.py modules/campaigns/screening-superpowers.v1.json --check-all --json

screening-manifest-check:
	$(PYTHON) scripts/structure_factory/screening_manifest_check.py $(SCREENING_MANIFEST) --json

screening-schema-check:
	$(PYTHON) scripts/structure_factory/screening_schema_check.py --json

screening-fanout-estimate:
	$(PYTHON) scripts/structure_factory/screening_fanout_estimator.py --manifest $(SCREENING_MANIFEST) --out .runtime/screening-superpowers-fanout.json --json

screening-fixture-run:
	$(PYTHON) scripts/structure_factory/screening_fixture_run.py --manifest $(SCREENING_MANIFEST) --out $(SCREENING_RUNTIME) --json

screening-active-learning: screening-fixture-run
	$(PYTHON) scripts/structure_factory/screening_active_learning.py --artifact-root $(SCREENING_RUNTIME) --json

screening-results-check: screening-fixture-run
	$(PYTHON) scripts/structure_factory/screening_results_check.py --artifact-root $(SCREENING_RUNTIME) --json

screening-check: screening-module-check aws-profile-check neocloud-scope-check screening-manifest-check screening-fanout-estimate screening-active-learning screening-results-check screening-schema-check

provider-adapter-dry-run-check:
	$(PYTHON) scripts/structure_factory/provider_adapter_dry_run.py examples/screening-superpowers/provider-run-spec.json --out .runtime/provider-adapter-dry-run --json

demo-t2r14-check:
	$(PYTHON) scripts/structure_factory/t2r14_structure_report.py --out .runtime/t2r14-structure-report-local/runpod-execution --json
	$(PYTHON) scripts/structure_factory/build_t2r14_report_bridge_manifest.py
	@if command -v $(PROVIDER_BRIDGE_CLI) >/dev/null 2>&1; then \
		$(PROVIDER_BRIDGE_CLI) validate-manifest .runtime/bridge-manifests/t2r14-structure-report.json --json; \
		$(PROVIDER_BRIDGE_CLI) prepare .runtime/bridge-manifests/t2r14-structure-report.json --out-dir .runtime/t2r14-structure-report-packet --json; \
	else \
			echo "$(PROVIDER_BRIDGE_CLI) not installed; local report and manifest builder completed."; \
	fi

demo-t2r14-report-check: demo-t2r14-check

demo-poltheta-prep-check:
	$(PYTHON) scripts/structure_factory/build_poltheta_report_bridge_manifest.py
	@if command -v $(PROVIDER_BRIDGE_CLI) >/dev/null 2>&1; then \
		$(PROVIDER_BRIDGE_CLI) validate-manifest .runtime/bridge-manifests/poltheta-map-model-report.json --json; \
		$(PROVIDER_BRIDGE_CLI) prepare .runtime/bridge-manifests/poltheta-map-model-report.json --out-dir .runtime/poltheta-map-model-packet --json; \
	else \
		echo "$(PROVIDER_BRIDGE_CLI) not installed; public manifest builder completed. Full report prep may require public map download."; \
	fi

demo-poltheta-report-prep-check: demo-poltheta-prep-check

demo-structure-ranking-prep-check:
	$(PYTHON) scripts/structure_factory/build_dual_structure_comparison_bridge_manifest.py
	@if command -v $(PROVIDER_BRIDGE_CLI) >/dev/null 2>&1; then \
		$(PROVIDER_BRIDGE_CLI) validate-manifest .runtime/bridge-manifests/dual-structure-comparison.json --json; \
		$(PROVIDER_BRIDGE_CLI) prepare .runtime/bridge-manifests/dual-structure-comparison.json --out-dir .runtime/dual-structure-comparison-packet --json; \
	else \
		echo "$(PROVIDER_BRIDGE_CLI) not installed; public structure-comparison manifest builder completed."; \
	fi

demo-structure-comparison-prep-check: demo-structure-ranking-prep-check

launch-bundle:
	$(PYTHON) scripts/structure_factory/runpod_launch_bundle.py --manifest $(SMOKE_MANIFEST) --out .runtime/structure-factory-no-download-smoke

demo-genie3-toolcheck-manifest:
	$(PYTHON) scripts/structure_factory/build_genie3_toolcheck_bridge_manifest.py

demo-genie3-toolcheck-bridge-validate: demo-genie3-toolcheck-manifest
	@if command -v $(PROVIDER_BRIDGE_CLI) >/dev/null 2>&1; then \
		$(PROVIDER_BRIDGE_CLI) validate-manifest .runtime/bridge-manifests/genie3-no-download-toolcheck.json --json; \
	else \
		echo "$(PROVIDER_BRIDGE_CLI) not installed; skipped bridge validation."; \
	fi

demo-genie3-toolcheck-bridge-prepare: demo-genie3-toolcheck-manifest
	@if command -v $(PROVIDER_BRIDGE_CLI) >/dev/null 2>&1; then \
		$(PROVIDER_BRIDGE_CLI) prepare .runtime/bridge-manifests/genie3-no-download-toolcheck.json --out-dir .runtime/genie3-no-download-toolcheck-packet --json; \
	else \
		echo "$(PROVIDER_BRIDGE_CLI) not installed; skipped bridge packet prepare."; \
	fi

demo-genie3-toolcheck-execution-packet:
	@if [ "$$STRUCTURE_FACTORY_OPERATOR_GATE_ACK" != "I_UNDERSTAND_THIS_WRITES_RUNTIME_EXECUTION_STATE" ]; then \
		echo "Refusing to write execution packet. Set STRUCTURE_FACTORY_OPERATOR_GATE_ACK=I_UNDERSTAND_THIS_WRITES_RUNTIME_EXECUTION_STATE. This target writes ignored runtime state and does not start a provider."; \
		exit 2; \
	fi
	STRUCTURE_FACTORY_OPERATOR_GATE_ACK=I_UNDERSTAND_THIS_WRITES_RUNTIME_EXECUTION_STATE \
		$(PYTHON) scripts/structure_factory/build_genie3_toolcheck_bridge_manifest.py --execution-ready --out .runtime/genie3-no-download-toolcheck.execution-ready.json
	@echo "Runtime packet written. After readiness checks, use the selected validated provider client only with explicit human authorization."

demo-genie3-toolcheck-prep-check: demo-genie3-toolcheck-manifest demo-genie3-toolcheck-bridge-validate demo-genie3-toolcheck-bridge-prepare

mainline-readiness-check: public-contract-check docs-reference-check harness-check

issue-check:
	for issue_dir in campaigns/*/linear-issues; do \
		if [ -d "$$issue_dir" ] && find "$$issue_dir" -maxdepth 1 -name '*.md' -type f | read _; then \
			$(PYTHON) scripts/structure_factory/issue_check.py "$$issue_dir" --json || exit 1; \
		fi; \
	done

issue-file-check:
	for issue_dir in campaigns/*/linear-issues; do \
		if [ -d "$$issue_dir" ] && find "$$issue_dir" -maxdepth 1 -name '*.md' -type f | read _; then \
			$(PYTHON) scripts/structure_factory/issue_check.py "$$issue_dir" --check-file-references --json || exit 1; \
		fi; \
	done

public-contract-check:
	@if git ls-files | rg '(^|/)(\.runtime|artifacts|outputs|logs|runpod-runs|scratch|_book|__pycache__)/|\.(pyc|local\.json|pdb|cif|mmcif|bcif|map|mrc|mrcs|star|trb|mp4|mov|gif|npz|npy|pt|pth|safetensors|onnx|ckpt|pkl|pickle|joblib|parquet|feather|arrow|duckdb|sqlite|sqlite3|db|sdf|mol2|zip|tar|tgz|gz|xz|zst|7z|bz2|rar|pml|fasta|fa|fastq|pem|key)$$'; then \
		echo "tracked public-blocked generated or heavy artifacts found"; exit 1; \
	fi
	@if rg -n -g '*.json' 'base64 -d|gunzip|xz -d|approved_at": "20[0-9][0-9]-|US-[A-Z]{2}-[0-9]' runpod/bridge-manifests runpod/launch-manifests; then \
		echo "Tracked RunPod templates must not contain embedded payloads, live approval, or concrete provider resources"; exit 1; \
	fi
	PYTHONPATH=src $(PYTHON) -m biosymphony_structure_factory.cli audit .
	$(PYTHON) scripts/structure_factory/runpod_public_template_check.py runpod/bridge-manifests --json
	$(PYTHON) scripts/structure_factory/runpod_public_template_check.py runpod/launch-manifests --json

release-check: catalog test validate validate-examples issue-dry-run scaffold-check harness-check public-audit docs-reference-check public-contract-check binder-lane-check secret-scan

public-switch-check: release-check preflight registry-check module-check provider-check runpod-check runpod-scope-check runpod-public-template-check stage-contract-check issue-check issue-file-check screening-check provider-adapter-dry-run-check contract-self-check secret-scan

clean:
	find . -type d -name "__pycache__" -prune -exec rm -rf {} +
	find . -type d -name ".pytest_cache" -prune -exec rm -rf {} +
	find . -type d -name ".mypy_cache" -prune -exec rm -rf {} +
	find . -type d -name ".ruff_cache" -prune -exec rm -rf {} +
	rm -rf .runtime build dist *.egg-info
