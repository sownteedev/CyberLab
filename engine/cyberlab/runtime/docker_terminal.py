import os
import socket
from time import monotonic

from docker.errors import DockerException

from . import RuntimeFailure

def close_stream(stream):
    connection = getattr(stream, "_sock", stream)
    if connection is not None:
        try:
            connection.shutdown(socket.SHUT_RDWR)
        except OSError:
            pass
    response = getattr(stream, "_response", None)
    try:
        if response is not None:
            response.close()
    except OSError:
        pass
    finally:
        try:
            stream.close()
        except OSError:
            pass

class DockerTerminal:
    def __init__(self, api, exec_id, stream):
        self.api = api
        self.exec_id = exec_id
        self.stream = stream
        self.ended = False
        self.eof_since = None
        os.set_blocking(stream.fileno(), False)

    def read(self, limit):
        if self.ended:
            return b"", True
        try:
            data = os.read(self.stream.fileno(), limit)
            if not data:
                if not self.exited():
                    if self.eof_since is None:
                        self.eof_since = monotonic()
                    if monotonic() - self.eof_since < 2:
                        return b"", False
                    raise RuntimeFailure("Terminal stream interrupted; reset the Session")
                self.ended = True
            return data, self.ended
        except BlockingIOError:
            return b"", False
        except (OSError, DockerException):
            raise RuntimeFailure("Cannot read terminal; reset the Session") from None

    def write(self, data):
        if self.ended:
            raise RuntimeFailure("Terminal shell has exited")
        try:
            return os.write(self.stream.fileno(), data)
        except BlockingIOError:
            return 0
        except OSError:
            raise RuntimeFailure("Cannot write terminal; reset the Session") from None

    def resize(self, rows, columns):
        try:
            self.api.exec_resize(self.exec_id, height=rows, width=columns)
        except DockerException:
            raise RuntimeFailure("Cannot resize terminal; reset the Session") from None

    def exited(self):
        try:
            state = self.api.exec_inspect(self.exec_id)
            return not state["Running"] and state.get("ExitCode") is not None
        except DockerException:
            raise RuntimeFailure("Cannot inspect terminal; retry or reset the Session") from None

    def close(self):
        close_stream(self.stream)
