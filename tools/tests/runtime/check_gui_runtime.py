#!/usr/bin/env python3
"""Administrator-only GUI acceptance in a disposable Ubuntu lab, never user data."""

import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).resolve().parents[3]))

import argparse
import asyncio
from dataclasses import asdict
import json
import os
import pwd
import subprocess
import tempfile
from unittest.mock import patch
from uuid import uuid4

if '--installed' in sys.argv:
    from types import SimpleNamespace
    from cyberlab.lab.workstation import UBUNTU_IMAGE, workstation_user
    from cyberlab.policy import RuntimePolicy
    from cyberlab.runtime.docker import DockerRuntime
    from cyberlab.service import Engine
    from cyberlab.session import SessionState

    fixture = SimpleNamespace(ROOT=Path(__file__).resolve().parents[3], UBUNTU_IMAGE=UBUNTU_IMAGE,
        workstation_user=workstation_user, RuntimePolicy=RuntimePolicy, DockerRuntime=DockerRuntime,
        Engine=Engine, SessionState=SessionState)
else:
    from tools.tests.runtime import check_workstation_runtime as fixture
    sys.path.insert(0, str(fixture.ROOT / 'cli'))
from cyberlab_cli import desktop as client
from cyberlab.runtime import desktop as guest


async def verify(arguments):
    account = pwd.getpwuid(arguments.uid)
    with tempfile.TemporaryDirectory(prefix='cyberlab-gui-acceptance-', dir='/var/tmp') as temporary:
        root = Path(temporary)
        package = root / 'catalog/fixture'
        package.mkdir(parents=True)
        user = fixture.workstation_user('student')
        document = {'apiVersion': 'cyberlab.ptit/v1', 'kind': 'Lab',
                    'metadata': {'id': 'fixture', 'name': 'Disposable GUI acceptance', 'version': '1.0.0'},
                    'networks': [{'id': 'lan'}], 'terminals': ['client'],
                    'nodes': [{'id': 'client', 'image': fixture.UBUNTU_IMAGE, 'networks': ['lan'],
                               'command': ['sleep', 'infinity'], 'user': asdict(user),
                               'resources': {'memory_mb': 512, 'cpu_millicores': 1000}}]}
        (package / 'lab.yaml').write_text(json.dumps(document))
        runtime = fixture.DockerRuntime(workstation_images={fixture.UBUNTU_IMAGE}, checkpoint_scope='gui-' + uuid4().hex)
        runtime.client.api.timeout = 180
        policy = fixture.RuntimePolicy(frozenset({fixture.UBUNTU_IMAGE}), workstation_images=frozenset({fixture.UBUNTU_IMAGE}))
        engine = fixture.Engine(root / 'catalog', policy, runtime)
        session = None
        attachment = None
        client_log = root / 'client-check.log'
        original_spawn = asyncio.create_subprocess_exec
        async def spawn(*command, **options):
            with client_log.open('ab') as diagnostic:
                options['stderr'] = diagnostic
                return await original_spawn(*command, **options)
        try:
            session = engine.start('fixture', arguments.uid)
            assert session.state == fixture.SessionState.RUNNING, session.error
            print('PASS: disposable Ubuntu container started with normal 512 MiB policy', flush=True)
            engine.prepare_desktop(session.id, 'client', arguments.uid)
            print('PASS: guest GUI package preparation', flush=True)
            container = runtime._workspace_container(session, session.lab.nodes[0])
            debug_setup = guest.SETUP.replace('stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL',
                "stdout=open('/tmp/cyberlab-apps/server-check.log', 'wb'), stderr=subprocess.STDOUT")
            with patch.object(guest, 'SETUP', debug_setup):
                handle, _ = engine.open_desktop(session.id, 'client', arguments.uid, ':fixture')
            engine.desktop('close', handle, arguments.uid, ':fixture')
            print('PASS: real Ubuntu Xpra server startup and Docker binary bridge', flush=True)
            if not arguments.display:
                return
            result = container.exec_run(['/usr/bin/timeout', '150', '/bin/sh', '-c',
                                         'apt-get install -y --no-install-recommends mousepad >/dev/null 2>&1'], user='0:0')
            assert result.exit_code == 0, 'Mousepad installation failed'
            confirmed = False
            async def request(bus, operation, body):
                nonlocal confirmed
                if operation == 'GetDesktopStatus':
                    return json.dumps(engine.desktop_status(body[0], body[1], arguments.uid))
                if operation == 'OpenDesktop':
                    return engine.open_desktop(body[0], body[1], arguments.uid, ':fixture')
                operations = {'ConfirmDesktop': 'ready', 'ReadDesktop': 'read', 'WriteDesktop': 'write', 'CloseDesktop': 'close'}
                result = engine.desktop(operations[operation], body[0], arguments.uid, ':fixture', *body[1:])
                if operation == 'ConfirmDesktop':
                    confirmed = True
                return result
            original_command = client.viewer_command
            def command(executable, endpoint, password, node):
                for path in (endpoint.parent, endpoint, password):
                    os.chown(path, arguments.uid, account.pw_gid)
                return ['/usr/bin/runuser', '-u', account.pw_name, '--', *original_command(executable, endpoint, password, node)]
            environment = dict(os.environ, DISPLAY=arguments.display, XDG_RUNTIME_DIR=f'/run/user/{arguments.uid}',
                               HOME=account.pw_dir, GDK_BACKEND='x11')
            environment.pop('XAUTHORITY', None)
            title = 'CyberLab-GUI-check-' + uuid4().hex + '.txt'
            window_probe = ('import sys; sys.path.insert(0, ' + repr(str(fixture.ROOT)) + '); '
                            'from tools.tests.runtime.check_seamless_apps import window_names; '
                            'print(next((identifier for identifier, name in window_names(sys.argv[1], with_ids=True) if sys.argv[2] in name), 0))')
            paint_probe = '''import sys, gi
gi.require_version('Gdk', '3.0')
gi.require_version('GdkX11', '3.0')
from gi.repository import Gdk, GdkX11
Gdk.init([])
display = Gdk.Display.get_default()
window = GdkX11.X11Window.foreign_new_for_display(display, int(sys.argv[1]))
height = window.get_height() - 60
image = Gdk.pixbuf_get_from_window(window, 0, 60, window.get_width(), height) if height > 0 else None
if image is None: sys.exit(1)
pixels, channels = image.get_pixels(), image.get_n_channels()
colors = set()
for row in range(image.get_height()):
    start = row * image.get_rowstride()
    for offset in range(start, start + image.get_width() * channels, channels * 2):
        colors.add(pixels[offset:offset + 3])
    if len(colors) > 32: break
print(len(colors))
'''
            async def wait_window():
                for attempt in range(100):
                    if attachment.done():
                        attachment.result()
                        raise AssertionError('Display connection ended before window appeared')
                    result = await asyncio.to_thread(subprocess.run,
                        ['/usr/bin/runuser', '-u', account.pw_name, '--', sys.executable, '-B', '-I', '-c',
                         window_probe, arguments.display, title], env=environment,
                        capture_output=True, text=True, timeout=5)
                    if result.returncode == 0 and result.stdout.strip().isdigit() and int(result.stdout.strip()):
                        paint = await asyncio.to_thread(subprocess.run,
                            ['/usr/bin/runuser', '-u', account.pw_name, '--', '/usr/bin/python3', '-I', '-c',
                             paint_probe, result.stdout.strip()], env=environment,
                            capture_output=True, text=True, timeout=5)
                        if paint.returncode == 0 and paint.stdout.strip().isdigit() and int(paint.stdout.strip()) > 32:
                            return
                    await asyncio.sleep(0.1)
                raise AssertionError('Guest Mousepad window did not render content on the host display')
            with patch.dict(os.environ, environment, clear=True), patch.object(client, 'viewer_command', command), \
                    patch.object(asyncio, 'create_subprocess_exec', spawn):
                attachment = asyncio.create_task(client.interact(None, request, session.id, 'client'))
                for attempt in range(400):
                    if attachment.done():
                        attachment.result()
                        raise AssertionError('Client exited before readiness')
                    if confirmed:
                        break
                    await asyncio.sleep(0.1)
                assert confirmed, 'Real container client handshake did not complete'
                print('PASS: authenticated Xpra attachment through real Engine/Docker stream', flush=True)
                result = container.exec_run(['/bin/sh', '-c',
                    'printf "CyberLab GUI acceptance\\nThis file belongs to the disposable Ubuntu container.\\nThe test closes this window automatically.\\n" > "$1"',
                    'gui-check', user.home + '/' + title], user='2000:2000')
                assert result.exit_code == 0, 'Could not create disposable GUI test document'
                execution = runtime.client.api.exec_create(container.id,
                    cmd=['/bin/sh', '-c', 'exec /usr/bin/mousepad --disable-server "$1" > /tmp/cyberlab-apps/app-check.log 2>&1',
                         'gui-check', user.home + '/' + title], user='2000:2000',
                    environment={'HOME': user.home, 'DISPLAY': ':99', 'XAUTHORITY': '/tmp/cyberlab-apps/Xauthority'})
                runtime.client.api.exec_start(execution['Id'], detach=True)
                await wait_window()
                print('PASS: actual guest Mousepad window found on host X11/XWayland display', flush=True)
                await asyncio.sleep(arguments.visible_seconds)
                if attachment.done():
                    attachment.result()
                    raise AssertionError('Display connection ended during application check')
                print('PASS: application display stayed connected', flush=True)
                assert runtime.client.api.exec_inspect(execution['Id'])['Running'], 'Guest application exited before detach'
                attachment.cancel()
                await asyncio.gather(attachment, return_exceptions=True)
                assert runtime.client.api.exec_inspect(execution['Id'])['Running'], 'Detaching closed the guest application'
                confirmed = False
                attachment = asyncio.create_task(client.interact(None, request, session.id, 'client'))
                for attempt in range(400):
                    if attachment.done():
                        attachment.result()
                        raise AssertionError('Client exited before reconnect readiness')
                    if confirmed:
                        break
                    await asyncio.sleep(0.1)
                assert confirmed, 'Reconnect handshake did not complete'
                await wait_window()
                print('PASS: same guest application window returned after detach/reconnect', flush=True)
        except Exception:
            if client_log.exists():
                for line in client_log.read_text(errors='replace').splitlines()[-60:]:
                    if not any(word in line.lower() for word in ('auth', 'password', 'token', 'challenge', 'digest')):
                        print('Client diagnostic:', line[:400], file=sys.stderr)
            if session:
                container = runtime._workspace_container(session, session.lab.nodes[0])
                result = container.exec_run(['/bin/sh', '-c', 'tail -c 6000 /tmp/cyberlab-apps/server-check.log 2>/dev/null'], user='2000:2000')
                for line in result.output.decode(errors='replace').splitlines():
                    if not any(word in line.lower() for word in ('auth', 'password', 'token', 'challenge', 'digest')):
                        print('Guest diagnostic:', line[:400], file=sys.stderr)
                result = container.exec_run(['/bin/sh', '-c', 'tail -c 2000 /tmp/cyberlab-apps/app-check.log 2>/dev/null'], user='2000:2000')
                print('Application diagnostic:', result.output.decode(errors='replace'), file=sys.stderr)
            raise
        finally:
            if attachment:
                attachment.cancel()
                await asyncio.gather(attachment, return_exceptions=True)
            if session:
                engine._close_attachments(session.id)
                runtime.remove(session.id)
                assert not runtime._resources(runtime.client.containers, session.id, include_stopped=True)
                assert not runtime._resources(runtime.client.networks, session.id)
            runtime.system_checkpoints.collect(set())
            runtime.client.close()
            print('CLEANUP: removed only disposable test runtime', flush=True)


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--uid', required=True, type=int)
    parser.add_argument('--installed', action='store_true', help='Use the installed runtime/client, not repository source')
    parser.add_argument('--display', help='Explicit host X11/XWayland display for a visible acceptance window')
    parser.add_argument('--visible-seconds', type=int, default=15)
    arguments = parser.parse_args()
    if os.geteuid() != 0 or arguments.uid <= 0:
        parser.error('Requires administrator and a non-root desktop UID')
    asyncio.run(verify(arguments))
