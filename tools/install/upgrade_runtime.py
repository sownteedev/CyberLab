"""Administrator-only package update; never installs or rewrites Lab templates."""

import argparse
from contextlib import closing, contextmanager
from email.parser import BytesParser
import fcntl
from hashlib import sha256
import json
import os
from pathlib import Path, PurePosixPath
import pwd
import shutil
import signal
import sqlite3
import stat
import subprocess
import tempfile
import time
import tomllib
import zipfile

APP = Path("/usr/lib/cyberlab")
CONFIG = Path("/etc/cyberlab/daemon.toml")
STATE = Path("/var/lib/cyberlab/authoring")
SERVICE = "cyberlabd.service"
ROOT = Path(__file__).resolve().parents[2]
UNIT = Path("/etc/systemd/system/cyberlabd.service")
AUTHORING_DROPIN = Path("/etc/systemd/system/cyberlabd.service.d/authoring.conf")
INSTALLER_LOCK = Path("/run/cyberlab-installer.lock")
MAINTENANCE_LOCK = Path("/run/cyberlab/maintenance.lock")
PROC = Path("/proc")
SPACE_RESERVE = 64 * 1024 * 1024
ENVIRONMENT = {"PATH": "/usr/sbin:/usr/bin:/sbin:/bin", "HOME": "/root", "LANG": "C.UTF-8",
               "PYTHONNOUSERSITE": "1", "PYTHONDONTWRITEBYTECODE": "1", "PIP_CONFIG_FILE": "/dev/null",
               "PIP_DISABLE_PIP_VERSION_CHECK": "1"}


def run(*arguments, timeout=330, env=None):
    return subprocess.run([str(value) for value in arguments], env=ENVIRONMENT if env is None else env,
                          capture_output=True, text=True, check=True, timeout=timeout, start_new_session=True)

@contextmanager
def installer_lock(lock_fd=None, *, path=None):
    """Acquire the installer's flock, or reuse its inherited descriptor without unlocking it."""
    path = path or INSTALLER_LOCK
    check_admin_path(path.parent)
    descriptor = (os.dup(lock_fd) if lock_fd is not None else
                  os.open(path, os.O_RDWR | os.O_CREAT | os.O_NOFOLLOW |
                          os.O_NONBLOCK | os.O_CLOEXEC, 0o600))
    try:
        status = os.fstat(descriptor)
        target = path.lstat()
        if (not stat.S_ISREG(status.st_mode) or status.st_nlink != 1
                or status.st_uid != os.geteuid() or status.st_mode & 0o022
                or stat.S_ISLNK(target.st_mode)
                or (status.st_dev, status.st_ino) != (target.st_dev, target.st_ino)):
            raise ValueError("Unsafe or unrelated installer lock descriptor")
        try:
            fcntl.flock(descriptor, fcntl.LOCK_EX | fcntl.LOCK_NB)
        except BlockingIOError:
            raise RuntimeError("Another CyberLab installation/update is active") from None
        yield descriptor
    finally:
        os.close(descriptor)

@contextmanager
def recovery_signals():
    previous = {signum: signal.signal(signum, signal.SIG_IGN) for signum in (signal.SIGINT, signal.SIGTERM)}
    try:
        yield
    finally:
        for signum, handler in previous.items():
            signal.signal(signum, handler)

def check_studio_closed():
    """Inspect every visible process, not only configured users; never signal Studio."""
    found = []
    for process in PROC.iterdir():
        if not process.name.isdecimal():
            continue
        try:
            with (process / "cmdline").open("rb") as stream:
                command = stream.read(1024 * 1024 + 1)
            if len(command) > 1024 * 1024:
                raise ValueError(f"Cannot safely inspect process {process.name}")
            arguments = command.decode(errors="replace").split("\0")
            if not arguments[0]:
                continue
            executable = Path(arguments[0]).name.lower()
            is_shell = executable in {"qs", "quickshell"} or "quickshell" in executable
            is_studio = any("cyberlab_studio" in argument.lower()
                            or "cyberlab-studio" in argument.lower()
                            or ("cyberlab" in argument.lower() and
                                (is_shell or "run_studio" in argument.lower()))
                            for argument in arguments)
            if is_studio:
                found.append(f"PID {process.name}, UID {process.stat().st_uid}")
        except (FileNotFoundError, ProcessLookupError):
            continue
        except PermissionError as error:
            raise ValueError(f"Cannot inspect all users' Studio processes: {process.name}") from error
    if found:
        raise ValueError("Close CyberLab Studio explicitly before upgrading (" + "; ".join(found) + ")")

