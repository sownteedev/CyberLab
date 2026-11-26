"""Native display unit checks using temporary state, never Docker or host credentials."""

import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).resolve().parents[3]))

import asyncio
from contextlib import redirect_stdout
import io
import json
import os
import socket
import stat
import struct
import tempfile
from types import SimpleNamespace
import unittest
from threading import Event
from unittest.mock import AsyncMock, patch

from tools.tests.unit import check_desktops
from cyberlab.runtime.native_display import NativeDisplays
from cyberlab import host_display, xwayland
from cyberlab.x11 import authority, display_number
from cyberlab_cli import desktop, gui_environment, gui_preferences
from tools.install import upgrade_runtime
from tools.install import runtime_admin


class ContextChecks(unittest.TestCase):
    def test_pending_start_keeps_scoped_authorization_alive_and_stops(self):
        context = {**self.payload, 'uid': os.getuid(), 'identity': self.identity}
        repeated = Event()
        def probe(payload, uid):
            self.assertEqual(payload['cookie'], self.payload['cookie'])
            self.assertEqual(payload['operation'], 'probe')
            self.assertEqual(uid, os.getuid())
            if self.helper.call_count >= 2:
                repeated.set()
            return {'ready': True}
        self.helper.side_effect = probe
        with self.native.keepalive(context, interval=.01):
            self.assertTrue(repeated.wait(1))
        calls = self.helper.call_count
        self.assertGreaterEqual(calls, 2)
        repeated.clear()
        self.assertFalse(repeated.wait(.05))
        with self.native.keepalive({'fallback': 'test'}):
            pass
        self.assertEqual(self.helper.call_count, calls)

    def test_pending_start_probe_failure_keeps_fallback_available(self):
        self.helper.side_effect = ValueError('display unavailable')
        context = {**self.payload, 'uid': os.getuid(), 'identity': self.identity}
        with self.native.keepalive(context, interval=.01):
            pass

    def setUp(self):
        self.temporary = tempfile.TemporaryDirectory(prefix='cyberlab-native-check-')
        self.addCleanup(self.temporary.cleanup)
        self.clock = [100.0]
        self.native = NativeDisplays(Path(self.temporary.name) / 'leases', clock=lambda: self.clock[0])
        self.identity = {'socket': '/tmp/.X11-unix/X42', 'inode': 123, 'device': 1, 'leader': '1234', 'process': 2345}
        self.payload = {'display': ':42.1', 'login': 'session-test', 'cookie': '12' * 16, 'authorization': 12}
        self.session = SimpleNamespace(id='fixture-session', owner_uid=os.getuid(), lab=SimpleNamespace(nodes=[
            SimpleNamespace(id=name, software=SimpleNamespace(gui=gui), user=SimpleNamespace(uid=os.getuid(), gid=os.getgid()))
            for name, gui in (('gui', True), ('terminal', False))]))
        self.verify = patch('cyberlab.runtime.native_display.verify_display', return_value=self.identity).start()
        self.helper = patch('cyberlab.runtime.native_display.helper', side_effect=self.operation).start()
        self.relay = patch('cyberlab.runtime.native_display.DisplayRelay').start()
        self.relay.return_value.alive = True
        patch('cyberlab.x11.NATIVE_X11_ENABLED', True).start()
        self.addCleanup(patch.stopall)

    def operation(self, payload, uid):
        if payload.get('operation') == 'generate':
            return {'cookie': '34' * 16, 'authorization': 34}
        return {'ready': True}

    def context(self):
        token = self.native.register(json.dumps(self.payload), os.getuid(), ':test.1')
        return self.native.take(token, os.getuid(), ':test.1')

    def test_owner_sender_expiration_and_one_use(self):
        token = self.native.register(json.dumps(self.payload), os.getuid(), ':test.1')
        for uid, sender in ((os.getuid()+1, ':test.1'), (os.getuid(), ':test.2')):
            with self.assertRaises(ValueError):
                self.native.take(token, uid, sender)
        self.native.take(token, os.getuid(), ':test.1')
        with self.assertRaises(ValueError):
            self.native.take(token, os.getuid(), ':test.1')
        token = self.native.register(json.dumps(self.payload), os.getuid(), ':test.1')
        self.clock[0] += 31
        with self.assertRaises(ValueError):
            self.native.take(token, os.getuid(), ':test.1')

    def test_native_mounts_only_gui_node_and_no_secrets_in_status(self):
        self.native.prepare(self.session, self.context())
        gui, terminal = self.session.lab.nodes
        options = self.native.options(self.session, gui)
        self.assertEqual(len(options['mounts']), 2)
        self.assertTrue(all(mount['ReadOnly'] for mount in options['mounts']))
        self.assertEqual(self.native.options(self.session, terminal), {})
        self.assertEqual(self.native.environment(self.session, gui)['DISPLAY'], ':42.1')
        status = self.native.status(self.session, 'gui')
        self.assertEqual(status['backend'], 'native-x11')
        self.assertNotIn('cookie', json.dumps(status))
        record = self.native.nodes[(self.session.id, 'gui')]
        self.assertEqual((record['directory'] / 'lease.json').stat().st_mode & 0o777, 0o600)
        self.assertEqual((record['directory'] / 'Xauthority').stat().st_mode & 0o777, 0o400)

    def test_no_context_retains_xpra_without_files(self):
        self.native.prepare(self.session, None)
        self.assertEqual(self.native.status(self.session, 'gui')['backend'], 'xpra')
        self.assertFalse(self.native.root.exists())

    def test_failure_preserves_session_and_uses_xpra(self):
        context = self.context()
        self.helper.side_effect = ValueError('fixture failure')
        self.native.prepare(self.session, context)
        status = self.native.status(self.session, 'gui')
        self.assertEqual(status['backend'], 'xpra')
        self.assertTrue(status['fallback_reason'])

    def test_explicit_xpra_never_uses_host_helper(self):
        token = self.native.register(json.dumps({'fallback': '', 'requested_backend': 'xpra'}), os.getuid(), ':test.1')
        self.native.prepare(self.session, self.native.take(token, os.getuid(), ':test.1'))
        self.helper.assert_not_called()
        self.verify.assert_not_called()

    def test_stop_cleans_only_target_session(self):
        self.native.prepare(self.session, self.context())
        other = SimpleNamespace(id='another', owner_uid=os.getuid(), lab=self.session.lab)
        self.native.prepare(other, self.context())
        self.native.remove(self.session.id)
        self.assertNotIn((self.session.id, 'gui'), self.native.nodes)
        self.assertTrue(self.native.nodes[('another', 'gui')]['directory'].exists())
        self.native.remove(other.id)
        self.assertEqual(list(self.native.root.iterdir()), [])

    def test_logout_revokes_but_does_not_remove_container(self):
        self.native.prepare(self.session, self.context())
        self.verify.side_effect = ValueError('logged out')
        self.native.poll()
        self.assertFalse(self.native.status(self.session, 'gui')['ready'])
        self.assertTrue(self.native.nodes[(self.session.id, 'gui')]['directory'].exists())

    def test_wayland_changed_server_is_never_used_for_revocation(self):
        self.identity.update(server='Xwayland', start_time='100')
        self.native.prepare(self.session, self.context())
        self.helper.reset_mock()
        self.verify.return_value = {**self.identity, 'start_time': '200'}
        self.native.remove(self.session.id)
        self.helper.assert_not_called()
        self.assertEqual(list(self.native.root.iterdir()), [])

    def test_wayland_same_server_revokes_lease(self):
        self.identity.update(server='Xwayland', start_time='100')
        self.native.prepare(self.session, self.context())
        self.helper.reset_mock()
        self.native.remove(self.session.id)
        self.assertEqual(self.helper.call_args.args[0]['operation'], 'revoke')

    def test_wayland_mounts_private_relay_and_keeps_xpra_fallback(self):
        self.identity.update(server='Xwayland', start_time='100')
        self.relay.return_value.path = Path('/private/lease/Xsocket')
        self.native.prepare(self.session, self.context())
        node = self.session.lab.nodes[0]
        options = self.native.options(self.session, node)
        self.assertEqual(options['mounts'][0]['Source'], '/private/lease/Xsocket')
        self.assertEqual(options['mounts'][0]['Target'], self.identity['socket'])
        self.assertEqual(self.native.status(self.session, node.id)['transport'], 'private-x11-relay')
        with patch('cyberlab.runtime.workspace.execute', side_effect=ValueError('fixture failure')):
            self.native.verify_guest(SimpleNamespace(client=SimpleNamespace(api=None)), self.session, node, SimpleNamespace(id='fixture'))
        self.assertEqual(self.native.status(self.session, node.id)['backend'], 'xpra')
        self.relay.return_value.stop.assert_called_once()
        self.native.remove(self.session.id)
        self.relay.return_value.close.assert_called_once()

    def test_relay_start_failure_keeps_xpra_without_mounts(self):
        self.identity.update(server='Xwayland', start_time='100')
        self.relay.side_effect = ValueError('fixture relay unavailable')
        self.native.prepare(self.session, self.context())
        self.assertEqual(self.native.options(self.session, self.session.lab.nodes[0]), {})
        self.assertIn('xwayland-relay', self.native.status(self.session, 'gui')['fallback_reason'])
        self.assertEqual(list(self.native.root.iterdir()), [])

    def test_dead_relay_disconnects_and_reconnect_reuses_listener(self):
        self.identity.update(server='Xwayland', start_time='100')
        context = self.context()
        self.native.prepare(self.session, context)
        self.relay.return_value.alive = False
        self.native.poll()
        self.assertFalse(self.native.status(self.session, 'gui')['ready'])
        self.native.reconnect(self.session, 'gui', context)
        self.relay.return_value.restart.assert_called_once()
        self.assertTrue(self.native.status(self.session, 'gui')['ready'])

    def test_changed_server_reconnect_requires_new_container(self):
        context = self.context()
        self.native.prepare(self.session, context)
        context['identity'] = {**self.identity, 'inode': 999}
        with self.assertRaisesRegex(ValueError, 'X server changed'):
            self.native.reconnect(self.session, 'gui', context)

    def test_restart_cleans_only_private_lease_directory(self):
        self.native.prepare(self.session, self.context())
        restored = NativeDisplays(self.native.root)
        restored.cleanup()
        self.assertEqual(list(self.native.root.iterdir()), [])

    def test_test_runtime_disabled(self):
        native = NativeDisplays(None)
        with self.assertRaises(ValueError):
            native.register(json.dumps(self.payload), os.getuid(), ':test.1')
        native.cleanup()

    def test_authority_rejects_paths_remote_and_bad_cookies(self):
        for display in ('localhost:10', 'host:0', '../X0', ':0/../../tmp', 'unix:1'):
            with self.assertRaises(ValueError):
                display_number(display)
        self.assertEqual(display_number(':42.1'), '42')
        self.assertIn(b'MIT-MAGIC-COOKIE-1', authority(':42', '12' * 16))
        with self.assertRaises(ValueError):
            authority(':42', '00')


