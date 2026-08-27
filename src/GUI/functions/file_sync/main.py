from __future__ import annotations

import shutil
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Literal

from functions.file_sync.private_utils.upload_paths import collect_upload_paths
from functions.plan_editor import (
    parse_execution_plan_text,
    save_execution_plan,
    save_structured_plan,
    is_plan_ready,
)

SyncTarget = Literal["knowledge", "plan", "revise"]

CONTROL_FILENAMES = {".gitignore", "readme.md"}


@dataclass
class SyncResult:
    ok: bool
    target: str
    message: str
    details: list[str] = field(default_factory=list)


def sync_files(target: SyncTarget, **kwargs: Any) -> SyncResult:
    """Sync GUI-staged inputs to harness/knowledge or workspace/inputs."""
    if target == "knowledge":
        return _sync_knowledge(kwargs.get("uploads"))
    if target == "plan":
        return _sync_plan(
            values=kwargs.get("values"),
            source_text=kwargs.get("source_text"),
            target_path=kwargs.get("target_path"),
        )
    if target == "revise":
        return _sync_revise(
            values=kwargs.get("values"),
            source_text=kwargs.get("source_text"),
            target_path=kwargs.get("target_path"),
        )
    return SyncResult(
        ok=False,
        target=str(target),
        message=f"unsupported sync target: {target}",
    )


def _sync_knowledge(uploads: Any) -> SyncResult:
    import config

    knowledge_dir = config.KNOWLEDGE_DIR
    knowledge_dir.mkdir(parents=True, exist_ok=True)
    details: list[str] = []
    copied = 0

    for path in collect_upload_paths(uploads):
        if not (path.exists() and path.is_file()):
            details.append(f"skipped missing upload: {path}")
            continue
        if path.name.casefold() in CONTROL_FILENAMES:
            details.append(f"skipped control file name: {path.name}")
            continue
        dest_path = knowledge_dir / path.name
        try:
            shutil.copy2(path, dest_path)
            copied += 1
            details.append(f"copied {path.name} -> harness/knowledge/")
        except OSError as exc:
            return SyncResult(
                ok=False,
                target="knowledge",
                message=f"failed to copy {path.name}: {exc}",
                details=details,
            )

    if copied == 0:
        return SyncResult(
            ok=True,
            target="knowledge",
            message="no uploaded files to sync",
            details=details,
        )
    return SyncResult(
        ok=True,
        target="knowledge",
        message=f"synced {copied} file(s) to harness/knowledge/",
        details=details,
    )


def _sync_document(
    *,
    target_name: str,
    values: Any,
    source_text: str | None,
    target_path: Path | None,
    empty_error: str,
    fields_error: str,
) -> SyncResult:
    if target_path is None:
        return SyncResult(
            ok=False,
            target=target_name,
            message="target path is required",
        )
    if not source_text or not source_text.strip():
        return SyncResult(
            ok=False,
            target=target_name,
            message=empty_error,
        )
    try:
        template = parse_execution_plan_text(source_text)
        active_values = list(values or [])[: len(template.fields)]
        if template.fields:
            if not is_plan_ready(active_values):
                return SyncResult(
                    ok=False,
                    target=target_name,
                    message=fields_error,
                )
            saved = save_structured_plan(
                template=template,
                values=active_values,
                target_path=target_path,
            )
        else:
            saved = save_execution_plan(
                text=source_text,
                target_path=target_path,
            )
    except (OSError, UnicodeError, ValueError) as exc:
        return SyncResult(
            ok=False,
            target=target_name,
            message=str(exc),
        )
    return SyncResult(
        ok=True,
        target=target_name,
        message=f"synced to {saved.as_posix()}",
        details=[saved.as_posix()],
    )


def _sync_plan(
    values: Any,
    source_text: str | None,
    target_path: Path | None,
) -> SyncResult:
    return _sync_document(
        target_name="plan",
        values=values,
        source_text=source_text,
        target_path=target_path,
        empty_error="no plan content to sync",
        fields_error="plan requires at least one filled field",
    )


def _sync_revise(
    values: Any,
    source_text: str | None,
    target_path: Path | None,
) -> SyncResult:
    return _sync_document(
        target_name="revise",
        values=values,
        source_text=source_text,
        target_path=target_path,
        empty_error="no revision content to sync",
        fields_error="revision requires at least one filled field",
    )
