import asyncio
from contextlib import suppress
import json
import os
from pathlib import Path
import selectors
import signal
import socket
import subprocess
import sys
import tempfile

CHUNK_SIZE = 65536

def viewer_path():
    path = Path('/usr/bin/xpra')
    if not path.is_file() or not os.access(path, os.X_OK):
        raise RuntimeError('Graphical applications require the host xpra package (not TigerVNC). Terminal practice still works; Session is kept.')
    try:
        result = subprocess.run(['/usr/bin/python3', '-I', str(Path(__file__).with_name('xpra_client.py')), '--probe'],
                                stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL, timeout=5)
    except (OSError, subprocess.TimeoutExpired):
        raise RuntimeError('Cannot check the host Xpra client; Session is kept') from None
    if result.returncode:
        raise RuntimeError('Host Xpra needs GTK3, rencodeplus and a compatible version (3 to 6); Session is kept')
    return str(path)

def viewer_command(executable, endpoint, password, node_id, compatible=False):
    command = ['/usr/bin/python3', '-I', str(Path(__file__).with_name('xpra_client.py')),
            executable, 'attach', 'socket://' + str(endpoint), '--password-file=' + str(password),
            '--challenge-handlers=file', '--clipboard=no', '--printing=no', '--file-transfer=no',
            '--open-files=no', '--open-url=no', '--speaker=disabled', '--microphone=disabled', '--webcam=no',
            '--notifications=no', '--system-tray=no', '--tray=no', '--mmap=no', '--dbus-proxy=no',
            '--dbus-control=no', '--remote-logging=no', '--sharing=no', '--opengl=no',
            '--splash=no', '--reconnect=no',
            '--bind=none',
            '--packet-encoders=rencodeplus', '--title=@title@ [CyberLab: ' + node_id + ']']
    if compatible:
        command.extend(['--cyberlab-compat', '--encoding=rgb', '--compressors=none', '-z', '0'])
    return command

def viewer_environment(root):
    environment = {key: value for key, value in os.environ.items() if not key.startswith('XPRA_')}
    environment.update(XPRA_SYSTEM_CONF_DIRS=str(root / 'no-config'),
                       XPRA_USER_CONF_DIRS=str(root / 'no-config'),
                       XPRA_DEFAULT_CONF_DIRS=str(root / 'no-config'), GDK_BACKEND='x11')
    return environment

def launch(arguments):
    from .gui_environment import inspect_environment

    environment = inspect_environment()
    if not environment['ready']:
        raise RuntimeError(environment['message'])
    command = [sys.executable, '-m', 'cyberlab_cli.main']
    if arguments.test_session_bus:
        command.append('--test-session-bus')
    command += ['desktop', arguments.id, arguments.node]
    process = subprocess.Popen(command, stdin=subprocess.DEVNULL, stdout=subprocess.PIPE,
                               stderr=subprocess.DEVNULL, start_new_session=True)
    try:
        with selectors.DefaultSelector() as selector:
            selector.register(process.stdout, selectors.EVENT_READ)
            if not selector.select(90):
                raise RuntimeError('Desktop did not open in time; Session is kept')
            response = json.loads(process.stdout.readline(4096))
        if response.get('opened') is not True:
            raise RuntimeError(response.get('error', 'Desktop could not open; Session is kept'))
        return {'opened': True, 'session': arguments.id, 'node': arguments.node}
    except Exception:
        if process.poll() is None:
            os.killpg(process.pid, signal.SIGTERM)
            try:
                process.wait(timeout=5)
            except subprocess.TimeoutExpired:
                os.killpg(process.pid, signal.SIGKILL)
                process.wait(timeout=5)
        raise
    finally:
        process.stdout.close()

class HandshakeFailure(RuntimeError):
    pass


async def interact(bus, request, session_id, node_id):
    try:
        return await _interact(bus, request, session_id, node_id)
    except HandshakeFailure:
        return await _interact(bus, request, session_id, node_id, compatible=True)


