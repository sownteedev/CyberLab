#!/usr/bin/env python3
"""Validate the real QML-authored package using disposable engine fixtures."""

import argparse
import importlib.util
import json
import os
from pathlib import Path
import subprocess
import sys
import tempfile
import unittest

sys.dont_write_bytecode = True
ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "engine"))
spec = importlib.util.spec_from_file_location("cyberlab.schemas", ROOT / "schemas/__init__.py",
                                            submodule_search_locations=[str(ROOT / "schemas")])
sys.modules["cyberlab.schemas"] = importlib.util.module_from_spec(spec)
spec.loader.exec_module(sys.modules["cyberlab.schemas"])

from cyberlab.authoring.service import Authoring
from cyberlab.lab import load_lab
from cyberlab.lab.exchange import read_package
from cyberlab.policy import RuntimePolicy


class StartupAuthoringChecks(unittest.TestCase):
    package = None

    def setUp(self):
        temporary = tempfile.TemporaryDirectory(prefix="cyberlab-startup-authoring-")
        self.addCleanup(temporary.cleanup)
        self.root = Path(temporary.name)
        self.catalog = self.root / "catalog"
        self.catalog.mkdir()
        self.uid = os.getuid()
        self.api = Authoring(self.root / "drafts.sqlite", self.catalog,
                             RuntimePolicy(frozenset({"busybox:1.37.0"})))
        document = json.loads(self.package["definition"])
        self.lab_id = document["metadata"]["id"]
        document["metadata"]["tags"] = ["linux"]
        draft = self.api.create(self.lab_id, document["metadata"]["name"], self.uid, tags=["linux"])
        draft = self.api.put_assets(draft["id"], draft["revision"],
                                    [(path, text.encode()) for path, text in self.package["assets"].items()], self.uid)
        self.draft = self.api.save(draft["id"], draft["revision"], self.package["definition"], self.uid)

    def publish(self):
        report = self.api.validate(self.draft["id"], self.draft["revision"], self.uid)
        self.assertTrue(report["valid"], report)
        result = self.api.publish(self.draft["id"], self.draft["revision"], self.draft["digest"], self.uid)
        self.assertTrue(result["published"], result)
        return load_lab(self.catalog / self.lab_id / "lab.yaml")

    def test_qml_package_publishes_with_separate_startup_and_data(self):
        lab = self.publish()
        self.assertEqual(lab.nodes[0].command, ("/bin/sh", "start.sh"))
        seed = {entry.path: entry.data for entry in lab.nodes[0].seed}
        self.assertEqual(seed["input.txt"], b"data")
        self.assertEqual(seed["start.sh"], self.package["assets"]["assets/startup/client/start.sh"].encode())
        self.assertEqual(lab.documentation.content, "# Practice\n")
        self.assertEqual(sorted(path.relative_to(self.catalog / self.lab_id).as_posix()
                                for path in (self.catalog / self.lab_id).rglob("*") if path.is_file()),
                         sorted(["lab.yaml", *self.package["assets"]]))

    def test_export_import_retains_script_and_command(self):
        self.publish()
        archive = self.api.export_lab_package(self.lab_id, self.uid)
        definition, assets, _ = read_package(archive)
        self.assertEqual(json.loads(definition), json.loads(self.package["definition"]))
        self.assertEqual(dict(assets), {path: text.encode() for path, text in self.package["assets"].items()})
        imported = self.api.import_lab_package(archive, "imported", "Imported", self.uid)
        report = self.api.validate(imported["id"], imported["revision"], self.uid)
        self.assertTrue(report["valid"], report)

    def test_missing_referenced_script_blocks_publication(self):
        path = "assets/startup/client/start.sh"
        self.draft = self.api.remove_asset(self.draft["id"], self.draft["revision"], path, self.uid)
        result = self.api.publish(self.draft["id"], self.draft["revision"], self.draft["digest"], self.uid)
        self.assertFalse(result["published"])
        self.assertFalse((self.catalog / self.lab_id).exists())

    def test_known_fixture_script_runs_from_materialized_workspace(self):
        lab = self.publish()
        workspace = self.root / "workspace"
        workspace.mkdir()
        for entry in lab.nodes[0].seed:
            target = workspace / entry.path
            if entry.data is None:
                target.mkdir(parents=True, exist_ok=True)
            else:
                target.parent.mkdir(parents=True, exist_ok=True)
                target.write_bytes(entry.data)
        expected = "#!/bin/sh\nset -eu\nprintf ready > result.txt\n"
        self.assertEqual((workspace / "start.sh").read_text(), expected)
        subprocess.run(list(lab.nodes[0].command), cwd=workspace, check=True, timeout=5,
                       env={"PATH": "/usr/bin:/bin", "HOME": str(workspace)})
        self.assertEqual((workspace / "result.txt").read_text(), "ready")


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--qml-log", type=Path, required=True)
    arguments, remaining = parser.parse_known_args()
    marker = "STARTUP_AUTHORING_PACKAGE:"
    lines = [line.split(marker, 1)[1] for line in arguments.qml_log.read_text().splitlines() if marker in line]
    if len(lines) != 1:
        parser.error("Expected one package emitted by the editor startup test")
    StartupAuthoringChecks.package = json.loads(lines[0])
    unittest.main(argv=[sys.argv[0], *remaining])
