import json
from contextlib import contextmanager
import fcntl
from hashlib import sha256
import os
from pathlib import Path
import re
import signal
import stat
import sys
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
            for item in (*directory.glob("*.tabs"), *directory.glob("*.profile")):
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
            if (not stat.S_ISREG(status.st_mode) or status.st_size > 65536
                    or status.st_uid != os.geteuid() or status.st_mode & 0o077):
                return []
            value = json.loads(stream.read(65537))
    except (FileNotFoundError, json.JSONDecodeError, UnicodeError, OSError):
        return []
    if not isinstance(value, list) or len(value) > 32:
        return []
    return [item for item in value if _valid_record(item)]


def _valid_record(record):
    common = (
        isinstance(record, dict)
        and type(record.get("pid")) is int
        and record["pid"] > 0
        and type(record.get("start_time")) is int
        and record["start_time"] >= 0
    )
    if not common:
        return False
    if record.get("kind") == "attachment":
        return (isinstance(record.get("node"), str)
                and re.fullmatch(r"[a-z][a-z0-9]*(-[a-z0-9]+)*", record["node"]) is not None
                and len(record["node"]) <= 64
                and type(record.get("slot")) is int and 0 <= record["slot"] < 4
                and isinstance(record.get("token"), str) and SESSION_ID.fullmatch(record["token"]) is not None
                and isinstance(record.get("title"), str) and len(record["title"]) <= 128
                and isinstance(record.get("python"), str) and os.path.isabs(record["python"]))
    return False


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


def _matches(record):
    return _start_time(record["pid"]) == record["start_time"]


def attachment_command(session_id, node_id, slot, token, title, test_session_bus=False, python=None):
    command = [python or sys.executable, "-I", "-m", "cyberlab_cli.main"]
    if test_session_bus:
        command.append("--test-session-bus")
    return command + ["terminal", session_id, node_id, "--slot", str(slot),
                      "--window-token", token, "--window-title", title.encode("utf-8").hex()]

def decode_title(value):
    if not isinstance(value, str) or len(value) > 1024:
        raise ValueError("Invalid terminal title")
    title = bytes.fromhex(value).decode("utf-8")
    if len(title) > 128 or any(not character.isprintable() for character in title):
        raise ValueError("Invalid terminal title")
    return title


def register_attachment(session_id, node_id, slot, token, title, test_session_bus=False):
    record = {"kind": "attachment", "pid": os.getpid(), "start_time": _start_time(os.getpid()),
              "node": node_id, "slot": slot, "token": token, "title": title, "python": sys.executable}
    if not _valid_record(record) or not _belongs_to_session(record, session_id, test_session_bus):
        raise ValueError("Invalid managed terminal attachment")
    path = _path(session_id, test_session_bus)
    with _locked(path):
        records = [entry for entry in _read(path) if _matches(entry)]
        if len(records) >= 32:
            raise ValueError("Too many tracked terminal attachments")
        records.append(record)
        _write(path, records)


def unregister_attachment(session_id, token, test_session_bus=False):
    path = _path(session_id, test_session_bus)
    with _locked(path):
        _write(path, [record for record in _read(path)
                      if not (record.get("token") == token and record["pid"] == os.getpid())])


def attached_tokens(session_id, test_session_bus=False):
    path = _path(session_id, test_session_bus)
    with _locked(path):
        return {record["token"] for record in _read(path)
                if record.get("kind") == "attachment" and _matches(record)
                and _belongs_to_session(record, session_id, test_session_bus)}


def _belongs_to_session(record, session_id, test_session_bus):
    process = Path(f"/proc/{record['pid']}")
    try:
        if process.stat().st_uid != os.geteuid():
            return False
        arguments = process.joinpath("cmdline").read_bytes().split(b"\0")
        if arguments and arguments[-1] == b"":
            arguments.pop()
        if record.get("kind") == "attachment":
            expected = attachment_command(session_id, record["node"], record["slot"], record["token"],
                                          record["title"], test_session_bus, record["python"])
            return (arguments == [os.fsencode(argument) for argument in expected]
                    and os.path.samefile(process / "exe", record["python"]))
        return False
    except (OSError, ValueError):
        return False

def close_session(session_id, test_session_bus=False):
    """Detach only verified CyberLab CLI children for this Session."""
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
