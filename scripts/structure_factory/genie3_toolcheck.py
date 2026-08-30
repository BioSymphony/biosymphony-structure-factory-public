#!/usr/bin/env python3
"""Genie 3 no-download toolcheck (RunPod-side runner).

Probes host, downloads pinned source as a tarball (no git required), reads
dependency manifests, attempts pip install, runs smoke commands, HEADs the
HuggingFace weights revision (no body download), emits structured evidence.
Stdlib + torch + pip only. Soft-fail per stage; partial results are the
intended deliverable.
"""

from __future__ import annotations

import argparse
import datetime as _dt
import hashlib
import json
import os
import platform
import shutil
import subprocess
import sys
import tarfile
import time
import urllib.error
import urllib.request
from pathlib import Path
from typing import Any

GENIE3_REPO = "aqlaboratory/genie3"
GENIE3_PINNED_SHA = "5214459c42e69b01fadfc7d7ebda09d8e5082115"
GENIE3_HF_REPO = "yeqinglin/genie3"
GENIE3_HF_REVISION = "9ae31ebb8c56eebdc05ab282a8fd3f6a6d2a03a2"

SMOKE_COMMANDS = [
    [sys.executable, "-c", "import genie3; print(genie3.__file__)"],
    ["genie3", "--help"],
    ["genie3", "run", "--help"],
    ["genie3", "generate", "--help"],
    ["genie3", "evaluate", "--help"],
    [sys.executable, "-m", "genie3.cli", "--help"],
    [sys.executable, "-m", "genie3", "--help"],
]


def utc_iso() -> str:
    return _dt.datetime.now(_dt.timezone.utc).isoformat(timespec="seconds").replace("+00:00", "Z")


class Recorder:
    def __init__(self, artifact_root: Path):
        self.root = artifact_root
        for sub in ("validation", "logs", "source"):
            (self.root / sub).mkdir(parents=True, exist_ok=True)
        self.progress = self.root / "stage-progress.jsonl"
        self.commands = self.root / "executed-commands.jsonl"
        self.stage_states: dict[str, str] = {}

    def stage(self, stage_id: str, status: str, **fields: Any) -> None:
        rec = {"stage_id": stage_id, "status": status, "timestamp": utc_iso(), **fields}
        with self.progress.open("a") as fh:
            fh.write(json.dumps(rec) + "\n")
        self.stage_states[stage_id] = status

    def command(self, cmd: list[str], rc: int, stdout: str, stderr: str, duration: float) -> None:
        rec = {
            "command": cmd,
            "exit_code": rc,
            "duration_seconds": round(duration, 3),
            "stdout_head": stdout[:2048],
            "stderr_head": stderr[:2048],
            "stdout_bytes": len(stdout.encode("utf-8")),
            "stderr_bytes": len(stderr.encode("utf-8")),
            "timestamp": utc_iso(),
        }
        with self.commands.open("a") as fh:
            fh.write(json.dumps(rec) + "\n")


def run(cmd: list[str], cwd: Path | None = None, timeout: int = 1200) -> tuple[int, str, str, float]:
    start = time.time()
    try:
        proc = subprocess.run(cmd, cwd=cwd, capture_output=True, text=True, timeout=timeout, check=False)
        return proc.returncode, proc.stdout, proc.stderr, time.time() - start
    except subprocess.TimeoutExpired as exc:
        return 124, exc.stdout or "", exc.stderr or f"timeout {timeout}s", time.time() - start
    except FileNotFoundError as exc:
        return 127, "", f"FileNotFoundError: {exc}", time.time() - start


