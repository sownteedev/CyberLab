"""Declarative setup policy, independent of Docker and authoring UI."""

import re
from pathlib import PurePosixPath

from .assets import valid_path
from .models import NodeSetup, SetupUser, SetupGroup, SetupFile, HomePermission
from .workstation import validate_workstation, workstation_user

SYSTEM_ROOTS = ('/etc', '/usr/local', '/opt', '/srv', '/var/lib', '/home', '/shared_stuff')
PROTECTED = ('/etc/passwd', '/etc/group', '/etc/shadow', '/etc/gshadow', '/etc/sudoers',
             '/etc/sudoers.d', '/etc/pam.d', '/etc/security', '/etc/login.defs',
             '/etc/subuid', '/etc/subgid', '/etc/nsswitch.conf', '/etc/ld.so.conf',
             '/etc/ld.so.conf.d', '/etc/ld.so.preload', '/etc/environment', '/etc/profile',
             '/etc/profile.d', '/etc/bash.bashrc', '/etc/cron.d', '/etc/crontab',
             '/etc/cron.daily', '/etc/cron.hourly', '/etc/cron.weekly', '/etc/cron.monthly',
             '/etc/systemd', '/etc/init.d', '/etc/rc.local', '/etc/ssh', '/etc/apt',
             '/etc/polkit-1', '/etc/dbus-1', '/etc/ssl', '/etc/alternatives')


def parse_setup(document):
    if document is None:
        return None
    return NodeSetup(
        users=tuple(SetupUser(**{**user, 'groups': tuple(user.get('groups', []))})
                    for user in document.get('users', [])),
        groups=tuple(SetupGroup(**group) for group in document.get('groups', [])),
        files=tuple(SetupFile(**entry) for entry in document.get('files', [])),
        home=tuple(HomePermission(**entry) for entry in document.get('home', [])),
        sudo=document.get('sudo', 'passwordless'), password_hash=document.get('password_hash', ''),
    )


def validate_target(target):
    if (not isinstance(target, str) or not target.startswith('/') or not valid_path(target[1:])
            or len(PurePosixPath(target).parts) > 8
            or not any(target.startswith(root + '/') or target == root == '/shared_stuff'
                       for root in SYSTEM_ROOTS)
            or any(target == path or target.startswith(path + '/') for path in PROTECTED)
            or any('cyberlab' in part.lower() for part in target.split('/'))):
        raise ValueError('System file destination is protected or invalid')


def validate_hash(value, *, unchanged=False):
    if value == '!' or unchanged and value == '':
        return
    if not isinstance(value, str) or re.fullmatch(r'\$6\$[./A-Za-z0-9]{1,16}\$[./A-Za-z0-9]{86}', value) is None:
        raise ValueError('Lab password must be locked or a supported password hash')


def validate_setup(node):
    setup = node.setup
    if setup is None:
        if node.system_seed:
            raise ValueError('System files require a setup declaration')
        return
    validate_workstation(node)
    if len(setup.users) > 32 or len(setup.groups) > 32 or len(setup.files) > 128 or len(setup.home) > 128:
        raise ValueError('Machine setup exceeds its entry limit')
    users = {'root', 'student', node.user.name}
    groups = set(users)
    uids, gids = {0, 2000}, {0, 2000}
    for group in (*setup.groups, *[SetupGroup(user.name, user.gid) for user in setup.users]):
        workstation_user(group.name)
        if group.name in groups or type(group.gid) is not int or not 3000 <= group.gid <= 59999 or group.gid in gids:
            raise ValueError('Duplicate or reserved group name/ID')
        groups.add(group.name)
        gids.add(group.gid)
    for user in setup.users:
        workstation_user(user.name)
        if user.name in users or type(user.uid) is not int or not 3000 <= user.uid <= 59999 or user.uid in uids:
            raise ValueError('Duplicate or reserved account name/ID')
        if len(user.groups) > 32 or len(set(user.groups)) != len(user.groups) or any(group not in groups - {'root', 'student', node.user.name} for group in user.groups):
            raise ValueError('Unknown or reserved supplementary group')
        users.add(user.name)
        uids.add(user.uid)
        if user.sudo not in ('disabled', 'password', 'passwordless'):
            raise ValueError('Unsupported sudo permission')
        validate_hash(user.password_hash)
    if node.user.name != 'student':
        users.discard('student')
        groups.discard('student')
    if setup.sudo not in ('disabled', 'password', 'passwordless'):
        raise ValueError('Unsupported sudo permission')
    validate_hash(setup.password_hash, unchanged=True)
    targets, home_paths = set(), set()
    for entry in (*setup.files, *setup.home):
        if entry.owner not in users or entry.group not in groups:
            raise ValueError('File owner/group does not exist; select a replacement before deleting an account')
        if not isinstance(entry.mode, str) or re.fullmatch(r'[0-3][0-7]{3}', entry.mode) is None:
            raise ValueError('Permissions require four octal digits without setuid')
        if isinstance(entry, SetupFile):
            validate_target(entry.target)
            if not valid_path(entry.source) or not entry.source.startswith('assets/') or entry.target in targets:
                raise ValueError('Invalid or duplicate System file mapping')
            if entry.target == node.user.home or entry.target.startswith(node.user.home + '/'):
                raise ValueError('Use Home for the terminal account files')
            targets.add(entry.target)
        else:
            if not valid_path(entry.path) or entry.path in home_paths:
                raise ValueError('Invalid or duplicate Home permission path')
            home_paths.add(entry.path)


def validate_setup_seed(node):
    validate_setup(node)
    if node.setup is None:
        return
    home = {entry.path: entry for entry in node.seed}
    system = {entry.path: entry for entry in node.system_seed}
    for entry in node.setup.home:
        if entry.path not in home:
            raise ValueError('Home permission refers to a missing file')
        if home[entry.path].data is not None and int(entry.mode, 8) & 0o7000:
            raise ValueError('Special permissions are only supported on directories')
    for entry in node.setup.files:
        if entry.target[1:] not in system:
            raise ValueError('System file mapping has not been loaded')
        if system[entry.target[1:]].data is not None and int(entry.mode, 8) & 0o7000:
            raise ValueError('Special permissions are only supported on directories')
    for entry in node.system_seed:
        target = '/' + entry.path
        declared = any(target == mapping.target or target.startswith(mapping.target + '/') for mapping in node.setup.files)
        if declared:
            validate_target(target)
            if target == node.user.home or target.startswith(node.user.home + '/'):
                raise ValueError('Use Home for the terminal account files')
        elif entry.data is not None or not any(mapping.target.startswith(target + '/') for mapping in node.setup.files):
            raise ValueError('Undeclared System file')
