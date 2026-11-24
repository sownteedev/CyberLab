#!/usr/bin/env python3
"""Verify username preference persistence in isolated offscreen Qt processes."""

import json
import os
from pathlib import Path
import shutil
import signal
import subprocess
import tempfile

def main():
    studio = Path(__file__).resolve().parents[1] / "ui/studio"
    runner = shutil.which("qmltestrunner6") or "/usr/lib/qt6/bin/qmltestrunner"
    with tempfile.TemporaryDirectory(prefix="cyberlab-username-prefs-") as temporary:
        root = Path(temporary)
        for name in ("home", "config", "cache", "data", "runtime", "probe"):
            (root / name).mkdir(mode=0o700)
        environment = dict(os.environ)
        for name in ("DISPLAY", "WAYLAND_DISPLAY", "DBUS_SESSION_BUS_ADDRESS", "QML_IMPORT_PATH", "QML2_IMPORT_PATH"):
            environment.pop(name, None)
        environment.update(HOME=str(root / "home"), XDG_CONFIG_HOME=str(root / "config"),
                           XDG_CONFIG_DIRS=str(root / "config"), XDG_CACHE_HOME=str(root / "cache"),
                           XDG_DATA_HOME=str(root / "data"), XDG_RUNTIME_DIR=str(root / "runtime"),
                           QT_QPA_PLATFORM="offscreen", QT_QUICK_BACKEND="software", QT_QUICK_CONTROLS_STYLE="Basic")
        phases = {
            "save": '''compare(Studio.LabPreferences.username, "student");
                verify(Studio.LabPreferences.setUsername("alice"));
                verify(!Studio.LabPreferences.setUsername("root"));
                compare(Studio.LabPreferences.username, "alice");''',
            "restart": '''compare(Studio.LabPreferences.username, "alice");
                Studio.LabPreferences.storage.username = "../../invalid";
                Studio.LabPreferences.storage.sync();''',
            "corrupt": '''compare(Studio.LabPreferences.username, "student");
                verify(Studio.LabPreferences.invalidStoredValue);
                compare(Studio.LabPreferences.storage.username, "../../invalid");
                verify(Studio.LabPreferences.setUsername("bob_2"));''',
            "repaired_restart": '''compare(Studio.LabPreferences.username, "bob_2");
                verify(!Studio.LabPreferences.invalidStoredValue);''',
        }
        for phase, assertions in phases.items():
            (root / "probe/tst_Preferences.qml").write_text(f'''import QtQuick
import QtTest
import {json.dumps(studio.as_uri())} as Studio
TestCase {{
    name: "UsernamePreferences_{phase}"
    function test_persistence() {{ {assertions} }}
}}
''')
            process = subprocess.Popen([runner, "-input", str(root / "probe")], env=environment, cwd=root,
                                       stdout=subprocess.PIPE, stderr=subprocess.STDOUT, text=True, start_new_session=True)
            try:
                output, _ = process.communicate(timeout=30)
            finally:
                if process.poll() is None:
                    os.killpg(process.pid, signal.SIGTERM)
                    try:
                        process.wait(timeout=5)
                    except subprocess.TimeoutExpired:
                        os.killpg(process.pid, signal.SIGKILL)
                        process.wait()
            print(output, end="")
            if process.returncode or "QWARN" in output:
                raise SystemExit(1)

if __name__ == "__main__":
    main()
