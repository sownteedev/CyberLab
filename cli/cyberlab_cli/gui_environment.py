"""Local graphical capability checks, independent of the daemon and DE/WM."""

import json
import os
from pathlib import Path
import subprocess
from cyberlab import x11


def probe(option):
    try:
        result = subprocess.run(['/usr/bin/python3', '-I', str(Path(__file__).with_name('xpra_client.py')), option],
                                capture_output=True, text=True, timeout=8)
        value = json.loads(result.stdout) if result.returncode == 0 else {}
        return value if isinstance(value, dict) else {}
    except (OSError, ValueError, subprocess.TimeoutExpired):
        return {}


def inspect_environment(force_xpra=False):
    from .gui_preferences import preference
    from cyberlab.host_display import helper, login_session, verify_display

    selected = preference()
    wayland = bool(os.environ.get('WAYLAND_DISPLAY')) or os.environ.get('XDG_SESSION_TYPE') == 'wayland'
    report = {'ready': False, 'backend': 'xpra', 'session_type': 'wayland' if wayland else 'x11' if os.environ.get('DISPLAY') else 'headless',
              'display_ready': False, 'client_ready': False, 'code': '', 'message': ''}
    if os.geteuid() == 0:
        report.update(code='desktop-user-required', message='Run CyberLab as your normal desktop user, not root. Terminal practice is unaffected.')
        return report
    report.update(preferred=selected['preferred'], warning=selected['warning'], native_ready=False, fallback_reason='')
    login = os.environ.get('XDG_SESSION_ID', 'self')
    try:
        properties = login_session(login, os.getuid())
        login = properties['Id']
        wayland = wayland or properties['Type'] == 'wayland'
        if wayland:
            report['session_type'] = 'wayland'
        if not force_xpra and selected['preferred'] == 'auto' and os.environ.get('DISPLAY') and x11.NATIVE_X11_ENABLED:
            identity = verify_display(os.environ['DISPLAY'], login, os.getuid())
            if wayland and identity.get('server') != 'Xwayland':
                raise ValueError('The Wayland display is not a verified Xwayland server')
            helper({'display': os.environ['DISPLAY'], 'operation': 'probe'})
            report.update(ready=True, backend='native-x11', native_ready=True, display_ready=True,
                          client_ready=True, code='ready', login=login,
                          display_server='Xwayland' if wayland else 'Xorg',
                          message='Direct XWayland is available. Lab applications share access to this X server.' if wayland else
                          'Native X11 is available. Lab applications share access to this X server.')
            return report
    except Exception:
        if not force_xpra and selected['preferred'] == 'auto' and report['session_type'] in ('x11', 'wayland'):
            report['fallback_reason'] = ('Direct XWayland' if wayland else 'Native X11') + ' could not be verified; using Xpra when available'
    if not force_xpra and selected['preferred'] == 'auto' and report['session_type'] in ('x11', 'wayland') and not x11.NATIVE_X11_ENABLED:
        report['fallback_reason'] = x11.NATIVE_X11_DISABLED_REASON
    executable = Path('/usr/bin/xpra')
    if not executable.is_file() or not os.access(executable, os.X_OK):
        report.update(code='xpra-missing', message='The host needs the xpra package for application windows. The CyberLab installer can prepare it; terminal practice still works.')
        return report
    package = probe('--probe')
    report['client_ready'] = package.get('ready') is True
    report['version'] = package.get('version', '')
    if not report['client_ready']:
        report.update(code='xpra-incompatible', message='The host Xpra client needs GTK3, rencodeplus and a supported version (3-6). Check CyberLab dependencies; Session is kept.')
        return report
    if report['session_type'] == 'headless':
        report.update(code='headless', message='No graphical session is available. Open CyberLab from your Linux desktop; CLI/headless practice still works.')
        return report
    report['display_ready'] = probe('--display-probe').get('ready') is True
    if not report['display_ready']:
        if wayland:
            report.update(code='xwayland-unavailable', message='The Wayland session cannot open an X11 display for Xpra. Enable XWayland in your compositor (xwayland-satellite on Niri), then reopen CyberLab from the desktop launcher. Do not change to an X11 desktop.')
        else:
            report.update(code='x11-unavailable', message='CyberLab cannot connect to this X11 session. Reopen it from the desktop launcher as the desktop user; do not use sudo or xhost +.')
        return report
    report.update(ready=True, code='ready', message='Application windows are available via XWayland.' if wayland else 'Application windows are available via X11.')
    return report
