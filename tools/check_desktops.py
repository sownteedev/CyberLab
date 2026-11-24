#!/usr/bin/env python3
"""Isolated desktop checks: no Docker, host display or production data."""

import asyncio
from contextlib import redirect_stdout
import importlib.util
import io
import json
import os
import select
import shutil
import signal
import socket
import subprocess
from pathlib import Path
import sys
import tempfile
from types import SimpleNamespace
import unittest
from unittest.mock import Mock, patch
import xml.etree.ElementTree as ET

sys.dont_write_bytecode = True
ROOT = Path(__file__).resolve().parents[1]
sys.path[:0] = [str(ROOT / name) for name in ('engine', 'daemon', 'cli', 'tools')]
spec = importlib.util.spec_from_file_location('cyberlab.schemas', ROOT / 'schemas/__init__.py',
                                             submodule_search_locations=[str(ROOT / 'schemas')])
sys.modules['cyberlab.schemas'] = importlib.util.module_from_spec(spec)
spec.loader.exec_module(sys.modules['cyberlab.schemas'])

from cyberlab.desktop import Desktops
from cyberlab.runtime import RuntimeFailure
from cyberlab.service import SessionBusy
from cyberlab.runtime.desktop import BRIDGE, SETUP, STATUS, PACKAGES, DesktopRuntime
from cyberlab.runtime.docker_desktop import DockerDesktopStream
from cyberlab.lab.workstation import UBUNTU_IMAGE, UBUNTU_USER
from cyberlab_cli import desktop as client
from cyberlab_cli import gui_environment
from cyberlab_cli.xpra_client import compatible_hello, compatible_metadata
from cyberlab_ipc import METHODS
from cyberlab_cli.main import request, ClientError
import cyberlab_cli.main as cli_main
from cyberlab_ipc import BUS_NAME
from cyberlabd.server import Server
from dbus_next.aio import MessageBus
import check_session_state

