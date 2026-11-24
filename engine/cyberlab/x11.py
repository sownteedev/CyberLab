"""Bounded, unprivileged X SECURITY helper. Credentials travel only on stdin/stdout."""

import ctypes
import json
import os
import re
import struct
import sys

NATIVE_X11_ENABLED = True
NATIVE_X11_DISABLED_REASON = 'Native X11 is unavailable; using Xpra when available'


def require_disposable_server(payload):
    import socket
    import stat
    from pathlib import Path

    fixture = payload.get('_fixture')
    if not isinstance(fixture, dict) or set(fixture) != {'pid', 'start_time'}:
        raise ValueError(NATIVE_X11_DISABLED_REASON)
    process = fixture['pid']
    if type(process) is not int or process <= 0:
        raise ValueError('Invalid disposable display process')
    directory = Path(f'/proc/{process}')
    fields = (directory / 'stat').read_text().rsplit(')', 1)[1].split()
    if directory.stat().st_uid != os.getuid() or int(fields[1]) != os.getppid() or fields[19] != fixture['start_time']:
        raise ValueError('Display is not a child of the isolated test runner')
    if (directory / 'exe').resolve().name not in ('Xvfb', 'Xwayland'):
        raise ValueError('Only a disposable Xvfb or Xwayland server may exercise X SECURITY')
    endpoint = Path('/tmp/.X11-unix') / ('X' + display_number(payload['display']))
    info = endpoint.lstat()
    if not stat.S_ISSOCK(info.st_mode) or info.st_uid != os.getuid():
        raise ValueError('Invalid disposable display socket')
    with socket.socket(socket.AF_UNIX) as connection:
        connection.settimeout(1)
        connection.connect(str(endpoint))
        peer, owner, _group = struct.unpack('3i', connection.getsockopt(socket.SOL_SOCKET, socket.SO_PEERCRED, 12))
    if owner != os.getuid():
        raise ValueError('Display socket does not belong to the disposable server')
    if peer != process:
        if peer != os.getppid() or (directory / 'exe').resolve().name != 'Xwayland':
            raise ValueError('Display listener does not belong to the fixture runner')
        sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
        from cyberlab.xwayland import verified_server
        if verified_server(endpoint, peer, owner)['process'] != process:
            raise ValueError('Display listener was not inherited by the disposable server')


def display_number(display):
    match = re.fullmatch(r':(0|[1-9][0-9]{0,3})(?:\.([0-9]{1,2}))?', display)
    if not match:
        raise ValueError('Only local X11 displays are supported')
    return match.group(1)


def authority(display, cookie):
    data = bytes.fromhex(cookie)
    if len(data) != 16:
        raise ValueError('Invalid X11 authorization')
    fields = (b'', display_number(display).encode(), b'MIT-MAGIC-COOKIE-1', data)
    return struct.pack('!H', 65535) + b''.join(struct.pack('!H', len(field)) + field for field in fields)


class Xauth(ctypes.Structure):
    _fields_ = [('family', ctypes.c_ushort), ('address_length', ctypes.c_ushort), ('address', ctypes.c_void_p),
                ('number_length', ctypes.c_ushort), ('number', ctypes.c_void_p),
                ('name_length', ctypes.c_ushort), ('name', ctypes.c_void_p),
                ('data_length', ctypes.c_ushort), ('data', ctypes.c_void_p)]


class Attributes(ctypes.Structure):
    _fields_ = [('timeout', ctypes.c_uint), ('trust_level', ctypes.c_uint),
                ('group', ctypes.c_ulong), ('event_mask', ctypes.c_long)]


def generate_authorization(library, extension, display, errors, timeout):
    protocol = ctypes.create_string_buffer(b'MIT-MAGIC-COOKIE-1')
    source = Xauth()
    source.name_length = 18
    source.name = ctypes.cast(protocol, ctypes.c_void_p)
    attributes = Attributes(timeout, 0, 0, 0)
    identifier = ctypes.c_ulong()
    generated = extension.XSecurityGenerateAuthorization(display, ctypes.byref(source), 3,
                                                          ctypes.byref(attributes), ctypes.byref(identifier))
    library.XSync(display, 0)
    if not generated:
        raise ValueError('Cannot create a revocable X11 authorization')
    try:
        if errors or generated.contents.data_length != 16 or not identifier.value:
            raise ValueError('Unsupported X11 authorization')
        return {'cookie': ctypes.string_at(generated.contents.data, 16).hex(), 'authorization': identifier.value}
    finally:
        extension.XSecurityFreeXauth(generated)


