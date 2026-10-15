"""Repository guard: no new references to workspace/outputs or workspace/records paths."""

from __future__ import annotations

import re
import subprocess
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[3]

SCAN_SUFFIXES = {".py", ".ts", ".tsx", ".mjs", ".js", ".yaml", ".yml", ".md"}

DOC_ALLOWLIST = {
    "docs/REFACTOR_PLAN.md",
    "docs/ISSUES.md",
}

# Explicit legacy path mentions required for cleanup tests / config (see comment per entry).
LINE_ALLOWLIST: dict[str, list[str]] = {
    "src/backend/services/workspace_clean.py": [
        '"legacy_dirs": ["outputs", "records"]',
    ],
    "src/tests/t_scripts/test_workspace_clean_legacy.py": [
        "outputs/",
        "records/",
    ],
    # negative tests: files under legacy outputs/ must NOT be read
    "src/tests/t_harness/tools/lca_artifacts/test_artifact_paths.py": [
        "outputs/",
        'legacy = ctx02.workspace / "outputs"',
        'legacy = ctx.workspace / "outputs"',
    ],
    # docstring of the negative test asserting records/ is not created
    "src/tests/t_harness/tools/control_openlca/test_health_service_reconcile.py": [
        "must not create workspace/records/",
    ],
    "src/tests/t_harness/tools/control_openlca/test_cleanup_descriptor_only.py": [
        '"outputs"',
    ],
    "src/tests/t_harness/tools/lca_artifacts/test_lci_import_dir.py": [
        'resolve_workflow_lci_dir("workspace/outputs/LCI"',
    ],
    "src/tests/t_harness/tools/control_openlca/test_import_identity.py": [
        "outputs/",
    ],
    "src/tests/t_repo/test_no_legacy_workspace_paths.py": [
        "workspace/outputs",
        "workspace/records",
        "outputs/",
        "records/",
    ],
}

PATTERNS = [
    re.compile(r"workspace/outputs"),
    re.compile(r"workspace/records"),
    re.compile(r'["\']outputs/'),
    re.compile(r'["\']records/'),
    re.compile(r"/\s*[\"']outputs[\"']\s*/"),
    re.compile(r"/\s*[\"']records[\"']\s*/"),
    re.compile(r"workspace\s*/\s*[\"']outputs[\"']"),
    re.compile(r"workspace\s*/\s*[\"']records[\"']"),
    re.compile(r"outputs/inventory"),
    re.compile(r"outputs/LCI"),
    re.compile(r"outputs/reports"),
    re.compile(r"records/handoffs"),
]


def _git_tracked_files() -> list[str]:
    out = subprocess.check_output(
        ["git", "ls-files"],
        cwd=ROOT,
        text=True,
    )
    return [line.strip() for line in out.splitlines() if line.strip()]


def _should_scan(rel: str) -> bool:
    if rel.startswith("docs/") and rel not in DOC_ALLOWLIST:
        if rel.startswith("docs/"):
            return False
    if "node_modules/" in rel:
        return False
    path = Path(rel)
    if path.suffix not in SCAN_SUFFIXES:
        return False
    if rel.startswith("harness/") and path.suffix == ".md":
        return True
    if rel in {"AGENTS.md"}:
        return True
    if rel.startswith("src/"):
        return True
    if rel.startswith("harness/"):
        return True
    if rel.startswith(".cursor/"):
        return True
    return False


def _line_allowed(rel: str, line: str) -> bool:
    for fragment in LINE_ALLOWLIST.get(rel, []):
        if fragment in line:
            return True
    return False


def test_no_legacy_workspace_path_literals() -> None:
    violations: list[str] = []
    for rel in _git_tracked_files():
        if not _should_scan(rel):
            continue
        if rel.endswith("test_no_legacy_workspace_paths.py"):
            continue
        path = ROOT / rel
        if not path.is_file():
            continue
        text = path.read_text(encoding="utf-8", errors="replace")
        for lineno, line in enumerate(text.splitlines(), start=1):
            if _line_allowed(rel, line):
                continue
            for pattern in PATTERNS:
                if pattern.search(line):
                    violations.append(f"{rel}:{lineno}: {line.strip()}")
                    break
    assert not violations, "legacy workspace paths found:\n" + "\n".join(violations)
