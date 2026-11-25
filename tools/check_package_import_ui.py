#!/usr/bin/env python3
"""Exercise the package service offscreen without a daemon or user data."""
import argparse
import os
from pathlib import Path
import shutil
import tempfile

from check_notifications import run_probe

ROOT = Path(__file__).resolve().parents[1]
QML = '''import QtQuick
import QtTest

TestCase {
    id: checks
    name: "PackageImport"
    property int reloads: 0
    property int opened: 0
    property QtObject backend: QtObject {
        property bool busy: false
        property var capabilities: ["lab-package-import", "lab-package-export", "labtainer-import"]
        property var response: ({installed: true, lab_id: "received", edit_protected: false})
        property string failure: ""
        property var calls: []
        property var notices: []
        property bool deferred: false
        property var pending: null
        function request(arguments, done) {
            calls = calls.concat([arguments]);
            if (deferred) pending = done;
            else done(response, failure);
        }
        function notify(message, error) { notices = notices.concat([{message, error}]); }
    }
    property QtObject editorObject: QtObject {
        property bool dirty: false
        property var draft: ({id: "existing"})
        property string definition: "existing definition"
        property int section: 3
        property int adoptions: 0
        property int refreshes: 0
        function adopt(result, dirty) { adoptions++; }
        function refresh() { refreshes++; }
    }
    property LabPackageService packages: LabPackageService {
        api: checks.backend
        editor: checks.editorObject
        onLibraryReloadRequested: checks.reloads++
        onDraftOpened: checks.opened++
    }
    function init() {
        reloads = 0;
        opened = 0;
        backend.calls = [];
        backend.notices = [];
        backend.failure = "";
        backend.deferred = false;
        backend.pending = null;
        backend.response = {installed: true, lab_id: "received", edit_protected: false};
        editorObject.dirty = false;
        editorObject.definition = "existing definition";
        editorObject.section = 3;
        editorObject.adoptions = 0;
        editorObject.refreshes = 0;
    }
    function test_native_install_data() {
        return [{tag: "unprotected", protected: false}, {tag: "protected", protected: true}];
    }
    function test_native_install(data) {
        backend.response.edit_protected = data.protected;
        packages.importPackage("/temporary/fixture.cyberlab");
        compare(backend.calls, [["import-lab", "/temporary/fixture.cyberlab"]]);
        compare(reloads, 1);
        compare(opened, 0);
        compare(editorObject.adoptions, 0);
        compare(editorObject.refreshes, 0);
        compare(editorObject.definition, "existing definition");
        compare(editorObject.section, 3);
        compare(backend.notices.length, 1);
        compare(backend.notices[0].error, false);
        compare(packages.importing, false);
    }
    function test_import_completion_preserves_new_editor_work() {
        backend.deferred = true;
        packages.importPackage("/temporary/fixture.cyberlab");
        compare(packages.importing, true);
        editorObject.definition = "new unsaved work";
        editorObject.dirty = true;
        backend.pending(backend.response, "");
        compare(reloads, 1);
        compare(editorObject.adoptions, 0);
        compare(editorObject.definition, "new unsaved work");
        compare(editorObject.dirty, true);
        compare(packages.importing, false);
    }
    function test_labtainer_remains_a_draft() {
        backend.response = {id: "converted", import_report: {}};
        packages.importPackage("/temporary/fixture.zip");
        compare(backend.calls[0][0], "import-labtainer");
        compare(reloads, 0);
        compare(opened, 1);
        compare(editorObject.adoptions, 1);
        compare(editorObject.refreshes, 1);
    }
    function test_failed_import_never_opens_or_refreshes() {
        backend.failure = "ID collision";
        packages.importPackage("/temporary/fixture.cyberlab");
        compare(reloads, 0);
        compare(opened, 0);
        compare(editorObject.adoptions, 0);
        compare(backend.notices.length, 0);
        compare(packages.importing, false);
    }
    function test_installed_export_uses_public_operation() {
        packages.exportPackage({kind: "lab", id: "locked"}, "/temporary/export.cyberlab");
        compare(backend.calls, [["export-lab", "locked", "/temporary/export.cyberlab"]]);
    }
}
'''


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--service", type=Path, default=ROOT / "ui/studio/services/LabPackageService.qml")
    arguments = parser.parse_args()
    runner = shutil.which("qmltestrunner6") or "/usr/lib/qt6/bin/qmltestrunner"
    if not Path(runner).is_file():
        raise SystemExit("Qt 6 qmltestrunner is required; no packages were installed")
    with tempfile.TemporaryDirectory(prefix="cyberlab-package-ui-") as temporary:
        root = Path(temporary)
        for name in ("home", "config", "cache", "data", "runtime"):
            (root / name).mkdir(mode=0o700)
        shutil.copyfile(arguments.service, root / "LabPackageService.qml")
        (root / "tst_PackageImport.qml").write_text(QML)
        environment = dict(os.environ)
        for name in ("DISPLAY", "WAYLAND_DISPLAY", "DBUS_SESSION_BUS_ADDRESS", "QML_IMPORT_PATH", "QML2_IMPORT_PATH"):
            environment.pop(name, None)
        environment.update(HOME=str(root / "home"), XDG_CONFIG_HOME=str(root / "config"),
                           XDG_CONFIG_DIRS=str(root / "config"), XDG_DATA_HOME=str(root / "data"),
                           XDG_CACHE_HOME=str(root / "cache"), XDG_RUNTIME_DIR=str(root / "runtime"),
                           QT_QPA_PLATFORM="offscreen", QT_QUICK_BACKEND="software")
        result, output = run_probe([runner, "-input", str(root)], environment, root, timeout=30)
        print(output, end="")
        raise SystemExit(result or (1 if "QWARN" in output else 0))


if __name__ == "__main__":
    main()
