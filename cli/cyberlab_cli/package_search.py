"""Public package metadata lookup in the desktop user's process, never root."""
import fcntl
import json
import math
import os
from pathlib import Path
import stat
import subprocess
import sys
from time import time
from uuid import uuid4

from cyberlab.authoring.packages import MAX_PACKAGES, PackageSearch
from cyberlab.lab.software import PACKAGE_NAME

MAX_CACHE = 64 * 1024**2
CACHE_TTL = 6 * 3600
CACHE_VERSION = 2


def private_file(descriptor, directory=False):
    info = os.fstat(descriptor)
    kind = stat.S_ISDIR if directory else stat.S_ISREG
    if not kind(info.st_mode) or info.st_uid != os.getuid() or info.st_mode & 0o077 or (not directory and info.st_nlink != 1):
        raise ValueError("Package search cache must be private and owned by the current user")
    return info


def cache_directory():
    if os.geteuid() == 0:
        raise ValueError("Package search must run as the desktop user, not root")
    base = os.environ.get("XDG_CACHE_HOME", "")
    location = (Path(base) if base and Path(base).is_absolute() else Path.home() / ".cache") / "cyberlab" / "package-search"
    location.mkdir(mode=0o700, parents=True, exist_ok=True)
    descriptor = os.open(location, os.O_RDONLY | os.O_DIRECTORY | os.O_NOFOLLOW | os.O_CLOEXEC)
    try:
        private_file(descriptor, directory=True)
        return descriptor
    except Exception:
        os.close(descriptor)
        raise


def read_json(directory, name, limit):
    try:
        descriptor = os.open(name, os.O_RDONLY | os.O_NOFOLLOW | os.O_NONBLOCK | os.O_CLOEXEC, dir_fd=directory)
    except FileNotFoundError:
        return None
    with os.fdopen(descriptor, "rb") as source:
        if private_file(source.fileno()).st_size > limit:
            return None
        data = source.read(limit + 1)
    if len(data) > limit:
        return None
    try:
        value = json.loads(data)
        return value if isinstance(value, dict) else None
    except (ValueError, UnicodeError):
        return None


def write_json(directory, name, value, limit):
    data = json.dumps(value, ensure_ascii=True, separators=(",", ":")).encode()
    if len(data) > limit:
        raise ValueError("Package search cache exceeds its size limit")
    temporary = ".index-" + uuid4().hex
    descriptor = os.open(temporary, os.O_WRONLY | os.O_CREAT | os.O_EXCL | os.O_NOFOLLOW | os.O_CLOEXEC, 0o600, dir_fd=directory)
    try:
        with os.fdopen(descriptor, "wb") as destination:
            destination.write(data)
            destination.flush()
            os.fsync(destination.fileno())
        os.replace(temporary, name, src_dir_fd=directory, dst_dir_fd=directory)
    finally:
        try:
            os.unlink(temporary, dir_fd=directory)
        except FileNotFoundError:
            pass


def timestamp(value):
    return value if type(value) in (int, float) and math.isfinite(value) and 0 <= value <= time() + 60 else 0


def cached_entries(document, architecture, field="entries"):
    if not document or document.get("version") != CACHE_VERSION or document.get("architecture") != architecture or not timestamp(document.get("loaded_at")):
        return {}
    entries = document.get(field, {})
    if not isinstance(entries, dict) or len(entries) > MAX_PACKAGES:
        return {}
    valid = {}
    for name, entry in entries.items():
        if not isinstance(name, str) or PACKAGE_NAME.fullmatch(name) is None or not isinstance(entry, dict):
            return {}
        if field == "mozilla_entries" and name != "firefox":
            return {}
        description = entry.get("description", "")
        searchable = entry.get("search", "")
        requires_snap = entry.get("requires_snap", False)
        if not isinstance(description, str) or len(description) > 240 or not isinstance(searchable, str) or len(searchable) > 500 or type(requires_snap) is not bool:
            return {}
        valid[name] = {"id": name, "name": name, "description": description, "search": searchable}
        if requires_snap:
            if field == "mozilla_entries":
                return {}
            valid[name]["requires_snap"] = True
    return valid


def start_worker(directory, lock):
    subprocess.Popen([sys.executable, "-I", "-m", "cyberlab_cli.package_search", str(directory), str(lock)],
                     stdin=subprocess.DEVNULL, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL,
                     pass_fds=(directory, lock), start_new_session=True)


def search(query, refresh=False):
    index = PackageSearch(auto_load=False)
    result = index.search(query, refresh)
    if not index.architecture:
        return result
    directory = cache_directory()
    lock = None
    try:
        lock = os.open("index.lock", os.O_RDWR | os.O_CREAT | os.O_NOFOLLOW | os.O_NONBLOCK | os.O_CLOEXEC, 0o600, dir_fd=directory)
        private_file(lock)
        acquired = True
        try:
            fcntl.flock(lock, fcntl.LOCK_EX | fcntl.LOCK_NB)
        except BlockingIOError:
            acquired = False
        document = read_json(directory, "index.json", MAX_CACHE)
        index.entries = cached_entries(document, index.architecture)
        index.mozilla_entries = cached_entries(document, index.architecture, "mozilla_entries")
        index.mozilla_error = bool(document and document.get("version") == CACHE_VERSION and document.get("mozilla_error") is True)
        now = time()
        if index.entries:
            index.loaded_at = index.clock() - max(0, now - document["loaded_at"])
        status = read_json(directory, "status.json", 2048) or {}
        if not acquired:
            index.loading = True
        else:
            stale = not index.entries or now - document["loaded_at"] >= CACHE_TTL
            retry = now - timestamp(status.get("attempted_at")) >= (10 if refresh else 60)
            if (stale or refresh) and retry:
                write_json(directory, "status.json", {"state": "loading", "attempted_at": now}, 2048)
                try:
                    start_worker(directory, lock)
                    index.loading = True
                except OSError:
                    write_json(directory, "status.json", {"state": "error", "attempted_at": now}, 2048)
                    index.error = "unavailable"
            elif status.get("state") in {"loading", "error"} or not index.entries:
                index.error = "unavailable"
        return index.search(query, False)
    finally:
        if lock is not None:
            os.close(lock)
        os.close(directory)


def update(directory, lock):
    if os.geteuid() == 0:
        raise ValueError("Metadata worker must not run as root")
    private_file(directory, directory=True)
    private_file(lock)
    index = PackageSearch(auto_load=False)
    attempted_at = time()
    try:
        if not index.architecture:
            raise ValueError("Unsupported package architecture")
        previous = read_json(directory, "index.json", MAX_CACHE)
        index.mozilla_entries = cached_entries(previous, index.architecture, "mozilla_entries")
        index._load()
        if index.error:
            raise ValueError("Ubuntu metadata is unavailable")
        write_json(directory, "index.json", {"version": CACHE_VERSION, "architecture": index.architecture, "loaded_at": time(), "entries": index.entries, "mozilla_entries": index.mozilla_entries, "mozilla_error": index.mozilla_error}, MAX_CACHE)
        write_json(directory, "status.json", {"state": "ready", "attempted_at": attempted_at}, 2048)
    except Exception:
        write_json(directory, "status.json", {"state": "error", "attempted_at": attempted_at}, 2048)
    finally:
        os.close(lock)
        os.close(directory)


if __name__ == "__main__":
    if len(sys.argv) != 3:
        raise SystemExit("This module is an internal metadata worker")
    update(int(sys.argv[1]), int(sys.argv[2]))
