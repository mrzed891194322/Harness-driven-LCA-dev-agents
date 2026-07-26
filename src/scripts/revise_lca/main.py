#!/usr/bin/env python
"""Snapshot and activate the previous LCA run for a revise-lca execution."""

from __future__ import annotations

import argparse
import hashlib
import json
import shutil
import tempfile
from pathlib import Path
from typing import Any


PROJECT_ROOT = next(
    parent
    for parent in Path(__file__).resolve().parents
    if (parent / "pyproject.toml").is_file()
)
STAGING_NAME = "revise-lca-baseline"
SNAPSHOT_VERSION = "1.0"


def _workspace_root(project_root: Path) -> Path:
    root = project_root.resolve()
    if root == Path(root.anchor) or not (root / "pyproject.toml").is_file():
        raise ValueError(f"project root 不安全或缺少 pyproject.toml：{root}")
    workspace = root / "workspace"
    if workspace.is_symlink():
        raise ValueError(f"workspace 不允许是符号链接：{workspace}")
    resolved = workspace.resolve()
    if resolved.parent != root:
        raise ValueError(f"workspace 路径逃逸 project root：{workspace}")
    return workspace


def _sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as stream:
        for block in iter(lambda: stream.read(1024 * 1024), b""):
            digest.update(block)
    return digest.hexdigest()


def _require_regular_file(path: Path, label: str) -> None:
    if not path.is_file() or path.is_symlink():
        raise ValueError(f"{label}不存在或不是普通文件：{path}")
    if not path.read_text(encoding="utf-8-sig").strip():
        raise ValueError(f"{label}不能为空：{path}")


def _iter_source_files(workspace: Path) -> list[tuple[Path, Path]]:
    inputs = workspace / "inputs"
    memory = workspace / "memory"
    outputs = workspace / "outputs"
    required = (
        (inputs / "plan.md", "原 LCA 计划"),
        (inputs / "revise.md", "LCA 改进意见"),
        (memory / "manifest.json", "原工作流 manifest"),
        (outputs / "reports" / "lca_report.md", "原 LCA 报告"),
    )
    for path, label in required:
        _require_regular_file(path, label)
    manifest_path = memory / "manifest.json"
    try:
        manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
    except json.JSONDecodeError as exc:
        raise ValueError(f"原工作流 manifest 不是有效 JSON：{manifest_path}") from exc
    supported_manifests = {
        "whole-lca/workflow-manifest": "2.0",
        "revise-lca/workflow-manifest": "1.0",
    }
    if (
        not isinstance(manifest, dict)
        or supported_manifests.get(str(manifest.get("schema"))) != str(
            manifest.get("version")
        )
        or manifest.get("status") != "completed"
    ):
        raise ValueError("原工作流 manifest 必须是受支持且已 completed 的运行。")
    lci_dir = outputs / "LCI"
    if not lci_dir.is_dir() or lci_dir.is_symlink():
        raise ValueError(f"原 LCI 目录不存在：{lci_dir}")
    if not any(path.is_file() and not path.is_symlink() for path in lci_dir.rglob("*")):
        raise ValueError(f"原 LCI 目录不包含任何产物：{lci_dir}")

    sources: list[tuple[Path, Path]] = [
        (inputs / "plan.md", Path("plan.md")),
        (inputs / "revise.md", Path("revise.md")),
    ]
    for root, destination in (
        (memory, Path("memory")),
        (outputs, Path("outputs")),
    ):
        if not root.is_dir() or root.is_symlink():
            raise ValueError(f"基线目录不存在或不安全：{root}")
        for path in sorted(root.rglob("*")):
            if path.is_symlink():
                raise ValueError(f"基线中不允许符号链接：{path}")
            if not path.is_file():
                continue
            relative = path.relative_to(root)
            if root == memory and relative.parts[:1] == ("baseline",):
                continue
            sources.append((path, destination / relative))
    return sources


def _inventory(payload: Path) -> list[dict[str, Any]]:
    return [
        {
            "path": path.relative_to(payload).as_posix(),
            "sha256": _sha256(path),
            "size": path.stat().st_size,
        }
        for path in sorted(payload.rglob("*"))
        if path.is_file()
    ]


