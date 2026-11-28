"""System-Python entry point for the distro Xpra client, not the CyberLab venv."""

import json
import os
import sys


def probe():
    from xpra import __version__
    from xpra.net.rencodeplus import rencodeplus
    import gi

    major = int(__version__.split('.')[0])
    if not 3 <= major <= 6:
        raise RuntimeError('CyberLab supports Xpra 3 through 6; this version needs compatibility testing')
    gi.require_version('Gtk', '3.0')
    gi.require_foreign('cairo')
    from gi.repository import Gtk
    from PIL import Image
    if Gtk.get_major_version() != 3:
        raise RuntimeError('The Xpra client requires GTK3')
    Image.new('RGB', (1, 1)).close()
    return {'version': __version__, 'ready': callable(rencodeplus.dumps)}

def display_probe():
    import ctypes

    if not os.environ.get('DISPLAY'):
        return False
    library = ctypes.CDLL('libX11.so.6')
    library.XOpenDisplay.argtypes = [ctypes.c_char_p]
    library.XOpenDisplay.restype = ctypes.c_void_p
    library.XCloseDisplay.argtypes = [ctypes.c_void_p]
    display = library.XOpenDisplay(None)
    if not display:
        return False
    library.XCloseDisplay(display)
    return True


def compatible_hello(capabilities):
    result = dict(capabilities)
    def flatten(prefix, values):
        for name, value in values.items():
            key = prefix + '.' + name if name else prefix
            if isinstance(value, dict):
                flatten(key, value)
            else:
                result[key] = value
    for namespace in ('encodings', 'encoding', 'dpi', 'batch'):
        values = result.get(namespace)
        if isinstance(values, dict):
            del result[namespace]
            flatten(namespace, values)
    result.update(zlib=False, lz4=False, lzo=False, brotli=False)
    result['notify-startup-complete'] = True
    result['generic-rgb-encodings'] = True
    keymap = result.get('keymap')
    if isinstance(keymap, dict):
        for name, value in keymap.items():
            result['xkbmap_' + name] = value
    return result


def compatible_metadata(metadata):
    result = dict(metadata)
    for name in ('title', 'icon-title', 'client-machine'):
        if isinstance(result.get(name), bytes):
            result[name] = result[name].decode('utf-8', errors='replace')
    return result


def run(arguments):
    probe()
    compatible = '--cyberlab-compat' in arguments
    arguments = [value for value in arguments if value != '--cyberlab-compat']
    os.environ['XPRA_DELAY_KEYBOARD_DATA'] = '0'
    sys.stdout.flush()
    readiness = os.fdopen(os.dup(1), 'w')
    os.dup2(2, 1)
    from xpra.scripts import main
    from xpra.scripts.config import OPTION_TYPES

    for name in ('dbus-proxy', 'splash', 'reconnect'):
        if name not in OPTION_TYPES:
            arguments = [value for value in arguments if value != '--' + name + '=no']
    if 'dbus' in OPTION_TYPES:
        arguments.append('--dbus=no')

    make_client = main.make_client

    def tracked_client(*args, **kwargs):
        client = make_client(*args, **kwargs)
        make_hello = client.make_hello
        if compatible:
            client.make_hello = lambda: compatible_hello(make_hello())
        cook_metadata = client.cook_metadata
        if compatible:
            client.cook_metadata = lambda new, metadata: cook_metadata(new, compatible_metadata(metadata))
        startup_complete = client._process_startup_complete
        announced = False

        def ready(packet):
            nonlocal announced
            startup_complete(packet)
            if not announced:
                announced = True
                print('CYBERLAB_APPS_READY', file=readiness, flush=True)

        client._process_startup_complete = ready
        return client

    main.make_client = tracked_client
    return main.main(arguments[0], arguments)


if __name__ == '__main__':
    if sys.argv[1:] == ['--probe']:
        print(json.dumps(probe()))
    elif sys.argv[1:] == ['--display-probe']:
        print(json.dumps({'ready': display_probe()}))
    else:
        sys.exit(run(sys.argv[1:]))