class DesktopChecks(unittest.TestCase):
    def setUp(self):
        self.stream = Mock()
        self.stream.exited.return_value = False
        self.stream.read.return_value = (b'RFB 003.008\n', False)
        self.stream.write.side_effect = len
        self.runtime = SimpleNamespace(desktop=Mock())
        self.runtime.desktop.open.return_value = (self.stream, b'12345678')
        self.now = 0
        self.desktops = Desktops(self.runtime, clock=lambda: self.now)
        self.session = SimpleNamespace(id='a' * 32)

    def open(self):
        return self.desktops.open(self.session, 'client', 1234, ':1.1')[0]

    def test_owner_and_connection_are_required(self):
        handle = self.open()
        for uid, sender in ((4321, ':1.1'), (1234, ':1.2')):
            with self.assertRaises(RuntimeFailure):
                self.desktops.operate('read', handle, uid, sender)
        self.assertEqual(self.desktops.operate('read', handle, 1234, ':1.1'), [b'RFB 003.008\n', False])

    def test_readiness_is_not_assumed_before_authenticated_client_confirmation(self):
        handle = self.open()
        self.assertFalse(self.desktops.channels[handle].ready)
        with self.assertRaises(RuntimeFailure):
            self.desktops.operate('ready', handle, 1234, ':another')
        self.assertTrue(self.desktops.operate('ready', handle, 1234, ':1.1'))
        self.assertTrue(self.desktops.channels[handle].ready)

    def test_writes_are_bounded_and_acknowledged(self):
        handle = self.open()
        self.assertEqual(self.desktops.operate('write', handle, 1234, ':1.1', b'hello'), 5)
        for invalid in ('string', b'x' * 65537):
            with self.assertRaises(ValueError):
                self.desktops.operate('write', handle, 1234, ':1.1', invalid)

    def test_busy_expiration_and_reopen(self):
        handle = self.open()
        with self.assertRaises(RuntimeFailure):
            self.open()
        self.now = 31
        with self.assertRaises(RuntimeFailure):
            self.desktops.operate('read', handle, 1234, ':1.1')
        self.stream.close.assert_called_once()
        self.assertNotEqual(self.open(), handle)

    def test_stop_ends_only_selected_session(self):
        handle = self.open()
        other = Mock()
        other.exited.return_value = False
        self.runtime.desktop.open.return_value = (other, b'12345678')
        self.desktops.open(SimpleNamespace(id='b' * 32), 'client', 1234, ':1.2')
        self.desktops.close_session(self.session.id)
        with self.assertRaises(RuntimeFailure):
            self.desktops.operate('read', handle, 1234, ':1.1')
        self.stream.close.assert_called_once()
        other.close.assert_not_called()

    def test_disconnect_does_not_stop_lab(self):
        handle = self.open()
        self.desktops.operate('close', handle, 1234, ':1.1')
        self.assertNotIn(handle, self.desktops.channels)
        self.stream.close.assert_called_once()

    def test_dead_bridge_is_reaped_before_status_or_reopen(self):
        handle = self.open()
        self.stream.exited.return_value = True
        self.desktops.expire(inspect_streams=True)
        self.assertNotIn(handle, self.desktops.channels)
        self.stream.close.assert_called_once()
        self.stream.exited.return_value = False
        self.assertNotEqual(self.open(), handle)

    def test_eof_releases_channel_and_returns_last_bytes(self):
        handle = self.open()
        self.stream.read.return_value = (b'last frame', True)
        self.assertEqual(self.desktops.operate('read', handle, 1234, ':1.1'), [b'last frame', True])
        self.assertNotIn(handle, self.desktops.channels)
        self.stream.close.assert_called_once()

    def test_failed_io_releases_only_its_channel(self):
        for operation in ('read', 'write'):
            with self.subTest(operation=operation):
                self.setUp()
                handle = self.open()
                getattr(self.stream, operation).side_effect = RuntimeFailure('stream lost')
                with self.assertRaisesRegex(RuntimeFailure, 'reconnect GUI'):
                    self.desktops.operate(operation, handle, 1234, ':1.1', b'input')
                self.assertNotIn(handle, self.desktops.channels)
                self.stream.close.assert_called_once()

    def test_live_bridge_is_not_replaced_or_inspected_on_every_chunk(self):
        handle = self.open()
        self.desktops.expire(inspect_streams=True)
        with self.assertRaises(RuntimeFailure):
            self.open()
        self.stream.exited.reset_mock()
        self.desktops.operate('read', handle, 1234, ':1.1')
        self.stream.exited.assert_not_called()
        self.stream.close.assert_not_called()

    def test_contract_matches_xml(self):
        root = ET.parse(ROOT / 'daemon/cyberlab_ipc/org.ptit.CyberLab1.xml')
        for method in root.findall('.//method'):
            name = method.attrib['name']
            if 'Desktop' not in name:
                continue
            signature = tuple(''.join(argument.attrib['type'] for argument in method.findall('arg')
                              if argument.attrib.get('direction', 'in') == direction) for direction in ('in', 'out'))
            self.assertEqual(METHODS[name], signature)

    def test_guest_programs_compile_and_no_host_forwarding(self):
        self.assertIn('python3-pil', PACKAGES)
        self.assertIn('from PIL import Image', STATUS)
        self.assertIn('os.dup2(errors.fileno(), 2)', BRIDGE)
        for code in (SETUP, STATUS, BRIDGE):
            compile(code, '<guest-desktop>', 'exec')
        self.assertIn('-nolisten tcp', SETUP)
        self.assertIn("'--auth=file:filename='", SETUP)
        self.assertIn("'--socket-permissions=600'", SETUP)
        for flag in ('clipboard', 'file-transfer', 'open-files', 'open-url', 'webcam', 'dbus-proxy', 'start-new-commands'):
            self.assertIn('--' + flag + '=no', SETUP)
        self.assertNotIn('x11vnc', SETUP)
        self.assertNotIn('openbox', SETUP)
        self.assertNotIn('tty', BRIDGE)

    def test_guest_readiness_requires_imaging_not_only_executables(self):
        import builtins
        original_import = builtins.__import__
        for available in (False, True):
            def imports(name, *arguments, **options):
                if name == 'PIL':
                    if available:
                        return SimpleNamespace(Image=object())
                    raise ImportError('Pillow absent')
                return original_import(name, *arguments, **options)
            output = io.StringIO()
            with patch('builtins.__import__', imports), patch('shutil.which', return_value='/fixture/bin/tool'), redirect_stdout(output):
                exec(compile(STATUS, '<guest-status>', 'exec'), {})
            self.assertEqual(json.loads(output.getvalue())['ready'], available)

    def test_guest_bridge_preserves_binary_bytes_over_pipes(self):
        with tempfile.TemporaryDirectory() as temporary, socket.socket(socket.AF_UNIX) as listener:
            listener.bind(str(Path(temporary) / 'display.sock'))
            listener.listen(1)
            listener.settimeout(5)
            program = BRIDGE.replace(repr('/tmp/cyberlab-apps/display.sock'), repr(listener.getsockname()))
            process = subprocess.Popen([sys.executable, '-I', '-c', program], stdin=subprocess.PIPE, stdout=subprocess.PIPE,
                                       stderr=subprocess.DEVNULL, start_new_session=True)
            try:
                os.write(process.stdin.fileno(), b'hello')
                with listener.accept()[0] as connection:
                    connection.settimeout(5)
                    self.assertEqual(connection.recv(5), b'hello')
                    payload = bytes(range(256)) + b'\x10\x11\r\n\x00\x03\x04\xff'
                    connection.sendall(payload)
                    self.assertTrue(select.select([process.stdout], [], [], 5)[0])
                    self.assertEqual(os.read(process.stdout.fileno(), 1024), payload)
                    os.write(process.stdin.fileno(), payload)
                    received = b''
                    while len(received) < len(payload):
                        received += connection.recv(len(payload) - len(received))
                    self.assertEqual(received, payload)
            finally:
                process.stdin.close()
                process.stdout.close()
                if process.poll() is None:
                    process.terminate()
                process.wait(timeout=5)

    def test_runtime_rejects_non_workstation_and_uses_fixed_guest_argv(self):
        node = SimpleNamespace(id='client', image=UBUNTU_IMAGE, user=UBUNTU_USER)
        session = SimpleNamespace(lab=SimpleNamespace(nodes=[node]))
        runtime = Mock(workstation_images=frozenset())
        desktop = DesktopRuntime(runtime)
        with self.assertRaises(RuntimeFailure):
            desktop.status(session, 'client')
        runtime.workstation_images = {UBUNTU_IMAGE}
        container = runtime._workspace_container.return_value
        runtime.client.api.exec_create.return_value = {'Id': 'execution'}
        with patch('cyberlab.runtime.desktop.DockerDesktopStream') as stream, patch('cyberlab.runtime.desktop.execute', side_effect=[b'{"ready":true}', b'x' * 32]) as bounded:
            result, credential = desktop.open(session, 'client')
        self.assertEqual([call.kwargs['maximum'] for call in bounded.call_args_list], [256, 32])
        self.assertEqual(credential, b'x' * 32)
        self.assertEqual(result, stream.return_value)
        arguments = runtime.client.api.exec_create.call_args.kwargs
        self.assertEqual(arguments['user'], 'student')
        self.assertFalse(arguments['privileged'])
        self.assertFalse(arguments['tty'])
        self.assertFalse(runtime.client.api.exec_start.call_args.kwargs['tty'])
        self.assertEqual(arguments['environment']['DISPLAY'], ':99')
        self.assertEqual(arguments['cmd'][:3], ['/usr/bin/python3', '-I', '-c'])

    def test_missing_tools_do_not_open_stream(self):
        runtime = Mock(workstation_images={UBUNTU_IMAGE})
        node = SimpleNamespace(id='client', image=UBUNTU_IMAGE, user=UBUNTU_USER)
        runtime._workspace_container.return_value.exec_run.return_value = SimpleNamespace(exit_code=0, output=b'{"ready":false}')
        with patch('cyberlab.runtime.desktop.execute', return_value=b'{"ready":false}'), self.assertRaisesRegex(RuntimeFailure, 'Prepare desktop'):
            DesktopRuntime(runtime).open(SimpleNamespace(lab=SimpleNamespace(nodes=[node])), 'client')
        runtime.client.api.exec_create.assert_not_called()

    def test_prepare_uses_fixed_root_command_inside_selected_container(self):
        runtime = Mock(workstation_images={UBUNTU_IMAGE})
        node = SimpleNamespace(id='client', image=UBUNTU_IMAGE, user=UBUNTU_USER)
        runtime.client.api.exec_create.return_value = {'Id': 'prepare'}
        runtime.client.api.exec_inspect.return_value = {'Running': False, 'ExitCode': 0}
        runtime._workspace_container.return_value.exec_run.return_value = SimpleNamespace(exit_code=0, output=b'{"ready":true}')
        with patch('cyberlab.runtime.desktop.execute', return_value=b'{"ready":true}'):
            self.assertTrue(DesktopRuntime(runtime).prepare(SimpleNamespace(lab=SimpleNamespace(nodes=[node])), 'client'))
        arguments = runtime.client.api.exec_create.call_args.kwargs
        self.assertEqual(arguments['user'], '0:0')
        self.assertFalse(arguments['privileged'])
        self.assertEqual(arguments['cmd'][:5], ['/usr/bin/env', 'DEBIAN_FRONTEND=noninteractive', '/usr/bin/timeout', '150', '/bin/sh'])
        self.assertIn('apt-get install -y --no-install-recommends xpra xvfb xauth dbus-x11 fonts-dejavu-core', arguments['cmd'][-1])

    def test_preparation_failure_is_reported(self):
        runtime = Mock(workstation_images={UBUNTU_IMAGE})
        node = SimpleNamespace(id='client', image=UBUNTU_IMAGE, user=UBUNTU_USER)
        runtime.client.api.exec_create.return_value = {'Id': 'prepare'}
        runtime.client.api.exec_inspect.return_value = {'Running': False, 'ExitCode': 100}
        with self.assertRaisesRegex(RuntimeFailure, 'preparation did not finish'):
            DesktopRuntime(runtime).prepare(SimpleNamespace(lab=SimpleNamespace(nodes=[node])), 'client')

    def test_installer_native_viewer_package_mapping(self):
        for family, expected in [('arch', 'xpra'), ('debian', 'xpra'), ('fedora', 'xpra'), ('suse', 'xpra')]:
            result = subprocess.run(['bash', '-c', 'source "$1"; family="$2"; configure_packages; printf "%s\\n" "${host_packages[@]}"',
                                     'check', str(ROOT / 'tools/install/packages.sh'), family], capture_output=True, text=True, check=True)
            self.assertIn(expected, result.stdout.splitlines())

