#!/usr/bin/env python3
"""Catch stale public documentation references."""

from __future__ import annotations

import argparse
import json
import os
import re
from pathlib import Path


DOC_SUFFIXES = {".md", ".qmd", ".yaml", ".yml", ".toml", ".json"}
PRIVATE_REPO_URL_PATTERN = re.compile(
    r"https://(?:github\.com|raw\.githubusercontent\.com)/BioSymphony/biosymphony-structure-factory(?!-public)"
)
SKIP_DIRS = {".git", ".runtime", ".venv", "venv", "__pycache__", ".pytest_cache", "build", "dist"}
REPO_PREFIXES = (
    ".github/",
    "campaigns/",
    "demos/",
    "docs/",
    "examples/",
    "modules/",
    "packs/",
    "recipes/",
    "references/",
    "runpod/",
    "schemas/",
    "scripts/",
    "skills/",
    "src/",
    "templates/",
    "tests/",
    "tools/",
)
ROOT_FILES = {
    "AGENTS.md",
    "BIOSAFETY.md",
    "CHANGELOG.md",
    "CITATION.cff",
    "CODE_OF_CONDUCT.md",
    "CONTRIBUTING.md",
    "LICENSE",
    "Makefile",
    "NON_CLAIMS.md",
    "PUBLIC_RELEASE.md",
    "README.md",
    "SECURITY.md",
    "SUPPORT.md",
    "sidecar.yaml",
}
RELATIVE_LINK_CHECK_DOCS = {
    "README.md",
    "docs/agent-recipes.md",
    "docs/quickstart-tour.md",
    "docs/standalone-agent-workflow.md",
    "docs/use-cases.md",
    "recipes/README.md",
}
RELATIVE_LINK_CHECK_PREFIXES: tuple[str, ...] = ()


def is_bundled_skill_reference(root: Path, path: Path) -> bool:
    try:
        parts = path.relative_to(root).parts
    except ValueError:
        return False
    return len(parts) >= 4 and parts[0] == "skills" and parts[2] == "references"


def skill_local_ref(root: Path, source_rel: str, ref: str) -> Path | None:
    parts = Path(source_rel).parts
    if len(parts) >= 3 and parts[0] == "skills" and ref.startswith(("assets/", "references/", "scripts/", "tools/")):
        return root / "skills" / parts[1] / ref
    return None


def make_targets(root: Path) -> set[str]:
    targets: set[str] = set()
    makefile = root / "Makefile"
    for line in makefile.read_text(encoding="utf-8").splitlines():
        match = re.match(r"^([A-Za-z0-9_.-]+):(?:\s|$)", line)
        if match and not line.startswith("\t"):
            targets.add(match.group(1))
    return targets


def iter_docs(root: Path) -> list[Path]:
    paths: list[Path] = []
    for current, dirs, names in os.walk(root):
        dirs[:] = [name for name in dirs if name not in SKIP_DIRS]
        current_path = Path(current)
        for name in names:
            path = current_path / name
            rel = path.relative_to(root).as_posix()
            if is_bundled_skill_reference(root, path):
                continue
            if "/linear-issues/" in rel:
                continue
            if rel.startswith("runpod/bridge-manifests/"):
                continue
            if rel.startswith("campaigns/") and rel != "campaigns/README.md":
                continue
            if path.suffix.lower() in DOC_SUFFIXES or path.name in ROOT_FILES:
                paths.append(path)
    return sorted(paths)


def iter_all_public_docs(root: Path) -> list[Path]:
    paths: list[Path] = []
    for current, dirs, names in os.walk(root):
        dirs[:] = [name for name in dirs if name not in SKIP_DIRS]
        current_path = Path(current)
        for name in names:
            path = current_path / name
            if is_bundled_skill_reference(root, path):
                continue
            if path.suffix.lower() in {".md", ".qmd"} or path.name in ROOT_FILES:
                paths.append(path)
    return sorted(paths)


