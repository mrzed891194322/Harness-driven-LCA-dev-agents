"""revise-lca revision files (I-45): originals stay untouched, revision N writes ``<name>.rev<N>.<ext>``.

Unit of revision = one entry directly inside a produce dir (``bom/bom.json``, ``bom/bom.md``,
``mapping/LCI``, ``report/raw`` ...). Original = rev 0. A revise run allocates, per produce entry,
N = 1 + the highest existing rev of that entry; companions in the same dir use the same N
(``bom.rev1.md``, ``LCI.rev1/``). N is saved in ``runs/_run/revisions.json`` so a resume reuses it.
Inputs (``requires``) resolve to the latest version (highest rev, else original); inside a node's own
produce dir the latest *below* its N, so a resumed node never reads its own half-written revision.
"""
from __future__ import annotations

import json
import re
import shutil
from pathlib import Path, PurePosixPath

from backend.v5.access import produce_dir
from backend.v5.config import Node, Produce

_REV = re.compile(r"\.rev(\d+)$")
FILE = "revisions.json"


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


def latest(art: Path, rel: str, below: int | None = None) -> str:
    revs = [r for r in versions(art, rel) if below is None or r < below]
    return rev_path(rel, max(revs)) if revs else rel


def allocate(art: Path, nodes: list[Node]) -> dict[str, int]:
    """{produce path: N}; one fresh revise run allocates once, before any node writes."""
    return {p.path: 1 + max(versions(art, p.path) or [0]) for n in nodes for p in n.produces}


def load(run_dir: Path) -> dict[str, int]:
    path = run_dir / FILE
    return {k: int(v) for k, v in json.loads(path.read_text(encoding="utf-8")).items()} if path.is_file() else {}


def save(run_dir: Path, revs: dict[str, int]) -> None:
    run_dir.mkdir(parents=True, exist_ok=True)
    (run_dir / FILE).write_text(json.dumps(revs, ensure_ascii=False, indent=2), encoding="utf-8")


def node_rev(node: Node, revs: dict[str, int]) -> int:
    return max((revs.get(p.path, 0) for p in node.produces), default=0)


def effective(art: Path, node: Node, revs: dict[str, int]) -> Node:
    """Node copy whose produces point at rev N and whose requires point at the latest inputs."""
    n = node_rev(node, revs)
    if not n:
        return node
    own = {produce_dir(p.path) for p in node.produces}
    requires = [latest(art, r, below=n if PurePosixPath(r).parts[0] in own else None) for r in node.requires]
    produces = [Produce(spec=p.spec, path=rev_path(p.path, revs.get(p.path, n))) for p in node.produces]
    return node.model_copy(update={"requires": requires, "produces": produces, "revision": n})


def clear(art: Path, node: Node, n: int) -> None:
    """Remove only this node's rev-N entries (originals and other revs untouched)."""
    for d in {produce_dir(p.path) for p in node.produces}:
        parent = art / d
        if not parent.is_dir():
            continue
        for item in parent.iterdir():
            if split(item.name)[1] == n:
                shutil.rmtree(item) if item.is_dir() and not item.is_symlink() else item.unlink()
