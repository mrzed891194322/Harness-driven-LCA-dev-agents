"""Status page shows the real Pi SDK version (temp dirs only)."""

import json
import sys
from pathlib import Path

from backend.services.diagnostics_service import (
    PI_SDK_PACKAGE,
    pi_sdk_version,
    toolchain_versions,
)


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


def test_toolchain_reads_packages_and_blanks_missing(tmp_path: Path) -> None:
    web = tmp_path / "src/frontend/web/node_modules"
    (web / "next").mkdir(parents=True)
    (web / "next/package.json").write_text(json.dumps({"version": "15.5.27"}))
    out = toolchain_versions(tmp_path)
    assert out["next"] == "15.5.27"
    assert out["typescript"] == ""  # not installed in the temp root -> dropped by the page
    assert out["python"] == sys.version.split()[0]
    assert set(out) == {"typescript", "next", "npm", "pi_sdk", "python", "uv"}
