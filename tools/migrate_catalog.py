"""Explicit administrator migration to the private system catalog; keeps the source."""

import argparse
from hashlib import sha256
import json
import os
from pathlib import Path
import pwd
import re
import shutil
import signal
import stat
import sys
import tempfile
import tomllib

import upgrade_runtime as updater


DESTINATION = Path("/var/lib/cyberlab/labs")
MAX_FILES = 100000
MAX_BYTES = 8 * 1024**3


def walk_catalog(source, destination=None):
    manifest = {}
    total = 0

    def visit(descriptor, prefix, output, depth):
        nonlocal total
        if depth > 64:
            raise ValueError("Catalog directory nesting exceeds limit")
        for name in sorted(os.listdir(descriptor)):
            if len(manifest) >= MAX_FILES:
                raise ValueError("Catalog entry count exceeds limit")
            relative = f"{prefix}/{name}" if prefix else name
            before = os.stat(name, dir_fd=descriptor, follow_symlinks=False)
            if stat.S_ISDIR(before.st_mode):
                child = os.open(name, os.O_RDONLY | os.O_DIRECTORY | os.O_NOFOLLOW, dir_fd=descriptor)
                try:
                    opened = os.fstat(child)
                    if (before.st_dev, before.st_ino) != (opened.st_dev, opened.st_ino):
                        raise ValueError("Catalog directory changed while reading")
                    target = output / name if output is not None else None
                    if target is not None:
                        target.mkdir(mode=0o700)
                    manifest[relative] = ("directory",)
                    visit(child, relative, target, depth + 1)
                finally:
                    os.close(child)
            elif stat.S_ISREG(before.st_mode) and before.st_nlink == 1:
                total += before.st_size
                if total > MAX_BYTES:
                    raise ValueError("Catalog size exceeds limit")
                child = os.open(name, os.O_RDONLY | os.O_NOFOLLOW | os.O_NONBLOCK, dir_fd=descriptor)
                with os.fdopen(child, "rb") as stream:
                    opened = os.fstat(stream.fileno())
                    if (before.st_dev, before.st_ino, before.st_size, before.st_mtime_ns,
                        before.st_ctime_ns) != (opened.st_dev, opened.st_ino, opened.st_size,
                                               opened.st_mtime_ns, opened.st_ctime_ns):
                        raise ValueError("Catalog file changed while opening")
                    digest = sha256()
                    length = 0
                    target = None
                    try:
                        if output is not None:
                            target = os.fdopen(os.open(output / name, os.O_WRONLY | os.O_CREAT | os.O_EXCL, 0o600), "wb")
                        while block := stream.read(1024 * 1024):
                            length += len(block)
                            if length > before.st_size:
                                raise ValueError("Catalog file grew while reading")
                            digest.update(block)
                            if target is not None:
                                target.write(block)
                        if target is not None:
                            target.flush()
                            os.fsync(target.fileno())
                    finally:
                        if target is not None:
                            target.close()
                    after = os.fstat(stream.fileno())
                    if (length, after.st_mtime_ns, after.st_ctime_ns) != (before.st_size, before.st_mtime_ns, before.st_ctime_ns):
                        raise ValueError("Catalog file changed while reading")
                    manifest[relative] = ("file", length, digest.hexdigest())
            else:
                raise ValueError(f"Catalog contains a link or special file: {relative}")

    descriptor = os.open(source, os.O_RDONLY | os.O_DIRECTORY | os.O_NOFOLLOW)
    try:
        visit(descriptor, "", destination, 0)
    finally:
        os.close(descriptor)
    return manifest


def tree_digest(source):
    return walk_catalog(source)


def copy_catalog(source, destination):
    destination.mkdir(mode=0o700)
    return walk_catalog(source, destination)


def catalog_config(original, destination):
    document = tomllib.loads(original.decode("utf-8"))
    text, count = re.subn(r"(?m)^catalog\s*=.*$", lambda _: "catalog = " + json.dumps(str(destination)), original.decode("utf-8"))
    expected = dict(document, catalog=str(destination))
    if count != 1 or tomllib.loads(text) != expected:
        raise ValueError("Cannot safely replace the existing catalog setting")
    return text.encode("utf-8")