class PreferenceChecks(unittest.TestCase):
    def test_atomic_preferences_invalid_config_and_spaces(self):
        with tempfile.TemporaryDirectory(prefix='cyberlab config ') as root, patch.dict(os.environ, {'XDG_CONFIG_HOME': root}):
            self.assertEqual(gui_preferences.preference()['preferred'], 'auto')
            self.assertEqual(gui_preferences.preference('xpra')['preferred'], 'xpra')
            path = Path(root) / 'cyberlab/gui.json'
            self.assertEqual(path.stat().st_mode & 0o777, 0o600)
            path.write_text('broken')
            self.assertTrue(gui_preferences.preference()['warning'])
            self.assertEqual(path.read_text(), 'broken')
            with self.assertRaises(ValueError):
                gui_preferences.preference('sh -c injected')

    def test_native_without_xpra_and_wayland_requires_verified_xwayland(self):
        with patch('cyberlab_cli.gui_preferences.preference', return_value={'preferred': 'auto', 'warning': ''}), \
             patch('cyberlab.x11.NATIVE_X11_ENABLED', True), \
             patch('cyberlab.host_display.login_session', return_value={'Id': 'fixture', 'Type': 'x11'}), \
             patch('cyberlab.host_display.verify_display', return_value={}) as verified, patch('cyberlab.host_display.helper'), \
             patch.object(gui_environment, 'probe', return_value={'ready': True}), \
             patch.dict(os.environ, {'DISPLAY': ':42', 'XDG_SESSION_TYPE': 'x11', 'WAYLAND_DISPLAY': ''}, clear=True):
            self.assertEqual(gui_environment.inspect_environment()['backend'], 'native-x11')
            verified.assert_called_once()
            verified.reset_mock()
            with patch.dict(os.environ, {'WAYLAND_DISPLAY': 'wayland-1'}):
                self.assertEqual(gui_environment.inspect_environment()['backend'], 'xpra')
                verified.assert_called_once()

    def test_wayland_direct_and_forced_xpra(self):
        with patch('cyberlab_cli.gui_preferences.preference', return_value={'preferred': 'auto', 'warning': ''}) as preference, \
             patch('cyberlab.host_display.login_session', return_value={'Id': 'fixture', 'Type': 'wayland'}), \
             patch('cyberlab.host_display.verify_display', return_value={'server': 'Xwayland'}) as verified, \
             patch('cyberlab.host_display.helper') as helper, \
             patch.object(gui_environment, 'probe', return_value={'ready': True}), \
             patch.dict(os.environ, {'DISPLAY': ':42', 'XDG_SESSION_TYPE': 'wayland', 'WAYLAND_DISPLAY': 'wayland-1'}, clear=True):
            report = gui_environment.inspect_environment()
            self.assertEqual(report['backend'], 'native-x11')
            self.assertEqual(report['display_server'], 'Xwayland')
            self.assertTrue(report['native_ready'])
            verified.reset_mock()
            helper.reset_mock()
            self.assertEqual(gui_environment.inspect_environment(force_xpra=True)['backend'], 'xpra')
            preference.return_value = {'preferred': 'xpra', 'warning': ''}
            self.assertEqual(gui_environment.inspect_environment()['backend'], 'xpra')
            verified.assert_not_called()
            helper.assert_not_called()

    def test_wayland_failure_falls_back_without_authorization(self):
        with patch('cyberlab_cli.gui_preferences.preference', return_value={'preferred': 'auto', 'warning': ''}), \
             patch('cyberlab.host_display.login_session', return_value={'Id': 'fixture', 'Type': 'wayland'}), \
             patch('cyberlab.host_display.verify_display', side_effect=ValueError('wrong owner')), \
             patch('cyberlab.host_display.helper') as helper, \
             patch.object(gui_environment, 'probe', return_value={'ready': True}), \
             patch.dict(os.environ, {'DISPLAY': ':42', 'XDG_SESSION_TYPE': 'wayland'}, clear=True):
            report = gui_environment.inspect_environment()
            self.assertEqual(report['backend'], 'xpra')
            self.assertIn('XWayland', report['fallback_reason'])
            helper.assert_not_called()


