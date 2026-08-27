#!/usr/bin/env python
# -*- coding: utf-8 -*-

import argparse
import sys
from pathlib import Path


SCRIPT_DIR = Path(__file__).resolve().parent

try:
    from .config import (
        ALL_TARGET_NAMES,
        CLEAN_PRESETS,
        CLEAN_TARGETS,
        PROJECT_ROOT,
    )
    from .utils.clean import clean_ignored_dir, clean_root_files, parse_gitignore
    from .utils.openlca_clean import run_openlca_clean
except ImportError:
    if str(SCRIPT_DIR) not in sys.path:
        sys.path.insert(0, str(SCRIPT_DIR))
    from config import (
        ALL_TARGET_NAMES,
        CLEAN_PRESETS,
        CLEAN_TARGETS,
        PROJECT_ROOT,
    )
    from utils.clean import clean_ignored_dir, clean_root_files, parse_gitignore
    from utils.openlca_clean import run_openlca_clean


def _print_ok(target_name: str) -> None:
    print(f"[OK] clean target '{target_name}' completed")


def _print_fail(target_name: str, reason: str) -> None:
    print(f"[FAIL] clean target '{target_name}': {reason}", file=sys.stderr)


def _clean_filesystem_target(
    target_cfg: dict,
    *,
    dry_run: bool = False,
) -> tuple[int, int, int, int]:
    name = target_cfg["name"]
    root_dir = target_cfg["path"]
    gitignore_path = target_cfg.get("gitignore") or root_dir / ".gitignore"

    ignored_dirs, keep_patterns = parse_gitignore(gitignore_path)
    ignored_dirs = list(target_cfg.get("ignored_dirs", ignored_dirs))
    keep_patterns = list(target_cfg.get("keep_patterns", keep_patterns))

    total_files = total_dirs = total_kept = total_failed = 0

    if target_cfg.get("clean_root_files"):
        print(f"\n开始清理 [{name}] 根级文件...")
        if keep_patterns:
            print(f"  例外保留: {', '.join(keep_patterns)}")
        files, dirs, kept, failed = clean_root_files(
            root_dir,
            PROJECT_ROOT,
            keep_patterns,
            dry_run=dry_run,
        )
        return files + total_files, dirs + total_dirs, kept + total_kept, failed + total_failed

    exclude_top_level = {
        item.strip("/") for item in target_cfg.get("exclude_top_level", [])
    }
    if exclude_top_level:
        ignored_dirs = [
            f"{child.name}/**"
            for child in sorted(root_dir.iterdir())
            if child.is_dir() and child.name not in exclude_top_level
        ]

    if not ignored_dirs:
        return 0, 0, 0, 0

    print(f"\n开始清理 [{name}] 目录...")
    print(f"  忽略子目录: {', '.join(ignored_dirs)}")
    if exclude_top_level:
        print(f"  顶层保留: {', '.join(sorted(exclude_top_level))}")
    if keep_patterns:
        print(f"  例外保留: {', '.join(keep_patterns)}")

    skipped_ignored = set(target_cfg.get("skip_ignored", []))
    for ignored in ignored_dirs:
        if ignored in skipped_ignored:
            print(f"  保留活动目录: {ignored}")
            continue
        target_path = root_dir / ignored.replace("/**", "").strip("/")
        if not target_path.exists() or not target_path.is_dir():
            continue
        files, dirs, kept, failed = clean_ignored_dir(
            target_path,
            root_dir,
            PROJECT_ROOT,
            keep_patterns,
            dry_run=dry_run,
        )
        total_files += files
        total_dirs += dirs
        total_kept += kept
        total_failed += failed

    return total_files, total_dirs, total_kept, total_failed


