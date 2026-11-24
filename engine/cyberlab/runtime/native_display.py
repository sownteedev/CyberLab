"""Daemon-owned native display leases, separate from Lab definitions/checkpoints."""

from contextlib import contextmanager, suppress
import json
import os
from pathlib import Path
import secrets
import stat
from time import monotonic
from threading import Event, Thread

from cyberlab.host_display import helper, checked_display as verify_display
from cyberlab.x11 import authority
from cyberlab import x11
from .display_relay import DisplayRelay


class NativeDisplays:
    def __init__(self, root=Path('/run/cyberlab/native'), clock=monotonic):
        self.root = root
        self.clock = clock
        self.contexts = {}
        self.nodes = {}

    @property
    def enabled(self):
        return x11.NATIVE_X11_ENABLED and self.root is not None

    def register(self, payload, uid, sender):
        if not self.enabled:
            raise ValueError(x11.NATIVE_X11_DISABLED_REASON)
        if self.root is None:
            raise ValueError('Native display support is disabled in this runtime')
        self.expire()
        if len(self.contexts) >= 16:
            raise ValueError('Too many pending desktop contexts')
        context = json.loads(payload)
        if isinstance(context, dict) and set(context) == {'fallback', 'requested_backend'}:
            if context['requested_backend'] not in ('auto', 'xpra') or not isinstance(context['fallback'], str) or len(context['fallback']) > 256:
                raise ValueError('Invalid display fallback')
            token = secrets.token_hex(32)
            self.contexts[token] = {**context, 'uid': uid, 'sender': sender, 'deadline': self.clock() + 30}
            return token
        if not isinstance(context, dict) or set(context) != {'display', 'login', 'cookie', 'authorization'}:
            raise ValueError('Invalid desktop context')
        if type(context['authorization']) is not int or not 0 < context['authorization'] < 2**32:
            raise ValueError('Invalid desktop authorization')
        authority(context['display'], context['cookie'])
        identity = verify_display(context['display'], context['login'], uid)
        helper({**context, 'operation': 'probe'}, uid)
        token = secrets.token_hex(32)
        self.contexts[token] = {**context, 'uid': uid, 'sender': sender, 'identity': identity,
                                'deadline': self.clock() + 30}
        return token

    def take(self, token, uid, sender):
        if not self.enabled:
            raise ValueError(x11.NATIVE_X11_DISABLED_REASON)
        self.expire()
        context = self.contexts.get(token)
        if context is None or (context['uid'], context['sender']) != (uid, sender):
            raise ValueError('Desktop context expired or belongs to another connection')
        self.contexts.pop(token)
        if 'cookie' not in context:
            return context
        try:
            if verify_display(context['display'], context['login'], uid) != context['identity']:
                raise ValueError('Desktop session changed')
        except Exception:
            self.revoke(context)
            raise
        return context

    @contextmanager
    def keepalive(self, context, interval=30):
        if not self.enabled or 'cookie' not in context:
            yield
            return
        stopped = Event()
        def probe():
            if verify_display(context['display'], context['login'], context['uid']) != context['identity']:
                raise ValueError('Desktop session changed')
            helper({**context, 'operation': 'probe'}, context['uid'])
        def maintain():
            while not stopped.wait(interval):
                try:
                    probe()
                except Exception:
                    return
        worker = None
        try:
            try:
                probe()
            except Exception:
                pass
            else:
                worker = Thread(target=maintain, name='cyberlab-display-lease', daemon=True)
                worker.start()
            yield
        finally:
            stopped.set()
            if worker is not None:
                worker.join(timeout=6)

    def revoke(self, context):
        if not self.enabled or 'cookie' not in context:
            return
        with suppress(Exception):
            if context.get('identity', {}).get('server') == 'Xwayland':
                if verify_display(context['display'], context['login'], context['uid']) != context['identity']:
                    return
            helper({**context, 'operation': 'revoke'}, context['uid'])

    def release(self, token, uid, sender):
        context = self.contexts.get(token)
        if context and (context['uid'], context['sender']) == (uid, sender):
            self.revoke(self.contexts.pop(token))
        return True

    def _root(self):
        if self.root is None:
            raise ValueError('Native display support is disabled')
        self.root.mkdir(mode=0o700, parents=True, exist_ok=True)
        info = self.root.lstat()
        if not stat.S_ISDIR(info.st_mode) or info.st_uid != os.geteuid() or info.st_mode & 0o077:
            raise ValueError('Unsafe native display state directory')

    def prepare(self, session, context):
        if not self.enabled:
            context = {'fallback': x11.NATIVE_X11_DISABLED_REASON, 'requested_backend': 'auto'}
        for node in session.lab.nodes:
            if not node.software.gui:
                continue
            key = (session.id, node.id)
            fallback = (context or {}).get('fallback', '')
            record = {'backend': 'xpra', 'requested_backend': 'native-x11' if context and 'cookie' in context else (context or {}).get('requested_backend', 'auto'),
                      'fallback_reason': fallback}
            self.nodes[key] = record
            if not context or 'cookie' not in context:
                continue
            generated = None
            directory = None
            relay = None
            phase = 'authorization'
            try:
                if verify_display(context['display'], context['login'], session.owner_uid) != context['identity']:
                    raise ValueError('Desktop session changed')
                generated = {**context, **helper({**context, 'operation': 'generate'}, session.owner_uid)}
                helper({**generated, 'operation': 'probe'}, session.owner_uid)
                self._root()
                directory = self.root / secrets.token_hex(24)
                directory.mkdir(mode=0o700)
                auth_file = directory / 'Xauthority'
                auth_file.write_bytes(authority(generated['display'], generated['cookie']))
                os.chmod(auth_file, 0o400)
                os.chown(auth_file, node.user.uid, node.user.gid)
                metadata = {name: generated[name] for name in ('display', 'login', 'cookie', 'authorization', 'uid', 'identity')}
                metadata.update(session=session.id, node=node.id)
                descriptor = os.open(directory / 'lease.json', os.O_WRONLY | os.O_CREAT | os.O_EXCL, 0o600)
                with os.fdopen(descriptor, 'w') as output:
                    json.dump(metadata, output)
                if context['identity'].get('server') == 'Xwayland':
                    phase = 'xwayland-relay'
                    relay = DisplayRelay(directory, generated, node.user.uid, node.user.gid)
                    record['relay'] = relay
                record.update(metadata, backend='native-x11', directory=directory, ready=True, fallback_reason='')
            except Exception:
                if relay:
                    relay.close()
                if generated:
                    self.revoke(generated)
                if directory:
                    self._delete(directory)
                record.update(backend='xpra', fallback_reason=f'Native X11 preparation failed [{phase}]; using Xpra')

    def options(self, session, node):
        if not self.enabled:
            return {}
        record = self.nodes.get((session.id, node.id), {})
        if record.get('backend') != 'native-x11':
            return {}
        from docker.types import Mount
        socket_path = record['identity']['socket']
        source = str(record['relay'].path) if record.get('relay') else socket_path
        return {'mounts': [Mount(socket_path, source, type='bind', read_only=True),
                           Mount('/run/cyberlab-native/Xauthority', str(record['directory'] / 'Xauthority'), type='bind', read_only=True)]}

    def environment(self, session, node):
        if not self.enabled:
            return {}
        record = self.nodes.get((session.id, node.id), {})
        if record.get('backend') == 'native-x11':
            if not record.get('ready'):
                return {}
            return {'DISPLAY': record['display'], 'XAUTHORITY': '/run/cyberlab-native/Xauthority'}
        return {'DISPLAY': ':99', 'XAUTHORITY': '/tmp/cyberlab-apps/Xauthority'}

    def verify_guest(self, runtime, session, node, container):
        if not self.enabled:
            return
        record = self.nodes.get((session.id, node.id), {})
        if record.get('backend') != 'native-x11':
            return
        from .workspace import execute
        program = ('import ctypes,sys; library=ctypes.CDLL("libX11.so.6"); '
                   'library.XOpenDisplay.argtypes=[ctypes.c_char_p]; library.XOpenDisplay.restype=ctypes.c_void_p; '
                   'library.XCloseDisplay.argtypes=[ctypes.c_void_p]; display=library.XOpenDisplay(None); '
                   'sys.exit(1) if not display else library.XCloseDisplay(display); '
                   'print("ready")')
        try:
            result = execute(runtime.client.api, container.id, node,
                             'exec /usr/bin/env DISPLAY="$1" XAUTHORITY="$2" /usr/bin/python3 -I -c "$3"',
                             [record['display'], '/run/cyberlab-native/Xauthority', program], maximum=32)
            if result.strip() != b'ready':
                raise ValueError('Guest X11 probe failed')
        except Exception:
            if record.get('relay'):
                record['relay'].stop()
            self.revoke(record)
            record.update(backend='xpra', ready=False, fallback_reason='Lab could not connect to its X11 display; using Xpra')

    def status(self, session, node_id):
        record = self.nodes.get((session.id, node_id))
        if record is None:
            return {}
        result = {name: record[name] for name in ('backend', 'requested_backend', 'fallback_reason')}
        if record['backend'] == 'native-x11':
            result.update(ready=record['ready'], attached=record['ready'], opening=False,
                          reconnectable=True, state='ready' if record['ready'] else 'disconnected',
                          display_server=record['identity'].get('server', 'Xorg'),
                          transport='private-x11-relay' if record.get('relay') else 'direct-socket')
        return result

    def reconnect(self, session, node_id, context):
        if not self.enabled:
            raise ValueError(x11.NATIVE_X11_DISABLED_REASON)
        record = self.nodes.get((session.id, node_id))
        if not record or record['backend'] != 'native-x11':
            raise ValueError('This machine has no native display mount')
        if record['identity'] != context['identity']:
            raise ValueError('X server changed; save, suspend and resume the Session to use this desktop')
        if record['ready']:
            return True
        generated = {**context, **helper({**context, 'operation': 'generate'}, session.owner_uid)}
        try:
            helper({**generated, 'operation': 'probe'}, session.owner_uid)
            if record.get('relay'):
                record['relay'].restart(generated)
            auth_file = record['directory'] / 'Xauthority'
            original = auth_file.lstat()
            if not stat.S_ISREG(original.st_mode) or original.st_nlink != 1:
                raise ValueError('Invalid node authorization file')
            os.chown(auth_file, os.geteuid(), os.getegid())
            try:
                os.chmod(auth_file, 0o600)
                descriptor = os.open(auth_file, os.O_WRONLY | os.O_TRUNC | os.O_NOFOLLOW)
                with os.fdopen(descriptor, 'wb') as output:
                    output.write(authority(generated['display'], generated['cookie']))
            finally:
                os.chmod(auth_file, 0o400)
                os.chown(auth_file, original.st_uid, original.st_gid)
            record.update({name: generated[name] for name in ('cookie', 'authorization', 'display', 'login', 'uid', 'identity')})
            metadata = {name: record[name] for name in ('cookie', 'authorization', 'display', 'login', 'uid', 'identity')}
            (record['directory'] / 'lease.json').write_text(json.dumps(metadata))
            record.update(ready=True, fallback_reason='')
            return True
        except Exception:
            if record.get('relay'):
                record['relay'].stop()
            self.revoke(generated)
            raise ValueError('Native display reconnect failed; Session is kept') from None

    def expire(self):
        for token, context in tuple(self.contexts.items()):
            if self.clock() >= context['deadline']:
                self.revoke(self.contexts.pop(token))

    def poll(self):
        self.expire()
        if not self.enabled:
            return
        for record in self.nodes.values():
            if record['backend'] != 'native-x11' or not record.get('ready'):
                continue
            try:
                if record.get('relay') and not record['relay'].alive:
                    raise ValueError('XWayland relay stopped')
                if verify_display(record['display'], record['login'], record['uid']) != record['identity']:
                    raise ValueError('Desktop session changed')
                helper({**record, 'operation': 'probe', 'directory': str(record['directory'])}, record['uid'])
            except Exception:
                if record.get('relay'):
                    record['relay'].stop()
                self.revoke(record)
                record.update(ready=False, fallback_reason='Native display disconnected; save and resume to authorize the current desktop')

    def _delete(self, directory):
        for name in ('Xauthority', 'lease.json', 'Xsocket'):
            with suppress(FileNotFoundError):
                (directory / name).unlink()
        with suppress(FileNotFoundError):
            directory.rmdir()

    def remove(self, session_id=None):
        for key, record in tuple(self.nodes.items()):
            if session_id is None or key[0] == session_id:
                self.nodes.pop(key)
                if record.get('relay'):
                    record['relay'].close()
                if 'directory' in record:
                    self.revoke(record)
                    self._delete(record['directory'])

    def cleanup(self):
        self.remove()
        if self.root is None or not self.root.exists():
            return
        self._root()
        for directory in self.root.iterdir():
            if directory.is_symlink() or not directory.is_dir():
                continue
            try:
                record = json.loads((directory / 'lease.json').read_text())
                self.revoke(record)
                self._delete(directory)
            except (OSError, ValueError):
                continue