class BinaryDisplayChecks(unittest.TestCase):
    def setUp(self):
        connection, self.peer = socket.socketpair()
        self.api = Mock()
        self.api.exec_inspect.return_value = {'Running': False, 'ExitCode': 0}
        self.stream = DockerDesktopStream(self.api, 'fixture', connection)
        self.addCleanup(self.stream.close)
        self.addCleanup(self.peer.close)

    def frame(self, payload, channel=1):
        return bytes([channel, 0, 0, 0]) + len(payload).to_bytes(4, 'big') + payload

    def test_fragmented_headers_payloads_and_detach_sequence_are_transparent(self):
        payload = bytes(range(256)) + b'\x10\x11\x00\r\n'
        wire = self.frame(payload) + self.frame(b'ignored diagnostics', 2) + self.frame(b'end')
        received = bytearray()
        for offset in range(0, len(wire), 3):
            self.peer.sendall(wire[offset:offset + 3])
            output, ended = self.stream.read(65536)
            self.assertFalse(ended)
            received.extend(output)
        self.assertEqual(self.stream.write(payload), len(payload))
        self.assertEqual(self.peer.recv(65536), payload)
        self.peer.shutdown(socket.SHUT_WR)
        output, ended = self.stream.read(65536)
        received.extend(output)
        self.assertTrue(ended)
        self.assertEqual(received, payload + b'end')

    def test_large_frame_is_returned_in_bounded_chunks(self):
        payload = bytes(range(256)) * 400
        self.peer.sendall(self.frame(payload))
        self.peer.shutdown(socket.SHUT_WR)
        output = bytearray()
        for attempt in range(100):
            chunk, ended = self.stream.read(4096)
            self.assertLessEqual(len(chunk), 4096)
            output.extend(chunk)
            if ended:
                break
        self.assertTrue(ended)
        self.assertEqual(output, payload)

    def test_truncated_frame_is_not_reported_as_clean_eof(self):
        self.peer.sendall(self.frame(b'payload')[:-2])
        self.peer.shutdown(socket.SHUT_WR)
        self.stream.read(65536)
        with self.assertRaisesRegex(RuntimeFailure, 'Incomplete'):
            self.stream.read(65536)

    def test_invalid_header_is_rejected(self):
        self.peer.sendall(b'notframe')
        with self.assertRaisesRegex(RuntimeFailure, 'header'):
            self.stream.read(65536)

    def test_oversized_header_is_rejected_before_buffer_allocation(self):
        self.peer.sendall(b'\x01\0\0\0' + (16 * 1024 * 1024 + 1).to_bytes(4, 'big'))
        with self.assertRaisesRegex(RuntimeFailure, 'exceeds'):
            self.stream.read(65536)


