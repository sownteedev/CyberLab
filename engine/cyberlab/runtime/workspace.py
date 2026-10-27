import socket
from time import monotonic, sleep

from docker.errors import DockerException

from cyberlab.lab.environment import runtime_user, workspace
from cyberlab.workspace import MAX_ARCHIVE, MAX_UPLOAD_CONTENT, Entry, folder_name, make_archive, read_archive

from . import RuntimeFailure
from .docker_terminal import close_stream

READ_SCRIPT = '''
set -eu
test ! -L "$1"
if [ ! -e "$1" ]; then /bin/tar -cf - -T /dev/null; exit; fi
exec 3< "$1"
test -d /proc/self/fd/3
test "$(/bin/readlink /proc/self/fd/3)" = "$1"
/bin/tar -cf - -C /proc/self/fd/3 .
test "$(/bin/readlink /proc/self/fd/3)" = "$1"
'''

IMPORT_SCRIPT = '''
set -eu
umask 077
test ! -L "$1"
/bin/mkdir -p "$1"
exec 3< "$1"
test -d /proc/self/fd/3
test "$(/bin/readlink /proc/self/fd/3)" = "$1"
cd /proc/self/fd/3
/bin/mkdir -m 700 -- "$2"
exec 4< "$2"
test "$(/bin/readlink /proc/self/fd/4)" = "$1/$2"
/bin/tar -xf - -C /proc/self/fd/4
test "$(/bin/readlink /proc/self/fd/3)" = "$1"
test "$(/bin/readlink /proc/self/fd/4)" = "$1/$2"
'''


def execute(api, container_id, node, script, arguments, data=None, maximum=MAX_ARCHIVE):
    stream = None
    output = bytearray()
    errors = bytearray()
    deadline = monotonic() + 25
    try:
        execution = api.exec_create(
            container_id,
            cmd=["/bin/timeout", "-s", "KILL", "20", "/bin/sh", "-c", script, "cyberlab-workspace", *arguments],
            stdin=data is not None, stdout=True, stderr=True, tty=False, privileged=False,
            user=runtime_user(node), workdir="/tmp",
            environment={"ENV": "/dev/null", "BASH_ENV": "/dev/null", "LC_ALL": "C"},
        )
        stream = api.exec_start(execution["Id"], tty=False, socket=True)
        connection = getattr(stream, "_sock", stream)
        connection.settimeout(10)
        if data is not None:
            connection.sendall(data)
            connection.shutdown(socket.SHUT_WR)

        def receive(size, eof=False):
            received = bytearray()
            while len(received) < size:
                remaining = deadline - monotonic()
                if remaining <= 0:
                    raise RuntimeFailure("Workspace transfer timed out")
                connection.settimeout(min(remaining, 10))
                chunk = connection.recv(min(size - len(received), 65536))
                if not chunk:
                    if eof and not received:
                        return b""
                    raise RuntimeFailure("Workspace transfer ended unexpectedly")
                received.extend(chunk)
            return bytes(received)

        while header := receive(8, eof=True):
            if header[0] not in {1, 2} or header[1:4] != b"\0\0\0":
                raise RuntimeFailure("Invalid workspace transfer response")
            length = int.from_bytes(header[4:], "big")
            target, limit = (output, maximum) if header[0] == 1 else (errors, 4096)
            if len(target) + length > limit:
                raise RuntimeFailure("Workspace transfer exceeds its size limit")
            target.extend(receive(length))
        while monotonic() < deadline:
            state = api.exec_inspect(execution["Id"])
            if not state["Running"]:
                if state.get("ExitCode") != 0:
                    raise RuntimeFailure("Workspace transfer failed; check permissions, destination collisions and image tools. A partial import may remain.")
                return bytes(output)
            sleep(0.05)
        raise RuntimeFailure("Workspace transfer timed out")
    except (DockerException, OSError):
        raise RuntimeFailure("Cannot transfer workspace data; check the Session and retry only after inspecting its files") from None
    finally:
        if stream is not None:
            close_stream(stream)


def snapshot(api, container_id, node):
    data = execute(api, container_id, node, READ_SCRIPT, [workspace(node)])
    try:
        return read_archive(data, unsafe=True)
    except ValueError as error:
        raise RuntimeFailure(str(error)) from None


def import_folder(api, container_id, node, name, entries):
    folder_name(name)
    contents = sum(entry.size for entry in entries)
    if contents > MAX_UPLOAD_CONTENT:
        raise ValueError("Folder import exceeds its content-size limit")
    normalized = tuple(Entry(entry.path, entry.kind, entry.data, 0o700 if entry.kind == "directory" else 0o600) for entry in entries)
    archive = make_archive(normalized)
    execute(api, container_id, node, IMPORT_SCRIPT, [workspace(node), name], archive, maximum=4096)
