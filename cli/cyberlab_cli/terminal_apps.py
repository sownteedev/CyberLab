"""Unprivileged native terminal discovery, preferences and argv adapters."""

import argparse
import json
import os
from pathlib import Path
import shlex
import shutil
import stat
import subprocess
import tempfile


ADAPTERS = {
    "alacritty": ("Alacritty", ("alacritty",), ("Alacritty.desktop", "org.alacritty.Alacritty.desktop"), ("-e",)),
    "blackbox": ("Black Box", ("blackbox-terminal", "blackbox"), ("com.raggesilver.BlackBox.desktop",), ("--command",)),
    "foot": ("Foot", ("foot",), ("foot.desktop", "footclient.desktop"), ("--",)),
    "ghostty": ("Ghostty", ("ghostty",), ("com.mitchellh.ghostty.desktop",), ("-e",)),
    "gnome-console": ("GNOME Console", ("kgx",), ("org.gnome.Console.desktop",), ("--",)),
    "gnome-terminal": ("GNOME Terminal", ("gnome-terminal",), ("org.gnome.Terminal.desktop", "gnome-terminal.desktop"), ("--window", "--wait", "--")),
    "kitty": ("Kitty", ("kitty",), ("kitty.desktop",), ("--",)),
    "konsole": ("Konsole", ("konsole",), ("org.kde.konsole.desktop", "konsole.desktop"), ("--separate", "--builtin-profile", "-e")),
    "lxterminal": ("LXTerminal", ("lxterminal",), ("lxterminal.desktop",), ("-e",)),
    "mate-terminal": ("MATE Terminal", ("mate-terminal",), ("mate-terminal.desktop",), ("--disable-factory", "--window", "--")),
    "ptyxis": ("Ptyxis", ("ptyxis",), ("org.gnome.Ptyxis.desktop",), ("--new-window", "--")),
    "tilix": ("Tilix", ("tilix",), ("com.gexperts.Tilix.desktop",), ("--new-process", "-e")),
    "wezterm": ("WezTerm", ("wezterm",), ("org.wezfurlong.wezterm.desktop",), ("start", "--always-new-process", "--")),
    "xfce4-terminal": ("Xfce Terminal", ("xfce4-terminal",), ("xfce4-terminal.desktop",), ("--disable-server", "--execute")),
    "xterm": ("XTerm", ("xterm",), ("xterm.desktop", "debian-xterm.desktop"), ("-e",)),
}


def search_path(environment):
    return os.pathsep.join(part for part in environment.get("PATH", os.defpath).split(os.pathsep)
                           if os.path.isabs(part))


def discover(environment=None):
    environment = os.environ if environment is None else environment
    path_value = search_path(environment)
    if not path_value:
        return []
    options = []
    identities = set()
    for identifier, (name, executables, _, _) in sorted(ADAPTERS.items()):
        for executable in executables:
            resolved = shutil.which(executable, path=path_value)
            if not resolved:
                continue
            try:
                path = Path(resolved).resolve(strict=True)
                status = path.stat()
                identity = (status.st_dev, status.st_ino)
                if (not stat.S_ISREG(status.st_mode) or identity in identities
                        or "/snap/" in str(path) or "/snap/" in resolved or path.name in {"snap", "flatpak"}):
                    continue
                with path.open("rb") as stream:
                    if stream.read(4) != b"\x7fELF":
                        continue
            except OSError:
                continue
            options.append({"id": identifier, "name": name, "executable": str(path)})
            identities.add(identity)
            break
    return options


def _base(environment, key, fallback):
    value = environment.get(key, "")
    return Path(value) if os.path.isabs(value) else Path(fallback)


def preference_path(environment=None):
    environment = os.environ if environment is None else environment
    home = _base(environment, "HOME", Path.home())
    return _base(environment, "XDG_CONFIG_HOME", home / ".config") / "cyberlab" / "terminal.json"


def read_preference(environment=None):
    path = preference_path(environment)
    try:
        descriptor = os.open(path, os.O_RDONLY | os.O_NOFOLLOW | os.O_NONBLOCK | os.O_CLOEXEC)
        with os.fdopen(descriptor, encoding="utf-8") as stream:
            status = os.fstat(stream.fileno())
            if (not stat.S_ISREG(status.st_mode) or status.st_uid != os.geteuid()
                    or status.st_size > 4096 or status.st_mode & 0o022):
                raise ValueError("Unsafe terminal preference file")
            value = json.loads(stream.read(4097))
        if (not isinstance(value, dict) or value.get("version") != 1 or not isinstance(value.get("preferred"), str)
                or value.get("preferred") not in {"auto", *ADAPTERS}):
            raise ValueError("Unknown terminal preference format")
        return value["preferred"], []
    except FileNotFoundError:
        return "auto", []
    except (OSError, ValueError, UnicodeError):
        return "auto", ["invalid-config"]


def save_preference(identifier, options, environment=None):
    if os.geteuid() == 0:
        raise ValueError("Terminal preferences belong to the desktop user; do not use sudo")
    if identifier != "auto" and identifier not in {option["id"] for option in options}:
        raise ValueError("Choose auto or an available terminal ID from terminal-apps")
    path = preference_path(environment)
    path.parent.mkdir(mode=0o700, parents=True, exist_ok=True)
    status = path.parent.lstat()
    if not stat.S_ISDIR(status.st_mode) or status.st_uid != os.geteuid() or status.st_mode & 0o022:
        raise ValueError("Unsafe terminal preference directory")
    if path.is_symlink():
        raise ValueError("Terminal preferences must not be a symbolic link")
    temporary = None
    try:
        with tempfile.NamedTemporaryFile(mode="w", encoding="utf-8", dir=path.parent, delete=False) as stream:
            temporary = Path(stream.name)
            json.dump({"version": 1, "preferred": identifier}, stream)
            stream.write("\n")
            stream.flush()
            os.fsync(stream.fileno())
        os.replace(temporary, path)
    finally:
        if temporary is not None:
            temporary.unlink(missing_ok=True)


