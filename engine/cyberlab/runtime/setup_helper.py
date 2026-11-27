"""Fixed container-only bootstrap, sent as Python source, not author code."""

import base64
import grp
import json
import os
import pwd
import re
import stat
import subprocess
import sys

STATUS = '/run/cyberlab-setup-status'


def run(arguments, data=None):
    subprocess.run(arguments, input=data, stdout=subprocess.DEVNULL,
                   stderr=subprocess.DEVNULL, check=True, timeout=15)


def directory(root, parts):
    descriptor = os.dup(root)
    try:
        for part in parts:
            try:
                os.mkdir(part, mode=0o755, dir_fd=descriptor)
            except FileExistsError:
                pass
            child = os.open(part, os.O_RDONLY | os.O_DIRECTORY | os.O_NOFOLLOW, dir_fd=descriptor)
            os.close(descriptor)
            descriptor = child
        return descriptor
    except BaseException:
        os.close(descriptor)
        raise


def install_entry(root, path, data, uid, gid, mode, *, apply=True):
    parts = path.split('/')
    if (not parts or any(re.fullmatch(r'[A-Za-z0-9_][A-Za-z0-9_.-]{0,63}', part) is None for part in parts)
            or mode & ~0o3777 or data is not None and mode & 0o7000):
        raise ValueError('Unsafe file declaration')
    parent = directory(root, parts[:-1])
    descriptor = None
    try:
        name = parts[-1]
        try:
            status = os.stat(name, dir_fd=parent, follow_symlinks=False)
        except FileNotFoundError:
            status = None
        if status is not None:
            if data is None:
                if not stat.S_ISDIR(status.st_mode):
                    raise ValueError('Destination is not a directory')
            elif not stat.S_ISREG(status.st_mode) or status.st_nlink != 1 or status.st_mode & 0o111:
                raise ValueError('Cannot replace linked, special or executable files')
        if data is None:
            try:
                os.mkdir(name, mode=0o755, dir_fd=parent)
            except FileExistsError:
                pass
            descriptor = os.open(name, os.O_RDONLY | os.O_DIRECTORY | os.O_NOFOLLOW, dir_fd=parent)
        else:
            descriptor = os.open(name, os.O_WRONLY | os.O_CREAT | os.O_NOFOLLOW | os.O_NONBLOCK,
                                 0o600, dir_fd=parent)
            actual = os.fstat(descriptor)
            if (not stat.S_ISREG(actual.st_mode) or actual.st_nlink != 1
                    or status is not None and (actual.st_ino, actual.st_dev) != (status.st_ino, status.st_dev)):
                raise ValueError('Destination changed during setup')
            os.ftruncate(descriptor, 0)
            with os.fdopen(os.dup(descriptor), 'wb') as output:
                output.write(data)
        if apply:
            os.fchown(descriptor, uid, gid)
            os.fchmod(descriptor, mode)
    finally:
        if descriptor is not None:
            os.close(descriptor)
        os.close(parent)


def available(name, numeric, lookup_name, lookup_id):
    for lookup, value in ((lookup_name, name), (lookup_id, numeric)):
        try:
            lookup(value)
        except KeyError:
            continue
        raise ValueError('Account or group already exists in the image')


def sudo_policy(name, mode):
    path = '/etc/sudoers.d/cyberlab-' + name
    data = f'{name} ALL=(ALL:ALL) {"NOPASSWD: " if mode == "passwordless" else ""}ALL\n'
    if mode == 'disabled':
        data = ''
    descriptor = os.open(path, os.O_WRONLY | os.O_CREAT | os.O_EXCL | os.O_NOFOLLOW, 0o440)
    with os.fdopen(descriptor, 'w') as output:
        output.write(data)
    run(['/usr/sbin/visudo', '-cf', path])


def configure(payload):
    user, setup = payload['user'], payload['setup']
    main = pwd.getpwnam('student')
    if (main.pw_uid, main.pw_gid, main.pw_dir, main.pw_shell) != (2000, 2000, '/home/student', '/bin/bash'):
        raise ValueError('Unsupported base account')
    if os.path.islink('/home/student') or not os.path.isdir('/home/student'):
        raise ValueError('Invalid base home')
    if user['name'] != 'student':
        if os.path.lexists(user['home']):
            raise ValueError('Main home already exists')
        available(user['name'], -1, pwd.getpwnam, pwd.getpwuid)
        available(user['name'], -1, grp.getgrnam, grp.getgrgid)
    for account in setup['users']:
        available(account['name'], account['uid'], pwd.getpwnam, pwd.getpwuid)
        available(account['name'], account['gid'], grp.getgrnam, grp.getgrgid)
        if os.path.lexists('/home/' + account['name']):
            raise ValueError('Extra account home already exists')
    for group in setup['groups']:
        available(group['name'], group['gid'], grp.getgrnam, grp.getgrgid)
    if user['name'] != 'student':
        run(['/usr/sbin/groupmod', '--new-name', user['name'], 'student'])
        run(['/usr/sbin/usermod', '--login', user['name'], '--home', user['home'], '--move-home', 'student'])
    for group in setup['groups']:
        run(['/usr/sbin/groupadd', '--gid', str(group['gid']), group['name']])
    for account in setup['users']:
        run(['/usr/sbin/groupadd', '--gid', str(account['gid']), account['name']])
        run(['/usr/sbin/useradd', '--uid', str(account['uid']), '--gid', str(account['gid']),
             '--create-home', '--no-log-init', '--shell', '/bin/bash', account['name']])
        if account['groups']:
            run(['/usr/sbin/usermod', '--groups', ','.join(account['groups']), account['name']])
    existing = os.stat('/etc/sudoers.d/student', follow_symlinks=False)
    if not stat.S_ISREG(existing.st_mode) or existing.st_nlink != 1:
        raise ValueError('Unsafe default sudo policy')
    os.unlink('/etc/sudoers.d/student')
    for group in grp.getgrall():
        if group.gr_name in ('sudo', 'admin') and user['name'] in group.gr_mem:
            run(['/usr/bin/gpasswd', '-d', user['name'], group.gr_name])
    for account in [dict(name=user['name'], sudo=setup['sudo'], password_hash=setup['password_hash']), *setup['users']]:
        if account['password_hash']:
            run(['/usr/sbin/chpasswd', '-e'], (account['name'] + ':' + account['password_hash'] + '\n').encode())
        sudo_policy(account['name'], account['sudo'])
    root = os.open('/', os.O_RDONLY | os.O_DIRECTORY)
    try:
        for entry in payload['entries']:
            data = base64.b64decode(entry['data'], validate=True) if entry['data'] is not None else None
            install_entry(root, entry['path'], data, pwd.getpwnam(entry['owner']).pw_uid,
                          grp.getgrnam(entry['group']).gr_gid, int(entry['mode'], 8), apply=entry['apply'])
    finally:
        os.close(root)


def main():
    try:
        raw = sys.stdin.buffer.read(24 * 1024 * 1024 + 1)
        if len(raw) > 24 * 1024 * 1024:
            raise ValueError('Setup exceeds its limit')
        payload = json.loads(raw)
        configure(payload)
        with open(STATUS, 'x', encoding='ascii') as status:
            status.write('ready')
        os.chdir(payload['user']['home'])
        os.execv('/usr/sbin/runuser', ['runuser', '--user', payload['user']['name'], '--', *sys.argv[1:]])
    except Exception:
        try:
            with open(STATUS, 'w', encoding='ascii') as status:
                status.write('failed')
        finally:
            sys.exit(125)


if __name__ == '__main__':
    main()
