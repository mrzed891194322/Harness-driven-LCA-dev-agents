"""v5: check path arguments of openLCA tools against the calling agent's read/write scope.

The host passes the agent's globs as JSON in V5_READ_GLOBS / V5_WRITE_GLOBS / V5_DENIED_WRITE_GLOBS.
Without them (standalone use) nothing is enforced. Paths are resolved (symlinks followed) first.
"""
from __future__ import annotations

import fnmatch
import json
import os
from pathlib import Path
from typing import Any

READ_ARGS = ("lci_dir",)
WRITE_ARGS = ("operation_dir",)


class PathScopeError(PermissionError):
    pass


def _globs(name: str) -> list[str] | None:
    raw = os.environ.get(name)
    if raw is None:
        return None
    return [str(g) for g in json.loads(raw)]


def _match(path: str, globs: list[str]) -> bool:
    for g in globs:
        if fnmatch.fnmatchcase(path, g):
            return True
        if g.endswith("/**") and path == g[:-3]:
            return True
    return False


def check_path_args(params: dict[str, Any]) -> None:
    read, write = _globs("V5_READ_GLOBS"), _globs("V5_WRITE_GLOBS")
    if read is None and write is None:
        return
    denied = _globs("V5_DENIED_WRITE_GLOBS") or []
    write = write or []
    read = (read or []) + write
    for key in READ_ARGS + WRITE_ARGS:
        value = params.get(key)
        if not value:
            continue
        resolved = str(Path(str(value)).expanduser().resolve())
        if key in WRITE_ARGS:
            if not _match(resolved, write) or _match(resolved, denied):
                raise PathScopeError(f"{key}={value} 不在本 agent 的写入范围内（解析为 {resolved}）")
        elif not _match(resolved, read):
            raise PathScopeError(f"{key}={value} 不在本 agent 的读取范围内（解析为 {resolved}）")
