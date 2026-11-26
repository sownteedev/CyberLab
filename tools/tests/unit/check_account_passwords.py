#!/usr/bin/env python3
"""Account password pipeline checks; disposable drafts, no bus or catalog writes."""

import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).resolve().parents[3]))

import argparse
import asyncio
import io
import json
import os
import selectors
import signal
import subprocess
import tempfile
import time
import unittest
from unittest.mock import patch

from tools.tests.unit import check_editing_drafts as fixtures
from tools.tests.unit.check_editing_drafts import drafts, dispatch, METHODS
from cyberlab.authoring.store import DraftConflict, DraftNotFound
from cyberlabd.authoring import bounded
from cyberlab.policy import RuntimePolicy


class AccountPasswordChecks(unittest.TestCase):
    def test_capabilities_require_approved_ubuntu(self):
        image = "cyberlab/ubuntu:24.04-1"
        for approved in (False, True):
            self.api.policy = RuntimePolicy(frozenset({image}), workstation_images=frozenset({image}) if approved else frozenset())
            info = self.api.capabilities()
            self.assertEqual(info["machine_setup"], approved)
            self.assertEqual(info["machine_setup_version"], 1 if approved else 0)

    def setUp(self):
        fixtures.EditingDraftChecks.setUp(self)
        image = "cyberlab/ubuntu:24.04-1"
        self.api.policy = RuntimePolicy(frozenset({image}), workstation_images=frozenset({image}))
        self.draft = self.api.create("accounts", "Accounts", 1000, tags=["linux"])
        document = json.loads(self.draft["definition"])
        document["nodes"] = [{"id": "desktop", "image": "cyberlab/ubuntu:24.04-1",
                              "user": {"name": "student", "uid": 2000, "gid": 2000},
                              "setup": {"users": [{"name": "alice", "uid": 3000, "gid": 3000,
                                                    "password_hash": "!", "sudo": "disabled"}],
                                        "files": [], "home": []}}]
        self.draft = self.api.save(self.draft["id"], self.draft["revision"], json.dumps(document), 1000)

    def apply(self, account="student", action="replace", password="test-secret-123", uid=1000, revision=None):
        payload = {"account": account, "action": action}
        if action == "replace":
            payload["password"] = password
        return self.api.set_node_account_password(self.draft["id"], revision or self.draft["revision"],
                                                  "desktop", json.dumps(payload), uid)

    def test_owner_and_revision_checked_before_hashing(self):
        with patch("cyberlab.authoring.passwords.hash_password") as hashed:
            with self.assertRaises(DraftNotFound):
                self.apply(uid=9999)
            with self.assertRaises(DraftConflict):
                self.apply(revision=9999)
            hashed.assert_not_called()

    def test_main_password_and_extra_lock_preserve_other_fields(self):
        result = self.apply()
        node = json.loads(result["definition"])["nodes"][0]
        self.assertRegex(node["setup"]["password_hash"], r"^\$6\$[^$]+\$[./0-9A-Za-z]{86}$")
        self.assertNotIn("test-secret-123", json.dumps(result))
        self.assertEqual(node["setup"]["users"][0]["password_hash"], "!")
        self.assertEqual(node["user"]["uid"], 2000)
        self.draft = result
        locked = self.apply(account="alice", action="lock")
        self.assertEqual(json.loads(locked["definition"])["nodes"][0]["setup"]["users"][0]["password_hash"], "!")
        self.assertNotIn(b"test-secret-123", Path(self.api.store.database).read_bytes())

    def test_concurrent_edit_during_hash_never_overwrites_revision(self):
        def concurrent(password):
            self.api.save(self.draft["id"], self.draft["revision"], self.draft["definition"], 1000)
            return "!"
        with patch("cyberlab.authoring.passwords.hash_password", side_effect=concurrent):
            with self.assertRaises(DraftConflict):
                self.apply()
        current = self.api.get(self.draft["id"], 1000)
        self.assertEqual(current["revision"], self.draft["revision"] + 1)
        self.assertEqual(current["definition"], self.draft["definition"])

    def test_unapproved_image_rejected_before_hash(self):
        self.api.policy = RuntimePolicy(frozenset({"cyberlab/ubuntu:24.04-1"}))
        with patch("cyberlab.authoring.passwords.hash_password") as hashed:
            with self.assertRaises(ValueError):
                self.apply()
            hashed.assert_not_called()

    def test_password_boundaries_never_truncate(self):
        from cyberlab.authoring.passwords import hash_password
        for secret in ("é" * 64, "x" * 128):
            hashed = hash_password(secret)
            expected = subprocess.run(["/usr/bin/openssl", "passwd", "-6", "-salt", hashed.split("$")[2], "-stdin"],
                                      input=(secret + "\n").encode(), capture_output=True, check=True).stdout.decode().strip()
            self.assertEqual(hashed, expected)
        for secret in ("x" * 129, "é" * 65, "\ud800"):
            with self.assertRaises(ValueError):
                hash_password(secret)

    def test_random_salt_and_linux_compatibility(self):
        from cyberlab.authoring.passwords import hash_password
        first, second = hash_password("sample"), hash_password("sample")
        self.assertNotEqual(first, second)
        salt = first.split("$")[2]
        expected = subprocess.run(["/usr/bin/openssl", "passwd", "-6", "-salt", salt, "-stdin"],
                                  input="sample\n", text=True, capture_output=True, check=True).stdout.strip()
        self.assertEqual(first, expected)

    def test_hash_input_only_on_stdin_and_failure_is_sanitized(self):
        from cyberlab.authoring.passwords import hash_password
        with patch("cyberlab.authoring.passwords.subprocess.run", side_effect=RuntimeError("sensitive-value")) as run:
            with self.assertRaisesRegex(ValueError, "Password operation failed") as caught:
                hash_password("sensitive-value")
            self.assertNotIn("sensitive-value", str(caught.exception))
            self.assertNotIn("sensitive-value", repr(run.call_args.args))
            self.assertEqual(run.call_args.kwargs["input"], b"sensitive-value\n")

    def test_invalid_passwords_and_targets_do_not_write(self):
        for password in ("", "a\nb", "a\rb", "a\x00b", "x" * 1025, "é" * 513, None):
            with self.subTest(password_type=type(password).__name__):
                with self.assertRaises(ValueError):
                    self.apply(password=password)
        with self.assertRaises(ValueError):
            self.apply(account="missing")
        self.assertEqual(self.api.get(self.draft["id"], 1000), self.draft)

    def test_payload_parser_is_bounded_strict_and_sanitized(self):
        from cyberlab.authoring.passwords import parse_request
        for payload in ('{"password":"secret"', "[]", "null", "x" * 8193,
                        json.dumps({"account": "student", "action": "lock", "password": "secret"}),
                        '{"account":"student","action":"lock","action":"replace","password":"secret"}'):
            with self.assertRaises(ValueError) as caught:
                parse_request(payload)
            self.assertNotIn("secret", str(caught.exception))

    def test_daemon_contract_bounds_dispatch(self):
        self.assertEqual(METHODS["SetNodeAccountPassword"], ("suss", "s"))
        payload = json.dumps({"account": "student", "action": "lock"})
        body = [self.draft["id"], self.draft["revision"], "desktop", payload]
        self.assertTrue(bounded("SetNodeAccountPassword", body))
        self.assertFalse(bounded("SetNodeAccountPassword", body[:3] + ["x" * 8193]))
        result = json.loads(dispatch(self.api, "SetNodeAccountPassword", body, 1000))
        self.assertEqual(json.loads(result["definition"])["nodes"][0]["setup"]["password_hash"], "!")

    def test_cli_stdin_only_bounded_and_routes_same_operation(self):
        parser = argparse.ArgumentParser()
        drafts.add_parser(parser.add_subparsers(dest="command"))
        args = parser.parse_args(["draft", "account-password", self.draft["id"], "desktop", "--revision", "2"])
        payload = '{"account":"student","action":"replace","password":"private-value"}'
        with patch("sys.stdin", io.TextIOWrapper(io.BytesIO(payload.encode()))):
            prepared = drafts.prepare(args)
        calls = []
        async def request(bus, member, body):
            calls.append((member, body))
            return "{}"
        asyncio.run(drafts.run(None, request, args, prepared))
        self.assertEqual(calls, [("SetNodeAccountPassword", [self.draft["id"], 2, "desktop", payload])])
        for data in (b"x" * 8193, b"\xff", b'{"password":"private-value"'):
            with patch("sys.stdin", io.TextIOWrapper(io.BytesIO(data))):
                with self.assertRaises(ValueError) as caught:
                    drafts.prepare(args)
                self.assertNotIn("private-value", str(caught.exception))


