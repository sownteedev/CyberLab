from . import RuntimeFailure
from .docker_terminal import DockerTerminal


class DockerDesktopStream(DockerTerminal):
    """Decode Docker's non-TTY output frames without interpreting GUI bytes."""

    def __init__(self, api, exec_id, stream):
        super().__init__(api, exec_id, stream)
        self.buffer = bytearray()
        self.remaining = 0
        self.output_stream = 1

    def read(self, limit):
        if not 1 <= limit <= 65536:
            raise ValueError('Invalid application display chunk size')
        if len(self.buffer) < limit and not self.ended:
            data, _ = super().read(limit)
            self.buffer.extend(data)
        output = bytearray()
        while len(output) < limit:
            if self.remaining == 0:
                if len(self.buffer) < 8:
                    break
                header = self.buffer[:8]
                del self.buffer[:8]
                if header[0] not in (1, 2) or header[1:4] != b'\0\0\0':
                    raise RuntimeFailure('Invalid application display transport header')
                self.remaining = int.from_bytes(header[4:8], 'big')
                if self.remaining > 16 * 1024 * 1024:
                    raise RuntimeFailure('Application display transport frame exceeds limit')
                self.output_stream = header[0]
                if not self.remaining:
                    continue
            size = min(self.remaining, len(self.buffer), limit - len(output))
            if not size:
                break
            if self.output_stream == 1:
                output.extend(self.buffer[:size])
            del self.buffer[:size]
            self.remaining -= size
        if self.ended and len(output) < limit and (self.remaining or self.buffer):
            raise RuntimeFailure('Incomplete application display transport frame')
        return bytes(output), self.ended and not self.buffer and not self.remaining
