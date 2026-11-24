#!/usr/bin/env python3
"""Isolated declarative machine setup checks; never uses host accounts or Docker."""

from copy import deepcopy
from dataclasses import asdict
from pathlib import Path
import tempfile
import unittest
import os
from dataclasses import replace
from unittest.mock import Mock, patch

from check_workstations import definition
from cyberlab.lab.loader import validate_lab, LabValidationError, load_lab
from cyberlab.lab.package import load_snapshot
import yaml


def setup_definition():
    document = definition()
    document['nodes'][0]['setup'] = {
        'groups': [{'name': 'bakers', 'gid': 3100}],
        'users': [{'name': 'frank', 'uid': 3001, 'gid': 3001, 'groups': ['bakers']},
                  {'name': 'mary', 'uid': 3002, 'gid': 3002}],
        'files': [{'source': 'assets/recipe.txt', 'target': '/shared_stuff/recipe.txt',
                   'owner': 'frank', 'group': 'bakers', 'mode': '0660'}],
        'home': [{'path': 'notes.txt', 'owner': 'student', 'group': 'student', 'mode': '0600'}],
    }
    return document


class SetupChecks(unittest.TestCase):
    def test_old_lab_has_no_setup(self):
        self.assertIsNone(validate_lab(definition()).nodes[0].setup)

    def test_accounts_and_permissions_survive_snapshot_roundtrip(self):
        document = setup_definition()
        document['nodes'][0]['files'] = [{'source': 'assets/notes.txt', 'target': 'notes.txt'}]
        package = {'definition': yaml.safe_dump(document),
                   'assets': {'assets': None, 'assets/recipe.txt': b'recipe', 'assets/notes.txt': b'notes'}}
        lab = load_snapshot(package)
        self.assertEqual(lab.nodes[0].setup.users[0].groups, ('bakers',))
        self.assertEqual(lab.nodes[0].setup.users[1].password_hash, '!')
        self.assertEqual(lab.nodes[0].setup.users[1].sudo, 'disabled')
        self.assertEqual([(entry.path, entry.data) for entry in lab.nodes[0].system_seed
                          if entry.data is not None], [('shared_stuff/recipe.txt', b'recipe')])
        self.assertEqual(lab.nodes[0].seed[0].data, b'notes')

    def test_rejects_unsafe_paths_and_protected_system_files(self):
        for target in ('/etc/passwd', '/etc/shadow', '/etc/sudoers.d/evil', '/etc/pam.d/login',
                       '/etc/../tmp/oops', '/proc/x', '/var/run/x', '/usr/bin/python3',
                       '/etc/cron.d/job', '/etc/ld.so.preload', '/home', '/etc',
                       '/opt/cyberlab/private', '/shared_stuff/.cyberlab-owned'):
            with self.subTest(target=target):
                document = setup_definition()
                document['nodes'][0]['setup']['files'][0]['target'] = target
                with self.assertRaises(LabValidationError):
                    validate_lab(document)

    def test_rejects_account_collisions_and_dangling_references(self):
        for change in ({'name': 'student'}, {'name': 'root'}, {'uid': 2000}, {'uid': 3002},
                       {'gid': 3100}, {'groups': ['missing']}, {'sudo': 'all'},
                       {'password_hash': 'plaintext'}, {'password': 'secret'}):
            document = setup_definition()
            document['nodes'][0]['setup']['users'][0].update(change)
            with self.subTest(change=change), self.assertRaises(LabValidationError):
                validate_lab(document)
        document = setup_definition()
        document['nodes'][0]['setup']['users'].pop(0)
        with self.assertRaises(LabValidationError):
            validate_lab(document)


