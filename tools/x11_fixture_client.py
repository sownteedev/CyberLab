"""Small owned-display client for revocation tests; never uses inherited credentials."""

import ctypes
import json
from pathlib import Path
import select
import sys

sys.dont_write_bytecode = True
sys.path.insert(0, str(Path(__file__).resolve().parents[1] / 'engine'))
from cyberlab.x11 import require_disposable_server


def main():
    incoming = sys.stdin.buffer.readline(4097)
    if len(incoming) > 4096:
        raise ValueError('Oversized fixture request')
    payload = json.loads(incoming)
    require_disposable_server(payload)
    cookie = bytes.fromhex(payload['cookie'])
    if len(cookie) != 16:
        raise ValueError('Invalid fixture credential')
    library = ctypes.CDLL('libX11.so.6')
    library.XSetAuthorization.argtypes = [ctypes.c_char_p, ctypes.c_int, ctypes.c_char_p, ctypes.c_int]
    library.XSetAuthorization(b'MIT-MAGIC-COOKIE-1', 18, cookie, 16)
    library.XOpenDisplay.argtypes = [ctypes.c_char_p]
    library.XOpenDisplay.restype = ctypes.c_void_p
    library.XCloseDisplay.argtypes = [ctypes.c_void_p]
    library.XSync.argtypes = [ctypes.c_void_p, ctypes.c_int]
    library.XPending.argtypes = [ctypes.c_void_p]
    library.XConnectionNumber.argtypes = [ctypes.c_void_p]
    library.XDefaultRootWindow.argtypes = [ctypes.c_void_p]
    library.XDefaultRootWindow.restype = ctypes.c_ulong
    library.XCreateSimpleWindow.argtypes = [ctypes.c_void_p, ctypes.c_ulong, ctypes.c_int, ctypes.c_int,
                                           ctypes.c_uint, ctypes.c_uint, ctypes.c_uint, ctypes.c_ulong, ctypes.c_ulong]
    library.XCreateSimpleWindow.restype = ctypes.c_ulong
    library.XMapWindow.argtypes = [ctypes.c_void_p, ctypes.c_ulong]
    display = library.XOpenDisplay(payload['display'].encode())
    if not display:
        raise ValueError('Fixture display did not authenticate')
    try:
        window = library.XCreateSimpleWindow(display, library.XDefaultRootWindow(display), 10, 10, 240, 140, 0, 0, 0)
        library.XMapWindow(display, window)
        library.XSync(display, 0)
        print('ready', flush=True)
        descriptor = library.XConnectionNumber(display)
        while True:
            readable, _, _ = select.select([sys.stdin.fileno(), descriptor], [], [], 15)
            if not readable:
                raise ValueError('Fixture client timed out')
            if descriptor in readable:
                library.XPending(display)
            if sys.stdin.fileno() in readable:
                command = sys.stdin.buffer.readline(16)
                if command != b'ping\n':
                    break
                library.XSync(display, 0)
                print('pong', flush=True)
    finally:
        library.XCloseDisplay(display)


if __name__ == '__main__':
    try:
        main()
    except Exception:
        print('Fixture client failed', file=sys.stderr)
        sys.exit(1)