class PasswordBusChecks(unittest.TestCase):
    def test_cli_private_bus_daemon_password_round_trip(self):
        processes = []
        try:
            with tempfile.TemporaryDirectory(prefix="cyberlab-password-bus-") as directory:
                root = Path(directory)
                (root / "catalog").mkdir()
                bus = subprocess.Popen(["dbus-daemon", "--session", "--nofork", "--print-address=1"],
                                       stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True, start_new_session=True)
                processes.append(bus)
                with selectors.DefaultSelector() as selector:
                    selector.register(bus.stdout, selectors.EVENT_READ)
                    self.assertTrue(selector.select(timeout=5), "Private bus did not start")
                environment = dict(os.environ, DBUS_SESSION_BUS_ADDRESS=bus.stdout.readline().strip(), PYTHONDONTWRITEBYTECODE="1")
                bootstrap = """from cyberlabd import main
from cyberlab.policy import RuntimePolicy
main.RuntimePolicy = lambda images, **kwargs: RuntimePolicy(images | {'cyberlab/ubuntu:24.04-1'}, workstation_images=frozenset({'cyberlab/ubuntu:24.04-1'}))
raise SystemExit(main.main())
"""
                with (root / "daemon.log").open("w") as log:
                    daemon = subprocess.Popen([sys.executable, "-I", "-B", "-c", bootstrap, "--test-session-bus", "--catalog", str(root / "catalog"),
                                               "--authoring-state", str(root / "drafts.sqlite")], env=environment, stdout=log,
                                              stderr=subprocess.STDOUT, start_new_session=True)
                    processes.append(daemon)

                    def cli(*arguments, payload=None, success=True):
                        result = subprocess.run([sys.executable, "-I", "-B", "-m", "cyberlab_cli.main", "--test-session-bus", *arguments],
                                                input=payload, text=True, capture_output=True, env=environment, timeout=15)
                        if success:
                            self.assertEqual(result.returncode, 0, result.stderr)
                        return result

                    for _ in range(50):
                        ready = cli("info", success=False)
                        if ready.returncode == 0:
                            break
                        if daemon.poll() is not None:
                            self.fail((root / "daemon.log").read_text())
                        time.sleep(0.05)
                    self.assertEqual(ready.returncode, 0, ready.stderr)
                    info = json.loads(cli("draft", "info").stdout)
                    self.assertTrue(info["machine_setup"])
                    draft = json.loads(cli("draft", "create", "account-check", "--title", "Accounts", "--tag", "linux", "--difficulty", "easy").stdout)
                    document = json.loads(draft["definition"])
                    document["nodes"] = [{"id": "desktop", "image": "cyberlab/ubuntu:24.04-1", "user": {
                        "name": "student", "uid": 2000, "gid": 2000, "home": "/home/student", "shell": "/bin/bash"},
                        "setup": {"users": [{"name": "alice", "uid": 3000, "gid": 3000}]}}]
                    draft = json.loads(cli("draft", "save", draft["id"], "-", "--revision", str(draft["revision"]), payload=json.dumps(document)).stdout)
                    secret = "isolated-password-fixture"
                    payload = json.dumps({"account": "student", "action": "replace", "password": secret})
                    result = cli("draft", "account-password", draft["id"], "desktop", "--revision", str(draft["revision"]), payload=payload)
                    self.assertNotIn(secret, result.stdout + result.stderr)
                    updated = json.loads(result.stdout)
                    self.assertEqual(updated["revision"], draft["revision"] + 1)
                    self.assertTrue(json.loads(updated["definition"])["nodes"][0]["setup"]["password_hash"].startswith("$6$"))
                    stale = cli("draft", "account-password", draft["id"], "desktop", "--revision", str(draft["revision"]), payload=payload, success=False)
                    self.assertNotEqual(stale.returncode, 0)
                    self.assertNotIn(secret, stale.stdout + stale.stderr)
                    invalid = cli("draft", "account-password", draft["id"], "desktop", "--revision", str(updated["revision"]),
                                  payload=json.dumps({"account": "missing", "action": "replace", "password": secret}), success=False)
                    self.assertNotEqual(invalid.returncode, 0)
                    self.assertNotIn(secret, invalid.stdout + invalid.stderr)
                    locked = json.loads(cli("draft", "account-password", draft["id"], "desktop", "--revision", str(updated["revision"]),
                                            payload=json.dumps({"account": "alice", "action": "lock"})).stdout)
                    self.assertEqual(json.loads(locked["definition"])["nodes"][0]["setup"]["users"][0]["password_hash"], "!")
                    self.assertNotIn(secret, (root / "daemon.log").read_text())
                    self.assertNotIn(secret.encode(), (root / "drafts.sqlite").read_bytes())
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
