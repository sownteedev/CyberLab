from hashlib import sha256
import socket
from time import monotonic, sleep

from docker.errors import DockerException

from cyberlab.imports import import_path, validate_import
from cyberlab.lab.environment import runtime_user, workspace

from . import RuntimeFailure
from .docker_terminal import close_stream

IMPORT_SCRIPT = '''
set -eC
umask 077
test ! -L "$4"
/bin/mkdir -p -m 700 "$4"
exec 4< "$4"
test -d /proc/self/fd/4
test "$(/bin/readlink /proc/self/fd/4)" = "$4"
if [ -e "$1" ] || [ -L "$1" ]; then exit 73; fi
exec 3> "/proc/self/fd/4/${1##*/}"
test -f /proc/self/fd/3
test "$(/bin/readlink /proc/self/fd/3)" = "$1"
/bin/cat >&3
test "$(/bin/wc -c < /proc/self/fd/3)" -eq "$2"
checksum=$(/bin/sha256sum /proc/self/fd/3)
test "${checksum%% *}" = "$3"
test "$(/bin/readlink /proc/self/fd/3)" = "$1"
'''

def transfer_file(api, container_id, node, record, data):
    validate_import(record.name, data)
    if record.node != node.id or record.path != import_path(node, record.id, record.name) or record.size != len(data) or record.sha256 != sha256(data).hexdigest():
        raise ValueError("Invalid import record")
    stream = None
    try:
        execution = api.exec_create(
            container_id,
            cmd=["/bin/timeout", "-s", "KILL", "15", "/bin/sh", "-c", IMPORT_SCRIPT,
                 "cyberlab-import", record.path, str(record.size), record.sha256, workspace(node)],
            stdin=True, stdout=False, stderr=False, tty=False, privileged=False,
            user=runtime_user(node), workdir=node.user.home if node.user else "/tmp",
            environment={"ENV": "/dev/null", "BASH_ENV": "/dev/null", "LC_ALL": "C"},
        )
        stream = api.exec_start(execution["Id"], tty=False, socket=True)
        connection = getattr(stream, "_sock", stream)
        connection.settimeout(10)
        connection.sendall(data)
        connection.shutdown(socket.SHUT_WR)
        deadline = monotonic() + 20
        while monotonic() < deadline:
            state = api.exec_inspect(execution["Id"])
            if not state["Running"]:
                if state.get("ExitCode") == 0:
                    return
                raise RuntimeFailure("Import failed: destination, image tools, disk space, or integrity check; inspect imports before retrying")
            sleep(0.1)
        raise RuntimeFailure("Import timed out; a partial file may remain until reset or stop")
    except (DockerException, OSError):
        raise RuntimeFailure("Cannot transfer file; inspect imports before retrying") from None
    finally:
        if stream is not None:
            close_stream(stream)
