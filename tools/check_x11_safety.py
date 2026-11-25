"""Native-X11 regression checks; never connect to a host display."""

import json
from contextlib import redirect_stderr
import io
import os
from pathlib import Path
import tempfile
from types import SimpleNamespace
import unittest
from unittest.mock import AsyncMock, patch

import check_desktops
from cyberlab import host_display, x11
from cyberlab.runtime.native_display import NativeDisplays
from cyberlab_cli import display_context, gui_environment
from cyberlabd.server import Server


class QuarantineChecks(unittest.TestCase):
    def test_helper_rejects_mutation_before_spawning(self):
        with patch.object(x11, 'NATIVE_X11_ENABLED', False), patch.object(host_display.subprocess, 'run') as run:
            for operation in ('generate', 'revoke'):
                with self.assertRaisesRegex(ValueError, 'unavailable'):
                    host_display.helper({'display': ':42', 'operation': operation})
            run.assert_not_called()

    def test_direct_entrypoint_rejects_mutation_before_loading_xlib(self):
        with patch.object(x11, 'NATIVE_X11_ENABLED', False), patch.object(x11.ctypes, 'CDLL') as library:
            for operation in ('generate', 'revoke'):
                with self.assertRaises(ValueError):
                    x11.operate({'display': ':42', 'operation': operation})
            library.assert_not_called()

    def test_fixture_rejects_non_child_and_stale_pid_before_loading_xlib(self):
        with patch.object(x11.ctypes, 'CDLL') as library:
            for process in (os.getpid(), os.getppid(), -1, True):
                with self.assertRaises(ValueError):
                    x11.operate({'display': ':42', 'operation': 'generate',
                                 '_fixture': {'pid': process, 'start_time': 'stale'}})
            library.assert_not_called()

    def test_runtime_rejects_registration_reconnect_and_existing_tokens(self):
        with tempfile.TemporaryDirectory() as directory:
            native = NativeDisplays(Path(directory) / 'leases')
            with patch('cyberlab.runtime.native_display.helper') as helper, \
                 patch('cyberlab.runtime.native_display.verify_display') as verify:
                with patch.object(x11, 'NATIVE_X11_ENABLED', False):
                    self.assertFalse(native.enabled)
                    actions = (lambda: native.register('{}', os.getuid(), ':test'),
                               lambda: native.take('old-token', os.getuid(), ':test'),
                               lambda: native.reconnect(SimpleNamespace(id='test'), 'gui', {}))
                    for action in actions:
                        with self.assertRaisesRegex(ValueError, 'unavailable'):
                            action()
                    helper.assert_not_called()
                    verify.assert_not_called()

    def test_cleanup_never_revokes_on_the_host(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory) / 'leases'
            root.mkdir(mode=0o700)
            lease = root / 'test-node'
            lease.mkdir(mode=0o700)
            record = {'cookie': 'fixture-not-a-credential', 'uid': os.getuid()}
            (lease / 'lease.json').write_text(json.dumps(record))
            (lease / 'Xauthority').write_bytes(b'fixture')
            native = NativeDisplays(root)
            native.contexts['expired'] = {**record, 'deadline': 0}
            with patch.object(x11, 'NATIVE_X11_ENABLED', False), patch('cyberlab.runtime.native_display.helper') as helper:
                native.poll()
                native.cleanup()
                helper.assert_not_called()
            self.assertEqual(list(root.iterdir()), [])

    def test_start_never_mounts_host_display(self):
        with tempfile.TemporaryDirectory() as directory:
            native = NativeDisplays(Path(directory) / 'leases')
            node = SimpleNamespace(id='gui', software=SimpleNamespace(gui=True))
            session = SimpleNamespace(id='test', lab=SimpleNamespace(nodes=[node]))
            with patch.object(x11, 'NATIVE_X11_ENABLED', False), patch('cyberlab.runtime.native_display.helper') as helper:
                native.prepare(session, {'cookie': 'untrusted'})
                self.assertEqual(native.options(session, node), {})
                self.assertEqual(native.environment(session, node), {})
                self.assertEqual(native.status(session, node.id)['backend'], 'xpra')
                helper.assert_not_called()

    def test_api_does_not_advertise_native_or_accept_context_calls(self):
        engine = SimpleNamespace(runtime=SimpleNamespace(name='fixture', native=NativeDisplays(None)),
                                 practice_store=None, policy=SimpleNamespace(workstation_images=[]))
        server = Server(None, engine, {os.getuid()})
        self.assertNotIn('native-x11', Server.dispatch(server, 'GetCapabilities', [], os.getuid()))
        for operation in ('PrepareDesktopContext', 'ReleaseDesktopContext', 'StartLabWithDesktop',
                          'ResumeSessionWithDesktop', 'ResetSessionWithDesktop', 'ReconnectNativeDesktop'):
            with self.assertRaisesRegex(ValueError, 'unavailable'):
                Server.dispatch(server, operation, [], os.getuid())

    def test_api_only_advertises_machine_setup_for_allowed_ubuntu(self):
        image = 'cyberlab/ubuntu:24.04-1'
        runtime = SimpleNamespace(name='fixture', native=NativeDisplays(None))
        for allowed_images, workstation_images, expected in (
                ({image}, {image}, True),
                (set(), {image}, False),
                ({'busybox:1.37.0'}, set(), False)):
            engine = SimpleNamespace(runtime=runtime, practice_store=None,
                                     policy=SimpleNamespace(allowed_images=allowed_images,
                                                            workstation_images=workstation_images))
            server = Server(None, engine, {os.getuid()})
            capabilities = Server.dispatch(server, 'GetCapabilities', [], os.getuid())
            self.assertEqual('machine-setup-v1' in capabilities, expected)

    def test_x11_wayland_headless_and_missing_xpra_stay_fail_closed(self):
        with patch('cyberlab_cli.gui_preferences.preference', return_value={'preferred': 'auto', 'warning': ''}), \
             patch('cyberlab.host_display.login_session', return_value={'Id': 'fixture', 'Type': 'x11'}), \
             patch('cyberlab.host_display.verify_display') as verify, patch('cyberlab.host_display.helper') as helper, \
             patch.object(gui_environment, 'probe', return_value={'ready': True}), \
             patch.object(gui_environment.Path, 'is_file', return_value=True), \
             patch.object(gui_environment.os, 'access', return_value=True):
            for environment, kind in (({'DISPLAY': ':42', 'XDG_SESSION_TYPE': 'x11'}, 'x11'),
                                      ({'DISPLAY': ':42', 'WAYLAND_DISPLAY': 'fixture'}, 'wayland'), ({}, 'headless')):
                with patch.dict(os.environ, environment, clear=True):
                    report = gui_environment.inspect_environment()
                    self.assertEqual(report['backend'], 'native-x11' if kind == 'x11' else 'xpra')
                    self.assertEqual(report['session_type'], kind)
                    self.assertEqual(report['ready'], kind != 'headless')
                    if kind == 'x11':
                        verify.assert_called_once()
                        verify.reset_mock()
            with patch.dict(os.environ, {'DISPLAY': ':42', 'WAYLAND_DISPLAY': 'fixture'}, clear=True), \
                 patch.object(gui_environment.Path, 'is_file', return_value=False):
                self.assertFalse(gui_environment.inspect_environment()['ready'])
            helper.assert_called()


