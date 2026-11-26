"""Check relocated tool entry points without services, Docker or user data."""

import ast
from pathlib import Path
import subprocess
import sys
import tempfile
import unittest

ROOT = Path(__file__).resolve().parents[3]


class ToolLayoutChecks(unittest.TestCase):
    def run_tool(self, relative, *arguments):
        with tempfile.TemporaryDirectory(prefix="cyberlab-tool-layout-") as directory:
            result = subprocess.run(
                [sys.executable, "-B", "-I", str(ROOT / relative), *arguments],
                cwd=directory, capture_output=True, text=True, timeout=60,
            )
        self.assertEqual(result.returncode, 0, result.stdout + result.stderr)
        return result

    def test_installer_and_administrative_entry_points(self):
        for relative in (
            "tools/install/runtime_admin.py", "tools/install/upgrade_runtime.py",
            "tools/admin/migrate_catalog.py", "tools/admin/prepare_lab_images.py",
            "tools/admin/prepare_ubuntu_workstation.py",
        ):
            with self.subTest(relative=relative):
                self.run_tool(relative, "--help")

    def test_unit_entry_point_works_outside_checkout(self):
        self.run_tool("tools/tests/unit/check_installer_distros.py")

    def test_cross_group_ui_import_works_outside_checkout(self):
        self.run_tool("tools/tests/ui/check_ui_diagnostics.py")

    def test_registered_tool_imports_exist(self):
        for path in (ROOT / "tools").rglob("*.py"):
            for node in ast.walk(ast.parse(path.read_text())):
                names = [node.module] if isinstance(node, ast.ImportFrom) else (
                    [alias.name for alias in node.names] if isinstance(node, ast.Import) else []
                )
                if isinstance(node, ast.ImportFrom) and node.module and node.module.startswith("tools."):
                    module_path = ROOT.joinpath(*node.module.split("."))
                    if module_path.is_dir():
                        names.extend(f"{node.module}.{alias.name}" for alias in node.names)
                for name in names:
                    if name and name.startswith("tools."):
                        target = ROOT.joinpath(*name.split("."))
                        self.assertTrue(target.is_dir() or target.with_suffix(".py").is_file(),
                                        f"{path}: missing {name}")

    def test_runtime_helper_import_works_outside_checkout(self):
        with tempfile.TemporaryDirectory(prefix="cyberlab-tool-import-") as directory:
            result = subprocess.run(
                [sys.executable, "-B", "-I", "-c",
                 f"import sys; sys.path.insert(0, {str(ROOT)!r}); "
                 "from tools.tests.runtime.check_seamless_apps import window_names; "
                 "assert callable(window_names)"],
                cwd=directory, capture_output=True, text=True, timeout=15,
            )
        self.assertEqual(result.returncode, 0, result.stdout + result.stderr)


if __name__ == "__main__":
    unittest.main()