def normalize_ref(candidate: str, source_rel: str, *, allow_relative: bool) -> str | None:
    if " " in candidate and not candidate.startswith("<"):
        return None
    candidate = candidate.strip("<>").split("#", 1)[0]
    if not candidate:
        return None
    if candidate.startswith(("http://", "https://", "#", "mailto:")):
        return None
    if candidate.startswith((".runtime/", "artifacts/", "outputs/", "runpod-execution/")):
        return None
    if "<" in candidate or ">" in candidate or "$" in candidate or "*" in candidate or "{" in candidate or "}" in candidate:
        return None
    if candidate.startswith(REPO_PREFIXES) or candidate in ROOT_FILES:
        return candidate
    if allow_relative and (candidate.startswith(("./", "../")) or Path(candidate).suffix):
        source_parent = Path(source_rel).parent
        resolved = (source_parent / candidate).as_posix()
        parts: list[str] = []
        for part in resolved.split("/"):
            if part in {"", "."}:
                continue
            if part == "..":
                if not parts:
                    return None
                parts.pop()
                continue
            parts.append(part)
        normalized = "/".join(parts)
        if normalized.startswith(REPO_PREFIXES) or normalized in ROOT_FILES:
            return normalized
    return None


def referenced_paths(text: str, source_rel: str) -> set[str]:
    refs: set[str] = set()
    allow_relative = source_rel in RELATIVE_LINK_CHECK_DOCS or source_rel.startswith(RELATIVE_LINK_CHECK_PREFIXES)
    for match in re.finditer(r"\[([^\]]+)\]\(([^)]+)\)", text):
        candidate = match.group(2)
        # Markdown links are intentional references. Check relative links broadly
        # while keeping inline code-path extraction conservative below.
        ref = normalize_ref(candidate, source_rel, allow_relative=True)
        if ref is not None:
            refs.add(ref)
    for match in re.finditer(r"<img\s+[^>]*src=[\"']([^\"']+)[\"']", text, flags=re.I):
        candidate = match.group(1)
        ref = normalize_ref(candidate, source_rel, allow_relative=allow_relative)
        if ref is not None:
            refs.add(ref)
    for match in re.finditer(r"`([^`]+\.(?:md|json|yaml|yml|py|sh|toml|html|cff|in|svg))`", text):
        candidate = match.group(1)
        ref = normalize_ref(candidate, source_rel, allow_relative=False)
        if ref is not None:
            refs.add(ref)
    return refs