def wheel_size(wheel, *, offline=False):
    total = 0
    with zipfile.ZipFile(wheel) as archive:
        for entry in archive.infolist():
            member = PurePosixPath(entry.filename)
            if (member.is_absolute() or ".." in member.parts or "\\" in entry.filename
                    or stat.S_ISLNK(entry.external_attr >> 16)):
                raise ValueError("Unsafe wheel member")
            total += entry.file_size
            if total > 512 * 1024 * 1024:
                raise ValueError("Unpacked dependency wheel exceeds limit")
            if offline and entry.filename.endswith(".dist-info/METADATA"):
                if entry.file_size > 1024 * 1024:
                    raise ValueError("Wheel metadata exceeds limit")
                metadata = BytesParser().parsebytes(archive.read(entry))
                if any("@" in requirement for requirement in metadata.get_all("Requires-Dist", [])):
                    raise ValueError("Offline wheels must not contain direct URL dependencies")
    return total

def dependency_wheels(wheelhouse):
    if wheelhouse.is_symlink() or not wheelhouse.is_dir():
        raise ValueError("Wheelhouse must be a directory, not a link")
    entries = sorted(wheelhouse.iterdir())
    if not entries or len(entries) > 64:
        raise ValueError("Wheelhouse must contain between 1 and 64 wheels")
    for entry in entries:
        status = entry.lstat()
        if (not entry.name.endswith(".whl") or not stat.S_ISREG(status.st_mode)
                or status.st_nlink != 1 or status.st_size > 64 * 1024 * 1024):
            raise ValueError("Wheelhouse must contain bounded regular wheels without links")
    return entries

def tree_size(directory):
    return sum(entry.lstat().st_size for entry in directory.rglob("*")
               if not entry.is_symlink() and entry.is_file()) if directory.exists() else 0

def preflight_space(wheel, backup, wheelhouse=None):
    """Budget backups, installation, pip temporaries and rollback on each filesystem."""
    wheels = [wheel, *(dependency_wheels(wheelhouse) if wheelhouse is not None else [])]
    compressed = sum(entry.stat().st_size for entry in wheels)
    unpacked = sum(wheel_size(entry, offline=wheelhouse is not None) for entry in wheels)
    venv_size, state_size = tree_size(APP / "venv"), tree_size(STATE)
    requirements = {}
    for directory, required in ((backup, venv_size + state_size + compressed + 3 * unpacked),
                                (APP, venv_size + unpacked),
                                (STATE if STATE.exists() else STATE.parent, state_size)):
        device = directory.stat().st_dev
        previous = requirements.get(device, (directory, SPACE_RESERVE))
        requirements[device] = (directory, previous[1] + required)
    for directory, required in requirements.values():
        available = shutil.disk_usage(directory).free
        if available < required:
            raise ValueError(f"Insufficient disk space on {directory}: need {required} bytes, have {available}")

def stage_wheelhouse(source, backup):
    destination = backup / "upgrade-wheelhouse"
    destination.mkdir(mode=0o700)
    for entry in dependency_wheels(source):
        descriptor = os.open(entry, os.O_RDONLY | os.O_NOFOLLOW | os.O_NONBLOCK | os.O_CLOEXEC)
        with os.fdopen(descriptor, "rb") as stream:
            before = os.fstat(stream.fileno())
            if not stat.S_ISREG(before.st_mode) or before.st_nlink != 1 or before.st_size > 64 * 1024 * 1024:
                raise ValueError("Unsafe dependency wheel")
            data = stream.read(64 * 1024 * 1024 + 1)
            after = os.fstat(stream.fileno())
        if (len(data) != before.st_size or
                (before.st_size, before.st_mtime_ns, before.st_ctime_ns) !=
                (after.st_size, after.st_mtime_ns, after.st_ctime_ns)):
            raise ValueError("Dependency wheel changed while staging")
        target = destination / entry.name
        with target.open("xb") as stream:
            stream.write(data)
        target.chmod(0o600)
        wheel_size(target, offline=True)
    return destination

