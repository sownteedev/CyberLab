#!/usr/bin/env python3
"""Isolated system-update protocol checks; never install or contact GitHub."""
import contextlib
import io
import json
from pathlib import Path
import sys
import unittest
import importlib.util
import os
import tempfile
from types import SimpleNamespace
from unittest.mock import patch

ROOT = Path(__file__).resolve().parents[3]
sys.path.insert(0, str(ROOT / "cli"))
from cyberlab_cli import system_update as update

COMMIT = "a" * 40
spec = importlib.util.spec_from_file_location("update_window", ROOT / "ui/update_window.py")
window = importlib.util.module_from_spec(spec)
spec.loader.exec_module(window)

class UpdateProtocolTests(unittest.TestCase):
    def events(self, **kwargs):
        output = io.StringIO()
        with contextlib.redirect_stdout(output):
            code = update.run_update(json_output=True, **kwargs)
        return code, [json.loads(line) for line in output.getvalue().splitlines()]

    def test_check_json_unknown_metadata_never_installs(self):
        with patch.object(update, "latest_commit", return_value=COMMIT), patch.object(update, "installed_commit", return_value=None), patch.object(update, "install_snapshot") as install:
            code, events = self.events(check=True)
        self.assertEqual(code, 0)
        self.assertFalse(events[-1]["available"])
        self.assertIsNone(events[-1]["installed"])
        install.assert_not_called()

    def test_unknown_metadata_plain_check_does_not_recommend_update(self):
        output = io.StringIO()
        with patch.object(update, "latest_commit", return_value=COMMIT), patch.object(update, "installed_commit", return_value=None), patch.object(update, "install_snapshot") as install, contextlib.redirect_stdout(output):
            self.assertEqual(update.run_update(check=True), 0)
        self.assertIn("Chưa thể xác định", output.getvalue())
        self.assertNotIn("Chạy cyberlab update", output.getvalue())
        install.assert_not_called()

    def test_same_commit_is_current(self):
        with patch.object(update, "latest_commit", return_value=COMMIT), patch.object(update, "installed_commit", return_value=COMMIT), patch.object(update, "install_snapshot") as install:
            code, events = self.events(check=True)
        self.assertEqual(code, 0)
        self.assertFalse(events[-1]["available"])
        install.assert_not_called()

    def test_only_descendant_commit_is_an_update(self):
        for status in ("ahead", "behind", "diverged"):
            def fetch(url, output, limit):
                self.assertIn('/compare/' + 'b' * 40 + '...' + COMMIT, url)
                output.write(json.dumps({"status": status}).encode())
            with self.subTest(status=status), patch.object(update, "latest_commit", return_value=COMMIT), patch.object(update, "installed_commit", return_value='b' * 40), patch.object(update, "download", side_effect=fetch), patch.object(update, "install_snapshot") as install:
                code, events = self.events(check=True)
                self.assertEqual(code, 0)
                self.assertEqual(events[-1]["available"], status == "ahead")
                self.assertEqual(events[-1]["comparison"], status)
                install.assert_not_called()

    def test_explicit_update_refuses_downgrade_and_divergence(self):
        for status in ("behind", "diverged"):
            def fetch(url, output, limit):
                output.write(json.dumps({"status": status}).encode())
            with self.subTest(status=status), patch.object(update, "installed_commit", return_value='b' * 40), patch.object(update, "download", side_effect=fetch), patch.object(update, "install_snapshot") as install:
                code, events = self.events(commit=COMMIT)
                self.assertNotEqual(code, 0)
                self.assertEqual(events[-1]["event"], "error")
                install.assert_not_called()

    def test_missing_local_commit_on_github_is_unknown_not_update(self):
        from urllib.error import HTTPError
        with patch.object(update, "latest_commit", return_value=COMMIT), patch.object(update, "installed_commit", return_value='b' * 40), patch.object(update, "download", side_effect=HTTPError('https://example.test', 404, 'missing', {}, None)):
            code, events = self.events(check=True)
        self.assertEqual(code, 0)
        self.assertFalse(events[-1]["available"])
        self.assertEqual(events[-1]["comparison"], "unknown")

    def test_forward_update_installs_and_verifies_receipt(self):
        def fetch(url, output, limit):
            output.write(b'{"status":"ahead"}')
        with patch.object(update, "installed_commit", side_effect=['b' * 40, COMMIT]), patch.object(update, "download", side_effect=fetch), patch.object(update, "install_snapshot", return_value=0) as install:
            code, events = self.events(commit=COMMIT)
        self.assertEqual(code, 0)
        self.assertEqual(install.call_args.args[0], COMMIT)
        self.assertEqual(events[-1]["event"], "complete")

    def test_unknown_or_invalid_ancestry_never_replaces_known_installation(self):
        from urllib.error import HTTPError
        for status in (None, "identical", "invalid"):
            def fetch(url, output, limit):
                if status is None:
                    raise HTTPError(url, 404, 'missing', {}, None)
                output.write(json.dumps({"status": status}).encode())
            with self.subTest(status=status), patch.object(update, "installed_commit", return_value='b' * 40), patch.object(update, "download", side_effect=fetch), patch.object(update, "install_snapshot") as install:
                code, events = self.events(commit=COMMIT)
                self.assertEqual(code, 1)
                self.assertEqual(events[-1]["event"], "error")
                install.assert_not_called()

    def test_network_error_is_structured(self):
        with patch.object(update, "latest_commit", side_effect=OSError("offline")):
            code, events = self.events(check=True)
        self.assertEqual(code, 1)
        self.assertEqual(events[-1]["event"], "error")

    def test_pinned_commit_not_refetched(self):
        with patch.object(update, "latest_commit") as latest, patch.object(update, "installed_commit", side_effect=[None, COMMIT]), patch.object(update, "install_snapshot", return_value=0) as install:
            code, events = self.events(commit=COMMIT)
        self.assertEqual(code, 0)
        latest.assert_not_called()
        self.assertEqual(install.call_args.args[0], COMMIT)
        self.assertEqual(events[-1]["event"], "complete")

    def test_receipt_mismatch_never_reports_success(self):
        with patch.object(update, "installed_commit", return_value=None), patch.object(update, "install_snapshot", return_value=0):
            code, events = self.events(commit=COMMIT)
        self.assertEqual(code, 1)
        self.assertEqual(events[-1]["event"], "error")

    def test_install_failure_never_reports_success(self):
        with patch.object(update, "installed_commit", return_value=None), patch.object(update, "install_snapshot", return_value=126):
            code, events = self.events(commit=COMMIT)
        self.assertNotEqual(code, 0)
        self.assertEqual(events[-1]["event"], "error")

    def test_download_percent_uses_content_length(self):
        response = io.BytesIO(b"sample")
        response.url = "https://example.test/snapshot"
        response.headers = {"Content-Length": "6"}
        events = []
        with patch.object(update.urllib.request, "urlopen", return_value=response):
            update.download(response.url, io.BytesIO(), 10, lambda event, **data: events.append(data))
        self.assertEqual(events[-1]["percent"], 100)
        self.assertEqual(events[-1]["received"], 6)

    def test_unknown_length_is_indeterminate(self):
        response = io.BytesIO(b"sample")
        response.url = "https://example.test/snapshot"
        response.headers = {}
        events = []
        with patch.object(update.urllib.request, "urlopen", return_value=response):
            update.download(response.url, io.BytesIO(), 10, lambda event, **data: events.append(data))
        self.assertIsNone(events[-1]["percent"])

    def test_truncated_download_rejected(self):
        response = io.BytesIO(b"small")
        response.url = "https://example.test/snapshot"
        response.headers = {"Content-Length": "8"}
        with patch.object(update.urllib.request, "urlopen", return_value=response), self.assertRaises(ValueError):
            update.download(response.url, io.BytesIO(), 10, lambda *args, **kwargs: None)

    def test_gui_authentication_uses_existing_guarded_installer(self):
        with tempfile.TemporaryDirectory() as directory:
            temporary = tempfile.TemporaryDirectory
            def staging(**kwargs):
                return temporary(prefix=kwargs["prefix"], dir=directory)
            def extract(archive, source, commit):
                (source / "tools/install").mkdir(parents=True)
                (source / "tools/install/system.sh").touch()
            process = SimpleNamespace(stdout=io.BytesIO(b"CYBERLAB_UPDATE_PHASE:build\n"), wait=lambda: 0)
            events = []
            with patch.object(update.tempfile, "TemporaryDirectory", side_effect=staging), patch.object(update, "download"), patch.object(update, "extract_snapshot", side_effect=extract), patch.object(update, "root_probe_access"), patch.object(update.os, "geteuid", return_value=1000), patch.object(update.os, "access", return_value=True), patch.object(update.subprocess, "Popen", return_value=process) as spawn:
                code = update.install_snapshot(COMMIT, ("--update",), graphical=True, progress=lambda event, **data: events.append(event))
            self.assertEqual(code, 0)
            command = spawn.call_args.args[0]
            self.assertEqual(command[:3], ["/usr/bin/pkexec", "--disable-internal-agent", "/bin/bash"])
            self.assertIn("--update", command)
            self.assertIn("--user", command)
            self.assertIn("build", events)
            self.assertEqual(list(Path(directory).iterdir()), [])

    def test_wait_identity_tracks_process_start(self):
        self.assertTrue(window.process_identity(os.getpid()))
        with self.assertRaises(ValueError):
            window.process_identity(0)

    def test_cancelled_handoff_does_not_install(self):
        with tempfile.TemporaryDirectory() as directory:
            stage = Path(directory)
            (stage / "config.json").write_text(json.dumps({"pid": os.getpid(), "identity": window.process_identity(os.getpid())}))
            (stage / "cancel").touch()
            with self.assertRaisesRegex(ValueError, "Studio"):
                window.run_worker(stage)

    def test_restart_uses_installed_launcher_without_shell(self):
        with patch.object(window.time, "sleep"), patch.object(window.subprocess, "Popen", return_value=SimpleNamespace(poll=lambda: None)) as spawn:
            window.restart_studio()
        self.assertEqual(spawn.call_args.args[0], ["/usr/local/bin/cyberlab-studio"])
        self.assertTrue(spawn.call_args.kwargs["start_new_session"])

    def test_restart_failure_remains_visible_to_updater(self):
        with patch.object(window.time, "sleep"), patch.object(window.subprocess, "Popen", return_value=SimpleNamespace(poll=lambda: 1)), self.assertRaises(ValueError):
            window.restart_studio()

    def test_updater_is_independent_but_studio_guard_still_applies(self):
        spec = importlib.util.spec_from_file_location("upgrade_probe", ROOT / "tools/install/upgrade_runtime.py")
        upgrade = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(upgrade)
        with tempfile.TemporaryDirectory() as directory:
            process = Path(directory) / "123"
            process.mkdir()
            command = process / "cmdline"
            with patch.object(upgrade, "PROC", Path(directory)):
                for executable in ("/usr/bin/qs", "/usr/lib/cyberlab/gui-runtime/bin/quickshell"):
                    with self.subTest(executable=executable):
                        command.write_bytes(f"{executable}\0--path\0/var/tmp/cl-updater-fixture/studio\0".encode())
                        upgrade.check_studio_closed()
                        command.write_bytes(f"{executable}\0--path\0/usr/lib/cyberlab/venv/cyberlab_studio/studio\0".encode())
                        with self.assertRaisesRegex(ValueError, "Close CyberLab Studio"):
                            upgrade.check_studio_closed()

if __name__ == "__main__":
    unittest.main()
