#!/usr/bin/env python3
"""Isolated topic authoring and transport checks; never touches user data."""

import json
import argparse
import asyncio
from contextlib import redirect_stderr
from io import StringIO
from pathlib import Path
import tempfile
import unittest

from check_workstations import definition, validate_lab, LabValidationError, RuntimePolicy, UBUNTU_IMAGE
from cyberlab.authoring.service import Authoring
from cyberlabd.authoring import dispatch, bounded
from cyberlabd.server import lab_fields
from cyberlab_ipc import METHODS
from check_editing_drafts import drafts


class TopicChecks(unittest.TestCase):
    def setUp(self):
        temporary = tempfile.TemporaryDirectory(prefix="cyberlab-topics-")
        self.addCleanup(temporary.cleanup)
        self.root = Path(temporary.name)
        self.api = Authoring(self.root / "drafts.sqlite3", self.root / "catalog",
                             RuntimePolicy(frozenset({UBUNTU_IMAGE})))

    def snapshot(self, tags=None):
        document = definition()
        if tags is not None:
            document["metadata"]["tags"] = tags
        return self.api.store.clone("fixture", "Fixture", json.dumps(document), (), 1000)

    def test_catalog_has_twelve_unique_choices(self):
        choices = self.api.capabilities()["topic_catalog"]
        self.assertEqual(len(choices), 12)
        self.assertEqual(len({entry["id"] for entry in choices}), 12)
        self.assertTrue(all(entry["label"] for entry in choices))

    def test_creation_requires_topics_without_writing_a_draft(self):
        for tags in (None, [], ["unknown"], ["linux", "linux"], "linux"):
            with self.subTest(tags=tags), self.assertRaises(ValueError):
                self.api.create("fixture", "Fixture", 1000, tags=tags)
        self.assertEqual(self.api.list(1000), [])

    def test_create_and_transport_keep_tags(self):
        self.assertEqual(METHODS["CreateTaggedDraft"], ("ssass", "s"))
        body = ["fixture", "Fixture", ["linux", "networking"], "medium"]
        self.assertTrue(bounded("CreateTaggedDraft", body))
        result = json.loads(dispatch(self.api, "CreateTaggedDraft", body, 1000))
        self.assertEqual(json.loads(result["definition"])["metadata"]["tags"], body[2])
        with self.assertRaises(ValueError):
            dispatch(self.api, "CreateDraft", ["legacy", "Legacy"], 1000)
        self.assertFalse(bounded("CreateTaggedDraft", ["fixture", "Fixture", ["linux"] * 13]))

    def test_legacy_lab_loads_but_publication_requires_topics(self):
        lab = validate_lab(definition())
        self.assertEqual(lab.metadata.tags, ())
        snapshot = self.snapshot()
        report = self.api.validate(snapshot["id"], snapshot["revision"], 1000)
        self.assertFalse(report["valid"])
        self.assertEqual(report["issues"][0]["path"], "/metadata/tags")
        self.assertFalse(self.api.publish(snapshot["id"], snapshot["revision"], snapshot["digest"], 1000)["valid"])
        self.assertFalse((self.root / "catalog" / "fixture").exists())
        self.api.update_checker = lambda *_: self.fail("An untagged draft must not reach the catalog updater")
        updated = self.api.update_installed("fixture", snapshot["id"], snapshot["revision"], snapshot["digest"], "previous", 1000)
        self.assertFalse(updated["updated"])

    def test_cli_requires_tags_and_sends_them_to_shared_api(self):
        parser = argparse.ArgumentParser()
        drafts.add_parser(parser.add_subparsers(dest="command"))
        with redirect_stderr(StringIO()), self.assertRaises(SystemExit):
            parser.parse_args(["draft", "create", "fixture", "--title", "Fixture"])
        arguments = parser.parse_args(["draft", "create", "fixture", "--title", "Fixture", "--tag", "linux", "--tag", "networking", "--difficulty", "medium"])
        calls = []
        async def request(bus, method, body):
            calls.append((method, body))
            return dispatch(self.api, method, body, 1000)
        result = asyncio.run(drafts.run(None, request, arguments, None))
        self.assertEqual(calls, [("CreateTaggedDraft", ["fixture", "Fixture", ["linux", "networking"], "medium"])])
        self.assertEqual(json.loads(result["definition"])["metadata"]["tags"], ["linux", "networking"])

    def test_schema_rejects_unknown_duplicate_and_empty_tags(self):
        for tags in (["unknown"], ["linux", "linux"], [], "linux"):
            document = definition()
            document["metadata"]["tags"] = tags
            with self.subTest(tags=tags), self.assertRaises(LabValidationError):
                validate_lab(document)

    def test_library_fields_and_package_round_trip(self):
        snapshot = self.snapshot(["linux", "networking"])
        document = json.loads(snapshot["definition"])
        lab = validate_lab(document)
        fields = lab_fields(lab)
        self.assertEqual(fields["tags"].value, ["linux", "networking"])
        self.assertEqual(fields["tag_labels"].value["linux"], "Linux")
        self.api.catalog.mkdir()
        self.api.policy = RuntimePolicy(frozenset({UBUNTU_IMAGE}), workstation_images=frozenset({UBUNTU_IMAGE}))
        package = self.api.export_draft_package(snapshot["id"], snapshot["revision"], 1000)
        before = self.api.list(1000)
        imported = self.api.import_lab_package(package, "imported", "Imported", 1000)
        self.assertEqual(imported, {"installed": True, "lab_id": "imported", "edit_protected": False})
        metadata = json.loads((self.api.catalog / "imported" / "lab.yaml").read_text())["metadata"]
        self.assertEqual(metadata["tags"], ["linux", "networking"])
        self.assertEqual(self.api.list(1000), before)


if __name__ == "__main__":
    unittest.main()
