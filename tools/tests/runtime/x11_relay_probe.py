"""Minimal X11 window exchange over an explicitly supplied disposable socket."""

import json
import socket
import struct
import sys


def receive(connection, size):
    result = bytearray()
    while len(result) < size:
        chunk = connection.recv(size - len(result))
        if not chunk:
            raise ValueError('X11 connection closed')
        result.extend(chunk)
    return result


def probe(path, cookie):
    with socket.socket(socket.AF_UNIX) as connection:
        connection.settimeout(3)
        connection.connect(path)
        connection.sendall(b'l\0' + struct.pack('<HHHHH', 11, 0, 18, 16, 0)
                           + b'MIT-MAGIC-COOKIE-1\0\0' + bytes.fromhex(cookie))
        header = receive(connection, 8)
        length = struct.unpack_from('<H', header, 6)[0] * 4
        if header[0] != 1 or not 32 <= length <= 65536:
            raise ValueError('X11 setup rejected')
        setup = receive(connection, length)
        base = struct.unpack_from('<I', setup, 4)[0]
        vendor_length = struct.unpack_from('<H', setup, 16)[0]
        screen_offset = 32 + ((vendor_length + 3) // 4) * 4 + setup[21] * 8
        root = struct.unpack_from('<I', setup, screen_offset)[0]
        window = base | 1
        connection.sendall(struct.pack('<BBHIIhhHHHHII', 1, 0, 8, window, root, 10, 10, 240, 140, 0, 1, 0, 0))
        connection.sendall(struct.pack('<BBHI', 8, 0, 2, window))
        connection.sendall(struct.pack('<BBH', 43, 0, 1))
        reply = receive(connection, 32)
        if reply[0] != 1 or struct.unpack_from('<H', reply, 2)[0] != 3:
            raise ValueError('X11 window creation failed')
        connection.sendall(struct.pack('<BBHI', 4, 0, 2, window))


if __name__ == '__main__':
    payload = json.loads(sys.stdin.buffer.read(8193))
    try:
        probe(payload['path'], payload['cookie'])
    except (OSError, ValueError):
        if not payload.get('reject'):
            raise
        print('rejected')
    else:
        if payload.get('reject'):
            raise ValueError('Invalid authorization was accepted')
        print('window-ready')
