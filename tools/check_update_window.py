#!/usr/bin/env python3
"""Exercise the native update window with a fake engine; no network or install."""
import json
import importlib.util
import os
from pathlib import Path
import shutil
import subprocess
import sys
import tempfile
from unittest.mock import patch

from check_notifications import run_probe

ROOT = Path(__file__).resolve().parents[1]


def check_handoff(environment, executable):
    sys.path.insert(0, str(ROOT / "cli"))
    package_spec = importlib.util.spec_from_file_location("cyberlab_studio", ROOT / "ui/__init__.py", submodule_search_locations=[str(ROOT / "ui")])
    package = importlib.util.module_from_spec(package_spec)
    sys.modules["cyberlab_studio"] = package
    package_spec.loader.exec_module(package)
    from cyberlab_studio import update_window
    original_spawn = subprocess.Popen
    original_access = os.access
    supervisor = []
    staged = []
    waiter = original_spawn(["/usr/bin/sleep", "30"])

    def spawn(command, **options):
        stage = Path(command[-1])
        staged.append(stage)
        (stage / "engine.py").write_text('''import json
def run_update(**kwargs):
    print(json.dumps({"event":"complete"}), flush=True)
    return 0
''')
        shell = stage / "studio/shell.qml"
        shell.write_text(shell.read_text().replace("    Process {\n        id: ready", '''    Timer {
        interval: 100; repeat: true; running: true
        onTriggered: if (!view.running) Qt.quit()
    }
    Process {
        id: ready'''))
        process = original_spawn(command, **options)
        supervisor.append(process)
        return process

    try:
        with patch.dict(os.environ, environment, clear=True), patch.object(update_window.subprocess, "Popen", side_effect=spawn), patch.object(update_window.os, "access", side_effect=lambda path, mode: True if str(path) == "/usr/bin/pkexec" else original_access(path, mode)):
            result = update_window.launch_window("a" * 40, waiter.pid, "dark")
        assert result == {"ready": True}
        assert waiter.poll() is None
        assert (staged[0] / "ready").is_file()
        waiter.terminate()
        waiter.wait(timeout=5)
        assert supervisor[0].wait(timeout=15) == 0
        assert not staged[0].exists()
        print("PASS: staged-window handshake precedes Studio exit; fake update finishes and cleans up")
    finally:
        if waiter.poll() is None:
            waiter.terminate()
            waiter.wait(timeout=5)
        for process in supervisor:
            if process.poll() is None:
                process.wait(timeout=15)
        for stage in staged:
            shutil.rmtree(stage, ignore_errors=True)


