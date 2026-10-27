import os
from pathlib import Path
import stat

from .package import MAX_PATHS


def remove_tree(parent, name):
    """Remove only an opened tree, reclaiming directory ownership with CAP_CHOWN."""
    if name in ("", ".", "..") or Path(name).name != name:
        raise ValueError("Removal requires one directory name")
    count = 0
    device = os.fstat(parent).st_dev

    def remove(directory, entry):
        nonlocal count
        descriptor = os.open(entry, os.O_RDONLY | os.O_DIRECTORY | os.O_NOFOLLOW | os.O_CLOEXEC, dir_fd=directory)
        try:
            status = os.fstat(descriptor)
            if status.st_dev != device:
                raise OSError("Cannot remove a tree across filesystem boundaries")
            if os.geteuid() == 0:
                os.fchown(descriptor, 0, status.st_gid)
                os.fchmod(descriptor, stat.S_IMODE(status.st_mode) | 0o700)
            with os.scandir(descriptor) as entries:
                for child in entries:
                    count += 1
                    if count > MAX_PATHS + 1:
                        raise OSError("Removal exceeds the Lab package entry limit")
                    if child.is_dir(follow_symlinks=False):
                        remove(descriptor, child.name)
                    else:
                        os.unlink(child.name, dir_fd=descriptor)
            current = os.stat(entry, dir_fd=directory, follow_symlinks=False)
            if (current.st_dev, current.st_ino) != (status.st_dev, status.st_ino):
                raise OSError("Directory changed during removal")
            os.rmdir(entry, dir_fd=directory)
        finally:
            os.close(descriptor)

    remove(parent, name)
