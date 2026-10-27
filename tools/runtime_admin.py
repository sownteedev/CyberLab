#!/usr/bin/env python3
"""Bounded validation, build and rollback helpers for the Bash installer."""

import argparse
from datetime import datetime, timezone
import grp
from hashlib import sha256
from importlib.util import find_spec, module_from_spec, spec_from_file_location
import json
import os
from pathlib import Path
import pwd
import re
import shutil
import signal
import stat
import subprocess
import sys
import tempfile
import time
import zipfile

sys.dont_write_bytecode = True
ROOT = Path(__file__).resolve().parents[1]
HOME_ROOT = Path("/home")
PYTHON = Path(sys.executable)
APP = Path("/usr/lib/cyberlab")
CONFIG = Path("/etc/cyberlab")
STATE = Path("/var/lib/cyberlab")
UNIT = Path("/etc/systemd/system/cyberlabd.service")
DROPIN = Path("/etc/systemd/system/cyberlabd.service.d")
BUS_POLICY = Path("/etc/dbus-1/system.d/org.ptit.CyberLab1.conf")
CLI = Path("/usr/local/bin/cyberlab")
STUDIO = Path("/usr/local/bin/cyberlab-studio")
DESKTOP = Path("/usr/share/applications/cyberlab-studio.desktop")
SERVICE = "cyberlabd.service"
IMAGE = "busybox:1.37.0"
MANAGED = "org.ptit.cyberlab.managed=mvp-v1"
SEARCH_PATH = "/usr/sbin:/usr/bin:/sbin:/bin"
ENVIRONMENT = {
    "PATH": SEARCH_PATH, "HOME": "/root", "LANG": "C.UTF-8",
    "PYTHONNOUSERSITE": "1", "PYTHONDONTWRITEBYTECODE": "1",
    "PIP_CONFIG_FILE": "/dev/null", "PIP_DISABLE_PIP_VERSION_CHECK": "1",
    "DEBIAN_FRONTEND": "noninteractive",
}
COMMANDS = ("systemctl", "systemd-analyze", "dbus-send", "docker", "runuser", "konsole")


def tool(name):
    spec = spec_from_file_location(name, ROOT / "tools" / f"{name}.py")
    module = module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def run(*arguments, account=None, timeout=300, check=True):
    environment = ENVIRONMENT.copy()
    command = [str(argument) for argument in arguments]
    if account is not None:
        environment.update(HOME=account.pw_dir, USER=account.pw_name, LOGNAME=account.pw_name)
        if os.geteuid() == 0:
            command = [shutil.which("runuser", path=SEARCH_PATH), "-u", account.pw_name, "--", *command]
        elif os.geteuid() != account.pw_uid:
            raise ValueError("Cannot verify a different Unix user without administrator access")
    result = subprocess.run(command, cwd="/", env=environment, text=True,
                            capture_output=True, timeout=timeout)
    if check and result.returncode:
        detail = (result.stderr or result.stdout).strip()[-5000:]
        raise RuntimeError(f"Command failed: {command[0]}: {detail}")
    return result


def account_for(name):
    name = name or os.environ.get("SUDO_USER") or pwd.getpwuid(os.getuid()).pw_name
    account = pwd.getpwnam(name)
    if account.pw_uid == 0:
        raise ValueError("Choose the desktop user with --user NAME; never run Studio as root")
    try:
        docker_group = grp.getgrnam("docker")
    except KeyError:
        docker_group = None
    if docker_group and docker_group.gr_gid in os.getgrouplist(account.pw_name, account.pw_gid):
        raise ValueError("The selected user belongs to the docker group; review access before installing")
    home = Path(account.pw_dir)
    if not home.is_absolute() or ".." in home.parts or home == HOME_ROOT or not home.is_relative_to(HOME_ROOT):
        raise ValueError("The current daemon policy requires a user home under /home")
    if any(ord(character) < 32 or ord(character) == 127 for character in str(home)):
        raise ValueError("Control characters are not allowed in the home path")
    for entry in (*reversed(home.parents), home):
        status = entry.lstat()
        if not stat.S_ISDIR(status.st_mode) or status.st_mode & 0o002:
            raise ValueError(f"Home ancestors must be real, non-world-writable directories: {entry}")
    if home.stat().st_uid != account.pw_uid:
        raise ValueError("The selected user must own their home directory")
    return account


