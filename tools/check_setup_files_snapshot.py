"""Validate file-UI model output through snapshot loading without Docker or D-Bus."""

import json
from pathlib import Path
import subprocess
import unittest

from check_workstations import definition
from cyberlab.lab.package import load_snapshot
from cyberlab.runtime.machine_setup import setup_payload


class SetupFilesSnapshotChecks(unittest.TestCase):
    def test_ui_directory_child_override_rename_delete_snapshot(self):
        root = Path(__file__).resolve().parents[1]
        script = r"""
const fs = require('node:fs');
const vm = require('node:vm');
const model = vm.createContext({});
vm.runInContext(fs.readFileSync('ui/studio/models/DraftFiles.js', 'utf8').replace('.pragma library', ''), model);
const document = JSON.parse(fs.readFileSync(0, 'utf8'));
document.nodes[0].files = [{source: 'assets/home', target: '.'}];
document.nodes[0].setup = {files: [{source: 'assets/home', target: '/srv/project', owner: 'root', group: 'root', mode: '2770'}]};
let state = model.initial(document, [{path: 'assets/home', kind: 'directory'}, {path: 'assets/home/notes.py', kind: 'file'}]);
state = model.properties(state, 'client', '/srv/project/notes.py', {owner: 'student', group: 'student', mode: '0600'});
const snapshots = [state];
state = model.privateSystem(state, 'client');
state = model.create(state, 'client', '/etc/demo.conf', false);
state = model.properties(state, 'client', 'notes.py', {owner: 'student', group: 'student', mode: '0640'});
snapshots.push(state);
state = model.rename(state, 'client', '/srv/project', 'renamed');
snapshots.push(state);
state = model.remove(state, 'client', '/srv/renamed/notes.py');
snapshots.push(state);
console.log(JSON.stringify(snapshots));
"""
        result = subprocess.run(["node", "-e", script], input=json.dumps(definition()),
                                cwd=root, text=True, capture_output=True, check=True)
        original = {"assets/home": None, "assets/home/notes.py": b"print(1)\n"}
        for index, state in enumerate(json.loads(result.stdout)):
            with self.subTest(step=index):
                assets = {path: content for path, content in original.items() if path not in state['removals']}
                for path, entry in state['pending'].items():
                    assets[path] = None if entry.get('directory') else original[entry['copy']] if 'copy' in entry else entry['text'].encode()
                lab = load_snapshot({'definition': json.dumps(state['document']), 'assets': assets})
                payload = json.loads(setup_payload(lab.nodes[0]))
                home = next(entry for entry in payload['entries'] if entry['path'] == 'home/student/notes.py')
                self.assertEqual(home['mode'], '0644' if index == 0 else '0640')
                if index < 3:
                    target = 'srv/project/notes.py' if index < 2 else 'srv/renamed/notes.py'
                    entry = next(entry for entry in payload['entries'] if entry['path'] == target)
                    self.assertEqual((entry['owner'], entry['group'], entry['mode']), ('student', 'student', '0600'))
                else:
                    self.assertFalse(any(entry['path'] == 'srv/renamed/notes.py' for entry in payload['entries']))


if __name__ == '__main__':
    unittest.main()
