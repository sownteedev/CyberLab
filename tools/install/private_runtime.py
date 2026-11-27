"""Pinned private Qt/Quickshell builder; never build or launch GUI as root."""

import argparse
import fcntl
import hashlib
import json
import os
from pathlib import Path, PurePosixPath
import platform
import pwd
import resource
import shutil
import signal
import stat
import subprocess
import sys
import tarfile
import tempfile

HERE = Path(__file__).resolve().parent
DESTINATION = Path('/usr/lib/cyberlab/gui-runtime')
MAX_EXPANDED = 3 * 1024**3
MAX_FILES = 100000


def manifest():
    return json.loads((HERE / 'gui-runtime.json').read_text())


def safe_path(name):
    path = PurePosixPath(name)
    if not name or path.is_absolute() or '..' in path.parts or '\\' in name or ':' in name:
        raise ValueError('Unsafe archive path: ' + name)
    return path


def validate_listing(text):
    size = 0
    count = 0
    for line in text.splitlines():
        if line.startswith('Path = '):
            safe_path(line[7:])
            count += 1
        if line.startswith('Size = '):
            value = int(line[7:])
            if value < 0:
                raise ValueError('Invalid archive size')
            size += value
    if not count or count > MAX_FILES or size > MAX_EXPANDED:
        raise ValueError('Archive exceeds extraction limits')


def audit_tree(root):
    count = 0
    size = 0
    for entry in root.rglob('*'):
        count += 1
        info = entry.lstat()
        if stat.S_ISLNK(info.st_mode):
            if os.path.isabs(os.readlink(entry)) or not entry.resolve().is_relative_to(root.resolve()):
                raise ValueError('Runtime symlink escapes its tree: ' + str(entry))
        elif not (stat.S_ISREG(info.st_mode) or stat.S_ISDIR(info.st_mode)):
            raise ValueError('Special runtime file: ' + str(entry))
        size += info.st_size
    if count > MAX_FILES or size > MAX_EXPANDED:
        raise ValueError('Runtime exceeds size limits')


def extract_source(archive, destination):
    with tarfile.open(archive) as bundle:
        members = []
        names = set()
        links = set()
        size = 0
        for entry in bundle:
            members.append(entry)
            if len(members) > MAX_FILES:
                raise ValueError('Too many archive entries')
            path = safe_path(entry.name)
            if str(path) in names:
                raise ValueError('Duplicate archive path')
            names.add(str(path))
            if not (entry.isfile() or entry.isdir() or entry.issym()):
                raise ValueError('Unsupported archive entry')
            if entry.issym():
                target = destination / path.parent / entry.linkname
                if os.path.isabs(entry.linkname) or not target.resolve().is_relative_to(destination.resolve()):
                    raise ValueError('Archive symlink escapes destination')
                links.add(path)
            size += entry.size
            if entry.size < 0 or size > MAX_EXPANDED:
                raise ValueError('Archive exceeds extraction limits')
        for name in names:
            if any(parent in links for parent in PurePosixPath(name).parents):
                raise ValueError('Archive entry traverses a symlink')
        destination.mkdir(parents=True, exist_ok=True)
        bundle.extractall(destination, members=members, filter='data')
    audit_tree(destination)


def run_group(command, *, timeout, **options):
    with subprocess.Popen(command, start_new_session=True, **options) as process:
        try:
            status = process.wait(timeout=timeout)
            if status:
                raise subprocess.CalledProcessError(status, command)
        finally:
            try:
                os.killpg(process.pid, signal.SIGKILL)
            except ProcessLookupError:
                pass
            process.wait()


def download(item, destination):
    subprocess.run(['curl', '--fail', '--silent', '--show-error', '--location',
                    '--proto', '=https', '--proto-redir', '=https', '--connect-timeout', '20',
                    '--max-time', '600', '--max-filesize', str(item['size']),
                    '--output', str(destination), item['url']], check=True, timeout=620)
    with destination.open('rb') as stream:
        digest = hashlib.file_digest(stream, 'sha256').hexdigest()
    if destination.stat().st_size != item['size'] or digest != item['sha256']:
        raise ValueError('Downloaded artifact does not match pinned SHA-256: ' + item['name'])


def verify_display_libraries(root):
    for name in ('libqxcb.so', 'libqwayland.so'):
        plugin = root / 'qt/plugins/platforms' / name
        if not plugin.is_file():
            raise ValueError('Missing required display plugin: ' + name)
        output = subprocess.check_output(['ldd', str(plugin)], text=True, timeout=30)
        if 'not found' in output:
            raise ValueError('Missing display dependencies: ' + output)


