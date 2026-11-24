from hashlib import sha256
import json
from time import monotonic, sleep
from uuid import uuid4
from threading import Lock
from io import BytesIO
import tarfile
import shutil

from docker.types import LogConfig
from docker.errors import DockerException, ImageNotFound

from cyberlab.lab.software import APPLICATIONS, RECIPE_VERSION, fingerprint, specification, validate_software
from cyberlab.lab.workstation import UBUNTU_IMAGE, WORKSTATION_LABEL, WORKSTATION_VERSION
from . import RuntimeFailure
from .desktop import PACKAGES
from .checkpoints import CHECKPOINT_LABEL
from .image_storage import ImageStorage

LABEL = "org.ptit.cyberlab.software"
MAX_IMAGE_BYTES = 2 * 1024**3
MAX_CACHE_BYTES = 12 * 1024**3
CAPABILITIES = ["CHOWN", "DAC_OVERRIDE", "FOWNER", "FSETID", "KILL", "SETGID", "SETUID", "SETPCAP", "NET_BIND_SERVICE", "SYS_CHROOT", "AUDIT_WRITE", "SETFCAP"]
INSTALL = r'''
set -eu
export DEBIAN_FRONTEND=noninteractive
printf '#!/bin/sh\nexit 101\n' > /usr/sbin/policy-rc.d
chmod 755 /usr/sbin/policy-rc.d
printf 'wireshark-common wireshark-common/install-setuid boolean true\n' | debconf-set-selections
apt-get -o Acquire::Retries=2 -o Acquire::http::Timeout=30 update -qq
if [ "$1" = firefox ]; then
    apt-get install -y --no-install-recommends ca-certificates curl gnupg
    install -d -m 0755 /etc/apt/keyrings
    curl --fail --location --max-time 90 https://packages.mozilla.org/apt/repo-signing-key.gpg -o /etc/apt/keyrings/packages.mozilla.org.asc
    fingerprint=$(gpg --batch --show-keys --with-colons /etc/apt/keyrings/packages.mozilla.org.asc | awk -F: '$1=="fpr" {print $10; exit}')
    test "$fingerprint" = 35BAA0B33E9EB396F59CA838C0BA5CE6DC6315A3
    printf 'deb [signed-by=/etc/apt/keyrings/packages.mozilla.org.asc] https://packages.mozilla.org/apt mozilla main\n' > /etc/apt/sources.list.d/mozilla.list
    printf 'Package: firefox*\nPin: origin packages.mozilla.org\nPin-Priority: 1000\n' > /etc/apt/preferences.d/mozilla
    apt-get -o Acquire::Retries=2 -o Acquire::http::Timeout=30 update -qq
fi
shift
apt-get -o Acquire::Retries=2 -o Acquire::http::Timeout=30 install -y --no-install-recommends -- "$@"
if command -v dumpcap >/dev/null 2>&1; then
    usermod -a -G wireshark student
    chown root:wireshark /usr/bin/dumpcap
    chmod 0750 /usr/bin/dumpcap
    setcap cap_net_raw,cap_net_admin=eip /usr/bin/dumpcap
fi
if command -v firefox >/dev/null 2>&1; then
    test ! -e /usr/bin/firefox || ! grep -q 'requires the firefox snap' /usr/bin/firefox
    firefox --version
fi
dpkg-query -W -f='${Package}\t${Version}\n' > /var/lib/cyberlab-software-packages.txt
apt-get clean
rm -rf /var/lib/apt/lists/* /root/.gnupg /root/.cache
test -z "$(find /home/student -mindepth 1 -print -quit)"
'''

