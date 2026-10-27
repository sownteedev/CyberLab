from gzip import GzipFile
from io import BytesIO
import tarfile
import zlib

from cyberlab.archives import read_zip
from cyberlab.workspace import relative_path

MAX_ARCHIVE = 32 * 1024 * 1024
MAX_CONTENT = 32 * 1024 * 1024
MAX_ENTRIES = 512
MAX_TAR_STREAM = MAX_CONTENT + 2 * 1024 * 1024


class BoundedStream:
    def __init__(self, source):
        self.source = source
        self.remaining = MAX_TAR_STREAM

    def read(self, size):
        data = self.source.read(min(size, self.remaining + 1))
        self.remaining -= len(data)
        if self.remaining < 0:
            raise ValueError("Labtainer TAR stream exceeds its decompressed byte limit")
        return data


def read_tar(data):
    entries = {}
    total = 0
    with BytesIO(data) as raw:
        stream = GzipFile(fileobj=raw) if data.startswith(b"\x1f\x8b") else raw
        bounded = BoundedStream(stream)
        try:
            with tarfile.open(fileobj=bounded, mode="r|") as archive:
                for count, member in enumerate(archive, 1):
                    if count > MAX_ENTRIES:
                        raise ValueError("Labtainer archive exceeds its entry limit")
                    name = member.name
                    if name.startswith("./"):
                        name = name[2:]
                    if name in {"", "."} and member.isdir():
                        continue
                    if member.isdir():
                        name = name.removesuffix("/")
                    relative_path(name)
                    if name in entries:
                        raise ValueError("Labtainer archive contains duplicate entries")
                    if (not (member.isfile() or member.isdir()) or member.sparse is not None
                            or member.size < 0 or (member.isdir() and member.size)):
                        raise ValueError("Labtainer archive contains a link, special file or unsupported entry")
                    total += member.size
                    if total > MAX_CONTENT:
                        raise ValueError("Labtainer archive exceeds its uncompressed byte limit")
                    if member.isdir():
                        entries[name] = None
                    else:
                        with archive.extractfile(member) as source:
                            content = source.read(member.size + 1)
                        if len(content) != member.size:
                            raise ValueError("Labtainer archive entry size is inconsistent")
                        entries[name] = content
            while bounded.read(64 * 1024):
                pass
        finally:
            if stream is not raw:
                stream.close()
    return entries


def read_labtainer_archive(data):
    if not isinstance(data, bytes) or not data or len(data) > MAX_ARCHIVE:
        raise ValueError("Labtainer archive is empty or exceeds 32 MiB")
    if data.startswith(b"PK"):
        entries = read_zip(data, max_archive=MAX_ARCHIVE, max_entries=MAX_ENTRIES, max_content=MAX_CONTENT)
    else:
        try:
            entries = read_tar(data)
        except (OSError, EOFError, tarfile.TarError, zlib.error):
            raise ValueError("Invalid Labtainer TAR or gzip archive") from None
    for path in entries:
        parts = path.split("/")
        if any("/".join(parts[:index]) in entries and entries["/".join(parts[:index])] is not None
               for index in range(1, len(parts))):
            raise ValueError("Labtainer archive path traverses a file")
    return entries
