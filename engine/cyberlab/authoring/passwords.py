"""Bounded account password updates for owner-checked draft revisions."""

import json
import re
import subprocess

import yaml

from cyberlab.lab.loader import _LabYamlLoader

MAX_REQUEST = 8192
MAX_PASSWORD = 128


def _unique(pairs):
    result = {}
    for key, value in pairs:
        if key in result:
            raise ValueError("Invalid password request")
        result[key] = value
    return result


def password_bytes(password):
    try:
        encoded = password.encode("utf-8") if isinstance(password, str) else b""
    except UnicodeError:
        raise ValueError("Invalid password request") from None
    if not 1 <= len(encoded) <= MAX_PASSWORD or any(char in encoded for char in (0, 10, 13)):
        raise ValueError("Password requires 1-128 UTF-8 bytes without NUL or newlines")
    return encoded


def parse_request(payload):
    try:
        if not isinstance(payload, str) or len(payload.encode("utf-8")) > MAX_REQUEST:
            raise ValueError()
        request = json.loads(payload, object_pairs_hook=_unique)
        if not isinstance(request, dict):
            raise ValueError()
        action = request.get("action")
        required = {"account", "action", "password"} if action == "replace" else {"account", "action"}
        if action not in {"replace", "lock"} or set(request) != required:
            raise ValueError()
        if not isinstance(request["account"], str) or not re.fullmatch(r"[a-z][a-z0-9_-]{0,31}", request["account"]):
            raise ValueError()
        if action == "replace":
            password_bytes(request["password"])
        return request
    except (ValueError, TypeError, UnicodeError, RecursionError):
        raise ValueError("Invalid password request") from None


def hash_password(password):
    encoded = password_bytes(password)
    try:
        result = subprocess.run(["/usr/bin/openssl", "passwd", "-6", "-stdin"],
                                input=encoded + b"\n", stdout=subprocess.PIPE, stderr=subprocess.DEVNULL,
                                timeout=10, check=True, env={"PATH": "/usr/bin:/bin", "LC_ALL": "C"})
        hashed = result.stdout.decode("ascii").strip()
        if not re.fullmatch(r"\$6\$[./0-9A-Za-z]{1,16}\$[./0-9A-Za-z]{86}", hashed):
            raise ValueError()
        return hashed
    except Exception:
        raise ValueError("Password operation failed") from None


def set_password(store, policy, identifier, revision, node_id, payload, uid):
    snapshot = store.get(identifier, uid, revision)
    request = parse_request(payload)
    try:
        document = yaml.load(snapshot["definition"], Loader=_LabYamlLoader)
        nodes = [node for node in document["nodes"] if node.get("id") == node_id]
        if len(nodes) != 1:
            raise ValueError()
        node = nodes[0]
        if node.get("image") not in policy.workstation_images:
            raise ValueError()
        main = node.get("user", {})
        if main.get("uid") != 2000 or main.get("gid") != 2000:
            raise ValueError()
        setup = node.setdefault("setup", {})
        users = setup.get("users", [])
        if not isinstance(users, list) or len(users) > 32:
            raise ValueError()
        targets = ([setup] if request["account"] == main.get("name") else []) + [
            user for user in users if user.get("name") == request["account"]]
        if len(targets) != 1:
            raise ValueError()
    except (AttributeError, KeyError, TypeError, ValueError, yaml.YAMLError):
        raise ValueError("Account is unavailable for this operation") from None
    targets[0]["password_hash"] = "!" if request["action"] == "lock" else hash_password(request["password"])
    return store.change(identifier, uid, revision, definition=json.dumps(document, ensure_ascii=False, indent=2))