def stopped_checkpoints(allowed_uids):
    result = {}
    for allowed_uid in allowed_uids:
        for session in cli(allowed_uid, "sessions"):
            if session.get("state") != "STOPPED":
                raise ValueError("Save work and stop all Sessions explicitly before upgrading")
            if session.get("saved"):
                result[session["id"]] = session
    return result

def offline_snapshot(allowed_uids):
    active = run("/usr/bin/systemctl", "show", SERVICE, "--property", "ActiveState", "--value").stdout.strip()
    if active != "inactive":
        raise ValueError("Offline migration requires an explicitly inactive daemon; it never stops a service")
    containers = run("/usr/bin/docker", "--host=unix:///var/run/docker.sock", "container", "ls", "--all", "--quiet",
                     "--filter", "label=org.ptit.cyberlab.managed=mvp-v1").stdout.strip()
    if containers:
        raise ValueError("Managed containers remain; offline migration refuses to discard their work")
    result = {}
    database = STATE / "practice.sqlite3"
    if database.exists():
        check_state()
        with closing(sqlite3.connect(database.as_uri() + "?mode=ro", uri=True)) as connection:
            rows = connection.execute("SELECT id, owner, state, checkpoint_at, updated_at FROM saved_sessions").fetchall()
        for identifier, owner, state, checkpoint, updated in rows:
            if state != "STOPPED":
                raise ValueError("Stored Sessions must be STOPPED before offline migration")
            if owner in allowed_uids:
                result[identifier] = {"id": identifier, "owner_uid": owner, "state": state,
                                      "checkpoint_at": checkpoint, "updated_at": updated, "saved": True}
    script = ("import json; from pathlib import Path; from cyberlabd.config import load_config; "
              "from cyberlab.lab import list_labs; "
              "print(json.dumps([dict(id=lab.metadata.id,name=lab.metadata.name,version=lab.metadata.version) "
              "for lab in list_labs(load_config(Path('/etc/cyberlab/daemon.toml')).catalog)]))")
    labs = json.loads(run(APP / "venv/bin/python", "-I", "-c", script).stdout)
    return result, labs

def check_stored_sessions(allowed_uids, checkpoints):
    """Recheck persisted Sessions after shutdown; unsaved Sessions are only available over D-Bus."""
    database = STATE / "practice.sqlite3"
    if not database.exists():
        if checkpoints:
            raise ValueError("Saved Session database disappeared during upgrade")
        return
    with closing(sqlite3.connect(database.as_uri() + "?mode=ro", uri=True)) as connection:
        rows = connection.execute("SELECT id, owner, state, checkpoint_at, updated_at FROM saved_sessions").fetchall()
    actual = sorted(row for row in rows if row[1] in allowed_uids)
    expected = sorted((entry["id"], entry["owner_uid"], "STOPPED", entry["checkpoint_at"], entry["updated_at"])
                      for entry in checkpoints.values())
    if actual != expected:
        raise ValueError("Stored Session state changed during upgrade; inspect Sessions before retrying")


def cli(uid, *arguments, timeout=330):
    account = pwd.getpwuid(uid)
    return json.loads(run("/usr/sbin/runuser", "-u", account.pw_name, "--",
                          "/usr/local/bin/cyberlab", *arguments, timeout=timeout).stdout)

def error_detail(error):
    detail = getattr(error, 'stderr', None) or getattr(error, 'stdout', None)
    if isinstance(detail, bytes):
        detail = detail.decode(errors='replace')
    return f"{error}\n{detail.strip()[-4000:]}" if detail else str(error)