class DesktopLifecycleChecks(check_session_state.SessionStateChecks):
    def test_failed_preparation_clears_busy_guard_and_keeps_session(self):
        self.runtime.desktop = Mock()
        def prepare(session, node):
            with self.assertRaises(SessionBusy):
                self.engine.stop(session.id, 1234)
            raise RuntimeFailure('apt failed')
        self.runtime.desktop.prepare.side_effect = prepare
        with self.assertRaisesRegex(RuntimeFailure, 'apt failed'):
            self.engine.prepare_desktop(self.session.id, 'client', 1234)
        self.assertNotIn(self.session.id, self.engine._checking)
        self.assertIn(self.session.id, self.runtime.active)

    def test_desktop_methods_check_owner_state_and_cleanup(self):
        desktop = Mock()
        stream = Mock()
        stream.exited.return_value = False
        desktop.open.return_value = (stream, b'12345678')
        self.runtime.desktop = desktop
        with self.assertRaises(Exception):
            self.engine.open_desktop(self.session.id, 'client', 4321, ':1.1')
        desktop.open.assert_not_called()
        handle, _ = self.engine.open_desktop(self.session.id, 'client', 1234, ':1.1')
        self.engine.stop(self.session.id, 1234)
        with self.assertRaises(RuntimeFailure):
            self.engine.desktop('read', handle, 1234, ':1.1')
        with self.assertRaises(RuntimeFailure):
            self.engine.open_desktop(self.session.id, 'client', 1234, ':1.1')

    def test_status_reaps_dead_ready_channel_without_replacing_live_viewer(self):
        stream = Mock()
        stream.exited.return_value = False
        self.runtime.desktop = Mock()
        self.runtime.desktop.status.return_value = {'backend': 'xpra', 'ready': True}
        self.runtime.desktop.open.return_value = (stream, b'x' * 32)
        handle, _ = self.engine.open_desktop(self.session.id, 'client', 1234, ':1.1')
        self.engine.desktop('ready', handle, 1234, ':1.1')
        self.assertTrue(self.engine.desktop_status(self.session.id, 'client', 1234)['attached'])
        stream.close.assert_not_called()
        stream.exited.return_value = True
        state = self.engine.desktop_status(self.session.id, 'client', 1234)
        self.assertFalse(state['attached'])
        self.assertFalse(state['opening'])
        stream.close.assert_called_once()
        self.assertIn(self.session.id, self.runtime.active)

class DesktopCommandExitChecks(unittest.TestCase):
    def invoke(self, command, result=None, error=None):
        from contextlib import redirect_stderr
        from unittest.mock import AsyncMock

        output, errors = io.StringIO(), io.StringIO()
        with patch.object(sys, 'argv', ['cyberlab', *command]), \
             patch.object(cli_main, 'run', AsyncMock(return_value=result, side_effect=error)), \
             redirect_stdout(output), redirect_stderr(errors):
            code = cli_main.main()
        return code, output.getvalue(), errors.getvalue()

    def test_unprepared_desktop_is_successful_status_not_failed_operation(self):
        for ready in (False, True):
            for viewer_ready in (False, True):
                report = {'backend': 'xpra', 'ready': ready, 'viewer_ready': viewer_ready}
                code, output, errors = self.invoke(['desktop-status', 'fixture', 'client'], report)
                self.assertEqual(code, 0)
                self.assertEqual(json.loads(output), report)
                self.assertEqual(errors, '')

    def test_status_request_failure_is_still_an_error(self):
        code, _, errors = self.invoke(['desktop-status', 'fixture', 'client'], error=ClientError('Daemon unavailable'))
        self.assertEqual(code, 1)
        self.assertIn('Daemon unavailable', errors)

    def test_failed_preparation_and_host_probe_keep_failure_exit_code(self):
        for command in (['prepare-desktop', 'fixture', 'client', '--yes'], ['gui-status']):
            code, output, _ = self.invoke(command, {'ready': False})
            self.assertEqual(code, 1)
            self.assertFalse(json.loads(output)['ready'])