def stage_host_probe(rec: Recorder) -> dict[str, Any]:
    rec.stage("host_probe", "in_progress")
    info: dict[str, Any] = {
        "python_version": sys.version,
        "python_executable": sys.executable,
        "platform": platform.platform(),
        "machine": platform.machine(),
        "uname": dict(zip(("system", "node", "release", "version", "machine"), platform.uname())),
        "env_subset": {k: os.environ.get(k) for k in (
            "CUDA_HOME", "CUDA_PATH", "CUDA_VERSION", "LD_LIBRARY_PATH",
            "GENIE3_INSTALL", "GENIE3_DOWNLOAD_WEIGHTS",
            "GENIE3_DOWNLOAD_TRAINING_DATA", "GENIE3_ALLOW_COLABFOLD_PARAMS",
            "GENIE3_OPERATOR_GATE_ACK",
        )},
    }
    rc, out, err, dur = run(["nvidia-smi", "--query-gpu=name,driver_version,memory.total", "--format=csv,noheader"], timeout=30)
    rec.command(["nvidia-smi"], rc, out, err, dur)
    info["nvidia_smi"] = {"exit_code": rc, "stdout": out.strip(), "stderr": err.strip()[:512]}

    torch_probe = (
        "import json\n"
        "try:\n"
        "  import torch\n"
        "  ok=torch.cuda.is_available()\n"
        "  r={'ok':True,'torch':torch.__version__,'cuda_available':ok,'device_count':torch.cuda.device_count() if ok else 0}\n"
        "  if ok:\n"
        "    r['device_name']=torch.cuda.get_device_name(0)\n"
        "    r['cuda_version_torch']=torch.version.cuda\n"
        "  print(json.dumps(r))\n"
        "except Exception as e:\n"
        "  print(json.dumps({'ok':False,'error':str(e),'error_type':type(e).__name__}))\n"
    )
    rc, out, err, dur = run([sys.executable, "-c", torch_probe], timeout=120)
    rec.command([sys.executable, "-c", "torch_gpu_probe"], rc, out, err, dur)
    info["torch"] = _parse_json_tail(out, fallback={"ok": False, "error": err[:512]})

    jax_probe = (
        "import json\n"
        "try:\n"
        "  import jax\n"
        "  print(json.dumps({'ok':True,'jax':jax.__version__,'devices':[str(d) for d in jax.devices()]}))\n"
        "except Exception as e:\n"
        "  print(json.dumps({'ok':False,'error':str(e),'error_type':type(e).__name__}))\n"
    )
    rc, out, err, dur = run([sys.executable, "-c", jax_probe], timeout=60)
    rec.command([sys.executable, "-c", "jax_probe"], rc, out, err, dur)
    info["jax"] = _parse_json_tail(out, fallback={"ok": False})

    (rec.root / "validation" / "host_probe.json").write_text(json.dumps(info, indent=2, sort_keys=True) + "\n")
    rec.stage("host_probe", "completed", torch_cuda_ok=info["torch"].get("cuda_available", False))
    return info


def _parse_json_tail(out: str, fallback: dict[str, Any]) -> dict[str, Any]:
    lines = [l for l in out.strip().splitlines() if l.strip()]
    for line in reversed(lines):
        try:
            return json.loads(line)
        except json.JSONDecodeError:
            continue
    return fallback


def stage_source_download(rec: Recorder) -> dict[str, Any]:
    rec.stage("source_download", "in_progress", repo=GENIE3_REPO, sha=GENIE3_PINNED_SHA)
    url = f"https://github.com/{GENIE3_REPO}/archive/{GENIE3_PINNED_SHA}.tar.gz"
    archive_path = rec.root / "source" / f"genie3-{GENIE3_PINNED_SHA[:12]}.tar.gz"
    extract_dir = rec.root / "source" / "genie3"
    info: dict[str, Any] = {"url": url, "archive_path": str(archive_path), "extract_dir": str(extract_dir)}
    try:
        data: bytes | None = None
        for attempt in range(3):
            try:
                req = urllib.request.Request(url, headers={"User-Agent": "structure-factory-toolcheck/1.0"})
                with urllib.request.urlopen(req, timeout=120) as resp:
                    data = resp.read()
                break
            except (urllib.error.URLError, TimeoutError) as exc:
                info.setdefault("retries", []).append(str(exc))
                if attempt == 2:
                    raise
                time.sleep(2 ** attempt)
        assert data is not None
        archive_path.write_bytes(data)
        info["archive_bytes"] = len(data)
        info["archive_sha256"] = hashlib.sha256(data).hexdigest()

        if extract_dir.exists():
            shutil.rmtree(extract_dir)
        extract_dir.mkdir(parents=True)
        with tarfile.open(archive_path, "r:gz") as tar:
            for m in tar.getmembers():
                parts = m.name.split("/", 1)
                if len(parts) != 2 or not parts[1]:
                    continue
                m.name = parts[1]
                target = (extract_dir / m.name).resolve()
                if not str(target).startswith(str(extract_dir.resolve())):
                    continue
                tar.extract(m, extract_dir)
        info["extracted_files"] = sum(1 for p in extract_dir.rglob("*") if p.is_file())
        rec.stage("source_download", "completed", archive_bytes=info["archive_bytes"], extracted_files=info["extracted_files"])
    except Exception as exc:
        info["error"] = str(exc)
        info["error_type"] = type(exc).__name__
        rec.stage("source_download", "failed", error=str(exc))
    (rec.root / "validation" / "source_download.json").write_text(json.dumps(info, indent=2, sort_keys=True) + "\n")
    return info


