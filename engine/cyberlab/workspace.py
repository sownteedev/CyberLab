from dataclasses import dataclass
from io import BytesIO
from pathlib import PurePosixPath
import tarfile

MAX_ENTRIES = 1024
MAX_CONTENT = 16 * 1024 * 1024
MAX_ARCHIVE = 20 * 1024 * 1024
MAX_UPLOAD_CONTENT = 4 * 1024 * 1024
MAX_UPLOAD_ARCHIVE = 8 * 1024 * 1024


class WorkspaceNotFound(Exception):
    pass


def relative_path(value, root=False):
    if not isinstance(value, str) or not value or len(value.encode("utf-8")) > 1024:
        raise ValueError("Workspace path is empty or too long")
    if root and value == ".":
        return value
    parts = value.split("/")
    if (len(parts) > 16 or any(part in {"", ".", ".."} for part in parts)
            or "\\" in value or any(ord(character) < 32 or ord(character) == 127 for character in value)
            or any(len(part.encode("utf-8")) > 255 for part in parts)):
        raise ValueError("Workspace paths must be safe relative paths without traversal")
    return value


def folder_name(value):
    relative_path(value)
    if "/" in value or len(value.encode("utf-8")) > 128:
        raise ValueError("Import destination must be one folder name of at most 128 bytes")
    return value


@dataclass(frozen=True)
class Entry:
    path: str
    kind: str
    data: bytes | None = None
    mode: int | None = None

    def __post_init__(self):
        if self.mode is None:
            object.__setattr__(self, "mode", 0o700 if self.kind == "directory" else 0o600)

    @property
    def size(self):
        return len(self.data) if self.data is not None else 0

    def metadata(self):
        return {"path": self.path, "kind": self.kind, "size": self.size, "mode": self.mode}


def validate_entries(entries, unsafe=False, limit=MAX_CONTENT):
    if len(entries) > MAX_ENTRIES or sum(entry.size for entry in entries) > limit:
        raise ValueError("Workspace exceeds its file-count or content-size limit")
    paths = {}
    for entry in entries:
        relative_path(entry.path)
        if entry.path in paths:
            raise ValueError("Duplicate workspace path")
        if entry.kind not in {"file", "directory", "symlink", "hardlink", "special"}:
            raise ValueError("Unknown workspace entry type")
        if not unsafe and entry.kind not in {"file", "directory"}:
            raise ValueError("Transfers do not follow links or include special files")
        if (entry.kind == "file") != isinstance(entry.data, bytes):
            raise ValueError("Invalid workspace file contents")
        if not isinstance(entry.mode, int) or entry.mode < 0 or entry.mode > 0o777:
            raise ValueError("Unsupported workspace permissions")
        paths[entry.path] = entry
    for entry in entries:
        for parent in PurePosixPath(entry.path).parents:
            existing = paths.get(str(parent))
            if existing is not None and existing.kind != "directory":
                raise ValueError("Workspace path traverses a non-directory entry")
    return tuple(entries)


def read_archive(data, unsafe=False, limit=MAX_CONTENT):
    if not isinstance(data, bytes) or len(data) > MAX_ARCHIVE:
        raise ValueError("Workspace archive exceeds its size limit")
    result = []
    size = 0
    try:
        with tarfile.open(fileobj=BytesIO(data), mode="r:") as archive:
            for member in archive:
                name = member.name
                while name.startswith("./"):
                    name = name[2:]
                if name in {"", "."}:
                    if not member.isdir():
                        raise ValueError("Workspace archive root must be a directory")
                    continue
                name = name.rstrip("/") if member.isdir() else name
                relative_path(name)
                if len(result) >= MAX_ENTRIES or member.size < 0 or size + member.size > limit:
                    raise ValueError("Workspace exceeds its file-count or content-size limit")
                if member.sparse is not None:
                    raise ValueError("Sparse file archives are not supported")
                contents = None
                if member.isfile():
                    size += member.size
                    contents = archive.extractfile(member).read(member.size + 1)
                    if len(contents) != member.size:
                        raise ValueError("Truncated workspace archive")
                    kind = "file"
                elif member.isdir():
                    kind = "directory"
                elif member.issym():
                    kind = "symlink"
                elif member.islnk():
                    kind = "hardlink"
                else:
                    kind = "special"
                result.append(Entry(name, kind, contents, member.mode & 0o777))
    except (tarfile.TarError, OSError, OverflowError, UnicodeError):
        raise ValueError("Invalid uncompressed workspace archive") from None
    return validate_entries(result, unsafe=unsafe, limit=limit)


def make_archive(entries, uid=65534, gid=65534):
    entries = validate_entries(entries)
    output = BytesIO()
    with tarfile.open(fileobj=output, mode="w", format=tarfile.PAX_FORMAT) as archive:
        for entry in sorted(entries, key=lambda item: item.path):
            member = tarfile.TarInfo(entry.path)
            member.uid, member.gid = uid, gid
            member.mode = entry.mode
            member.type = tarfile.DIRTYPE if entry.kind == "directory" else tarfile.REGTYPE
            member.size = entry.size
            archive.addfile(member, BytesIO(entry.data) if entry.data is not None else None)
    data = output.getvalue()
    if len(data) > MAX_ARCHIVE:
        raise ValueError("Workspace archive exceeds its size limit")
    return data


def select(entries, path):
    relative_path(path, root=True)
    if path == ".":
        return validate_entries(entries)
    selected = tuple(entry for entry in entries if entry.path == path or entry.path.startswith(path + "/"))
    if not selected:
        raise WorkspaceNotFound("Workspace entry no longer exists; refresh the file list")
    return validate_entries(selected)


def file_contents(entries, path):
    relative_path(path)
    selected = select(entries, path)
    if len(selected) != 1 or selected[0].kind != "file":
        raise ValueError("Select one regular workspace file")
    return selected[0].data