def wait_for_daemon(uid, timeout=60):
    deadline = time.monotonic() + timeout
    last_error = None
    while True:
        remaining = deadline - time.monotonic()
        if remaining <= 0:
            raise RuntimeError(f"Daemon API did not become ready: {error_detail(last_error)}") from last_error
        run("/usr/bin/systemctl", "is-active", "--quiet", SERVICE, timeout=min(5, remaining))
        try:
            return cli(uid, "info", timeout=min(5, remaining))
        except (subprocess.CalledProcessError, subprocess.TimeoutExpired) as error:
            last_error = error
        time.sleep(min(0.5, remaining))


def stage_wheel(source, stage, expected):
    if len(expected) != 64 or any(character not in "0123456789abcdef" for character in expected):
        raise ValueError("Expected SHA-256 must be 64 lowercase hexadecimal characters")
    if not source.name.startswith("cyberlab_engine-") or not source.name.endswith("-py3-none-any.whl"):
        raise ValueError("Expected a CyberLab pure-Python wheel")
    descriptor = os.open(source, os.O_RDONLY | os.O_NOFOLLOW | os.O_NONBLOCK | os.O_CLOEXEC)
    with os.fdopen(descriptor, "rb") as stream:
        before = os.fstat(stream.fileno())
        if not stat.S_ISREG(before.st_mode) or before.st_nlink != 1 or before.st_size > 16 * 1024 * 1024:
            raise ValueError("Wheel must be a bounded regular file, not a link")
        data = stream.read(16 * 1024 * 1024 + 1)
        after = os.fstat(stream.fileno())
    if (before.st_size, before.st_mtime_ns, before.st_ctime_ns) != (after.st_size, after.st_mtime_ns, after.st_ctime_ns):
        raise ValueError("Wheel changed while reading")
    if len(data) > 16 * 1024 * 1024 or sha256(data).hexdigest() != expected:
        raise ValueError("Wheel checksum mismatch")
    destination = stage / source.name
    with destination.open("xb") as stream:
        stream.write(data)
    destination.chmod(0o600)
    with zipfile.ZipFile(destination) as archive:
        total = 0
        for entry in archive.infolist():
            path = PurePosixPath(entry.filename)
            mode = entry.external_attr >> 16
            if path.is_absolute() or ".." in path.parts or "\\" in entry.filename or stat.S_ISLNK(mode):
                raise ValueError("Unsafe wheel member")
            total += entry.file_size
            if total > 64 * 1024 * 1024:
                raise ValueError("Unpacked wheel exceeds limit")
            if path.parts and path.parts[0] in {"labs", "tests", "ui", "tools"}:
                raise ValueError("Runtime wheel must not contain catalog or development directories")
    return destination


def check_admin_path(path):
    for entry in (*reversed(path.parents), path):
        status = entry.lstat()
        if stat.S_ISLNK(status.st_mode) or status.st_uid != 0 or status.st_mode & 0o022:
            raise ValueError(f"Unsafe administrator path: {entry}")