def stage_dependency_review(rec: Recorder, source: dict[str, Any]) -> dict[str, Any]:
    rec.stage("dependency_review", "in_progress")
    extract_dir = Path(source.get("extract_dir", ""))
    info: dict[str, Any] = {"manifests": {}}
    if not extract_dir.is_dir():
        info["error"] = "source not extracted"
        rec.stage("dependency_review", "failed", error=info["error"])
        (rec.root / "validation" / "dependency_review.json").write_text(json.dumps(info, indent=2) + "\n")
        return info
    candidates = [
        "setup.py", "setup.cfg", "pyproject.toml",
        "requirements.txt", "requirements-dev.txt", "requirements_lock.txt",
        "environment.yml", "environment.yaml", "conda.yml",
        "README.md", "INSTALL.md", "docs/setup.md", "docs/install.md",
        "docs/setup_genie3.md",
    ]
    for name in candidates:
        p = extract_dir / name
        if p.is_file():
            try:
                content = p.read_text(encoding="utf-8", errors="replace")
            except Exception as exc:
                content = f"<read_error: {exc}>"
            info["manifests"][name] = {"size": p.stat().st_size, "first_8kb": content[:8192]}
    info["top_level_entries"] = sorted([p.name for p in extract_dir.iterdir()])
    rec.stage("dependency_review", "completed", manifest_count=len(info["manifests"]))
    (rec.root / "validation" / "dependency_review.json").write_text(json.dumps(info, indent=2, sort_keys=True) + "\n")
    return info


def stage_pip_install(rec: Recorder, source: dict[str, Any], do_install: bool) -> dict[str, Any]:
    rec.stage("pip_install", "in_progress")
    extract_dir = Path(source.get("extract_dir", ""))
    info: dict[str, Any] = {"do_install": do_install, "extract_dir": str(extract_dir)}
    if not do_install:
        info["status"] = "skipped"
        rec.stage("pip_install", "completed", skipped=True)
        (rec.root / "validation" / "pip_install.json").write_text(json.dumps(info, indent=2) + "\n")
        return info
    if not extract_dir.is_dir():
        info["error"] = "source not extracted"
        rec.stage("pip_install", "failed", error=info["error"])
        (rec.root / "validation" / "pip_install.json").write_text(json.dumps(info, indent=2) + "\n")
        return info
    has_setup = (extract_dir / "setup.py").is_file() or (extract_dir / "pyproject.toml").is_file()
    if not has_setup:
        info["status"] = "skipped"
        info["skip_reason"] = "no setup.py or pyproject.toml in extracted source"
        rec.stage("pip_install", "completed", skipped=True, reason=info["skip_reason"])
        (rec.root / "validation" / "pip_install.json").write_text(json.dumps(info, indent=2) + "\n")
        return info
    cmd = [sys.executable, "-m", "pip", "install", "--no-cache-dir", "-e", str(extract_dir)]
    rc, out, err, dur = run(cmd, timeout=1800)
    rec.command(cmd, rc, out, err, dur)
    log_path = rec.root / "logs" / "pip_install.log"
    log_path.write_text(f"# stdout\n{out}\n\n# stderr\n{err}\n")
    info["exit_code"] = rc
    info["log_path"] = str(log_path)
    info["duration_seconds"] = round(dur, 3)
    if rc == 0:
        rc2, freeze, _, _ = run([sys.executable, "-m", "pip", "freeze"], timeout=120)
        (rec.root / "logs" / "pip_freeze.txt").write_text(freeze)
        info["pip_freeze_lines"] = len(freeze.splitlines())
        rec.stage("pip_install", "completed", pip_freeze_lines=info["pip_freeze_lines"])
    else:
        rec.stage("pip_install", "failed", exit_code=rc)
    (rec.root / "validation" / "pip_install.json").write_text(json.dumps(info, indent=2, sort_keys=True) + "\n")
    return info


