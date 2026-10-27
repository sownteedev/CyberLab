import re

from .models import NodeUser

def validate_environment(hostname, user):
    if hostname is not None and (
        not isinstance(hostname, str) or len(hostname) > 63
        or not re.fullmatch(r"[a-z][a-z0-9]*(?:-[a-z0-9]+)*", hostname)
    ):
        raise ValueError("Node hostname must be a safe single DNS label")
    if user is None:
        return
    if not isinstance(user, NodeUser) or not isinstance(user.name, str) or not re.fullmatch(r"[a-z_][a-z0-9_-]{0,31}", user.name):
        raise ValueError("Node user requires a safe account name")
    if user.name in {"root", "nobody"} or any(type(value) is not int or not 1000 <= value <= 60000 for value in (user.uid, user.gid)):
        raise ValueError("Configured node users require non-system UID/GID between 1000 and 60000")
    if user.home != f"/home/{user.name}" or user.shell not in {"/bin/sh", "/bin/bash"}:
        raise ValueError("Node user requires /home/<name> and an approved sh or bash shell")

def workspace(node):
    return node.user.home if node.user else "/tmp/lab"

def runtime_user(node):
    return f"{node.user.uid}:{node.user.gid}" if node.user else "65534:65534"

def shell_environment(node):
    if node.user is None:
        return {"TERM": "xterm-256color", "HOME": "/tmp"}
    return {
        "TERM": "xterm-256color", "HOME": node.user.home,
        "USER": node.user.name, "LOGNAME": node.user.name, "SHELL": node.user.shell,
        "PS1": f"{node.user.name}@{node.hostname or node.id}:\\w\\$ ",
        "ENV": "/dev/null", "BASH_ENV": "/dev/null",
    }
