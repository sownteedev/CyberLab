#!/usr/bin/env python3
"""Isolated Labtainer compatibility checks; no Docker or production catalog."""

import importlib.util
from io import BytesIO
import json
import os
from pathlib import Path
import selectors
import signal
import subprocess
import sys
import tempfile
import time
import unittest
import zipfile

sys.dont_write_bytecode = True
ROOT = Path(__file__).resolve().parents[3]
sys.path[:0] = [str(ROOT / name) for name in ("engine", "daemon", "cli")]
spec = importlib.util.spec_from_file_location("cyberlab.schemas", ROOT / "schemas/__init__.py",
                                            submodule_search_locations=[str(ROOT / "schemas")])
sys.modules["cyberlab.schemas"] = importlib.util.module_from_spec(spec)
spec.loader.exec_module(sys.modules["cyberlab.schemas"])

from cyberlab.authoring.service import Authoring
from cyberlab.lab.labtainer_compatibility import inspect_archive, LabtainerCompatibilityError
from cyberlab.lab.labtainer_converter import convert_labtainer_archive
from cyberlab.policy import RuntimePolicy
from cyberlabd.authoring import bounded, dispatch
from cyberlab_ipc import MAX_LABTAINER_ARCHIVE, METHODS


def archive_bytes(start="GLOBAL_SETTINGS\nCONTAINER shared\nUSER admin\nX11 NO\n", extra=None):
    output = BytesIO()
    with zipfile.ZipFile(output, "w") as archive:
        archive.writestr("lesson/config/start.config", start)
        for name, data in (extra or {}).items():
            archive.writestr("lesson/" + name, data)
    return output.getvalue()