def verify_private_catalog(destination, allowed_uids):
    for entry in [destination, *destination.rglob("*")]:
        status = entry.lstat()
        expected = 0o700 if stat.S_ISDIR(status.st_mode) else 0o600
        if status.st_uid != 0 or status.st_gid != 0 or stat.S_IMODE(status.st_mode) != expected or entry.is_symlink():
            raise RuntimeError(f"Catalog is not root-private: {entry}")
    for uid in allowed_uids:
        result = updater.run("/usr/sbin/runuser", "-u", pwd.getpwuid(uid).pw_name, "--", "/usr/bin/test", "!", "-r", destination)
        if result.returncode:
            raise RuntimeError("Desktop account can read the private catalog")


def activate(staged, destination, replacements, uid, allowed_uids, checkpoints, labs):
    originals = [(path, path.read_bytes(), stat.S_IMODE(path.stat().st_mode)) for path, _, _ in replacements]
    try:
        updater.run("/usr/bin/systemctl", "stop", updater.SERVICE)
        updater.check_studio_closed()
        updater.check_stored_sessions(allowed_uids, checkpoints)
        for path, content, _ in originals:
            if path.read_bytes() != content:
                raise RuntimeError("Configuration changed during migration")
        if os.path.lexists(destination):
            raise FileExistsError(destination)
        staged.rename(destination)
        for path, content, mode in replacements:
            updater.replace_file(path, content, mode)
        updater.run("/usr/bin/systemctl", "daemon-reload")
        updater.run("/usr/bin/systemctl", "start", updater.SERVICE)
        updater.wait_for_daemon(uid)
        identity = lambda entries: sorted((entry["id"], entry["name"], entry["version"]) for entry in entries)
        if identity(updater.cli(uid, "labs")) != identity(labs):
            raise RuntimeError("Catalog identities changed after migration")
        updater.check_stored_sessions(allowed_uids, checkpoints)
        current = updater.stopped_checkpoints(allowed_uids)
        keys = ("id", "owner_uid", "checkpoint_at", "updated_at")
        checkpoint_identity = lambda entries: sorted(tuple(entry[key] for key in keys) for entry in entries.values())
        if set(current) != set(checkpoints) or checkpoint_identity(current) != checkpoint_identity(checkpoints):
            raise RuntimeError("Saved Session identities changed after migration")
        verify_private_catalog(destination, allowed_uids)
    except BaseException as error:
        with updater.recovery_signals():
            try:
                updater.run("/usr/bin/systemctl", "stop", updater.SERVICE)
                for path, content, mode in originals:
                    updater.replace_file(path, content, mode)
                updater.run("/usr/bin/systemctl", "daemon-reload")
                updater.run("/usr/bin/systemctl", "start", updater.SERVICE)
                updater.wait_for_daemon(uid)
            except BaseException as rollback_error:
                raise RuntimeError(f"Migration failed: {error}; rollback FAILED: {rollback_error}. Preserve backup.") from rollback_error
        raise RuntimeError(f"Migration failed; previous configuration restored: {error}. Preserve backup; do not blindly retry.") from error


