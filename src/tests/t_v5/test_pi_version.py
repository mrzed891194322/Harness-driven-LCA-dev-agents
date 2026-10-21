"""Status page shows the real Pi SDK version (temp dirs only)."""

import json
from pathlib import Path

from backend.services.diagnostics_service import PI_SDK_PACKAGE, pi_sdk_version


def test_pi_sdk_version_installed_then_pinned(tmp_path: Path) -> None:
    runtime = tmp_path / "src/pi-runtime"
    runtime.mkdir(parents=True)
    (runtime / "package.json").write_text(json.dumps({"dependencies": {PI_SDK_PACKAGE: "^1.3.0"}}))
    assert pi_sdk_version(tmp_path) == "1.3.0"
    installed = runtime / "node_modules" / PI_SDK_PACKAGE
    installed.mkdir(parents=True)
    (installed / "package.json").write_text(json.dumps({"version": "1.3.2"}))
    assert pi_sdk_version(tmp_path) == "1.3.2"
    assert pi_sdk_version(tmp_path / "missing") == ""
