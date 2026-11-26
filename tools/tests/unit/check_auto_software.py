#!/usr/bin/env python3
"""Automatic software startup checks using temporary catalogs and fake builders."""

import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).resolve().parents[3]))
from concurrent.futures import ThreadPoolExecutor
from dataclasses import replace
from threading import Event
from time import monotonic, sleep
import unittest
from unittest.mock import patch
import json
import asyncio
import subprocess
from types import SimpleNamespace
from unittest.mock import AsyncMock

from tools.tests.unit import check_software as software_checks
from tools.tests.unit.check_workstations import Engine, MemoryRuntime, SessionState
from cyberlab.lab.loader import validate_lab
from cyberlab.runtime import RuntimeFailure
from cyberlab.lab.software import STARTUP_TIMEOUT_SECONDS
from cyberlab_cli.main import request
from cyberlab_ipc import BUS_NAME, METHODS
from dbus_next import MessageType
from dbus_next.aio import MessageBus
from cyberlabd.server import Server


class AutomaticSoftwareChecks(software_checks.SoftwareChecks):
    def publish(self):
        result = self.authoring.publish(self.draft['id'], self.draft['revision'], self.draft['digest'], self.uid)
        self.assertTrue(result['published'])
        runtime = MemoryRuntime()
        runtime.prepared_software = self.manager
        self.engine = Engine(self.root / 'catalog', self.authoring.policy, runtime)
        self.manager.active_images = self.engine.software_image_ids
        self.authoring.lifecycle_lock = self.engine._lock
        return self.document['metadata']['id']

    def test_publication_does_not_build(self):
        self.publish()
        self.assertEqual(self.builder.calls, 0)

    def test_optional_preinstall_is_reused_when_starting(self):
        job = self.done(self.start())
        self.assertEqual(job['state'], 'READY')
        self.draft = self.manager.apply(job['id'], self.uid)
        identifier = self.publish()
        self.assertEqual(self.builder.calls, 1)
        session = self.engine.start(identifier, self.uid)
        self.assertEqual(session.state, SessionState.RUNNING, session.error)
        self.assertEqual(self.builder.calls, 1)

    def test_stop_before_worker_entry_reserves_start_until_cancelled(self):
        identifier = self.publish()
        entered, release = Event(), Event()
        start = self.engine._start
        def delayed(*args, **kwargs):
            entered.set()
            self.assertTrue(release.wait(3))
            return start(*args, **kwargs)
        with patch.object(self.engine, '_start', side_effect=delayed), ThreadPoolExecutor(max_workers=1) as pool:
            running = pool.submit(self.engine.start, identifier, self.uid)
            try:
                self.assertTrue(entered.wait(2))
                session = next(iter(self.engine._sessions.values()))
                self.assertEqual(self.engine.stop(session.id, self.uid).state, SessionState.STOPPED)
                from cyberlab.service import SessionBusy
                with self.assertRaises(SessionBusy):
                    self.engine.reset(session.id, self.uid)
            finally:
                release.set()
            self.assertEqual(running.result(timeout=3).state, SessionState.STOPPED)
        self.assertEqual(self.builder.calls, 0)
        self.assertFalse(self.engine._starting)
        self.assertEqual(self.engine.reset(session.id, self.uid).state, SessionState.RUNNING)

    def test_first_start_prepares_and_reuses_without_changing_catalog(self):
        self.builder = self.manager.runtime = software_checks.StoredSoftware()
        identifier = self.publish()
        path = self.root / 'catalog' / identifier / 'lab.yaml'
        original = path.read_bytes()
        first = self.engine.start(identifier, self.uid)
        self.assertEqual(first.state, SessionState.RUNNING, first.error)
        self.assertTrue(first.lab.nodes[0].software.environment)
        self.assertEqual(self.builder.calls, 1)
        self.engine.stop(first.id, self.uid)
        second = self.engine.start(identifier, self.uid)
        self.assertEqual(second.state, SessionState.RUNNING, second.error)
        self.assertEqual(self.builder.calls, 1)
        self.assertEqual(path.read_bytes(), original)
        self.assertEqual(self.authoring.get(self.draft['id'], self.uid)['definition'], self.draft['definition'])

    def test_start_keeps_image_between_preparation_and_runtime_handoff(self):
        self.builder = self.manager.runtime = software_checks.StoredSoftware()
        identifier = self.publish()
        prepare = self.manager.prepare_lab

        def collect_during_handoff(*args, **kwargs):
            prepared = prepare(*args, **kwargs)
            self.document['nodes'][0]['software']['packages'] = ['nano']
            self.authoring.save(self.draft['id'], self.draft['revision'], json.dumps(self.document), self.uid)
            path = self.root / 'catalog' / identifier / 'lab.yaml'
            path.write_text(json.dumps(self.document))
            self.manager.cleanup_unreferenced()
            for node in prepared.nodes:
                self.manager.resolve(node.software)
            return prepared

        with patch.object(self.manager, 'prepare_lab', side_effect=collect_during_handoff):
            session = self.engine.start(identifier, self.uid)
        self.assertEqual(session.state, SessionState.RUNNING, session.error)
        self.assertFalse(self.manager.image_leases)
        self.manager.cleanup_unreferenced()
        self.assertTrue(self.builder.images)
        self.engine.stop(session.id, self.uid)
        self.assertFalse(self.builder.images)

    def test_repeated_start_stop_and_edit_do_not_accumulate_images(self):
        self.builder = self.manager.runtime = software_checks.StoredSoftware()
        identifier = self.publish()
        first_images = None
        for attempt in range(5):
            session = self.engine.start(identifier, self.uid)
            self.assertEqual(session.state, SessionState.RUNNING, session.error)
            self.engine.stop(session.id, self.uid)
            self.assertEqual(len(self.builder.images), 1)
            if first_images is None:
                first_images = set(self.builder.images)
            self.assertEqual(self.builder.images, first_images)
        self.assertEqual(self.builder.calls, 1)
        self.document['nodes'][0]['software']['packages'] = ['nano']
        self.authoring.save(self.draft['id'], self.draft['revision'], json.dumps(self.document), self.uid)
        (self.root / 'catalog' / identifier / 'lab.yaml').write_text(json.dumps(self.document))
        updated = self.engine.start(identifier, self.uid)
        self.assertEqual(updated.state, SessionState.RUNNING, updated.error)
        self.assertEqual(len(self.builder.images), 1)
        self.assertTrue(self.builder.images.isdisjoint(first_images))
        self.assertEqual(self.builder.calls, 2)

    def test_saved_software_reference_survives_database_reload(self):
        from unittest.mock import Mock
        from cyberlab.session.persistence import PracticeStore
        self.builder = self.manager.runtime = software_checks.StoredSoftware()
        identifier = self.publish()
        self.engine.practice_store = PracticeStore(self.root / 'practice.sqlite3')
        self.engine.runtime.system_checkpoints = SimpleNamespace(capture=Mock(return_value={}),
                                                                 release=Mock(), collect=Mock())
        session = self.engine.start(identifier, self.uid)
        environment = session.lab.nodes[0].software.environment
        self.engine.save(session.id, self.uid)
        self.engine.stop(session.id, self.uid)
        restored = Engine(self.root / 'catalog', self.authoring.policy, self.engine.runtime,
                          PracticeStore(self.root / 'practice.sqlite3'))
        self.assertEqual(restored.sessions(self.uid)[0].lab.nodes[0].software.environment, environment)
        self.assertIn(environment, restored.software_image_ids())
        self.assertFalse(self.manager.image_leases)

    def test_missing_record_rebuilds_declared_software(self):
        lab = validate_lab(self.document)
        node = lab.nodes[0]
        lab = replace(lab, nodes=(replace(node, software=replace(node.software, environment='sha256:' + 'f' * 64)),))
        prepared = self.manager.prepare_lab(lab, self.uid, Event())
        self.assertNotEqual(prepared.nodes[0].software.environment, lab.nodes[0].software.environment)
        self.assertEqual(self.builder.calls, 1)

    def test_failure_never_launches_nodes(self):
        identifier = self.publish()
        self.builder.fail = True
        session = self.engine.start(identifier, self.uid)
        self.assertEqual(session.state, SessionState.FAILED)
        self.assertIn('Simulated apt failure', session.error)
        self.assertFalse(self.engine.runtime.active)

    def test_all_nodes_prepare_before_any_node_launches(self):
        second = dict(self.document['nodes'][0], id='server', software={'gui': True, 'apps': [], 'packages': ['nano']})
        self.document['nodes'].append(second)
        self.draft = self.authoring.save(self.draft['id'], self.draft['revision'], json.dumps(self.document), self.uid)
        identifier = self.publish()
        prepare = self.builder.prepare
        def fail_second(software, base, cancel, progress):
            self.assertFalse(self.engine.runtime.active)
            if software.packages:
                raise RuntimeFailure('Second machine installation failed')
            return prepare(software, base, cancel, progress)
        with patch.object(self.builder, 'prepare', side_effect=fail_second):
            session = self.engine.start(identifier, self.uid)
        self.assertEqual(session.state, SessionState.FAILED)
        self.assertFalse(self.engine.runtime.active)
        self.builder.fail = False
        retried = self.engine.reset(session.id, self.uid)
        self.assertEqual(retried.state, SessionState.RUNNING, retried.error)
        self.assertTrue(all(node.software.environment for node in retried.lab.nodes))
        self.assertEqual(self.builder.calls, 2)

    def test_deleted_cached_image_is_rebuilt(self):
        identifier = self.publish()
        first = self.engine.start(identifier, self.uid)
        self.engine.stop(first.id, self.uid)
        verify = self.builder.verify
        attempts = []
        def missing_once(software, receipt):
            attempts.append(receipt)
            if len(attempts) == 1:
                raise RuntimeFailure('Prepared software image is no longer available')
            return verify(software, receipt)
        with patch.object(self.builder, 'verify', side_effect=missing_once):
            second = self.engine.start(identifier, self.uid)
        self.assertEqual(second.state, SessionState.RUNNING, second.error)
        self.assertEqual(self.builder.calls, 2)

    def test_automatic_timeout_fails_without_launching(self):
        identifier = self.publish()
        self.builder.gate.clear()
        with patch('cyberlab.authoring.software.STARTUP_TIMEOUT_SECONDS', .03):
            session = self.engine.start(identifier, self.uid)
        self.assertEqual(session.state, SessionState.FAILED)
        self.assertFalse(self.engine.runtime.active)
        self.assertFalse(self.manager.automatic)

    def test_shutdown_cancels_background_preparation(self):
        identifier = self.publish()
        self.builder.gate.clear()
        with ThreadPoolExecutor(max_workers=2) as pool:
            started = pool.submit(self.engine.start, identifier, self.uid)
            try:
                deadline = monotonic() + 3
                while not self.builder.calls and monotonic() < deadline:
                    sleep(.01)
                pool.submit(self.manager.shutdown).result(timeout=2)
                self.assertEqual(started.result(timeout=2).state, SessionState.FAILED)
                self.assertFalse(self.engine.runtime.active)
            finally:
                self.builder.gate.set()

    def test_saved_system_skips_installation(self):
        lab = validate_lab(self.document)
        prepared = self.manager.prepare_lab(lab, self.uid, Event(), skip_nodes={'client': 'saved-image'})
        self.assertEqual(prepared, lab)
        self.assertEqual(self.builder.calls, 0)

    def test_concurrent_users_share_cache_and_keep_capacity_limits(self):
        lab = validate_lab(self.document)
        self.builder.gate.clear()
        with ThreadPoolExecutor(max_workers=2) as pool:
            first = pool.submit(self.manager.prepare_lab, lab, self.uid, Event())
            second = None
            try:
                deadline = monotonic() + 3
                while not self.builder.calls and monotonic() < deadline:
                    sleep(.01)
                with self.assertRaisesRegex(RuntimeFailure, 'current software preparation'):
                    self.manager.prepare_lab(lab, self.uid, Event())
                second = pool.submit(self.manager.prepare_lab, lab, self.uid + 1, Event())
                deadline = monotonic() + 3
                while len(self.manager.automatic) != 2 and monotonic() < deadline:
                    sleep(.01)
                with self.assertRaisesRegex(RuntimeFailure, 'capacity reached'):
                    self.manager.prepare_lab(lab, self.uid + 2, Event())
            finally:
                self.builder.gate.set()
            self.assertEqual(first.result(timeout=3), second.result(timeout=3))
            self.assertEqual(self.builder.calls, 1)
            self.assertFalse(self.manager.automatic)

    def test_lifecycle_waits_longer_without_changing_read_timeouts(self):
        async def check():
            wait_for = asyncio.wait_for
            for method, body, timeout in [('StartLab', ['fixture'], STARTUP_TIMEOUT_SECONDS + 180),
                                          ('GetSession', ['fixture'], 180)]:
                bus = SimpleNamespace(call=AsyncMock(return_value=SimpleNamespace(
                    message_type=MessageType.METHOD_RETURN, signature=METHODS[method][1], body=[{}])))
                with patch('cyberlab_cli.main.asyncio.wait_for', wraps=wait_for) as waited:
                    await request(bus, method, body)
                    self.assertEqual(waited.call_args.kwargs['timeout'], timeout)
        asyncio.run(check())

    def test_start_over_private_dbus_waits_without_blocking_status(self):
        identifier = self.publish()
        self.builder.gate.clear()
        async def check():
            process = subprocess.Popen(['dbus-daemon', '--session', '--nofork', '--print-address=1'], stdout=subprocess.PIPE, text=True)
            bus = client = task = None
            try:
                address = process.stdout.readline().strip()
                bus = await MessageBus(bus_address=address).connect()
                await bus.request_name(BUS_NAME)
                server = Server(bus, self.engine, {self.uid}, self.authoring)
                bus.add_message_handler(server.handle)
                client = await MessageBus(bus_address=address).connect()
                task = asyncio.create_task(request(client, 'StartLabWithParameters', [identifier, {}]))
                deadline = monotonic() + 3
                while not self.builder.calls and monotonic() < deadline:
                    await asyncio.sleep(.01)
                sessions = await asyncio.wait_for(request(client, 'ListSessions', []), 1)
                self.assertEqual(sessions[0]['state'], 'PREPARING')
                self.assertFalse(task.done())
                self.assertFalse(self.engine.runtime.active)
                self.builder.gate.set()
                result = await asyncio.wait_for(task, 2)
                self.assertEqual(result['state'], 'RUNNING')
                self.assertEqual(result['prepared_gui_nodes'], ['client'])
            finally:
                self.builder.gate.set()
                if task is not None and not task.done():
                    await asyncio.wait_for(task, 3)
                if client:
                    client.disconnect()
                    await client.wait_for_disconnect()
                if bus:
                    bus.disconnect()
                    await bus.wait_for_disconnect()
                process.terminate()
                process.wait(timeout=5)
                process.stdout.close()
        asyncio.run(check())

    def test_status_and_stop_remain_available_during_installation(self):
        identifier = self.publish()
        self.builder.gate.clear()
        with ThreadPoolExecutor(max_workers=2) as pool:
            started = pool.submit(self.engine.start, identifier, self.uid)
            try:
                deadline = monotonic() + 3
                while not self.builder.calls and monotonic() < deadline:
                    sleep(.01)
                self.assertEqual(self.builder.calls, 1)
                sessions = pool.submit(self.engine.sessions, self.uid).result(timeout=1)
                self.assertEqual(sessions[0].state, SessionState.PREPARING)
                self.assertFalse(self.engine.runtime.active)
                stopped = pool.submit(self.engine.stop, sessions[0].id, self.uid).result(timeout=1)
                self.assertEqual(stopped.state, SessionState.STOPPED)
            finally:
                self.builder.gate.set()
            self.assertEqual(started.result(timeout=3).state, SessionState.STOPPED)
            self.assertFalse(self.engine.runtime.active)


if __name__ == '__main__':
    unittest.main()