class SoftwareRuntime:
    def __init__(self, runtime, scope):
        self.runtime = runtime
        self.client = runtime.client
        self.scope = scope
        self.build_lock = Lock()
        self.storage = ImageStorage()

    def base(self):
        if UBUNTU_IMAGE not in self.runtime.workstation_images:
            raise RuntimeFailure("Software preparation requires administrator-enabled Ubuntu")
        image = self.client.images.get(UBUNTU_IMAGE)
        config = image.attrs.get("Config", {})
        if config.get("Volumes") or (config.get("Labels") or {}).get(WORKSTATION_LABEL) != WORKSTATION_VERSION:
            raise RuntimeFailure("Unreviewed Ubuntu base image")
        return image.id

    def verify(self, software, receipt):
        validate_software(software, UBUNTU_IMAGE)
        if receipt.get("spec") != fingerprint(software) or receipt.get("image") != software.environment:
            raise RuntimeFailure("Software changed or environment is not prepared; prepare this exact configuration")
        try:
            image = self.client.images.get(software.environment)
        except ImageNotFound:
            raise RuntimeFailure("Prepared software image is no longer available") from None
        config = image.attrs.get("Config", {})
        labels = config.get("Labels") or {}
        if image.id != receipt["image"] or config.get("Volumes") or labels.get(LABEL) != RECIPE_VERSION or labels.get(LABEL + ".spec") != receipt["spec"] or labels.get(LABEL + ".scope") != self.scope:
            raise RuntimeFailure("Prepared software image failed provenance checks")
        return image.id

    def cleanup(self):
        for container in self.client.containers.list(all=True, filters={"label": [LABEL + ".building=" + self.scope]}):
            labels = container.labels or {}
            if container.name.startswith("cyberlab-software-") and not labels.get("org.ptit.cyberlab.managed"):
                container.remove(force=True)

    def cleanup_images(self, protected):
        """Remove only unused prepared images from this CyberLab scope."""
        protected = set(protected)
        removed = set()
        images = self.client.images.list(filters={"label": [LABEL + ".scope=" + self.scope]})
        for image in images:
            labels = image.attrs.get('Config', {}).get('Labels') or {}
            if (image.id in protected or not labels.get(LABEL)
                    or labels.get(LABEL + '.scope') != self.scope or CHECKPOINT_LABEL in labels):
                continue
            try:
                image.remove(force=False, noprune=True)
            except ImageNotFound:
                removed.add(image.id)
            except DockerException:
                continue
            else:
                removed.add(image.id)
        return removed

    def prepare(self, software, base, cancel, progress):
        while not self.build_lock.acquire(timeout=0.5):
            if cancel.is_set():
                raise RuntimeFailure("Preparation cancelled")
        try:
            return self._prepare(software, base, cancel, progress)
        finally:
            self.build_lock.release()

    def _prepare(self, software, base, cancel, progress):
        validate_software(software, UBUNTU_IMAGE)
        if base != self.base():
            raise RuntimeFailure("Ubuntu base changed; review preparation again")
        existing = self.client.images.list(filters={"label": [LABEL + ".scope=" + self.scope]})
        used = self.storage.total(image for image in existing
                                  if CHECKPOINT_LABEL not in (image.attrs.get('Config', {}).get('Labels') or {}))
        if used + MAX_IMAGE_BYTES > MAX_CACHE_BYTES:
            raise RuntimeFailure("Prepared software storage limit reached; no referenced image was deleted")
        docker_root = self.client.info().get("DockerRootDir", "/var/lib/docker")
        if shutil.disk_usage(docker_root).free < MAX_IMAGE_BYTES:
            raise RuntimeFailure("Not enough free Docker storage to prepare software (2 GiB required)")
        packages = set(software.packages)
        if software.gui:
            packages.update(PACKAGES)
        for app in APPLICATIONS:
            if app['id'] in software.apps:
                packages.update(app['packages'])
        container = None
        image = None
        try:
            progress("Installing signed packages in an isolated preparation container", 15)
            container = self.client.containers.create(
                base, name="cyberlab-software-" + uuid4().hex,
                command=["/usr/bin/timeout", "1200", "/bin/sh", "-c", INSTALL, "cyberlab-software", "firefox" if "firefox" in software.apps else "ubuntu", *sorted(packages)],
                entrypoint=[], user="0:0", working_dir="/tmp", privileged=False, cap_drop=["ALL"], cap_add=CAPABILITIES,
                environment={"HOME": "/root", "USER": "root", "LOGNAME": "root"},
                network_mode="bridge", init=True, mem_limit="2g", memswap_limit="2g", nano_cpus=2_000_000_000,
                pids_limit=256, restart_policy={"Name": "no"},
                tmpfs={"/tmp": "rw,nosuid,nodev,size=256m", "/run": "rw,nosuid,nodev,size=16m"},
                labels={LABEL + ".building": self.scope}, log_config=LogConfig(type="local", config={"max-size": "1m", "max-file": "1", "compress": "false"}),
                healthcheck={"test": ["NONE"]})
            container.start()
            deadline = monotonic() + 1220
            next_size_check = 0
            while True:
                if cancel.is_set():
                    raise RuntimeFailure("Preparation cancelled")
                if monotonic() > deadline:
                    raise RuntimeFailure("Software preparation timed out")
                container.reload()
                if monotonic() >= next_size_check:
                    sizes = self.client.api.containers(all=True, size=True, filters={"id": container.id})
                    if len(sizes) != 1 or sizes[0].get("SizeRw", MAX_IMAGE_BYTES + 1) > MAX_IMAGE_BYTES:
                        raise RuntimeFailure("Software preparation exceeds the 2 GiB writable-layer limit")
                    if shutil.disk_usage(docker_root).free < 512 * 1024**2:
                        raise RuntimeFailure("Software preparation stopped to preserve free Docker storage")
                    next_size_check = monotonic() + 5
                if container.status in {"exited", "dead"}:
                    break
                cancel.wait(1)
            if container.attrs.get("State", {}).get("ExitCode") != 0:
                log = container.logs(tail=30).decode("utf-8", "replace")[-4096:]
                raise RuntimeFailure("Software installation failed: " + log)
            progress("Recording immutable software environment", 90)
            stream, _ = container.get_archive("/var/lib/cyberlab-software-packages.txt")
            archive = bytearray()
            for chunk in stream:
                archive.extend(chunk)
                if len(archive) > 1024 * 1024:
                    raise RuntimeFailure("Package manifest exceeds limit")
            with tarfile.open(fileobj=BytesIO(archive)) as package_archive:
                entry = package_archive.next()
                if entry is None or not entry.isfile() or entry.size > 512 * 1024:
                    raise RuntimeFailure("Invalid package manifest")
                versions = package_archive.extractfile(entry).read().decode("utf-8")
            labels = {WORKSTATION_LABEL: WORKSTATION_VERSION, LABEL: RECIPE_VERSION,
                      LABEL + ".scope": self.scope, LABEL + ".spec": fingerprint(software), LABEL + ".building": ""}
            image = container.commit(repository="cyberlab-software", tag=uuid4().hex,
                                     conf={"Labels": labels, "User": "2000:2000", "Cmd": ["sleep", "infinity"], "Entrypoint": [], "WorkingDir": "/home/student",
                                           "Env": ["PATH=/usr/local/sbin:/usr/local/bin:/usr/sbin:/usr/bin:/sbin:/bin", "HOME=/home/student", "USER=student", "LOGNAME=student"]})
            image.reload()
            if image.attrs.get("Size", MAX_IMAGE_BYTES + 1) > MAX_IMAGE_BYTES:
                raise RuntimeFailure("Prepared environment exceeds the 2 GiB image limit")
            if cancel.is_set():
                raise RuntimeFailure("Preparation cancelled")
            return {"image": image.id, "base": base, "spec": fingerprint(software), "recipe": RECIPE_VERSION,
                    "software": specification(software), "size": image.attrs.get("Size", 0), "packages": versions}
        except Exception:
            if image is not None:
                self.client.images.remove(image.id, force=False, noprune=True)
            raise
        finally:
            if container is not None:
                container.remove(force=True)
