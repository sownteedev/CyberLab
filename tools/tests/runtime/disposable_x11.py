"""Authenticated, dynamically allocated X server with an owned process lifetime."""

from contextlib import contextmanager, suppress
import os
from pathlib import Path
import resource
import secrets
import select
import signal
import socket
import subprocess
import tempfile

from cyberlab.host_display import helper
from cyberlab.x11 import authority


def disable_core_dumps():
    resource.setrlimit(resource.RLIMIT_CORE, (0, 0))


@contextmanager
def disposable_display(executable, wayland_environment=None, activated=False):
    executable = Path(executable).resolve(strict=True)
    if executable.name not in ('Xvfb', 'Xwayland') or os.geteuid() == 0:
        raise ValueError('Run the isolated test as an ordinary user with Xvfb or Xwayland')
    with tempfile.TemporaryDirectory(prefix='cyberlab-xsecurity-') as directory:
        root = Path(directory)
        cookie = secrets.token_hex(16)
        authentication = root / 'server-auth'
        authentication.write_bytes(authority(':0', cookie))
        authentication.chmod(0o600)
        environment = {'PATH': '/usr/bin:/bin', 'HOME': str(root), 'XDG_CONFIG_HOME': str(root), 'LANG': 'C.UTF-8'}
        arguments = ['-screen', '0', '800x600x24']
        if executable.name == 'Xwayland':
            if not wayland_environment or set(wayland_environment) != {'XDG_RUNTIME_DIR', 'WAYLAND_DISPLAY'}:
                raise ValueError('Xwayland needs an isolated Wayland compositor')
            environment.update(wayland_environment)
            arguments = ['-shm', '-geometry', '800x600']
        read_fd, write_fd = os.pipe()
        process = None
        listener = None
        listener_path = None
        listener_inode = None
        try:
            descriptors = [write_fd]
            if activated:
                if executable.name != 'Xwayland':
                    raise ValueError('Socket activation fixture requires Xwayland')
                listener = socket.socket(socket.AF_UNIX)
                for _attempt in range(100):
                    number = str(1000 + secrets.randbelow(9000))
                    candidate = Path('/tmp/.X11-unix') / ('X' + number)
                    try:
                        listener.bind(str(candidate))
                    except OSError:
                        continue
                    listener_path = candidate
                    listener_inode = candidate.lstat().st_ino
                    break
                if listener_path is None:
                    raise RuntimeError('No disposable listener available')
                listener.listen()
                descriptors.append(listener.fileno())
                arguments.extend([':' + number, '-listenfd', str(listener.fileno())])
            process = subprocess.Popen(
                [str(executable), '-displayfd', str(write_fd), '-auth', str(authentication),
                 '-noreset', '-nolisten', 'tcp', *arguments],
                stdin=subprocess.DEVNULL, stdout=subprocess.DEVNULL,
                stderr=None if executable.name == 'Xwayland' else subprocess.DEVNULL,
                pass_fds=descriptors, env=environment, start_new_session=wayland_environment is None,
                preexec_fn=disable_core_dumps)
            os.close(write_fd)
            write_fd = None
            if not select.select([read_fd], [], [], 10)[0]:
                raise RuntimeError('Disposable X server startup timed out')
            number = os.read(read_fd, 32).decode('ascii').strip()
            if not number.isdecimal() or process.poll() is not None:
                raise RuntimeError('Disposable X server failed to start')
            fields = Path(f'/proc/{process.pid}/stat').read_text().rsplit(')', 1)[1].split()
            owner = {'display': ':' + number, 'cookie': cookie,
                     '_fixture': {'pid': process.pid, 'start_time': fields[19]}}
            if not helper({**owner, 'operation': 'probe'}).get('ready'):
                raise RuntimeError('Disposable X server did not authenticate')
            yield owner, process
        finally:
            os.close(read_fd)
            if write_fd is not None:
                os.close(write_fd)
            if process is not None:
                if process.poll() is None:
                    with suppress(ProcessLookupError):
                        if wayland_environment is None:
                            os.killpg(process.pid, signal.SIGTERM)
                        else:
                            process.terminate()
                try:
                    process.wait(timeout=5)
                except subprocess.TimeoutExpired:
                    if wayland_environment is None:
                        os.killpg(process.pid, signal.SIGKILL)
                    else:
                        process.kill()
                    process.wait()
            if listener is not None:
                listener.close()
            if listener_path is not None:
                with suppress(FileNotFoundError):
                    if listener_path.lstat().st_ino == listener_inode:
                        listener_path.unlink()
