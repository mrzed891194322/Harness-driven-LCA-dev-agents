"""Artifact revisions (WORKFLOW_DESIGN §1): rev 0 writes the original path, rev k writes ``<name>.rev<k>.<ext>``.

Unit of revision = one entry directly inside a produce dir (``bom/bom.json``, ``mapping/LCI`` ...); all older
versions stay. A queue item's rev is 0 on a normal first run, else 1 + the highest existing rev of its produces
(redo, revise-lca ``start_rev: next``). ``requires`` resolve to the latest existing version at node start.
"""
from __future__ import annotations

import re
import shutil
from pathlib import Path, PurePosixPath

from backend.v5.access import produce_dir
from backend.v5.config import Node, Produce

_REV = re.compile(r"\.rev(\d+)$")


def split(name: str) -> tuple[str, int, str]:
    """``bom.rev2.json`` -> (``bom``, 2, ``.json``); ``LCI`` -> (``LCI``, 0, ``""``)."""
    p = PurePosixPath(name)
    stem, ext = (p.stem, p.suffix) if p.suffix and not _REV.search(name) else (name, "")
    m = _REV.search(stem)
    if m:
        return stem[: m.start()], int(m.group(1)), ext
    return stem, 0, ext


def rev_name(name: str, n: int) -> str:
    stem, _r, ext = split(name)
    return f"{stem}.rev{n}{ext}" if n else f"{stem}{ext}"


def rev_path(rel: str, n: int) -> str:
    """Rename the entry directly under the produce dir: ``mapping/LCI/processes`` -> ``mapping/LCI.rev1/processes``."""
    parts = PurePosixPath(rel).parts
    if len(parts) < 2 or not n:
        return rel
    return str(PurePosixPath(parts[0], rev_name(parts[1], n), *parts[2:]))


def versions(art: Path, rel: str) -> list[int]:
    """Existing revs (0 = original) of the entry that ``rel`` names."""
    parts = PurePosixPath(rel).parts
    if len(parts) < 2:
        return [0] if (art / rel).exists() else []
    parent = art / parts[0]
    stem, _r, ext = split(parts[1])
    found = []
    if parent.is_dir():
        for item in parent.iterdir():
            s, r, e = split(item.name)
            if s == stem and e == ext:
                found.append(r)
    return sorted(found)


def latest(art: Path, rel: str) -> str:
    revs = versions(art, rel)
    return rev_path(rel, max(revs)) if revs else rel


def next_rev(art: Path, node: Node) -> int:
    return 1 + max((r for p in node.produces for r in versions(art, p.path)), default=0)


def at_rev(art: Path, node: Node, rev: int) -> Node:
    """Node copy for one queue item: produces at rev ``rev``, requires at their latest existing version."""
    requires = [latest(art, r) for r in node.requires]
    produces = [Produce(spec=p.spec, path=rev_path(p.path, rev)) for p in node.produces]
    return node.model_copy(update={"requires": requires, "produces": produces, "rev": rev})


def clear(art: Path, node: Node, rev: int) -> None:
    """Remove a queue item's outputs: rev 0 = its whole produce dirs; rev k = only the rev-k entries in them."""
    for d in {produce_dir(p.path) for p in node.produces}:
        parent = art / d
        if not rev:
            shutil.rmtree(parent, ignore_errors=True)
            continue
        for item in list(parent.iterdir()) if parent.is_dir() else []:
            if split(item.name)[1] == rev:
                shutil.rmtree(item) if item.is_dir() and not item.is_symlink() else item.unlink()