def build(work):
    if os.geteuid() == 0:
        raise ValueError('Private runtime must be built without root')
    pins = manifest()
    if platform.machine() != pins['architecture']:
        raise ValueError('Private runtime currently requires x86_64')
    sdk = work / 'sdk'
    sdk.mkdir()
    archiver = shutil.which('7z') or shutil.which('7zz')
    if not archiver:
        raise ValueError('7-Zip is required to unpack the pinned Qt SDK')
    for item in pins['downloads']:
        archive = work / item['name']
        print('Downloading pinned GUI component: ' + item['name'], flush=True)
        download(item, archive)
        if item['name'].endswith('.7z'):
            listing = subprocess.check_output([archiver, 'l', '-slt', '-ba', str(archive)], text=True)
            validate_listing(listing)
            extraction = sdk / 'lib' if item['name'].startswith('icu-') else sdk
            subprocess.run([archiver, 'x', '-y', '-aoa', '-bso0', '-bsp0', '-o' + str(extraction), str(archive)],
                           check=True, timeout=300)
            audit_tree(sdk)
        else:
            extract_source(archive, work / 'source')
        archive.unlink()
    source = work / 'source' / ('quickshell-' + pins['quickshell'])
    output = work / 'payload'
    output.mkdir()
    build_dir = work / 'build'
    disabled = ('CRASH_HANDLER', 'WAYLAND', 'X11', 'I3', 'SERVICE_STATUS_NOTIFIER',
                'SERVICE_PIPEWIRE', 'SERVICE_MPRIS', 'SERVICE_PAM', 'SERVICE_POLKIT',
                'SERVICE_GREETD', 'SERVICE_UPOWER', 'SERVICE_NOTIFICATIONS', 'BLUETOOTH', 'NETWORK')
    command = ['cmake', '-S', str(source), '-B', str(build_dir), '-G', 'Ninja',
               '-DCMAKE_BUILD_TYPE=Release', '-DCMAKE_PREFIX_PATH=' + str(sdk),
               '-DCMAKE_INSTALL_PREFIX=' + str(output), '-DCMAKE_INSTALL_LIBDIR=lib',
               '-DCMAKE_INSTALL_RPATH=$ORIGIN/../qt/lib', '-DDISTRIBUTOR=CyberLab private runtime',
               '-DNO_PCH=ON',
               *(f'-D{feature}=OFF' for feature in disabled)]
    subprocess.run(command, check=True, timeout=120)
    subprocess.run(['cmake', '--build', str(build_dir), '--parallel', '2'], check=True, timeout=1800)
    (output / 'bin').mkdir()
    shutil.copy2(build_dir / 'src/quickshell', output / 'bin/quickshell')
    subprocess.run(['patchelf', '--set-rpath', '$ORIGIN/../qt/lib', str(output / 'bin/quickshell')], check=True)
    qt = output / 'qt'
    qt.mkdir()
    for name in ('lib', 'plugins', 'qml', 'translations', 'licenses', 'share', 'sbom'):
        if (sdk / name).exists():
            shutil.copytree(sdk / name, qt / name, symlinks=True)
    for name in ('cmake', 'pkgconfig', 'metatypes'):
        shutil.rmtree(qt / 'lib' / name, ignore_errors=True)
    for entry in (qt / 'lib').glob('*'):
        if entry.suffix in ('.a', '.prl'):
            entry.unlink()
    (output / 'bin/qt.conf').write_text('[Paths]\nPrefix=../qt\n')
    shutil.copy2(source / 'LICENSE', output / 'LICENSE.quickshell')
    shutil.copytree(HERE / 'gui-licenses', output / 'licenses')
    (output / 'manifest.json').write_text(json.dumps(pins, indent=2) + '\n')
    audit_tree(output)
    verify_display_libraries(output)
    subprocess.run([str(output / 'bin/quickshell'), '--version'], check=True, timeout=30)
    probe = work / 'probe'
    probe.mkdir()
    shutil.copy2(HERE / 'probe.qml', probe / 'shell.qml')
    environment = os.environ | {'QT_QPA_PLATFORM': 'offscreen', 'QT_QUICK_BACKEND': 'software',
                                'XDG_RUNTIME_DIR': str(work)}
    result = subprocess.run([str(output / 'bin/quickshell'), '--path', str(probe)],
                            env=environment, text=True, stdout=subprocess.PIPE,
                            stderr=subprocess.STDOUT, timeout=30)
    if result.returncode or 'CYBERLAB_NATIVE_QML_OK' not in result.stdout:
        raise ValueError('Private QML probe failed: ' + result.stdout[-6000:])
    return output


