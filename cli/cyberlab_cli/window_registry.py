import json
from contextlib import contextmanager
import fcntl
from hashlib import sha256
import os
from pathlib import Path
import re
import signal
import stat
import tempfile


SESSION_ID = re.compile(r"[a-f0-9]{32}\Z")


def _root():
    if os.geteuid() == 0:
        raise ValueError("Terminal window tracking must run as the desktop user, not root")
    runtime_dir = os.environ.get("XDG_RUNTIME_DIR")
    if runtime_dir and os.path.isabs(runtime_dir):
        root = Path(runtime_dir) / "cyberlab" / "terminal-windows"
    else:
        root = Path.home() / ".cache" / "cyberlab" / "terminal-windows"
    root.mkdir(mode=0o700, parents=True, exist_ok=True)
    status = root.lstat()
    if not stat.S_ISDIR(status.st_mode) or status.st_uid != os.geteuid() or status.st_mode & 0o077:
        raise ValueError("Unsafe terminal window registry permissions")
    return root


def _path(session_id, test_session_bus=False):
    if not isinstance(session_id, str) or SESSION_ID.fullmatch(session_id) is None:
        raise ValueError("Invalid Session ID")
    namespace = "system"
    if test_session_bus:
        namespace = "test-" + sha256(os.environ.get("DBUS_SESSION_BUS_ADDRESS", "").encode()).hexdigest()[:24]
    return _root() / f"{namespace}-{session_id}.json"

def tabs_dir(session_id, test_session_bus=False):
    if not isinstance(session_id, str) or SESSION_ID.fullmatch(session_id) is None:
        raise ValueError("Invalid Session ID")
    namespace = "system"
    if test_session_bus:
        namespace = "test-" + sha256(os.environ.get("DBUS_SESSION_BUS_ADDRESS", "").encode()).hexdigest()[:24]
    directory = _root() / "tabs" / f"{namespace}-{session_id}"
    directory.mkdir(mode=0o700, parents=True, exist_ok=True)
    return directory

def cleanup_tabs(session_id, test_session_bus=False):
    try:
        directory = tabs_dir(session_id, test_session_bus)
        if directory.is_dir():
            for item in directory.glob("*.tabs"):
                try:
                    item.unlink()
                except OSError:
                    pass
            try:
                directory.rmdir()
            except OSError:
                pass
    except (OSError, ValueError):
        pass

@contextmanager
def _locked(path):
    descriptor = os.open(path.parent / ".lock", os.O_CREAT | os.O_RDWR | os.O_NOFOLLOW | os.O_CLOEXEC, 0o600)
    try:
        status = os.fstat(descriptor)
        if not stat.S_ISREG(status.st_mode) or status.st_uid != os.geteuid() or status.st_mode & 0o077:
            raise ValueError("Unsafe window registry lock")
        fcntl.flock(descriptor, fcntl.LOCK_EX)
        yield
    finally:
        os.close(descriptor)


def _read(path):
    try:
        descriptor = os.open(path, os.O_RDONLY | os.O_NOFOLLOW | os.O_NONBLOCK | os.O_CLOEXEC)
        with os.fdopen(descriptor, encoding="utf-8") as stream:
            status = os.fstat(stream.fileno())
            if not stat.S_ISREG(status.st_mode) or status.st_size > 65536:
                return []
            value = json.loads(stream.read(65537))
    except (FileNotFoundError, json.JSONDecodeError, UnicodeError, OSError):
        return []
    if not isinstance(value, list) or len(value) > 32:
        return []
    return [item for item in value if _valid_record(item)]


def _valid_record(record):
    return (
        isinstance(record, dict)
        and type(record.get("pid")) is int
        and record["pid"] > 0
        and type(record.get("start_time")) is int
        and record["start_time"] >= 0
        and type(record.get("pgid")) is int
        and record["pgid"] == record["pid"]
    )


def _write(path, records):
    if not records:
        try:
            path.unlink()
        except FileNotFoundError:
            pass
        return
    path.parent.mkdir(mode=0o700, parents=True, exist_ok=True)
    with tempfile.NamedTemporaryFile(
        mode="w", encoding="utf-8", dir=path.parent, delete=False
    ) as stream:
        json.dump(records, stream, separators=(",", ":"))
        stream.write("\n")
        temporary = Path(stream.name)
    temporary.chmod(0o600)
    os.replace(temporary, path)


def _start_time(pid):
    try:
        fields = Path(f"/proc/{pid}/stat").read_text(encoding="ascii").rsplit(")", 1)[1].split()
        return int(fields[19])
    except (FileNotFoundError, OSError, ValueError, IndexError):
        return None


def record_process(session_id, process, test_session_bus=False):
    """Record a detached terminal process when it exposes a real PID."""
    pid = getattr(process, "pid", None)
    if type(pid) is not int or pid <= 0:
        return False
    start_time = _start_time(pid)
    if start_time is None:
        return False
    try:
        pgid = os.getpgid(pid)
    except (ProcessLookupError, PermissionError, OSError):
        return False
    if pgid != pid:
        return False
    path = _path(session_id, test_session_bus)
    with _locked(path):
        records = [entry for entry in _read(path) if _matches(entry)]
        record = {"pid": pid, "pgid": pgid, "start_time": start_time}
        if record not in records:
            if len(records) >= 32:
                raise ValueError("Too many tracked terminal windows")
            records.append(record)
            _write(path, records)
    return True


def _matches(record):
    return _start_time(record["pid"]) == record["start_time"]


def _belongs_to_session(record, session_id, test_session_bus):
    process = Path(f"/proc/{record['pid']}")
    try:
        if process.stat().st_uid != os.geteuid() or os.getpgid(record["pid"]) != record["pid"]:
            return False
        arguments = process.joinpath("cmdline").read_bytes().split(b"\0")
        if not arguments or arguments[0] != b"/usr/bin/konsole":
            return False
        if b"-e" in arguments:
            idx = arguments.index(b"-e")
            if idx + 4 > len(arguments) or arguments[idx + 2:idx + 4] != [b"-I", b"-m"] or b"cyberlab_cli.main" not in arguments[idx + 4]:
                return False
            index = idx + 5
            if test_session_bus:
                if arguments[index:index + 1] != [b"--test-session-bus"]:
                    return False
                index += 1
            return arguments[index:index + 2] == [b"terminal", session_id.encode("ascii")]
        if b"--tabs-from-file" in arguments:
            idx = arguments.index(b"--tabs-from-file")
            if idx + 1 < len(arguments):
                tabfile = Path(arguments[idx + 1].decode("utf-8", "replace"))
                if session_id in tabfile.name and tabfile.is_file():
                    content = tabfile.read_text("utf-8", "replace")
                    return session_id in content
        return False
    except (OSError, ValueError):
        return False

def close_session(session_id, test_session_bus=False):
    """Ask all terminal windows tracked for a Session to close."""
    path = _path(session_id, test_session_bus)
    closed = 0
    with _locked(path):
        remaining = []
        for record in _read(path):
            if not _matches(record):
                continue
            descriptor = None
            try:
                descriptor = os.pidfd_open(record["pid"])
                if not _matches(record) or not _belongs_to_session(record, session_id, test_session_bus):
                    continue
                signal.pidfd_send_signal(descriptor, signal.SIGTERM)
                closed += 1
            except ProcessLookupError:
                continue
            except OSError:
                remaining.append(record)
            finally:
                if descriptor is not None:
                    os.close(descriptor)
        _write(path, remaining)
    cleanup_tabs(session_id, test_session_bus)
    return closed
