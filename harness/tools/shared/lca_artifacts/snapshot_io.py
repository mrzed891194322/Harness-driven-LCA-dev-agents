"""Reuse file reads only inside one deterministic check, never across turns."""

from __future__ import annotations

import functools
import hashlib
import json
from contextvars import ContextVar
from pathlib import Path

from harness.tools.shared.control_openlca.workflow import sha256_file as _hash_file

_reads: ContextVar[dict | None] = ContextVar("lca_check_reads", default=None)


def check_snapshot(function):
    @functools.wraps(function)
    def wrapped(*args, **kwargs):
        token = _reads.set({})
        try:
            return function(*args, **kwargs)
        finally:
            _reads.reset(token)

    return wrapped


def _identity(path: Path):
    stat = path.stat()
    return stat.st_dev, stat.st_ino, stat.st_size, stat.st_mtime_ns, stat.st_ctime_ns


def _read(path: Path) -> bytes:
    cache = _reads.get()
    if cache is None:
        return path.read_bytes()
    path = path.resolve()
    identity = _identity(path)
    previous = cache.get(path)
    if previous is not None and previous[0] == identity:
        return previous[1]
    data = path.read_bytes()
    if _identity(path) != identity:
        raise ValueError(f"input changed while reading: {path}")
    cache[path] = (identity, data, None)
    return data


def sha256_file(path: Path) -> str:
    cache = _reads.get()
    if cache is None:
        return _hash_file(path)
    path = path.resolve()
    data = _read(path)
    identity, _, digest = cache[path]
    if digest is None:
        digest = hashlib.sha256(data).hexdigest()
        cache[path] = (identity, data, digest)
    return digest


def load_json(path: Path):
    # Parse separately so a caller cannot mutate another reader's cached object.
    return json.loads(_read(path).decode("utf-8"))
