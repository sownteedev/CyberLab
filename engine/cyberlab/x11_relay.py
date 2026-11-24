"""Bounded X11 forwarding worker. No image processing or host login credentials."""

import array
from contextlib import suppress
import hmac
import json
import os
from pathlib import Path
import select
import socket
import stat
import struct
import sys
import threading
from time import monotonic

MAX_CLIENTS = 32
MAX_CHUNK = 65536
MAX_FDS = 16


def close_fds(descriptors):
    for descriptor in descriptors:
        with suppress(OSError):
            os.close(descriptor)


def receive(connection, maximum):
    data, ancillary, flags, _address = connection.recvmsg(
        maximum, socket.CMSG_SPACE(MAX_FDS * array.array('i').itemsize), socket.MSG_CMSG_CLOEXEC)
    descriptors = []
    try:
        for level, kind, payload in ancillary:
            if (level, kind) != (socket.SOL_SOCKET, socket.SCM_RIGHTS):
                raise ValueError('Unsupported X11 ancillary data')
            values = array.array('i')
            values.frombytes(payload[:len(payload) - len(payload) % values.itemsize])
            descriptors.extend(values)
        if flags & (socket.MSG_TRUNC | socket.MSG_CTRUNC) or len(descriptors) > MAX_FDS:
            raise ValueError('Oversized X11 ancillary data')
        return data, descriptors
    except BaseException:
        close_fds(descriptors)
        raise


def setup_packet(connection, cookie, stop):
    packet = bytearray()
    required = 12
    deadline = monotonic() + 5
    while len(packet) < required:
        if stop.is_set() or monotonic() >= deadline:
            raise ValueError('X11 setup timed out')
        if not select.select([connection], [], [], 0.1)[0]:
            continue
        data, descriptors = receive(connection, required - len(packet))
        close_fds(descriptors)
        if not data or descriptors:
            raise ValueError('Invalid X11 setup')
        packet.extend(data)
        if len(packet) == 12:
            order = '<' if packet[0] == ord('l') else '>' if packet[0] == ord('B') else None
            if order is None:
                raise ValueError('Invalid X11 byte order')
            major, minor, protocol_size, cookie_size = struct.unpack_from(order + 'HHHH', packet, 2)
            if (major, minor, protocol_size, cookie_size) != (11, 0, 18, 16):
                raise ValueError('X11 requires the node authorization')
            required = 48
    if packet[12:30] != b'MIT-MAGIC-COOKIE-1' or not hmac.compare_digest(packet[32:48], bytes.fromhex(cookie)):
        raise ValueError('Wrong node authorization')
    return packet


def pump(first, second, stop):
    sockets = (first, second)
    pending = [b'', b'']
    descriptors = [[], []]
    reading = [True, True]
    finished = [False, False]
    for connection in sockets:
        connection.setblocking(False)
    try:
        while not stop.is_set():
            for index in range(2):
                if not reading[index] and not pending[index] and not finished[index]:
                    with suppress(OSError):
                        sockets[1 - index].shutdown(socket.SHUT_WR)
                    finished[index] = True
            if all(finished):
                return
            readers = [sockets[index] for index in range(2) if reading[index] and not pending[index]]
            writers = [sockets[1 - index] for index in range(2) if pending[index]]
            readable, writable, _errors = select.select(readers, writers, [], 0.1)
            for index in range(2):
                if sockets[index] in readable:
                    try:
                        pending[index], descriptors[index] = receive(sockets[index], MAX_CHUNK)
                        if not pending[index]:
                            reading[index] = False
                            close_fds(descriptors[index])
                            descriptors[index] = []
                    except BlockingIOError:
                        pass
                if sockets[1 - index] in writable:
                    ancillary = [(socket.SOL_SOCKET, socket.SCM_RIGHTS, array.array('i', descriptors[index]))] if descriptors[index] else []
                    try:
                        count = sockets[1 - index].sendmsg([pending[index]], ancillary)
                        if count <= 0:
                            raise ValueError('X11 connection stopped')
                        close_fds(descriptors[index])
                        descriptors[index] = []
                        pending[index] = pending[index][count:]
                    except BlockingIOError:
                        pass
    finally:
        for values in descriptors:
            close_fds(values)


def upstream(identity):
    from cyberlab.xwayland import process_state

    endpoint = Path(identity['socket'])
    info = endpoint.lstat()
    if not stat.S_ISSOCK(info.st_mode) or info.st_uid != os.getuid() or (info.st_dev, info.st_ino) != (identity['device'], identity['inode']):
        raise ValueError('XWayland socket changed')
    connection = socket.socket(socket.AF_UNIX)
    try:
        connection.settimeout(2)
        connection.connect(str(endpoint))
        peer, owner, _group = struct.unpack('3i', connection.getsockopt(socket.SOL_SOCKET, socket.SO_PEERCRED, 12))
        if (peer, owner) != (identity['peer'], os.getuid()):
            raise ValueError('XWayland listener changed')
        for process, started in ((peer, identity['peer_start_time']), (identity['process'], identity['start_time'])):
            if process_state(process, os.getuid())['start_time'] != started:
                raise ValueError('XWayland process changed')
        return connection
    except BaseException:
        connection.close()
        raise


def serve(listener, control, payload):
    stop = threading.Event()
    slots = threading.BoundedSemaphore(MAX_CLIENTS)
    threads = []

    def forward(client):
        try:
            with client:
                _process, owner, _group = struct.unpack('3i', client.getsockopt(socket.SOL_SOCKET, socket.SO_PEERCRED, 12))
                if owner != payload['guest_uid']:
                    return
                packet = setup_packet(client, payload['cookie'], stop)
                with upstream(payload['identity']) as server:
                    server.sendall(packet)
                    pump(client, server, stop)
        except (OSError, ValueError):
            pass
        finally:
            slots.release()

    with upstream(payload['identity']):
        pass
    listener.setblocking(False)
    print('ready', flush=True)
    try:
        while True:
            readable, _writers, _errors = select.select([listener, control], [], [], 1)
            if control in readable:
                return
            if listener in readable:
                with suppress(BlockingIOError):
                    client, _address = listener.accept()
                    if slots.acquire(blocking=False):
                        thread = threading.Thread(target=forward, args=(client,), daemon=True)
                        threads = [entry for entry in threads if entry.is_alive()]
                        threads.append(thread)
                        try:
                            thread.start()
                        except BaseException:
                            client.close()
                            slots.release()
                            raise
                    else:
                        client.close()
    finally:
        stop.set()
        deadline = monotonic() + 0.5
        for thread in threads:
            thread.join(timeout=max(0, deadline - monotonic()))


def main():
    if os.geteuid() == 0:
        raise ValueError('The display relay must not run as root')
    incoming = bytearray()
    while not incoming.endswith(b'\n'):
        chunk = os.read(0, 1)
        if not chunk or len(incoming) >= 8192:
            raise ValueError('Invalid relay configuration')
        incoming.extend(chunk)
    payload = json.loads(incoming)
    if len(bytes.fromhex(payload['cookie'])) != 16 or type(payload['guest_uid']) is not int:
        raise ValueError('Invalid node authorization')
    with socket.socket(fileno=int(sys.argv[1])) as listener:
        if listener.family != socket.AF_UNIX or not listener.getsockopt(socket.SOL_SOCKET, socket.SO_ACCEPTCONN):
            raise ValueError('Expected a private Unix listener')
        serve(listener, 0, payload)


if __name__ == '__main__':
    sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
    try:
        main()
    except Exception:
        sys.exit(1)
