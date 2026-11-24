"""Bounded setup delivery to a fresh container, with an explicit readiness gate."""

import base64
from dataclasses import asdict
import json
from pathlib import Path
import socket
from time import monotonic, sleep

from docker.errors import DockerException
from cyberlab.lab.setup import validate_setup, validate_setup_seed
from . import RuntimeFailure
from .docker_terminal import close_stream
from .setup_helper import STATUS


def setup_command(node, command):
    validate_setup(node)
    return ['/usr/bin/python3', '-I', '-c', Path(__file__).with_name('setup_helper.py').read_text(), *command]


def setup_payload(node):
    validate_setup_seed(node)
    entries = []
    home_permissions = {entry.path: entry for entry in node.setup.home}
    system_permissions = {entry.target[1:]: entry for entry in node.setup.files}
    for seed, permissions, prefix in ((node.seed, home_permissions, node.user.home[1:] + '/'),
                                      (node.system_seed, system_permissions, '')):
        for entry in seed:
            permission = permissions.get(entry.path)
            if permission is None and not prefix:
                parents = [target for target in system_permissions if entry.path.startswith(target + '/')]
                permission = system_permissions[max(parents, key=len)] if parents else None
            owner = permission.owner if permission else node.user.name if prefix else 'root'
            group = permission.group if permission else node.user.name if prefix else 'root'
            mode = permission.mode if permission else '0755' if entry.data is None else '0644'
            if permission and entry.path not in permissions and entry.data is not None:
                mode = format(int(mode, 8) & 0o666, '04o')
            entries.append(dict(path=prefix + entry.path, owner=owner, group=group, mode=mode,
                                apply=bool(prefix or permission),
                                data=base64.b64encode(entry.data).decode('ascii') if entry.data is not None else None))
    payload = json.dumps(dict(user=asdict(node.user), setup=asdict(node.setup), entries=entries), separators=(',', ':')).encode()
    if len(payload) > 2 * 1024 * 1024:
        raise RuntimeFailure('Machine setup exceeds its transfer limit')
    return payload


def configure_container(container, node, timeout=60):
    stream = None
    try:
        payload = setup_payload(node)
        stream = container.attach_socket(params={'stdin': 1, 'stdout': 0, 'stderr': 0, 'stream': 1})
        connection = getattr(stream, '_sock', stream)
        connection.settimeout(timeout)
        connection.sendall(payload)
        connection.shutdown(socket.SHUT_WR)
        deadline = monotonic() + timeout
        while monotonic() < deadline:
            result = container.exec_run(['/bin/cat', STATUS], user='0:0', privileged=False, stderr=False)
            if result.exit_code == 0:
                if result.output == b'ready':
                    return
                raise RuntimeFailure('Machine account/file setup failed; check image conflicts')
            container.reload()
            if container.status != 'running':
                raise RuntimeFailure('Machine stopped during account/file setup')
            sleep(0.1)
        raise RuntimeFailure('Machine setup timed out; terminals were not opened')
    except (DockerException, OSError):
        raise RuntimeFailure('Cannot transfer machine setup to the practice container') from None
    finally:
        if stream is not None:
            close_stream(stream)
