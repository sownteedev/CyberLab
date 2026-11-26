#!/usr/bin/env python3
"""Isolated terminal regression checks; no Docker, system bus or user data."""

import asyncio
from contextlib import redirect_stderr
import io
import json
import os
from pathlib import Path
import shlex
import subprocess
import sys
import tempfile
from types import SimpleNamespace
import unittest
from unittest.mock import patch

sys.dont_write_bytecode = True
ROOT = Path(__file__).resolve().parents[3]
sys.path[:0] = [str(ROOT / "cli"), str(ROOT / "daemon")]

from cyberlab_cli import terminal_apps as apps
from cyberlab_cli import window_registry as registry
from cyberlab_cli import windows


class TerminalChecks(unittest.TestCase):
    def setUp(self):
        self.temporary = tempfile.TemporaryDirectory(prefix="cyberlab-terminal-check-")
        self.addCleanup(self.temporary.cleanup)
        self.root = Path(self.temporary.name)
        self.bin = self.root / "bin with spaces"
        self.bin.mkdir()
        self.environment = {"HOME": str(self.root), "PATH": str(self.bin),
                            "XDG_CONFIG_HOME": str(self.root / "config"),
                            "XDG_CONFIG_DIRS": str(self.root / "system-config"),
                            "XDG_DATA_DIRS": str(self.root / "data"),
                            "XDG_RUNTIME_DIR": str(self.root / "runtime"), "WAYLAND_DISPLAY": "test"}
        Path(self.environment["XDG_RUNTIME_DIR"]).mkdir(mode=0o700)
        self.session = {"id": "a" * 32, "state": "RUNNING", "terminals": ["client", "server"],
                        "nodes": [["client", "busybox"], ["server", "busybox"]],
                        "terminal_counts": [["client", 2], ["server", 1]],
                        "terminal_slots": [["client", 0], ["client", 1], ["server", 0]]}

    def executable(self, name, native=True):
        path = self.bin / name
        path.write_bytes(b"\x7fELFfixture" if native else b"#!/bin/sh\nexit 0\n")
        path.chmod(0o700)
        return path

    def xdg_list(self, content, location=None):
        path = location or Path(self.environment["XDG_CONFIG_HOME"]) / "xdg-terminals.list"
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(content)

    def test_empty_and_single_inventory(self):
        self.assertIsNone(apps.inspect_apps(environment=self.environment)["selected"])
        self.executable("blackbox-terminal")
        result = apps.inspect_apps(environment=self.environment)
        self.assertEqual(result["selected"]["id"], "blackbox")
        self.assertEqual(result["source"], "fallback")
        self.assertFalse(apps.preference_path(self.environment).exists())

    def test_stable_order_aliases_and_native_only(self):
        self.executable("konsole")
        blackbox = self.executable("blackbox-terminal")
        (self.bin / "blackbox").symlink_to(blackbox)
        self.executable("kitty", native=False)
        (self.bin / "ghostty").symlink_to(self.executable("snap"))
        (self.bin / "foot").symlink_to(self.executable("flatpak"))
        self.assertEqual([entry["id"] for entry in apps.discover(self.environment)], ["blackbox", "konsole"])

    def test_executable_duplicates(self):
        blackbox = self.executable("blackbox-terminal")
        (self.bin / "konsole").symlink_to(blackbox)
        self.assertEqual(len(apps.discover(self.environment)), 1)

    def test_preferences_persist_and_missing_choice_is_preserved(self):
        self.executable("blackbox-terminal")
        konsole = self.executable("konsole")
        result = apps.inspect_apps("konsole", self.environment)
        self.assertEqual(result["source"], "preference")
        self.assertEqual(apps.preference_path(self.environment).stat().st_mode & 0o777, 0o600)
        konsole.unlink()
        result = apps.inspect_apps(environment=self.environment)
        self.assertEqual(result["preferred"], "konsole")
        self.assertEqual(result["selected"]["id"], "blackbox")
        self.assertIn("missing-preferred", result["warnings"])
        self.assertEqual(apps.read_preference(self.environment)[0], "konsole")
        self.assertEqual(apps.inspect_apps("auto", self.environment)["preferred"], "auto")

    def test_preference_requires_available_id(self):
        for identifier in ("unknown", "konsole", "sh -c whoami"):
            with self.subTest(identifier=identifier), self.assertRaises(ValueError):
                apps.inspect_apps(identifier, self.environment)

    def test_corrupt_preferences_never_execute_or_rewrite(self):
        self.executable("konsole")
        path = apps.preference_path(self.environment)
        path.parent.mkdir(parents=True)
        for content in ("invalid", '{"version":1,"preferred":[]}', '{"version":2,"preferred":"auto"}', "[]"):
            path.write_text(content)
            result = apps.inspect_apps(environment=self.environment)
            self.assertIn("invalid-config", result["warnings"])
            self.assertEqual(path.read_text(), content)

    def test_symlink_preferences_are_not_followed(self):
        path = apps.preference_path(self.environment)
        path.parent.mkdir(parents=True)
        target = self.root / "untouched"
        target.write_text("private")
        path.symlink_to(target)
        self.assertIn("invalid-config", apps.read_preference(self.environment)[1])
        with self.assertRaises(ValueError):
            apps.save_preference("auto", [], self.environment)
        self.assertEqual(target.read_text(), "private")

    def test_selection_precedence(self):
        blackbox = self.executable("blackbox-terminal")
        self.executable("konsole")
        self.environment["TERMINAL"] = str(blackbox)
        self.xdg_list("org.kde.konsole.desktop\n")
        self.assertEqual(apps.inspect_apps(environment=self.environment)["source"], "xdg")
        self.assertEqual(apps.inspect_apps("blackbox", self.environment)["source"], "preference")
        apps.save_preference("auto", apps.discover(self.environment), self.environment)
        self.xdg_list("")
        self.assertEqual(apps.inspect_apps(environment=self.environment)["source"], "environment")
        self.environment.pop("TERMINAL")
        (self.bin / "x-terminal-emulator").symlink_to(blackbox)
        self.assertEqual(apps.inspect_apps(environment=self.environment)["source"], "alternative")

    def test_xdg_precedence_exclusions_and_unknown_entries(self):
        self.executable("blackbox-terminal")
        self.executable("konsole")
        self.environment["XDG_CURRENT_DESKTOP"] = "NIRI:GNOME"
        self.xdg_list("com.raggesilver.BlackBox.desktop\n")
        self.xdg_list("org.kde.konsole.desktop\n", Path(self.environment["XDG_CONFIG_HOME"]) / "niri-xdg-terminals.list")
        self.assertEqual(apps.inspect_apps(environment=self.environment)["selected"]["id"], "konsole")
        self.xdg_list("-com.raggesilver.BlackBox.desktop\n/unknown:directive\nunknown.desktop\n")
        (Path(self.environment["XDG_CONFIG_HOME"]) / "niri-xdg-terminals.list").unlink()
        self.assertEqual(apps.inspect_apps(environment=self.environment)["selected"]["id"], "konsole")

    def test_helper_queries_do_not_launch_terminal(self):
        self.executable("blackbox-terminal")
        helper = self.executable("xdg-terminal-exec", native=False)
        response = SimpleNamespace(returncode=0, stdout="com.raggesilver.BlackBox.desktop\n")
        with patch.object(apps.subprocess, "run", side_effect=[SimpleNamespace(returncode=0, stdout="--print-id"), response]) as run:
            result = apps.inspect_apps(environment=self.environment)
        self.assertEqual(result["source"], "xdg")
        self.assertEqual(run.call_args.args[0], [str(helper), "--print-id"])
        with patch.object(apps.subprocess, "run", side_effect=subprocess.TimeoutExpired("helper", 2)):
            result = apps.inspect_apps(environment=self.environment)
        self.assertEqual(result["source"], "fallback")
        self.assertIn("xdg-unavailable", result["warnings"])

    def test_old_xdg_helper_never_receives_unrecognized_query(self):
        self.executable("konsole")
        helper = self.executable("xdg-terminal-exec", native=False)
        with patch.object(apps.subprocess, "run", return_value=SimpleNamespace(returncode=0, stdout="old helper")) as run:
            result = apps.inspect_apps(environment=self.environment)
        self.assertEqual(run.call_count, 1)
        self.assertEqual(run.call_args.args[0], [str(helper), "--help"])
        self.assertEqual(result["source"], "fallback")

    def test_relative_path_entries_are_not_searched(self):
        self.executable("konsole")
        self.environment["PATH"] = ".:relative:"
        with patch.object(apps.shutil, "which") as which:
            self.assertIsNone(apps.inspect_apps(environment=self.environment)["selected"])
        which.assert_not_called()

    def test_terminal_environment_is_not_a_shell_command(self):
        self.executable("konsole")
        self.environment["TERMINAL"] = "konsole; touch /tmp/not-allowed"
        self.assertEqual(apps.inspect_apps(environment=self.environment)["source"], "fallback")

    def test_all_adapters_preserve_argv(self):
        command = ["/path with spaces/python", "-I", "-m", "cyberlab_cli.main", "literal;not-a-shell", "$(not-executed)"]
        for identifier in apps.ADAPTERS:
            with self.subTest(identifier=identifier):
                argv = apps.launch_command({"id": identifier, "executable": "/native/" + identifier}, command)
                if identifier == "blackbox":
                    self.assertEqual(argv[1], "--command")
                    self.assertEqual(shlex.split(argv[2]), ["exec", *command])
                    continue
                if identifier == "tilix":
                    self.assertEqual(argv[1:3], ["--new-process", "-e"])
                    self.assertEqual(shlex.split(argv[3]), command)
                    continue
                self.assertEqual(argv[-len(command):], command)
                self.assertEqual(argv[1:-len(command)], list(apps.ADAPTERS[identifier][3]))

    def test_slot_validation(self):
        self.assertEqual(windows.terminal_slots(self.session, "client", 1), [["client", 1]])
        for session in ({**self.session, "id": "../bad"}, {**self.session, "state": "STOPPED"},
                        {**self.session, "terminal_slots": [["client", 1]]},
                        {**self.session, "terminals": ["client;uname"]}):
            with self.subTest(session=session), self.assertRaises(ValueError):
                windows.terminal_slots(session)
        with self.assertRaises(ValueError):
            windows.terminal_slots(self.session, "server", 1)

    def test_headless_never_spawns(self):
        environment = {**self.environment}
        environment.pop("WAYLAND_DISPLAY")
        with patch.dict(os.environ, environment, clear=True), patch.object(windows.subprocess, "Popen") as spawn, redirect_stderr(io.StringIO()):
            result = windows.launch_terminals(self.session, interactive=False)
        self.assertTrue(result["errors"])
        spawn.assert_not_called()

    def test_shared_launcher_zero_exit_and_tracking(self):
        self.executable("blackbox-terminal")
        captured = []
        def spawn(command, **kwargs):
            captured.append(command)
            self.assertNotIn("shell", kwargs)
            return SimpleNamespace(returncode=0, poll=lambda: 0)
        def tokens(*args):
            commands = [shlex.split(command[2])[1:] for command in captured]
            return {command[command.index("--window-token") + 1] for command in commands}
        with patch.dict(os.environ, self.environment, clear=True), patch.object(windows.subprocess, "Popen", side_effect=spawn), patch.object(windows, "attached_tokens", side_effect=tokens):
            result = windows.launch_terminals(self.session, True, interactive=False)
        self.assertEqual(result["attached"], 3)
        self.assertFalse(result["errors"])
        self.assertTrue(all("--test-session-bus" in shlex.split(command[2]) for command in captured))

    def test_blackbox_shell_quoting_is_literal(self):
        marker = self.root / "must-not-exist"
        arguments = ["value with spaces", "single'quote", 'double"quote', f'$(touch {marker})', f'; touch {marker}']
        command = [sys.executable, '-I', '-c', 'import json,sys; print(json.dumps(sys.argv[1:]))', *arguments]
        argv = apps.launch_command({"id": "blackbox", "executable": "/native/blackbox"}, command)
        response = subprocess.run(['/bin/sh', '-c', argv[2]], capture_output=True, text=True, check=True)
        self.assertEqual(json.loads(response.stdout), arguments)
        self.assertFalse(marker.exists())

    def test_launch_failure_keeps_session_and_attempts_other_slots(self):
        self.executable("konsole")
        with patch.dict(os.environ, self.environment, clear=True), patch.object(windows.subprocess, "Popen", side_effect=OSError("fixture failure")) as spawn:
            result = windows.launch_terminals(self.session, interactive=False)
        self.assertEqual(spawn.call_count, 3)
        self.assertEqual(len(result["errors"]), 3)
        self.assertEqual(self.session["state"], "RUNNING")

    def test_launcher_nonzero_and_missing_acknowledgement(self):
        self.executable("konsole")
        for code in (0, 7):
            with self.subTest(code=code), patch.dict(os.environ, self.environment, clear=True), \
                    patch.object(windows.subprocess, "Popen", return_value=SimpleNamespace(returncode=code, poll=lambda: code)), \
                    patch.object(windows, "attached_tokens", return_value=set()), \
                    patch.object(windows.time, "monotonic", side_effect=[0, 1, 6]), \
                    patch.object(windows.time, "sleep"):
                result = windows.launch_terminals(self.session, interactive=False)
            self.assertEqual(result["attached"], 0)
            self.assertTrue(result["errors"])
            self.assertIn("confirmed" if code == 0 else "code 7", result["errors"][0])
            self.assertEqual(self.session["state"], "RUNNING")

    def test_konsole_groups_quote_argv_and_sanitize_titles(self):
        self.executable("konsole")
        self.session["terminal_metadata"] = [["client", "group", "title\n;; command: bad"], ["server", "group", "server"]]
        captured = []
        def spawn(command, **kwargs):
            captured.append(command)
            return SimpleNamespace(returncode=0, poll=lambda: 0)
        def tokens(*args):
            token_ids = set()
            for path in Path(self.environment["XDG_RUNTIME_DIR"]).rglob("*.tabs"):
                lines = path.read_text().splitlines()
                self.assertEqual(len(lines), 3)
                for line in lines:
                    self.assertEqual(line.count(";; profile:"), 1)
                    profile = Path(line.split(";; profile: ", 1)[1])
                    self.assertEqual(profile.stat().st_mode & 0o777, 0o600)
                    encoded = profile.read_text().split("Command=", 1)[1].strip()
                    command = shlex.split(encoded)
                    token_ids.add(command[command.index("--window-token") + 1])
            return token_ids
        with patch.dict(os.environ, self.environment, clear=True), patch.object(windows.subprocess, "Popen", side_effect=spawn), patch.object(windows, "attached_tokens", side_effect=tokens):
            result = windows.launch_terminals(self.session, interactive=False)
        self.assertEqual(len(captured), 1)
        self.assertIn("--tabs-from-file", captured[0])
        self.assertEqual(result["attached"], 3)

    def test_stale_registry_never_signals_process(self):
        with patch.dict(os.environ, self.environment, clear=True):
            path = registry._path(self.session["id"])
            registry._write(path, [{"kind": "attachment", "pid": 12345, "start_time": 99,
                                   "node": "client", "slot": 0, "token": "b" * 32,
                                   "title": "title", "python": sys.executable}])
            with patch.object(registry, "_matches", return_value=False), patch.object(registry.os, "pidfd_open") as pidfd:
                self.assertEqual(registry.close_session(self.session["id"]), 0)
                pidfd.assert_not_called()

    def test_legacy_emulator_pid_never_authorizes_cleanup(self):
        with patch.dict(os.environ, self.environment, clear=True):
            path = registry._path(self.session["id"])
            registry._write(path, [{"pid": 12345, "pgid": 12345, "start_time": 99}])
            with patch.object(registry, "_matches", return_value=True), patch.object(registry.os, "pidfd_open") as pidfd:
                self.assertEqual(registry.close_session(self.session["id"]), 0)
                pidfd.assert_not_called()

    def test_cleanup_rechecks_identity_after_opening_pidfd(self):
        record = {"kind": "attachment", "pid": 12345, "start_time": 99,
                  "node": "client", "slot": 0, "token": "b" * 32,
                  "title": "title", "python": sys.executable}
        for belongs in (True, False):
            with self.subTest(belongs=belongs), patch.dict(os.environ, self.environment, clear=True):
                registry._write(registry._path(self.session["id"]), [record])
                with patch.object(registry, "_matches", return_value=True), \
                        patch.object(registry, "_belongs_to_session", return_value=belongs) as identity, \
                        patch.object(registry.os, "pidfd_open", side_effect=lambda pid: os.open("/dev/null", os.O_RDONLY)) as opened, \
                        patch.object(registry.signal, "pidfd_send_signal") as sent:
                    self.assertEqual(registry.close_session(self.session["id"]), int(belongs))
                opened.assert_called_once_with(12345)
                identity.assert_called_once_with(record, self.session["id"], False)
                self.assertEqual(sent.call_count, int(belongs))

    def test_attachment_identity_rejects_manual_shell_and_other_session(self):
        record = {"kind": "attachment", "pid": 12345, "start_time": 99, "node": "client", "slot": 0,
                  "token": "b" * 32, "title": "title", "python": sys.executable}
        command = registry.attachment_command(self.session["id"], "client", 0, record["token"], "title")
        encoded = b"\0".join(os.fsencode(part) for part in command) + b"\0"
        with patch.object(Path, "stat", return_value=SimpleNamespace(st_uid=os.geteuid())), patch.object(Path, "read_bytes", return_value=encoded), patch.object(registry.os.path, "samefile", return_value=True):
            self.assertTrue(registry._belongs_to_session(record, self.session["id"], False))
            self.assertFalse(registry._belongs_to_session(record, "c" * 32, False))
            self.assertFalse(registry._belongs_to_session(record, self.session["id"], True))
        with patch.object(Path, "stat", return_value=SimpleNamespace(st_uid=os.geteuid())), patch.object(Path, "read_bytes", return_value=b"/bin/bash\0"):
            self.assertFalse(registry._belongs_to_session(record, self.session["id"], False))

    def test_titles_do_not_undergo_emulator_variable_expansion(self):
        title = "Client $HOME ${USER} ' ; $(literal)"
        command = registry.attachment_command(self.session["id"], "client", 0, "b" * 32, title)
        encoded = command[command.index("--window-title") + 1]
        self.assertNotIn("$", encoded)
        self.assertEqual(registry.decode_title(encoded), title)
        for invalid in ("not-hex", "00", "ff", "a" * 1025):
            with self.subTest(invalid=invalid), self.assertRaises(ValueError):
                registry.decode_title(invalid)

    def test_cli_inventory_does_not_connect_to_dbus(self):
        from cyberlab_cli import main
        arguments = SimpleNamespace(command="terminal-apps", preferred=None)
        with patch.dict(os.environ, self.environment, clear=True), patch.object(main, "MessageBus") as bus:
            asyncio.run(main.run(arguments))
        bus.assert_not_called()

    def test_installer_fallback_across_distributions(self):
        for family in ("arch", "debian", "fedora", "suse"):
            for probe in (0, 1, 2):
                with self.subTest(family=family, probe=probe):
                    script = f'''
set -eu
source {shlex.quote(str(ROOT / "tools/install/packages.sh"))}
family={family}
configure_packages
native_terminals_present() {{ return {probe}; }}
package_available() {{ [[ $1 == xfce4-terminal ]]; }}
fail() {{ echo "$*" >&2; exit 1; }}
collect_terminal_package >/dev/null
printf '%s\\n' "${{host_packages[@]}}" "pending=$terminal_probe_pending"
'''
                    result = subprocess.run(["/bin/bash", "-c", script], text=True, capture_output=True, check=True)
                    packages = result.stdout.splitlines()
                    self.assertNotIn("konsole", packages)
                    if family == "debian":
                        self.assertIn("qml6-module-qt-labs-folderlistmodel", packages)
                    self.assertEqual("xfce4-terminal" in packages, probe == 1)
                    self.assertIn("pending=" + ("yes" if probe == 2 else "no"), packages)


if __name__ == "__main__":
    unittest.main(verbosity=2)
