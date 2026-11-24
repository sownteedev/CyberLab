"""Private-socket tests only; no desktop credentials or Docker access."""

import array
from contextlib import contextmanager, suppress
import os
from pathlib import Path
import socket
import struct
import sys
import tempfile
import threading
import time
import unittest
from unittest.mock import patch

sys.dont_write_bytecode = True
sys.path.insert(0, str(Path(__file__).resolve().parents[1] / 'engine'))
from cyberlab import x11_relay, xwayland
from cyberlab.runtime.display_relay import DisplayRelay


def packet(cookie='12' * 16, order='<'):
    return (b'l' if order == '<' else b'B') + b'\0' + struct.pack(order + 'HHHHH', 11, 0, 18, 16, 0) + b'MIT-MAGIC-COOKIE-1\0\0' + bytes.fromhex(cookie)


@contextmanager
def pumping():
    client, first = socket.socketpair()
    second, server = socket.socketpair()
    stop = threading.Event()
    errors = []
    def run():
        try:
            x11_relay.pump(first, second, stop)
        except Exception as error:
            errors.append(error)
    thread = threading.Thread(target=run)
    thread.start()
    client.settimeout(3)
    server.settimeout(3)
    try:
        yield client, server, errors
    finally:
        stop.set()
        thread.join(timeout=3)
        for connection in (client, first, second, server):
            connection.close()
        assert not thread.is_alive()


