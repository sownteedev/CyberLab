"""Identify an owner-bound Xwayland server, including compositor-owned listeners."""

from pathlib import Path
import stat


class DisplayNotReady(ValueError):
    pass


def process_state(process, uid):
    directory = Path(f'/proc/{process}')
    if directory.stat().st_uid != uid:
        raise ValueError('Xwayland must belong to the desktop user')
    fields = (directory / 'stat').read_text().rsplit(')', 1)[1].split()
    return {'parent': int(fields[1]), 'start_time': fields[19]}


def descendants(process, uid):
    pending = [(process, 0)]
    seen = set()
    while pending and len(seen) < 256:
        candidate, depth = pending.pop(0)
        if candidate in seen:
            continue
        seen.add(candidate)
        try:
            state = process_state(candidate, uid)
            yield candidate, state
            if depth < 8:
                directory = Path(f'/proc/{candidate}/task')
                for task in directory.iterdir():
                    children = (task / 'children').read_text().split()
                    pending.extend((int(child), depth + 1) for child in children)
        except (OSError, ValueError):
            continue


def listener_inodes(endpoint):
    entries = Path('/proc/net/unix').read_text().splitlines()[1:]
    return {fields[6] for line in entries if len(fields := line.split()) == 8
            and fields[7] == str(endpoint) and fields[3:6] == ['00010000', '0001', '01']}


def owns_listener(process, inodes):
    targets = {f'socket:[{inode}]' for inode in inodes}
    try:
        for descriptor in Path(f'/proc/{process}/fd').iterdir():
            try:
                if descriptor.readlink().as_posix() in targets:
                    return True
            except OSError:
                continue
    except OSError:
        pass
    return False


def server_candidates(peer, uid):
    seen = set()
    for process, state in descendants(peer, uid):
        seen.add(process)
        yield process, state
    for index, directory in enumerate(Path('/proc').iterdir()):
        if index >= 8192:
            break
        if not directory.name.isdecimal() or int(directory.name) in seen:
            continue
        try:
            if directory.stat().st_uid == uid and (directory / 'exe').resolve(strict=True).name == 'Xwayland':
                yield int(directory.name), process_state(int(directory.name), uid)
        except (OSError, ValueError):
            continue


def verified_server(endpoint, peer, uid):
    peer_state = process_state(peer, uid)
    inodes = listener_inodes(endpoint)
    if not inodes or not owns_listener(peer, inodes):
        raise ValueError('Xwayland listener ownership could not be verified')
    for process, state in server_candidates(peer, uid):
        try:
            executable = Path(f'/proc/{process}/exe').resolve(strict=True)
            info = executable.stat()
            if executable not in (Path('/usr/bin/Xwayland'), Path('/usr/lib/xorg/Xwayland')):
                continue
            if not stat.S_ISREG(info.st_mode) or info.st_uid != 0 or info.st_mode & 0o022:
                continue
            if not owns_listener(process, inodes):
                continue
            if process_state(process, uid) != state or process_state(peer, uid) != peer_state:
                raise ValueError('Xwayland process changed')
            return {'process': process, 'start_time': state['start_time'], 'server': 'Xwayland',
                    'peer': peer, 'peer_start_time': peer_state['start_time']}
        except OSError:
            continue
    raise DisplayNotReady('Display is not a verified local Xwayland server')
