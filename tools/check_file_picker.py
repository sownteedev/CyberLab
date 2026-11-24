#!/usr/bin/env python3
"""Exercise Studio's local picker offscreen, using only temporary file metadata."""

import argparse
import hashlib
import json
import os
from pathlib import Path
import shutil
import signal
import subprocess
import tempfile


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--studio", type=Path, default=Path(__file__).resolve().parents[1] / "ui/studio")
    parser.add_argument("--artifacts", type=Path)
    arguments = parser.parse_args()
    runner = shutil.which("qmltestrunner6") or next(
        (str(path) for path in (Path("/usr/lib/qt6/bin/qmltestrunner"), Path("/usr/lib64/qt6/bin/qmltestrunner")) if path.is_file()), None
    )
    if not runner:
        raise SystemExit("Qt 6 qmltestrunner is required; no packages were installed.")
    with tempfile.TemporaryDirectory(prefix="cyberlab-picker-check-") as temporary:
        root = Path(temporary)
        for name in ("config", "cache", "data", "runtime", "home", "probe", "artifacts", "files"):
            (root / name).mkdir(mode=0o700)
        fixtures = root / "files"
        (fixtures / "Mang can ban").mkdir()
        blocked = fixtures / "unreadable"
        blocked.mkdir()
        blocked.chmod(0)
        for name in ("mang-co-ban.cyberlab", "Mạng #1 % thử.cyberlab", "huong-dan.md", ".hidden.cyberlab"):
            (fixtures / name).write_text("Isolated metadata fixture.\n", encoding="utf-8")
        pictures = fixtures / "Pictures"
        pictures.mkdir()
        (pictures / "Wallpapers").mkdir()
        for index, colors in enumerate((("#104d72", "#61dcde"), ("#60428c", "#e8b9df"), ("#a84828", "#ffd67a"),
                                         ("#214e3a", "#abd17d"), ("#1d3672", "#96b9f5"), ("#a32c64", "#ffadba"))):
            (pictures / f"Landscape {index + 1}.svg").write_text(
                f'<svg xmlns="http://www.w3.org/2000/svg" width="640" height="400" viewBox="0 0 640 400">'
                f'<rect width="640" height="400" fill="{colors[0]}"/>'
                f'<circle cx="460" cy="110" r="64" fill="{colors[1]}"/>'
                f'<path d="M0 360L220 120L440 400H0Z M260 400L470 210L640 360V400Z" fill="{colors[1]}"/>'
                '</svg>', encoding="utf-8")
        before = {str(path.relative_to(fixtures)): hashlib.sha256(path.read_bytes()).hexdigest()
                  for path in fixtures.rglob("*") if path.is_file()}
        test = f'''import {json.dumps((arguments.studio.resolve() / "testing").as_uri())} as Checks
Checks.FilePickerTest {{
    fixtureFolder: {json.dumps(fixtures.as_uri())}
    screenshotFolder: {json.dumps(str(root / "artifacts"))}
}}
'''
        (root / "probe/tst_FilePicker.qml").write_text(test, encoding="utf-8")
        environment = dict(os.environ)
        for name in ("DISPLAY", "WAYLAND_DISPLAY", "DBUS_SESSION_BUS_ADDRESS", "QML_IMPORT_PATH", "QML2_IMPORT_PATH"):
            environment.pop(name, None)
        environment.update(HOME=str(root / "home"), XDG_CONFIG_HOME=str(root / "config"), XDG_CONFIG_DIRS=str(root / "config"),
                           XDG_DATA_HOME=str(root / "data"), XDG_CACHE_HOME=str(root / "cache"), XDG_RUNTIME_DIR=str(root / "runtime"),
                           QT_QPA_PLATFORM="offscreen", QT_QUICK_BACKEND="software", QT_QUICK_CONTROLS_STYLE="Basic")
        process = subprocess.Popen([runner, "-input", str(root / "probe")], env=environment, cwd=root, stdout=subprocess.PIPE,
                                   stderr=subprocess.STDOUT, text=True, encoding="utf-8", errors="replace", start_new_session=True)
        try:
            output, _ = process.communicate(timeout=90)
        finally:
            if process.poll() is None:
                os.killpg(process.pid, signal.SIGTERM)
                try:
                    process.wait(timeout=5)
                except subprocess.TimeoutExpired:
                    os.killpg(process.pid, signal.SIGKILL)
                    process.wait()
            blocked.chmod(0o700)
        print(output, end="")
        after = {str(path.relative_to(fixtures)): hashlib.sha256(path.read_bytes()).hexdigest()
                 for path in fixtures.rglob("*") if path.is_file()}
        if before != after:
            raise SystemExit("Picker unexpectedly changed fixture files.")
        if arguments.artifacts:
            arguments.artifacts.mkdir(parents=True, exist_ok=True)
            for path in (root / "artifacts").iterdir():
                shutil.copyfile(path, arguments.artifacts / path.name)
            (arguments.artifacts / "picker-tests.log").write_text(output, encoding="utf-8")
        raise SystemExit(process.returncode or (1 if "QWARN" in output else 0))


if __name__ == "__main__":
    main()
