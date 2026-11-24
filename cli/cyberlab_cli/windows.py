import os
import re
import shlex
import subprocess
import sys
import time
from uuid import uuid4

from .terminal_apps import inspect_apps, launch_command
from .window_registry import attachment_command, attached_tokens, close_session, tabs_dir


def terminal_slots(session, node_id=None, slot=0):
    if not isinstance(session, dict) or session.get("state") != "RUNNING":
        raise ValueError("Session is not running")
    session_id = session.get("id")
    nodes = session.get("terminals", [])
    if not isinstance(nodes, list):
        raise ValueError("Invalid terminal plan; no windows opened")
    slots = session.get("terminal_slots", [[node, 0] for node in nodes])
    if node_id is not None:
        counts = session.get("terminal_counts", [[entry[0], 1] for entry in session.get("nodes", [])])
        count = next((entry[1] for entry in counts if entry[0] == node_id), 0)
        if type(slot) is not int or type(count) is not int or not 0 <= slot < count <= 4:
            raise ValueError("Terminal slot is outside the node's configured range")
        nodes, slots = [node_id], [[node_id, slot]]
    if (not isinstance(session_id, str) or re.fullmatch(r"[a-f0-9]{32}", session_id) is None
            or len(nodes) > 4
            or any(not isinstance(node, str) or len(node) > 64
                   or re.fullmatch(r"[a-z][a-z0-9]*(-[a-z0-9]+)*", node) is None for node in nodes)
            or len(set(nodes)) != len(nodes)):
        raise ValueError("Invalid terminal plan; no windows opened")
    if not nodes:
        return []
    if (not isinstance(slots, list) or not 1 <= len(slots) <= 8
            or any(not isinstance(entry, list) or len(entry) != 2 or entry[0] not in nodes
                   or type(entry[1]) is not int or not 0 <= entry[1] < 4 for entry in slots)):
        raise ValueError("Invalid terminal slots; no windows opened")
    expected = [[node, number] for node in nodes for number in range(sum(entry[0] == node for entry in slots))]
    if node_id is None and (slots != expected or {entry[0] for entry in slots} != set(nodes)):
        raise ValueError("Invalid terminal slots; no windows opened")
    return slots


def _title(value):
    return "".join(character for character in value if character.isprintable()).replace(";;", " ")[:128]


def _write_private(path, content):
    descriptor = os.open(path, os.O_WRONLY | os.O_CREAT | os.O_EXCL | os.O_NOFOLLOW, 0o600)
    with os.fdopen(descriptor, "w", encoding="utf-8") as stream:
        stream.write(content)

def _konsole_tab_profile(directory, token, command):
    path = directory / f"{token}.profile"
    if any(separator in str(path) for separator in (";;", "\n", "\r")):
        raise ValueError("Konsole tab profile path contains an unsupported separator")
    encoded = shlex.join(command).replace("\\", "\\\\").replace("\n", "\\n").replace("\r", "\\r").replace("\t", "\\t")
    _write_private(path, f"[General]\nName=CyberLab-{token}\nCommand={encoded}\n")
    return path

def launch_terminals(session, test_session_bus=False, *, interactive=True, node_id=None, slot=0):
    slots = terminal_slots(session, node_id, slot)
    result = {"terminal": None, "requested": len(slots), "attached": 0, "warnings": [], "errors": []}
    if not slots:
        return result
    reason = None
    if os.geteuid() == 0:
        reason = "Terminal windows must run as the desktop user, not root"
    elif interactive and not sys.stdout.isatty():
        reason = "stdout is not an interactive terminal"
    elif not (os.environ.get("DISPLAY") or os.environ.get("WAYLAND_DISPLAY")):
        reason = "No graphical desktop is available"
    if reason:
        result["warnings" if interactive else "errors"].append(reason)
        print(f"NOTE: {reason}; Session is kept. Attach manually:", file=sys.stderr)
        for node, number in slots:
            mode = "--test-session-bus " if test_session_bus else ""
            print(f"  cyberlab {mode}terminal {session['id']} {node} --slot {number}", file=sys.stderr)
        return result
    selection = inspect_apps()
    option = selection["selected"]
    if option is None:
        result["errors"].append("No compatible native terminal is available; install xfce4-terminal or attach with cyberlab terminal")
        return result
    result["terminal"] = option["id"]
    if "missing-preferred" in selection["warnings"]:
        result["warnings"].append(f"Saved terminal {selection['preferred']} is unavailable; temporarily using {option['name']}")
    if "invalid-config" in selection["warnings"]:
        result["warnings"].append("Invalid terminal preference file; temporarily using automatic selection")
    metadata = {entry[0]: (_title(entry[1]), _title(entry[2])) for entry in session.get("terminal_metadata", [])
                if isinstance(entry, list) and len(entry) == 3 and all(isinstance(value, str) for value in entry)}
    groups = {}
    launches = []
    for node, number in slots:
        group, title = metadata.get(node, ("", ""))
        display = _title(f"CyberLab · {group + ' · ' if group else ''}{title or node} ({number + 1})")
        token = uuid4().hex
        command = attachment_command(session["id"], node, number, token, display, test_session_bus)
        if option["id"] == "konsole" and group and node_id is None:
            groups.setdefault(group, []).append((token, display, command))
        else:
            launches.append((launch_command(option, command), [token]))
    for group, entries in groups.items():
        if len(entries) == 1:
            launches.append((launch_command(option, entries[0][2]), [entries[0][0]]))
            continue
        directory = tabs_dir(session["id"], test_session_bus)
        tabfile = directory / f"{session['id']}_{uuid4().hex}.tabs"
        lines = []
        for token, title, command in entries:
            profile = _konsole_tab_profile(directory, token, command)
            lines.append(f"title: {title} ;; profile: {profile}\n")
        _write_private(tabfile, "".join(lines))
        launches.append(([option["executable"], "--separate", "--builtin-profile", "--title", group,
                          "--tabs-from-file", str(tabfile)], [entry[0] for entry in entries]))
    tokens = set()
    processes = []
    for command, requested in launches:
        try:
            process = subprocess.Popen(command, stdin=subprocess.DEVNULL, stdout=subprocess.DEVNULL,
                                       stderr=subprocess.DEVNULL, start_new_session=True)
            processes.append((process, requested))
            tokens.update(requested)
        except OSError as error:
            result["errors"].append(f"Could not launch {option['name']}: {error}")
    deadline = time.monotonic() + 5
    confirmed = set()
    while tokens - confirmed and time.monotonic() < deadline:
        confirmed.update(attached_tokens(session["id"], test_session_bus) & tokens)
        for process, requested in processes:
            code = process.poll()
            if code not in (None, 0) and not set(requested) <= confirmed:
                result["errors"].append(f"{option['name']} launcher exited with code {code}")
                tokens.difference_update(requested)
        processes = [(process, requested) for process, requested in processes if process.returncode in (None, 0)]
        if tokens - confirmed:
            time.sleep(0.05)
    result["attached"] = len(confirmed)
    if tokens - confirmed:
        result["errors"].append("Terminal attachment was not confirmed within 5 seconds; inspect its window or retry opening the terminal, not starting the Lab")
    return result


def close_terminals(session_id, test_session_bus=False):
    return close_session(session_id, test_session_bus)