class ClientChecks(unittest.IsolatedAsyncioTestCase):
    async def test_fallback_identifies_phase_without_exposing_credentials(self):
        for phase in ('host-authorization', 'daemon-context'):
            credential = {'cookie': 'fixture-secret', 'authorization': 123}
            def operation(payload):
                if payload['operation'] == 'generate':
                    if phase == 'host-authorization':
                        raise ValueError('fixture-secret')
                    return credential
                return {'ready': True}
            request = AsyncMock(side_effect=[ValueError('fixture-secret'), 'fallback-token']
                                if phase == 'daemon-context' else ['fallback-token'])
            output = io.StringIO()
            with patch.object(display_context, 'inspect_environment', return_value={
                    'backend': 'native-x11', 'ready': True, 'login': 'fixture', 'preferred': 'auto'}), \
                 patch.object(display_context, 'helper', side_effect=operation) as helper, \
                 patch.dict(os.environ, {'DISPLAY': ':42'}), redirect_stderr(output):
                self.assertEqual(await display_context.prepare(None, request), 'fallback-token')
            fallback = json.loads(request.await_args.args[2][0])
            self.assertIn(f'[{phase}]', fallback['fallback'])
            self.assertNotIn('fixture-secret', fallback['fallback'])
            self.assertNotIn('fixture-secret', output.getvalue())
            operations = [call.args[0]['operation'] for call in helper.call_args_list]
            self.assertEqual(operations, ['generate', 'revoke'] if phase == 'daemon-context' else ['generate'])

    async def test_lifecycle_keeps_legacy_api_without_preparing_context(self):
        for command, method in (('start', 'StartLabWithParameters'), ('resume', 'ResumeSession'), ('reset', 'ResetSession')):
            request = AsyncMock(return_value={'id': 'test'})
            with patch.object(display_context.x11, 'NATIVE_X11_ENABLED', False), patch.object(display_context, 'prepare') as prepare:
                result = await display_context.lifecycle(None, request,
                    SimpleNamespace(command=command, id='test', test_session_bus=False), {})
                self.assertEqual(result, {'id': 'test'})
                self.assertEqual(request.await_args.args[1], method)
                self.assertEqual(request.await_count, 1)
                prepare.assert_not_called()

    async def test_direct_prepare_does_not_inspect_host(self):
        with patch.object(display_context.x11, 'NATIVE_X11_ENABLED', False), patch.object(display_context, 'inspect_environment') as inspect:
            with self.assertRaisesRegex(ValueError, 'unavailable'):
                await display_context.prepare(None, AsyncMock())
            inspect.assert_not_called()


if __name__ == '__main__':
    unittest.main()
