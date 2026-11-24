#!/usr/bin/env python3
"""Isolated editing-draft reuse checks; no system bus, Docker or user catalog."""

import argparse
import asyncio
from concurrent.futures import ThreadPoolExecutor
import importlib.util
import json
import os
from pathlib import Path
import selectors
import signal
import sqlite3
import subprocess
import sys
import tempfile
import time
import unittest
from unittest.mock import patch

sys.dont_write_bytecode = True
ROOT = Path(__file__).resolve().parents[1]
sys.path[:0] = [str(ROOT / name) for name in ("engine", "daemon", "cli")]
spec = importlib.util.spec_from_file_location("cyberlab.schemas", ROOT / "schemas/__init__.py",
                                            submodule_search_locations=[str(ROOT / "schemas")])
sys.modules["cyberlab.schemas"] = importlib.util.module_from_spec(spec)
spec.loader.exec_module(sys.modules["cyberlab.schemas"])

from cyberlab.authoring.service import Authoring
from cyberlab.authoring.store import DraftConflict
from cyberlab.lab.catalog import read_package
from cyberlab.policy import RuntimePolicy
from cyberlab_cli import drafts
from cyberlabd.authoring import dispatch
from cyberlab_ipc import METHODS


class EditingDraftChecks(unittest.TestCase):
    def setUp(self):
        directory = tempfile.TemporaryDirectory(prefix="cyberlab-edit-reuse-")
        self.addCleanup(directory.cleanup)
        self.api = Authoring(Path(directory.name) / "drafts.sqlite3", Path(directory.name) / "catalog",
                             RuntimePolicy(frozenset({"busybox:1.37.0"})), update_checker=lambda *_: None)
        self.definition = json.dumps({"apiVersion": "cyberlab.ptit/v1", "kind": "Lab",
                                      "metadata": {"id": "example", "name": "Example", "version": "1.0.0"},
                                      "nodes": [], "networks": []})
        reader = patch("cyberlab.authoring.service.read_package", return_value=(self.definition, (), "old-catalog"))
        self.reader = reader.start()
        self.addCleanup(reader.stop)

    def test_repeated_edit_reuses_exact_saved_contents(self):
        first = self.api.edit_lab("example", 1000)
        edited = self.api.save(first["id"], first["revision"], self.definition.replace("Example", "Changed"), 1000)
        edited = self.api.put_assets(edited["id"], edited["revision"], [("assets/notes.txt", b"saved work")], 1000)
        for _ in range(3):
            self.assertEqual(self.api.edit_lab("example", 1000), edited)
        self.assertEqual(len(self.api.list(1000)), 1)

    def test_explicit_new_and_multiple_choice_do_not_modify_old_drafts(self):
        first = self.api.edit_lab("example", 1000)
        second = self.api.edit_lab("example", 1000, fresh=True)
        result = self.api.edit_lab("example", 1000)
        self.assertTrue(result["selection_required"])
        self.assertEqual({entry["id"] for entry in result["drafts"]}, {first["id"], second["id"]})
        self.assertEqual(self.api.edit_lab("example", 1000, draft_id=first["id"]), first)
        self.assertEqual(self.api.get(second["id"], 1000), second)
        self.assertEqual(len(self.api.list(1000)), 2)

    def test_reuse_preserves_stale_origin_for_update_conflict_checks(self):
        first = self.api.edit_lab("example", 1000)
        self.reader.return_value = self.definition, (), "new-catalog"
        self.assertEqual(self.api.edit_lab("example", 1000), first)
        second = self.api.edit_lab("example", 1000, fresh=True)
        result = self.api.edit_lab("example", 1000)
        states = {entry["id"]: entry["based_on_current"] for entry in result["drafts"]}
        self.assertEqual(states, {first["id"]: False, second["id"]: True})

    def test_candidates_are_owner_scoped_even_for_root(self):
        first = self.api.edit_lab("example", 1000)
        second = self.api.edit_lab("example", 1001)
        self.assertNotEqual(first["id"], second["id"])
        self.assertEqual(self.api.edit_lab("example", 1000), first)
        with self.assertRaises(DraftConflict):
            self.api.edit_lab("example", 1001, draft_id=first["id"])
        root = self.api.edit_lab("example", 0)
        self.assertEqual(root["owner"], 0)

    def test_renamed_and_unrelated_drafts_are_not_reused(self):
        first = self.api.edit_lab("example", 1000)
        self.api.save(first["id"], first["revision"], self.definition.replace('"example"', '"different"'), 1000)
        unrelated = self.api.create("example", "Unrelated", 1000, tags=["linux"])
        result = self.api.edit_lab("example", 1000)
        self.assertNotIn(result["id"], (first["id"], unrelated["id"]))

    def test_removed_choice_never_creates_replacement(self):
        first = self.api.edit_lab("example", 1000)
        self.api.store.delete(first["id"], 1000, first["revision"])
        with self.assertRaises(DraftConflict):
            self.api.edit_lab("example", 1000, draft_id=first["id"])
        self.assertEqual(self.api.list(1000), [])

    def test_concurrent_requests_create_only_one_draft(self):
        with ThreadPoolExecutor(max_workers=4) as pool:
            results = list(pool.map(lambda _: self.api.edit_lab("example", 1000), range(8)))
        self.assertEqual(len({result["id"] for result in results}), 1)
        self.assertEqual(len(self.api.list(1000)), 1)

    def test_reuse_works_at_owner_quota(self):
        first = self.api.edit_lab("example", 1000)
        for index in range(9):
            self.api.create("extra-" + str(index), "Other", 1000, tags=["linux"])
        self.assertEqual(self.api.edit_lab("example", 1000), first)

    def test_explicit_choices_are_mutually_exclusive(self):
        with self.assertRaises(ValueError):
            self.api.edit_lab("example", 1000, draft_id="a" * 32, fresh=True)

    def test_shared_dispatch_and_contract(self):
        self.assertEqual(METHODS["ResolveLabDraft"], ("ssb", "s"))
        first = json.loads(dispatch(self.api, "EditLab", ["example"], 1000))
        selected = json.loads(dispatch(self.api, "ResolveLabDraft", ["example", first["id"], False], 1000))
        self.assertEqual(first, selected)

    def test_cli_routes_default_choice_and_explicit_new(self):
        parser = argparse.ArgumentParser()
        drafts.add_parser(parser.add_subparsers(dest="command"))
        for extra, method, body in (([], "EditLab", ["example"]),
                                    (["--draft", "a" * 32], "ResolveLabDraft", ["example", "a" * 32, False]),
                                    (["--new"], "ResolveLabDraft", ["example", "", True])):
            arguments = parser.parse_args(["draft", "edit", "example", *extra])
            calls = []

            async def request(bus, member, values):
                calls.append((member, values))
                return '{"selection_required": true}'

            result = asyncio.run(drafts.run(None, request, arguments, None))
            self.assertTrue(result["selection_required"])
            self.assertEqual(calls, [(method, body)])

    def test_private_bus_cli_daemon_round_trip(self):
        root = Path(self.api.store.database).parent
        project = root / "catalog/example"
        project.mkdir(parents=True)
        definition = json.loads(self.definition)
        definition["nodes"] = [{"id": "client", "image": "busybox:1.37.0", "command": ["sleep", "3600"], "networks": []}]
        (project / "lab.yaml").write_text(json.dumps(definition))
        processes = []
        try:
            bus = subprocess.Popen(["dbus-daemon", "--session", "--nofork", "--print-address=1"],
                                   stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True, start_new_session=True)
            processes.append(bus)
            with selectors.DefaultSelector() as selector:
                selector.register(bus.stdout, selectors.EVENT_READ)
                self.assertTrue(selector.select(timeout=5), "Private bus did not start")
            environment = dict(os.environ, DBUS_SESSION_BUS_ADDRESS=bus.stdout.readline().strip(),
                               PYTHONDONTWRITEBYTECODE="1", PYTHONPATH=os.pathsep.join(str(ROOT / name) for name in ("engine", "daemon", "cli")))
            bootstrap = ("import importlib.util,sys; from pathlib import Path; "
                         f"root=Path({str(ROOT)!r}); "
                         "spec=importlib.util.spec_from_file_location('cyberlab.schemas',root/'schemas/__init__.py',submodule_search_locations=[str(root/'schemas')]); "
                         "sys.modules['cyberlab.schemas']=importlib.util.module_from_spec(spec); spec.loader.exec_module(sys.modules['cyberlab.schemas']); "
                         "from cyberlabd.main import main; raise SystemExit(main())")
            with (root / "daemon.log").open("w") as log:
                daemon = subprocess.Popen([sys.executable, "-B", "-c", bootstrap, "--test-session-bus", "--catalog", str(root / "catalog"),
                                           "--authoring-state", str(root / "bus-drafts.sqlite3")],
                                          env=environment, stdout=log, stderr=subprocess.STDOUT, start_new_session=True)
                processes.append(daemon)

                def cli(*arguments, check=True):
                    return subprocess.run([sys.executable, "-B", "-m", "cyberlab_cli.main", "--test-session-bus", *arguments],
                                          env=environment, capture_output=True, text=True, timeout=15, check=check)

                for _ in range(40):
                    ready = cli("info", check=False)
                    if ready.returncode == 0:
                        break
                    if daemon.poll() is not None:
                        self.fail((root / "daemon.log").read_text())
                    time.sleep(0.1)
                self.assertEqual(ready.returncode, 0, ready.stderr)
                first = json.loads(cli("draft", "edit", "example").stdout)
                again = json.loads(cli("draft", "edit", "example").stdout)
                self.assertEqual(first, again)
                second = json.loads(cli("draft", "edit", "example", "--new").stdout)
                choices = json.loads(cli("draft", "edit", "example").stdout)
                self.assertTrue(choices["selection_required"])
                self.assertEqual(len(choices["drafts"]), 2)
                selected = json.loads(cli("draft", "edit", "example", "--draft", second["id"]).stdout)
                self.assertEqual(selected, second)
                self.assertEqual(len(json.loads(cli("draft", "list").stdout)), 2)
                authored = json.loads(cli("draft", "create", "file-workspace", "--title", "File workspace", "--tag", "linux", "--difficulty", "easy").stdout)
                authored_definition = json.loads(authored["definition"])
                authored_definition["nodes"] = [{"id": "client", "image": "busybox:1.37.0", "command": ["/bin/sh", "scripts/hello.sh"],
                                                   "networks": [], "files": [{"source": "assets/client", "target": "."}]}]
                payload = {"definition": json.dumps(authored_definition), "entries": {
                    "assets/client/scripts/hello.sh": {"text": "#!/bin/sh\nprintf ready\n"},
                    "assets/client/empty": {"directory": True}, "assets/client/data.bin": {"bytes": "AP8="}}, "removals": []}
                payload_file = root / "workspace.json"
                payload_file.write_text(json.dumps(payload))
                saved = json.loads(cli("draft", "save-workspace", authored["id"], str(payload_file), "--revision", str(authored["revision"])).stdout)
                self.assertEqual(saved["revision"], authored["revision"] + 1)
                stale = cli("draft", "save-workspace", authored["id"], str(payload_file), "--revision", str(authored["revision"]), check=False)
                self.assertNotEqual(stale.returncode, 0)
                binary = json.loads(cli("draft", "asset", saved["id"], "assets/client/data.bin", "--revision", str(saved["revision"]), "--preview").stdout)
                self.assertFalse(binary["editable"])
                report = json.loads(cli("draft", "check", saved["id"], "--revision", str(saved["revision"])).stdout)
                self.assertTrue(report["valid"], report)
                published = json.loads(cli("draft", "publish", saved["id"], "--revision", str(saved["revision"]), "--digest", saved["digest"]).stdout)
                self.assertTrue(published["published"], published)
                self.assertEqual((root / "catalog/file-workspace/assets/client/scripts/hello.sh").read_text(), "#!/bin/sh\nprintf ready\n")
                self.assertTrue((root / "catalog/file-workspace/assets/client/empty").is_dir())
                imported = json.loads(cli("draft", "read-local", str(root / "catalog/file-workspace/assets/client"), "--folder").stdout)
                self.assertTrue(any(entry["path"] == "empty" and entry["kind"] == "directory" for entry in imported["resources"]))
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
                    if stream: stream.close()