class CompatibilityChecks(unittest.TestCase):
    def setUp(self):
        temporary = tempfile.TemporaryDirectory(prefix="cyberlab-labtainer-check-")
        self.addCleanup(temporary.cleanup)
        self.root = Path(temporary.name)
        self.api = Authoring(self.root / "drafts.sqlite3", self.root / "catalog",
                             RuntimePolicy(frozenset({"busybox:1.37.0"})))

    def test_simple_archive_converts_but_is_not_runtime_ready(self):
        report = inspect_archive(archive_bytes())
        self.assertTrue(report["can_import"])
        self.assertFalse(report["runtime_ready"])
        self.assertEqual(report["status"], "requires-runtime-review")
        self.assertEqual(self.api.list(1000), [])

    def test_x11_and_system_requirements_reported_together_without_content(self):
        content = archive_bytes("CONTAINER shared\nX11 YES\n", {
            "shared/_system/etc/example": "SENSITIVE_TEST_CONTENT",
            "shared/_bin/start.sh": "SENSITIVE_TEST_CONTENT",
            "instr_config/pregrade.sh": "SENSITIVE_TEST_CONTENT",
            "dockerfiles/Dockerfile.example": "SENSITIVE_TEST_CONTENT",
        })
        report = inspect_archive(content)
        self.assertFalse(report["can_import"])
        self.assertEqual({issue["code"] for issue in report["issues"]},
                         {"x11", "system_files", "startup_hooks", "grading_hooks", "image_build"})
        self.assertNotIn("SENSITIVE_TEST_CONTENT", json.dumps(report))
        with self.assertRaises(LabtainerCompatibilityError) as caught:
            self.api.import_labtainer(content, "", "", 1000)
        self.assertIn("X11", str(caught.exception))
        self.assertIn("System files", str(caught.exception))
        self.assertNotIn("SENSITIVE_TEST_CONTENT", str(caught.exception))
        self.assertEqual(self.api.list(1000), [])

    def test_removing_x11_does_not_hide_other_blockers(self):
        report = inspect_archive(archive_bytes(extra={"shared/_system/etc/config": "fixture"}))
        self.assertFalse(report["can_import"])
        self.assertEqual(report["issues"][0]["code"], "system_files")

    def test_shared_is_a_node_name_not_an_implicit_broadcast_folder(self):
        content = archive_bytes("CONTAINER shared\nCONTAINER other\n", {"shared/notes.txt": "only shared"})
        _, assets, lab = convert_labtainer_archive(content)
        self.assertEqual(assets["assets/nodes/shared/notes.txt"], b"only shared")
        self.assertNotIn("assets/nodes/other/notes.txt", assets)
        self.assertEqual(len(lab.nodes[1].files), 0)

    def test_keywords_preserved_without_colliding_with_docs(self):
        content = archive_bytes(extra={"config/keywords.txt": "accounts,linux", "docs/keywords.txt": "manual"})
        _, assets, _ = convert_labtainer_archive(content)
        self.assertEqual(assets["assets/docs/labtainer-keywords.txt"], b"accounts,linux")
        self.assertEqual(assets["assets/docs/source/keywords.txt"], b"manual")

    def test_unknown_declaration_gives_location_without_echoing_values(self):
        report = inspect_archive(archive_bytes("CONTAINER shared\nUNSUPPORTED SENSITIVE_TEST_CONTENT\n"))
        self.assertFalse(report["can_import"])
        self.assertEqual(report["issues"][0]["locations"], ["config/start.config:2"])
        self.assertNotIn("SENSITIVE_TEST_CONTENT", json.dumps(report))

    def test_comments_and_disabled_x11_are_not_blockers(self):
        self.assertTrue(inspect_archive(archive_bytes("# X11 YES\nCONTAINER shared\nX11 no\n"))["can_import"])

    def test_privileged_explicitly_blocked(self):
        report = inspect_archive(archive_bytes("CONTAINER shared\nNO_PRIVILEGE NO\n"))
        self.assertEqual(report["issues"][0]["code"], "privileged")

    def test_image_build_is_review_not_execution_or_runtime_readiness(self):
        report = inspect_archive(archive_bytes(extra={"dockerfiles/Dockerfile.fixture": "not executed"}))
        self.assertTrue(report["can_import"])
        self.assertFalse(report["runtime_ready"])
        self.assertEqual(report["issues"][0]["severity"], "review")

    def test_malformed_archive_reports_safe_error(self):
        for data in (b"", b"not an archive", archive_bytes(extra={"../outside": "fixture"}),
                     archive_bytes(extra={"other/config/start.config": "CONTAINER other"})):
            with self.subTest(size=len(data)):
                report = inspect_archive(data)
                self.assertFalse(report["can_import"])
                self.assertEqual(report["issues"][0]["code"], "archive")

    def test_keyword_encoding_and_package_limits_are_checked(self):
        for extra in ({"config/keywords.txt": b"\xff"},
                      {f"shared/file{index}.txt": b"a" for index in range(130)}):
            self.assertFalse(inspect_archive(archive_bytes(extra=extra))["can_import"])

    def test_locations_bounded_and_control_characters_removed(self):
        content = archive_bytes(extra={f"shared/_bin/script{index}\x1b.sh": "fixture" for index in range(30)})
        report = inspect_archive(content)
        self.assertFalse(report["can_import"])
        self.assertNotIn("\x1b", json.dumps(report, ensure_ascii=False))
        self.assertLess(len(json.dumps(report)), 4096)

    def test_inspection_dispatch_has_no_writes_and_is_bounded(self):
        content = archive_bytes()
        before = self.api.list(1000)
        result = json.loads(dispatch(self.api, "InspectLabtainer", [content, "", ""], 1000))
        self.assertTrue(result["can_import"])
        self.assertEqual(self.api.list(1000), before)
        self.assertEqual(METHODS["InspectLabtainer"], ("ayss", "s"))
        self.assertTrue(bounded("InspectLabtainer", [content, "", ""]))
        self.assertFalse(bounded("InspectLabtainer", [bytes(MAX_LABTAINER_ARCHIVE + 1), "", ""]))
        self.assertFalse(bounded("InspectLabtainer", [content, "a" * 65, ""]))
        with self.assertRaises(PermissionError):
            dispatch(None, "InspectLabtainer", [content, "", ""], 1000)

    def test_private_bus_cli_inspection_and_import(self):
        (self.root / "catalog").mkdir()
        supported = self.root / "supported.zip"
        supported.write_bytes(archive_bytes(extra={"config/keywords.txt": "fixture"}))
        blocked = self.root / "blocked.zip"
        blocked.write_bytes(archive_bytes("CONTAINER shared\nX11 YES\n"))
        processes = []
        try:
            bus = subprocess.Popen(["dbus-daemon", "--session", "--nofork", "--print-address=1"],
                                   stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True, start_new_session=True)
            processes.append(bus)
            with selectors.DefaultSelector() as selector:
                selector.register(bus.stdout, selectors.EVENT_READ)
                self.assertTrue(selector.select(timeout=5))
            environment = dict(os.environ, DBUS_SESSION_BUS_ADDRESS=bus.stdout.readline().strip(),
                               PYTHONDONTWRITEBYTECODE="1", PYTHONPATH=os.pathsep.join(str(ROOT / name) for name in ("engine", "daemon", "cli")))
            bootstrap = ("import importlib.util,sys; from pathlib import Path; "
                         f"root=Path({str(ROOT)!r}); "
                         "spec=importlib.util.spec_from_file_location('cyberlab.schemas',root/'schemas/__init__.py',submodule_search_locations=[str(root/'schemas')]); "
                         "sys.modules['cyberlab.schemas']=importlib.util.module_from_spec(spec); spec.loader.exec_module(sys.modules['cyberlab.schemas']); "
                         "from cyberlabd.main import main; raise SystemExit(main())")
            with (self.root / "daemon.log").open("w") as log:
                daemon = subprocess.Popen([sys.executable, "-B", "-c", bootstrap, "--test-session-bus", "--catalog", str(self.root / "catalog"),
                                           "--authoring-state", str(self.root / "bus.sqlite3")],
                                          env=environment, stdout=log, stderr=subprocess.STDOUT, start_new_session=True)
                processes.append(daemon)

                def cli(*arguments):
                    return subprocess.run([sys.executable, "-B", "-m", "cyberlab_cli.main", "--test-session-bus", *map(str, arguments)],
                                          env=environment, capture_output=True, text=True, timeout=15)

                for _ in range(40):
                    ready = cli("info")
                    if ready.returncode == 0 or daemon.poll() is not None:
                        break
                    time.sleep(0.1)
                self.assertEqual(ready.returncode, 0, (self.root / "daemon.log").read_text())
                self.assertIn("labtainer-inspect", ready.stdout)
                for path, expected in ((supported, True), (blocked, False)):
                    result = cli("inspect-labtainer", path)
                    self.assertEqual(result.returncode, 0, result.stderr)
                    self.assertEqual(json.loads(result.stdout)["can_import"], expected)
                self.assertEqual(json.loads(cli("draft", "list").stdout), [])
                failure = cli("import-labtainer", blocked)
                self.assertNotEqual(failure.returncode, 0)
                self.assertIn("LabtainerCompatibility", failure.stderr)
                self.assertIn("X11", failure.stderr)
                self.assertNotIn("Invalid request values", failure.stderr)
                imported = cli("import-labtainer", supported)
                self.assertEqual(imported.returncode, 0, imported.stderr)
                self.assertTrue(json.loads(imported.stdout)["id"])
                self.assertEqual(len(json.loads(cli("draft", "list").stdout)), 1)
                self.assertEqual(json.loads(cli("sessions").stdout), [])
        finally:
            for process in reversed(processes):
                if process.poll() is None:
                    os.killpg(process.pid, signal.SIGTERM)
                    try:
                        process.wait(timeout=5)
                    except subprocess.TimeoutExpired:
                        os.killpg(process.pid, signal.SIGKILL)
                        process.wait()
                for stream in (process.stdout, process.stderr):
                    if stream:
                        stream.close()


if __name__ == "__main__":
    unittest.main()
