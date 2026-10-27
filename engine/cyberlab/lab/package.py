from hashlib import sha256
import json
import os
from pathlib import Path
import stat
import tempfile

from .assets import valid_path

MAX_DEFINITION = 64 * 1024
MAX_ASSET = 1024 * 1024
MAX_PACKAGE = 2 * 1024 * 1024
MAX_PATHS = 128


class PackageLimit(Exception):
    pass


def definition_text(text):
    if not isinstance(text, str) or "\x00" in text or len(text.encode("utf-8")) > MAX_DEFINITION:
        raise ValueError("Draft definition must be UTF-8 text without NUL and at most 64 KiB")


def asset_path(path):
    if not valid_path(path) or not path.startswith("assets/"):
        raise ValueError("Draft assets require safe paths under assets/")


def check_package(definition, assets):
    definition_text(definition)
    paths = set()
    total = len(definition.encode("utf-8"))
    for path, data in assets.items():
        if path != "assets" or data is not None:
            asset_path(path)
        if data is not None and (not isinstance(data, bytes) or len(data) > MAX_ASSET):
            raise ValueError("An asset must contain at most 1 MiB of bytes")
        total += len(data) if data is not None else 0
        paths.add(path)
        for parent in Path(path).parents:
            if str(parent) != ".":
                if str(parent) in assets and assets[str(parent)] is not None:
                    raise ValueError("Asset file and directory paths conflict")
                paths.add(str(parent))
        if len(paths) > MAX_PATHS or total > MAX_PACKAGE:
            raise PackageLimit("Draft exceeds 128 paths or 2 MiB including its definition")


def digest(definition, assets):
    manifest = {"definition": definition, "assets": [
        [path, sha256(data).hexdigest() if data is not None else None]
        for path, data in sorted(assets.items())
        if data is not None or not any(other.startswith(path + "/") for other in assets)
    ]}
    return sha256(json.dumps(manifest, sort_keys=True, ensure_ascii=True).encode()).hexdigest()


def materialize(snapshot, directory):
    check_package(snapshot["definition"], snapshot["assets"])
    (directory / "lab.yaml").write_text(snapshot["definition"], encoding="utf-8")
    for path, data in snapshot["assets"].items():
        destination = directory / path
        destination.parent.mkdir(parents=True, exist_ok=True, mode=0o700)
        if data is None:
            destination.mkdir(exist_ok=True, mode=0o700)
        else:
            destination.write_bytes(data)


def load_snapshot(snapshot):
    from .loader import load_lab

    with tempfile.TemporaryDirectory(prefix="cyberlab-session-package-") as directory:
        project = Path(directory)
        materialize(snapshot, project)
        return load_lab(project / "lab.yaml")


def open_directory(path):
    descriptor = os.open("/", os.O_RDONLY | os.O_DIRECTORY | os.O_CLOEXEC)
    try:
        for part in Path(os.path.abspath(path)).parts[1:]:
            child = os.open(part, os.O_RDONLY | os.O_DIRECTORY | os.O_NOFOLLOW | os.O_CLOEXEC,
                            dir_fd=descriptor)
            os.close(descriptor)
            descriptor = child
        return descriptor
    except BaseException:
        os.close(descriptor)
        raise


def identity(status):
    return status.st_dev, status.st_ino, status.st_mode, status.st_size, status.st_mtime_ns, status.st_ctime_ns


def read_directory(directory):
    root = open_directory(directory)
    assets = {}
    total = 0
    count = 0
    device = os.fstat(root).st_dev

    def read_file(parent, name, before, limit):
        descriptor = os.open(name, os.O_RDONLY | os.O_NOFOLLOW | os.O_NONBLOCK | os.O_CLOEXEC, dir_fd=parent)
        with os.fdopen(descriptor, "rb") as source:
            actual = os.fstat(source.fileno())
            if (not stat.S_ISREG(actual.st_mode) or actual.st_nlink != 1
                    or identity(actual) != identity(before) or actual.st_size > limit):
                raise ValueError("Catalog package contains an unsafe, changed or oversized file")
            data = source.read(limit + 1)
            if len(data) > limit or identity(actual) != identity(os.fstat(source.fileno())):
                raise ValueError("Catalog package changed while reading")
            return data

    def walk(parent, prefix=""):
        nonlocal count, total
        before = os.fstat(parent)
        with os.scandir(parent) as iterator:
            names = []
            for entry in iterator:
                count += 1
                if count > MAX_PATHS + 1:
                    raise PackageLimit("Catalog package exceeds 128 asset paths")
                names.append(entry.name)
        if prefix and not names:
            assets[prefix] = None
        definition = None
        for name in sorted(names):
            path = prefix + "/" + name if prefix else name
            status = os.stat(name, dir_fd=parent, follow_symlinks=False)
            if status.st_dev != device:
                raise ValueError("Catalog package crosses a filesystem boundary")
            if path == "lab.yaml":
                data = read_file(parent, name, status, MAX_DEFINITION)
                definition = data.decode("utf-8")
                total += len(data)
                continue
            if path != "assets":
                asset_path(path)
            if stat.S_ISDIR(status.st_mode):
                child = os.open(name, os.O_RDONLY | os.O_DIRECTORY | os.O_NOFOLLOW | os.O_CLOEXEC, dir_fd=parent)
                try:
                    if identity(status) != identity(os.fstat(child)):
                        raise ValueError("Catalog directory changed while reading")
                    walk(child, path)
                finally:
                    os.close(child)
            elif stat.S_ISREG(status.st_mode) and path != "assets":
                data = read_file(parent, name, status, min(MAX_ASSET, MAX_PACKAGE - total))
                total += len(data)
                assets[path] = data
            else:
                raise ValueError("Catalog packages cannot contain links or special files")
            if total > MAX_PACKAGE:
                raise PackageLimit("Catalog package exceeds 2 MiB")
        if identity(before) != identity(os.fstat(parent)):
            raise ValueError("Catalog directory changed while reading")
        return definition

    try:
        definition = walk(root)
        check_package(definition, assets)
        return definition, assets, digest(definition, assets)
    finally:
        os.close(root)
