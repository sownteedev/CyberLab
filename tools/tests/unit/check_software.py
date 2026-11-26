#!/usr/bin/env python3
"""Software declaration/preparation checks with private fixtures; never uses Docker."""

import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).resolve().parents[3]))
import asyncio
from dataclasses import asdict, replace
from concurrent.futures import ThreadPoolExecutor
import json
import os
import sqlite3
import subprocess
import tempfile
from threading import Event
from time import monotonic, sleep
import unittest
import yaml
from unittest.mock import MagicMock, patch

from tools.tests.unit import check_workstations as fixture
sys.path.insert(0, str(fixture.ROOT / 'cli'))
from cyberlab.authoring.service import Authoring
from cyberlab.authoring.software import SoftwarePreparation
from cyberlab.authoring.store import DraftConflict
from cyberlab.lab.models import NodeSoftware
from cyberlab.lab.software import catalog, fingerprint, validate_software
from cyberlab.lab.loader import validate_lab
from cyberlab.runtime import RuntimeFailure
from cyberlabd.server import Server
from cyberlab_cli.main import request
from cyberlab_ipc import BUS_NAME, METHODS
from dbus_next.aio import MessageBus

class FakeSoftware:
    def __init__(self):
        self.calls = 0
        self.cleanup_calls = []
        self.gate = Event()
        self.gate.set()
        self.fail = False

    def base(self):
        return 'sha256:' + 'a' * 64

    def verify(self, software, receipt):
        if receipt['spec'] != fingerprint(software) or receipt['image'] != software.environment:
            raise RuntimeFailure('Wrong software receipt')
        return receipt['image']

    def prepare(self, software, base, cancel, progress):
        self.calls += 1
        progress('Test package installation', 50)
        while not self.gate.wait(0.01):
            if cancel.is_set():
                raise RuntimeFailure('Cancelled')
        if self.fail:
            raise RuntimeFailure('Simulated apt failure')
        return {'image': 'sha256:' + fingerprint(software), 'base': base, 'spec': fingerprint(software), 'packages': 'firefox\tfixture\n'}

    def cleanup_images(self, protected):
        self.cleanup_calls.append(set(protected))
        return {'sha256:stale'}

class StoredSoftware(FakeSoftware):
    def __init__(self):
        super().__init__()
        self.images = set()

    def prepare(self, *args):
        receipt = super().prepare(*args)
        self.images.add(receipt['image'])
        return receipt

    def verify(self, software, receipt):
        if receipt['image'] not in self.images:
            raise RuntimeFailure('Prepared software image is no longer available')
        return super().verify(software, receipt)

    def cleanup_images(self, protected):
        removed = self.images - set(protected)
        self.images.difference_update(removed)
        return removed

