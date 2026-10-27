from dataclasses import dataclass
import re

from cyberlab.lab.environment import workspace

MAX_FILE_BYTES = 256 * 1024
MAX_SESSION_BYTES = 4 * 1024 * 1024
MAX_SESSION_IMPORTS = 32

def validate_import(name, data):
    if not isinstance(name, str) or not re.fullmatch(r"[A-Za-z0-9_][A-Za-z0-9_.-]{0,63}", name):
        raise ValueError("Import name must be one safe filename, at most 64 ASCII characters")
    if not isinstance(data, bytes) or len(data) > MAX_FILE_BYTES:
        raise ValueError("Import data must be at most 256 KiB")

def import_path(node, identifier, name):
    validate_import(name, b"")
    if not re.fullmatch(r"[a-f0-9]{32}", identifier):
        raise ValueError("Invalid import ID")
    return f"{workspace(node)}/cyberlab-import-{identifier}-{name}"

@dataclass(frozen=True)
class ImportRecord:
    id: str
    node: str
    name: str
    path: str
    size: int
    sha256: str
    state: str = "PREPARING"
    error: str = ""
    kind: str = "file"
