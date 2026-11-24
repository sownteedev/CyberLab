"""Daemon-owned listener and unprivileged XWayland forwarding lifetime."""

from contextlib import suppress
import json
import os
from pathlib import Path
import pwd
import select
import socket
import subprocess

from cyberlab import x11_relay


class DisplayRelay:
    def __init__(self, directory, context, guest_uid, guest_gid):
        self.path = directory / 'Xsocket'
        self.listener = socket.socket(socket.AF_UNIX)
        self.process = None
        self.worker_options = {}
        self.inode = None
        self.guest_uid = guest_uid
        try:
            self.listener.bind(str(self.path))
            self.inode = self.path.lstat().st_ino
            os.chmod(self.path, 0o600)
            os.chown(self.path, guest_uid, guest_gid)
            self.listener.listen(32)
            self.restart(context)
        except BaseException:
            self.close()
            raise

    def restart(self, context):
        self.stop()
        uid = context['uid']
        options = {}
        if os.geteuid() == 0:
            account = pwd.getpwuid(uid)
            options.update(user=uid, group=account.pw_gid, extra_groups=[])
        elif uid != os.geteuid():
            raise ValueError('Wrong desktop user')
        self.worker_options = options
        self.process = subprocess.Popen(
            ['/usr/bin/python3', '-I', str(Path(x11_relay.__file__)), str(self.listener.fileno())],
            stdin=subprocess.PIPE, stdout=subprocess.PIPE, stderr=subprocess.DEVNULL,
            pass_fds=[self.listener.fileno()], env={'PATH': '/usr/bin:/bin', 'LANG': 'C.UTF-8'}, **options)
        try:
            payload = {'identity': context['identity'], 'cookie': context['cookie'], 'guest_uid': self.guest_uid}
            self.process.stdin.write(json.dumps(payload).encode() + b'\n')
            self.process.stdin.flush()
            if not select.select([self.process.stdout], [], [], 5)[0] or self.process.stdout.readline(32) != b'ready\n':
                raise ValueError('XWayland relay failed to start')
        except BaseException:
            self.stop()
            raise

    @property
    def alive(self):
        return self.process is not None and self.process.poll() is None

    def stop(self):
        if self.process is None:
            return
        with suppress(OSError):
            self.process.stdin.close()
        try:
            self.process.wait(timeout=3)
        except subprocess.TimeoutExpired:
            self._signal('TERM')
            try:
                self.process.wait(timeout=2)
            except subprocess.TimeoutExpired:
                self._signal('KILL')
                self.process.wait()
        self.process.stdout.close()
        self.process = None

    def _signal(self, name):
        if self.process.poll() is None:
            subprocess.run(['/usr/bin/kill', '-' + name, str(self.process.pid)],
                           env={'PATH': '/usr/bin:/bin'}, stdin=subprocess.DEVNULL,
                           stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL,
                           timeout=3, check=False, **self.worker_options)

    def close(self):
        self.stop()
        self.listener.close()
        with suppress(FileNotFoundError):
            if self.inode is not None and self.path.lstat().st_ino == self.inode:
                self.path.unlink()
