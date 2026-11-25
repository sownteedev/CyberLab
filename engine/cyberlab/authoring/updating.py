import ctypes
import logging
import os
from pathlib import Path
import tempfile

from cyberlab.lab.catalog import lab_directory
from cyberlab.lab.loader import load_lab
from cyberlab.lab.package import digest, materialize, open_directory, read_directory
from cyberlab.lab.removal import remove_tree

from .store import DraftConflict

SYSTEM_CATALOG = Path("/var/lib/cyberlab/labs")

def private_catalog(catalog):
    return Path(catalog).resolve() == SYSTEM_CATALOG


def exchange(parent, source, destination):
    library = ctypes.CDLL(None, use_errno=True)
    rename = library.renameat2
    rename.argtypes = [ctypes.c_int, ctypes.c_char_p, ctypes.c_int, ctypes.c_char_p, ctypes.c_uint]
    rename.restype = ctypes.c_int
    if rename(parent, os.fsencode(source), parent, os.fsencode(destination), 2):
        raise OSError(ctypes.get_errno(), "Cannot atomically exchange Lab directories")


def sync_tree(directory, owner, *, private=False):
    for entry in (*directory.rglob("*"), directory):
        entry.chmod((0o700 if entry.is_dir() else 0o600) if private else (0o755 if entry.is_dir() else 0o644))
        if not private and os.geteuid() == 0:
            os.chown(entry, owner.st_uid, owner.st_gid)
        descriptor = os.open(entry, os.O_RDONLY | os.O_NOFOLLOW | os.O_CLOEXEC)
        try:
            os.fsync(descriptor)
        finally:
            os.close(descriptor)


def update_catalog(catalog, lab_id, snapshot, expected_digest, policy, *, record_origin=None):
    destination = lab_directory(catalog, lab_id)
    original = destination.stat(follow_symlinks=False)
    if read_directory(destination)[2] != expected_digest:
        raise DraftConflict("Installed Lab changed; reopen it before updating")
    parent = open_directory(catalog)
    stage = None
    exchanged = False
    committed = False
    cleanup_pending = False
    preserve_stage = False
    replacement_digest = digest(snapshot["definition"], snapshot["assets"])
    try:
        stage = Path(tempfile.mkdtemp(prefix=".cyberlab-update-", dir=catalog))
        materialize(snapshot, stage)
        replacement = load_lab(stage / "lab.yaml")
        if replacement.metadata.id != lab_id:
            raise DraftConflict("Replacement Lab ID does not match the target")
        policy.validate(replacement)
        sync_tree(stage, original, private=private_catalog(catalog))
        staged = stage.stat(follow_symlinks=False)
        current = os.stat(destination.name, dir_fd=parent, follow_symlinks=False)
        if ((current.st_dev, current.st_ino) != (original.st_dev, original.st_ino)
                or read_directory(destination)[2] != expected_digest):
            raise DraftConflict("Installed Lab changed while staging; no replacement was made")
        exchange(parent, stage.name, destination.name)
        exchanged = True
        try:
            previous = os.stat(stage.name, dir_fd=parent, follow_symlinks=False)
            if ((previous.st_dev, previous.st_ino) != (original.st_dev, original.st_ino)
                    or read_directory(stage)[2] != expected_digest):
                raise DraftConflict("Installed Lab changed concurrently; the previous version was restored")
            os.fsync(parent)
            if record_origin is not None:
                record_origin(replacement_digest)
        except BaseException:
            preserve_stage = True
            logging.warning("Interrupted Lab update: retaining recovery directory %s", stage)
            try:
                actual = os.stat(destination.name, dir_fd=parent, follow_symlinks=False)
                unchanged = ((actual.st_dev, actual.st_ino) == (staged.st_dev, staged.st_ino)
                             and read_directory(destination)[2] == replacement_digest)
            except Exception:
                unchanged = False
            if not unchanged:
                raise DraftConflict("Installed Lab changed during update recovery; versions retained for administrator recovery") from None
            exchange(parent, stage.name, destination.name)
            exchanged = False
            os.fsync(parent)
            raise
        committed = True
        try:
            remove_tree(parent, stage.name)
            os.fsync(parent)
        except OSError:
            cleanup_pending = True
        return {"lab_id": lab_id, "version": replacement.metadata.version,
                "catalog_digest": replacement_digest,
                "cleanup_pending": cleanup_pending}
    finally:
        try:
            if stage is not None and not exchanged and not committed and not preserve_stage:
                remove_tree(parent, stage.name)
        finally:
            os.close(parent)
