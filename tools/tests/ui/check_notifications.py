#!/usr/bin/env python3
"""Check Studio UI components with isolated preferences and fixture data."""

import argparse
import json
import os
from pathlib import Path
import re
import shutil
import signal
import subprocess
import tempfile

def diagnostics(output, allow_worker_init_warning=False):
    if not allow_worker_init_warning:
        return output
    known = "qt.core.qobject.connect: QObject::connect(QJSEngine, QtObject): invalid nullptr parameter"
    return "\n".join(line for line in output.splitlines() if not re.sub(r"\x1b\[[0-9;]*m", "", line).rstrip().endswith(known))


def run_probe(command, environment, root, timeout=90):
    process = subprocess.Popen(command, env=environment, cwd=root, stdout=subprocess.PIPE,
                               stderr=subprocess.STDOUT, text=True, encoding="utf-8", errors="replace", start_new_session=True)
    try:
        output, _ = process.communicate(timeout=timeout)
    except subprocess.TimeoutExpired as error:
        output = (error.output or b"").decode("utf-8", errors="replace") + "\nUI check timed out.\n"
    finally:
        if process.poll() is None:
            os.killpg(process.pid, signal.SIGTERM)
            try:
                process.wait(timeout=5)
            except subprocess.TimeoutExpired:
                os.killpg(process.pid, signal.SIGKILL)
                process.wait()
    return process.returncode, output

