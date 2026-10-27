from hashlib import sha256
import json
import os
from pathlib import Path
import stat

from cyberlab.workspace import Entry, MAX_ARCHIVE, MAX_ENTRIES, MAX_UPLOAD_CONTENT, folder_name, make_archive, relative_path
from .drafts import read_file


def read_directory(source):
    entries = []
    total = 0
    root = os.open(source, os.O_RDONLY | os.O_DIRECTORY | os.O_NOFOLLOW | os.O_CLOEXEC)
    device = os.fstat(root).st_dev

    def walk(descriptor, prefix):
        nonlocal total
        initial = os.fstat(descriptor)
        with os.scandir(descriptor) as iterator:
            names = []
            for item in iterator:
                if len(names) + len(entries) >= MAX_ENTRIES:
                    raise ValueError("Folder exceeds its entry-count limit")
                names.append(item.name)
        for name in sorted(names):
            path = relative_path(prefix + name)
            before = os.stat(name, dir_fd=descriptor, follow_symlinks=False)
            if before.st_dev != device:
                raise ValueError("Folder cannot cross a filesystem boundary")
            if stat.S_ISDIR(before.st_mode):
                child = os.open(name, os.O_RDONLY | os.O_DIRECTORY | os.O_NOFOLLOW | os.O_CLOEXEC, dir_fd=descriptor)
                try:
                    actual = os.fstat(child)
                    if actual.st_ino != before.st_ino or actual.st_dev != before.st_dev:
                        raise ValueError("Folder changed while reading")
                    entries.append(Entry(path, "directory", mode=0o700))
                    walk(child, path + "/")
                finally:
                    os.close(child)
            elif stat.S_ISREG(before.st_mode):
                data = read_file(name, MAX_UPLOAD_CONTENT - total, descriptor)
                total += len(data)
                entries.append(Entry(path, "file", data, 0o600))
            else:
                raise ValueError("Folder cannot contain links or special files")
            if len(entries) > MAX_ENTRIES:
                raise ValueError("Folder exceeds its entry-count limit")
        final = os.fstat(descriptor)
        if (initial.st_mtime_ns, initial.st_ctime_ns) != (final.st_mtime_ns, final.st_ctime_ns):
            raise ValueError("Folder changed while reading")

    try:
        walk(root, "")
    finally:
        os.close(root)
    return make_archive(entries)


def write_export(destination, data):
    if not isinstance(data, bytes) or len(data) > MAX_ARCHIVE:
        raise ValueError("Invalid workspace export data")
    path = Path(destination)
    descriptor = os.open(path, os.O_WRONLY | os.O_CREAT | os.O_EXCL | os.O_NOFOLLOW | os.O_CLOEXEC, 0o600)
    with os.fdopen(descriptor, "wb") as output:
        output.write(data)
        output.flush()
        os.fsync(output.fileno())
    return {"destination": str(path.absolute()), "bytes": len(data), "sha256": sha256(data).hexdigest()}


def add_parser(commands):
    browser = commands.add_parser("files", help="List actual files in one node's workspace")
    browser.add_argument("id")
    browser.add_argument("node")
    imported = commands.add_parser("import-folder", help="Import a bounded folder, preserving empty directories; never overwrite")
    imported.add_argument("id")
    imported.add_argument("node")
    imported.add_argument("directory", type=Path)
    imported.add_argument("--name", help="New folder name inside the node workspace")
    for name in ("export-file", "export-folder"):
        exporter = commands.add_parser(name, help="Export workspace data to a new local file, never overwrite")
        exporter.add_argument("id")
        exporter.add_argument("node")
        exporter.add_argument("path", help="Relative workspace path; use . for the entire workspace archive")
        exporter.add_argument("output", type=Path, help="New output file; export-folder writes an uncompressed tar archive")


def prepare(arguments):
    if arguments.command == "import-folder":
        name = folder_name(arguments.name or arguments.directory.absolute().name)
        return name, read_directory(arguments.directory)
    if arguments.command in {"export-file", "export-folder"}:
        relative_path(arguments.path, root=arguments.command == "export-folder")
        if os.path.lexists(arguments.output):
            raise ValueError("Export destination already exists; choose a new filename")
    return None


async def run(bus, request, arguments, prepared):
    if arguments.command == "files":
        return json.loads(await request(bus, "ListWorkspace", [arguments.id, arguments.node]))
    if arguments.command == "import-folder":
        name, data = prepared
        return json.loads(await request(bus, "ImportWorkspace", [arguments.id, arguments.node, name, data]))
    method = "ReadWorkspaceFile" if arguments.command == "export-file" else "ExportWorkspace"
    data = await request(bus, method, [arguments.id, arguments.node, arguments.path])
    return write_export(arguments.output, data)
