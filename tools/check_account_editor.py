#!/usr/bin/env python3
"""Run account QML checks offscreen with isolated preferences and process cleanup."""
import json
import argparse
import os
from pathlib import Path
import tempfile

from check_notifications import run_probe


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--artifacts", type=Path)
    arguments = parser.parse_args()
    if arguments.artifacts:
        arguments.artifacts.mkdir(parents=True, exist_ok=True)
    studio = Path(__file__).resolve().parents[1] / "ui/studio"
    with tempfile.TemporaryDirectory(prefix="cyberlab-accounts-") as directory:
        root = Path(directory)
        for name in ("home", "config", "cache", "data", "runtime", "probe"):
            (root / name).mkdir(mode=0o700)
        (root / "probe/tst_Accounts.qml").write_text(
            f'import {json.dumps((studio / "testing").as_uri())} as Checks\nChecks.AccountEditorTest {{ screenshotFolder: {json.dumps(str(arguments.artifacts.resolve()) if arguments.artifacts else "")} }}\n')
        environment = dict(os.environ)
        for name in ("DISPLAY", "WAYLAND_DISPLAY", "DBUS_SESSION_BUS_ADDRESS", "QML_IMPORT_PATH", "QML2_IMPORT_PATH"):
            environment.pop(name, None)
        environment.update(HOME=str(root / "home"), XDG_CONFIG_HOME=str(root / "config"),
                           XDG_CONFIG_DIRS=str(root / "config"), XDG_CACHE_HOME=str(root / "cache"),
                           XDG_DATA_HOME=str(root / "data"), XDG_RUNTIME_DIR=str(root / "runtime"),
                           QT_QPA_PLATFORM="offscreen", QT_QUICK_BACKEND="software", QT_QUICK_CONTROLS_STYLE="Basic")
        code, output = run_probe(["/usr/lib/qt6/bin/qmltestrunner", "-input", str(root / "probe")], environment, root)
        print(output)
        return code or int("QWARN" in output)


if __name__ == "__main__":
    raise SystemExit(main())