def service_policy_updates():
    changes = {}
    for source, destination, key, previous, approved in (
        (ROOT / "daemon/systemd/cyberlabd.service", UNIT, "CapabilityBoundingSet", ('', 'CAP_CHOWN'), "CAP_CHOWN CAP_SETUID CAP_SETGID"),
        (ROOT / "daemon/systemd/cyberlabd.service", UNIT, "AmbientCapabilities", (), "CAP_SETUID"),
        (ROOT / "daemon/systemd/cyberlabd.service", UNIT, "BindReadOnlyPaths", (), "-/tmp/.X11-unix"),
        (ROOT / "daemon/systemd/cyberlabd.service", UNIT, "RuntimeDirectory", (), "cyberlab"),
        (ROOT / "daemon/systemd/cyberlabd.service", UNIT, "RuntimeDirectoryMode", (), "0700"),
        (ROOT / "daemon/systemd/cyberlabd.service", UNIT, "RuntimeDirectoryPreserve", (), "yes"),
        (ROOT / "daemon/systemd/authoring.conf", AUTHORING_DROPIN, "UMask", ('0002',), "0077"),
    ):
        if not destination.exists():
            raise ValueError(f"Expected existing service file: {destination}")
        check_admin_path(destination)
        status = destination.lstat()
        if not stat.S_ISREG(status.st_mode) or status.st_nlink != 1 or status.st_size > 65536:
            raise ValueError("Service file must be a bounded regular file")
        if f"{key}={approved}" not in source.read_text().splitlines():
            raise ValueError("Repository service policy differs from the reviewed repair")
        if destination not in changes:
            original = destination.read_bytes()
            changes[destination] = (original, original.decode().splitlines())
        original, lines = changes[destination]
        matches = [index for index, line in enumerate(lines) if line.strip().startswith(key + "=")]
        if not matches and not previous:
            index = lines.index('[Service]') + 1
            lines.insert(index, f'{key}={approved}')
            continue
        if len(matches) != 1 or lines[matches[0]].strip() not in {f"{key}={value}" for value in (*previous, approved)}:
            raise ValueError(f"Custom {key} policy requires administrator review")
        if lines[matches[0]].strip() == f"{key}={approved}":
            continue
        lines[matches[0]] = f"{key}={approved}"
    return [(destination, original, ('\n'.join(lines) + '\n').encode())
            for destination, (original, lines) in changes.items() if original != ('\n'.join(lines) + '\n').encode()]


def verify_service_capabilities():
    process = run('/usr/bin/systemctl', 'show', SERVICE, '--property=MainPID', '--value').stdout.strip()
    if not process.isdecimal() or int(process) <= 0:
        raise RuntimeError('Cannot verify daemon process capabilities')
    status = dict(line.split(':', 1) for line in Path(f'/proc/{process}/status').read_text().splitlines() if ':' in line)
    required = (1 << 0) | (1 << 6) | (1 << 7)
    try:
        masks = {name: int(status[name].strip(), 16) for name in ('CapPrm', 'CapEff', 'CapBnd', 'CapAmb')}
        restricted = status['NoNewPrivs'].strip() == '1'
    except (KeyError, ValueError):
        raise RuntimeError('Incomplete daemon capability status') from None
    if (any(masks[name] != required for name in ('CapPrm', 'CapEff', 'CapBnd'))
            or masks['CapAmb'] not in (0, 1 << 7) or not restricted):
        raise RuntimeError('Daemon effective capabilities differ from the reviewed native-helper policy')
    return {name: f'{value:016x}' for name, value in masks.items()}

def replace_file(destination, data, mode):
    descriptor, temporary = tempfile.mkstemp(prefix=".cyberlab-upgrade-", dir=destination.parent)
    try:
        with os.fdopen(descriptor, "wb") as output:
            output.write(data)
            output.flush()
            os.fsync(output.fileno())
            os.fchmod(output.fileno(), mode)
        os.replace(temporary, destination)
    finally:
        Path(temporary).unlink(missing_ok=True)


def check_state():
    check_admin_path(STATE)
    if not STATE.is_dir() or STATE.stat().st_mode & 0o077:
        raise ValueError("Authoring state directory must be private")
    for entry in STATE.iterdir():
        check_admin_path(entry)
        status = entry.lstat()
        if not stat.S_ISREG(status.st_mode) or status.st_nlink != 1:
            raise ValueError("Authoring state must contain only regular files without hardlinks")
        if entry.name != "practice.sqlite3" and status.st_mode & 0o077:
            raise ValueError("Authoring state files must be private")