async def _interact(bus, request, session_id, node_id, compatible=False):
    handle = None
    viewer = None
    connection = None
    tasks = []
    loop = asyncio.get_running_loop()
    task = asyncio.current_task()
    handlers = {}
    for signum in (signal.SIGTERM, signal.SIGHUP):
        handlers[signum] = signal.getsignal(signum)
        loop.add_signal_handler(signum, task.cancel)
    try:
        status = json.loads(await request(bus, 'GetDesktopStatus', [session_id, node_id]))
        if status.get('backend') == 'native-x11':
            if not status.get('ready'):
                from .display_context import prepare
                token = await prepare(bus, request)
                try:
                    await request(bus, 'ReconnectNativeDesktop', [session_id, node_id, token])
                finally:
                    await request(bus, 'ReleaseDesktopContext', [token])
            print(json.dumps({'opened': True, 'backend': 'native-x11'}), flush=True)
            return
        if status.get('backend') != 'xpra':
            raise RuntimeError('The installed daemon does not support seamless applications; update CyberLab first')
        if status.get('attached'):
            print(json.dumps({'opened': True, 'existing': True}), flush=True)
            return
        executable = viewer_path()
        for _ in range(10):
            if not status.get('opening'):
                break
            await asyncio.sleep(0.5)
            status = json.loads(await request(bus, 'GetDesktopStatus', [session_id, node_id]))
            if status.get('attached'):
                print(json.dumps({'opened': True, 'existing': True}), flush=True)
                return
        if status.get('opening'):
            raise RuntimeError('Application windows are still connecting for this machine; retry shortly')
        handle, credential = await request(bus, 'OpenDesktop', [session_id, node_id])
        if not isinstance(credential, bytes) or len(credential) != 32:
            raise RuntimeError('Invalid desktop authentication response')
        with tempfile.TemporaryDirectory(prefix='cyberlab-viewer-') as temporary:
            root = Path(temporary)
            password = root / 'auth'
            descriptor = os.open(password, os.O_WRONLY | os.O_CREAT | os.O_EXCL, 0o600)
            with os.fdopen(descriptor, 'wb') as stream:
                stream.write(credential)
            endpoint = root / 'display.sock'
            with socket.socket(socket.AF_UNIX, socket.SOCK_STREAM) as listener:
                listener.bind(str(endpoint))
                os.chmod(endpoint, 0o600)
                listener.listen(1)
                listener.setblocking(False)
                viewer = await asyncio.create_subprocess_exec(*viewer_command(executable, endpoint, password, node_id, compatible),
                    env=viewer_environment(root), stdin=subprocess.DEVNULL,
                    stdout=subprocess.PIPE, stderr=subprocess.DEVNULL, limit=4096)
                accepted = asyncio.create_task(loop.sock_accept(listener))
                exited = asyncio.create_task(viewer.wait())
                tasks = [accepted, exited]
                done, _ = await asyncio.wait(tasks, timeout=15, return_when=asyncio.FIRST_COMPLETED)
                if accepted not in done or exited in done:
                    raise HandshakeFailure('Xpra could not open an application display connection; Session is kept')
                connection, _ = accepted.result()
                connection.setblocking(False)
            relay = asyncio.create_task(relay_display(bus, request, handle, connection))
            ready = asyncio.create_task(viewer.stdout.readline())
            tasks = [relay, ready, exited]
            done, _ = await asyncio.wait(tasks, timeout=20, return_when=asyncio.FIRST_COMPLETED)
            if ready not in done or ready.result() != b'CYBERLAB_APPS_READY\n' or relay in done or exited in done:
                raise HandshakeFailure('Application display handshake failed or timed out; Session is kept. Check the host and guest Xpra packages.')
            await request(bus, 'ConfirmDesktop', [handle])
            print(json.dumps({'opened': True}), flush=True)
            done, _ = await asyncio.wait([relay, exited], return_when=asyncio.FIRST_COMPLETED)
            for task in done:
                task.result()
            if relay in done and viewer.returncode is None:
                try:
                    await asyncio.wait_for(asyncio.shield(exited), timeout=1)
                except asyncio.TimeoutError:
                    raise RuntimeError('Application display connection ended; reconnect GUI. Session is kept') from None
            if viewer.returncode not in (None, 0):
                raise RuntimeError(f'Application display client exited with code {viewer.returncode}; reconnect GUI. Session is kept')
    finally:
        for background in tasks:
            background.cancel()
        await asyncio.gather(*tasks, return_exceptions=True)
        if connection:
            connection.close()
        if viewer and viewer.returncode is None:
            with suppress(ProcessLookupError):
                viewer.terminate()
            try:
                await asyncio.wait_for(viewer.wait(), timeout=3)
            except asyncio.TimeoutError:
                with suppress(ProcessLookupError):
                    viewer.kill()
                await viewer.wait()
        if handle:
            with suppress(Exception):
                await asyncio.wait_for(request(bus, 'CloseDesktop', [handle]), timeout=3)
        for signum, previous in handlers.items():
            loop.remove_signal_handler(signum)
            signal.signal(signum, previous)