class ViewerChecks(unittest.IsolatedAsyncioTestCase):
    async def test_private_dbus_desktop_round_trip_and_sender_isolation(self):
        fixture = check_session_state.SessionStateChecks('test_stop_is_idempotent')
        fixture.setUp()
        self.addCleanup(fixture.doCleanups)
        stream = Mock()
        stream.exited.return_value = False
        stream.read.return_value = (b'RFB 003.008\n', False)
        stream.write.side_effect = len
        fixture.runtime.desktop = Mock()
        fixture.runtime.desktop.open.return_value = (stream, b'12345678')
        fixture.runtime.desktop.status.return_value = {'ready': True}
        session = fixture.engine.start('fixture', os.getuid())
        process = subprocess.Popen(['dbus-daemon', '--session', '--nofork', '--print-address=1'],
                                   stdout=subprocess.PIPE, stderr=subprocess.DEVNULL, text=True, start_new_session=True)
        connections = []
        try:
            self.assertTrue(select.select([process.stdout], [], [], 5)[0])
            address = process.stdout.readline().strip()
            server_bus = await MessageBus(bus_address=address).connect()
            connections.append(server_bus)
            await server_bus.request_name(BUS_NAME)
            server = Server(server_bus, fixture.engine, {os.getuid()})
            server_bus.add_message_handler(server.handle)
            first = await MessageBus(bus_address=address).connect()
            second = await MessageBus(bus_address=address).connect()
            connections.extend([first, second])
            handle, credential = await request(first, 'OpenDesktop', [session.id, 'client'])
            self.assertEqual(credential, b'12345678')
            self.assertEqual(await request(first, 'ReadDesktop', [handle]), [b'RFB 003.008\n', False])
            self.assertEqual(await request(first, 'WriteDesktop', [handle, b'input']), 5)
            with self.assertRaises(ClientError):
                await request(second, 'ReadDesktop', [handle])
            with self.assertRaises(ClientError):
                await request(first, 'WriteDesktop', [handle, b'x' * 65537])
            await request(first, 'CloseDesktop', [handle])
            stream.close.assert_called_once()
            fixture.runtime.desktop.status.return_value = {'backend': 'xpra', 'ready': False}
            await self.assert_real_cli_opens_preparation_dialog(address, session.id)
            fixture.runtime.desktop.prepare.assert_not_called()
        finally:
            for bus in reversed(connections):
                bus.disconnect()
                await bus.wait_for_disconnect()
            process.terminate()
            process.wait(timeout=5)
            process.stdout.close()

    async def assert_real_cli_opens_preparation_dialog(self, address, session_id):
        executable = shutil.which('qs') or shutil.which('quickshell')
        self.assertIsNotNone(executable, 'Native Quickshell required for the end-to-end GUI preparation regression')
        bootstrap = ('import sys; sys.path[:0]=' + repr([str(ROOT / name) for name in ('cli', 'daemon', 'engine')]) + '; '
                     'from cyberlab_cli import gui_environment; '
                     'gui_environment.inspect_environment=lambda **kwargs: {"ready":True,"code":"ready"}; '
                     'from cyberlab_cli.main import main; sys.exit(main())')
        with tempfile.TemporaryDirectory(prefix='cyberlab-gui-preparation-ui-') as temporary:
            root = Path(temporary)
            for name in ('home', 'config', 'cache', 'data', 'runtime'):
                (root / name).mkdir(mode=0o700)
            configuration = '''//@ pragma UseQApplication
import QtQuick
import QtQuick.Controls.Basic
import Quickshell
import STUDIO as Studio
ShellRoot {
    Studio.Backend {
        id: backend
        capabilities: ["seamless-apps"]
        prefix: PREFIX
    }
    ApplicationWindow {
        visible: true
        width: 900; height: 700
        Studio.SessionNodeCard {
            id: card
            width: 600
            session: ({id: SESSION, state: "RUNNING", desktop_nodes: ["client"], environments: [], terminal_counts: []})
            nodeId: "client"
            desktopSupported: true
            onDesktopRequested: dialog.openFor(card.session, card.nodeId)
        }
        Studio.DesktopDialog { id: dialog; api: backend }
    }
    Timer {
        property int attempts: 0
        interval: 100; running: true; repeat: true
        function findButton(item) {
            if (item.objectName === "nodeDesktopButton") return item;
            for (let child of item.children || []) {
                let found = findButton(child);
                if (found) return found;
            }
            return null;
        }
        onTriggered: {
            if (++attempts === 2) {
                const button = findButton(card);
                if (!button || !button.enabled) { console.error("GUI button unavailable"); Qt.quit(); return; }
                button.clicked();
            }
            if (backend.error) { console.error(backend.error); Qt.quit(); }
            else if (dialog.opened) { console.log("CYBERLAB_PREPARATION_DIALOG_PASS"); Qt.quit(); }
            else if (attempts > 100) { console.error("Preparation dialog timed out"); Qt.quit(); }
        }
    }
}
'''
            configuration = configuration.replace('STUDIO', json.dumps((ROOT / 'ui/studio').as_uri())).replace(
                'PREFIX', json.dumps([sys.executable, '-B', '-c', bootstrap, '--test-session-bus'])).replace('SESSION', json.dumps(session_id))
            (root / 'shell.qml').write_text(configuration)
            environment = {key: value for key, value in os.environ.items() if key not in
                           ('DISPLAY', 'WAYLAND_DISPLAY', 'QML_IMPORT_PATH', 'QML2_IMPORT_PATH')}
            environment.update(DBUS_SESSION_BUS_ADDRESS=address, HOME=str(root / 'home'),
                XDG_CONFIG_HOME=str(root / 'config'), XDG_DATA_HOME=str(root / 'data'),
                XDG_CACHE_HOME=str(root / 'cache'), XDG_RUNTIME_DIR=str(root / 'runtime'),
                QT_QPA_PLATFORM='offscreen', QT_QUICK_BACKEND='software')
            process = await asyncio.create_subprocess_exec(executable, '--path', str(root), env=environment,
                stdout=subprocess.PIPE, stderr=subprocess.STDOUT, start_new_session=True)
            try:
                output, _ = await asyncio.wait_for(process.communicate(), 20)
                self.assertEqual(process.returncode, 0, output.decode(errors='replace'))
                self.assertIn(b'CYBERLAB_PREPARATION_DIALOG_PASS', output, output.decode(errors='replace'))
            finally:
                try:
                    os.killpg(process.pid, signal.SIGKILL)
                except ProcessLookupError:
                    pass
                await process.wait()

    async def test_private_socket_relay_and_exact_viewer_cleanup(self):
        await self.check_viewer_exit(0)

    async def test_client_crash_after_handshake_is_not_reported_as_success(self):
        with self.assertRaisesRegex(RuntimeError, 'exited with code 7'):
            await self.check_viewer_exit(7)

    async def check_viewer_exit(self, exit_code):
        with tempfile.TemporaryDirectory(prefix='cyberlab-viewer-check-') as temporary:
            executable = Path(temporary) / 'viewer'
            executable.write_text('#!' + sys.executable + '\n' + '''import pathlib, socket, sys, time
password = pathlib.Path(sys.argv[2])
assert password.stat().st_mode & 0o777 == 0o600
with socket.socket(socket.AF_UNIX, socket.SOCK_STREAM) as connection:
    connection.connect(sys.argv[1])
    connection.sendall(b'viewer-input')
    assert connection.recv(65536) == b'frame'
    print('CYBERLAB_APPS_READY', flush=True)
    time.sleep(0.1)
''' + '\nsys.exit(' + str(exit_code) + ')\n')
            executable.chmod(0o700)
            operations = []
            async def request(bus, operation, body):
                operations.append(operation)
                if operation == 'GetDesktopStatus': return '{"backend":"xpra","ready":true}'
                if operation == 'OpenDesktop': return ['handle', b'x' * 32]
                if operation == 'ReadDesktop': return [b'frame' if operations.count(operation) == 1 else b'', False]
                if operation == 'WriteDesktop': return len(body[1])
                return True
            output = io.StringIO()
            with patch.object(client, 'viewer_path', return_value=str(executable)), \
                 patch.object(client, 'viewer_command', side_effect=lambda app, endpoint, password, node, compatible=False: [app, str(endpoint), str(password)]), redirect_stdout(output):
                await asyncio.wait_for(client.interact(None, request, 'session', 'client'), timeout=5)
            self.assertEqual(json.loads(output.getvalue()), {'opened': True})
            self.assertIn('CloseDesktop', operations)
            self.assertLess(operations.index('ConfirmDesktop'), operations.index('CloseDesktop'))

    async def test_client_failure_does_not_confirm_readiness_or_leak_attachment(self):
        from unittest.mock import AsyncMock
        operations = []
        async def request(bus, operation, body):
            operations.append(operation)
            if operation == 'GetDesktopStatus': return '{"backend":"xpra","ready":true}'
            if operation == 'OpenDesktop': return ['handle', b'x' * 32]
            return True
        with patch.object(client, 'viewer_path', return_value='/usr/bin/false'), \
             patch.object(client, 'viewer_command', return_value=['/usr/bin/false']), \
             self.assertRaisesRegex(RuntimeError, 'could not open'):
            await asyncio.wait_for(client.interact(None, request, 'session', 'node'), timeout=5)
        self.assertNotIn('ConfirmDesktop', operations)
        self.assertIn('CloseDesktop', operations)

    async def test_invalid_server_credential_closes_handle_before_starting_client(self):
        from unittest.mock import AsyncMock
        request = AsyncMock(side_effect=['{"backend":"xpra"}', ['handle', b'old-vnc!'], True])
        with patch.object(client, 'viewer_path', return_value='/usr/bin/xpra'), \
             patch.object(client.asyncio, 'create_subprocess_exec') as spawn, \
             self.assertRaisesRegex(RuntimeError, 'authentication'):
            await client.interact(None, request, 'session', 'node')
        spawn.assert_not_called()
        self.assertEqual(request.call_args.args[1:], ('CloseDesktop', ['handle']))

    async def test_existing_ready_attachment_is_reused_without_new_client(self):
        from unittest.mock import AsyncMock
        request = AsyncMock(return_value='{"backend":"xpra","attached":true}')
        output = io.StringIO()
        with patch.object(client, 'viewer_path', return_value='/usr/bin/xpra'), redirect_stdout(output):
            await client.interact(None, request, 'session', 'node')
        self.assertEqual(json.loads(output.getvalue()), {'opened': True, 'existing': True})
        request.assert_awaited_once()

    async def test_opening_connection_waits_then_reuses_authenticated_viewer(self):
        from unittest.mock import AsyncMock

        request = AsyncMock(side_effect=[
            '{"backend":"xpra","opening":true}',
            '{"backend":"xpra","attached":true}',
        ])
        output = io.StringIO()
        with patch.object(client, 'viewer_path', return_value='/usr/bin/xpra'), \
             patch.object(client.asyncio, 'sleep', AsyncMock()), redirect_stdout(output):
            await client.interact(None, request, 'session', 'node')
        self.assertTrue(json.loads(output.getvalue())['existing'])
        self.assertEqual([call.args[1] for call in request.call_args_list], ['GetDesktopStatus'] * 2)

    async def test_busy_opening_is_bounded_and_never_replaced(self):
        from unittest.mock import AsyncMock

        request = AsyncMock(return_value='{"backend":"xpra","opening":true}')
        with patch.object(client, 'viewer_path', return_value='/usr/bin/xpra'), \
             patch.object(client.asyncio, 'sleep', AsyncMock()), \
             self.assertRaisesRegex(RuntimeError, 'still connecting'):
            await client.interact(None, request, 'session', 'node')
        self.assertEqual(request.await_count, 11)
        self.assertTrue(all(call.args[1] == 'GetDesktopStatus' for call in request.call_args_list))

    async def test_unprepared_and_headless_terminals_do_not_install_or_launch(self):
        from unittest.mock import AsyncMock
        for environment, status in (({}, {'backend': 'xpra', 'ready': True}),
                                    ({'DISPLAY': ':test'}, {'backend': 'xpra', 'ready': True, 'auto_connect': False}),
                                    ({'DISPLAY': ':test'}, {'backend': 'xpra', 'ready': False}),
                                    ({'DISPLAY': ':test'}, {'backend': 'xpra', 'ready': True, 'attached': True})):
            request = AsyncMock(return_value=json.dumps(status))
            with patch.dict(os.environ, environment, clear=True), patch.object(client, 'launch') as launch:
                await client.attach_prepared(None, request, 'session', 'node')
                launch.assert_not_called()

    async def test_prepared_terminal_reattaches_without_installing(self):
        from unittest.mock import AsyncMock
        request = AsyncMock(side_effect=['{"backend":"xpra","ready":true}', '{"backend":"xpra","ready":true,"attached":true}'])
        with patch.dict(os.environ, {'DISPLAY': ':test'}), patch.object(client, 'launch') as launch:
            await client.attach_prepared(None, request, 'session', 'node', True)
            launch.assert_called_once()
            self.assertTrue(launch.call_args.args[0].test_session_bus)
        self.assertEqual([call.args[1] for call in request.call_args_list], ['GetDesktopStatus', 'GetDesktopStatus'])

    async def test_concurrent_terminal_waits_for_shared_handshake(self):
        from unittest.mock import AsyncMock
        request = AsyncMock(side_effect=[json.dumps(state) for state in (
            {'backend': 'xpra', 'ready': True}, {'opening': True}, {'attached': True})])
        with patch.dict(os.environ, {'DISPLAY': ':test'}), patch.object(client, 'launch', side_effect=RuntimeError('Already opening')):
            await client.attach_prepared(None, request, 'session', 'node')
        self.assertEqual(request.await_count, 3)

    def test_viewer_argv_disables_host_integration(self):
        argv = client.viewer_command('/usr/bin/xpra', Path('/tmp/space here/display.sock'), Path('/tmp/space here/auth'), 'node')
        self.assertIn('socket:///tmp/space here/display.sock', argv)
        self.assertNotIn('--compressors=none', argv)
        fallback = client.viewer_command('/usr/bin/xpra', Path('/tmp/socket'), Path('/tmp/auth'), 'node', compatible=True)
        self.assertEqual(fallback[fallback.index('-z') + 1], '0')
        self.assertIn('--compressors=none', fallback)
        for flag in ('clipboard', 'file-transfer', 'open-files', 'open-url', 'webcam', 'dbus-proxy', 'printing', 'mmap', 'splash', 'reconnect'):
            self.assertIn('--' + flag + '=no', argv)
        self.assertNotIn('shadow', argv)
        with patch.dict(os.environ, {'XPRA_USER_CONF_DIRS': '/user/config', 'XPRA_OPEN_COMMAND': 'unsafe'}):
            environment = client.viewer_environment(Path('/private'))
        self.assertNotIn('XPRA_OPEN_COMMAND', environment)
        self.assertEqual(environment['XPRA_USER_CONF_DIRS'], '/private/no-config')