def recover_private_state(uid, backup):
    check_admin_path(CONFIG)
    document = tomllib.loads(CONFIG.read_text())
    if uid not in document["allowed_uids"]:
        raise ValueError("Recovery user is not allowed by the installed daemon")
    run("/usr/bin/systemctl", "is-failed", "--quiet", SERVICE)
    check_state()
    practice = STATE / "practice.sqlite3"
    if not practice.is_file() or stat.S_IMODE(practice.stat().st_mode) != 0o644:
        raise ValueError("Recovery is only for the confirmed legacy 0644 practice database")
    with closing(sqlite3.connect(practice.as_uri() + "?mode=ro", uri=True)) as connection:
        if connection.execute("SELECT COUNT(*) FROM saved_sessions").fetchone()[0]:
            raise ValueError("Saved Sessions require administrator review before recovery deployment")
    for arguments in (("ps", "--all", "--quiet"), ("network", "ls", "--quiet")):
        if run("/usr/bin/docker", "--host", "unix:///var/run/docker.sock", *arguments,
               "--filter", "label=org.ptit.cyberlab.managed=mvp-v1").stdout.strip():
            raise ValueError("CyberLab Docker resources remain; recovery will not remove them")
    shutil.copy2(practice, backup / "recovery-practice.sqlite3")
    (backup / "recovery-practice.sqlite3").chmod(0o600)
    practice.chmod(0o600)
    run("/usr/bin/systemctl", "start", SERVICE)
    run("/usr/bin/systemctl", "is-active", "--quiet", SERVICE)
    (backup / "recovery.json").write_text(json.dumps({
        "previous_mode": "0644", "current_mode": "0600", "saved_sessions": 0,
        "managed_resources": 0, "result": "service-started",
    }, indent=2) + "\n")


def preserve_stopped_checkpoints(database, sessions):
    if not sessions:
        return
    with closing(sqlite3.connect(database.as_uri() + "?mode=rw", uri=True)) as connection, connection:
        for session in sessions:
            if session.get("state") != "STOPPED" or not session.get("saved") or not session.get("checkpoint_at"):
                raise ValueError("Only verified stopped checkpoints can be preserved during upgrade")
            cursor = connection.execute("""
                UPDATE saved_sessions SET state='STOPPED', updated_at=?
                WHERE id=? AND owner=? AND checkpoint_at=?
            """, (session["updated_at"], session["id"], session["owner_uid"], session["checkpoint_at"]))
            if cursor.rowcount != 1:
                raise ValueError("Saved Session changed during upgrade; refuse to rewrite checkpoint state")

def upgrade(wheel, uid, backup, repair_service_policy=False, *, wheelhouse=None,
            verify_callback=None, lock_fd=None, offline=False):
    """Upgrade under the shared lock; a zero-argument callback participates in rollback.

    Pass the installer's inherited flock descriptor as lock_fd (normally 9).
    A supplied wheelhouse is copied into private staging for offline dependency
    installation; omitting it preserves the legacy no-deps installation path.
    """
    with installer_lock(lock_fd):
        if offline and not MAINTENANCE_LOCK.parent.exists():
            check_admin_path(MAINTENANCE_LOCK.parent.parent)
            MAINTENANCE_LOCK.parent.mkdir(mode=0o700)
        with installer_lock(path=MAINTENANCE_LOCK):
            return _upgrade(wheel, uid, backup, repair_service_policy, wheelhouse, verify_callback, offline)