async def relay_display(bus, request, handle, connection):
    loop = asyncio.get_running_loop()

    async def receive():
        delay = 0.001
        while True:
            output, ended = await request(bus, 'ReadDesktop', [handle])
            if not isinstance(output, bytes) or len(output) > CHUNK_SIZE or type(ended) is not bool:
                raise RuntimeError('Invalid application display read response')
            if output:
                await asyncio.wait_for(loop.sock_sendall(connection, output), timeout=5)
                delay = 0.001
            if ended:
                return
            if not output:
                await asyncio.sleep(delay)
                delay = min(0.02, delay * 2)

    async def send():
        while True:
            pending = await loop.sock_recv(connection, CHUNK_SIZE)
            if not pending:
                return
            deadline = loop.time() + 5
            while pending:
                accepted = await asyncio.wait_for(request(bus, 'WriteDesktop', [handle, pending]), timeout=5)
                if type(accepted) is not int or not 0 <= accepted <= len(pending):
                    raise RuntimeError('Invalid application display write acknowledgement')
                pending = pending[accepted:]
                if accepted:
                    deadline = loop.time() + 5
                elif loop.time() >= deadline:
                    raise RuntimeError('Application display write timed out')
                else:
                    await asyncio.sleep(0.001)

    tasks = [asyncio.create_task(receive()), asyncio.create_task(send())]
    try:
        done, _pending = await asyncio.wait(tasks, return_when=asyncio.FIRST_COMPLETED)
        for task in done:
            task.result()
    finally:
        for task in tasks:
            task.cancel()
        await asyncio.gather(*tasks, return_exceptions=True)

async def attach_prepared(bus, request, session_id, node_id, test_session_bus=False):
    from types import SimpleNamespace

    if not (os.environ.get('DISPLAY') or os.environ.get('WAYLAND_DISPLAY')):
        return
    try:
        status = json.loads(await request(bus, 'GetDesktopStatus', [session_id, node_id]))
    except Exception:
        return
    if status.get('backend') != 'xpra' or not status.get('ready') or not status.get('auto_connect', True) or status.get('attached'):
        return
    try:
        if not status.get('opening'):
            try:
                await asyncio.to_thread(launch, SimpleNamespace(id=session_id, node=node_id, test_session_bus=test_session_bus))
            except (RuntimeError, OSError):
                status = json.loads(await request(bus, 'GetDesktopStatus', [session_id, node_id]))
                if not (status.get('opening') or status.get('attached')):
                    raise
        deadline = asyncio.get_running_loop().time() + 25
        while asyncio.get_running_loop().time() < deadline:
            status = json.loads(await request(bus, 'GetDesktopStatus', [session_id, node_id]))
            if status.get('attached'):
                return
            await asyncio.sleep(0.2)
        raise RuntimeError('GUI connection timed out')
    except Exception:
        print('Graphical applications could not attach. Use the Applications button to retry; terminal practice still works.',
              file=sys.stderr, flush=True)
