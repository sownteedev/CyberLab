import os
from pathlib import Path
import re
import subprocess
import sys

from .window_registry import close_session, record_process, tabs_dir

KONSOLE = Path("/usr/bin/konsole")

def launch_terminals(session, test_session_bus=False, *, interactive=True, node_id=None, slot=0):
    if not isinstance(session, dict) or session.get("state") != "RUNNING":
        return
    if node_id is not None:
        counts = session.get("terminal_counts", [[entry[0], 1] for entry in session.get("nodes", [])])
        count = next((entry[1] for entry in counts if entry[0] == node_id), 0)
        if type(slot) is not int or type(count) is not int or not 0 <= slot < count <= 4:
            raise ValueError("Terminal slot is outside the node's configured range")
        session = {**session, "terminals": [node_id], "terminal_slots": [[node_id, number] for number in range(count)]}
    metadata = {entry[0]: (entry[1], entry[2]) for entry in session.get("terminal_metadata", [])
                if isinstance(entry, list) and len(entry) == 3 and isinstance(entry[0], str)}
    nodes = session.get("terminals", [])
    if not nodes:
        return
    session_id = session.get("id")
    if (
        not isinstance(session_id, str) or re.fullmatch(r"[a-f0-9]{32}", session_id) is None
        or not isinstance(nodes, list) or len(nodes) > 4
        or any(not isinstance(node, str) or len(node) > 64 or re.fullmatch(r"[a-z][a-z0-9]*(-[a-z0-9]+)*", node) is None for node in nodes)
        or len(set(nodes)) != len(nodes)
    ):
        print("WARNING: invalid terminal plan; Session is kept, no windows opened.", file=sys.stderr)
        return
    slots = session.get("terminal_slots", [[node, 0] for node in nodes])
    if (
        not isinstance(slots, list) or not 1 <= len(slots) <= 8
        or any(not isinstance(entry, list) or len(entry) != 2 or entry[0] not in nodes
               or type(entry[1]) is not int or not 0 <= entry[1] < 4 for entry in slots)
    ):
        print("WARNING: invalid terminal slots; Session is kept, no windows opened.", file=sys.stderr)
        return
    expected = [[node, slot] for node in nodes for slot in range(sum(entry[0] == node for entry in slots))]
    if slots != expected or {entry[0] for entry in slots} != set(nodes):
        print("WARNING: invalid terminal slots; Session is kept, no windows opened.", file=sys.stderr)
        return
    if os.geteuid() == 0:
        reason = "automatic terminal windows must run as the student, not root"
    elif interactive and not sys.stdout.isatty():
        reason = "stdout is not an interactive terminal"
    elif not (os.environ.get("DISPLAY") or os.environ.get("WAYLAND_DISPLAY")):
        reason = "no graphical desktop is available"
    elif not KONSOLE.is_file() or not os.access(KONSOLE, os.X_OK):
        reason = "Konsole is not installed at /usr/bin/konsole"
    else:
        reason = None
    if node_id is not None:
        slots = [[node_id, slot]]
    if reason is not None:
        if not interactive:
            raise RuntimeError(reason)
        print(f"NOTE: {reason}; Session is running. Attach manually:", file=sys.stderr)
        for node, slot in slots:
            mode = "--test-session-bus " if test_session_bus else ""
            suffix = f" --slot {slot}" if slot else ""
            print(f"  cyberlab {mode}terminal {session_id} {node}{suffix}", file=sys.stderr)
        return
    def _spawn(command, target=""):
        target_text = f" for {target}" if target else ""
        try:
            process = subprocess.Popen(
                command, stdin=subprocess.DEVNULL, stdout=subprocess.DEVNULL,
                stderr=subprocess.DEVNULL, start_new_session=True,
            )
            try:
                code = process.wait(timeout=0.2)
            except subprocess.TimeoutExpired:
                try:
                    if not record_process(session_id, process, test_session_bus):
                        print("WARNING: window process could not be tracked; close it manually if needed.", file=sys.stderr)
                except (OSError, ValueError):
                    print("WARNING: window opened but could not be tracked; close it manually if needed.", file=sys.stderr)
                print(f"Requested terminal window{target_text} (Session {session_id}).", file=sys.stderr)
            else:
                print(f"WARNING: terminal window{target_text} exited early ({code}); Session is kept.", file=sys.stderr)
        except OSError:
            print(f"WARNING: could not launch terminal window{target_text}; Session is kept.", file=sys.stderr)

    if node_id is not None:
        group, title = metadata.get(node_id, ("", ""))
        title = (group + " · " + title) if group and title else group or title
        command = [str(KONSOLE), "--separate", "--builtin-profile"]
        if title:
            command.extend(["--title", title[:128]])
        command.extend(["-e", sys.executable, "-I", "-m", "cyberlab_cli.main"])
        if test_session_bus:
            command.append("--test-session-bus")
        command.extend(["terminal", session_id, node_id])
        if slot:
            command.extend(["--slot", str(slot)])
        _spawn(command, node_id)
        return

    grouped = {}
    ungrouped = []
    for node, slot_num in slots:
        group, title = metadata.get(node, ("", ""))
        if group:
            grouped.setdefault(group, []).append((node, slot_num, title))
        else:
            ungrouped.append((node, slot_num, title))

    for group, group_slots in grouped.items():
        if len(group_slots) >= 2:
            tab_directory = tabs_dir(session_id, test_session_bus)
            safe_name = re.sub(r"[^A-Za-z0-9_-]", "_", group)[:32]
            tabfile = tab_directory / f"{session_id}_{safe_name}.tabs"
            lines = []
            for node, slot_num, title in group_slots:
                tab_title = (title if title else node) + (f" ({slot_num + 1})" if slot_num else "")
                bus_flag = " --test-session-bus" if test_session_bus else ""
                slot_flag = f" --slot {slot_num}" if slot_num else ""
                lines.append(f"title: {tab_title[:64]} ;; command: {sys.executable} -I -m cyberlab_cli.main{bus_flag} terminal {session_id} {node}{slot_flag}\n")
            tabfile.write_text("".join(lines), encoding="utf-8")
            tabfile.chmod(0o600)
            command = [str(KONSOLE), "--separate", "--builtin-profile", "--title", group[:128], "--tabs-from-file", str(tabfile)]
            _spawn(command, group)
        else:
            ungrouped.extend(group_slots)

    for node, slot_num, title in ungrouped:
        group = metadata.get(node, ("", ""))[0]
        display_title = (group + " · " + title) if group and title else group or title
        command = [str(KONSOLE), "--separate", "--builtin-profile"]
        if display_title:
            command.extend(["--title", display_title[:128]])
        command.extend(["-e", sys.executable, "-I", "-m", "cyberlab_cli.main"])
        if test_session_bus:
            command.append("--test-session-bus")
        command.extend(["terminal", session_id, node])
        if slot_num:
            command.extend(["--slot", str(slot_num)])
        _spawn(command, node)


def close_terminals(session_id, test_session_bus=False):
    return close_session(session_id, test_session_bus)
