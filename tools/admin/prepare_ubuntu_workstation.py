#!/usr/bin/env python3
"""Prepare one reviewed Ubuntu workstation image; never edits Labs or starts Sessions."""

import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).resolve().parents[2]))

import argparse
from hashlib import sha256
import json
import os
import re
import shutil
import stat
import subprocess
import tempfile
import tomllib

from tools.install import upgrade_runtime as guarded

IMAGE = "cyberlab/ubuntu:24.04-1"
BASE = "ubuntu:24.04"
LABEL = "org.ptit.cyberlab.workstation"
RECIPE = '''FROM {base}
ENV DEBIAN_FRONTEND=noninteractive
RUN apt-get update && apt-get install -y --no-install-recommends bash sudo coreutils findutils grep sed gawk tar gzip procps iproute2 iputils-ping curl wget ca-certificates nano less python3 && rm -rf /var/lib/apt/lists/*
RUN groupadd --gid 2000 student && useradd --uid 2000 --gid 2000 --no-create-home --home-dir /home/student --shell /bin/bash student && install -d -m 0700 -o 2000 -g 2000 /home/student && printf 'student ALL=(ALL) NOPASSWD: ALL\\n' > /etc/sudoers.d/student && chmod 0440 /etc/sudoers.d/student && visudo -cf /etc/sudoers.d/student
RUN printf '#!/bin/sh\\nexit 101\\n' > /usr/sbin/policy-rc.d && chmod 0755 /usr/sbin/policy-rc.d
LABEL org.ptit.cyberlab.workstation="ubuntu-v1"
USER 2000:2000
WORKDIR /home/student
ENV HOME=/home/student USER=student LOGNAME=student SHELL=/bin/bash LANG=C.UTF-8
CMD ["sleep", "infinity"]
'''

def docker(*arguments, timeout=120):
    result = subprocess.run(["/usr/bin/docker", "--host=unix:///var/run/docker.sock", *arguments], env=guarded.ENVIRONMENT,
                            text=True, capture_output=True, timeout=timeout)
    if result.returncode:
        raise RuntimeError("Docker operation failed: " + result.stderr[-4000:])
    return result.stdout

def stopped_users(uid):
    guarded.check_admin_path(guarded.CONFIG)
    original = guarded.CONFIG.read_bytes()
    config = tomllib.loads(original.decode())
    if uid not in config["allowed_uids"]:
        raise ValueError("Desktop user must already be allowed by cyberlabd")
    for owner in config["allowed_uids"]:
        if any(session["state"] != "STOPPED" for session in guarded.cli(owner, "sessions")):
            raise ValueError("Save work and explicitly stop all users' Sessions before enabling Ubuntu")
    return original, config

def inspect_image(reference):
    return json.loads(docker("image", "inspect", reference))[0]

def verify_image(image):
    config = image.get("Config", {})
    if (not re.fullmatch(r"sha256:[0-9a-f]{64}", image.get("Id", ""))
            or config.get("Volumes") or (config.get("Labels") or {}).get(LABEL) != "ubuntu-v1"
            or config.get("User") != "2000:2000" or config.get("WorkingDir") != "/home/student"
            or config.get("Entrypoint") or config.get("Cmd") != ["sleep", "infinity"]):
        raise ValueError("Expected the reviewed Ubuntu workstation image; refusing to overwrite an existing image")
    return image

def check_build_space(stage):
    storage = Path(docker("info", "--format", "{{.DockerRootDir}}").strip())
    if not storage.is_absolute() or not storage.is_dir():
        raise ValueError("Cannot determine the local Docker storage directory")
    for location in (stage, storage):
        if shutil.disk_usage(location).free < 3 * 1024**3:
            raise ValueError(f"Ubuntu preparation needs at least 3 GiB free space: {location}")

def prepare_image(stage):
    """Prepare only the fixed base image; never change daemon policy or user Labs."""
    existing = docker("image", "ls", "--quiet", "--filter", f"reference={IMAGE}").strip()
    if existing:
        image = verify_image(inspect_image(IMAGE))
        receipt = {"image": IMAGE, "image_id": image["Id"], "action": "reused"}
    else:
        check_build_space(stage)
        context = stage / "ubuntu-build"
        context.mkdir(mode=0o700)
        print("Preparing the reviewed Ubuntu 24.04 Lab image (first installation may take several minutes)...", flush=True)
        docker("pull", BASE, timeout=900)
        base = inspect_image(BASE)
        if not re.fullmatch(r"sha256:[0-9a-f]{64}", base.get("Id", "")):
            raise ValueError("Invalid Ubuntu base image identity")
        recipe = RECIPE.format(base=base["Id"])
        (context / "Dockerfile").write_text(recipe)
        docker("build", "--pull=false", "--network=default", "--tag", IMAGE, str(context), timeout=1800)
        image = verify_image(inspect_image(IMAGE))
        receipt = {"image": IMAGE, "image_id": image["Id"], "base_id": base["Id"],
                   "base_digests": base.get("RepoDigests", []), "action": "built",
                   "recipe_sha256": sha256(recipe.encode()).hexdigest()}
    (stage / "ubuntu-image.json").write_text(json.dumps(receipt, indent=2) + "\n")
    print(json.dumps(receipt, indent=2), flush=True)
    return receipt

def build(uid):
    stopped_users(uid)
    stage = Path(tempfile.mkdtemp(prefix="cyberlab-ubuntu-build-", dir="/var/tmp"))
    print(f"Build receipt: {stage}", flush=True)
    return prepare_image(stage)