class InstalledUpdateChecks(unittest.TestCase):
    def setUp(self):
        directory = tempfile.TemporaryDirectory(prefix="cyberlab-update-recovery-")
        self.addCleanup(directory.cleanup)
        self.root = Path(directory.name)
        catalog = self.root / "catalog"
        package = catalog / "example"
        package.mkdir(parents=True)
        (package / "lab.yaml").write_text(json.dumps({
            "apiVersion": "cyberlab.ptit/v1", "kind": "Lab",
            "metadata": {"id": "example", "name": "Original", "version": "1.0.0", "tags": ["linux"]},
            "nodes": [{"id": "client", "image": "busybox:1.37.0", "command": ["sleep", "infinity"], "networks": []}],
            "networks": [], "terminals": ["client"],
        }))
        self.api = Authoring(self.root / "drafts.sqlite3", catalog,
                             RuntimePolicy(frozenset({"busybox:1.37.0"})), update_checker=lambda *_: None)
        self.original = read_package(catalog, "example")
        draft = self.api.edit_lab("example", os.getuid())
        self.draft = self.api.save(draft["id"], draft["revision"], draft["definition"].replace("Original", "Updated"), os.getuid())

    def update(self):
        return self.api.update_installed("example", self.draft["id"], self.draft["revision"],
                                         self.draft["digest"], self.original[2], os.getuid())

    def test_origin_storage_failure_rolls_back_catalog_and_allows_retry(self):
        before = self.api.get(self.draft["id"], os.getuid())
        with self.api.store.transaction() as connection:
            connection.execute("""
                CREATE TRIGGER fail_origin_write BEFORE INSERT ON origins
                BEGIN SELECT RAISE(ABORT, 'injected storage failure'); END
            """)
        with self.assertRaises(sqlite3.IntegrityError):
            self.update()
        self.assertEqual(read_package(self.api.catalog, "example"), self.original)
        self.assertEqual(self.api.get(self.draft["id"], os.getuid()), before)
        backups = list(self.api.catalog.glob(".cyberlab-update-*"))
        self.assertEqual(len(backups), 1)
        self.assertEqual((backups[0] / "lab.yaml").read_text(), self.draft["definition"])
        with self.api.store.transaction() as connection:
            connection.execute("DROP TRIGGER fail_origin_write")
        result = self.update()
        self.assertTrue(result["updated"])
        self.assertEqual(read_package(self.api.catalog, "example")[2], result["catalog_digest"])
        updated = self.api.get(self.draft["id"], os.getuid())
        self.assertEqual(updated["origin"], {"lab_id": "example", "digest": result["catalog_digest"]})

    def test_external_catalog_change_is_never_replaced(self):
        definition = self.api.catalog / "example/lab.yaml"
        definition.write_text(definition.read_text().replace("Original", "External"))
        changed = read_package(self.api.catalog, "example")
        with self.assertRaises(DraftConflict):
            self.update()
        self.assertEqual(read_package(self.api.catalog, "example"), changed)
        self.assertEqual(self.api.get(self.draft["id"], os.getuid())["origin"]["digest"], self.original[2])

    def assert_rollback_preserves_concurrent_edit(self, contents):
        definition = self.api.catalog / "example/lab.yaml"

        def fail_after_external_edit(*arguments):
            definition.write_text(contents)
            raise sqlite3.OperationalError("database full")

        with patch.object(self.api.store, "set_origin", side_effect=fail_after_external_edit):
            with self.assertRaises(DraftConflict):
                self.update()
        self.assertEqual(definition.read_text(), contents)
        backups = list(self.api.catalog.glob(".cyberlab-update-*"))
        self.assertEqual(len(backups), 1)
        self.assertEqual((backups[0] / "lab.yaml").read_text(), self.original[0])
        self.assertEqual(self.api.get(self.draft["id"], os.getuid())["origin"]["digest"], self.original[2])

    def test_rollback_preserves_concurrent_catalog_edit(self):
        self.assert_rollback_preserves_concurrent_edit(self.draft["definition"].replace("Updated", "External"))

    def test_rollback_preserves_concurrent_invalid_catalog_edit(self):
        self.assert_rollback_preserves_concurrent_edit("unfinished: [")


if __name__ == "__main__":
    unittest.main()