def _upgrade(wheel, uid, backup, repair_service_policy, wheelhouse, verify_callback, offline):
    venv = APP / "venv"
    check_admin_path(venv)
    check_admin_path(CONFIG)
    old_config = CONFIG.read_bytes()
    document = tomllib.loads(old_config.decode())
    if uid not in document["allowed_uids"]:
        raise ValueError("Verification user is not allowed by the installed daemon")
    if verify_callback is not None and not callable(verify_callback):
        raise ValueError("Verification callback must be callable")
    check_studio_closed()
    preflight_space(wheel, backup, wheelhouse)
    staged_wheelhouse = stage_wheelhouse(wheelhouse, backup) if wheelhouse is not None else None
    temporary = backup / "pip-tmp"
    temporary.mkdir(mode=0o700)
    receipt = APP / "installation.json"
    old_receipt = None
    receipt_mode = None
    if receipt.exists() or receipt.is_symlink():
        check_admin_path(receipt)
        status = receipt.lstat()
        if not stat.S_ISREG(status.st_mode) or status.st_nlink != 1 or status.st_size > 1024 * 1024:
            raise ValueError("Installation receipt must be a bounded regular file")
        old_receipt = receipt.read_bytes()
        receipt_mode = stat.S_IMODE(status.st_mode)
        (backup / "installation.json").write_bytes(old_receipt)
        (backup / "installation.json").chmod(0o600)
    if offline:
        checkpoints, labs = offline_snapshot(document["allowed_uids"])
    else:
        run("/usr/bin/systemctl", "is-active", "--quiet", SERVICE)
        info = wait_for_daemon(uid)
        if "runtime:docker" not in info.get("capabilities", []):
            raise ValueError("Expected the installed System D-Bus Docker daemon")
        if "maintenance-lock-v1" not in info.get("capabilities", []):
            raise ValueError("Installed daemon lacks the maintenance barrier; automatic replacement is unsafe. "
                             "Use the documented administrator migration; no service was stopped")
        if "maintenance-busy" in info.get("capabilities", []):
            raise ValueError("Wait for background software preparation to finish before upgrading")
        checkpoints = stopped_checkpoints(document["allowed_uids"])
        labs = cli(uid, "labs")
    updates = service_policy_updates() if repair_service_policy else []
    (backup / "daemon.toml").write_bytes(old_config)
    (backup / "daemon.toml").chmod(0o600)
    copied = False
    state_copied = False
    applied = []
    check_studio_closed()
    if (offline_snapshot(document["allowed_uids"])[0] if offline else stopped_checkpoints(document["allowed_uids"])) != checkpoints:
        raise ValueError("Saved Sessions changed during upgrade preflight")
    try:
        if not offline:
            run("/usr/bin/systemctl", "stop", SERVICE)
        check_studio_closed()
        if CONFIG.read_bytes() != old_config:
            raise RuntimeError("Installed configuration changed during upgrade")
        if STATE.exists():
            check_state()
        check_stored_sessions(document["allowed_uids"], checkpoints)
        shutil.copytree(venv, backup / "venv", symlinks=True)
        copied = True
        if STATE.exists():
            check_state()
            shutil.copytree(STATE, backup / "authoring", symlinks=False)
            state_copied = True
            practice = STATE / "practice.sqlite3"
            if practice.exists():
                practice.chmod(0o600)
        preserve_stopped_checkpoints(STATE / "practice.sqlite3", list(checkpoints.values()))
        for index, (destination, previous, current) in enumerate(updates):
            (backup / f"service-{index}-{destination.name}").write_bytes(previous)
            if destination.read_bytes() != previous:
                raise RuntimeError("Service configuration changed during upgrade")
            replace_file(destination, current, 0o644)
            applied.append((destination, previous))
        if applied:
            run("/usr/bin/systemctl", "daemon-reload")
        dependency_options = (["--find-links", staged_wheelhouse, "--only-binary=:all:"]
                              if staged_wheelhouse is not None else ["--no-deps"])
        run(venv / "bin/python", "-I", "-m", "pip", "--isolated", "--no-cache-dir",
            "install", "--no-index", *dependency_options, "--force-reinstall", wheel,
            env={**ENVIRONMENT, "TMPDIR": str(temporary)})
        run(venv / "bin/python", "-I", "-m", "pip", "check")
        if CONFIG.read_bytes() != old_config:
            raise RuntimeError("Installed configuration changed during upgrade")
        run("/usr/bin/systemctl", "start", SERVICE)
        run("/usr/bin/systemctl", "is-active", "--quiet", SERVICE)
        effective_capabilities = verify_service_capabilities() if repair_service_policy else None
        installed = wait_for_daemon(uid)
        if not {"runtime:docker", "maintenance-lock-v1"}.issubset(installed.get("capabilities", [])):
            raise RuntimeError("Updated daemon failed runtime verification")
        after = cli(uid, "labs")
        identity = lambda entries: sorted((entry["id"], entry["name"], entry["version"]) for entry in entries)
        if identity(after) != identity(labs):
            raise RuntimeError("Catalog identity changed during package update")
        restored_checkpoints = {}
        for allowed_uid in document["allowed_uids"]:
            for session in cli(allowed_uid, "sessions"):
                if session.get("state") != "STOPPED":
                    raise RuntimeError("Session is no longer stopped after package update")
                if session.get("saved"):
                    restored_checkpoints[session["id"]] = session
        checkpoint_identity = lambda entries: sorted(
            (entry["id"], entry["owner_uid"], entry["checkpoint_at"], entry["updated_at"])
            for entry in entries.values())
        if checkpoint_identity(restored_checkpoints) != checkpoint_identity(checkpoints):
            raise RuntimeError("Saved Session identity changed during package update")
        if verify_callback is not None:
            verify_callback()
        (backup / "verification.json").write_text(json.dumps({
            "wheel": wheel.name, "sha256": sha256(wheel.read_bytes()).hexdigest(),
            "daemon": installed, "catalog_identity_preserved": True,
            "stopped_checkpoints_preserved": len(checkpoints),
            "service_policy_repaired": bool(applied), "result": "passed",
            "service_capabilities": effective_capabilities,
        }, indent=2) + "\n")
    except BaseException:
        with recovery_signals():
            run("/usr/bin/systemctl", "stop", SERVICE)
            if copied:
                failed = APP / ("failed-venv-" + backup.name)
                venv.rename(failed)
                shutil.copytree(backup / "venv", venv, symlinks=True)
            if state_copied:
                shutil.move(str(STATE), str(backup / "failed-authoring"))
                shutil.copytree(backup / "authoring", STATE, symlinks=False)
                practice = STATE / "practice.sqlite3"
                if practice.exists():
                    practice.chmod(0o600)
            for destination, previous in reversed(applied):
                replace_file(destination, previous, 0o644)
            if applied:
                run("/usr/bin/systemctl", "daemon-reload")
            if old_receipt is None:
                receipt.unlink(missing_ok=True)
            else:
                replace_file(receipt, old_receipt, receipt_mode)
            (backup / "verification.json").unlink(missing_ok=True)
            if not offline:
                run("/usr/bin/systemctl", "start", SERVICE)
        raise