def configured_bytes(config):
    allowed = {"catalog", "allowed_uids", "allowed_images", "authoring", "workstation_images"}
    if set(config) - allowed:
        raise ValueError("Unknown config fields; refusing to rewrite them")
    updated = dict(config)
    updated["allowed_images"] = list(dict.fromkeys([*config["allowed_images"], IMAGE]))
    updated["workstation_images"] = [IMAGE]
    return ("\n".join(f"{key} = {json.dumps(value, ensure_ascii=True)}" for key, value in updated.items()) + "\n").encode()

def enable(uid):
    stage = Path(tempfile.mkdtemp(prefix="cyberlab-ubuntu-enable-", dir="/var/tmp"))
    return prepare_existing(uid, stage, build_image=False)

def prepare_existing(uid, stage, lock_fd=None, *, build_image=True):
    with guarded.installer_lock(lock_fd):
        with guarded.installer_lock(path=guarded.MAINTENANCE_LOCK):
            return activate_existing(uid, stage, build_image=build_image)

def activate_existing(uid, stage, *, build_image):
    guarded.check_studio_closed()
    original, config = stopped_users(uid)
    mode = stat.S_IMODE(guarded.CONFIG.stat().st_mode)
    information = guarded.wait_for_daemon(uid)
    if not {"maintenance-lock-v1", "runtime:docker"}.issubset(information.get("capabilities", [])):
        raise ValueError("Update CyberLab first: the daemon must support the maintenance barrier")
    if "maintenance-busy" in information.get("capabilities", []):
        raise ValueError("Wait for background software preparation before enabling Ubuntu")
    info = guarded.cli(uid, "draft", "info")
    if not info.get("workstation_runtime"):
        raise ValueError("Deploy the workstation-capable runtime with the guarded updater first")
    updated = configured_bytes(config)
    checkpoints = guarded.stopped_checkpoints(config["allowed_uids"])
    before_labs = {owner: guarded.cli(owner, "labs") for owner in config["allowed_uids"]}
    if build_image:
        prepare_image(stage)
    image = verify_image(inspect_image(IMAGE))
    if guarded.CONFIG.read_bytes() != original:
        raise ValueError("Configuration changed; retry after review")
    guarded.check_studio_closed()
    if guarded.stopped_checkpoints(config["allowed_uids"]) != checkpoints:
        raise ValueError("Saved Sessions changed while preparing Ubuntu")
    if IMAGE in config["allowed_images"] and IMAGE in config.get("workstation_images", []):
        verify_activation(uid, config, before_labs, checkpoints)
        print("Ubuntu is already prepared and enabled; no configuration or service changed.")
        return
    backup = stage / "daemon.toml.before"
    backup.write_bytes(original)
    backup.chmod(0o600)
    stopped = False
    changed = False
    try:
        guarded.run("/usr/bin/systemctl", "stop", guarded.SERVICE)
        stopped = True
        guarded.check_studio_closed()
        if guarded.CONFIG.read_bytes() != original:
            raise ValueError("Configuration changed; retry after review")
        guarded.replace_file(guarded.CONFIG, updated, mode)
        changed = True
        guarded.run("/usr/bin/systemctl", "start", guarded.SERVICE)
        guarded.wait_for_daemon(uid)
        verify_activation(uid, config, before_labs, checkpoints)
    except BaseException:
        if stopped:
            with guarded.recovery_signals():
                guarded.run("/usr/bin/systemctl", "stop", guarded.SERVICE)
                if changed:
                    guarded.replace_file(guarded.CONFIG, original, mode)
                guarded.run("/usr/bin/systemctl", "start", guarded.SERVICE)
                guarded.wait_for_daemon(uid)
        raise
    (stage / "receipt.json").write_text(json.dumps({"image": IMAGE, "image_id": image["Id"],
        "catalog_preserved": True, "saved_sessions_preserved": len(checkpoints), "result": "passed"}, indent=2) + "\n")
    print(f"Ubuntu enabled; configuration backup and verification: {stage}")

def verify_activation(uid, config, labs, checkpoints):
    after = guarded.cli(uid, "draft", "info")
    profiles = [profile for profile in after.get("image_profiles", []) if profile.get("image") == IMAGE]
    if (not profiles or not profiles[0].get("workstation")
            or not after.get("machine_setup") or not after.get("software_preparation")
            or {owner: guarded.cli(owner, "labs") for owner in config["allowed_uids"]} != labs
            or guarded.stopped_checkpoints(config["allowed_uids"]) != checkpoints):
        raise RuntimeError("Ubuntu activation verification failed")

def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("action", choices=("plan", "build", "enable", "check"))
    parser.add_argument("--uid", type=int)
    args = parser.parse_args()
    if args.action == "plan":
        print(RECIPE.format(base=BASE))
        print("Ubuntu only: writable container filesystem, student sudo, outbound bridge; no host mounts, Docker socket or privileged mode.")
        print("Save/Suspend retains the Ubuntu system image; Reset discards it. /tmp and /run remain temporary.")
        return
    if os.geteuid() != 0 or not args.uid or args.uid < 1:
        parser.error("Administrator action requires root and the existing desktop --uid; use the host authentication dialog")
    if args.action == "build":
        with guarded.installer_lock():
            with guarded.installer_lock(path=guarded.MAINTENANCE_LOCK):
                guarded.check_studio_closed()
                build(args.uid)
    elif args.action == "enable":
        enable(args.uid)
    else:
        image = inspect_image(IMAGE)
        print(json.dumps({"image": IMAGE, "image_id": image["Id"], "workstation": image["Config"].get("Labels", {}).get(LABEL)}, indent=2))

if __name__ == "__main__":
    main()
