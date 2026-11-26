"""Run real Xwayland authorization checks inside an owned headless Cage compositor."""

import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).resolve().parents[3]))

import argparse
import json
from contextlib import suppress
import os
import signal
import socket
import stat
import struct
import subprocess
import tempfile
from unittest.mock import patch

sys.dont_write_bytecode = True
sys.path.insert(0, str(Path(__file__).resolve().parents[3] / 'engine'))
from cyberlab.host_display import helper, verify_display
from tools.tests.runtime.disposable_x11 import disposable_display, disable_core_dumps
from tools.tests.runtime.check_x11_security import client as active_client, response
from cyberlab.runtime.display_relay import DisplayRelay
from tools.tests.runtime.x11_relay_probe import probe


def isolated_environment():
    root = Path(os.environ['XDG_RUNTIME_DIR'])
    info = root.lstat()
    if root.parent != Path('/tmp') or not root.name.startswith('cyberlab-xwayland-'):
        raise ValueError('Only the temporary test runtime is allowed')
    if not stat.S_ISDIR(info.st_mode) or info.st_uid != os.getuid() or info.st_mode & 0o077:
        raise ValueError('Private runtime directory required')
    display = os.environ['WAYLAND_DISPLAY']
    if '/' in display or not display:
        raise ValueError('Private Wayland socket required')
    with socket.socket(socket.AF_UNIX) as connection:
        connection.connect(str(root / display))
        process, owner, _group = struct.unpack('3i', connection.getsockopt(socket.SOL_SOCKET, socket.SO_PEERCRED, 12))
    if owner != os.getuid() or process != os.getppid() or Path(f'/proc/{process}/exe').resolve().name != 'cage':
        raise ValueError('Only the owned Cage parent may host this fixture')
    parent_environment = dict(entry.split('=', 1) for entry in Path(f'/proc/{process}/environ').read_text().split('\0') if '=' in entry)
    if parent_environment.get('WLR_BACKENDS') != 'headless' or parent_environment.get('XDG_RUNTIME_DIR') != str(root):
        raise ValueError('Only the private headless compositor is allowed')
    return {'XDG_RUNTIME_DIR': str(root), 'WAYLAND_DISPLAY': display}


def check(guest=False, guest_image=None):
    environment = isolated_environment()
    for activated in (False, True):
        check_server(environment, activated, guest, guest_image)


def check_server(environment, activated, guest=False, guest_image=None):
    with disposable_display('/usr/bin/Xwayland', environment, activated) as (owner, server):
        with patch('cyberlab.host_display.login_session', return_value={'Type': 'wayland', 'Leader': str(os.getpid())}):
            identity = verify_display(owner['display'], 'fixture', os.getuid())
            assert identity['process'] == server.pid
            assert identity['server'] == 'Xwayland'
            assert identity['peer'] == (os.getpid() if activated else server.pid)
        target = {**owner, **helper({**owner, 'operation': 'generate'}), 'identity': identity, 'uid': os.getuid()}
        with tempfile.TemporaryDirectory(prefix='cyberlab-relay-') as directory:
            relay = DisplayRelay(Path(directory), target, os.getuid(), os.getgid())
            try:
                probe(str(relay.path), target['cookie'])
                try:
                    probe(str(relay.path), '00' * 16)
                except (ValueError, OSError):
                    pass
                else:
                    raise AssertionError('Relay accepted the wrong cookie')
                relay.restart(target)
                probe(str(relay.path), target['cookie'])
                print('PASS: real X11 window through private relay; invalid cookie rejected; same socket reconnect works', flush=True)
            finally:
                relay.close()
        if guest:
            endpoint = Path(identity['socket'])
            endpoint.chmod(0o755)
            result = subprocess.run(['/usr/bin/pkexec', '/usr/lib/cyberlab/venv/bin/python',
                                     str(Path(__file__).with_name('check_xwayland_guest.py'))],
                                    input=json.dumps({**target, 'fixture_image': guest_image}), capture_output=True, text=True, timeout=90)
            print(result.stdout, flush=True)
            if result.returncode:
                print(result.stderr, flush=True)
                raise RuntimeError('Cross-UID Docker relay verification failed')
        helper({**target, 'operation': 'revoke'})
        for _attempt in range(3):
            target = {**owner, **helper({**owner, 'operation': 'generate'})}
            assert helper({**target, 'operation': 'probe'})['ready']
            with active_client(owner, separate_session=False) as unrelated, active_client(target, separate_session=False) as client:
                helper({**target, 'operation': 'revoke'})
                client.wait(timeout=5)
                unrelated.stdin.write(b'ping\n')
                unrelated.stdin.flush()
                assert response(unrelated) == b'pong'
            for credential in (target, {**owner, 'cookie': '00' * 16}):
                try:
                    helper({**credential, 'operation': 'probe'})
                except ValueError:
                    continue
                raise AssertionError('Revoked or invalid authorization was accepted')
            assert helper({**owner, 'operation': 'probe'})['ready']
            assert server.poll() is None
        print('PASS: real isolated Xwayland: generate, connect, revoke active client, reject stale/bad cookie; unrelated client survives', flush=True)


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('--inside', action='store_true')
    parser.add_argument('--guest', action='store_true', help='Explicit pkexec test of a disposable Docker UID 2000 client')
    parser.add_argument('--guest-image', help='Cached CyberLab software image with libX11; never pulled or modified')
    arguments = parser.parse_args()
    if arguments.guest and not arguments.guest_image:
        parser.error('--guest requires --guest-image with libX11 installed')
    if os.geteuid() == 0:
        raise ValueError('Run as a normal user')
    if arguments.inside:
        check(arguments.guest, arguments.guest_image)
        return
    with tempfile.TemporaryDirectory(prefix='cyberlab-xwayland-') as directory:
        environment = {'PATH': '/usr/bin:/bin', 'HOME': directory, 'XDG_CONFIG_HOME': directory,
                       'XDG_RUNTIME_DIR': directory, 'LANG': 'C.UTF-8',
                       'WLR_BACKENDS': 'headless', 'WLR_RENDERER': 'pixman', 'WLR_HEADLESS_OUTPUTS': '1'}
        with tempfile.TemporaryFile() as log:
            process = subprocess.Popen(['/usr/bin/cage', '--', sys.executable, str(Path(__file__).resolve()), '--inside',
                                        *(['--guest', '--guest-image', arguments.guest_image] if arguments.guest else [])],
                                       stdin=subprocess.DEVNULL, stdout=log, stderr=log, env=environment,
                                       start_new_session=True, preexec_fn=disable_core_dumps)
            try:
                process.wait(timeout=240 if arguments.guest else 60)
            finally:
                with suppress(ProcessLookupError):
                    os.killpg(process.pid, signal.SIGTERM)
                try:
                    process.wait(timeout=5)
                except subprocess.TimeoutExpired:
                    os.killpg(process.pid, signal.SIGKILL)
                    process.wait()
            log.seek(0)
            output = log.read().decode(errors='replace')
            print(output)
            if process.returncode or 'PASS: real isolated Xwayland' not in output:
                raise RuntimeError('Isolated Xwayland verification failed')


if __name__ == '__main__':
    main()