def main():
    def interrupted(signum, frame):
        raise KeyboardInterrupt("Upgrade interrupted")

    signal.signal(signal.SIGTERM, interrupted)
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("wheel", type=Path)
    parser.add_argument("--sha256", required=True)
    parser.add_argument("--uid", type=int, required=True)
    parser.add_argument("--wheelhouse", type=Path, help="Dependency wheels to stage and install offline; omitted keeps --no-deps")
    parser.add_argument("--offline", action="store_true", help="Explicit migration after the administrator has safely stopped the legacy daemon")
    parser.add_argument("--repair-service-policy", action="store_true", help="Apply the reviewed private state and native-X11 helper/socket policy to the existing service")
    parser.add_argument("--recover-private-state", action="store_true", help="Recover the confirmed 0644 database startup failure only when no saved Sessions or managed resources remain")
    arguments = parser.parse_args()
    if os.geteuid() != 0 or arguments.uid <= 0:
        parser.error("Run with sudo and a non-root verification UID")
    with installer_lock() as lock_fd:
        check_studio_closed()
        backup = Path(tempfile.mkdtemp(prefix="cyberlab-runtime-backup-", dir="/var/tmp"))
        print(f"Backup and staging: {backup}", flush=True)
        wheel = stage_wheel(arguments.wheel.absolute(), backup, arguments.sha256)
        wheelhouse = arguments.wheelhouse.absolute() if arguments.wheelhouse is not None else None
        preflight_space(wheel, backup, wheelhouse)
        if arguments.recover_private_state:
            recover_private_state(arguments.uid, backup)
        upgrade(wheel, arguments.uid, backup, arguments.repair_service_policy,
                wheelhouse=wheelhouse, lock_fd=lock_fd, offline=arguments.offline)
    print("DONE: runtime package updated; catalog/configuration were not rewritten.")
    print("No real-Docker Session was created. Perform the documented acceptance checks separately.")


if __name__ == "__main__":
    try:
        main()
    except (OSError, ValueError, RuntimeError, zipfile.BadZipFile, subprocess.SubprocessError) as error:
        raise SystemExit(f"Upgrade failed: {error_detail(error)}. Preserve the backup; do not blindly retry.")