class RelayChecks(unittest.TestCase):
    def test_failed_bind_never_removes_existing_file(self):
        with tempfile.TemporaryDirectory(prefix='cyberlab-relay-') as directory:
            path = Path(directory) / 'Xsocket'
            path.write_text('retained')
            with self.assertRaises(OSError):
                DisplayRelay(Path(directory), {}, os.getuid(), os.getgid())
            self.assertEqual(path.read_text(), 'retained')

    def test_cookie_required_in_both_byte_orders(self):
        for order in ('<', '>'):
            for cookie, valid in (('12' * 16, True), ('00' * 16, False)):
                first, second = socket.socketpair()
                with first, second:
                    first.sendall(packet(cookie, order))
                    if valid:
                        self.assertEqual(x11_relay.setup_packet(second, cookie, threading.Event()), packet(cookie, order))
                    else:
                        with self.assertRaises(ValueError):
                            x11_relay.setup_packet(second, '12' * 16, threading.Event())

    def test_setup_rejects_empty_or_oversized_authorization(self):
        for length in (0, 65535):
            first, second = socket.socketpair()
            with first, second:
                first.sendall(b'l\0' + struct.pack('<HHHHH', 11, 0, 18, length, 0))
                with self.assertRaises(ValueError):
                    x11_relay.setup_packet(second, '12' * 16, threading.Event())

    def test_setup_is_fragment_safe_and_does_not_consume_first_request(self):
        first, second = socket.socketpair()
        with first, second:
            payload = packet()
            def send():
                for part in (payload[:3], payload[3:15], payload[15:] + b'next'):
                    first.sendall(part)
                    time.sleep(0.01)
            thread = threading.Thread(target=send)
            thread.start()
            self.assertEqual(x11_relay.setup_packet(second, '12' * 16, threading.Event()), payload)
            self.assertEqual(second.recv(4), b'next')
            thread.join()

    def test_setup_does_not_leak_received_fds(self):
        first, second = socket.socketpair()
        descriptor = os.memfd_create('relay-test')
        try:
            count = len(list(Path('/proc/self/fd').iterdir()))
            with first, second:
                first.sendmsg([packet()], [(socket.SOL_SOCKET, socket.SCM_RIGHTS, array.array('i', [descriptor]))])
                with self.assertRaises(ValueError):
                    x11_relay.setup_packet(second, '12' * 16, threading.Event())
                self.assertEqual(len(list(Path('/proc/self/fd').iterdir())), count)
        finally:
            os.close(descriptor)

    def test_bidirectional_data_and_half_close(self):
        with pumping() as (client, server, errors):
            payload = b'X11 data ' * 40000
            thread = threading.Thread(target=lambda: client.sendall(payload))
            thread.start()
            received = bytearray()
            while len(received) < len(payload):
                received.extend(server.recv(32768))
            thread.join()
            self.assertEqual(received, payload)
            client.shutdown(socket.SHUT_WR)
            self.assertEqual(server.recv(1), b'')
            server.sendall(b'final reply')
            server.shutdown(socket.SHUT_WR)
            received = bytearray()
            while chunk := client.recv(1024):
                received.extend(chunk)
            self.assertEqual(received, b'final reply')
            self.assertEqual(errors, [])

    def test_unix_fd_forwarding_both_directions(self):
        with pumping() as (client, server, errors):
            for sender, receiver in ((client, server), (server, client)):
                descriptor = os.memfd_create('relay-buffer')
                received = []
                try:
                    os.write(descriptor, b'shared buffer')
                    sender.sendmsg([b'fd'], [(socket.SOL_SOCKET, socket.SCM_RIGHTS, array.array('i', [descriptor]))])
                    data, received = x11_relay.receive(receiver, 16)
                    self.assertEqual(data, b'fd')
                    self.assertEqual(len(received), 1)
                    self.assertEqual(os.pread(received[0], 13, 0), b'shared buffer')
                    self.assertFalse(os.get_inheritable(received[0]))
                finally:
                    os.close(descriptor)
                    x11_relay.close_fds(received)
            self.assertEqual(errors, [])

    def test_truncated_ancillary_closes_descriptors(self):
        first, second = socket.socketpair()
        descriptor = os.memfd_create('relay-limit')
        try:
            count = len(list(Path('/proc/self/fd').iterdir()))
            with first, second:
                first.sendmsg([b'x'], [(socket.SOL_SOCKET, socket.SCM_RIGHTS, array.array('i', [descriptor] * 32))])
                with self.assertRaises(ValueError):
                    x11_relay.receive(second, 16)
                self.assertEqual(len(list(Path('/proc/self/fd').iterdir())), count)
        finally:
            os.close(descriptor)

    def test_reparented_xwayland_is_a_candidate(self):
        with patch.object(xwayland, 'descendants', return_value=iter([])), \
             patch.object(Path, 'iterdir', return_value=[Path('/proc/42')]), \
             patch.object(Path, 'stat', return_value=type('Info', (), {'st_uid': 1000})()), \
             patch.object(Path, 'resolve', return_value=Path('/usr/bin/Xwayland')), \
             patch.object(xwayland, 'process_state', return_value={'start_time': '123', 'parent': 1}):
            self.assertEqual(list(xwayland.server_candidates(10, 1000)), [(42, {'start_time': '123', 'parent': 1})])

    def test_worker_lifecycle_preserves_socket_inode_and_exits_on_parent_eof(self):
        with tempfile.TemporaryDirectory(prefix='cyberlab-relay-') as temporary:
            root = Path(temporary)
            endpoint = root / 'upstream'
            with socket.socket(socket.AF_UNIX) as listener:
                listener.bind(str(endpoint))
                listener.listen(32)
                info = endpoint.stat()
                started = xwayland.process_state(os.getpid(), os.getuid())['start_time']
                context = {'uid': os.getuid(), 'cookie': '12' * 16, 'identity': {
                    'socket': str(endpoint), 'inode': info.st_ino, 'device': info.st_dev,
                    'peer': os.getpid(), 'process': os.getpid(), 'peer_start_time': started, 'start_time': started}}
                relay = DisplayRelay(root, context, os.getuid(), os.getgid())
                try:
                    self.assertTrue(relay.alive)
                    inode = relay.path.stat().st_ino
                    self.assertEqual(relay.path.stat().st_mode & 0o777, 0o600)
                    original = relay.process
                    relay.restart(context)
                    self.assertIsNotNone(original.poll())
                    self.assertEqual(relay.path.stat().st_ino, inode)
                    relay.process.stdin.close()
                    self.assertEqual(relay.process.wait(timeout=5), 0)
                    self.assertFalse(relay.alive)
                finally:
                    relay.close()
                self.assertFalse((root / 'Xsocket').exists())


if __name__ == '__main__':
    unittest.main(verbosity=2)
