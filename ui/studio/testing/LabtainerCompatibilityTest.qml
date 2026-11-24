import QtQuick
import QtQuick.Controls.Basic
import QtTest
import ".." as Studio

Item {
    id: checks
    property string screenshotFolder: ""
    readonly property var blocked: ({can_import: false, runtime_ready: false, issues: [
        {code: "x11", severity: "blocker", locations: ["config/start.config:5"]},
        {code: "system_files", severity: "blocker", locations: ["shared/_system/etc/example"]},
        {code: "startup_hooks", severity: "blocker", locations: ["shared/_bin/start.sh"]},
        {code: "grading_hooks", severity: "blocker", locations: ["instr_config/pregrade.sh"]},
        {code: "image_build", severity: "review", locations: ["dockerfiles/Dockerfile.example"]}
    ]})
    QtObject {
        id: api
        property bool busy: false
        property var capabilities: ["lab-package-import", "labtainer-import", "labtainer-inspect"]
        property var calls: []
        property var response: checks.blocked
        property string failure: ""
        property bool changeEditor: false
        function notify(message, failure) { }
        function request(arguments, done) {
            calls = calls.concat([arguments]);
            if (arguments[0] === "inspect-labtainer") {
                if (changeEditor) editor.dirty = true;
                done(response, failure);
            } else {
                done({id: "fixture-draft", import_report: {}}, "");
            }
        }
    }
    QtObject {
        id: editor
        property bool dirty: false
        property var draft: null
        property string definition: "fixture"
        property int section: 0
        property int adoptions: 0
        function adopt(result, dirty) { adoptions++; }
        function refresh() { }
    }
    ApplicationWindow {
        id: window
        width: 1000
        height: 760
        visible: true
        color: Studio.Theme.surface
        Studio.LabPackageDialogs { id: dialogs; api: api; editor: editor }
        TestCase {
            name: "LabtainerCompatibility"
            when: windowShown
            readonly property var dialog: findChild(dialogs, "labtainerCompatibilityDialog")
            function init() {
                Studio.Theme.reducedMotion = true;
                Studio.Theme.themeMode = "dark";
                Studio.Theme.setZoomPercent(100);
                api.calls = [];
                api.response = checks.blocked;
                api.failure = "";
                api.changeEditor = false;
                api.capabilities = ["lab-package-import", "labtainer-import", "labtainer-inspect"];
                editor.dirty = false;
                editor.adoptions = 0;
                window.width = 1000;
                window.height = 760;
                window.requestActivate();
                tryCompare(window, "active", true);
            }
            function cleanup() {
                dialog.close();
                tryCompare(dialog, "visible", false);
            }
            function test_blocked_import_shows_report_without_creating_draft() {
                dialogs.service.importPackage("/tmp/fixture.zip");
                compare(api.calls.length, 1);
                compare(api.calls[0][0], "inspect-labtainer");
                compare(editor.adoptions, 0);
                compare(dialogs.service.importing, false);
                tryCompare(dialog, "opened", true);
                verify(dialog.modal && dialog.dim);
                compare(dialog.contentItem.count, 5);
                tryCompare(findChild(dialog, "closeLabtainerCompatibility"), "activeFocus", true);
                mouseClick(findChild(dialog, "closeLabtainerCompatibility"));
                tryCompare(dialog, "visible", false);
                compare(dialog.report, null);
            }
            function test_convertible_lab_continues_through_existing_import() {
                api.response = {can_import: true, runtime_ready: false, issues: []};
                dialogs.service.importPackage("/tmp/fixture.zip");
                compare(api.calls.length, 2);
                compare(api.calls[1][0], "import-labtainer");
                compare(editor.adoptions, 1);
                compare(dialog.visible, false);
            }
            function test_native_packages_do_not_use_labtainer_inspection() {
                dialogs.service.importPackage("/tmp/fixture.cyberlab");
                compare(api.calls.length, 1);
                compare(api.calls[0][0], "import-lab");
            }
            function test_old_daemon_uses_strict_import() {
                api.capabilities = ["lab-package-import", "labtainer-import"];
                dialogs.service.importPackage("/tmp/fixture.zip");
                compare(api.calls[0][0], "import-labtainer");
            }
            function test_inspection_failure_does_not_import() {
                api.failure = "fixture failure";
                dialogs.service.importPackage("/tmp/fixture.zip");
                compare(api.calls.length, 1);
                compare(editor.adoptions, 0);
                compare(dialog.visible, false);
                compare(dialogs.service.importing, false);
            }
            function test_edit_started_during_inspection_is_preserved() {
                api.changeEditor = true;
                api.response = {can_import: true};
                dialogs.service.importPackage("/tmp/fixture.zip");
                compare(api.calls.length, 1);
                compare(editor.adoptions, 0);
                verify(editor.dirty);
            }
            function test_small_window_scrolls_without_overflow() {
                window.width = 480;
                window.height = 560;
                dialogs.service.importPackage("/tmp/fixture.zip");
                tryCompare(dialog, "opened", true);
                waitForRendering(dialog.contentItem);
                verify(dialog.width <= window.width && dialog.height <= window.height);
                verify(dialog.contentItem.contentHeight > dialog.contentItem.height);
                keyClick(Qt.Key_Escape);
                tryCompare(dialog, "visible", false);
            }
            function test_screenshot() {
                dialogs.service.importPackage("/tmp/fixture.zip");
                tryCompare(dialog, "opened", true);
                waitForRendering(dialog.contentItem);
                if (checks.screenshotFolder) grabImage(window.contentItem).save(checks.screenshotFolder + "/labtainer-compatibility.png");
            }
        }
    }
}
