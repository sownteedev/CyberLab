from dataclasses import replace
from itertools import islice
import os
from pathlib import Path
import re
import stat

from .models import SeedEntry

MAX_BYTES = 1024 * 1024
MAX_ENTRIES = 128

class AssetError(Exception):
    """The initial file snapshot violates the restricted asset policy."""

def valid_path(value):
    return (
        isinstance(value, str) and len(value) <= 200
        and 1 <= len(value.split("/")) <= 8
        and all(re.fullmatch(r"[A-Za-z0-9_][A-Za-z0-9_.-]{0,63}", part) for part in value.split("/"))
    )

def validate_mappings(mappings):
    if len(mappings) > 16:
        raise AssetError("Too many file mappings")
    targets = []
    for mapping in mappings:
        if not valid_path(mapping.source) or not mapping.source.startswith("assets/") or (mapping.target != "." and not valid_path(mapping.target)):
            raise AssetError("File mappings require safe assets-relative sources and workspace-relative targets")
        if any(mapping.target == "." or target == "." or mapping.target == target or mapping.target.startswith(target + "/") or target.startswith(mapping.target + "/") for target in targets):
            raise AssetError("File mapping targets must not overlap")
        targets.append(mapping.target)

def validate_seed(entries):
    if len(entries) > MAX_ENTRIES:
        raise AssetError("Initial files exceed the entry limit")
    paths = {}
    total = 0
    for entry in entries:
        if not valid_path(entry.path) or entry.path in paths:
            raise AssetError("Invalid or duplicate initial file path")
        if entry.data is not None and not isinstance(entry.data, bytes):
            raise AssetError("Initial files must contain immutable bytes")
        paths[entry.path] = entry.data
        total += len(entry.data) if entry.data is not None else 0
    if total > MAX_BYTES:
        raise AssetError("Initial files exceed the 1 MiB limit")
    for path in paths:
        parent = Path(path).parent
        while str(parent) != ".":
            if str(parent) not in paths or paths[str(parent)] is not None:
                raise AssetError("Initial files require directory parents")
            parent = parent.parent

def _check(status, is_home=False):
    if os.geteuid() == 0:
        if is_home:
            if status.st_mode & 0o002:
                raise AssetError("Production assets in home must not be world-writable")
        else:
            if status.st_uid != 0 or status.st_mode & 0o022:
                raise AssetError("Production assets must be root-owned and not writable by others")

def _open_directory(name, parent=None, trusted=True, is_home=False):
    descriptor = os.open(name, os.O_RDONLY | os.O_DIRECTORY | os.O_NOFOLLOW | os.O_CLOEXEC, dir_fd=parent)
    try:
        if trusted:
            _check(os.fstat(descriptor), is_home=is_home)
        return descriptor
    except BaseException:
        os.close(descriptor)
        raise

def snapshot_lab(lab, project):
    if not any(node.files for node in lab.nodes):
        return lab
    project_path = Path(os.path.abspath(project))
    is_home = len(project_path.parts) > 1 and project_path.parts[1] == "home"
    root = _open_directory("/")
    total_bytes = 0
    total_entries = 0
    try:
        for component in project_path.parts[1:]:
            child = _open_directory(component, root, trusted=False)
            os.close(root)
            root = child
        _check(os.fstat(root), is_home=is_home)
        device = os.fstat(root).st_dev
        nodes = []
        for node in lab.nodes:
            validate_mappings(node.files)
            entries = {}

            def add(path, data):
                nonlocal total_bytes, total_entries
                if not valid_path(path):
                    raise AssetError("Invalid or too deeply nested asset path")
                if path in entries:
                    if data is None and entries[path] is None:
                        return
                    raise AssetError("Overlapping initial file paths")
                total_entries += 1
                total_bytes += len(data) if data is not None else 0
                if total_entries > MAX_ENTRIES or total_bytes > MAX_BYTES:
                    raise AssetError("Lab assets exceed the 128 entry or 1 MiB limit")
                entries[path] = data

            def read_entry(parent, name, target):
                status = os.stat(name, dir_fd=parent, follow_symlinks=False)
                _check(status, is_home=is_home)
                if status.st_dev != device or not (stat.S_ISREG(status.st_mode) or stat.S_ISDIR(status.st_mode)):
                    raise AssetError("Assets must be regular files or directories on the project filesystem")
                if stat.S_ISDIR(status.st_mode):
                    descriptor = _open_directory(name, parent, is_home=is_home)
                    try:
                        actual = os.fstat(descriptor)
                        if (actual.st_dev, actual.st_ino) != (status.st_dev, status.st_ino):
                            raise AssetError("Asset directory changed while reading")
                        if target != ".":
                            add(target, None)
                        with os.scandir(descriptor) as iterator:
                            names = [entry.name for entry in islice(iterator, MAX_ENTRIES + 1)]
                        if len(names) > MAX_ENTRIES:
                            raise AssetError("Asset directory exceeds the entry limit")
                        for child in sorted(names):
                            read_entry(descriptor, child, child if target == "." else target + "/" + child)
                    finally:
                        os.close(descriptor)
                else:
                    if target == ".":
                        raise AssetError("Home-root mapping requires a directory source, not a file")
                    if status.st_nlink != 1 or status.st_size > MAX_BYTES - total_bytes:
                        raise AssetError("Asset hardlinks and oversized files are not allowed")
                    descriptor = os.open(name, os.O_RDONLY | os.O_NOFOLLOW | os.O_NONBLOCK | os.O_CLOEXEC, dir_fd=parent)
                    with os.fdopen(descriptor, "rb") as source:
                        actual = os.fstat(source.fileno())
                        _check(actual, is_home=is_home)
                        if (actual.st_dev, actual.st_ino, actual.st_mode, actual.st_nlink) != (status.st_dev, status.st_ino, status.st_mode, 1):
                            raise AssetError("Asset changed while reading")
                        data = source.read(MAX_BYTES - total_bytes + 1)
                        after = os.fstat(source.fileno())
                        if (after.st_size, after.st_mtime_ns, after.st_ctime_ns) != (status.st_size, status.st_mtime_ns, status.st_ctime_ns):
                            raise AssetError("Asset changed while reading")
                    add(target, data)

            for mapping in node.files:
                parent = os.dup(root)
                try:
                    parts = mapping.source.split("/")
                    for component in parts[:-1]:
                        child = _open_directory(component, parent, is_home=is_home)
                        os.close(parent)
                        parent = child
                        if os.fstat(parent).st_dev != device:
                            raise AssetError("Asset source crosses a filesystem boundary")
                    for ancestor in reversed(Path(mapping.target).parents):
                        if str(ancestor) != ".":
                            add(str(ancestor), None)
                    read_entry(parent, parts[-1], mapping.target)
                finally:
                    os.close(parent)
            seed = tuple(SeedEntry(path, data) for path, data in sorted(entries.items()))
            validate_seed(seed)
            nodes.append(replace(node, seed=seed))
        return replace(lab, nodes=tuple(nodes))
    except OSError:
        raise AssetError("Cannot safely read lab assets") from None
    finally:
        os.close(root)
