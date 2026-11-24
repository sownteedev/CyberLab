from dataclasses import dataclass
from time import monotonic
from uuid import uuid4

from cyberlab.runtime import RuntimeFailure

CHUNK_SIZE = 65536
LEASE_SECONDS = 30

@dataclass
class DesktopChannel:
    session: str
    node: str
    uid: int
    sender: str
    stream: object
    deadline: float
    ready: bool = False

class Desktops:
    def __init__(self, runtime, clock=monotonic):
        self.runtime = runtime
        self.clock = clock
        self.channels = {}

    def expire(self, inspect_streams=False):
        for handle, channel in tuple(self.channels.items()):
            expired = channel.deadline <= self.clock()
            if not expired and inspect_streams and channel.stream is not None:
                try:
                    expired = channel.stream.exited()
                except RuntimeFailure:
                    expired = True
            if expired:
                self.close(handle)

    def close(self, handle):
        channel = self.channels.pop(handle, None)
        if channel and channel.stream:
            channel.stream.close()

    def open(self, session, node_id, uid, sender):
        self.expire(inspect_streams=True)
        if any(channel.session == session.id and channel.node == node_id and channel.stream for channel in self.channels.values()):
            raise RuntimeFailure('This machine already has a desktop viewer; close it before reopening')
        if len(self.channels) >= 16:
            raise RuntimeFailure('Desktop attachment limit reached; close an unused viewer')
        stream, credential = self.runtime.desktop.open(session, node_id)
        handle = uuid4().hex
        self.channels[handle] = DesktopChannel(session.id, node_id, uid, sender, stream, self.clock() + LEASE_SECONDS)
        return [handle, credential]

    def operate(self, operation, handle, uid, sender, data=None):
        self.expire()
        channel = self.channels.get(handle)
        if channel is None or (channel.uid, channel.sender) != (uid, sender):
            raise RuntimeFailure('Desktop attachment is unavailable for this connection')
        channel.deadline = self.clock() + LEASE_SECONDS
        if operation == 'ready':
            channel.ready = True
            return True
        if operation == 'close':
            self.close(handle)
            return True
        if operation == 'read':
            try:
                output, ended = channel.stream.read(CHUNK_SIZE) if channel.stream else (b'', True)
            except (RuntimeFailure, OSError):
                self.close(handle)
                raise RuntimeFailure('Application display connection interrupted; reconnect GUI. Session is kept') from None
            if ended:
                self.close(handle)
            return [output, ended]
        if operation == 'write':
            if not isinstance(data, bytes) or len(data) > CHUNK_SIZE:
                raise ValueError('Desktop writes are limited to 65536 bytes')
            try:
                return channel.stream.write(data) if channel.stream else 0
            except (RuntimeFailure, OSError):
                self.close(handle)
                raise RuntimeFailure('Application display connection interrupted; reconnect GUI. Session is kept') from None
        raise ValueError('Unknown desktop operation')

    def close_session(self, session_id=None):
        for handle, channel in tuple(self.channels.items()):
            if session_id is None or channel.session == session_id:
                self.close(handle)