def missing_dependencies():
    missing = {command for command in COMMANDS
               if shutil.which(command, path=SEARCH_PATH) is None}
    if find_spec("ensurepip") is None or find_spec("venv") is None:
        missing.add("Python venv/ensurepip")
    return sorted(missing)


def check_running_kernel(module_root=Path("/lib/modules")):
    release = os.uname().release
    if (module_root / release).is_dir() or not module_root.is_dir():
        return
    if not any(entry.is_dir() for entry in module_root.iterdir()):
        return
    active = run("/usr/bin/systemctl", "is-active", "--quiet", "docker.service", check=False)
    if active.returncode:
        raise ValueError(
            f"Kernel modules for the running kernel {release} are missing, but another kernel is installed. "
            "Reboot into the installed kernel before installing/starting Docker; no automatic reboot is performed"
        )


def docker_readiness(account, allow_stopped=False):
    unit = run("/usr/bin/systemctl", "show", "docker.service",
               "--property=LoadState", "--value").stdout.strip()
    if unit != "loaded":
        raise ValueError(f"System Docker service is {unit}; missing/masked/custom services are not changed automatically")
    identity = run("/usr/bin/docker", "--version", timeout=15).stdout.strip()
    if not identity.startswith("Docker version "):
        raise ValueError("CyberLab requires Docker Engine, not a Podman-compatible CLI")
    active = run("/usr/bin/systemctl", "is-active", "--quiet", "docker.service", check=False).returncode == 0
    if not active:
        if allow_stopped:
            print("READY TO START: system Docker is installed but stopped; installation will start it only after the UI checks pass")
            return True
        raise ValueError("Docker is not active. --check will not start services; explicitly start docker.service or run the installer")
    if os.geteuid() != 0:
        print("UNVERIFIED: Docker API health needs root. Run sudo bash install.sh --check --user " + account.pw_name)
        return False
    information = json.loads(run("/usr/bin/docker", "--host=unix:///var/run/docker.sock", "info", "--format", "{{json .}}", timeout=30).stdout)
    if information.get("OSType") != "linux" or not information.get("ServerVersion"):
        raise ValueError("The system Docker socket does not expose a ready Linux Docker Engine")
    if any("rootless" in option for option in information.get("SecurityOptions", [])):
        raise ValueError("The current CyberLab policy requires the root-owned system Docker Engine, not a rootless user daemon")
    print("PASS: system Docker Engine " + information["ServerVersion"])
    return True

def preflight(account, backend_only=False, allow_stopped=False):
    if sys.platform != "linux":
        raise ValueError("CyberLab requires Linux")
    if sys.version_info < (3, 12):
        raise ValueError("Python 3.12 or newer is required; no automatic Python/OS upgrade is performed")
    if not Path("/run/systemd/system").is_dir():
        raise ValueError("A running systemd host is required (not a container/chroot installer)")
    check_running_kernel()
    run(PYTHON, "-I", "-c", "import sys; assert sys.version_info >= (3, 12), 'Python >= 3.12 required'")
    missing = missing_dependencies()
    if missing:
        raise ValueError("Missing host dependencies: " + ", ".join(missing) + ". Run bash install.sh --deps-only")
    if not Path("/run/dbus/system_bus_socket").is_socket():
        raise ValueError("The host System D-Bus is not available")
    if not Path("/usr/bin/konsole").is_file():
        raise ValueError("CyberLab requires Konsole at /usr/bin/konsole")
    catalog = Path(account.pw_dir) / "CyberLab-labs"
    if os.path.lexists(catalog) and not backend_only:
        check_catalog_permissions(account, catalog)
    if Path("/var/run/docker.sock").exists():
        run(PYTHON, "-I", "-c", "import os; assert not os.access('/var/run/docker.sock', os.W_OK), 'Desktop user must not have Docker socket access'", account=account)
    if not backend_only:
        probe_runtime(account)
        try:
            run("/usr/bin/env", "QT_QPA_PLATFORM=offscreen", "/usr/bin/konsole", "--version", account=account, timeout=20)
        except RuntimeError as error:
            raise RuntimeError(
                "Konsole is installed but its native libraries are incompatible. "
                "Review --plan --allow-dependency-upgrades and repair the native dependency set; "
                "no application files have been installed. " + str(error)
            ) from error
    print("PASS: Python, systemd, System D-Bus, Docker CLI and Konsole prerequisites")
    return docker_readiness(account, allow_stopped)


