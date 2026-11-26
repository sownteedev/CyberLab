#!/usr/bin/env python3
"""Exercise the daemon/update barrier without touching the system bus."""

import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).resolve().parents[3]))
import fcntl
import tempfile
import unittest
from unittest.mock import Mock

from tools.tests.unit import check_edit_protection
from cyberlabd.maintenance import request_lease
from cyberlabd.server import Server
from cyberlab.service import SessionBusy


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