class WaylandIdentityChecks(unittest.TestCase):
    def test_process_owner_and_start_time(self):
        self.assertTrue(xwayland.process_state(os.getpid(), os.getuid())['start_time'].isdigit())
        with self.assertRaises(ValueError):
            xwayland.process_state(os.getpid(), os.getuid() + 1)

    def test_only_named_listening_stream_socket_matches(self):
        entries = 'header\n0: 2 0 00010000 0001 01 111 /tmp/.X11-unix/X42\n'
        entries += '0: 2 0 00000000 0001 03 222 /tmp/.X11-unix/X42\n'
        entries += '0: 2 0 00010000 0001 01 333 @/tmp/.X11-unix/X42\n'
        with patch.object(Path, 'read_text', return_value=entries):
            self.assertEqual(xwayland.listener_inodes(Path('/tmp/.X11-unix/X42')), {'111'})

    def test_closed_descriptor_does_not_hide_listener(self):
        with patch.object(Path, 'iterdir', return_value=iter([Path('/proc/42/fd/3'), Path('/proc/42/fd/4')])), \
             patch.object(Path, 'readlink', side_effect=[FileNotFoundError(), Path('socket:[111]')]):
            self.assertTrue(xwayland.owns_listener(42, {'111'}))

    def test_activated_listener_requires_trusted_child_and_same_inode(self):
        state = {'parent': 10, 'start_time': '123'}
        trusted = SimpleNamespace(st_mode=stat.S_IFREG | 0o755, st_uid=0)
        with patch.object(xwayland, 'process_state', return_value=state), \
             patch.object(xwayland, 'server_candidates', return_value=[(20, state)]), \
             patch.object(xwayland, 'listener_inodes', return_value={'111'}), \
             patch.object(xwayland, 'owns_listener', return_value=True) as owns, \
             patch.object(Path, 'resolve', return_value=Path('/usr/bin/Xwayland')) as executable, \
             patch.object(Path, 'stat', return_value=trusted) as info:
            identity = xwayland.verified_server(Path('/tmp/.X11-unix/X42'), 10, 1000)
            self.assertEqual((identity['peer'], identity['process']), (10, 20))
            for binary, owner, mode, listener in (
                ('/tmp/Xwayland', 0, 0o755, True),
                ('/usr/bin/Xwayland', 1000, 0o755, True),
                ('/usr/bin/Xwayland', 0, 0o777, True),
                ('/usr/bin/Xwayland', 0, 0o755, False),
            ):
                executable.return_value = Path(binary)
                info.return_value = SimpleNamespace(st_mode=stat.S_IFREG | mode, st_uid=owner)
                owns.return_value = listener
                with self.assertRaises(ValueError):
                    xwayland.verified_server(Path('/tmp/.X11-unix/X42'), 10, 1000)

    def test_reused_pid_rejected(self):
        state = {'parent': 10, 'start_time': '123'}
        with patch.object(xwayland, 'process_state', side_effect=[state, {**state, 'start_time': '124'}]), \
             patch.object(xwayland, 'server_candidates', return_value=[(20, state)]), \
             patch.object(xwayland, 'listener_inodes', return_value={'111'}), \
             patch.object(xwayland, 'owns_listener', return_value=True), \
             patch.object(Path, 'resolve', return_value=Path('/usr/bin/Xwayland')), \
             patch.object(Path, 'stat', return_value=SimpleNamespace(st_mode=stat.S_IFREG | 0o755, st_uid=0)):
            with self.assertRaisesRegex(ValueError, 'changed'):
                xwayland.verified_server(Path('/tmp/.X11-unix/X42'), 10, 1000)

    def test_wayland_socket_owner_and_replacement(self):
        directory = SimpleNamespace(st_mode=stat.S_IFDIR | 0o1777, st_uid=0)
        endpoint = SimpleNamespace(st_mode=stat.S_IFSOCK | 0o755, st_uid=1000, st_dev=1, st_ino=123)
        changed = SimpleNamespace(st_mode=stat.S_IFSOCK | 0o755, st_uid=1000, st_dev=1, st_ino=124)
        with patch.object(host_display, 'login_session', return_value={'Type': 'wayland'}), \
             patch.object(Path, 'lstat', side_effect=[directory, endpoint, endpoint]) as lstat, \
             patch.object(host_display.socket, 'socket') as connection, \
             patch.object(xwayland, 'verified_server', return_value={'process': 20, 'server': 'Xwayland'}) as verify:
            peer = connection.return_value.__enter__.return_value
            peer.getsockopt.return_value = struct.pack('3i', 10, 1000, 1000)
            self.assertEqual(host_display.verify_display(':42', 'fixture', 1000)['server'], 'Xwayland')
            lstat.side_effect = [directory, endpoint, endpoint]
            verify.side_effect = [xwayland.DisplayNotReady('starting'), {'process': 20, 'server': 'Xwayland'}]
            with patch.object(host_display, 'sleep') as sleep:
                self.assertEqual(host_display.verify_display(':42', 'fixture', 1000)['server'], 'Xwayland')
                sleep.assert_called_once_with(0.05)
            verify.side_effect = None
            lstat.side_effect = [directory, endpoint, changed]
            with self.assertRaisesRegex(ValueError, 'changed'):
                host_display.verify_display(':42', 'fixture', 1000)
            verify.reset_mock()
            lstat.side_effect = [directory, endpoint]
            peer.getsockopt.return_value = struct.pack('3i', 10, 1001, 1001)
            with self.assertRaisesRegex(ValueError, 'another user'):
                host_display.verify_display(':42', 'fixture', 1000)
            verify.assert_not_called()