def stage_smoke_commands(rec: Recorder) -> dict[str, Any]:
    rec.stage("smoke_commands", "in_progress")
    attempts = []
    any_ok = False
    for cmd in SMOKE_COMMANDS:
        rc, out, err, dur = run(cmd, timeout=120)
        rec.command(cmd, rc, out, err, dur)
        attempts.append({
            "command": cmd,
            "exit_code": rc,
            "stdout_head": out[:1024],
            "stderr_head": err[:1024],
            "duration_seconds": round(dur, 3),
        })
        if rc == 0:
            any_ok = True
    info = {"attempts": attempts, "any_smoke_ok": any_ok}
    rec.stage("smoke_commands", "completed" if any_ok else "failed", any_smoke_ok=any_ok)
    (rec.root / "validation" / "smoke_commands.json").write_text(json.dumps(info, indent=2, sort_keys=True) + "\n")
    return info


def stage_hf_weights_probe(rec: Recorder) -> dict[str, Any]:
    rec.stage("hf_weights_probe", "in_progress")
    info: dict[str, Any] = {"repo": GENIE3_HF_REPO, "revision": GENIE3_HF_REVISION}
    api_url = f"https://huggingface.co/api/models/{GENIE3_HF_REPO}/revision/{GENIE3_HF_REVISION}"
    try:
        req = urllib.request.Request(api_url, headers={"User-Agent": "structure-factory-toolcheck/1.0"})
        with urllib.request.urlopen(req, timeout=60) as resp:
            data = json.loads(resp.read())
        info["status"] = "ok"
        info["sha"] = data.get("sha")
        siblings = data.get("siblings", []) or []
        info["sibling_count"] = len(siblings)
        info["sibling_paths_sample"] = [s.get("rfilename") for s in siblings[:25]]
        info["model_id"] = data.get("modelId") or data.get("id")
        rec.stage("hf_weights_probe", "completed", sibling_count=info["sibling_count"])
    except Exception as exc:
        info["status"] = "failed"
        info["error"] = str(exc)
        info["error_type"] = type(exc).__name__
        rec.stage("hf_weights_probe", "failed", error=str(exc))
    (rec.root / "validation" / "hf_weights_probe.json").write_text(json.dumps(info, indent=2, sort_keys=True) + "\n")
    return info


