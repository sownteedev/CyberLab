import QtQuick
import QtQuick.Controls.Basic
import QtQuick.Layouts
import QtTest
import ".." as Studio

Item {
    id: checks
    property string screenshotFolder: ""
    QtObject {
        id: updater
        property bool checking: false
        property bool handingOff: false
        property bool available: false
        property bool checked: false
        property string comparison: "unknown"
        property string installedCommit: ""
        property string latestCommit: "aaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaa"
        property string problem: ""
        property int calls: 0
        function check(manual) { calls++; checking = true; }
        function refresh() {}
    }
    ApplicationWindow {
        id: window
        width: 650; height: 740; visible: true
        color: Studio.Theme.surface
        palette: Studio.Theme.controlPalette
        Studio.UpdateSettings { id: settings; x: 24; y: 24; width: parent.width - 48; updater: updater }
        Studio.UpdateProgress { id: progress; x: 24; y: 24; width: parent.width - 48; visible: false }
        Studio.SettingsDialog { id: settingsDialog; terminals: updater; updater: updater }
        TestCase {
            name: "SystemUpdateUI"
            when: windowShown
            function init() {
                settingsDialog.close();
                tryCompare(settingsDialog, "visible", false);
                updater.checking = false; updater.handingOff = false; updater.available = false;
                updater.checked = false; updater.problem = ""; updater.calls = 0;
                updater.installedCommit = "";
                updater.comparison = "unknown";
                settings.visible = true; progress.visible = false;
                progress.running = true; progress.completed = false; progress.problem = "";
                progress.percent = -1; progress.received = 0; progress.phase = "waiting";
                window.width = 650;
            }
            function test_check_and_busy_state() {
                mouseClick(findChild(settings, "checkSystemUpdate"));
                compare(updater.calls, 1);
                verify(!findChild(settings, "checkSystemUpdate").enabled);
                verify(findChild(settings, "updateStatus").text.includes("Đang kiểm tra"));
            }
            function test_available_and_handoff() {
                updater.available = true;
                updater.installedCommit = "b".repeat(40);
                updater.comparison = "ahead";
                const button = findChild(settings, "installSystemUpdate");
                verify(button.visible);
                updater.handingOff = true;
                verify(!button.enabled);
            }
            function test_unknown_version_is_not_current_or_available() {
                updater.checked = true;
                compare(findChild(settings, "updateStatus").text, "Chưa xác định phiên bản");
                verify(!findChild(settings, "installSystemUpdate").visible);
            }
            function test_known_current_version() {
                updater.checked = true;
                updater.installedCommit = updater.latestCommit;
                compare(findChild(settings, "updateStatus").text, "Bạn đang dùng bản mới nhất");
            }
            function test_non_forward_versions_data() {
                return [{tag: "ahead-local", state: "behind", title: "Bản cài đi trước GitHub"},
                    {tag: "diverged", state: "diverged", title: "Bản cài khác nhánh GitHub"},
                    {tag: "unpublished", state: "unknown", title: "Chưa xác định phiên bản"}];
            }
            function test_non_forward_versions(data) {
                updater.checked = true;
                updater.installedCommit = "b".repeat(40);
                updater.comparison = data.state;
                compare(findChild(settings, "updateStatus").text, data.title);
                verify(!findChild(settings, "installSystemUpdate").visible);
                wait(50);
                if (checks.screenshotFolder) grabImage(window.contentItem).save(checks.screenshotFolder + "/update-state-" + data.tag + ".png");
            }
            function test_progress_only_measured_for_download() {
                progress.acceptEvent({event: "download", percent: 42});
                compare(progress.percent, 42);
                progress.acceptEvent({event: "build", percent: 75});
                compare(progress.percent, -1);
                verify(findChild(progress, "systemUpdateProgress").indeterminate);
            }
            function test_exit_without_complete_is_failure() {
                progress.finish(0);
                verify(!progress.completed);
                verify(progress.problem.length > 0);
            }
            function test_unknown_download_size_shows_bytes_not_fake_percent() {
                progress.acceptEvent({event: "download", percent: null, received: 1048576});
                compare(progress.percent, -1);
                verify(findChild(progress, "systemUpdatePercent").text.includes("1.0 MB"));
            }
            function test_failed_exit_overrides_complete() {
                progress.acceptEvent({event: "complete"});
                progress.finish(1);
                verify(!progress.completed);
            }
            function test_complete_requires_exit_before_restart() {
                progress.visible = true;
                settings.visible = false;
                progress.acceptEvent({event: "complete"});
                verify(!findChild(progress, "restartAfterUpdate").visible);
                progress.finish(0);
                verify(findChild(progress, "restartAfterUpdate").visible);
            }
            function test_visuals_data() {
                return [{tag:"light", mode:"light", width:650}, {tag:"dark", mode:"dark", width:650},
                    {tag:"compact", mode:"dark", width:360}];
            }
            function test_visuals(data) {
                Studio.Theme.themeMode = data.mode; window.width = data.width;
                updater.available = true;
                updater.installedCommit = "b".repeat(40);
                updater.comparison = "ahead";
                wait(50);
                if (checks.screenshotFolder) grabImage(window.contentItem).save(checks.screenshotFolder + "/update-settings-" + data.tag + ".png");
                settings.visible = false; progress.visible = true;
                progress.acceptEvent({event:"download",percent:42});
                wait(50);
                if (checks.screenshotFolder) grabImage(window.contentItem).save(checks.screenshotFolder + "/update-progress-" + data.tag + ".png");
                verify(progress.width <= window.width);
            }
            function test_settings_update_tab_data() { return [{tag:"wide",width:800}, {tag:"small",width:420}]; }
            function test_settings_update_tab(data) {
                window.width = data.width;
                updater.available = true;
                updater.installedCommit = "b".repeat(40);
                updater.comparison = "ahead";
                settingsDialog.sectionIndex = 4;
                settingsDialog.open();
                tryCompare(settingsDialog, "opened", true);
                wait(50);
                verify(findChild(settingsDialog, "installSystemUpdate").visible);
                verify(settingsDialog.width < window.width);
                if (data.width < 600) {
                    verify(findChild(settingsDialog, "settingsSectionPicker").visible);
                    verify(!findChild(settingsDialog, "settingsSections").visible);
                }
                if (checks.screenshotFolder) grabImage(window.contentItem).save(checks.screenshotFolder + "/update-dialog-" + data.tag + ".png");
            }
        }
    }
}
