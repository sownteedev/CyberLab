"""Local display validation and short-lived X11 helper invocation."""

import json
import os
from pathlib import Path
import pwd
import re
import socket
import stat
import struct
import subprocess
from time import monotonic, sleep

from . import x11


def helper(payload, uid=None):
    if payload.get('operation') in ('generate', 'revoke') and not x11.NATIVE_X11_ENABLED and '_fixture' not in payload:
        raise ValueError(x11.NATIVE_X11_DISABLED_REASON)
    payload = {name: payload[name] for name in ('display', 'cookie', 'authorization', 'operation', 'login', '_fixture') if name in payload}
    options = {}
    environment = {'PATH': '/usr/bin:/bin', 'LANG': 'C.UTF-8'}
    if uid is not None:
        account = pwd.getpwuid(uid)
        if os.geteuid() == 0:
            options.update(user=uid, group=account.pw_gid, extra_groups=[])
        elif uid != os.geteuid():
            raise ValueError('Wrong desktop user')
    elif os.environ.get('XAUTHORITY'):
        environment['XAUTHORITY'] = os.environ['XAUTHORITY']
    if uid is None:
        environment['HOME'] = str(Path.home())
    result = subprocess.run(['/usr/bin/python3', '-I', str(Path(x11.__file__))],
                            input=json.dumps(payload), capture_output=True, text=True,
                            env=environment, timeout=5, **options)
    if result.returncode or len(result.stdout) > 4096:
        raise ValueError('X11 authorization is unavailable')
    value = json.loads(result.stdout)
    if not isinstance(value, dict) or value.get('error'):
        raise ValueError('X11 authorization is unavailable')
    return value


def login_session(identifier, uid):
    if not re.fullmatch(r'[A-Za-z0-9_-]{1,64}', identifier):
        raise ValueError('Invalid login session')
    result = subprocess.run(['/usr/bin/loginctl', 'show-session', identifier,
                             '-p', 'Id', '-p', 'User', '-p', 'Type', '-p', 'Remote',
                             '-p', 'Display', '-p', 'Scope', '-p', 'Leader', '-p', 'State'],
                            capture_output=True, text=True, timeout=3)
    properties = dict(line.split('=', 1) for line in result.stdout.splitlines() if '=' in line)
    if result.returncode or properties.get('User') != str(uid) or properties.get('Remote') != 'no' or properties.get('State') not in ('active', 'online'):
        raise ValueError('Local desktop login could not be verified')
    return properties


def verify_display(display, login, uid):
    number = x11.display_number(display)
    properties = login_session(login, uid)
    if properties.get('Type') not in ('x11', 'wayland'):
        raise ValueError('The login session is not a local graphical desktop')
    endpoint = Path('/tmp/.X11-unix') / ('X' + number)
    directory = endpoint.parent.lstat()
    info = endpoint.lstat()
    if not stat.S_ISDIR(directory.st_mode) or directory.st_uid != 0 or not stat.S_ISSOCK(info.st_mode) or info.st_uid not in (0, uid):
        raise ValueError('Untrusted X11 socket')
    with socket.socket(socket.AF_UNIX) as connection:
        connection.settimeout(2)
        connection.connect(str(endpoint))
        process, peer_uid, _group = struct.unpack('3i', connection.getsockopt(socket.SOL_SOCKET, socket.SO_PEERCRED, 12))
    if properties['Type'] == 'wayland':
        from .xwayland import DisplayNotReady, verified_server
        if peer_uid != uid or info.st_uid != uid:
            raise ValueError('Xwayland socket belongs to another user')
        deadline = monotonic() + 1
        while True:
            try:
                identity = verified_server(endpoint, process, uid)
                break
            except DisplayNotReady:
                if monotonic() >= deadline:
                    raise
                sleep(0.05)
        current = endpoint.lstat()
        if (current.st_dev, current.st_ino) != (info.st_dev, info.st_ino):
            raise ValueError('Xwayland socket changed')
        return {'socket': str(endpoint), 'inode': info.st_ino, 'device': info.st_dev,
                'leader': properties.get('Leader', ''), **identity}
    if peer_uid not in (0, uid) or Path(f'/proc/{process}/exe').resolve().name not in ('Xorg', 'Xorg.bin'):
        raise ValueError('Display is not a verified local Xorg server')
    advertised = properties.get('Display')
    if advertised:
        if x11.display_number(advertised) != number:
            raise ValueError('Display does not match the login session')
    elif not properties.get('Scope') or properties['Scope'] not in Path(f'/proc/{process}/cgroup').read_text().split('/')[-1].strip():
        raise ValueError('Xorg does not belong to this login session')
    return {'socket': str(endpoint), 'inode': info.st_ino, 'device': info.st_dev,
            'process': process, 'leader': properties.get('Leader', '')}


def checked_display(display, login, uid):
    if os.geteuid() == 0:
        return helper({'display': display, 'login': login, 'operation': 'identity'}, uid)
    return verify_display(display, login, uid)
