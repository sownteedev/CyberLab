#!/usr/bin/env python3
"""Real Xpra window forwarding on two temporary displays; no Docker or user data."""

import argparse
import asyncio
import ctypes
import json
import os
from pathlib import Path
import signal
import socket
import subprocess
import sys
import tempfile
from unittest.mock import patch

ROOT = Path(__file__).resolve().parents[3]
sys.dont_write_bytecode = True
sys.path[:0] = [str(ROOT / 'engine'), str(ROOT / 'cli')]


def window_names(display, *, with_ids=False):
    library = ctypes.CDLL('libX11.so.6')
    library.XOpenDisplay.argtypes = [ctypes.c_char_p]
    library.XOpenDisplay.restype = ctypes.c_void_p
    library.XDefaultRootWindow.argtypes = [ctypes.c_void_p]
    library.XDefaultRootWindow.restype = ctypes.c_ulong
    library.XQueryTree.argtypes = [ctypes.c_void_p, ctypes.c_ulong, ctypes.POINTER(ctypes.c_ulong),
                                  ctypes.POINTER(ctypes.c_ulong), ctypes.POINTER(ctypes.POINTER(ctypes.c_ulong)),
                                  ctypes.POINTER(ctypes.c_uint)]
    library.XFetchName.argtypes = [ctypes.c_void_p, ctypes.c_ulong, ctypes.POINTER(ctypes.c_void_p)]
    library.XInternAtom.argtypes = [ctypes.c_void_p, ctypes.c_char_p, ctypes.c_int]
    library.XInternAtom.restype = ctypes.c_ulong
    library.XGetWindowProperty.argtypes = [ctypes.c_void_p, ctypes.c_ulong, ctypes.c_ulong,
                                           ctypes.c_long, ctypes.c_long, ctypes.c_int, ctypes.c_ulong,
                                           ctypes.POINTER(ctypes.c_ulong), ctypes.POINTER(ctypes.c_int),
                                           ctypes.POINTER(ctypes.c_ulong), ctypes.POINTER(ctypes.c_ulong),
                                           ctypes.POINTER(ctypes.POINTER(ctypes.c_ubyte))]
    library.XGetWindowProperty.restype = ctypes.c_int
    library.XFree.argtypes = [ctypes.c_void_p]
    library.XCloseDisplay.argtypes = [ctypes.c_void_p]
    connection = library.XOpenDisplay(display.encode())
    if not connection:
        return []
    names = []
    net_wm_name = library.XInternAtom(connection, b'_NET_WM_NAME', 0)
    def visit(window, depth=0):
        title = ctypes.c_void_p()
        name = None
        if library.XFetchName(connection, window, ctypes.byref(title)) and title.value:
            name = ctypes.string_at(title).decode(errors='replace')
            library.XFree(title)
        if not name and net_wm_name:
            actual_type, format_value = ctypes.c_ulong(), ctypes.c_int()
            item_count, bytes_after = ctypes.c_ulong(), ctypes.c_ulong()
            value = ctypes.POINTER(ctypes.c_ubyte)()
            if library.XGetWindowProperty(connection, window, net_wm_name, 0, 1024, 0, 0,
                                          ctypes.byref(actual_type), ctypes.byref(format_value),
                                          ctypes.byref(item_count), ctypes.byref(bytes_after),
                                          ctypes.byref(value)) == 0 and value and item_count.value:
                name = ctypes.string_at(value, item_count.value).decode(errors='replace')
                library.XFree(value)
        if name:
            names.append((window, name) if with_ids else name)
        if depth >= 3:
            return
        root, parent, count = ctypes.c_ulong(), ctypes.c_ulong(), ctypes.c_uint()
        children = ctypes.POINTER(ctypes.c_ulong)()
        if library.XQueryTree(connection, window, ctypes.byref(root), ctypes.byref(parent), ctypes.byref(children), ctypes.byref(count)):
            try:
                for index in range(count.value):
                    visit(children[index], depth + 1)
            finally:
                library.XFree(children)
    try:
        visit(library.XDefaultRootWindow(connection))
        return names
    finally:
        library.XCloseDisplay(connection)


