"""Check the narrow optional Qt WorkerScript diagnostic exemption."""

import unittest

from check_notifications import diagnostics


class DiagnosticChecks(unittest.TestCase):
    warning = "qt.core.qobject.connect: QObject::connect(QJSEngine, QtObject): invalid nullptr parameter"

    def test_strict_default_preserves_warning(self):
        self.assertEqual(diagnostics(self.warning), self.warning)

    def test_plain_and_colored_known_warning(self):
        colored = "\x1b[33m WARN\x1b[97m qt.core.qobject.connect\x1b[0m: " + self.warning.split(": ", 1)[1]
        for line in (self.warning, "QWARN : Fixture() " + self.warning, colored):
            with self.subTest(line=line):
                self.assertEqual(diagnostics(line + "\nPASS: fixture", True), "PASS: fixture")

    def test_other_warnings_and_errors_survive(self):
        for line in ("QWARN: another problem", "ERROR: TypeError", self.warning + " extra problem"):
            with self.subTest(line=line):
                self.assertEqual(diagnostics(line, True), line)


if __name__ == "__main__":
    unittest.main()