def main():
    executable = next(str(path) for path in (Path("/usr/bin/qs"), Path("/usr/bin/quickshell")) if path.is_file())
    with tempfile.TemporaryDirectory(prefix="cl-updater-", dir="/var/tmp") as directory:
        stage = Path(directory)
        for folder in ("home", "config", "data", "runtime", "cache"):
            (stage / folder).mkdir(mode=0o700)
        environment = os.environ.copy()
        for key in ("DISPLAY", "WAYLAND_DISPLAY", "DBUS_SESSION_BUS_ADDRESS", "QML_IMPORT_PATH", "QML2_IMPORT_PATH"):
            environment.pop(key, None)
        environment.update(HOME=str(stage / "home"), XDG_CONFIG_HOME=str(stage / "config"),
            XDG_DATA_HOME=str(stage / "data"), XDG_CACHE_HOME=str(stage / "cache"), XDG_RUNTIME_DIR=str(stage / "runtime"),
            QT_QPA_PLATFORM="offscreen", QT_QUICK_BACKEND="software", CYBERLAB_UPDATE_STAGE=str(stage), CYBERLAB_UPDATE_THEME="dark")
        shutil.copytree(ROOT / "ui/studio", stage / "studio")
        shutil.copyfile(ROOT / "ui/update_window.py", stage / "window.py")
        (stage / "config.json").write_text(json.dumps({"pid": 2147483647, "identity": "fixture", "commit": "a" * 40}))
        (stage / "engine.py").write_text('''import json
def run_update(**kwargs):
    assert kwargs == {"json_output": True, "commit": "a" * 40, "graphical": True}
    for event in ({"event":"download","percent":42}, {"event":"build"}, {"event":"verify"}, {"event":"complete"}):
        print(json.dumps(event), flush=True)
    return 0
''')
        shell = stage / "studio/shell.qml"
        shell.write_text((stage / "studio/update.qml").read_text().replace("    Process {\n        id: ready", '''    Timer {
        interval: 100; repeat: true; running: true
        onTriggered: if (!view.running) {
            if (view.completed && !view.problem) console.log("UPDATE_WINDOW_PASS");
            else console.error("UPDATE_WINDOW_FAIL: " + view.problem);
            Qt.quit();
        }
    }
    Process {
        id: ready'''))
        code, output = run_probe([executable, "--path", str(shell.parent)], environment, stage, timeout=15)
        print(output)
        if code or "UPDATE_WINDOW_PASS" not in output or "ReferenceError" in output or "TypeError" in output:
            return 1
        probe = stage
        (probe / "shell.qml").write_text('''//@ pragma UseQApplication
import QtQuick
import Quickshell
import "./studio" as Studio
ShellRoot {
    property int notices: 0
    property int errors: 0
    Studio.SystemUpdateService {
        id: service
        automatic: false
        onNewVersion: notices++
        onErrorOccurred: errors++
    }
    Component.onCompleted: {
        const payload = JSON.stringify({event:"checked",installed:null,latest:"aaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaa",available:true});
        service.acceptCheck(payload, 0);
        if (notices !== 0 || service.available || !service.checked) throw new Error("unknown receipt must not notify");
        service.acceptCheck(JSON.stringify({event:"checked",installed:"b".repeat(40),latest:"a".repeat(40),available:true}), 0);
        if (notices !== 1 || !service.available) throw new Error("known update must notify");
        service.acceptCheck(payload, 0);
        if (notices !== 1 || service.available || !service.checked) throw new Error("unknown receipt must clear stale update");
        service.acceptCheck(JSON.stringify({event:"checked",installed:"b".repeat(40),latest:"a".repeat(40),available:true}), 0);
        if (notices !== 1 || !service.available) throw new Error("notification deduplication");
        service.acceptCheck("invalid", 1);
        if (errors !== 0 || !service.problem) throw new Error("automatic error is not quiet");
        service.manualCheck = true;
        service.acceptCheck("invalid", 1);
        if (errors !== 1) throw new Error("manual error not reported");
        service.prefix = ["/usr/bin/python3", "-c", "import json; print(json.dumps({'event':'checked','installed':'" + "a".repeat(40) + "','latest':'" + "a".repeat(40) + "','available':False}))"];
        service.check(true);
        service.check(true);
        completion.start();
    }
    Timer {
        id: completion
        interval: 100; repeat: true
        onTriggered: if (!service.checking) {
            if (service.available || errors !== 1 || service.problem) throw new Error("CLI check result was not applied");
            console.log("UPDATE_SERVICE_PASS");
            Qt.quit();
        }
    }
}
''')
        code, output = run_probe([executable, "--path", str(probe)], environment, stage, timeout=15)
        print(output)
        if code != 0 or "UPDATE_SERVICE_PASS" not in output or "ReferenceError" in output or "TypeError" in output:
            return 1
        detached = Path(tempfile.mkdtemp(prefix="cl-updater-", dir="/var/tmp"))
        try:
            shutil.copytree(stage / "studio", detached / "studio")
            for name in ("window.py", "engine.py"):
                shutil.copyfile(stage / name, detached / name)
            (detached / "config.json").write_text(json.dumps({"pid":2147483647,"identity":"fixture","commit":"a"*40,"theme":"dark","quickshell":executable}))
            code, output = run_probe([sys.executable, "-I", str(detached / "window.py"), "supervise", str(detached)], environment, stage, timeout=15)
            print(output)
            if code or "UPDATE_WINDOW_PASS" not in output or detached.exists():
                return 1
            print("PASS: detached supervisor kept the snapshot through worker exit and cleaned it")
            check_handoff(environment, executable)
            return 0
        finally:
            shutil.rmtree(detached, ignore_errors=True)


if __name__ == "__main__":
    raise SystemExit(main())
