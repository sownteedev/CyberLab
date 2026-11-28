#!/usr/bin/env python3
"""Exercise the daemon/update barrier without touching the system bus."""

import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).resolve().parents[3]))
import fcntl
import json
import tempfile
from types import SimpleNamespace
import unittest
from unittest.mock import Mock, patch

from tools.tests.unit import check_edit_protection
from cyberlabd.maintenance import request_lease
from cyberlabd.server import Server
from cyberlab.service import SessionBusy
from tools.install import runtime_admin


class MaintenanceChecks(unittest.TestCase):
    def setUp(self):
        temporary = tempfile.TemporaryDirectory()
        self.addCleanup(temporary.cleanup)
        self.path = Path(temporary.name) / 'maintenance.lock'
        self.server = Server(None, None, {1000}, maintenance_path=self.path)
        self.server._dispatch = Mock(return_value='completed')

    def test_active_request_prevents_exclusive_maintenance(self):
        with request_lease(self.path), self.path.open('rb') as lock:
            with self.assertRaises(BlockingIOError):
                fcntl.flock(lock.fileno(), fcntl.LOCK_EX | fcntl.LOCK_NB)

    def test_maintenance_blocks_start_and_authoring_before_dispatch(self):
        self.path.touch(mode=0o600)
        with self.path.open('rb') as lock:
            fcntl.flock(lock.fileno(), fcntl.LOCK_EX)
            for member in ('StartLab', 'ResumeSession', 'SaveDraft', 'ProtectedAuthoring', 'ImportLabPackage'):
                with self.subTest(member=member), self.assertRaises(SessionBusy):
                    self.server.dispatch(member, [], 1000)
            self.server._dispatch.assert_not_called()
            self.assertEqual(self.server.dispatch('ListSessions', [], 1000), 'completed')
        self.assertEqual(self.server.dispatch('StartLab', [], 1000), 'completed')

    def test_installer_verifies_authoring_without_releasing_maintenance(self):
        from cyberlab.authoring.service import Authoring
        from cyberlab.policy import RuntimePolicy
        from cyberlab.lab.workstation import UBUNTU_IMAGE
        from cyberlab.service import Engine
        from cyberlabd.testing import MemoryRuntime

        for workstation in (False, True):
            with self.subTest(workstation=workstation), tempfile.TemporaryDirectory() as directory:
                root = Path(directory)
                catalog = root / 'catalog'
                catalog.mkdir()
                policy = RuntimePolicy(
                    allowed_images=frozenset({UBUNTU_IMAGE} if workstation else {'busybox:1.37.0'}),
                    workstation_images=frozenset({UBUNTU_IMAGE} if workstation else set()))
                authoring = Authoring(root / 'drafts.db', catalog, policy)
                authoring.software = SimpleNamespace(lock=authoring.lifecycle_lock,
                    workers={}, automatic={}, image_leases={})
                runtime = MemoryRuntime()
                runtime.name = 'docker'
                runtime.desktop = Mock()
                server = Server(None, Engine(catalog, policy, runtime), {1000}, authoring,
                                maintenance_path=self.path)
                methods = {('info',): None, ('labs',): 'ListLabs', ('draft', 'info'): 'GetAuthoringInfo'}
                probes = []

                def run(command, *arguments, **kwargs):
                    self.assertEqual(command, runtime_admin.CLI)
                    with self.path.open('rb') as contender:
                        with self.assertRaises(BlockingIOError):
                            fcntl.flock(contender.fileno(), fcntl.LOCK_SH | fcntl.LOCK_NB)
                    probes.append(arguments)
                    if arguments == ('info',):
                        payload = {'version': server.dispatch('GetVersion', [], 1000),
                                   'capabilities': server.dispatch('GetCapabilities', [], 1000)}
                    else:
                        payload = server.dispatch(methods[arguments], [], 1000)
                    return SimpleNamespace(returncode=0,
                        stdout=payload if isinstance(payload, str) else json.dumps(payload))

                self.path.touch(mode=0o600)
                with self.path.open('rb') as lock, patch.object(runtime_admin, 'run', side_effect=run):
                    fcntl.flock(lock.fileno(), fcntl.LOCK_EX | fcntl.LOCK_NB)
                    information = runtime_admin.verify_daemon(SimpleNamespace(pw_uid=1000),
                                                             require_workstation=workstation)
                    self.assertIn('authoring', information['capabilities'])
                    self.assertIn(('draft', 'info'), probes)
                    for member in ('StartLab', 'SaveDraft', 'ProtectedAuthoring', 'ImportLabPackage'):
                        with self.assertRaises(SessionBusy):
                            server.dispatch(member, [], 1000)

    def test_unsafe_lock_is_not_used(self):
        target = self.path.with_name('other')
        target.touch()
        self.path.symlink_to(target)
        with self.assertRaises(OSError), request_lease(self.path):
            self.fail('symlink accepted')

    def test_background_software_job_is_advertised_as_busy(self):
        from types import SimpleNamespace
        from threading import RLock
        software = SimpleNamespace(lock=RLock(), workers={'job': object()}, automatic={}, image_leases={})
        engine = SimpleNamespace(runtime=SimpleNamespace(name='fixture'), practice_store=None,
                                 policy=SimpleNamespace(workstation_images=set(), allowed_images=set()))
        server = Server(None, engine, {1000}, SimpleNamespace(software=software), maintenance_path=self.path)
        self.assertIn('maintenance-busy', server.dispatch('GetCapabilities', [], 1000))
        software.workers.clear()
        self.assertNotIn('maintenance-busy', server.dispatch('GetCapabilities', [], 1000))


if __name__ == '__main__':
    unittest.main()