def trusted_parents(path):
    for entry in reversed(path.parents):
        if not os.path.lexists(entry):
            continue
        status = entry.lstat()
        if not stat.S_ISDIR(status.st_mode) or status.st_uid != 0 or status.st_mode & 0o022:
            raise ValueError(f"Unsafe installation parent: {entry}")


def fresh_targets(check_service=True):
    for destination in (APP, CONFIG, STATE, UNIT, DROPIN, BUS_POLICY, CLI, STUDIO, DESKTOP):
        if os.path.lexists(destination):
            raise ValueError(f"Existing installation path: {destination}. Use --update for a healthy installation; do not overwrite a partial install")
        trusted_parents(destination)
    if check_service:
        loaded = run("/usr/bin/systemctl", "show", SERVICE, "--property=LoadState", "--value").stdout.strip()
        if loaded != "not-found":
            raise ValueError("A CyberLab service already exists; initial installation will not replace it")


def read_regular(path, limit):
    descriptor = os.open(path, os.O_RDONLY | os.O_NOFOLLOW | os.O_NONBLOCK | os.O_CLOEXEC)
    with os.fdopen(descriptor, "rb") as stream:
        before = os.fstat(stream.fileno())
        if not stat.S_ISREG(before.st_mode) or before.st_nlink != 1 or before.st_size > limit:
            raise ValueError(f"Expected a bounded regular file without links: {path}")
        content = stream.read(limit + 1)
        after = os.fstat(stream.fileno())
    if len(content) > limit or (before.st_size, before.st_mtime_ns, before.st_ctime_ns) != (after.st_size, after.st_mtime_ns, after.st_ctime_ns):
        raise ValueError(f"Source changed while reading: {path}")
    return content


def build_wheels(account, stage):
    build = Path(tempfile.mkdtemp(prefix="cyberlab-source-", dir="/var/tmp"))
    try:
        source = build / "source"
        source.mkdir()
        for name in ("pyproject.toml", "engine", "daemon", "cli", "schemas", "ui"):
            origin, destination = ROOT / name, source / name
            if origin.is_symlink():
                raise ValueError(f"Source symlinks are not supported: {origin}")
            if origin.is_dir():
                shutil.copytree(origin, destination, symlinks=True,
                                ignore=shutil.ignore_patterns("__pycache__", "*.pyc", "*.egg-info"))
            else:
                destination.write_bytes(read_regular(origin, 1024 * 1024))
        for entry in (*reversed(list(build.rglob("*"))), build):
            status = entry.lstat()
            if not (stat.S_ISDIR(status.st_mode) or stat.S_ISREG(status.st_mode)):
                raise ValueError(f"Source contains a link or special file: {entry}")
            os.chown(entry, account.pw_uid, account.pw_gid, follow_symlinks=False)
        build_python = build / "venv/bin/python"
        print("Building the app and downloading dependency wheels as the desktop user...", flush=True)
        run(PYTHON, "-I", "-m", "venv", build / "venv", account=account)
        run(build_python, "-I", "-m", "pip", "--isolated", "wheel", "--no-cache-dir",
            "--only-binary=:all:", "--wheel-dir", build / "wheels", source, account=account, timeout=1200)
        wheels = stage / "wheels"
        wheels.mkdir()
        manifest = {}
        for entry in sorted((build / "wheels").iterdir()):
            if not entry.name.endswith(".whl") or len(manifest) >= 64:
                raise ValueError("Unexpected build output")
            content = read_regular(entry, 32 * 1024 * 1024)
            (wheels / entry.name).write_bytes(content)
            manifest[entry.name] = sha256(content).hexdigest()
        candidates = list(wheels.glob("cyberlab_engine-*-py3-none-any.whl"))
        if len(candidates) != 1:
            raise ValueError("Build must produce exactly one CyberLab wheel")
        validated = tool("upgrade_runtime").stage_wheel(candidates[0], stage, manifest[candidates[0].name])
        (stage / "wheels.json").write_text(json.dumps(manifest, indent=2) + "\n")
        return validated
    finally:
        shutil.rmtree(build)