class SoftwareChecks(unittest.TestCase):
    def setUp(self):
        self.temporary = tempfile.TemporaryDirectory(prefix='cyberlab-software-test-')
        self.addCleanup(self.temporary.cleanup)
        self.root = Path(self.temporary.name)
        (self.root / 'catalog').mkdir()
        policy = fixture.RuntimePolicy(frozenset({fixture.UBUNTU_IMAGE}), workstation_images=frozenset({fixture.UBUNTU_IMAGE}))
        self.authoring = Authoring(self.root / 'drafts.sqlite3', self.root / 'catalog', policy)
        self.builder = FakeSoftware()
        self.manager = SoftwarePreparation(self.root / 'software.sqlite3', self.authoring, self.builder)
        self.authoring.software = self.manager
        self.addCleanup(self.manager.shutdown)
        self.uid = os.getuid()
        self.document = fixture.definition()
        self.document['metadata']['tags'] = ['linux']
        self.document['nodes'][0]['software'] = {'gui': True, 'apps': ['wireshark', 'firefox'], 'packages': []}
        self.document['nodes'][0]['resources'] = {'memory_mb': 2048, 'cpu_millicores': 2000}
        self.draft = self.authoring.create('software-test', 'Software test', self.uid, tags=['linux'])
        self.draft = self.authoring.save(self.draft['id'], self.draft['revision'], json.dumps(self.document), self.uid)

    def start(self):
        return self.manager.prepare(self.draft['id'], self.draft['revision'], 'client', self.uid)

    def done(self, job):
        deadline = monotonic() + 5
        while monotonic() < deadline:
            result = self.manager.get(job['id'], self.uid)
            if result['state'] not in {'QUEUED', 'PREPARING', 'CANCELLING'}:
                return result
            sleep(.01)
        self.fail('Software job did not finish')

    def test_schema_legacy_and_packages(self):
        validate_lab(fixture.definition())
        for name in ['--allow-unauthenticated', 'foo;id', '../foo', 'https://example/x.deb', 'foo=1', 'foo:amd64', 'foo\nbar', 'firefox', 'snapd']:
            with self.subTest(name=name), self.assertRaises(ValueError):
                validate_software(NodeSoftware(True, (), (name,)), fixture.UBUNTU_IMAGE)
        validate_software(NodeSoftware(True, (), ('mousepad', 'libgtk-3-0')), fixture.UBUNTU_IMAGE)

    def test_policy_catalog_and_package_only_environment(self):
        choices = self.authoring.capabilities()['software_catalog']['packages']
        self.assertEqual(choices, [])
        choices.append({'id': 'invented-package'})
        self.assertEqual(catalog()['packages'], [])
        self.document['nodes'][0]['software'] = {'gui': False, 'apps': [], 'packages': ['openssh-client']}
        self.draft = self.authoring.save(self.draft['id'], self.draft['revision'], json.dumps(self.document), self.uid)
        job = self.done(self.start())
        self.assertEqual(job['state'], 'READY', job)
        applied = self.manager.apply(job['id'], self.uid)
        node = validate_lab(json.loads(applied['definition'])).nodes[0]
        self.assertFalse(node.software.gui)
        self.assertEqual(node.software.packages, ('openssh-client',))
        self.assertEqual(self.manager.resolve(node.software), job['environment'])

    def test_prepare_apply_and_cached_image(self):
        self.assertFalse(self.manager.plan(self.draft['id'], self.draft['revision'], 'client', self.uid)['ready'])
        job = self.done(self.start())
        self.assertEqual(job['state'], 'READY', job)
        applied = self.manager.apply(job['id'], self.uid)
        self.assertEqual(applied['revision'], self.draft['revision'] + 1)
        node = validate_lab(json.loads(applied['definition'])).nodes[0]
        self.assertEqual(self.manager.resolve(node.software), job['environment'])
        self.draft = applied
        self.assertEqual(self.done(self.start())['environment'], job['environment'])
        self.assertEqual(self.builder.calls, 1)

    def test_cleanup_keeps_applied_image_and_removes_unreferenced_image(self):
        job = self.done(self.start())
        applied = self.manager.apply(job['id'], self.uid)
        self.assertEqual(self.manager.cleanup_unreferenced(), {'sha256:stale'})
        self.assertEqual(self.builder.cleanup_calls[-1], {job['environment']})
        with self.manager.connection() as connection:
            rows = connection.execute('SELECT image FROM software_environments ORDER BY image').fetchall()
        self.assertEqual([row[0] for row in rows], [job['environment']])

    def test_publication_defers_preparation(self):
        result = self.authoring.publish(self.draft['id'], self.draft['revision'], self.draft['digest'], self.uid)
        self.assertTrue(result['published'])
        self.assertEqual(self.builder.calls, 0)

    def test_obsolete_ready_job_does_not_keep_old_image(self):
        job = self.done(self.start())
        self.document['nodes'][0]['software']['packages'] = ['nano']
        self.authoring.save(self.draft['id'], self.draft['revision'], json.dumps(self.document), self.uid)
        self.assertNotIn(job['environment'], self.manager.referenced_images())

    def test_finished_failed_job_does_not_keep_old_image(self):
        self.manager.write({'id': 'failed', 'owner': self.uid, 'state': 'FAILED',
                            'environment': 'sha256:' + 'f' * 64})
        self.assertNotIn('sha256:' + 'f' * 64, self.manager.referenced_images())

    def test_automatic_images_survive_cleanup_for_unchanged_draft(self):
        self.builder = self.manager.runtime = StoredSoftware()
        lab = validate_lab(self.document)
        prepared = self.manager.prepare_lab(lab, self.uid, Event())
        self.manager.cleanup_unreferenced()
        self.manager.resolve(prepared.nodes[0].software)
        self.manager.prepare_lab(lab, self.uid, Event())
        self.assertEqual(self.builder.calls, 1)

    def test_multinode_preparation_keeps_earlier_images_until_handoff(self):
        self.builder = self.manager.runtime = StoredSoftware()
        document = json.loads(json.dumps(self.document))
        document['nodes'][0]['software']['packages'] = ['nano']
        document['nodes'].append(dict(document['nodes'][0], id='server',
                                     software={'gui': True, 'apps': [], 'packages': ['curl']}))
        lab = validate_lab(document)
        cancel = Event()
        with self.manager.image_lease(cancel):
            prepared = self.manager.prepare_lab(lab, self.uid, cancel)
            self.manager.cleanup_unreferenced()
            for node in prepared.nodes:
                self.manager.resolve(node.software)
        self.manager.cleanup_unreferenced()
        self.assertFalse(self.builder.images)

    def test_cleanup_does_not_wait_for_running_builder(self):
        self.builder = self.manager.runtime = StoredSoftware()
        entered = Event()
        self.builder.gate.clear()
        prepare = self.builder.prepare

        def building(*args):
            entered.set()
            return prepare(*args)

        with patch.object(self.builder, 'prepare', side_effect=building), ThreadPoolExecutor(max_workers=2) as pool:
            job = self.start()
            try:
                self.assertTrue(entered.wait(2))
                cleanup = pool.submit(self.manager.cleanup_unreferenced)
                self.assertEqual(cleanup.result(timeout=2), set())
            finally:
                self.builder.gate.set()
            self.assertEqual(self.done(job)['state'], 'READY')

    def test_cleanup_without_software_does_not_require_ubuntu(self):
        self.document['nodes'][0].pop('software')
        self.authoring.save(self.draft['id'], self.draft['revision'], json.dumps(self.document), self.uid)
        with patch.object(self.builder, 'base', side_effect=RuntimeFailure('Ubuntu is disabled')):
            self.assertEqual(self.manager.cleanup_unreferenced(), {'sha256:stale'})

    def test_yaml_draft_can_prepare_and_keep_its_software(self):
        self.builder = self.manager.runtime = StoredSoftware()
        self.draft = self.authoring.save(self.draft['id'], self.draft['revision'],
                                         yaml.safe_dump(self.document), self.uid)
        job = self.done(self.start())
        self.assertEqual(job['state'], 'READY', job)
        self.manager.cleanup_unreferenced()
        self.assertIn(job['environment'], self.builder.images)

    def test_unfinished_other_draft_skips_cleanup_without_blocking_preparation(self):
        other = self.authoring.create('unfinished', 'Unfinished', self.uid, tags=['linux'])
        self.authoring.save(other['id'], other['revision'], 'nodes: [', self.uid)
        with self.assertLogs(level='WARNING'):
            job = self.done(self.start())
        self.assertEqual(job['state'], 'READY', job)
        self.assertFalse(self.builder.cleanup_calls)

    def test_owner_and_revision(self):
        job = self.done(self.start())
        with self.assertRaises(ValueError):
            self.manager.get(job['id'], self.uid + 100)
        self.authoring.save(self.draft['id'], self.draft['revision'], json.dumps(self.document), self.uid)
        with self.assertRaises(DraftConflict):
            self.manager.apply(job['id'], self.uid)

    def test_duplicate_cancel_retry(self):
        self.builder.gate.clear()
        job = self.start()
        self.assertEqual(self.start()['id'], job['id'])
        self.manager.cancel(job['id'], self.uid)
        self.assertEqual(self.done(job)['state'], 'CANCELLED')
        self.builder.gate.set()
        self.assertEqual(self.done(self.start())['state'], 'READY')

    def test_job_storage_failure_releases_worker_capacity(self):
        self.addCleanup(self.manager.workers.clear)
        with patch('cyberlab.authoring.software.Thread.start'):
            job = self.start()
        cancel = self.manager.workers[job['id']][0]
        _, node = self.manager.node(self.draft['id'], self.draft['revision'], 'client', self.uid)
        write = self.manager.write

        def fail_final_write(current):
            if current['state'] in {'READY', 'FAILED', 'CANCELLED'}:
                raise sqlite3.OperationalError('database full')
            write(current)

        with patch.object(self.manager, 'write', side_effect=fail_final_write):
            with self.assertRaises(sqlite3.OperationalError):
                self.manager.run(job, node.software, self.builder.base(), cancel)
        self.assertNotIn(job['id'], self.manager.workers)
        failed = self.manager.get(job['id'], self.uid)
        self.assertEqual(failed['state'], 'FAILED')
        self.assertTrue(failed['error'])
        self.assertEqual(self.manager.latest(self.draft['id'], 'client', self.uid), failed)
        self.assertEqual(self.manager.cancel(job['id'], self.uid), failed)
        self.assertEqual(self.manager.plan(self.draft['id'], self.draft['revision'], 'client', self.uid)['latest_job'], failed)
        with self.assertRaises(ValueError):
            self.manager.get(job['id'], self.uid + 1)
        self.assertEqual(self.done(self.start())['state'], 'READY')

    def test_failure_and_stale_revision_keep_draft(self):
        self.builder.fail = True
        self.assertEqual(self.done(self.start())['state'], 'FAILED')
        self.assertEqual(self.authoring.get(self.draft['id'], self.uid)['definition'], self.draft['definition'])
        self.builder.fail = False
        self.builder.gate.clear()
        job = self.start()
        self.authoring.save(self.draft['id'], self.draft['revision'], json.dumps(self.document), self.uid)
        self.builder.gate.set()
        self.assertEqual(self.done(job)['state'], 'FAILED')

    def test_restart_marks_interrupted_jobs(self):
        self.manager.write({'id': 'interrupted', 'owner': self.uid, 'state': 'PREPARING'})
        other = SoftwarePreparation(self.root / 'software.sqlite3', self.authoring, self.builder)
        self.assertEqual(other.get('interrupted', self.uid)['state'], 'FAILED')
        self.assertEqual((self.root / 'software.sqlite3').stat().st_mode & 0o777, 0o600)

    def test_changed_configuration_cannot_reuse_image(self):
        job = self.done(self.start())
        with self.assertRaises(RuntimeFailure):
            self.manager.resolve(NodeSoftware(True, ('wireshark',), (), job['environment']))

    def test_private_dbus_round_trip(self):
        async def check():
            process = subprocess.Popen(['dbus-daemon', '--session', '--nofork', '--print-address=1'], stdout=subprocess.PIPE, text=True)
            bus = client = None
            try:
                address = process.stdout.readline().strip()
                bus = await MessageBus(bus_address=address).connect()
                await bus.request_name(BUS_NAME)
                server = Server(bus, None, {self.uid}, self.authoring)
                bus.add_message_handler(server.handle)
                client = await MessageBus(bus_address=address).connect()
                info = json.loads(await request(client, 'GetAuthoringInfo', []))
                self.assertEqual(info['software_catalog']['packages'], catalog()['packages'])
                self.assertTrue(info['software_search'])
                body = [self.draft['id'], self.draft['revision'], 'client']
                plan = json.loads(await request(client, 'PlanNodeSoftware', body))
                self.assertFalse(plan['ready'])
                job = json.loads(await request(client, 'PrepareNodeSoftware', body))
                result = await asyncio.to_thread(self.done, job)
                self.assertEqual(result['state'], 'READY')
                applied = json.loads(await request(client, 'ApplySoftwareJob', [job['id']]))
                self.assertGreater(applied['revision'], self.draft['revision'])
            finally:
                if client: client.disconnect(); await client.wait_for_disconnect()
                if bus: bus.disconnect(); await bus.wait_for_disconnect()
                process.terminate()
                process.wait(timeout=5)
                process.stdout.close()
        asyncio.run(check())