class RelayChecks(unittest.IsolatedAsyncioTestCase):
    async def test_native_never_launches_xpra(self):
        request = AsyncMock(return_value=json.dumps({'backend': 'native-x11', 'ready': True}))
        with patch.object(desktop, 'viewer_path') as viewer, redirect_stdout(io.StringIO()) as output:
            await desktop.interact(None, request, 'session', 'gui')
        viewer.assert_not_called()
        self.assertEqual(json.loads(output.getvalue())['backend'], 'native-x11')

    async def test_bidirectional_relay_partial_writes_and_eof(self):
        local, remote = socket.socketpair()
        local.setblocking(False)
        remote.setblocking(False)
        received = bytearray()
        supplied = False
        async def request(bus, operation, arguments):
            nonlocal supplied
            if operation == 'ReadDesktop':
                if not supplied:
                    supplied = True
                    return [b'frame', False]
                return [b'', False]
            data = arguments[1][:2]
            received.extend(data)
            return len(data)
        try:
            task = asyncio.create_task(desktop.relay_display(None, request, 'handle', local))
            loop = asyncio.get_running_loop()
            await loop.sock_sendall(remote, b'keyboard')
            self.assertEqual(await asyncio.wait_for(loop.sock_recv(remote, 5), 1), b'frame')
            for _attempt in range(100):
                if received == b'keyboard':
                    break
                await asyncio.sleep(0.001)
            self.assertEqual(received, b'keyboard')
            remote.close()
            await asyncio.wait_for(task, 1)
        finally:
            local.close()
            remote.close()


