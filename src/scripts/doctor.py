#!/usr/bin/env python
"""npm run doctor -- v5 config self-check that needs no model call.

Loads every workflow under harness/workflows, its nodes, roles, rules and
specs, and renders each agent's system prompt. Any YAML, schema or template
error is printed with its file.
"""

from __future__ import annotations

import sys
from pathlib import Path

_ROOT = next(p for p in Path(__file__).resolve().parents if (p / "pyproject.toml").is_file())
for _p in (_ROOT / "src", _ROOT):
    if str(_p) not in sys.path:
        sys.path.insert(0, str(_p))


def check(root: Path) -> bool:
    from backend.v5.config import ConfigError, list_workflows, load_workflow
    from backend.v5.inject import Injector

    ok = True
    injector = Injector(root)
    for name in list_workflows(root):
        try:
            _wf, nodes = load_workflow(root, name)
            for node in nodes:
                for role in node.agents:
                    injector.system(node, role)
        except (ConfigError, OSError, ValueError) as exc:
            print(f"✗ {name}: {exc}")
            ok = False
            continue
        print(f"✓ {name}: {len(nodes)} node(s)")
    return ok


def main(argv: list[str] | None = None) -> int:
    del argv
    return 0 if check(_ROOT) else 1


if __name__ == "__main__":
    raise SystemExit(main())