def snapshot_baseline(project_root: Path = PROJECT_ROOT, *, replace: bool = False) -> Path:
    workspace = _workspace_root(project_root)
    staging = workspace / "tmp" / STAGING_NAME
    if staging.exists() and not replace:
        raise ValueError(
            f"已有未激活的 revise-lca 基线：{staging}；确认后使用 --yes 重建。"
        )

    sources = _iter_source_files(workspace)
    staging.parent.mkdir(parents=True, exist_ok=True)
    temporary = Path(
        tempfile.mkdtemp(prefix=f".{STAGING_NAME}-", dir=staging.parent)
    )
    try:
        payload = temporary / "payload"
        for source, relative in sources:
            target = payload / relative
            target.parent.mkdir(parents=True, exist_ok=True)
            shutil.copy2(source, target)
        manifest = {
            "schema": "revise-lca/baseline-snapshot",
            "version": SNAPSHOT_VERSION,
            "files": _inventory(payload),
        }
        (temporary / "snapshot.json").write_text(
            json.dumps(manifest, ensure_ascii=False, indent=2) + "\n",
            encoding="utf-8",
        )
        if staging.exists():
            shutil.rmtree(staging)
        temporary.replace(staging)
    except Exception:
        shutil.rmtree(temporary, ignore_errors=True)
        raise
    return staging


def _load_snapshot(staging: Path) -> tuple[Path, dict[str, Any]]:
    snapshot_path = staging / "snapshot.json"
    payload = staging / "payload"
    try:
        manifest = json.loads(snapshot_path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as exc:
        raise ValueError(f"无法读取基线快照清单：{snapshot_path}") from exc
    if (
        not isinstance(manifest, dict)
        or manifest.get("schema") != "revise-lca/baseline-snapshot"
        or manifest.get("version") != SNAPSHOT_VERSION
        or not isinstance(manifest.get("files"), list)
    ):
        raise ValueError("基线快照清单 schema/version 不受支持。")
    expected = {
        item.get("path"): (item.get("sha256"), item.get("size"))
        for item in manifest["files"]
        if isinstance(item, dict)
    }
    actual = {
        item["path"]: (item["sha256"], item["size"])
        for item in _inventory(payload)
    }
    if expected != actual:
        raise ValueError("基线快照文件或哈希已变化，拒绝激活。")
    return payload, manifest


def _clear_children(root: Path) -> None:
    root.mkdir(parents=True, exist_ok=True)
    for child in root.iterdir():
        if child.name == "README.md":
            continue
        if child.is_symlink() or child.is_file():
            child.unlink()
        else:
            shutil.rmtree(child)


def activate_baseline(project_root: Path = PROJECT_ROOT, *, yes: bool = False) -> Path:
    if not yes:
        raise ValueError("激活会清理当前 memory/outputs；必须显式传入 --yes。")
    workspace = _workspace_root(project_root)
    staging = workspace / "tmp" / STAGING_NAME
    payload, _ = _load_snapshot(staging)
    memory = workspace / "memory"
    outputs = workspace / "outputs"
    _clear_children(memory)
    _clear_children(outputs)
    baseline = memory / "baseline"
    shutil.copytree(payload, baseline)
    shutil.copy2(staging / "snapshot.json", baseline / "snapshot.json")
    shutil.rmtree(staging)
    return baseline


def main() -> int:
    parser = argparse.ArgumentParser(
        description="为 revise-lca 校验、快照并激活上一轮 LCA 证据。"
    )
    parser.add_argument("action", choices=("snapshot", "activate"))
    parser.add_argument(
        "--project-root",
        type=Path,
        default=PROJECT_ROOT,
        help="仅供隔离测试使用的项目根目录。",
    )
    parser.add_argument(
        "-y",
        "--yes",
        action="store_true",
        help="允许替换暂存快照或激活后清理 canonical 产物。",
    )
    args = parser.parse_args()
    try:
        path = (
            snapshot_baseline(args.project_root.resolve(), replace=args.yes)
            if args.action == "snapshot"
            else activate_baseline(args.project_root.resolve(), yes=args.yes)
        )
    except (OSError, UnicodeError, ValueError) as exc:
        print(f"[ERROR] {exc}")
        return 1
    print(path)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
