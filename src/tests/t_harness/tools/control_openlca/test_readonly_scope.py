from __future__ import annotations

import unittest

from harness.tools.shared.control_openlca.readonly import category_outside_project


class CategoryScopeTests(unittest.TestCase):
    def test_outside_project_flags(self) -> None:
        target = "my-lca-run"
        self.assertTrue(category_outside_project(None, target))
        self.assertTrue(category_outside_project("", target))
        self.assertTrue(category_outside_project("other", target))
        self.assertFalse(category_outside_project(target, target))
        self.assertFalse(category_outside_project(f"{target}/foreground", target))
