#!/usr/bin/env python3
"""Check that QML types used by Studio are registered in its qmldir."""

from pathlib import Path
import unittest


ROOT = Path(__file__).resolve().parents[1]


class QmlManifestChecks(unittest.TestCase):
    def test_account_editor_types_are_registered(self):
        manifest = (ROOT / "ui/studio/qmldir").read_text(encoding="utf-8").splitlines()
        entries = set(line for line in manifest if line and not line.startswith("#"))
        self.assertIn("AccountCredentials 1.0 views/editor/AccountCredentials.qml", entries)
        self.assertIn("AccountNameField 1.0 views/editor/AccountNameField.qml", entries)


if __name__ == "__main__":
    unittest.main()