def native_runtime():
    spec = spec_from_file_location("studio_launcher", ROOT / "ui/launcher.py")
    launcher = module_from_spec(spec)
    spec.loader.exec_module(launcher)
    executable = launcher.native_quickshell()
    if executable is None:
        raise ValueError("Native Quickshell not found at /usr/bin/qs or /usr/bin/quickshell. Install the distro package; user AppImage wrappers are not accepted")
    return executable

def native_version(account):
    executable = native_runtime()
    version = run("/usr/bin/env", "QT_QPA_PLATFORM=offscreen", executable, "--version", account=account, timeout=20)
    version_text = (version.stdout + version.stderr).strip()
    match = re.search(r"quickshell\s+v?(\d+)\.(\d+)\.(\d+)", version_text, re.IGNORECASE)
    if not match or tuple(map(int, match.groups())) < (0, 3, 1):
        raise ValueError(f"Quickshell >=0.3.1 is required; native runtime reports: {version_text}")
    return executable, version_text

def probe_runtime(account):
    executable, version_text = native_version(account)
    with tempfile.TemporaryDirectory(prefix="cyberlab-qml-probe-") as directory:
        root = Path(directory)
        (root / "shell.qml").write_bytes(read_regular(ROOT / "tools/install/probe.qml", 16384))
        (root / "runtime").mkdir(mode=0o700)
        for entry in (root, root / "shell.qml", root / "runtime"):
            if os.geteuid() == 0:
                os.chown(entry, account.pw_uid, account.pw_gid)
        environment = ENVIRONMENT | {
            "HOME": directory, "USER": account.pw_name, "LOGNAME": account.pw_name,
            "XDG_CONFIG_HOME": directory, "XDG_CACHE_HOME": directory,
            "XDG_DATA_HOME": directory, "XDG_RUNTIME_DIR": str(root / "runtime"),
            "QT_QPA_PLATFORM": "offscreen", "QT_QUICK_BACKEND": "software",
            "QT_QUICK_CONTROLS_STYLE": "Material",
        }
        command = [str(executable), "--path", directory]
        if os.geteuid() == 0:
            command = [shutil.which("runuser", path=SEARCH_PATH), "-u", account.pw_name, "--", *command]
        process = subprocess.Popen(command, env=environment, cwd=directory, start_new_session=True,
                                   stdout=subprocess.PIPE, stderr=subprocess.STDOUT, text=True)
        try:
            output, _ = process.communicate(timeout=25)
        except subprocess.TimeoutExpired as error:
            detail = error.output or b""
            if isinstance(detail, bytes):
                detail = detail.decode(errors="replace")
            raise RuntimeError("Native QML probe timed out; its process group was closed. " + detail[-5000:]) from None
        finally:
            try:
                os.killpg(process.pid, signal.SIGKILL)
            except ProcessLookupError:
                pass
            process.wait()
        if process.returncode or "CYBERLAB_NATIVE_QML_OK" not in output:
            raise RuntimeError(f"Native Qt/QML modules failed the isolated offscreen check (exit {process.returncode}): " + output[-5000:])
    print("PASS: native Quickshell and required Qt/QML modules (isolated, offscreen)")
    return {"executable": str(executable), "version": version_text, "qml_probe": "passed"}


def install_file(destination, content, mode=0o644):
    trusted_parents(destination)
    destination.parent.mkdir(parents=True, exist_ok=True, mode=0o755)
    descriptor = os.open(destination, os.O_WRONLY | os.O_CREAT | os.O_EXCL | os.O_NOFOLLOW, mode)
    with os.fdopen(descriptor, "wb") as stream:
        stream.write(content)
        stream.flush()
        os.fchmod(stream.fileno(), mode)
        os.fsync(stream.fileno())


def configuration(account):
    catalog = Path(account.pw_dir) / "CyberLab-labs"
    config = (f"catalog = {json.dumps(str(catalog), ensure_ascii=False)}\n"
              f"allowed_uids = [{account.pw_uid}]\n"
              f"allowed_images = [{json.dumps(IMAGE)}]\nauthoring = true\n")
    escaped = json.dumps(str(catalog).replace("%", "%%"), ensure_ascii=False)
    dropin = (f"[Service]\nProtectHome=tmpfs\nBindPaths={escaped}\nReadWritePaths={escaped} {STATE}/authoring\n"
              f"SupplementaryGroups={account.pw_gid}\nUMask=0077\n")
    return catalog, config.encode(), dropin.encode()


