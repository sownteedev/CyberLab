#!/usr/bin/env python3
"""Atomic draft workspace checks using disposable data only."""

import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).resolve().parents[3]))

import argparse
import base64
import asyncio
import json
import unittest
import os
import tempfile

from tools.tests.unit.check_editing_drafts import EditingDraftChecks, DraftConflict, drafts, dispatch, METHODS


class FileEditorChecks(unittest.TestCase):
    def test_large_binary_import_save_export_and_reload(self):
        from cyberlab.lab import exchange
        from cyberlab.lab.models import SeedEntry
        from cyberlab.lab.assets import validate_seed
        from types import SimpleNamespace
        data = b"\x89PNG\r\n\x1a\n" + os.urandom(2 * 1024 * 1024)
        with tempfile.TemporaryDirectory() as directory:
            source = Path(directory) / 'diagram.png'
            source.write_bytes(data)
            for folder in (False, True):
                result = drafts.prepare(argparse.Namespace(draft_action='read-local',
                    source=directory if folder else str(source), folder=folder))
                resource = next(item for item in result if item['path'] == 'diagram.png')
                self.assertEqual(base64.b64decode(resource['content']['bytes']), data)
            saved = self.apply({'assets/diagram.png': resource['content']})
            snapshot = self.api.store.get(saved['id'], 1000)
            validate_seed([SeedEntry('diagram.png', data)])
            encoded = exchange.create_package(snapshot['definition'], snapshot['assets'],
                SimpleNamespace(metadata=SimpleNamespace(id='file-editor', name='File editor', version='1'), nodes=[]))
            decoded = exchange.read_package(encoded)
            self.assertEqual(decoded[1]['assets/diagram.png'], data)

    def test_local_input_errors_distinguish_size_and_links(self):
        with tempfile.TemporaryDirectory() as directory:
            source = Path(directory) / 'data.bin'
            source.write_bytes(b'12345')
            with self.assertRaisesRegex(ValueError, 'exceeds the byte limit'):
                drafts.read_file(source, 4)
            link = Path(directory) / 'alias.bin'
            link.symlink_to(source)
            with self.assertRaisesRegex(ValueError, 'symbolic link'):
                drafts.read_file(link, 8)
            link.unlink()
            os.link(source, link)
            with self.assertRaisesRegex(ValueError, 'hardlinks'):
                drafts.read_file(source, 8)

    def setUp(self):
        EditingDraftChecks.setUp(self)
        self.draft = self.api.create("file-editor", "File editor", 1000, tags=["linux"])
        self.draft = self.api.put_assets(self.draft["id"], self.draft["revision"],
                                        [("assets/original", b"\x00binary")], 1000)

    def apply(self, entries, removals=(), revision=None):
        payload = json.dumps({"definition": self.draft["definition"], "entries": entries,
                              "removals": list(removals)})
        return self.api.save_workspace(self.draft["id"], revision or self.draft["revision"], payload, 1000)

    def test_atomic_copy_directory_and_text(self):
        result = self.apply({"assets/new/bin": {"copy": "assets/original"},
                             "assets/new/empty": {"directory": True},
                             "assets/new/hello.sh": {"text": "echo hello\n"}}, ["assets/original"])
        self.assertEqual(result["revision"], self.draft["revision"] + 1)
        snapshot = self.api.store.get(result["id"], 1000)
        self.assertEqual(snapshot["assets"], {"assets/new/bin": b"\x00binary",
                         "assets/new/empty": None, "assets/new/hello.sh": b"echo hello\n"})

    def test_failure_rolls_back_everything(self):
        for entries in ({"assets/new": {"text": "ok"}, "../escape": {"text": "bad"}},
                        {"assets/new": {"copy": "assets/missing"}},
                        {"assets/new": {"text": "a" * (65536 + 1)}},
                        {"assets/new": {"directory": False}},
                        {"assets/new": {"text": "ok", "copy": "assets/original"}}):
            with self.subTest(entries=list(entries)):
                with self.assertRaises(Exception):
                    self.apply(entries, ["assets/original"])
                self.assertEqual(self.api.get(self.draft["id"], 1000), self.draft)

    def test_stale_revision_and_owner(self):
        self.apply({"assets/new": {"text": "ok"}})
        with self.assertRaises(DraftConflict):
            self.apply({"assets/new": {"text": "stale"}})
        with self.assertRaises(Exception):
            self.api.save_workspace(self.draft["id"], self.draft["revision"], "{}", 2000)

    def test_contract_cli_and_dispatch(self):
        self.assertEqual(METHODS["SaveDraftWorkspace"], ("sus", "s"))
        payload = json.dumps({"definition": self.draft["definition"], "entries": {}, "removals": []})
        result = json.loads(dispatch(self.api, "SaveDraftWorkspace",
                                   [self.draft["id"], self.draft["revision"], payload], 1000))
        self.assertEqual(result["revision"], self.draft["revision"] + 1)
        parser = argparse.ArgumentParser()
        drafts.add_parser(parser.add_subparsers(dest="command"))
        args = parser.parse_args(["draft", "save-workspace", self.draft["id"], "-", "--revision", "4"])
        calls = []
        async def request(bus, member, body):
            calls.append((member, body))
            return "{}"
        asyncio.run(drafts.run(None, request, args, payload))
        self.assertEqual(calls, [("SaveDraftWorkspace", [self.draft["id"], 4, payload])])

    def test_binary_import_and_invalid_encoding_are_atomic(self):
        data = b"\x00\xffbinary"
        result = self.apply({"assets/imported": {"bytes": base64.b64encode(data).decode()}})
        self.assertEqual(self.api.asset(result["id"], result["revision"], "assets/imported", 1000), data)
        with self.assertRaises(ValueError):
            self.apply({"assets/imported": {"bytes": "@@@"}}, revision=result["revision"])
        self.assertEqual(self.api.get(result["id"], 1000)["revision"], result["revision"])

    def test_local_folder_retains_empty_directories(self):
        import tempfile
        from pathlib import Path
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            (root / "empty").mkdir()
            (root / "binary").write_bytes(b"\x00\xff")
            result = drafts.prepare(argparse.Namespace(draft_action="read-local", source=directory, folder=True))
            self.assertTrue(any(entry["path"] == "empty" and entry["content"] == {"directory": True} for entry in result))
            self.assertTrue(any(entry["path"] == "binary" and "bytes" in entry["content"] for entry in result))
            (root / "link").symlink_to(root / "binary")
            with self.assertRaises(ValueError):
                drafts.prepare(argparse.Namespace(draft_action="read-local", source=directory, folder=True))


if __name__ == "__main__":
    unittest.main()
