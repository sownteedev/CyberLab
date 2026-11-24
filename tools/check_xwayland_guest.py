"""Explicit root fixture: UID 2000 and a disposable networkless Docker client."""

from contextlib import suppress
import json
import os
from pathlib import Path
import socket
import struct
import subprocess
import sys
import tempfile
from types import SimpleNamespace
from uuid import uuid4
from unittest.mock import patch

sys.dont_write_bytecode = True
sys.path.insert(0, str(Path(__file__).resolve().parents[1] / 'engine'))
from cyberlab.runtime.display_relay import DisplayRelay
from cyberlab.runtime.native_display import NativeDisplays
from cyberlab.runtime.workspace import execute
from cyberlab.x11 import authority
from cyberlab.xwayland import verified_server


def main():
    import docker

    if os.geteuid() != 0 or not os.environ.get('PKEXEC_UID'):
        raise ValueError('Run this fixture through pkexec as the desktop user')
    uid = int(os.environ['PKEXEC_UID'])
    context = json.loads(sys.stdin.buffer.read(8193))
    identity = context['identity']
    process = Path('/proc') / str(identity['process'])
    arguments = (process / 'cmdline').read_bytes().split(b'\0')
    auth_index = arguments.index(b'-auth')
    auth = Path(os.fsdecode(arguments[auth_index + 1]))
    if process.stat().st_uid != uid or auth.parent.parent != Path('/tmp') or not auth.parent.name.startswith('cyberlab-xsecurity-'):
        raise ValueError('Only an authenticated disposable Xwayland fixture is allowed')
    environment = dict(entry.split(b'=', 1) for entry in (process / 'environ').read_bytes().split(b'\0') if b'=' in entry)
    runtime = Path(os.fsdecode(environment[b'XDG_RUNTIME_DIR']))
    if runtime.parent != Path('/tmp') or not runtime.name.startswith('cyberlab-xwayland-'):
        raise ValueError('Only the headless test compositor is allowed')
    endpoint = Path(identity['socket'])
    info = endpoint.lstat()
    if info.st_uid != uid or (info.st_dev, info.st_ino) != (identity['device'], identity['inode']):
        raise ValueError('Disposable socket changed')
    with socket.socket(socket.AF_UNIX) as connection:
        connection.connect(str(endpoint))
        peer, owner, _group = struct.unpack('3i', connection.getsockopt(socket.SOL_SOCKET, socket.SO_PEERCRED, 12))
    if owner != uid or any(verified_server(endpoint, peer, uid)[key] != identity[key]
                           for key in ('process', 'start_time', 'peer', 'peer_start_time')):
        raise ValueError('Disposable server identity mismatch')
    context['uid'] = uid
    denial = subprocess.run(['/usr/bin/python3', '-I', '-c',
        'import socket,sys; connection=socket.socket(socket.AF_UNIX); connection.connect(sys.argv[1])', str(endpoint)],
        user=2000, group=2000, extra_groups=[], env={'PATH': '/usr/bin:/bin'}, capture_output=True, timeout=5)
    if denial.returncode == 0 or b'PermissionError' not in denial.stderr:
        raise ValueError('The fixture must reproduce the UID 2000 socket denial')
    print('PASS: UID 2000 cannot access the unchanged 0755 upstream socket', flush=True)
    with tempfile.TemporaryDirectory(prefix='cyberlab-guest-relay-', dir='/var/tmp') as directory:
        relay = DisplayRelay(Path(directory), context, 2000, 2000)
        auth_file = Path(directory) / 'Xauthority'
        auth_file.write_bytes(authority(context['display'], context['cookie']))
        auth_file.chmod(0o400)
        os.chown(auth_file, 2000, 2000)
        native = NativeDisplays(Path(directory))
        session = SimpleNamespace(id='fixture', owner_uid=uid)
        node = SimpleNamespace(id='client', user=SimpleNamespace(uid=2000, gid=2000))
        native.nodes[(session.id, node.id)] = {
            **context, 'relay': relay, 'directory': Path(directory), 'backend': 'native-x11',
            'requested_backend': 'native-x11', 'ready': True, 'fallback_reason': ''}
        client = docker.from_env()
        container = None
        try:
            image = client.images.get(context['fixture_image'])
            if image.labels.get('org.ptit.cyberlab.software') != 'ubuntu-apps-v1' or image.attrs['Config'].get('Volumes'):
                raise ValueError('Use a cached CyberLab software image without declared volumes')
            destination = identity['socket']
            container = client.containers.run(
                image.id, command=['sleep', '120'], entrypoint=[''], detach=True,
                name='cyberlab-relay-fixture-' + uuid4().hex[:12],
                labels={'cyberlab.fixture': 'xwayland-relay'}, user='2000:2000',
                network_mode='none', cap_drop=['ALL'], security_opt=['no-new-privileges:true'],
                read_only=True, privileged=False, mem_limit='128m', memswap_limit='128m',
                nano_cpus=1_000_000_000, pids_limit=32,
                tmpfs={'/tmp': 'rw,nosuid,nodev,size=16m'},
                **native.options(session, node))
            program = Path(__file__).with_name('x11_relay_probe.py').read_text()
            for cookie, reject in ((context['cookie'], False), ('00' * 16, True), (context['cookie'], False)):
                payload = json.dumps({'path': destination, 'cookie': cookie, 'reject': reject}).encode()
                result = execute(client.api, container.id, node, 'exec /usr/bin/python3 -I -c "$1"',
                                 [program], data=payload, maximum=128)
                assert result.strip() == (b'rejected' if reject else b'window-ready')
            with patch.object(native, 'revoke') as revoke:
                native.verify_guest(SimpleNamespace(client=client), session, node, container)
                if native.status(session, node.id)['backend'] != 'native-x11':
                    raise RuntimeError('Production guest XOpenDisplay probe failed')
                revoke.assert_not_called()
            fields = Path(f'/proc/{relay.process.pid}/status').read_text().splitlines()
            assert next(line for line in fields if line.startswith('Uid:')).split()[1:] == [str(uid)] * 4
            assert endpoint.lstat().st_mode == info.st_mode
            print('PASS: real Docker UID 2000 creates/maps X11 windows through unprivileged relay; bad cookie rejected; host socket unchanged', flush=True)
            print('PASS: production native mounts, guest Xauthority and XOpenDisplay readiness probe', flush=True)
            relay.stop()
            assert not relay.alive
        finally:
            if container is not None:
                with suppress(Exception):
                    container.remove(force=True)
            client.close()
            relay.close()


if __name__ == '__main__':
    main()