def check_catalog_permissions(account, catalog):
    status = catalog.lstat()
    if not stat.S_ISDIR(status.st_mode) or status.st_mode & 0o002:
        raise ValueError("Existing catalog must be a real, non-world-writable directory")
    writable = status.st_uid == 0 and status.st_mode & 0o700 == 0o700
    writable |= status.st_gid in {0, account.pw_gid} and status.st_mode & 0o070 == 0o070
    if not writable:
        raise ValueError("Existing catalog is not writable by the bounded daemon. Its ownership/permissions were preserved; ask an administrator to grant the primary group access to this catalog only before retrying")

def prepare_catalog(account, catalog):
    if os.path.lexists(catalog):
        check_catalog_permissions(account, catalog)
        print(f"Preserving existing catalog, contents and permissions: {catalog}")
    else:
        catalog.mkdir(mode=0o775)
        os.chown(catalog, 0, account.pw_gid)
        catalog.chmod(0o2775)


def docker_preflight(account):
    run("/usr/bin/docker", "--host=unix:///var/run/docker.sock", "info", "--format", "{{.ServerVersion}}")
    run(PYTHON, "-I", "-c", "import os; assert not os.access('/var/run/docker.sock', os.W_OK), 'Desktop user must not have Docker socket access'", account=account)
    for kind in ("container", "network"):
        existing = run("/usr/bin/docker", "--host=unix:///var/run/docker.sock", kind,
                       "ls", "--quiet", "--filter", f"label={MANAGED}", *(["--all"] if kind == "container" else [])).stdout.strip()
        if existing:
            raise ValueError("Existing CyberLab Docker resources require review; refusing daemon startup cleanup")
    inspected = run("/usr/bin/docker", "--host=unix:///var/run/docker.sock", "image", "inspect", IMAGE, check=False)
    if inspected.returncode:
        print(f"Preloading the approved base image: {IMAGE}", flush=True)
        run("/usr/bin/docker", "--host=unix:///var/run/docker.sock", "pull", IMAGE, timeout=600)


def verify_daemon(account):
    for attempt in range(30):
        result = run(CLI, "info", account=account, check=False, timeout=15)
        if result.returncode == 0:
            information = json.loads(result.stdout)
            if {"runtime:docker", "authoring"}.issubset(information.get("capabilities", [])):
                run(CLI, "labs", account=account)
                return information
        time.sleep(0.5)
    raise RuntimeError("Daemon API did not become ready; inspect journalctl -u cyberlabd")


def stage_configuration(account, stage):
    _, config, dropin = configuration(account)
    destination = stage / "config"
    destination.mkdir()
    (destination / "daemon.toml").write_bytes(config)
    (destination / "authoring.conf").write_bytes(dropin)
    for name in ("daemon/systemd/cyberlabd.service", "daemon/dbus/org.ptit.CyberLab1.conf",
                 "daemon/bin/cyberlab", "daemon/bin/cyberlab-studio", "ui/cyberlab-studio.desktop"):
        (destination / Path(name).name).write_bytes(read_regular(ROOT / name, 65536))

def record_installation(account, stage, wheel):
    receipt = {"result": "passed", "installed_at": datetime.now(timezone.utc).isoformat(),
               "wheel": wheel.name, "sha256": sha256(read_regular(wheel, 16 * 1024 * 1024)).hexdigest(),
               "quickshell": json.loads((stage / "native-runtime.json").read_text()),
               "user": account.pw_name, "uid": account.pw_uid,
               "catalog": str(Path(account.pw_dir) / "CyberLab-labs"),
               "image": IMAGE, "verification": verify_daemon(account), "staging": str(stage)}
    (stage / "verification.json").write_text(json.dumps(receipt, indent=2) + "\n")
    install_file(APP / "installation.json", json.dumps(receipt, indent=2).encode() + b"\n")