class SoftwareRuntimeChecks(unittest.TestCase):
    def setUp(self):
        from io import BytesIO
        import tarfile
        from unittest.mock import MagicMock, patch
        from cyberlab.runtime.software import SoftwareRuntime, LABEL
        from cyberlab.lab.workstation import WORKSTATION_LABEL, WORKSTATION_VERSION

        self.label = LABEL
        self.runtime = MagicMock()
        self.runtime.workstation_images = {fixture.UBUNTU_IMAGE}
        self.builder = SoftwareRuntime(self.runtime, 'fixture')
        self.client = self.runtime.client
        self.client.images.get.return_value.id = 'sha256:' + 'a' * 64
        self.client.images.get.return_value.attrs = {'Config': {'Labels': {WORKSTATION_LABEL: WORKSTATION_VERSION}}}
        self.client.images.list.return_value = []
        self.container = self.client.containers.create.return_value
        self.container.status = 'exited'
        self.container.attrs = {'State': {'ExitCode': 0}}
        self.client.api.containers.return_value = [{'SizeRw': 1024}]
        self.image = self.container.commit.return_value
        self.image.id = 'sha256:' + 'b' * 64
        self.image.attrs = {'Size': 2048}
        archive = BytesIO()
        with tarfile.open(fileobj=archive, mode='w') as stream:
            entry = tarfile.TarInfo('packages.txt')
            entry.size = len(b'firefox\tfixture\n')
            stream.addfile(entry, BytesIO(b'firefox\tfixture\n'))
        self.container.get_archive.return_value = ([archive.getvalue()], {})
        disk = patch('cyberlab.runtime.software.shutil.disk_usage')
        self.disk = disk.start()
        self.disk.return_value.free = 20 * 1024**3
        self.addCleanup(disk.stop)

    def prepare(self, cancel=None):
        return self.builder.prepare(NodeSoftware(True, ('firefox', 'wireshark')), self.builder.base(), cancel or Event(), lambda *args: None)

    def test_package_only_build_does_not_install_gui_stack(self):
        self.builder.prepare(NodeSoftware(False, (), ('openssh-client',)), self.builder.base(), Event(), lambda *args: None)
        command = self.client.containers.create.call_args.kwargs['command']
        self.assertEqual(command[command.index('cyberlab-software') + 1:], ['ubuntu', 'openssh-client'])

    def test_cleanup_images_keeps_protected_and_removes_stale_scope_images(self):
        from cyberlab.lab.software import RECIPE_VERSION
        protected = MagicMock(id='sha256:' + 'c' * 64)
        stale = MagicMock(id='sha256:' + 'd' * 64)
        for image in (protected, stale):
            image.attrs = {'Config': {'Labels': {self.label: RECIPE_VERSION, self.label + '.scope': 'fixture'}}}
        self.client.images.list.return_value = [protected, stale]
        removed = self.builder.cleanup_images({protected.id})
        self.assertEqual(removed, {stale.id})
        protected.remove.assert_not_called()
        stale.remove.assert_called_once_with(force=False, noprune=True)

    def test_software_cleanup_never_deletes_checkpoint_with_inherited_labels(self):
        from cyberlab.lab.software import RECIPE_VERSION
        from cyberlab.runtime.checkpoints import CHECKPOINT_LABEL
        checkpoint = MagicMock(id='sha256:' + 'e' * 64)
        checkpoint.attrs = {'Config': {'Labels': {self.label: RECIPE_VERSION,
                            self.label + '.scope': 'fixture', CHECKPOINT_LABEL: 'v1'}}}
        self.client.images.list.return_value = [checkpoint]
        self.assertEqual(self.builder.cleanup_images(set()), set())
        checkpoint.remove.assert_not_called()

    def test_builtin_app_without_gui_keeps_recipe_without_display_stack(self):
        from cyberlab.runtime.desktop import PACKAGES

        software = NodeSoftware(False, ('firefox',), ('nano',))
        self.builder.prepare(software, self.builder.base(), Event(), lambda *args: None)
        command = self.client.containers.create.call_args.kwargs['command']
        installed = command[command.index('cyberlab-software') + 1:]
        self.assertEqual(installed[0], 'firefox')
        self.assertIn('firefox', installed[1:])
        self.assertIn('nano', installed[1:])
        self.assertFalse(set(installed[1:]) & set(PACKAGES))

    def test_root_home_isolated_and_image_does_not_inherit_builder_identity(self):
        receipt = self.prepare()
        options = self.client.containers.create.call_args.kwargs
        self.assertEqual(options['environment']['HOME'], '/root')
        self.assertFalse(options['privileged'])
        self.assertNotIn('volumes', options)
        self.assertEqual(options['cap_drop'], ['ALL'])
        committed = self.container.commit.call_args.kwargs['conf']
        self.assertEqual(committed['Labels'][self.label + '.building'], '')
        self.assertIn('HOME=/home/student', committed['Env'])
        self.assertEqual(receipt['packages'], 'firefox\tfixture\n')
        self.container.remove.assert_called_once_with(force=True)

    def test_custom_gui_package_includes_display_without_builtin_apps(self):
        from cyberlab.runtime.desktop import PACKAGES

        software = NodeSoftware(True, (), ('mousepad',))
        receipt = self.builder.prepare(software, self.builder.base(), Event(), lambda *args: None)
        command = self.client.containers.create.call_args.kwargs['command']
        installed = command[command.index('cyberlab-software') + 1:]
        self.assertEqual(installed[0], 'ubuntu')
        self.assertEqual(set(installed[1:]), set(PACKAGES) | {'mousepad'})
        self.assertEqual(receipt['software'], {'gui': True, 'apps': [], 'packages': ['mousepad']})

    def test_running_layer_limit_and_low_disk_abort_before_commit(self):
        self.client.api.containers.return_value = [{'SizeRw': 3 * 1024**3}]
        with self.assertRaisesRegex(RuntimeFailure, 'writable-layer'):
            self.prepare()
        self.container.commit.assert_not_called()
        self.container.remove.assert_called_once()

    def test_low_disk_does_not_create_container(self):
        self.disk.return_value.free = 100
        with self.assertRaisesRegex(RuntimeFailure, 'free Docker storage'):
            self.prepare()
        self.client.containers.create.assert_not_called()

    def test_preparation_quota_counts_shared_ubuntu_only_once(self):
        from tools.tests.unit.check_image_storage import image
        gib = 1024**3
        self.client.images.list.return_value = [image(str(index), ['ubuntu', 'app-' + str(index)],
                                                       [gib, gib // 2]) for index in range(8)]
        receipt = self.prepare()
        self.assertEqual(receipt['image'], self.image.id)

    def test_preparation_quota_still_blocks_unshared_storage(self):
        from tools.tests.unit.check_image_storage import image
        gib = 1024**3
        self.client.images.list.return_value = [image(str(index), ['private-' + str(index)],
                                                       [2 * gib]) for index in range(6)]
        with self.assertRaisesRegex(RuntimeFailure, 'storage limit reached'):
            self.prepare()
        self.client.containers.create.assert_not_called()

    def test_cancel_removes_only_preparation_container(self):
        cancel = Event()
        cancel.set()
        with self.assertRaisesRegex(RuntimeFailure, 'cancelled'):
            self.prepare(cancel)
        self.container.commit.assert_not_called()
        self.container.remove.assert_called_once()

    def test_failed_apt_keeps_existing_image(self):
        self.container.attrs['State']['ExitCode'] = 1
        self.container.logs.return_value = b'Package not found'
        with self.assertRaisesRegex(RuntimeFailure, 'Package not found'):
            self.prepare()
        self.client.images.remove.assert_not_called()

    def test_cleanup_ignores_sessions_with_inherited_build_label(self):
        from unittest.mock import MagicMock
        session = MagicMock()
        session.name = 'cyberlab-software-old-session'
        session.labels = {'org.ptit.cyberlab.managed': 'mvp-v1', self.label + '.building': 'fixture'}
        builder = MagicMock()
        builder.name = 'cyberlab-software-test'
        builder.labels = {self.label + '.building': 'fixture'}
        self.client.containers.list.return_value = [session, builder]
        self.builder.cleanup()
        session.remove.assert_not_called()
        builder.remove.assert_called_once_with(force=True)

if __name__ == '__main__':
    unittest.main(verbosity=2)
