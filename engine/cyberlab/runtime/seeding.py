from io import BytesIO
import socket
import tarfile
from time import monotonic, sleep

from docker.errors import DockerException

from cyberlab.lab.assets import validate_seed

from . import RuntimeFailure
from .docker_terminal import close_stream

WORKSPACE = "/tmp/lab"
READY = "/tmp/.cyberlab-seeded"
BOOTSTRAP = (
    'umask 077; test ! -L /tmp/lab && /bin/mkdir -p -m 700 /tmp/lab && '
    'for entry in /tmp/lab/* /tmp/lab/.[!.]* /tmp/lab/..?*; do '
    'if [ -e "$entry" ] || [ -L "$entry" ]; then exit 73; fi; done && '
    '/bin/tar -xf - -C /tmp/lab && '
    '/bin/cat > /dev/null && '
    '/bin/touch /tmp/.cyberlab-seeded && exec "$@"'
)

def bootstrap_command(command, workspace=WORKSPACE):
    script = 'workspace=$1; shift; ' + BOOTSTRAP.replace(WORKSPACE, '"$workspace"')
    return ["/bin/sh", "-c", script, "cyberlab-seed", workspace, *command]

def seed_archive(entries, uid=65534, gid=65534):
    validate_seed(entries)
    buffer = BytesIO()
    with tarfile.open(fileobj=buffer, mode="w", format=tarfile.PAX_FORMAT) as archive:
        for entry in entries:
            info = tarfile.TarInfo(entry.path)
            info.uid, info.gid = uid, gid
            info.mtime = 0
            info.mode = 0o755 if entry.data is None else 0o644
            info.type = tarfile.DIRTYPE if entry.data is None else tarfile.REGTYPE
            info.size = len(entry.data) if entry.data is not None else 0
            archive.addfile(info, BytesIO(entry.data) if entry.data is not None else None)
    return buffer.getvalue()

def seed_container(container, archive, user="65534:65534"):
    stream = None
    try:
        stream = container.attach_socket(params={"stdin": 1, "stdout": 0, "stderr": 0, "stream": 1})
        connection = getattr(stream, "_sock", stream)
        connection.settimeout(10)
        connection.sendall(archive)
        connection.shutdown(socket.SHUT_WR)
        deadline = monotonic() + 10
        while monotonic() < deadline:
            result = container.exec_run(
                ["/bin/test", "-f", READY], user=user, privileged=False,
                stdout=False, stderr=False,
            )
            if result.exit_code == 0:
                return
            sleep(0.1)
        raise RuntimeFailure("Initial file setup timed out; Session cleanup is required")
    except (OSError, DockerException):
        raise RuntimeFailure("Cannot initialize node environment; verify the image account, UID/GID, home, shell, and required tools") from None
    finally:
        if stream is not None:
            close_stream(stream)
