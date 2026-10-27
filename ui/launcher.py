"""Run the installed Studio with the CLI from the same Python environment."""

import argparse
from importlib.resources import as_file, files
import os
from pathlib import Path
import stat
import subprocess
import sys

NATIVE_QUICKSHELL = (Path("/usr/bin/qs"), Path("/usr/bin/quickshell"))
LEGACY_QUICKSHELL = (Path("/usr/lib/cyberlab/quickshell.AppImage"),
                    Path.home() / ".local/share/cyberlab/quickshell-0.3.1.AppImage")

def native_quickshell():
    for candidate in NATIVE_QUICKSHELL:
        if not candidate.is_file() or not os.access(candidate, os.X_OK):
            continue
        executable = candidate.resolve(strict=True)
        if any(entry.stat().st_uid != 0 or entry.stat().st_mode & 0o022
               for entry in (executable, *executable.parents)):
            continue
        with executable.open("rb") as stream:
            header = stream.read(12)
        if header[:4] == b"\x7fELF" and header[8:11] not in (b"AI\x01", b"AI\x02"):
            return candidate
    return None

def resolve_quickshell(executable=None, require_native=False):
    if executable is not None:
        selected = Path(executable)
    else:
        selected = native_quickshell()
        if selected is None and not require_native:
            selected = next((path for path in LEGACY_QUICKSHELL if path.is_file()), None)
            if selected:
                print("Using an existing legacy Studio runtime; new installations use native Quickshell.", file=sys.stderr)
    if selected is None or not selected.is_absolute() or not selected.is_file() or not os.access(selected, os.X_OK):
        raise ValueError("Native Quickshell is missing. Run bash install.sh --deps-only; PATH wrappers are not used")
    if not stat.S_ISREG(selected.stat().st_mode):
        raise ValueError("Quickshell must be an executable regular file")
    return selected


def launch(executable=None, require_native=False):
    if os.geteuid() == 0:
        raise ValueError("Studio must run as the desktop user, never with sudo")
    if not (os.environ.get("DISPLAY") or os.environ.get("WAYLAND_DISPLAY")):
        raise ValueError("Studio requires a graphical desktop")
    executable = resolve_quickshell(executable, require_native)
    environment = os.environ.copy()
    for key in ("CYBERLAB_STUDIO_TEST_BUS", "CYBERLAB_STUDIO_SMOKE", "CYBERLAB_STUDIO_SCREENSHOT",
                "LD_LIBRARY_PATH", "LD_PRELOAD", "QT_PLUGIN_PATH", "QML_IMPORT_PATH",
                "QML2_IMPORT_PATH", "QT_QPA_PLATFORM", "APPIMAGE_EXTRACT_AND_RUN", "APPIMAGE", "APPDIR"):
        environment.pop(key, None)
    environment.update(CYBERLAB_STUDIO_PYTHON=sys.executable, DISABLE_AUTO_UPDATES="1",
                       QT_QUICK_CONTROLS_STYLE="Material")
    if executable.suffix == ".AppImage":
        environment["APPIMAGE_EXTRACT_AND_RUN"] = "1"
    with as_file(files("cyberlab_studio").joinpath("studio")) as configuration:
        if not (configuration / "shell.qml").is_file():
            raise ValueError("Installed package is missing Studio QML resources")
        return subprocess.call([str(executable), "--path", str(configuration)], env=environment)


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--quickshell", type=Path, help="Explicit local Quickshell executable; no download is performed")
    parser.add_argument("--require-native", action="store_true", help="Disable compatibility with an existing legacy AppImage")
    arguments = parser.parse_args()
    try:
        if arguments.require_native and arguments.quickshell:
            parser.error("--require-native cannot be combined with an explicit executable")
        return launch(arguments.quickshell, arguments.require_native)
    except (OSError, ValueError) as error:
        print(f"Cannot start CyberLab Studio: {error}", file=sys.stderr)
        return 1
    except KeyboardInterrupt:
        return 130


if __name__ == "__main__":
    raise SystemExit(main())
