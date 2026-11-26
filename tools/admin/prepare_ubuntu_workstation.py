#!/usr/bin/env python3
"""Prepare one reviewed Ubuntu workstation image; never edits Labs or starts Sessions."""

import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).resolve().parents[2]))

import argparse
from hashlib import sha256
import json
import os
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
    result = subprocess.run(["/usr/bin/docker", *arguments], env=guarded.ENVIRONMENT,
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

def build(uid):
    stopped_users(uid)
    existing = docker("image", "ls", "--quiet", "--filter", f"reference={IMAGE}").strip()
    if existing:
        raise ValueError("Ubuntu image already exists; refusing to overwrite it. Use check or enable.")
    stage = Path(tempfile.mkdtemp(prefix="cyberlab-ubuntu-build-", dir="/var/tmp"))
    print(f"Build receipt: {stage}", flush=True)
    docker("pull", BASE, timeout=900)
    base = inspect_image(BASE)
    recipe = RECIPE.format(base=base["Id"])
    (stage / "Dockerfile").write_text(recipe)
    docker("build", "--pull=false", "--network=default", "--tag", IMAGE, str(stage), timeout=1800)
    image = inspect_image(IMAGE)
    if image["Config"].get("Volumes") or image["Config"].get("Labels", {}).get(LABEL) != "ubuntu-v1":
        raise ValueError("Prepared image failed verification")
    receipt = {"image": IMAGE, "image_id": image["Id"], "base_id": base["Id"],
               "base_digests": base.get("RepoDigests", []), "recipe_sha256": sha256(recipe.encode()).hexdigest()}
    (stage / "receipt.json").write_text(json.dumps(receipt, indent=2) + "\n")
    print(json.dumps(receipt, indent=2))

def configured_bytes(config):
    allowed = {"catalog", "allowed_uids", "allowed_images", "authoring", "workstation_images"}
    if set(config) - allowed:
        raise ValueError("Unknown config fields; refusing to rewrite them")
    updated = dict(config)
    updated["allowed_images"] = list(dict.fromkeys([*config["allowed_images"], IMAGE]))
    updated["workstation_images"] = [IMAGE]
    return ("\n".join(f"{key} = {json.dumps(value, ensure_ascii=True)}" for key, value in updated.items()) + "\n").encode()

def enable(uid):
    original, config = stopped_users(uid)
    image = inspect_image(IMAGE)
    if image["Config"].get("Labels", {}).get(LABEL) != "ubuntu-v1" or image["Config"].get("Volumes"):
        raise ValueError("Expected the reviewed Ubuntu workstation image")
    info = guarded.cli(uid, "draft", "info")
    if not info.get("workstation_runtime"):
        raise ValueError("Deploy the workstation-capable runtime with the guarded updater first")
    updated = configured_bytes(config)
    stage = Path(tempfile.mkdtemp(prefix="cyberlab-ubuntu-enable-", dir="/var/tmp"))
    (stage / "daemon.toml.before").write_bytes(original)
    before_labs = guarded.cli(uid, "labs")
    guarded.run("/usr/bin/systemctl", "stop", guarded.SERVICE)
    try:
        if guarded.CONFIG.read_bytes() != original:
            raise ValueError("Configuration changed; retry after review")
        guarded.replace_file(guarded.CONFIG, updated, 0o644)
        guarded.run("/usr/bin/systemctl", "start", guarded.SERVICE)
        after = guarded.cli(uid, "draft", "info")
        profiles = [profile for profile in after["image_profiles"] if profile["image"] == IMAGE]
        if not profiles or not profiles[0].get("workstation") or guarded.cli(uid, "labs") != before_labs:
            raise RuntimeError("Ubuntu activation verification failed")
    except Exception:
        guarded.run("/usr/bin/systemctl", "stop", guarded.SERVICE)
        guarded.replace_file(guarded.CONFIG, original, 0o644)
        guarded.run("/usr/bin/systemctl", "start", guarded.SERVICE)
        raise
    (stage / "receipt.json").write_text(json.dumps({"image": IMAGE, "image_id": image["Id"],
                                                   "catalog_preserved": True, "result": "passed"}, indent=2) + "\n")
    print(f"Ubuntu enabled; configuration backup and verification: {stage}")

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
        build(args.uid)
    elif args.action == "enable":
        enable(args.uid)
    else:
        image = inspect_image(IMAGE)
        print(json.dumps({"image": IMAGE, "image_id": image["Id"], "workstation": image["Config"].get("Labels", {}).get(LABEL)}, indent=2))

if __name__ == "__main__":
    main()