async def verify(arguments):
    from cyberlab.runtime.desktop import SETUP
    from cyberlab_cli.desktop import interact, viewer_environment

    with tempfile.TemporaryDirectory(prefix='cyberlab-seamless-real-') as temporary:
        root = Path(temporary)
        for folder in ('home', 'runtime', 'config', 'guest'):
            (root / folder).mkdir(mode=0o700)
        environment = viewer_environment(root)
        environment.update(HOME=str(root / 'home'), XDG_RUNTIME_DIR=str(root / 'runtime'),
                           XDG_CONFIG_HOME=str(root / 'config'), GDK_BACKEND='x11')
        environment.pop('DBUS_SESSION_BUS_ADDRESS', None)
        environment.pop('XAUTHORITY', None)
        environment.pop('WAYLAND_DISPLAY', None)
        read_fd, write_fd = os.pipe()
        display = subprocess.Popen([arguments.xvfb, '-displayfd', str(write_fd), '-screen', '0', '1280x800x24',
                                    '-nolisten', 'tcp', '-ac'], pass_fds=[write_fd], env=environment,
                                   stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL, start_new_session=True)
        os.close(write_fd)
        processes = [display]
        relay = None
        server_pid = None
        connection = None
        try:
            import select
            if not select.select([read_fd], [], [], 10)[0]:
                raise RuntimeError('Temporary host display did not start')
            host_display = ':' + os.read(read_fd, 32).decode().strip()
            guest_display = ':' + str(10000 + os.getpid() % 20000)
            if Path('/tmp/.X11-unix/X' + guest_display[1:]).exists():
                raise RuntimeError('Temporary guest display already exists; retry')
            program = SETUP.replace('/tmp/cyberlab-apps', str(root / 'guest')).replace(':99', guest_display)
            program = program.replace('/usr/bin/Xvfb', arguments.xvfb)
            program = program.replace('stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL',
                                      "stdout=open(" + repr(str(root / 'server.log')) + ", 'wb'), stderr=subprocess.STDOUT")
            credential = b'0123456789abcdef0123456789abcdef'
            setup = subprocess.run(['/usr/bin/python3', '-I', '-c', program, credential.decode(), 'isolated-check'],
                                   env=environment, capture_output=True, timeout=20)
            pid_file = root / 'guest/xpra.pid'
            if pid_file.exists():
                server_pid = int(pid_file.read_text())
            if setup.returncode or setup.stdout != credential:
                log = (root / 'server.log').read_text(errors='replace')[-2500:] if (root / 'server.log').exists() else ''
                raise RuntimeError('Real Xpra server startup failed: ' + setup.stderr.decode(errors='replace')[-1000:] + log)
            environment['DISPLAY'] = host_display
            os.environ.clear()
            os.environ.update(environment)
            confirmed = False
            closed = False
            async def request(bus, operation, body):
                nonlocal confirmed, closed, connection
                if operation == 'GetDesktopStatus':
                    return json.dumps({'backend': 'xpra', 'ready': True})
                if operation == 'OpenDesktop':
                    return ['fixture-handle', credential]
                if operation == 'ConfirmDesktop':
                    confirmed = True
                    return True
                if operation == 'ReadDesktop':
                    if connection is None:
                        return [b'', False]
                    try:
                        data = connection.recv(65536)
                        return [data, not data]
                    except BlockingIOError:
                        return [b'', False]
                if operation == 'WriteDesktop':
                    if connection is None:
                        connection = socket.socket(socket.AF_UNIX)
                        connection.connect(str(root / 'guest/display.sock'))
                        connection.setblocking(False)
                    try:
                        return connection.send(body[1])
                    except BlockingIOError:
                        return 0
                if operation == 'CloseDesktop':
                    closed = True
                    if connection:
                        connection.close()
                        connection = None
                    return True
                raise AssertionError(operation)
            spawn = asyncio.create_subprocess_exec
            log_stream = (root / 'client.log').open('wb')
            async def logged_spawn(*args, **kwargs):
                kwargs['stderr'] = log_stream
                return await spawn(*args, **kwargs)
            async def attach():
                with patch('cyberlab_cli.desktop.asyncio.create_subprocess_exec', logged_spawn):
                    return await interact(None, request, 'fixture-session', 'machine')
            relay = asyncio.create_task(attach())
            for attempt in range(300):
                if relay.done():
                    relay.result()
                    raise AssertionError('Client exited before verification')
                if confirmed:
                    break
                await asyncio.sleep(0.1)
            assert confirmed, 'No authenticated startup-complete handshake'
            application = '''import gi
gi.require_version('Gtk', '3.0')
from gi.repository import Gtk
windows = [Gtk.Window(title='CyberLab fixture one'), Gtk.Window(title='CyberLab fixture two')]
for window in windows:
    window.set_default_size(260, 160)
    window.show_all()
Gtk.main()
'''
            guest_environment = dict(environment, DISPLAY=guest_display, XAUTHORITY=str(root / 'guest/Xauthority'))
            app = subprocess.Popen(['/usr/bin/python3', '-I', '-c', application], env=guest_environment,
                                   stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL, start_new_session=True)
            processes.append(app)
            for attempt in range(100):
                names = window_names(host_display)
                if any('fixture one' in name for name in names) and any('fixture two' in name for name in names):
                    break
                if relay.done():
                    relay.result()
                await asyncio.sleep(0.1)
            else:
                raise AssertionError('Two separate application windows did not reach the temporary host display')
            print('PASS: two guest application windows forwarded separately after authenticated handshake')
            relay.cancel()
            await asyncio.gather(relay, return_exceptions=True)
            assert closed, 'Attachment was not closed'
            assert app.poll() is None, 'Detaching killed guest applications'
            assert not any('fixture one' in name or 'fixture two' in name for name in window_names(host_display)), 'Client windows leaked'
            print('PASS: detaching closes only forwarded windows and preserves guest applications')
            confirmed = closed = False
            relay = asyncio.create_task(attach())
            for attempt in range(300):
                if relay.done():
                    relay.result()
                    raise AssertionError('Reconnect exited')
                names = window_names(host_display)
                if confirmed and any('fixture one' in name for name in names) and any('fixture two' in name for name in names):
                    break
                await asyncio.sleep(0.1)
            else:
                raise AssertionError('Existing application windows were not restored on reconnect')
            print('PASS: reconnect restores both application windows without restarting their processes')
        except Exception:
            for name in ('client.log', 'server.log'):
                if (root / name).exists():
                    print(name + ':\n' + (root / name).read_text(errors='replace')[-4500:], file=sys.stderr)
            raise
        finally:
            if relay:
                relay.cancel()
                await asyncio.gather(relay, return_exceptions=True)
            if connection:
                connection.close()
            if 'log_stream' in locals():
                log_stream.close()
            if server_pid:
                try:
                    os.kill(server_pid, signal.SIGTERM)
                except ProcessLookupError:
                    pass
                await asyncio.sleep(1)
            for process in reversed(processes):
                if process.poll() is None:
                    process.terminate()
                try:
                    process.wait(timeout=5)
                except subprocess.TimeoutExpired:
                    process.kill()
                    process.wait(timeout=5)
            os.close(read_fd)


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--xvfb', required=True, help='Absolute path to an existing Xvfb binary')
    asyncio.run(verify(parser.parse_args()))
