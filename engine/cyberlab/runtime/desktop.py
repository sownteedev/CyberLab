import secrets
from time import monotonic, sleep

from docker.errors import DockerException

from cyberlab.lab.workstation import UBUNTU_IMAGE
from . import RuntimeFailure
from .docker_terminal import close_stream
from .docker_desktop import DockerDesktopStream
from .workspace import execute

PACKAGES = ('xpra', 'xvfb', 'xauth', 'dbus-x11', 'fonts-dejavu-core', 'python3-pil')
STATUS = '''import json, shutil
try:
    from PIL import Image
    imaging = True
except ImportError:
    imaging = False
print(json.dumps({'backend': 'xpra', 'ready': imaging and all(shutil.which(name) for name in ('xpra', 'Xvfb', 'xauth', 'dbus-run-session'))}))
'''
SETUP = '''import json, os, pathlib, socket, stat, subprocess, sys, time
from xpra.scripts.config import OPTION_TYPES
os.umask(0o077)
root = pathlib.Path('/tmp/cyberlab-apps')
try: root.mkdir(mode=0o700)
except FileExistsError: pass
info = root.lstat()
if not stat.S_ISDIR(info.st_mode) or info.st_uid != os.getuid() or info.st_mode & 0o077:
    raise RuntimeError('Unsafe graphical application directory')
os.chdir(os.environ['HOME'])
endpoint = root / 'display.sock'
password = root / 'auth'
def connected():
    try:
        with socket.socket(socket.AF_UNIX) as probe:
            probe.settimeout(0.2)
            probe.connect(str(endpoint))
        return True
    except OSError: return False
if not connected():
    descriptor = os.open(password, os.O_WRONLY | os.O_CREAT | os.O_TRUNC | os.O_NOFOLLOW, 0o600)
    with os.fdopen(descriptor, 'w') as stream:
        if not stat.S_ISREG(os.fstat(stream.fileno()).st_mode): raise RuntimeError('Invalid authentication file')
        stream.write(sys.argv[1])
    environment = {key: value for key, value in os.environ.items() if not key.startswith('XPRA_')}
    environment.update(DISPLAY=':99', XAUTHORITY=str(root / 'Xauthority'),
        XPRA_SYSTEM_CONF_DIRS=str(root / 'no-config'), XPRA_USER_CONF_DIRS=str(root / 'no-config'),
        XPRA_DEFAULT_CONF_DIRS=str(root / 'no-config'))
    command = ['/usr/bin/xpra', 'start', ':99', '--daemon=no', '--use-display=no',
        '--bind=' + str(endpoint), '--socket-dir=' + str(root), '--socket-dirs=' + str(root),
        '--socket-permissions=600', '--auth=file:filename=' + str(password),
        '--xvfb=/usr/bin/Xvfb +extension Composite -screen 0 1920x1080x24 -nolisten tcp -noreset',
        '--mdns=no', '--html=off', '--ssh-upgrade=no', '--rfb-upgrade=0',
        '--pulseaudio=no', '--speaker=disabled', '--microphone=disabled', '--video-encoders=none',
        '--webcam=no', '--clipboard=no', '--printing=no', '--file-transfer=no', '--open-files=no',
        '--open-url=no', '--notifications=no', '--system-tray=no', '--mmap=no',
        '--dbus-control=no', '--remote-logging=no', '--start-new-commands=no',
        '--exit-with-client=no', '--sharing=no', '--session-name=CyberLab ' + sys.argv[2]]
    if 'dbus-proxy' in OPTION_TYPES: command.append('--dbus-proxy=no')
    child = subprocess.Popen(command, env=environment, stdin=subprocess.DEVNULL,
        stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL, start_new_session=True)
    (root / 'xpra.pid').write_text(str(child.pid))
    for attempt in range(100):
        if child.poll() is not None: raise RuntimeError('Application display startup failed')
        if connected(): break
        time.sleep(0.1)
    else: raise RuntimeError('Application display startup timed out')
descriptor = os.open(password, os.O_RDONLY | os.O_NOFOLLOW)
with os.fdopen(descriptor, 'rb') as stream:
    info = os.fstat(stream.fileno())
    if not stat.S_ISREG(info.st_mode) or info.st_uid != os.getuid() or info.st_mode & 0o077:
        raise RuntimeError('Invalid application display credential')
    data = stream.read(33)
if len(data) != 32: raise RuntimeError('Invalid application display credential')
sys.stdout.buffer.write(data)
'''
BRIDGE = '''import os, select, socket, sys
with open(os.devnull, 'wb') as errors: os.dup2(errors.fileno(), 2)
if not select.select([0], [], [], 25)[0]: sys.exit(1)
with socket.socket(socket.AF_UNIX, socket.SOCK_STREAM) as connection:
    connection.settimeout(5)
    connection.connect('/tmp/cyberlab-apps/display.sock')
    connection.settimeout(None)
    while True:
        readable, _, _ = select.select([0, connection], [], [])
        if 0 in readable:
            data = os.read(0, 65536)
            if not data: break
            connection.sendall(data)
        if connection in readable:
            data = connection.recv(65536)
            if not data: break
            while data:
                written = os.write(1, data)
                data = data[written:]
'''

