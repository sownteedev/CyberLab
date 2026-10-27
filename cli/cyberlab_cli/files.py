import os
from pathlib import Path
import re
import stat
import unicodedata

from cyberlab_ipc import MAX_IMPORT_BYTES

def read_import(path, name=None):
    path = Path(path)
    name = path.name if name is None else name
    if not re.fullmatch(r"[A-Za-z0-9_][A-Za-z0-9_.-]{0,63}", name):
        raise ValueError("Use --name with one safe ASCII filename of at most 64 characters")
    descriptor = os.open(path, os.O_RDONLY | os.O_NOFOLLOW | os.O_NONBLOCK | os.O_CLOEXEC)
    with os.fdopen(descriptor, "rb") as source:
        before = os.fstat(source.fileno())
        if not stat.S_ISREG(before.st_mode) or before.st_size > MAX_IMPORT_BYTES:
            raise ValueError("Import requires one regular file of at most 256 KiB")
        data = source.read(MAX_IMPORT_BYTES + 1)
        after = os.fstat(source.fileno())
        if len(data) > MAX_IMPORT_BYTES or (before.st_size, before.st_mtime_ns, before.st_ctime_ns) != (after.st_size, after.st_mtime_ns, after.st_ctime_ns):
            raise ValueError("Import file changed or exceeded its size limit while reading")
    return name, data

def terminal_text(content):
    return "".join(character if character in "\n\t" or not unicodedata.category(character).startswith("C") else f"\\u{ord(character):04x}" for character in content)
