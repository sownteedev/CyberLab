from dataclasses import dataclass
from time import monotonic
from uuid import uuid4

from cyberlab.runtime import RuntimeFailure, TerminalStream

CHUNK_SIZE = 4096
LEASE_SECONDS = 30

class TerminalNotFound(Exception):
    """No terminal attachment is visible to this D-Bus connection."""

class TerminalBusy(Exception):
    """Another connection is attached to this node."""

def validate_size(rows, columns):
    if any(type(value) is not int or not 1 <= value <= 1000 for value in (rows, columns)):
        raise ValueError("Terminal dimensions must be between 1 and 1000")

@dataclass
class Channel:
    stream: TerminalStream | None = None
    handle: str = ""
    uid: int = -1
    sender: str = ""
    deadline: float = 0
    ended: bool = False

class Terminals:
    """Bounded per-node shells; all methods run under the Engine lock."""

    def __init__(self, runtime, clock=monotonic):
        self.runtime = runtime
        self.clock = clock
        self.channels = {}
        self.handles = {}

    def _detach(self, channel):
        self.handles.pop(channel.handle, None)
        channel.handle = ""

    def _break(self, channel):
        if channel.stream is not None:
            channel.stream.close()
            channel.stream = None

    def open(self, session, node_id, uid, sender, rows, columns, slot=0):
        validate_size(rows, columns)
        node = next(node for node in session.lab.nodes if node.id == node_id)
        if type(slot) is not int or not 0 <= slot < node.terminal_count:
            raise ValueError("Terminal slot is outside the node's configured range")
        key = (session.id, node_id, slot)
        channel = self.channels.get(key)
        if channel is not None:
            if channel.handle and channel.deadline > self.clock():
                raise TerminalBusy("Terminal slot already has an attachment")
            self._detach(channel)
            if channel.ended or (channel.stream is not None and channel.stream.exited()):
                self._break(channel)
                del self.channels[key]
                channel = None
            elif channel.stream is None:
                raise RuntimeFailure("Terminal setup failed; reset the Session before retrying")
        if channel is None:
            channel = Channel()
            self.channels[key] = channel
            channel.stream = self.runtime.open_terminal(session, node_id)
        try:
            channel.stream.resize(rows, columns)
        except Exception:
            self._break(channel)
            raise
        channel.handle = uuid4().hex
        channel.uid, channel.sender = uid, sender
        channel.deadline = self.clock() + LEASE_SECONDS
        self.handles[channel.handle] = channel
        return channel.handle

    def _get(self, handle, uid, sender):
        channel = self.handles.get(handle)
        if channel is None or (channel.uid, channel.sender) != (uid, sender):
            raise TerminalNotFound("Terminal attachment not found")
        if channel.deadline <= self.clock():
            self._detach(channel)
            raise TerminalNotFound("Terminal attachment expired; reconnect")
        channel.deadline = self.clock() + LEASE_SECONDS
        return channel

    def operate(self, operation, handle, uid, sender, *arguments):
        channel = self._get(handle, uid, sender)
        if operation == "close":
            self._detach(channel)
            return True
        if channel.stream is None:
            raise RuntimeFailure("Terminal connection failed; reset the Session")
        try:
            if operation == "read":
                data, ended = channel.stream.read(CHUNK_SIZE)
                channel.ended = ended
                return [data, ended]
            if operation == "write":
                data, = arguments
                if not isinstance(data, bytes) or len(data) > CHUNK_SIZE:
                    raise ValueError("Terminal writes are limited to 4096 bytes")
                return channel.stream.write(data)
            if operation == "resize":
                validate_size(*arguments)
                channel.stream.resize(*arguments)
                return True
            raise ValueError("Unknown terminal operation")
        except RuntimeFailure:
            self._break(channel)
            raise

    def close_session(self, session_id=None):
        for key, channel in tuple(self.channels.items()):
            if session_id is None or key[0] == session_id:
                self._detach(channel)
                self._break(channel)
                del self.channels[key]