class DesktopRuntime:
    def __init__(self, runtime):
        self.runtime = runtime

    def node(self, session, node_id):
        node = next((node for node in session.lab.nodes if node.id == node_id), None)
        if node is None or node.image != UBUNTU_IMAGE or node.image not in self.runtime.workstation_images:
            raise RuntimeFailure('Desktop requires an administrator-enabled Ubuntu workstation')
        return node, self.runtime._workspace_container(session, node)

    def status(self, session, node_id):
        import json

        node, container = self.node(session, node_id)
        try:
            output = execute(self.runtime.client.api, container.id, node,
                             'exec /usr/bin/python3 -I -c "$1"', [STATUS], maximum=256)
        except (DockerException, RuntimeFailure):
            raise RuntimeFailure('Cannot check desktop tools; inspect the running lab machine') from None
        try:
            result = json.loads(output)
            if not isinstance(result, dict) or type(result.get('ready')) is not bool:
                raise ValueError
            return result
        except (ValueError, UnicodeError):
            raise RuntimeFailure('Invalid desktop readiness response from the lab machine') from None

    def prepare(self, session, node_id):
        _, container = self.node(session, node_id)
        command = 'apt-get update -qq && apt-get install -y --no-install-recommends ' + ' '.join(PACKAGES)
        try:
            execution = self.runtime.client.api.exec_create(container.id, cmd=['/usr/bin/env', 'DEBIAN_FRONTEND=noninteractive',
                                         '/usr/bin/timeout', '150', '/bin/sh', '-c', command],
                                        user='0:0', stdout=False, stderr=False, privileged=False)
            self.runtime.client.api.exec_start(execution['Id'], detach=True)
            deadline = monotonic() + 160
            while True:
                state = self.runtime.client.api.exec_inspect(execution['Id'])
                if not state['Running']:
                    break
                if monotonic() >= deadline:
                    raise RuntimeFailure('Desktop installation is still finishing; check apt inside the lab before retrying')
                sleep(0.5)
            if state.get('ExitCode') != 0 or not self.status(session, node_id).get('ready'):
                raise RuntimeFailure('Desktop preparation did not finish. Check apt/network inside the lab and retry; Session is kept.')
        except DockerException:
            raise RuntimeFailure('Cannot prepare desktop; inspect the lab package installation before retrying') from None
        return True

    def open(self, session, node_id):
        if hasattr(self.runtime, 'native') and self.runtime.native.status(session, node_id).get('backend') == 'native-x11':
            raise RuntimeFailure('This machine uses native X11; no Xpra viewer is needed')
        node, container = self.node(session, node_id)
        stream = None
        try:
            if not self.status(session, node_id).get('ready'):
                raise RuntimeFailure('Prepare desktop tools in this Ubuntu machine first')
            environment = {'HOME': node.user.home, 'USER': node.user.name, 'LOGNAME': node.user.name, 'DISPLAY': ':99'}
            try:
                credential = execute(self.runtime.client.api, container.id, node,
                    'exec /usr/bin/env HOME="$2" USER="$3" LOGNAME="$3" /usr/bin/python3 -I -c "$1" "$4" "$5"',
                    [SETUP, node.user.home, node.user.name, secrets.token_hex(16), node_id], maximum=32)
            except RuntimeFailure:
                raise RuntimeFailure('Isolated desktop startup failed or exceeded its limits; Session is kept') from None
            if len(credential) != 32:
                raise RuntimeFailure('Cannot start the isolated desktop; Session is kept')
            execution = self.runtime.client.api.exec_create(container.id, cmd=['/usr/bin/python3', '-I', '-c', BRIDGE],
                            stdin=True, stdout=True, stderr=False, tty=False, privileged=False,
                            user=node.user.name, environment=environment, workdir=node.user.home)
            stream = self.runtime.client.api.exec_start(execution['Id'], tty=False, socket=True)
            return DockerDesktopStream(self.runtime.client.api, execution['Id'], stream), credential
        except (DockerException, OSError):
            if stream is not None:
                close_stream(stream)
            raise RuntimeFailure('Cannot open the isolated desktop; Session is kept') from None