def revoke_from_controller(library, extension, display, display_name, identifier, errors):
    """Never revoke the authorization of the connection sending the request."""
    controller = None
    try:
        temporary = generate_authorization(library, extension, display, errors, timeout=2)
        if temporary['authorization'] == identifier:
            raise ValueError('Cleanup authorization must differ from its target')
        library.XSetAuthorization(b'MIT-MAGIC-COOKIE-1', 18, bytes.fromhex(temporary['cookie']), 16)
        controller = library.XOpenDisplay(display_name.encode())
        if not controller:
            raise ValueError('Cannot authenticate the temporary X11 cleanup connection')
        major, minor = ctypes.c_int(), ctypes.c_int()
        if not extension.XSecurityQueryExtension(controller, ctypes.byref(major), ctypes.byref(minor)):
            raise ValueError('Cleanup connection cannot use X11 SECURITY')
        library.XCloseDisplay(display)
        display = None
        extension.XSecurityRevokeAuthorization(controller, identifier)
        library.XSync(controller, 0)
        if errors:
            raise ValueError('Cannot revoke X11 authorization')
    finally:
        if display:
            library.XCloseDisplay(display)
        if controller:
            library.XCloseDisplay(controller)


def operate(payload):
    if os.geteuid() == 0:
        raise ValueError('X11 operations must run as the desktop user')
    operation = payload.get('operation', 'probe')
    if operation not in ('identity', 'probe', 'generate', 'revoke'):
        raise ValueError('Invalid X11 operation')
    if (operation in ('generate', 'revoke') and not NATIVE_X11_ENABLED) or '_fixture' in payload:
        require_disposable_server(payload)
    display_name = payload['display']
    display_number(display_name)
    if payload.get('operation') == 'identity':
        from pathlib import Path
        sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
        from cyberlab.host_display import verify_display
        return verify_display(display_name, payload['login'], os.getuid())
    descriptor = None
    if payload.get('cookie'):
        descriptor = os.memfd_create('cyberlab-xauth', os.MFD_CLOEXEC)
        os.write(descriptor, authority(display_name, payload['cookie']))
        os.environ['XAUTHORITY'] = '/proc/self/fd/' + str(descriptor)
    library = ctypes.CDLL('libX11.so.6')
    extension = ctypes.CDLL('libXext.so.6')
    library.XOpenDisplay.argtypes = [ctypes.c_char_p]
    library.XOpenDisplay.restype = ctypes.c_void_p
    library.XCloseDisplay.argtypes = [ctypes.c_void_p]
    library.XSetAuthorization.argtypes = [ctypes.c_char_p, ctypes.c_int, ctypes.c_char_p, ctypes.c_int]
    if payload.get('cookie'):
        library.XSetAuthorization(b'MIT-MAGIC-COOKIE-1', 18, bytes.fromhex(payload['cookie']), 16)
    library.XSync.argtypes = [ctypes.c_void_p, ctypes.c_int]
    errors = []
    handler_type = ctypes.CFUNCTYPE(ctypes.c_int, ctypes.c_void_p, ctypes.c_void_p)
    handler = handler_type(lambda *_args: errors.append(True) or 0)
    library.XSetErrorHandler.argtypes = [handler_type]
    library.XSetErrorHandler(handler)
    extension.XSecurityQueryExtension.argtypes = [ctypes.c_void_p, ctypes.POINTER(ctypes.c_int), ctypes.POINTER(ctypes.c_int)]
    extension.XSecurityGenerateAuthorization.argtypes = [ctypes.c_void_p, ctypes.POINTER(Xauth), ctypes.c_ulong,
                                                         ctypes.POINTER(Attributes), ctypes.POINTER(ctypes.c_ulong)]
    extension.XSecurityGenerateAuthorization.restype = ctypes.POINTER(Xauth)
    extension.XSecurityFreeXauth.argtypes = [ctypes.POINTER(Xauth)]
    extension.XSecurityRevokeAuthorization.argtypes = [ctypes.c_void_p, ctypes.c_ulong]
    display = library.XOpenDisplay(display_name.encode())
    try:
        if not display:
            raise ValueError('Cannot connect to the local X11 display')
        major, minor = ctypes.c_int(), ctypes.c_int()
        if not extension.XSecurityQueryExtension(display, ctypes.byref(major), ctypes.byref(minor)):
            raise ValueError('X11 SECURITY extension is unavailable')
        operation = payload.get('operation', 'probe')
        if operation == 'generate':
            return generate_authorization(library, extension, display, errors, timeout=120)
        if operation == 'revoke':
            identifier = payload.get('authorization')
            if type(identifier) is not int or not 0 < identifier < 2**32:
                raise ValueError('Invalid revocation target')
            original, display = display, None
            revoke_from_controller(library, extension, original, display_name, identifier, errors)
        elif operation != 'probe':
            raise ValueError('Invalid X11 operation')
        return {'ready': True}
    finally:
        if display:
            library.XCloseDisplay(display)
        if descriptor is not None:
            os.close(descriptor)


if __name__ == '__main__':
    try:
        incoming = sys.stdin.buffer.read(4097)
        if len(incoming) > 4096:
            raise ValueError('Oversized request')
        print(json.dumps(operate(json.loads(incoming))))
    except Exception:
        print(json.dumps({'error': 'X11 authorization operation failed'}))
        sys.exit(1)
