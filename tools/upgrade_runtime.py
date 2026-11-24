"""Administrator-only package update; never installs or rewrites Lab templates."""

import argparse
from hashlib import sha256
import json
import os
from pathlib import Path, PurePosixPath
import pwd
import shutil
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
ROOT = Path(__file__).resolve().parents[1]
UNIT = Path("/etc/systemd/system/cyberlabd.service")
AUTHORING_DROPIN = Path("/etc/systemd/system/cyberlabd.service.d/authoring.conf")
ENVIRONMENT = {"PATH": "/usr/sbin:/usr/bin:/sbin:/bin", "HOME": "/root", "LANG": "C.UTF-8",
               "PYTHONNOUSERSITE": "1", "PYTHONDONTWRITEBYTECODE": "1", "PIP_CONFIG_FILE": "/dev/null",
               "PIP_DISABLE_PIP_VERSION_CHECK": "1"}


def run(*arguments, timeout=330):
    return subprocess.run([str(value) for value in arguments], env=ENVIRONMENT,
                          capture_output=True, text=True, check=True, timeout=timeout)


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
    with sqlite3.connect(practice.as_uri() + "?mode=ro", uri=True) as connection:
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
    with sqlite3.connect(database.as_uri() + "?mode=rw", uri=True) as connection:
        for session in sessions:
            if session.get("state") != "STOPPED" or not session.get("saved") or not session.get("checkpoint_at"):
                raise ValueError("Only verified stopped checkpoints can be preserved during upgrade")
            cursor = connection.execute("""
                UPDATE saved_sessions SET state='STOPPED', updated_at=?
                WHERE id=? AND owner=? AND checkpoint_at=?
            """, (session["updated_at"], session["id"], session["owner_uid"], session["checkpoint_at"]))
            if cursor.rowcount != 1:
                raise ValueError("Saved Session changed during upgrade; refuse to rewrite checkpoint state")

def upgrade(wheel, uid, backup, repair_service_policy=False):
    venv = APP / "venv"
    check_admin_path(venv)
    check_admin_path(CONFIG)
    old_config = CONFIG.read_bytes()
    document = tomllib.loads(old_config.decode())
    if uid not in document["allowed_uids"]:
        raise ValueError("Verification user is not allowed by the installed daemon")
    run("/usr/bin/systemctl", "is-active", "--quiet", SERVICE)
    info = wait_for_daemon(uid)
    if "runtime:docker" not in info.get("capabilities", []):
        raise ValueError("Expected the installed System D-Bus Docker daemon")
    stopped_checkpoints = {}
    for allowed_uid in document["allowed_uids"]:
        sessions = cli(allowed_uid, "sessions")
        if any(session.get("state") != "STOPPED" for session in sessions):
            raise ValueError("Save work and stop all Sessions explicitly before upgrading")
        for session in sessions:
            if session.get("saved"):
                stopped_checkpoints[session["id"]] = session
    labs = cli(uid, "labs")
    updates = service_policy_updates() if repair_service_policy else []
    (backup / "daemon.toml").write_bytes(old_config)
    (backup / "daemon.toml").chmod(0o600)
    copied = False
    state_copied = False
    applied = []
    try:
        run("/usr/bin/systemctl", "stop", SERVICE)
        shutil.copytree(venv, backup / "venv", symlinks=True)
        copied = True
        if STATE.exists():
            check_state()
            shutil.copytree(STATE, backup / "authoring", symlinks=False)
            state_copied = True
            practice = STATE / "practice.sqlite3"
            if practice.exists():
                practice.chmod(0o600)
        preserve_stopped_checkpoints(STATE / "practice.sqlite3", list(stopped_checkpoints.values()))
        for index, (destination, previous, current) in enumerate(updates):
            (backup / f"service-{index}-{destination.name}").write_bytes(previous)
            if destination.read_bytes() != previous:
                raise RuntimeError("Service configuration changed during upgrade")
            replace_file(destination, current, 0o644)
            applied.append((destination, previous))
        if applied:
            run("/usr/bin/systemctl", "daemon-reload")
        run(venv / "bin/python", "-I", "-m", "pip", "install", "--no-index", "--no-deps", "--force-reinstall", wheel)
        run(venv / "bin/python", "-I", "-m", "pip", "check")
        if CONFIG.read_bytes() != old_config:
            raise RuntimeError("Installed configuration changed during upgrade")
        run("/usr/bin/systemctl", "start", SERVICE)
        run("/usr/bin/systemctl", "is-active", "--quiet", SERVICE)
        effective_capabilities = verify_service_capabilities() if repair_service_policy else None
        installed = wait_for_daemon(uid)
        if "runtime:docker" not in installed.get("capabilities", []):
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
        if checkpoint_identity(restored_checkpoints) != checkpoint_identity(stopped_checkpoints):
            raise RuntimeError("Saved Session identity changed during package update")
        (backup / "verification.json").write_text(json.dumps({
            "wheel": wheel.name, "sha256": sha256(wheel.read_bytes()).hexdigest(),
            "daemon": installed, "catalog_identity_preserved": True,
            "stopped_checkpoints_preserved": len(stopped_checkpoints),
            "service_policy_repaired": bool(applied), "result": "passed",
            "service_capabilities": effective_capabilities,
        }, indent=2) + "\n")
    except Exception:
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
        run("/usr/bin/systemctl", "start", SERVICE)
        raise


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("wheel", type=Path)
    parser.add_argument("--sha256", required=True)
    parser.add_argument("--uid", type=int, required=True)
    parser.add_argument("--repair-service-policy", action="store_true", help="Apply the reviewed private state and native-X11 helper/socket policy to the existing service")
    parser.add_argument("--recover-private-state", action="store_true", help="Recover the confirmed 0644 database startup failure only when no saved Sessions or managed resources remain")
    arguments = parser.parse_args()
    if os.geteuid() != 0 or arguments.uid <= 0:
        parser.error("Run with sudo and a non-root verification UID")
    backup = Path(tempfile.mkdtemp(prefix="cyberlab-runtime-backup-", dir="/var/tmp"))
    print(f"Backup and staging: {backup}", flush=True)
    wheel = stage_wheel(arguments.wheel.absolute(), backup, arguments.sha256)
    if arguments.recover_private_state:
        recover_private_state(arguments.uid, backup)
    upgrade(wheel, arguments.uid, backup, arguments.repair_service_policy)
    print("DONE: runtime package updated; catalog/configuration were not rewritten.")
    print("No real-Docker Session was created. Perform the documented acceptance checks separately.")


if __name__ == "__main__":
    try:
        main()
    except (OSError, ValueError, RuntimeError, zipfile.BadZipFile, subprocess.SubprocessError) as error:
        raise SystemExit(f"Upgrade failed: {error_detail(error)}. Preserve the backup; do not blindly retry.")