def _desktop_option(value, options):
    if not isinstance(value, str) or len(value) > 512:
        return None
    desktop_id = value.strip().split(":", 1)[0]
    return next((option for option in options if desktop_id in ADAPTERS[option["id"]][2]), None)


def _xdg_files(environment):
    home = _base(environment, "HOME", Path.home())
    roots = [_base(environment, "XDG_CONFIG_HOME", home / ".config")]
    roots.extend(Path(part) for part in environment.get("XDG_CONFIG_DIRS", "/etc/xdg").split(":")
                 if os.path.isabs(part))
    roots.extend(Path(part) / "xdg-terminal-exec"
                 for part in environment.get("XDG_DATA_DIRS", "/usr/local/share:/usr/share").split(":")
                 if os.path.isabs(part))
    desktops = [name.lower() for name in environment.get("XDG_CURRENT_DESKTOP", "").split(":")
                if name and len(name) <= 64 and all(character.isalnum() or character in "_-" for character in name)]
    names = [name + "-xdg-terminals.list" for name in desktops] + ["xdg-terminals.list"]
    return [root / name for root in roots for name in names]


def _xdg_selection(options, environment):
    path_value = search_path(environment)
    helper = shutil.which("xdg-terminal-exec", path=path_value) if path_value else None
    warnings = []
    if helper:
        try:
            help_result = subprocess.run([helper, "--help"], env=environment, stdin=subprocess.DEVNULL,
                                         capture_output=True, text=True, timeout=2, check=False)
            if help_result.returncode != 0 or "--print-id" not in help_result.stdout:
                raise ValueError("The XDG helper does not advertise query support")
            response = subprocess.run([helper, "--print-id"], env=environment, stdin=subprocess.DEVNULL,
                                      capture_output=True, text=True, timeout=2, check=False)
            selected = _desktop_option(response.stdout.strip(), options) if response.returncode == 0 else None
            if selected:
                return selected, set(), warnings
            warnings.append("xdg-unavailable")
        except (OSError, subprocess.SubprocessError, ValueError):
            warnings.append("xdg-unavailable")
    preferred = []
    exclusions = {}
    for path in _xdg_files(environment):
        try:
            descriptor = os.open(path, os.O_RDONLY | os.O_NONBLOCK | os.O_CLOEXEC)
            with os.fdopen(descriptor, encoding="utf-8") as stream:
                if not stat.S_ISREG(os.fstat(stream.fileno()).st_mode):
                    continue
                content = stream.read(65537)
            if len(content) > 65536:
                continue
        except (OSError, UnicodeError):
            continue
        for line in content.splitlines():
            value = line.strip()
            if not value or value.startswith(("#", "/")):
                continue
            directive = value[0] if value[0] in "+-" else ""
            option = _desktop_option(value[1:] if directive else value, options)
            if option is None:
                continue
            if directive:
                exclusions.setdefault(option["id"], directive == "-")
            else:
                preferred.append(option)
    excluded = {identifier for identifier, excluded in exclusions.items() if excluded}
    return (preferred[0] if preferred else None), excluded, warnings


def _executable_option(value, options, environment):
    if not value or "\x00" in value:
        return None
    path_value = search_path(environment)
    executable = value if os.path.isabs(value) else shutil.which(value, path=path_value) if path_value else None
    if executable:
        try:
            resolved = str(Path(executable).resolve(strict=True))
            return next((option for option in options if option["executable"] == resolved), None)
        except (OSError, ValueError):
            pass
    return None


def inspect_apps(preferred=None, environment=None):
    environment = os.environ.copy() if environment is None else dict(environment)
    options = discover(environment)
    if preferred is not None:
        save_preference(preferred, options, environment)
    saved, warnings = read_preference(environment)
    selected = next((option for option in options if option["id"] == saved), None)
    source = "preference"
    if saved != "auto" and selected is None:
        warnings.append("missing-preferred")
    if selected is None:
        selected, excluded, xdg_warnings = _xdg_selection(options, environment)
        warnings.extend(xdg_warnings)
        source = "xdg"
        if selected is None:
            selected = _executable_option(environment.get("TERMINAL", ""), options, environment)
            source = "environment"
        if selected is None:
            selected = _executable_option("x-terminal-emulator", options, environment)
            source = "alternative"
        if selected is None:
            selected = next((option for option in options if option["id"] not in excluded), None)
            source = "fallback"
    if selected is None:
        source = "unavailable"
        warnings.append("no-terminal")
    return {"preferred": saved, "selected": selected, "source": source, "options": options, "warnings": warnings}


def launch_command(option, command):
    identifier = option["id"]
    if identifier not in ADAPTERS or not command or any(not isinstance(part, str) or "\x00" in part for part in command):
        raise ValueError("Invalid terminal command")
    if identifier == "blackbox":
        return [option["executable"], "--command", "exec " + shlex.join(command)]
    if identifier == "tilix":
        return [option["executable"], "--new-process", "-e", shlex.join(command)]
    return [option["executable"], *ADAPTERS[identifier][3], *command]


def main():
    parser = argparse.ArgumentParser(description="Read-only native terminal discovery for the CyberLab installer")
    parser.add_argument("--probe", action="store_true", required=True)
    parser.parse_args()
    print(json.dumps({"options": discover()}, ensure_ascii=True))


if __name__ == "__main__":
    main()