class SetupRuntimeChecks(unittest.TestCase):
    def runtime_fixture(self):
        from check_workstations import WorkstationChecks
        fixture = WorkstationChecks('test_workstation_args_do_not_grant_host_access')
        fixture.setUp()
        self.addCleanup(fixture.doCleanups)
        node = validate_lab(setup_definition()).nodes[0]
        node = replace(node, setup=replace(node.setup, files=(), home=()))
        fixture.session = replace(fixture.session, lab=replace(fixture.lab, nodes=(node,)))
        return fixture

    def test_fresh_start_gates_user_command_on_setup_and_resume_skips_it(self):
        fixture = self.runtime_fixture()
        with patch('cyberlab.runtime.docker.configure_container') as configure:
            options, seed = fixture.start()
            self.assertEqual(options['command'][:3], ['/usr/bin/python3', '-I', '-c'])
            self.assertEqual(options['user'], '0:0')
            self.assertTrue(options['stdin_open'])
            self.assertFalse(options['privileged'])
            self.assertEqual(configure.call_count, 1)
            self.assertEqual(seed.call_count, 0)
        fixture.runtime.system_checkpoints.restore_image = Mock(return_value='sha256:' + 'e' * 64)
        with patch('cyberlab.runtime.docker.configure_container') as configure:
            options, seed = fixture.start(system_images={'client': 'sha256:' + 'e' * 64})
            self.assertEqual(options['user'], '2000:2000')
            self.assertNotEqual(options['command'][0], '/usr/bin/python3')
            self.assertEqual(configure.call_count, 0)
            self.assertEqual(seed.call_count, 0)

    def test_setup_failure_never_verifies_guest_or_reports_start_success(self):
        from cyberlab.runtime import RuntimeFailure
        fixture = self.runtime_fixture()
        fixture.runtime.native.verify_guest = Mock()
        with patch('cyberlab.runtime.docker.configure_container', side_effect=RuntimeFailure('fixture setup failure')):
            with self.assertRaises(RuntimeFailure):
                fixture.start()
        self.assertEqual(fixture.runtime.native.verify_guest.call_count, 0)

    def test_setup_transfer_timeout_closes_socket(self):
        from cyberlab.runtime.machine_setup import configure_container
        from cyberlab.runtime import RuntimeFailure
        fixture = self.runtime_fixture()
        container = Mock()
        stream = Mock(spec=['sendall', 'shutdown', 'settimeout', 'close'])
        container.attach_socket.return_value = stream
        with self.assertRaises(RuntimeFailure):
            configure_container(container, fixture.session.lab.nodes[0], timeout=0)
        self.assertTrue(stream.close.called)

    def test_safe_writer_rejects_symlinks_hardlinks_and_executables(self):
        from cyberlab.runtime.setup_helper import install_entry
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            (root / 'outside').write_bytes(b'keep')
            (root / 'link').symlink_to(root / 'outside')
            os.link(root / 'outside', root / 'hard')
            (root / 'tool').write_bytes(b'old tool')
            (root / 'tool').chmod(0o755)
            descriptor = os.open(root, os.O_RDONLY | os.O_DIRECTORY)
            try:
                for path in ('link', 'hard', 'tool', '../escape'):
                    with self.subTest(path=path), self.assertRaises(ValueError):
                        install_entry(descriptor, path, b'bad', os.getuid(), os.getgid(), 0o644)
                install_entry(descriptor, 'shared/recipe', b'new', os.getuid(), os.getgid(), 0o660)
                self.assertEqual((root / 'shared/recipe').read_bytes(), b'new')
                self.assertEqual((root / 'shared/recipe').stat().st_mode & 0o7777, 0o660)
                self.assertEqual((root / 'outside').read_bytes(), b'keep')
            finally:
                os.close(descriptor)

    def test_directory_mapping_cannot_smuggle_reserved_paths(self):
        document = setup_definition()
        document['nodes'][0]['setup']['home'] = []
        document['nodes'][0]['setup']['files'] = [dict(source='assets/tree', target='/opt/tools',
                                                     owner='root', group='root', mode='0755')]
        with self.assertRaises(LabValidationError):
            load_snapshot(dict(definition=yaml.safe_dump(document), assets={'assets/tree/cyberlab-secret': b'no'}))

    def test_file_metadata_cannot_use_directory_special_bits(self):
        document = setup_definition()
        document['nodes'][0]['setup']['home'] = []
        document['nodes'][0]['setup']['files'][0]['mode'] = '2660'
        with self.assertRaises(LabValidationError):
            load_snapshot(dict(definition=yaml.safe_dump(document), assets={'assets/recipe.txt': b'recipe'}))

    def test_old_lab_digest_stays_compatible(self):
        from cyberlab.assessment import lab_digest
        import hashlib
        import json
        lab = validate_lab(definition())
        old = asdict(lab)
        for node in old['nodes']:
            node.pop('setup')
            node.pop('system_seed')
        expected = hashlib.sha256(json.dumps(old, sort_keys=True, ensure_ascii=True,
                                             separators=(',', ':')).encode()).hexdigest()
        self.assertEqual(lab_digest(lab), expected)

    def test_setup_payload_is_stdin_only_and_does_not_change_software(self):
        from cyberlab.runtime.machine_setup import setup_command, setup_payload
        node = validate_lab(setup_definition()).nodes[0]
        node = replace(node, setup=replace(node.setup, files=(), home=()))
        original = validate_lab(definition()).nodes[0]
        self.assertEqual(node.software, original.software)
        command = setup_command(node, ['sleep', 'infinity'])
        self.assertNotIn('frank', command)
        payload = setup_payload(node)
        self.assertIn(b'frank', payload)
        self.assertEqual(command[:2], ['/usr/bin/python3', '-I'])

    def test_only_approved_workstation_supports_setup(self):
        document = setup_definition()
        document['nodes'][0]['image'] = 'busybox:1.37.0'
        with self.assertRaises(LabValidationError):
            validate_lab(document)

    def test_rejects_setuid_and_plaintext_main_password(self):
        document = setup_definition()
        document['nodes'][0]['setup']['files'][0]['mode'] = '4755'
        with self.assertRaises(LabValidationError):
            validate_lab(document)
        document = setup_definition()
        document['nodes'][0]['setup']['password_hash'] = 'secret'
        with self.assertRaises(LabValidationError):
            validate_lab(document)


if __name__ == '__main__':
    unittest.main()
