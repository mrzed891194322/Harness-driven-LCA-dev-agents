from __future__ import annotations

import os
import subprocess
from pathlib import Path

import pytest

PROJECT_ROOT = Path(__file__).resolve().parents[3]


def test_pi_runtime_protocol_version_mock() -> None:
    dist = PROJECT_ROOT / "src" / "pi-runtime" / "dist" / "main.js"
    argv = ["node", str(dist)] if dist.is_file() else [
        "node",
        "--import",
        "tsx",
        str(PROJECT_ROOT / "src" / "pi-runtime" / "src" / "main.ts"),
    ]
    env = {**os.environ, "PI_RUNTIME_MOCK": "1"}
    proc = subprocess.run(
        argv,
        input='{"type":"req","id":"1","method":"protocol.version","params":{}}\n',
        capture_output=True,
        text=True,
        cwd=str(PROJECT_ROOT),
        env=env,
        timeout=20,
    )
    assert proc.returncode == 0
    assert '"ok":true' in proc.stdout
    assert '"version":1' in proc.stdout