def stage_emit_artifacts(rec: Recorder, run_id: str, host: dict, source: dict, deps: dict, install: dict, smoke: dict, hf: dict) -> dict[str, Any]:
    rec.stage("emit_artifacts", "in_progress")

    overall_ok = (
        source.get("error") is None
        and (install.get("exit_code") == 0 or install.get("status") == "skipped")
        and smoke.get("any_smoke_ok", False)
    )

    versions = {
        "schema_version": 1,
        "run_id": run_id,
        "completed_at": utc_iso(),
        "genie3_pinned_commit_sha": GENIE3_PINNED_SHA,
        "genie3_hf_repo": GENIE3_HF_REPO,
        "genie3_hf_revision": GENIE3_HF_REVISION,
        "python_version": sys.version.split()[0],
        "torch": host.get("torch"),
        "jax": host.get("jax"),
        "nvidia_smi_stdout": host.get("nvidia_smi", {}).get("stdout", ""),
        "source_download_ok": source.get("error") is None,
        "pip_install_exit_code": install.get("exit_code"),
        "pip_install_status": install.get("status"),
        "smoke_any_ok": smoke.get("any_smoke_ok", False),
        "hf_probe_status": hf.get("status"),
    }
    (rec.root / "versions.json").write_text(json.dumps(versions, indent=2, sort_keys=True) + "\n")

    validation_ledger = {
        "schema_version": 1,
        "run_id": run_id,
        "campaign_id": "genie3-no-download-toolcheck",
        "claim_level": "candidate" if overall_ok else "insufficient_evidence",
        "claims": [
            {"claim": "source_download_ok", "value": source.get("error") is None, "evidence": "validation/source_download.json"},
            {"claim": "dependency_review_complete", "value": bool(deps.get("manifests")), "evidence": "validation/dependency_review.json"},
            {"claim": "pip_install_succeeded", "value": install.get("exit_code") == 0, "evidence": "validation/pip_install.json"},
            {"claim": "smoke_command_succeeded", "value": smoke.get("any_smoke_ok", False), "evidence": "validation/smoke_commands.json"},
            {"claim": "hf_weights_revision_resolvable", "value": hf.get("status") == "ok", "evidence": "validation/hf_weights_probe.json"},
        ],
        "forbidden_claims": [
            "genie3_runtime_validated",
            "weights_downloaded",
            "inference_succeeded",
            "binder_designed",
        ],
        "notes": "Toolcheck only. No weights downloaded. No inference. No design output.",
    }
    (rec.root / "validation_ledger.json").write_text(json.dumps(validation_ledger, indent=2, sort_keys=True) + "\n")

    md = [
        "# Genie 3 No-Download Toolcheck Report",
        "",
        f"- run_id: `{run_id}`",
        f"- completed_at: {versions['completed_at']}",
        f"- pinned_commit: `{GENIE3_PINNED_SHA}`",
        f"- pinned_hf_revision: `{GENIE3_HF_REVISION}`",
        f"- overall_outcome: **{'OK' if overall_ok else 'PARTIAL/FAILED'}**",
        f"- claim_level: **{validation_ledger['claim_level']}**",
        "",
        "## Stages",
        "",
        "| stage | status |",
        "|---|---|",
    ]
    for stage_id in ("host_probe", "source_download", "dependency_review", "pip_install", "smoke_commands", "hf_weights_probe"):
        md.append(f"| {stage_id} | {rec.stage_states.get(stage_id, 'missing')} |")
    md += [
        "",
        "## Host",
        "",
        f"- python: `{versions['python_version']}`",
        f"- torch: `{host.get('torch', {}).get('torch', 'missing')}` cuda_ok=`{host.get('torch', {}).get('cuda_available', False)}` device=`{host.get('torch', {}).get('device_name', 'n/a')}`",
        f"- jax: `{host.get('jax', {}).get('jax', 'missing')}`",
        f"- nvidia-smi: `{versions['nvidia_smi_stdout']}`",
        "",
        "## Source",
        "",
        f"- archive_bytes: {source.get('archive_bytes')}",
        f"- archive_sha256: `{source.get('archive_sha256')}`",
        f"- extracted_files: {source.get('extracted_files')}",
        f"- error: {source.get('error', 'none')}",
        "",
        "## Smoke Commands",
        "",
    ]
    for a in smoke.get("attempts", []):
        md.append(f"- `{' '.join(a['command'])}` → exit {a['exit_code']} ({a['duration_seconds']}s)")
    md += [
        "",
        "## Forbidden Claims",
        "",
        "- weights_downloaded",
        "- inference_succeeded",
        "- binder_designed",
        "- genie3_runtime_validated (toolcheck is necessary but not sufficient)",
        "",
    ]
    (rec.root / "genie3_toolcheck_report.md").write_text("\n".join(md) + "\n")

    index = {"files": []}
    for p in sorted(rec.root.rglob("*")):
        if p.is_file() and p.name != "runpod-execution.tar.gz":
            try:
                h = hashlib.sha256(p.read_bytes()).hexdigest()
            except Exception:
                h = None
            index["files"].append({"path": str(p.relative_to(rec.root)), "size": p.stat().st_size, "sha256": h})
    (rec.root / "artifact_index.json").write_text(json.dumps(index, indent=2, sort_keys=True) + "\n")

    rec.stage("emit_artifacts", "completed", overall_ok=overall_ok)
    return {"overall_ok": overall_ok, "claim_level": validation_ledger["claim_level"]}


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(description="Genie 3 no-download toolcheck")
    ap.add_argument("--out", default="/workspace/runpod-execution/artifacts")
    ap.add_argument("--run-id", default="genie3-no-download-toolcheck-v1")
    ap.add_argument("--no-install", action="store_true")
    ap.add_argument("--json", action="store_true")
    args = ap.parse_args(argv)

    artifact_root = Path(args.out)
    rec = Recorder(artifact_root)
    rec.stage("toolcheck_init", "completed", run_id=args.run_id)

    host = stage_host_probe(rec)
    source = stage_source_download(rec)
    deps = stage_dependency_review(rec, source)
    install = stage_pip_install(rec, source, do_install=not args.no_install)
    smoke = stage_smoke_commands(rec)
    hf = stage_hf_weights_probe(rec)
    final = stage_emit_artifacts(rec, args.run_id, host, source, deps, install, smoke, hf)

    status = {
        "ok": final["overall_ok"],
        "status": "completed" if final["overall_ok"] else "completed_partial",
        "run_id": args.run_id,
        "claim_level": final["claim_level"],
        "completed_at": utc_iso(),
        "stages": rec.stage_states,
    }
    (artifact_root.parent / "status.json").write_text(json.dumps(status, indent=2, sort_keys=True) + "\n")

    summary = {
        "run_id": args.run_id,
        "ok": final["overall_ok"],
        "claim_level": final["claim_level"],
        "stages": rec.stage_states,
    }
    if args.json:
        print(json.dumps(summary, indent=2, sort_keys=True))
    return 0


if __name__ == "__main__":
    sys.exit(main())