def create_runtime_parent(parent):
    parent.mkdir(mode=0o755)
    parent.chmod(0o755)


def install(user, lock_fd):
    if os.geteuid() != 0:
        raise ValueError('Installation requires administrator privileges')
    lock = Path('/run/cyberlab-installer.lock')
    descriptor = os.fstat(lock_fd)
    expected = lock.lstat()
    if (not stat.S_ISREG(expected.st_mode) or expected.st_uid != 0 or expected.st_mode & 0o022
            or (descriptor.st_dev, descriptor.st_ino) != (expected.st_dev, expected.st_ino)):
        raise ValueError('Invalid shared installer lock')
    fcntl.flock(lock_fd, fcntl.LOCK_EX | fcntl.LOCK_NB)
    account = pwd.getpwnam(user)
    if account.pw_uid == 0:
        raise ValueError('Select a non-root build account')
    if os.path.lexists(DESTINATION):
        raise ValueError('Existing private runtime is never overwritten; use its verified installed copy')
    if os.path.lexists(DESTINATION.parent):
        raise ValueError('Refusing to change the GUI provider of an existing installation')
    if shutil.disk_usage('/var/tmp').free < 5 * 1024**3 or shutil.disk_usage('/usr/lib').free < 1024**3:
        raise ValueError('Private runtime needs 5 GiB temporary space and 1 GiB installation space')
    for parent in (DESTINATION.parent, *DESTINATION.parents):
        if parent.exists() and (parent.is_symlink() or parent.stat().st_uid or parent.stat().st_mode & 0o022):
            raise ValueError('Unsafe installation parent: ' + str(parent))
    with tempfile.TemporaryDirectory(prefix='cyberlab-gui-build-', dir='/var/tmp') as directory:
        stage = Path(directory)
        stage.chmod(0o755)
        work = stage / 'work'
        work.mkdir(mode=0o700)
        os.chown(work, account.pw_uid, account.pw_gid)
        environment = ['PATH=/usr/local/bin:/usr/bin:/bin', 'LANG=C.UTF-8', 'HOME=' + str(work),
                       'XDG_CACHE_HOME=' + str(work / 'cache'), 'TMPDIR=' + str(work)]
        prefix = ['runuser', '-u', user, '--', '/usr/bin/env', '-i', *environment]
        run_group([*prefix, sys.executable, '-B', '-I', str(Path(__file__).resolve()),
                   '--build', str(work)], timeout=3600)
        archive = stage / 'payload.tar'
        with archive.open('wb') as stream:
            run_group([*prefix, 'tar', '-c', '-f', '-', '-C', str(work / 'payload'), '.'],
                      stdout=stream, timeout=120,
                      preexec_fn=lambda: resource.setrlimit(resource.RLIMIT_FSIZE, (MAX_EXPANDED, MAX_EXPANDED)))
        create_runtime_parent(DESTINATION.parent)
        try:
            with tempfile.TemporaryDirectory(prefix='.gui-stage-', dir=DESTINATION.parent) as staging:
                snapshot = Path(staging) / 'runtime'
                extract_source(archive, snapshot)
                for entry in (snapshot, *snapshot.rglob('*')):
                    if not entry.is_symlink():
                        entry.chmod(0o755 if entry.is_dir() or entry.stat().st_mode & 0o111 else 0o644)
                if json.loads((snapshot / 'manifest.json').read_text()) != manifest():
                    raise ValueError('Build manifest changed')
                snapshot.rename(DESTINATION)
        except BaseException:
            DESTINATION.parent.rmdir()
            raise
    print('Private Qt/Quickshell installed; temporary SDK/source removed.', flush=True)


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    mode = parser.add_mutually_exclusive_group(required=True)
    mode.add_argument('--build', type=Path)
    mode.add_argument('--user')
    mode.add_argument('--verify-display', type=Path)
    parser.add_argument('--lock-fd', type=int)
    args = parser.parse_args()
    def interrupted(signum, frame):
        raise KeyboardInterrupt
    signal.signal(signal.SIGTERM, interrupted)
    try:
        if args.build:
            build(args.build)
        elif args.verify_display:
            verify_display_libraries(args.verify_display)
        else:
            if args.lock_fd is None:
                raise ValueError('Use install.sh: a shared installer lock is required')
            install(args.user, args.lock_fd)
    except KeyboardInterrupt:
        print('Private GUI runtime cancelled; temporary build removed.', file=sys.stderr)
        return 130
    except (OSError, ValueError, subprocess.SubprocessError) as error:
        print('Private GUI runtime failed: ' + str(error), file=sys.stderr)
        return 1
    return 0


if __name__ == '__main__':
    raise SystemExit(main())