def migrate(uid):
    if os.geteuid() != 0:
        raise ValueError("Run this administrator tool with sudo in your terminal")
    os.umask(0o077)
    with updater.installer_lock(), updater.installer_lock(path=updater.MAINTENANCE_LOCK):
        updater.check_admin_path(updater.CONFIG)
        updater.check_admin_path(updater.AUTHORING_DROPIN)
        updater.check_admin_path(DESTINATION.parent)
        original = updater.CONFIG.read_bytes()
        document = tomllib.loads(original.decode())
        allowed_uids = document["allowed_uids"]
        if uid not in allowed_uids or 0 in allowed_uids:
            raise ValueError("Expected a permitted non-root desktop account")
        source = Path(document["catalog"])
        if not source.is_absolute() or source.resolve() != source:
            raise ValueError("Existing catalog must be an absolute path without symlinks")
        if source == DESTINATION or source in DESTINATION.parents or DESTINATION in source.parents:
            raise ValueError("Catalog is already migrated or overlaps the target")
        if os.path.lexists(DESTINATION):
            raise ValueError("Target already exists; no catalog will be overwritten")
        if set(updater.AUTHORING_DROPIN.parent.iterdir()) != {updater.AUTHORING_DROPIN}:
            raise ValueError("Additional systemd overrides need administrator review")
        dropin = updater.AUTHORING_DROPIN.read_text()
        escaped_source = json.dumps(str(source).replace("%", "%%"), ensure_ascii=False)
        for line in dropin.splitlines():
            if line.strip() and not line.startswith("#") and line not in {
                "[Service]", "ProtectHome=tmpfs", f"BindPaths={escaped_source}",
                f"ReadWritePaths={escaped_source} /var/lib/cyberlab/authoring",
                "UMask=0077", f"SupplementaryGroups={pwd.getpwuid(uid).pw_gid}",
            }:
                raise ValueError("Custom authoring service policy needs administrator review")
        updater.check_studio_closed()
        info = updater.wait_for_daemon(uid)
        if not {"runtime:docker", "maintenance-lock-v1"}.issubset(info.get("capabilities", [])):
            raise ValueError("Update the installed daemon before migrating its catalog")
        if "maintenance-busy" in info.get("capabilities", []):
            raise ValueError("Wait for background software preparation to finish")
        checkpoints = updater.stopped_checkpoints(allowed_uids)
        labs = updater.cli(uid, "labs")
        manifest = tree_digest(source)
        required = sum(entry[1] for entry in manifest.values() if entry[0] == "file") + updater.SPACE_RESERVE
        if shutil.disk_usage(DESTINATION.parent).free < required:
            raise ValueError("Not enough free space to copy the catalog safely")
        backup = Path(tempfile.mkdtemp(prefix="cyberlab-catalog-migration-", dir="/var/tmp"))
        print(f"Backup: {backup}", flush=True)
        replacements = [
            (updater.CONFIG, catalog_config(original, DESTINATION), 0o600),
            (updater.AUTHORING_DROPIN, b'[Service]\nProtectHome=true\nReadWritePaths=/var/lib/cyberlab/labs /var/lib/cyberlab/authoring\nUMask=0077\n', 0o644),
        ]
        receipt = updater.APP / "installation.json"
        if receipt.exists():
            updater.check_admin_path(receipt)
            content = json.loads(receipt.read_bytes())
            content["catalog"] = str(DESTINATION)
            replacements.append((receipt, (json.dumps(content, indent=2) + "\n").encode(), 0o644))
        for path, _, _ in replacements:
            (backup / path.name).write_bytes(path.read_bytes())
        (backup / "migration.json").write_text(json.dumps({"source": str(source), "target": str(DESTINATION), "manifest": manifest}, indent=2))
        staging = Path(tempfile.mkdtemp(prefix=".catalog-migration-", dir=DESTINATION.parent))
        print(f"Staging: {staging}", flush=True)
        staged = staging / "labs"
        try:
            copied = copy_catalog(source, staged)
            if copied != manifest or tree_digest(staged) != manifest or tree_digest(source) != manifest:
                raise RuntimeError("Catalog changed while copying; original kept unchanged")
            if updater.stopped_checkpoints(allowed_uids) != checkpoints:
                raise RuntimeError("Sessions changed during preparation")
            for path, _, _ in replacements:
                if path.read_bytes() != (backup / path.name).read_bytes():
                    raise RuntimeError("Configuration changed during preparation")
            updater.check_studio_closed()
            activate(staged, DESTINATION, replacements, uid, allowed_uids, checkpoints, labs)
        finally:
            if not any(staging.iterdir()):
                staging.rmdir()
        (backup / "verified").write_text("Catalog identity, stored Sessions and private permissions verified.\n")
        print(f"DONE: catalog is now {DESTINATION}. Original retained at {source}; it was NOT deleted.")


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--uid", type=int, required=True)
    args = parser.parse_args()
    def interrupted(signum, frame):
        raise InterruptedError(f"Interrupted by signal {signum}")
    signal.signal(signal.SIGTERM, interrupted)
    try:
        migrate(args.uid)
    except (Exception, KeyboardInterrupt) as error:
        print(f"FAIL: {error}", file=sys.stderr)
        return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