def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--studio", type=Path, default=Path(__file__).resolve().parents[3] / "ui/studio")
    parser.add_argument("--artifacts", type=Path)
    parser.add_argument("--native", action="store_true", help="Also load the practice/editor view in native Quickshell offscreen")
    parser.add_argument("--allow-worker-init-warning", action="store_true", help="Accept only the diagnosed Qt 6.12 WorkerScript null-connect warning; keep it in logs")
    parser.add_argument("--suite", choices=("notifications", "navigation", "library", "practice", "lifecycle", "desktop", "dialogs", "landing", "editor", "files", "software", "zoom", "labtainer", "gui", "quiz", "components", "assessment", "markdown", "updates"), default="notifications")
    arguments = parser.parse_args()
    if arguments.native and arguments.suite not in {"practice", "editor", "files"}:
        parser.error("--native checks the practice, editor and files suites")
    runner = shutil.which("qmltestrunner6") or next(
        (str(path) for path in (Path("/usr/lib/qt6/bin/qmltestrunner"), Path("/usr/lib64/qt6/bin/qmltestrunner")) if path.is_file()), None
    )
    if not runner:
        raise SystemExit("Qt 6 qmltestrunner is required; no packages were installed.")
    with tempfile.TemporaryDirectory(prefix="cyberlab-notification-check-") as temporary:
        root = Path(temporary)
        for name in ("config", "cache", "data", "runtime", "home", "probe", "artifacts"):
            (root / name).mkdir(mode=0o700)
        component = {"navigation": "NavigationTest", "notifications": "NotificationsTest", "library": "LibraryTest", "practice": "PracticeTest", "lifecycle": "LifecycleTest", "desktop": "DesktopTest", "dialogs": "DialogsTest", "landing": "DraftLandingTest", "editor": "DraftEditorTest", "software": "SoftwareEditorTest", "zoom": "ZoomTest", "labtainer": "LabtainerCompatibilityTest", "gui": "GuiSettingsTest", "files": "FileWorkspaceTest", "quiz": "QuizTest", "components": "ComponentsTest", "assessment": "AssessmentServiceTest", "markdown": "MarkdownTest", "updates": "UpdateUiTest"}[arguments.suite]
        if arguments.suite == "files":
            component = "FileWorkspaceTest"
        test = f'''import {json.dumps((arguments.studio.resolve() / "testing").as_uri())} as Checks
Checks.{component} {{ screenshotFolder: {json.dumps(str(root / "artifacts"))} }}
'''
        (root / "probe/tst_Notifications.qml").write_text(test, encoding="utf-8")
        environment = dict(os.environ)
        for name in ("DISPLAY", "WAYLAND_DISPLAY", "DBUS_SESSION_BUS_ADDRESS", "QML_IMPORT_PATH", "QML2_IMPORT_PATH"):
            environment.pop(name, None)
        environment.update(HOME=str(root / "home"), XDG_CONFIG_HOME=str(root / "config"), XDG_CONFIG_DIRS=str(root / "config"),
                           XDG_DATA_HOME=str(root / "data"), XDG_CACHE_HOME=str(root / "cache"), XDG_RUNTIME_DIR=str(root / "runtime"),
                           QT_QPA_PLATFORM="offscreen", QT_QUICK_BACKEND="software", QT_QUICK_CONTROLS_STYLE="Basic")
        if arguments.suite == "dialogs":
            environment["QT_QUICK_CONTROLS_HOVER_ENABLED"] = "1"
        result, output = run_probe([runner, "-input", str(root / "probe")], environment, root)
        if arguments.native and result == 0 and "QWARN" not in diagnostics(output, arguments.allow_worker_init_warning):
            executable = next((str(path) for path in (Path("/usr/bin/qs"), Path("/usr/bin/quickshell")) if path.is_file()), None)
            if not executable:
                raise SystemExit("Native Quickshell is required for --native; no packages were installed.")
            native = root / "native"
            shutil.copytree(arguments.studio, native)
            (native / "shell.qml").write_text('''//@ pragma UseQApplication
import QtQuick
import QtQuick.Controls.Basic
import Quickshell
ShellRoot {
    ApplicationWindow {
        width: 1000; height: 700; visible: true
        SessionView {
            anchors.fill: parent
            session: ({id: "fixture", lab_id: "fixture", state: "RUNNING", saved: false, environments: [], error: ""})
            submissionSupported: true
            persistenceSupported: true
        }
    }
    Timer {
        interval: 300; running: true
        onTriggered: { console.log("CYBERLAB_PRACTICE_LOAD_PASS"); Qt.quit(); }
    }
}
''')
            marker = "CYBERLAB_PRACTICE_LOAD_PASS"
            if arguments.suite == "editor":
                marker = "CYBERLAB_EDITOR_LOAD_PASS"
                (native / "shell.qml").write_text('''//@ pragma UseQApplication
import QtQuick
import QtQuick.Controls.Basic
import Quickshell
ShellRoot {
    QtObject {
        id: backend
        property bool busy: false
        property var capabilities: []
        function request() { throw new Error("Native editor probe must not contact a daemon"); }
    }
    Backend {
        id: errorBackend
        property int errorCount: 0
        property bool readWhileStarting: false
        property bool stoppedWhileStarting: false
        property bool startFinished: false
        property bool silentStart: false
        onErrorChanged: errorCount += 1
    }
    ApplicationWindow {
        width: 1000; height: 700; visible: true
        DraftEditor {
            anchors.fill: parent
            backend: backend
            Component.onCompleted: {
                service.policy = {allowed_images: [], software_preparation: true, software_catalog: {applications: [], packages: []}};
                service.adopt({id: "native-fixture", revision: 1, assets: [], definition: JSON.stringify({
                    metadata: {id: "fixture", name: "Fixture", version: "1"},
                    nodes: [{id: "client", image: "cyberlab/ubuntu:24.04-1", networks: []}], networks: [], terminals: []
                })}, false);
                service.section = 1;
            }
        }
    }
    Timer {
        interval: 300; running: true
        onTriggered: {
            errorBackend.reportError("Draft not found");
            errorBackend.reportError("Draft not found");
            errorBackend.prefix = ["/usr/bin/python3", "-c", "import sys,time; time.sleep(0.8 if sys.argv[1] == 'start' else 0.01); print('{}')"];
            errorBackend.request(["start", "fixture"], () => errorBackend.startFinished = true);
            errorBackend.silentStart = !errorBackend.busy && !errorBackend.loading && errorBackend.starting;
            errorBackend.request(["labs"], () => errorBackend.readWhileStarting = !errorBackend.startFinished);
            errorBackend.request(["stop", "fixture"], () => errorBackend.stoppedWhileStarting = !errorBackend.startFinished);
            completion.start();
        }
    }
    Timer {
        id: completion
        interval: 1500
        onTriggered: {
            const timeouts = errorBackend.requestTimeout(["start"]) > 7380000 && errorBackend.requestTimeout(["labs"]) === 180000;
            if (errorBackend.errorCount === 2 && errorBackend.silentStart && errorBackend.readWhileStarting && errorBackend.stoppedWhileStarting && errorBackend.startFinished && !errorBackend.busy && !errorBackend.inFlight && !errorBackend.starting && timeouts)
                console.log("CYBERLAB_EDITOR_LOAD_PASS");
            else console.error("Concurrent silent startup verification failed");
            Qt.quit();
        }
    }
}
''')
            if arguments.suite == "files":
                marker = "CYBERLAB_SYNTAX_LOAD_PASS"
                (native / "shell.qml").write_text('''//@ pragma UseQApplication
import QtQuick
import QtQuick.Controls.Basic
import Quickshell
ShellRoot {
    QtObject {
        id: backend
        property bool busy: false
        property var capabilities: ["authoring"]
        function request() { throw new Error("Syntax probe must not contact a daemon"); }
        function notify() {}
    }
    DraftService { id: editor; backend: backend }
    ApplicationWindow {
        width: 1000; height: 700; visible: true
        DraftResources {
            id: resources
            anchors.fill: parent
            editor: editor
            Component.onCompleted: {
                editor.adopt({id: "syntax-fixture", revision: 1, assets: [], definition: JSON.stringify({
                    metadata: {id: "fixture", name: "Fixture"}, nodes: [{id: "client"}], networks: [], terminals: []
                })}, false);
                editor.files.create("client", "hello.py", false);
                editor.files.edit("client", "hello.py", "print(42)");
            }
        }
    }
    Timer {
        interval: 1500; running: true
        function colored(item) {
            if (item.objectName === "fileSyntax-client:hello.py") return item.visible && item.text.includes("<font color=");
            return (item.children || []).some(child => colored(child));
        }
        onTriggered: {
            if (colored(resources)) console.log("CYBERLAB_SYNTAX_LOAD_PASS");
            else console.error("Syntax overlay did not load");
            Qt.quit();
        }
    }
}
''')
            native_result, native_output = run_probe([executable, "--path", str(native)], environment, root, timeout=15)
            output += native_output
            result = native_result or (0 if marker in native_output and "ERROR" not in diagnostics(native_output, arguments.allow_worker_init_warning) and "WARN" not in diagnostics(native_output, arguments.allow_worker_init_warning) else 1)
        if arguments.allow_worker_init_warning and diagnostics(output, True) != output:
            print("Known Qt WorkerScript initialization diagnostic accepted explicitly; original warnings retained below.")
        print(output, end="")
        if arguments.artifacts:
            arguments.artifacts.mkdir(parents=True, exist_ok=True)
            for path in (root / "artifacts").iterdir():
                shutil.copyfile(path, arguments.artifacts / path.name)
            (arguments.artifacts / f"{arguments.suite}-tests.log").write_text(output, encoding="utf-8")
        raise SystemExit(result or (1 if "QWARN" in diagnostics(output, arguments.allow_worker_init_warning) else 0))


if __name__ == "__main__":
    main()
