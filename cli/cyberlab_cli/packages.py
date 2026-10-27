from pathlib import Path
from io import BytesIO
import os
import stat
import zipfile

from cyberlab_ipc import MAX_LAB_PACKAGE, MAX_REVIEW_BYTES, MAX_REVIEW_ITEMS, MAX_SUBMISSION_BYTES
from cyberlab_ipc import MAX_LABTAINER_ARCHIVE, MAX_LABTAINER_CONTENT, MAX_LABTAINER_ENTRIES
from .drafts import read_file


def read_package(path):
    return read_file(path, MAX_LAB_PACKAGE)


def read_submissions(paths):
    if not 1 <= len(paths) <= MAX_REVIEW_ITEMS:
        raise ValueError("Select between 1 and 32 submissions")
    packages = []
    total = 0
    for path in paths:
        path = Path(path)
        if len(path.name) > 256:
            raise ValueError("Submission filename exceeds 256 characters")
        data = read_file(path, min(MAX_SUBMISSION_BYTES, MAX_REVIEW_BYTES - total))
        total += len(data)
        packages.append([path.name, data])
    return packages


def read_labtainer(path):
    path = Path(path)
    if not stat.S_ISDIR(path.lstat().st_mode):
        return read_file(path, MAX_LABTAINER_ARCHIVE)
    root = os.open(path, os.O_RDONLY | os.O_DIRECTORY | os.O_NOFOLLOW | os.O_CLOEXEC)
    total = 0
    count = 0
    device = os.fstat(root).st_dev
    output = BytesIO()

    def walk(directory, prefix, archive, depth=0):
        nonlocal total, count
        if depth > 15:
            raise ValueError("Labtainer folder nesting exceeds 16 levels")
        with os.scandir(directory) as entries:
            names = []
            for entry in entries:
                count += 1
                if count > MAX_LABTAINER_ENTRIES:
                    raise ValueError("Labtainer folder exceeds 512 entries")
                names.append(entry.name)
        for name in sorted(names):
            before = os.stat(name, dir_fd=directory, follow_symlinks=False)
            destination = prefix + name
            if before.st_dev != device:
                raise ValueError("Labtainer folder crosses a filesystem boundary")
            if stat.S_ISDIR(before.st_mode):
                child = os.open(name, os.O_RDONLY | os.O_DIRECTORY | os.O_NOFOLLOW | os.O_CLOEXEC, dir_fd=directory)
                try:
                    current = os.fstat(child)
                    if (before.st_dev, before.st_ino) != (current.st_dev, current.st_ino):
                        raise ValueError("Labtainer folder changed while reading")
                    archive.writestr(destination + "/", b"")
                    walk(child, destination + "/", archive, depth + 1)
                finally:
                    os.close(child)
            elif stat.S_ISREG(before.st_mode):
                data = read_file(name, MAX_LABTAINER_CONTENT - total, directory)
                total += len(data)
                archive.writestr(destination, data)
            else:
                raise ValueError("Labtainer folders cannot contain links or special files")

    try:
        with zipfile.ZipFile(output, "w", compression=zipfile.ZIP_DEFLATED) as archive:
            walk(root, "", archive)
    finally:
        os.close(root)
    if output.tell() > MAX_LABTAINER_ARCHIVE:
        raise ValueError("Labtainer archive exceeds 32 MiB")
    return output.getvalue()