def _run_single_target(
    target_name: str,
    *,
    dry_run: bool = False,
) -> int:
    if target_name == "openlca":
        print("\n开始清理 [openlca] 前景实体...")
        try:
            ok, message, _details = run_openlca_clean(dry_run=dry_run)
        except (ValueError, OSError) as exc:
            _print_fail("openlca", str(exc))
            return 1
        if ok:
            print(f"  {message}")
            _print_ok("openlca")
            return 0
        _print_fail("openlca", message)
        return 1

    target_cfg = next(
        (cfg for cfg in CLEAN_TARGETS if cfg["name"] == target_name),
        None,
    )
    if target_cfg is None:
        _print_fail(target_name, "unknown filesystem target")
        return 1

    total_files, total_dirs, total_kept, total_failed = _clean_filesystem_target(
        target_cfg,
        dry_run=dry_run,
    )

    print(f"\n  [{target_name}] 删除文件: {total_files}, 空目录: {total_dirs}, 保留: {total_kept}")
    if total_failed > 0:
        _print_fail(target_name, f"{total_failed} deletion(s) failed")
        return 1
    _print_ok(target_name)
    return 0


def _resolve_targets(target: str | None, preset: str | None) -> list[str] | None:
    if preset:
        return list(CLEAN_PRESETS[preset])
    if target:
        return [target]
    return ["workspace"]


def run_clean(
    dry_run: bool = False,
    yes: bool = False,
    target: str | None = None,
    preset: str | None = None,
) -> int:
    """Clean configured targets according to .gitignore rules or openLCA cleanup."""
    if target and preset:
        print("错误: --target 与 --preset 不能同时使用", file=sys.stderr)
        return 1

    if preset and preset not in CLEAN_PRESETS:
        print(f"错误: 未知 preset [{preset}]", file=sys.stderr)
        print("可用 preset: " + ", ".join(sorted(CLEAN_PRESETS)), file=sys.stderr)
        return 1

    try:
        targets = _resolve_targets(target, preset)
    except KeyError:
        print(f"错误: 未知 preset [{preset}]", file=sys.stderr)
        return 1

    if targets is None:
        targets = ["workspace"]

    for name in targets:
        if name not in ALL_TARGET_NAMES:
            print(f"错误: 未知清理目标 [{name}]", file=sys.stderr)
            print("可用目标: " + ", ".join(ALL_TARGET_NAMES), file=sys.stderr)
            return 1

    print("=" * 60)
    print(f"项目根目录: {PROJECT_ROOT}")
    if dry_run:
        print("模式: [演练模式] (只显示，不实际删除文件)")
    if preset:
        print(f"preset: [{preset}] -> {', '.join(targets)}")
    elif target:
        print(f"目标: [{target}]")
    else:
        print("目标: [workspace] (默认)")
    print("=" * 60)

    if not yes and not dry_run:
        confirm = input(
            "警告：这将删除所选目标中的生成及临时文件！\n确定要继续吗？(y/N): "
        )
        if confirm.strip().lower() not in ("y", "yes"):
            print("操作已取消。")
            return 0

    for target_name in targets:
        code = _run_single_target(target_name, dry_run=dry_run)
        if code != 0:
            print("\n" + "=" * 60)
            print(f"[FAIL] clean aborted after target '{target_name}'")
            print("=" * 60)
            return 1

    print("\n" + "=" * 60)
    if dry_run:
        print("[OK] dry-run completed for all requested targets")
    else:
        print("[OK] all requested clean targets completed")
    print("=" * 60)
    return 0


def main() -> None:
    parser = argparse.ArgumentParser(description="按目标清理 knowledge、workspace 或 openLCA 前景实体。")
    parser.add_argument("--dry-run", action="store_true", help="演练模式，仅打印将要删除的文件/目录")
    parser.add_argument("-y", "--yes", action="store_true", help="跳过二次确认，直接执行删除操作")
    parser.add_argument(
        "-t",
        "--target",
        type=str,
        default=None,
        help="单个清理目标: knowledge, workspace, openlca",
    )
    parser.add_argument(
        "--preset",
        type=str,
        default=None,
        choices=sorted(CLEAN_PRESETS),
        help="预设清理序列: whole-lca 或 revise-lca",
    )
    args = parser.parse_args()
    raise SystemExit(
        run_clean(
            dry_run=args.dry_run,
            yes=args.yes,
            target=args.target,
            preset=args.preset,
        )
    )


if __name__ == "__main__":
    main()