class UpdaterChecks(unittest.TestCase):
    def test_effective_capabilities_not_only_bounding_set(self):
        healthy = 'CapPrm: c1\nCapEff: c1\nCapBnd: c1\nCapAmb: 80\nNoNewPrivs: 1\n'
        with patch.object(upgrade_runtime, 'run', return_value=SimpleNamespace(stdout='4242\n')), \
             patch.object(Path, 'read_text', return_value=healthy) as read:
            self.assertEqual(upgrade_runtime.verify_service_capabilities()['CapEff'], '00000000000000c1')
            for broken in (healthy.replace('CapPrm: c1', 'CapPrm: 41').replace('CapEff: c1', 'CapEff: 41'),
                           healthy.replace('CapEff: c1', 'CapEff: 2000c1'),
                           healthy.replace('CapBnd: c1', 'CapBnd: 2000c1'),
                           healthy.replace('CapAmb: 80', 'CapAmb: c1'),
                           healthy.replace('NoNewPrivs: 1', 'NoNewPrivs: 0'), ''):
                read.return_value = broken
                with self.assertRaises(RuntimeError):
                    upgrade_runtime.verify_service_capabilities()

    def test_installer_update_requests_reviewed_service_policy(self):
        stage = Path('/var/tmp/cyberlab-app-install-fixture')
        wheel = stage / 'cyberlab_engine-0.9.0-py3-none-any.whl'
        account = SimpleNamespace(pw_uid=1234, pw_dir='/nonexistent')
        arguments = ['runtime_admin.py', '--user', 'fixture', 'update',
                     '--stage', str(stage), '--wheel', str(wheel)]
        with patch.object(sys, 'argv', arguments), \
             patch.object(runtime_admin, 'account_for', return_value=account), \
             patch.object(runtime_admin.os, 'geteuid', return_value=0), \
             patch.object(runtime_admin.os, 'umask'), \
             patch.object(Path, 'lstat', return_value=SimpleNamespace(st_mode=stat.S_IFDIR | 0o700, st_uid=0)), \
             patch.object(Path, 'is_symlink', return_value=False), \
             patch.object(Path, 'exists', return_value=False), \
             patch.object(runtime_admin, 'retain_backup') as retain, \
             patch.object(runtime_admin, 'record_installation') as record, \
             patch.object(runtime_admin, 'tool') as load_tool:
            self.assertEqual(runtime_admin.main(), 0)
            load_tool.assert_called_once_with('upgrade_runtime')
            load_tool.return_value.upgrade.assert_called_once_with(
                wheel, account.pw_uid, stage, repair_service_policy=True,
                wheelhouse=stage / 'wheels', lock_fd=None, offline=False,
                verify_callback=unittest.mock.ANY)
            load_tool.return_value.upgrade.call_args.kwargs['verify_callback']()
            record.assert_called_once_with(account, stage, wheel)
            retain.assert_called_once_with(stage)

    def test_service_migration_preserves_private_tmp_and_rejects_custom_policy(self):
        with tempfile.TemporaryDirectory() as root:
            unit, dropin = Path(root) / 'service', Path(root) / 'authoring.conf'
            unit.write_text('[Service]\nPrivateTmp=true\nCapabilityBoundingSet=CAP_CHOWN\n')
            dropin.write_text('[Service]\nUMask=0077\n')
            with patch.object(upgrade_runtime, 'UNIT', unit), patch.object(upgrade_runtime, 'AUTHORING_DROPIN', dropin), \
                 patch.object(upgrade_runtime, 'check_admin_path'):
                changes = upgrade_runtime.service_policy_updates()
                self.assertEqual(len(changes), 1)
                self.assertIn(b'PrivateTmp=true', changes[0][2])
                self.assertIn(b'CAP_SETUID CAP_SETGID', changes[0][2])
                self.assertIn(b'BindReadOnlyPaths=-/tmp/.X11-unix', changes[0][2])
                self.assertIn(b'AmbientCapabilities=CAP_SETUID', changes[0][2])
                for destination, previous, current in changes:
                    destination.write_bytes(current)
                self.assertEqual(upgrade_runtime.service_policy_updates(), [])
                unit.write_text(unit.read_text().replace('AmbientCapabilities=CAP_SETUID', 'AmbientCapabilities=CAP_SYS_ADMIN'))
                with self.assertRaises(ValueError):
                    upgrade_runtime.service_policy_updates()
                unit.write_text('[Service]\nCapabilityBoundingSet=CAP_SYS_ADMIN\n')
                with self.assertRaises(ValueError):
                    upgrade_runtime.service_policy_updates()


if __name__ == '__main__':
    unittest.main(verbosity=2)