def check(root: Path) -> dict[str, object]:
    targets = make_targets(root)
    findings: list[dict[str, str]] = []
    stale_text = [
        ".codex/",
        ".codex/skills/structure-factory/SKILL.md",
        ".codex/skills/structure-factory",
        "--yes-create-paid-runpod",
        "fully self-contained",
        "base64 in `dockerStartCmd`",
        "Keychain-backed",
        "RUNPOD_API_KEY` in the shell",
        "curl -L $BOOTSTRAP_URL | bash -",
        "runpod" + "-bridge " + "create-pod",
        "cloud" + "-bridge " + "create-pod",
        "symphony-neocloud-bridge " + "create-pod",
        "https://github.com/BioSymphony/biosymphony-" + "structure-factory.git",
    ]

    checked_make_refs: set[tuple[str, str]] = set()

    for path in iter_docs(root):
        rel = path.relative_to(root).as_posix()
        text = path.read_text(encoding="utf-8")
        for private_repo_url in PRIVATE_REPO_URL_PATTERN.finditer(text):
            findings.append(
                {
                    "path": rel,
                    "check_id": "private-package-url" if rel == "pyproject.toml" else "private-repo-url",
                    "message": private_repo_url.group(0),
                }
            )
        for marker in stale_text:
            if marker in text:
                findings.append({"path": rel, "check_id": "stale-or-unsafe-public-text", "message": marker})
        make_refs: set[str] = set()
        for match in re.finditer(r"`make\s+([A-Za-z0-9_.-]+)`", text):
            make_refs.add(match.group(1).rstrip(".,;:"))
        for line in text.splitlines():
            match = re.match(r"^\s*make\s+([A-Za-z0-9_.-]+)\s*$", line)
            if match:
                make_refs.add(match.group(1).rstrip(".,;:"))
        for target in sorted(make_refs):
            checked_make_refs.add((rel, target))
            if target not in targets:
                findings.append({"path": rel, "check_id": "missing-make-target", "message": target})
        for ref in referenced_paths(text, rel):
            skill_candidate = skill_local_ref(root, rel, ref)
            if skill_candidate is not None and skill_candidate.exists():
                continue
            if not (root / ref).exists():
                findings.append({"path": rel, "check_id": "missing-referenced-path", "message": ref})

    # Campaign and issue drafts are large and often contain runtime paths, so
    # their inline file references stay out of the stricter link checker above.
    # Copy-paste Make targets are still user-facing and must resolve.
    for path in iter_all_public_docs(root):
        rel = path.relative_to(root).as_posix()
        text = path.read_text(encoding="utf-8")
        make_refs: set[str] = set()
        for match in re.finditer(r"`make\s+([A-Za-z0-9_.-]+)`", text):
            make_refs.add(match.group(1).rstrip(".,;:"))
        for line in text.splitlines():
            match = re.match(r"^\s*make\s+([A-Za-z0-9_.-]+)\s*$", line)
            if match:
                make_refs.add(match.group(1).rstrip(".,;:"))
        for target in sorted(make_refs):
            key = (rel, target)
            if key in checked_make_refs:
                continue
            if target not in targets:
                findings.append({"path": rel, "check_id": "missing-make-target", "message": target})

    skills_root = root / "skills"
    if skills_root.is_dir():
        for skill_root in sorted(path for path in skills_root.iterdir() if path.is_dir()):
            skill_refs = skill_root / "references"
            if not skill_refs.is_dir():
                continue
            for bundled in sorted(path for path in skill_refs.rglob("*") if path.is_file()):
                relative = bundled.relative_to(skill_refs)
                canonical = root / relative
                if canonical.is_file() and bundled.read_bytes() != canonical.read_bytes():
                    findings.append(
                        {
                            "path": bundled.relative_to(root).as_posix(),
                            "check_id": "stale-skill-reference-copy",
                            "message": relative.as_posix(),
                        }
                    )
            if skill_root.name != "binder-lane-round":
                continue
            for markdown in sorted(skill_root.rglob("*.md")):
                text = markdown.read_text(encoding="utf-8")
                for match in re.finditer(r"\[[^\]]+\]\(([^)]+)\)", text):
                    candidate = match.group(1).strip().strip("<>").split("#", 1)[0]
                    if not candidate or candidate.startswith(("http://", "https://", "mailto:", "#")):
                        continue
                    if markdown.parent == skill_root and candidate.startswith(("assets/", "references/", "scripts/", "tools/")):
                        resolved = (skill_root / candidate).resolve()
                    else:
                        resolved = (markdown.parent / candidate).resolve()
                    try:
                        resolved.relative_to(skill_root.resolve())
                    except ValueError:
                        findings.append(
                            {
                                "path": markdown.relative_to(root).as_posix(),
                                "check_id": "escaping-bundled-skill-link",
                                "message": candidate,
                            }
                        )
                        continue
                    if not resolved.exists():
                        findings.append(
                            {
                                "path": markdown.relative_to(root).as_posix(),
                                "check_id": "missing-bundled-skill-link",
                                "message": candidate,
                            }
                        )

    return {"ok": not findings, "finding_count": len(findings), "findings": findings}


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--repo-root", default=".")
    parser.add_argument("--json", action="store_true")
    args = parser.parse_args()
    result = check(Path(args.repo_root).resolve())
    print(json.dumps(result, indent=2, sort_keys=True))
    return 0 if result["ok"] else 1


if __name__ == "__main__":
    raise SystemExit(main())
