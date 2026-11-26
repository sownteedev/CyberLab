#!/usr/bin/env python3
"""Editing authorization checks using disposable databases and catalogs."""
import importlib.util
import json
from pathlib import Path
import sys
import tempfile
import unittest
from unittest.mock import patch

ROOT = Path(__file__).resolve().parents[3]
sys.path[:0] = [str(ROOT / name) for name in ("engine", "daemon", "cli")]
spec = importlib.util.spec_from_file_location("cyberlab.schemas", ROOT / "schemas/__init__.py", submodule_search_locations=[str(ROOT / "schemas")])
sys.modules["cyberlab.schemas"] = importlib.util.module_from_spec(spec)
spec.loader.exec_module(sys.modules["cyberlab.schemas"])

from cyberlab.authoring.service import Authoring
from cyberlab.authoring.protection import EditLocked, EditPassword
from cyberlab.policy import RuntimePolicy
from cyberlabd.authoring import dispatch
from cyberlab_ipc.editing import encode, decode
from cyberlab.lab.exchange import read_package


class ProtectionChecks(unittest.TestCase):
    def setUp(self):
        self.temporary = tempfile.TemporaryDirectory(prefix="cyberlab-edit-lock-")
        self.addCleanup(self.temporary.cleanup)
        self.root = Path(self.temporary.name)
        self.catalog = self.root / "catalog"
        self.catalog.mkdir()
        self.api = Authoring(self.root / "drafts.db", self.catalog, RuntimePolicy(allowed_images=frozenset({"busybox:1.36"})), update_checker=lambda *args: None)
        self.draft = self.api.create("example", "Example", 1000, tags=["linux"], difficulty="medium")

    def call(self, member, body, token="", uid=1000):
        if token:
            result = dispatch(self.api, "ProtectedAuthoring", [token, member, encode(body)], uid)
            return decode(result)["value"]
        return dispatch(self.api, member, body, uid)

    def protect(self):
        return json.loads(self.call("SetEditPassword", ["draft", self.draft["id"], "", "secret passphrase"]))["token"]

    def publish(self, token=""):
        document = json.loads(self.draft["definition"])
        document["nodes"] = [{"id": "client", "image": "busybox:1.36", "command": ["sleep", "infinity"], "networks": []}]
        document["terminals"] = ["client"]
        self.draft = self.api.save(self.draft["id"], self.draft["revision"], json.dumps(document), 1000)
        result = json.loads(self.call("PublishDraft", [self.draft["id"], self.draft["revision"], self.draft["digest"]], token))
        self.assertTrue(result["published"], result)

    def test_protected_exchange_imports_installed_and_stays_locked(self):
        token = self.protect()
        self.publish(token)
        archive = self.call("ExportLabPackage", ["example"])
        definition, assets, manifest = read_package(archive)
        self.assertEqual(manifest["format"], "cyberlab-lab/v3")
        self.assertNotIn("secret passphrase", archive.decode("latin1"))
        catalog = self.root / "recipient"
        catalog.mkdir()
        recipient = Authoring(self.root / "recipient.db", catalog, self.api.policy, update_checker=lambda *args: None)
        result = json.loads(dispatch(recipient, "ImportLabPackage", [archive, "received", "Received"], 1001))
        self.assertEqual(result, {"installed": True, "lab_id": "received", "edit_protected": True})
        self.assertEqual(recipient.list(1001), [])
        self.assertTrue((catalog / "received" / "lab.yaml").is_file())
        for member, body in [("EditLab", ["received"]), ("CloneLab", ["received", "copy", "Copy"])]:
            with self.subTest(member=member), self.assertRaises(EditLocked):
                dispatch(recipient, member, body, 1001)
        unlocked = json.loads(dispatch(recipient, "UnlockEditing", ["lab", "received", "secret passphrase"], 1001))
        opened = decode(dispatch(recipient, "ProtectedAuthoring", [unlocked["token"], "EditLab", encode(["received"])], 1001))["value"]
        self.assertTrue(json.loads(opened)["edit_protected"])

    def test_existing_drafts_cannot_bypass_later_lab_lock_or_lab_removal(self):
        self.publish()
        draft = self.api.edit_lab("example", 1000)
        self.call("SetEditPassword", ["lab", "example", "", "locked later"])
        with self.assertRaises(EditLocked):
            self.call("GetDraft", [draft["id"]])
        self.api.protection.link("lab", "example", None)
        with self.assertRaises(EditLocked):
            self.call("GetDraft", [draft["id"]])

    def test_cloned_protection_is_independent_and_password_change_does_not_unlock_source(self):
        token = self.protect()
        self.publish(token)
        clone = json.loads(self.call("CloneLab", ["example", "copy", "Copy"], token))
        self.assertTrue(clone["edit_token"])
        self.call("SetEditPassword", ["draft", clone["id"], "secret passphrase", ""])
        self.call("GetDraft", [clone["id"]])
        with self.assertRaises(EditLocked):
            self.call("EditLab", ["example"])

    def test_software_job_paths_cannot_bypass_draft_lock(self):
        self.protect()
        from unittest.mock import Mock
        self.api.software = Mock()
        self.api.software.get.return_value = {"draft": self.draft["id"]}
        for member in ("GetSoftwareJob", "ApplySoftwareJob", "CancelSoftwareJob"):
            with self.subTest(member=member), self.assertRaises(EditLocked):
                self.call(member, ["job"])
        self.api.software.apply.assert_not_called()

    def test_unprotected_exchange_installs_v3_and_remains_editable(self):
        self.publish()
        archive = self.call("ExportLabPackage", ["example"])
        self.assertEqual(read_package(archive)[2]["format"], "cyberlab-lab/v3")
        imported = json.loads(self.call("ImportLabPackage", [archive, "copy", "Copy"]))
        self.assertEqual(imported, {"installed": True, "lab_id": "copy", "edit_protected": False})
        self.assertIn("definition", json.loads(self.call("EditLab", ["copy"])))

    def test_invalid_protected_import_does_not_leave_editable_draft(self):
        token = self.protect()
        self.publish(token)
        archive = self.call("ExportLabPackage", ["example"])
        before = self.api.list(1000)
        with patch.object(self.api, "publish", return_value={"published": False}), self.assertRaises(ValueError):
            self.call("ImportLabPackage", [archive, "bad", "Bad"])
        self.assertEqual(self.api.list(1000), before)
        self.assertFalse((self.catalog / "bad").exists())

    def test_locked_draft_rejects_read_write_export_and_delete(self):
        token = self.protect()
        identifier, revision = self.draft["id"], self.draft["revision"]
        operations = [("GetDraft", [identifier]), ("SaveDraft", [identifier, revision, self.draft["definition"]]), ("ExportDraftPackage", [identifier, revision]), ("DeleteDraft", [identifier, revision]), ("GetDraftAsset", [identifier, revision, "assets/test.txt"])]
        for member, body in operations:
            with self.subTest(member=member), self.assertRaises(EditLocked):
                self.call(member, body)
        self.assertEqual(json.loads(self.call("GetDraft", [identifier], token))["id"], identifier)

    def test_wrong_password_and_uid_and_resource_scope(self):
        token = self.protect()
        with self.assertRaises(EditPassword):
            self.call("UnlockEditing", ["draft", self.draft["id"], "incorrect"])
        with self.assertRaises(Exception):
            self.call("GetDraft", [self.draft["id"]], token, 1001)
        other = self.api.create("other", "Other", 1000, tags=["linux"])
        self.call("SetEditPassword", ["draft", other["id"], "", "another passphrase"])
        with self.assertRaises(EditLocked):
            self.call("GetDraft", [other["id"]], token)

    def test_password_rotation_revoke_restart_preserve_work(self):
        token = self.protect()
        body = ["draft", self.draft["id"], "secret passphrase", "replacement password"]
        replacement = json.loads(self.call("SetEditPassword", body))["token"]
        with self.assertRaises(EditLocked):
            self.call("GetDraft", [self.draft["id"]], token)
        self.assertTrue(self.call("RevokeEditing", [replacement]))
        with self.assertRaises(EditLocked):
            self.call("GetDraft", [self.draft["id"]], replacement)
        self.api = Authoring(self.root / "drafts.db", self.catalog, self.api.policy)
        with self.assertRaises(EditLocked):
            self.call("GetDraft", [self.draft["id"]])
        self.assertEqual(self.api.store.get(self.draft["id"], 1000)["definition"], self.draft["definition"])
        with self.assertRaises(EditPassword):
            self.call("SetEditPassword", ["draft", self.draft["id"], "", ""])

    def test_wrapper_rejects_recursive_and_unknown_methods(self):
        for member in ("ProtectedAuthoring", "DeleteLab", "UnlockEditing", "Nonexistent"):
            with self.subTest(member=member), self.assertRaises(ValueError):
                self.call("ProtectedAuthoring", ["", member, "[]"])


if __name__ == "__main__":
    unittest.main()
