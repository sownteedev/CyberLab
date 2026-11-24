"""Native window acceptance helper; invoked only by the disposable software fixture."""
import asyncio
import json
import os
from pathlib import Path
import pwd
import subprocess
import sys
import tempfile
from time import monotonic
from unittest.mock import patch
from uuid import uuid4

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / 'cli'))
from cyberlab_cli import desktop as client

async def verify_gui(engine, runtime, session, uid, display, terminal_command):
    account = pwd.getpwuid(uid)
    title = 'CyberLabAcceptance-' + uuid4().hex
    original = client.viewer_command
    def viewer(executable, endpoint, credential, node):
        for path in (endpoint.parent, endpoint, credential):
            os.chown(path, uid, account.pw_gid)
        return ['/usr/bin/runuser', '-u', account.pw_name, '--', *original(executable, endpoint, credential, node)]
    async def request(bus, operation, body):
        if operation == 'GetDesktopStatus':
            return json.dumps(await asyncio.to_thread(engine.desktop_status, body[0], body[1], uid))
        if operation == 'OpenDesktop':
            return await asyncio.to_thread(engine.open_desktop, body[0], body[1], uid, ':software-gui-fixture')
        operations = {'ConfirmDesktop': 'ready', 'ReadDesktop': 'read', 'WriteDesktop': 'write', 'CloseDesktop': 'close'}
        return await asyncio.to_thread(engine.desktop, operations[operation], body[0], uid, ':software-gui-fixture', *body[1:])
    environment = dict(os.environ, DISPLAY=display, XDG_RUNTIME_DIR=f'/run/user/{uid}', HOME=account.pw_dir, GDK_BACKEND='x11')
    environment.pop('XAUTHORITY', None)
    environment.pop('WAYLAND_DISPLAY', None)
    probe = '''import sys, json, gi
sys.path.insert(0, sys.argv[1])
from check_seamless_apps import window_names
gi.require_version('Gdk', '3.0')
gi.require_version('GdkX11', '3.0')
from gi.repository import Gdk, GdkX11
Gdk.init([])
display = Gdk.Display.get_default()
result = []
for identifier, title in window_names(sys.argv[2], with_ids=True):
    if '[CyberLab: client]' not in title or sys.argv[3] not in title: continue
    window = GdkX11.X11Window.foreign_new_for_display(display, identifier)
    width, height = window.get_width(), window.get_height()
    image = Gdk.pixbuf_get_from_window(window, 0, 0, width, height)
    if image is None: continue
    if len(sys.argv) > 4:
        image.savev(sys.argv[4] + '/' + str(identifier) + '.png', 'png', [], [])
    pixels, channels = image.get_pixels(), image.get_n_channels()
    colors = {pixels[index:index+3] for index in range(0, len(pixels)-3, channels*17)}
    result.append({'title': title, 'colors': len(colors), 'width': width, 'height': height})
print(json.dumps(result))
'''
    attachment = None
    viewer_log = tempfile.TemporaryFile()
    original_spawn = asyncio.create_subprocess_exec
    async def spawn(*command, **options):
        options['stderr'] = viewer_log
        return await original_spawn(*command, **options)
    def diagnostics():
        viewer_log.seek(max(0, os.fstat(viewer_log.fileno()).st_size - 16000))
        for line in viewer_log.read().decode(errors='replace').splitlines():
            if not any(word in line.lower() for word in ('auth', 'password', 'token', 'challenge', 'credential')):
                print('Viewer:', line[:600], file=sys.stderr, flush=True)
    async def wait_ready():
        for attempt in range(300):
            if attachment.done():
                try:
                    attachment.result()
                finally:
                    diagnostics()
                raise AssertionError('Native display client exited before ready')
            state = await request(None, 'GetDesktopStatus', [session.id, 'client'])
            if json.loads(state)['attached']:
                return
            await asyncio.sleep(.1)
        raise AssertionError('Native display handshake timed out')
    async def wait_windows(expected_title=None):
        for attempt in range(120):
            if attachment.done():
                try:
                    attachment.result()
                finally:
                    diagnostics()
                raise AssertionError('Native display client exited during application check')
            result = await asyncio.to_thread(subprocess.run,
                ['/usr/bin/runuser', '-u', account.pw_name, '--', '/usr/bin/python3', '-I', '-c', probe,
                 str(Path(__file__).resolve().parent), display, title],
                env=environment, capture_output=True, text=True, timeout=8)
            windows = json.loads(result.stdout) if result.returncode == 0 else []
            matched = [window for window in windows if title in window['title']]
            if (len(matched) >= 2 and all(window['colors'] > 32 for window in matched)
                    and (expected_title is None or any(expected_title in window['title'] for window in matched))):
                return matched
            await asyncio.sleep(.2)
        diagnostics()
        screenshots = tempfile.mkdtemp(prefix='cyberlab-gui-diagnostic-', dir='/var/tmp')
        os.chown(screenshots, uid, account.pw_gid)
        await asyncio.to_thread(subprocess.run,
            ['/usr/bin/runuser', '-u', account.pw_name, '--', '/usr/bin/python3', '-I', '-c', probe,
             str(Path(__file__).resolve().parent), display, title, screenshots],
            env=environment, capture_output=True, text=True, timeout=8)
        print('Fixture screenshots:', screenshots, flush=True)
        print('Window probe:', result.returncode, result.stdout[-2000:], result.stderr[-2000:], flush=True)
        all_windows = await asyncio.to_thread(subprocess.run,
            ['/usr/bin/runuser', '-u', account.pw_name, '--', '/usr/bin/python3', '-I', '-c',
             'import sys; sys.path.insert(0, sys.argv[1]); from check_seamless_apps import window_names; print(window_names(sys.argv[2]))',
             str(Path(__file__).resolve().parent), display],
            env=environment, capture_output=True, text=True, timeout=8)
        print('All host windows:', all_windows.stdout[-4000:], all_windows.stderr[-2000:], flush=True)
        xwininfo = await asyncio.to_thread(subprocess.run,
            ['/usr/bin/xprop', '-root', '_NET_CLIENT_LIST'], env=environment,
            capture_output=True, text=True, timeout=8)
        print('Host client list:', xwininfo.stdout[-2000:], xwininfo.stderr[-1000:], flush=True)
        raise AssertionError('Firefox and Wireshark did not both paint on the host display')
    async def command(script):
        return await asyncio.to_thread(terminal_command, runtime, session, script)
    try:
        with patch.dict(os.environ, environment, clear=True), patch.object(client, 'viewer_command', viewer), patch.object(asyncio, 'create_subprocess_exec', spawn):
            attachment = asyncio.create_task(client.interact(None, request, session.id, 'client'))
            await wait_ready()
            await command('cp /home/learner/fixture.pcap /home/learner/' + title + '.pcap; '
                          'printf \'<title>' + title + '</title><h1>CyberLab Firefox</h1><input accesskey="i" autofocus oninput="document.title=this.value"><div style="height:5000px">Scroll test</div>\' > /home/learner/gui-fixture.html')
            started = monotonic()
            await command('mkdir -p /home/learner/firefox-gui-fixture; '
                          'printf \'%s\\n\' \'user_pref("browser.aboutwelcome.enabled", false);\' '
                          '\'user_pref("datareporting.policy.dataSubmissionPolicyBypassNotification", true);\' '
                          '\'user_pref("datareporting.healthreport.uploadEnabled", false);\' '
                          '\'user_pref("telemetry.fog.test.localhost_port", -1);\' '
                          '> /home/learner/firefox-gui-fixture/user.js; '
                          'firefox --new-instance --profile /home/learner/firefox-gui-fixture file:///home/learner/gui-fixture.html >/tmp/firefox-gui.log 2>&1 & '
                          'wireshark -r /home/learner/' + title + '.pcap >/tmp/wireshark-gui.log 2>&1 & disown -a; sleep 1')
            windows = await wait_windows()
            print(f'PASS: Firefox + Wireshark painted native host windows in {monotonic() - started:.1f}s', flush=True)
            for size in ('900 650', '1100 750', '900 650'):
                await command('for window in $(xdotool search --onlyvisible --name ' + title + '); do xdotool windowsize "$window" ' + size + '; done')
                await wait_windows()
            print('PASS: repeated resize keeps both host application windows painted', flush=True)
            attachment.cancel()
            await asyncio.gather(attachment, return_exceptions=True)
            attachment = asyncio.create_task(client.interact(None, request, session.id, 'client'))
            await wait_ready()
            await wait_windows()
            print('PASS: both existing guest windows return after native-client reconnect', flush=True)
            await command('window=$(xdotool search --onlyvisible --name "' + title + '.*Mozilla Firefox" | head -1); '
                          'test -n "$window" && xdotool windowfocus --sync "$window" && '
                          'xdotool key --clearmodifiers alt+shift+i && '
                          'xdotool type --clearmodifiers ' + title + '-typed')
            windows = await wait_windows(title + '-typed')
            assert any(title + '-typed' in window['title'] for window in windows), 'Firefox input did not update fixture page'
            print('PASS: Firefox fixture page receives text input', flush=True)
    except Exception:
        diagnostics()
        container = runtime._workspace_container(session, session.lab.nodes[0])
        result = await asyncio.to_thread(container.exec_run,
            ['/bin/sh', '-c', 'tail -c 12000 /tmp/firefox-gui.log /tmp/wireshark-gui.log /tmp/cyberlab-apps/fixture-server.log; '
             'ps -eo pid,ppid,stat,comm; cat /sys/fs/cgroup/memory.events /sys/fs/cgroup/pids.events'], user='learner')
        for line in result.output.decode(errors='replace').splitlines():
            if not any(word in line.lower() for word in ('auth', 'password', 'token', 'challenge', 'credential')):
                print('Guest:', line[:600], flush=True)
        result = await asyncio.to_thread(container.exec_run,
            ['/bin/sh', '-c', 'xdotool search --onlyvisible --name "." getwindowname %@; df -h /tmp /dev/shm; '
             'du -sh /home/learner/firefox-gui-fixture; cat /home/learner/gui-fixture.html'], user='learner',
            environment={'DISPLAY': ':99', 'XAUTHORITY': '/tmp/cyberlab-apps/Xauthority'})
        print('Fixture windows:', result.output.decode(errors='replace')[-4000:], flush=True)
        raise
    finally:
        if attachment:
            attachment.cancel()
            await asyncio.gather(attachment, return_exceptions=True)
        engine._close_attachments(session.id)
        viewer_log.close()