def dnf_transaction_records(manifest):
    document = json.loads(read_regular(manifest, 8 * 1024 * 1024))
    if document.get("version") != "1.0" or document.get("groups") or document.get("environments"):
        raise ValueError("Unsupported DNF stored transaction format or group changes")
    packages = document.get("rpms")
    if not isinstance(packages, list) or not packages:
        raise ValueError("DNF stored transaction has no packages")
    records = []
    replacements = set()
    upgrades = set()
    for entry in packages:
        nevra = entry.get("nevra", "")
        if not re.fullmatch(r"[A-Za-z0-9][A-Za-z0-9+_.:~^%-]*", nevra):
            raise ValueError("Invalid DNF package identity")
        name, version, release_arch = nevra.rsplit("-", 2)
        release, architecture = release_arch.rsplit(".", 1)
        action = entry.get("action")
        if action == "Replaced":
            replacements.add((name, architecture))
            continue
        if action not in {"Install", "Upgrade", "Reinstall"}:
            raise ValueError(f"Unapproved DNF transaction action: {action}")
        if action == "Upgrade":
            upgrades.add((name, architecture))
        records.append(("upgrade" if action == "Upgrade" else "install", f"{name}.{architecture}", f"{version}-{release}"))
    if replacements - upgrades:
        raise ValueError("DNF would replace/remove packages outside an exact same-name architecture upgrade")
    for record in records:
        print("\t".join(record))


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--user", required=True)
    parser.add_argument("operation", choices=("account", "check", "native-version", "dnf-plan", "stage", "prepare", "verify", "update"))
    parser.add_argument("--backend-only", action="store_true")
    parser.add_argument("--allow-stopped-docker", action="store_true")
    parser.add_argument("--stage", type=Path)
    parser.add_argument("--wheel", type=Path)
    parser.add_argument("--manifest", type=Path)
    arguments = parser.parse_args()
    account = account_for(arguments.user)
    if arguments.operation == "dnf-plan":
        if arguments.manifest is None:
            parser.error("dnf-plan requires --manifest")
        dnf_transaction_records(arguments.manifest)
        return 0
    if arguments.operation == "account":
        check_running_kernel()
        if Path("/var/run/docker.sock").exists():
            run(PYTHON, "-I", "-c", "import os; assert not os.access('/var/run/docker.sock', os.W_OK), 'Desktop user must not have Docker socket access'", account=account)
        return 0
    if arguments.operation == "native-version":
        executable, version = native_version(account)
        print(f"PASS: {executable}: {version}")
        return 0
    if arguments.operation == "check":
        return 0 if preflight(account, arguments.backend_only, arguments.allow_stopped_docker) else 2
    if os.geteuid() != 0 or arguments.stage is None:
        parser.error("Administrative operations require root and --stage")
    stage = arguments.stage
    if not stage.is_absolute() or stage.parent != Path("/var/tmp") or not stage.name.startswith("cyberlab-app-install-"):
        raise ValueError("Expected an installer staging directory below /var/tmp")
    status = stage.lstat()
    if not stat.S_ISDIR(status.st_mode) or status.st_uid != 0 or status.st_mode & 0o077:
        raise ValueError("Staging must be a private root-owned directory, not a link")
    os.umask(0o022)
    if arguments.operation == "stage":
        build_wheels(account, stage)
        stage_configuration(account, stage)
    elif arguments.operation == "prepare":
        fresh_targets()
        runtime = probe_runtime(account)
        (stage / "native-runtime.json").write_text(json.dumps(runtime, indent=2) + "\n")
        docker_preflight(account)
        prepare_catalog(account, configuration(account)[0])
    else:
        wheel = arguments.wheel
        if wheel is None or wheel.parent != stage or wheel.is_symlink():
            raise ValueError("Expected a validated wheel in the private staging directory")
        if arguments.operation == "update":
            tool("upgrade_runtime").upgrade(wheel, account.pw_uid, stage)
        else:
            record_installation(account, stage, wheel)
    shadow = Path(account.pw_dir) / ".local/share/applications/cyberlab-studio.desktop"
    if shadow.exists() and arguments.operation in {"verify", "update"}:
        print(f"NOTE: a personal shortcut may shadow the global launcher; preserved: {shadow}")
    return 0


if __name__ == "__main__":
    try:
        raise SystemExit(main())
    except (OSError, KeyError, ValueError, RuntimeError, zipfile.BadZipFile, subprocess.SubprocessError) as error:
        raise SystemExit(f"Installation failed: {error}")
