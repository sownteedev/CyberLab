import re

from .models import NodeUser

UBUNTU_IMAGE = "cyberlab/ubuntu:24.04-1"
UBUNTU_USER = NodeUser("student", 2000, 2000, "/home/student", "/bin/bash")
WORKSTATION_LABEL = "org.ptit.cyberlab.workstation"
WORKSTATION_VERSION = "ubuntu-v1"
RESERVED_USERNAMES = frozenset({
    "root", "nobody", "daemon", "bin", "sys", "sync", "games", "man", "lp", "mail", "news", "uucp",
    "proxy", "www-data", "backup", "list", "irc", "ubuntu", "sshd", "messagebus", "polkitd",
    "systemd-network", "systemd-resolve", "systemd-timesync", "tcpdump", "uuidd", "landscape", "syslog",
})

def workstation_user(name):
    if not isinstance(name, str) or re.fullmatch(r"[a-z][a-z0-9_-]{0,31}", name) is None or name in RESERVED_USERNAMES:
        raise ValueError("Ubuntu username must be 1-32 lowercase ASCII characters, start with a letter and not be a system account")
    return NodeUser(name, 2000, 2000, f"/home/{name}", "/bin/bash")

def validate_workstation(node):
    if node.image != UBUNTU_IMAGE or node.user is None or node.user != workstation_user(node.user.name):
        raise ValueError("Ubuntu workstations require UID/GID 2000, Bash and /home/<username>")

def validate_images(images):
    if not isinstance(images, dict) or len(images) > 4 or any(
        not isinstance(node, str) or not re.fullmatch(r"[a-z][a-z0-9-]{0,63}", node)
        or not isinstance(image, str) or not re.fullmatch(r"sha256:[a-f0-9]{64}", image)
        for node, image in images.items()
    ):
        raise ValueError("Invalid saved system image references")
    return images
