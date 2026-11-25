#!/usr/bin/env python3
"""Isolated difficulty validation and package persistence checks."""

import json
from pathlib import Path
import tempfile
import unittest

from check_workstations import definition, validate_lab, LabValidationError, RuntimePolicy, UBUNTU_IMAGE
from cyberlab.assessment import lab_digest
from cyberlab.authoring.service import Authoring
from cyberlab.lab.exchange import create_package, read_package


class DifficultyChecks(unittest.TestCase):
    def test_absence_remains_unclassified_and_keeps_legacy_digest(self):
        document = definition()
        lab = validate_lab(document)
        self.assertIsNone(lab.metadata.difficulty)
        self.assertNotIn("difficulty", document["metadata"])
        self.assertEqual(lab_digest(lab), "5db8fd4a83fc14313553743c76a45b29e1ea5981e584ba2cd8fbe388ab4c19cd")

    def test_valid_values_load_and_affect_digest(self):
        digests = {lab_digest(validate_lab(definition()))}
        for difficulty in ("easy", "medium", "hard"):
            with self.subTest(difficulty=difficulty):
                document = definition()
                document["metadata"]["difficulty"] = difficulty
                lab = validate_lab(document)
                self.assertEqual(lab.metadata.difficulty, difficulty)
                digests.add(lab_digest(lab))
        self.assertEqual(len(digests), 4)

    def test_invalid_values_are_rejected_at_metadata_path(self):
        for difficulty in (None, "", "Easy", " easy", "hard ", "unclassified", "expert", 1, True, [], {}):
            document = definition()
            document["metadata"]["difficulty"] = difficulty
            with self.subTest(difficulty=difficulty), self.assertRaisesRegex(LabValidationError, "/metadata/difficulty"):
                validate_lab(document)

    def test_package_round_trip_preserves_explicit_and_absent_values(self):
        for difficulty in (None, "easy", "medium", "hard"):
            with self.subTest(difficulty=difficulty):
                document = definition()
                if difficulty is not None:
                    document["metadata"]["difficulty"] = difficulty
                source = json.dumps(document)
                lab = validate_lab(document)
                restored, assets, manifest = read_package(create_package(source, {}, lab))
                self.assertEqual(restored, source)
                self.assertEqual(assets, {})
                self.assertEqual(validate_lab(json.loads(restored)).metadata.difficulty, difficulty)

    def test_draft_export_import_preserves_difficulty(self):
        with tempfile.TemporaryDirectory(prefix="cyberlab-difficulty-") as directory:
            root = Path(directory)
            catalog = root / "catalog"
            catalog.mkdir()
            api = Authoring(root / "drafts.sqlite3", catalog,
                            RuntimePolicy(frozenset({UBUNTU_IMAGE}), workstation_images=frozenset({UBUNTU_IMAGE})))
            for difficulty in (None, "easy", "medium", "hard"):
                with self.subTest(difficulty=difficulty):
                    document = definition()
                    document["metadata"]["tags"] = ["linux"]
                    if difficulty is not None:
                        document["metadata"]["difficulty"] = difficulty
                    snapshot = api.store.clone("fixture", "Fixture", json.dumps(document), (), 1000)
                    package = api.export_draft_package(snapshot["id"], snapshot["revision"], 1000)
                    lab_id = "copy-" + (difficulty or "unset")
                    before = api.list(1000)
                    imported = api.import_lab_package(package, lab_id, "Copy", 1000)
                    self.assertEqual(imported, {"installed": True, "lab_id": lab_id, "edit_protected": False})
                    metadata = json.loads((catalog / lab_id / "lab.yaml").read_text())["metadata"]
                    self.assertEqual(api.list(1000), before)
                    self.assertEqual(metadata.get("difficulty"), difficulty)
                    if difficulty is None:
                        self.assertNotIn("difficulty", metadata)


if __name__ == "__main__":
    unittest.main()
