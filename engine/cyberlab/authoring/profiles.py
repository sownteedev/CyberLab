from copy import deepcopy


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


def image_profiles(allowed_images):
    return [deepcopy(profile) for profile in PROFILES if profile["image"] in allowed_images]