class HostEnvironmentChecks(unittest.TestCase):
    def test_legacy_window_title_decodes_without_touching_binary_metadata(self):
        source = {'title': b'Ubuntu editor', 'icon': b'\x00\xff'}
        self.assertEqual(compatible_metadata(source), {'title': 'Ubuntu editor', 'icon': b'\x00\xff'})
        self.assertEqual(source['title'], b'Ubuntu editor')

    def test_hello_preserves_legacy_encoding_and_dpi_types_without_changing_input(self):
        original = {'encodings': {'': ['rgb'], 'core': ['rgb24', 'rgb32']},
                    'encoding': {'rgb_formats': ['RGB', 'RGBA']}, 'dpi': {'': 96, 'x': 96, 'y': 96},
                    'keymap': {'layout': 'us'}, 'clipboard': False}
        result = compatible_hello(original)
        self.assertEqual(result['encodings'], ['rgb'])
        self.assertEqual(result['encodings.core'], ['rgb24', 'rgb32'])
        self.assertEqual(result['encoding.rgb_formats'], ['RGB', 'RGBA'])
        self.assertEqual(result['dpi'], 96)
        self.assertEqual(result['dpi.x'], 96)
        self.assertEqual(result['keymap'], {'layout': 'us'})
        self.assertEqual(result['xkbmap_layout'], 'us')
        self.assertIsInstance(original['encodings'], dict)
        for flag in ('zlib', 'lz4', 'lzo', 'brotli', 'clipboard'):
            self.assertFalse(result[flag])
        self.assertTrue(result['notify-startup-complete'])
        self.assertEqual(compatible_hello(result), result)

    def test_installer_probes_target_user_without_inheriting_display(self):
        import runtime_admin

        account = SimpleNamespace(pw_uid=1234, pw_name='fixture', pw_dir='/home/fixture')
        for output, expected in (('{"ready":true}', True), ('[]', False), ('broken', False)):
            with patch.object(runtime_admin, 'run', return_value=SimpleNamespace(returncode=0, stdout=output)) as run, \
                 redirect_stdout(io.StringIO()):
                self.assertEqual(runtime_admin.probe_gui_client(account), expected)
            self.assertIs(run.call_args.kwargs['account'], account)
            self.assertEqual(run.call_args.args[-1], '--probe')

    def inspect(self, environment, *, uid=1234, installed=True, compatible=True, display=True):
        with patch.dict(os.environ, environment, clear=True), \
             patch.object(gui_environment.os, 'geteuid', return_value=uid), \
             patch.object(gui_environment.Path, 'is_file', return_value=installed), \
             patch.object(gui_environment.os, 'access', return_value=installed), \
             patch.object(gui_environment, 'probe', side_effect=lambda option:
                 {'ready': compatible, 'version': '6.4.4'} if option == '--probe' else {'ready': display}):
            return gui_environment.inspect_environment()

    def test_x11_and_wayland_use_capabilities_not_desktop_names(self):
        for desktop in ('GNOME', 'KDE', 'Xfce', 'i3', 'sway', 'Hyprland', 'niri', 'unknown'):
            for session in ('x11', 'wayland'):
                with self.subTest(desktop=desktop, session=session):
                    result = self.inspect({'DISPLAY': ':42', 'XDG_SESSION_TYPE': session,
                                           'XDG_CURRENT_DESKTOP': desktop})
                    self.assertTrue(result['ready'])
                    self.assertEqual(result['session_type'], session)

    def test_wayland_needs_working_xwayland_not_only_environment_variable(self):
        for environment in ({'WAYLAND_DISPLAY': 'wayland-1'},
                            {'XDG_SESSION_TYPE': 'wayland', 'DISPLAY': ':invalid'}):
            result = self.inspect(environment, display=False)
            self.assertEqual(result['code'], 'xwayland-unavailable')
            self.assertFalse(result['ready'])

    def test_broken_x11_is_distinct_from_headless(self):
        self.assertEqual(self.inspect({'DISPLAY': ':invalid'}, display=False)['code'], 'x11-unavailable')
        self.assertEqual(self.inspect({})['code'], 'headless')

    def test_root_missing_and_incompatible_client_are_distinct(self):
        for options, code in (({'uid': 0}, 'desktop-user-required'),
                              ({'installed': False}, 'xpra-missing'),
                              ({'compatible': False}, 'xpra-incompatible')):
            self.assertEqual(self.inspect({'DISPLAY': ':42'}, **options)['code'], code)

    def test_failed_or_malformed_probes_fail_closed(self):
        for result in (SimpleNamespace(returncode=1, stdout=''),
                       SimpleNamespace(returncode=0, stdout='not json'),
                       SimpleNamespace(returncode=0, stdout='[]')):
            with patch.object(gui_environment.subprocess, 'run', return_value=result):
                self.assertEqual(gui_environment.probe('--probe'), {})
        with patch.object(gui_environment.subprocess, 'run', side_effect=subprocess.TimeoutExpired('probe', 8)):
            self.assertEqual(gui_environment.probe('--display-probe'), {})

    def test_unavailable_host_does_not_start_client_or_change_session(self):
        with patch.object(gui_environment, 'inspect_environment', return_value={'ready': False, 'message': 'No display'}), \
             patch.object(client.subprocess, 'Popen') as spawn:
            with self.assertRaisesRegex(RuntimeError, 'No display'):
                client.launch(SimpleNamespace(id='session', node='client', test_session_bus=False))
            spawn.assert_not_called()

if __name__ == '__main__':
    unittest.main(verbosity=2)
