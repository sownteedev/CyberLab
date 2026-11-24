from copy import deepcopy
from dataclasses import asdict
from cyberlab.lab.workstation import UBUNTU_IMAGE, UBUNTU_USER, RESERVED_USERNAMES


PROFILES = (
    {
        "image": "cyberlab/demo-users:0.6.0",
        "label": "Linux c\u01a1 b\u1ea3n",
        "command": ["sleep", "86400"],
        "accounts": [
            {"name": "alice", "uid": 2000, "gid": 2000, "home": "/home/alice", "shell": "/bin/sh"},
            {"name": "bob", "uid": 2001, "gid": 2001, "home": "/home/bob", "shell": "/bin/sh"},
        ],
    },
    {"image": "busybox:1.37.0", "label": "BusyBox", "command": ["sleep", "86400"], "accounts": []},
)


def image_profiles(allowed_images, workstation_images=frozenset()):
    profiles = []
    if UBUNTU_IMAGE in allowed_images and UBUNTU_IMAGE in workstation_images:
        profiles.append({"image": UBUNTU_IMAGE, "label": "Ubuntu 24.04 (sudo / apt)",
                         "command": ["sleep", "infinity"], "accounts": [asdict(UBUNTU_USER)],
                         "workstation": True, "custom_username": True, "machine_setup": True,
                         "reserved_usernames": sorted(RESERVED_USERNAMES),
                         "resources": {"memory_mb": 512, "cpu_millicores": 1000}})
    return profiles + [deepcopy(profile) for profile in PROFILES if profile["image"] in allowed_images]
