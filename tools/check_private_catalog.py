#!/usr/bin/env python3
"""Private catalog and public API regressions using only temporary data."""
from io import BytesIO
import asyncio
import fcntl
from hashlib import sha256
import json
import os
from pathlib import Path
import stat
import subprocess
import tempfile
import unittest
from unittest.mock import patch
import zipfile

import check_edit_protection as protection_checks
from cyberlab.authoring.service import Authoring
from cyberlab.authoring.store import DraftConflict
from cyberlab.authoring.protection import EditLocked
from cyberlab.lab import load_lab
from cyberlab.lab.catalog import read_package
from cyberlab.lab.package import digest, load_snapshot
from cyberlab.policy import RuntimePolicy
from cyberlabd.authoring import dispatch
from cyberlabd.server import lab_fields, session_fields
from cyberlab.session import Session, SessionState


class PrivateCatalogChecks(unittest.TestCase):
    def test_private_bus_import_practice_export_and_edit_guards(self):
        from dbus_next.aio import MessageBus
        from cyberlab_cli.main import request, ClientError
        from cyberlab_ipc import BUS_NAME
        from cyberlab.service import Engine
        from cyberlabd.server import Server
        from cyberlabd.testing import MemoryRuntime

        package = self.archive(protected=True)

        async def exercise():
            process = subprocess.Popen(['dbus-daemon', '--session', '--nofork', '--print-address=1'], stdout=subprocess.PIPE, text=True)
            bus = client = server = None
            engine = Engine(self.catalog, self.api.policy, MemoryRuntime())
            try:
                address = process.stdout.readline().strip()
                bus = await MessageBus(bus_address=address).connect()
                await bus.request_name(BUS_NAME)
                lock = self.root / 'maintenance.lock'
                server = Server(bus, engine, {self.uid}, self.api, maintenance_path=lock)
                bus.add_message_handler(server.handle)
                client = await MessageBus(bus_address=address).connect()
                imported = json.loads(await request(client, 'ImportLabPackage', [package, 'received', 'Received']))
                self.assertTrue(imported['installed'])
                for method, body in [('EditLab', ['received']), ('CloneLab', ['received', 'cheat', 'Cheat'])]:
                    with self.assertRaisesRegex(ClientError, 'EditLocked'):
                        await request(client, method, body)
                exported = await request(client, 'ExportLabPackage', ['received'])
                from cyberlab.lab.exchange import read_package as decode
                self.assertIn('edit_protection', decode(exported)[2])
                with lock.open('rb') as maintenance:
                    fcntl.flock(maintenance.fileno(), fcntl.LOCK_EX)
                    with self.assertRaisesRegex(ClientError, 'Busy'):
                        await request(client, 'StartLab', ['received'])
                    self.assertEqual(await request(client, 'ListSessions', []), [])
                session = await request(client, 'StartLab', ['received'])
                self.assertEqual(session['state'], 'RUNNING')
                stopped = await request(client, 'StopSession', [session['id']])
                self.assertEqual(stopped['state'], 'STOPPED')
            finally:
                if server:
                    await server.shutdown()
                if client:
                    client.disconnect()
                    await client.wait_for_disconnect()
                if bus:
                    bus.disconnect()
                    await bus.wait_for_disconnect()
                process.terminate()
                process.wait(timeout=5)
                process.stdout.close()

        asyncio.run(asyncio.wait_for(exercise(), 20))

    def test_advertises_legacy_and_new_package_formats(self):
        capabilities = self.api.capabilities()
        self.assertEqual(capabilities['lab_package_format'], 'cyberlab-lab/v3')
        self.assertEqual(capabilities['lab_package_import_formats'], ['cyberlab-lab/v1', 'cyberlab-lab/v2', 'cyberlab-lab/v3'])

    def setUp(self):
        temporary = tempfile.TemporaryDirectory(prefix="cyberlab-private-catalog-")
        self.addCleanup(temporary.cleanup)
        self.root = Path(temporary.name)
        self.catalog = self.root / "system-labs"
        self.catalog.mkdir(mode=0o700)
        private_root = patch("cyberlab.authoring.updating.SYSTEM_CATALOG", self.catalog, create=True)
        private_root.start()
        self.addCleanup(private_root.stop)
        self.uid = os.getuid()
        self.api = Authoring(self.root / "drafts.db", self.catalog,
                             RuntimePolicy(allowed_images=frozenset({"busybox:1.36"})),
                             update_checker=lambda *args: None)

    def draft(self, lab_id="example", image="busybox:1.36"):
        draft = self.api.create(lab_id, "Example", self.uid, tags=["linux"])
        document = json.loads(draft["definition"])
        document["nodes"] = [{"id": "client", "image": image,
                              "command": ["sleep", "infinity"], "networks": []}]
        document["terminals"] = ["client"]
        draft = self.api.save(draft["id"], draft["revision"], json.dumps(document), self.uid)
        return self.api.put_assets(draft["id"], draft["revision"],
                                   [("assets/private/setup.sh", b"echo private\n")], self.uid)

    def archive(self, protected=False, image="busybox:1.36", legacy=None):
        draft = self.draft(image=image)
        if protected:
            self.api.protection.change("draft", draft["id"], "", "test passphrase", self.uid)
        snapshot = self.api.store.get(draft["id"], self.uid)
        verifier = self.api.protection.verifier("draft", draft["id"], self.uid)
        archive = self.api.export_draft_package(draft["id"], draft["revision"], self.uid)
        self.api.store.delete(draft["id"], self.uid, draft["revision"])
        self.api.protection.link("draft", draft["id"], None)
        if legacy:
            definition = snapshot["definition"].encode()
            assets = snapshot["assets"]
            manifest = {
                "format": "cyberlab-lab/" + legacy,
                "definition": {"path": "lab.yaml", "size": len(definition), "sha256": sha256(definition).hexdigest()},
                "lab": {"id": "example", "name": "Example", "version": "1.0.0"},
                "images": [image],
                "assets": [{"path": path, "kind": "file", "size": len(data), "sha256": sha256(data).hexdigest()}
                           for path, data in sorted(assets.items())],
                "content_digest": digest(snapshot["definition"], assets),
            }
            if verifier:
                manifest["edit_protection"] = verifier
            entries = {"manifest.json": json.dumps(manifest).encode(), "lab.yaml": definition, **assets}
            output = BytesIO()
            with zipfile.ZipFile(output, "w", zipfile.ZIP_DEFLATED) as destination:
                for name, data in entries.items():
                    destination.writestr(name, data)
            archive = output.getvalue()
        return archive

    def publish(self, draft):
        result = self.api.publish(draft["id"], draft["revision"], draft["digest"], self.uid)
        self.assertTrue(result["published"], result)

    def assert_private(self, directory):
        for entry in (directory, *directory.rglob("*")):
            with self.subTest(path=entry.relative_to(self.root)):
                self.assertEqual(stat.S_IMODE(entry.stat().st_mode), 0o700 if entry.is_dir() else 0o600)
                self.assertEqual(entry.stat().st_uid, os.geteuid())

    def test_publish_preserves_private_modes_and_never_chowns_to_caller(self):
        draft = self.draft()
        with patch("os.chown") as chown:
            self.publish(draft)
        self.assert_private(self.catalog)
        chown.assert_not_called()

    def test_update_preserves_private_modes_without_inheriting_legacy_owner(self):
        self.publish(self.draft())
        draft = self.api.edit_lab("example", self.uid)
        document = json.loads(draft["definition"])
        document["metadata"]["name"] = "Updated"
        draft = self.api.save(draft["id"], draft["revision"], json.dumps(document), self.uid)
        with patch("os.chown") as chown:
            result = self.api.update_installed("example", draft["id"], draft["revision"],
                                               draft["digest"], draft["origin"]["digest"], self.uid)
        self.assertTrue(result["updated"])
        self.assertEqual(load_lab(self.catalog / "example/lab.yaml").metadata.name, "Updated")
        self.assert_private(self.catalog)
        chown.assert_not_called()

    def test_legacy_catalog_modes_stay_compatible(self):
        legacy = self.root / "CyberLab-labs"
        legacy.mkdir(mode=0o775)
        original_mode = stat.S_IMODE(legacy.stat().st_mode)
        self.api.catalog = legacy
        self.publish(self.draft())
        draft = self.api.edit_lab("example", self.uid)
        self.api.update_installed("example", draft["id"], draft["revision"], draft["digest"],
                                  draft["origin"]["digest"], self.uid)
        self.assertEqual(stat.S_IMODE(legacy.stat().st_mode), original_mode)
        for entry in (legacy / "example", *(legacy / "example").rglob("*")):
            self.assertEqual(stat.S_IMODE(entry.stat().st_mode), 0o755 if entry.is_dir() else 0o644)

    def test_all_native_formats_install_without_retaining_drafts(self):
        for protected, legacy in ((False, None), (True, None), (False, "v1"), (True, "v2")):
            with self.subTest(protected=protected, legacy=legacy):
                archive = self.archive(protected, legacy=legacy)
                lab_id = "received-" + (legacy or "current") + ("-locked" if protected else "-open")
                result = json.loads(dispatch(self.api, "ImportLabPackage", [archive, lab_id, "Received"], self.uid))
                self.assertEqual(result, {"installed": True, "lab_id": lab_id, "edit_protected": protected})
                self.assertEqual(self.api.list(self.uid), [])
                self.assert_private(self.catalog / lab_id)
                if protected:
                    with self.assertRaises(EditLocked):
                        dispatch(self.api, "EditLab", [lab_id], self.uid)
                else:
                    self.assertIn("definition", json.loads(dispatch(self.api, "EditLab", [lab_id], self.uid)))
                    draft = self.api.list(self.uid)[0]
                    self.api.store.delete(draft["id"], self.uid, draft["revision"])

    def test_invalid_native_import_leaves_no_draft_or_catalog_entry(self):
        for protected in (False, True):
            with self.subTest(protected=protected):
                archive = self.archive(protected, image="forbidden:latest")
                with self.assertRaises(ValueError):
                    self.api.import_lab_package(archive, "invalid", "Invalid", self.uid)
                self.assertEqual(self.api.list(self.uid), [])
                self.assertEqual(list(self.catalog.iterdir()), [])

    def test_duplicate_ids_reject_without_overwriting_or_retaining_drafts(self):
        archive = self.archive()
        self.api.import_lab_package(archive, "received", "Received", self.uid)
        before = read_package(self.catalog, "received")
        with self.assertRaises(DraftConflict):
            self.api.import_lab_package(archive, "received", "Changed", self.uid)
        self.assertEqual(read_package(self.catalog, "received"), before)
        self.assertEqual(self.api.list(self.uid), [])

    def test_import_sync_failure_rolls_back_publication_and_protection(self):
        archive = self.archive(protected=True)
        real_fsync = os.fsync
        catalog_inode = self.catalog.stat().st_ino

        def fail_catalog_sync(descriptor):
            if os.fstat(descriptor).st_ino == catalog_inode:
                raise OSError("simulated catalog sync failure")
            real_fsync(descriptor)

        with patch("os.fsync", side_effect=fail_catalog_sync), self.assertRaises(OSError):
            self.api.import_lab_package(archive, "received", "Received", self.uid)
        self.assertEqual(list(self.catalog.iterdir()), [])
        self.assertEqual(self.api.list(self.uid), [])
        self.assertIsNone(self.api.protection.record("lab", "received", self.uid))

    def test_implicit_edit_resume_cannot_reveal_independently_locked_draft(self):
        self.publish(self.draft())
        draft = self.api.edit_lab("example", self.uid)
        self.api.protection.change("draft", draft["id"], "", "private draft", self.uid)
        for member, arguments in (("EditLab", ["example"]), ("ResolveLabDraft", ["example", "", False])):
            with self.subTest(member=member), self.assertRaises(EditLocked):
                dispatch(self.api, member, arguments, self.uid)
        listed = json.loads(dispatch(self.api, "ListDrafts", [], self.uid))
        protected = next(entry for entry in listed if entry["id"] == draft["id"])
        self.assertNotIn("definition", protected)
        self.assertNotIn("assets", protected)
        self.assertTrue(protected["edit_protected"])

    def test_public_practice_dtos_hide_checkwork_logic_but_keep_labels_and_quiz(self):
        draft = self.draft()
        snapshot = self.api.store.get(draft["id"], self.uid)
        document = json.loads(snapshot["definition"])
        document["assessment"] = {
            "results": [{"id": "probe", "node": "client", "path": "hidden-answer.txt",
                         "operator": "equals", "expected": "secret answer", "description": "Answer file"}],
            "goals": [{"id": "done", "type": "boolean", "expression": "probe", "description": "Task complete"}]}
        document["quizzes"] = [{"id": "quiz", "items": [
            {"id": "question", "type": "choice", "question": "Choose", "options": ["Yes", "No"], "answer": 0}]}]
        lab = load_snapshot({**snapshot, "definition": json.dumps(document)})
        session = Session("a" * 32, lab, self.uid, SessionState.RUNNING, "now", "now")
        for fields in (lab_fields(lab), session_fields(session)):
            assessment = json.loads(fields["assessment"].value)
            self.assertEqual(assessment["results"], [{"id": "probe", "node": "client", "description": "Answer file"}])
            self.assertEqual(assessment["goals"], [{"id": "done", "description": "Task complete"}])
            public = json.dumps({key: value.value for key, value in fields.items()})
            for private in ("hidden-answer.txt", "secret answer", "expression", "echo private"):
                self.assertNotIn(private, public)
            self.assertEqual(fields["terminals"].value, ["client"])
            quiz = json.loads(fields["quiz"].value)
            self.assertEqual(quiz[0]["question"], "Choose")
            self.assertNotIn("answer", quiz[0])


if __name__ == "__main__":
    unittest.main()
