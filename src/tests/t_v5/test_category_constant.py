"""The openLCA project category is one constant, never derived from the checkout folder name."""
from __future__ import annotations

import re
import runpy
import shutil

from tests.t_v5.conftest import REPO

CAT = "202606-harness-agent-LCA"
USERS = [
    "harness/tools/mcp/control_openlca/main.py",
    "harness/tools/shared/control_openlca/cleanup_service.py",
]


def test_constant_value_independent_of_folder(tmp_path):
    other = tmp_path / "lca-some-other-checkout-name" / "category.py"
    other.parent.mkdir()
    shutil.copy(REPO / "harness/tools/shared/control_openlca/category.py", other)
    ns = runpy.run_path(str(other))
    assert ns["OPENLCA_PROJECT_CATEGORY"] == CAT
    assert ns["locked_category"]("") == CAT


def test_no_folder_name_derivation_left():
    for rel in USERS:
        text = (REPO / rel).read_text(encoding="utf-8")
        assert "OPENLCA_PROJECT_CATEGORY" in text or "locked_category" in text, rel
        assert not re.search(r"(PROJECT_ROOT|ROOT|root|parent)\.name", text), rel
        assert f'"{CAT}"' not in text, f"{rel} hardcodes the category; import the constant"
