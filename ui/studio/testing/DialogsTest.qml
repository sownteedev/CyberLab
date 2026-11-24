import QtQuick
import QtQuick.Controls.Basic
import QtTest
import ".." as Studio

Item {
    id: checks
    property string screenshotFolder: ""
    readonly property var report: ({ id: "fixture-report", lab_name: "Bài thực hành mạng", lab_version: "1.0.0", status: "PASS", created_at: "2026-10-29T10:00:00Z", goals: [], results: [], artifacts: [], quiz: null, submission_ready: true })

    QtObject {
        id: api
        property bool busy: false
        property var capabilities: ["submission-review"]
        function request(arguments, done) { done({summary: {submitted: 0, valid: 0, invalid: 0}, items: []}, ""); }
    }
    QtObject {
        id: reports
        property var api: api
        property bool checking: false
        property bool loading: false
        property string error: ""
        property var report: null
        property var reports: []
        property int checksRun: 0
        property int refreshes: 0
        property string removed: ""
        function check() { checksRun++; }
        function refresh() { refreshes++; }
        function selectReport(identifier) { report = checks.report; }
        function remove(identifier) { removed = identifier; }
        function exportReport(identifier, path) { }
    }
    QtObject {
        id: terminals
        property bool loaded: true
        property bool busy: false
        property string error: ""
        property int refreshes: 0
        property var state: ({ options: [{id: "konsole", name: "Konsole"}, {id: "blackbox", name: "Black Box"}], preferred: "auto", selected: {id: "konsole", name: "Konsole"}, source: "xdg", warnings: [] })
        function refresh() { refreshes++; }
        function select(identifier) { state = Object.assign({}, state, {preferred: identifier, source: identifier === "auto" ? "xdg" : "preference"}); }
    }
    ApplicationWindow {
        id: window
        width: 1280
        height: 820
        color: Studio.Theme.surface
        visible: true

        Studio.StudioViewport {
            id: viewport
            hostWindow: window

            Studio.StudioButton {
                id: opener
                x: 24; y: 24
                text: "Nội dung phía sau"
            }
            Studio.CheckworkDialog { id: checkwork; service: reports; connected: true; returnFocus: opener }
            Studio.SubmissionReviewDialog { id: review; api: api; returnFocus: opener }
            Studio.SettingsDialog { id: settings; terminals: terminals; returnFocus: opener }
            Studio.StudioComboBox {
                id: longChoice
                visible: false
                hoverEnabled: true
                x: 300; y: 100; width: 360
                model: Array.from({length: 24}, (_, index) => "Giá trị " + (index + 1))
            }
        }
        SignalSpy { id: outside; target: opener; signalName: "clicked" }

        TestCase {
            name: "StudioDialogs"
            when: window.visible

            function item(dialog, name) {
                return findChild(dialog.contentItem, name) || findChild(dialog.header, name) || findChild(dialog.footer, name) || findChild(dialog, name);
            }
            function open(dialog) {
                dialog.open();
                tryCompare(dialog, "opened", true);
                waitForRendering(dialog.contentItem);
            }
            function init() {
                Studio.Theme.reducedMotion = true;
                Studio.Theme.themeMode = "dark";
                Studio.Theme.setZoomPercent(100);
                window.width = 1280;
                window.height = 820;
                api.busy = false;
                reports.report = null;
                reports.reports = [];
                reports.checking = false;
                reports.loading = false;
                reports.error = "";
                reports.checksRun = 0;
                reports.removed = "";
                checkwork.session = null;
                settings.sectionIndex = 0;
                terminals.select("auto");
                longChoice.currentIndex = 0;
                longChoice.visible = false;
                window.requestActivate();
                tryCompare(window, "active", true);
                opener.forceActiveFocus();
                outside.clear();
            }
            function cleanup() {
                longChoice.popup.close();
                item(checkwork, "deleteReportConfirmation").close();
                item(checkwork, "exportSubmissionPicker").reject();
                item(review, "submissionReviewPicker").reject();
                for (const dialog of [checkwork, review, settings]) {
                    dialog.close();
                    tryCompare(dialog, "visible", false);
                }
            }
            function test_combo_hover_at_edges_does_not_scroll() {
                longChoice.visible = true;
                mouseClick(longChoice);
                tryCompare(longChoice.popup, "opened", true);
                const list = longChoice.popup.contentItem;
                list.contentY = 100;
                waitForRendering(list);
                const position = list.contentY;
                mouseMove(list, list.width / 2, list.height - 2);
                wait(250);
                fuzzyCompare(list.contentY, position, 1);
                mouseMove(list, list.width / 2, 2);
                wait(250);
                fuzzyCompare(list.contentY, position, 1);
            }
            function test_combo_hover_uses_theme_surface_data() {
                return [
                    {tag: "dark", mode: "dark", hoverColor: "#242f40"},
                    {tag: "light", mode: "light", hoverColor: "#dfe2e9"}
                ];
            }
            function test_combo_hover_uses_theme_surface(data) {
                Studio.Theme.themeMode = data.mode;
                longChoice.visible = true;
                mouseClick(longChoice);
                tryCompare(longChoice.popup, "opened", true);
                const list = longChoice.popup.contentItem;
                tryVerify(() => list.itemAtIndex(1) !== null);
                const option = list.itemAtIndex(1);
                const selected = list.itemAtIndex(0);
                verify(!option.highlighted);
                mouseMove(option, option.width / 2, option.height / 2);
                waitForRendering(option);
                if (checks.screenshotFolder)
                    grabImage(window.contentItem).save(checks.screenshotFolder + "/combo-hover-" + data.mode + ".png");
                compare(option.background.color, data.hoverColor);
                compare(option.contentItem.color, Studio.Theme.textOnSurface);
                compare(selected.background.color, Studio.Theme.secondaryContainer);
                compare(longChoice.currentIndex, 0);
                mouseMove(opener);
                tryCompare(option.background, "color", Studio.Theme.transparent);
                compare(selected.background.color, Studio.Theme.secondaryContainer);
            }
            function test_combo_manual_scroll_and_keyboard_selection() {
                longChoice.visible = true;
                mouseClick(longChoice);
                tryCompare(longChoice.popup, "opened", true);
                const list = longChoice.popup.contentItem;
                const start = list.contentY;
                mouseWheel(list, list.width / 2, list.height / 2, 0, -120);
                tryVerify(() => list.contentY > start);
                longChoice.popup.close();
                tryCompare(longChoice.popup, "visible", false);
                mouseMove(opener);
                longChoice.forceActiveFocus();
                keyClick(Qt.Key_Space);
                tryCompare(longChoice.popup, "opened", true);
                for (let index = 0; index < 12; index++) keyClick(Qt.Key_Down);
                compare(longChoice.highlightedIndex, 12);
                tryVerify(() => list.contentY > start);
                keyClick(Qt.Key_Return);
                compare(longChoice.currentIndex, 12);
                tryCompare(longChoice.popup, "visible", false);
            }
            function test_combo_click_selects_value() {
                longChoice.visible = true;
                mouseClick(longChoice);
                tryCompare(longChoice.popup, "opened", true);
                tryVerify(() => longChoice.popup.contentItem.itemAtIndex(2) !== null);
                const option = longChoice.popup.contentItem.itemAtIndex(2);
                verify(option !== null);
                mouseClick(option);
                compare(longChoice.currentIndex, 2);
                tryCompare(longChoice.popup, "visible", false);
            }
            function test_empty_reports_and_focus() {
                open(checkwork);
                verify(item(checkwork, "checkworkEmptyState").visible);
                verify(!item(checkwork, "exportSubmissionButton").visible);
                verify(item(checkwork, "closeCheckworkButton").activeFocus);
                mouseClick(item(checkwork, "refreshCheckworkButton"));
                verify(reports.refreshes > 0);
                mouseClick(item(checkwork, "closeCheckworkButton"));
                tryCompare(checkwork, "visible", false);
                verify(opener.activeFocus);
            }
            function test_report_actions_and_safe_deletion() {
                reports.report = checks.report;
                reports.reports = [checks.report];
                checkwork.session = { state: "RUNNING", checkwork_enabled: true };
                open(checkwork);
                const run = item(checkwork, "runCheckworkButton");
                verify(run.activeFocus);
                mouseClick(run);
                compare(reports.checksRun, 1);
                api.busy = true;
                verify(!run.enabled && !item(checkwork, "exportSubmissionButton").enabled);
                api.busy = false;
                mouseClick(item(checkwork, "deleteReportButton"));
                const confirmation = item(checkwork, "deleteReportConfirmation");
                tryCompare(confirmation, "opened", true);
                verify(item(confirmation, "confirmCancelButton").activeFocus);
                mouseClick(item(confirmation, "confirmCancelButton"));
                compare(reports.removed, "");
                mouseClick(item(checkwork, "deleteReportButton"));
                tryCompare(confirmation, "opened", true);
                mouseClick(item(confirmation, "confirmActionButton"));
                compare(reports.removed, "fixture-report");
            }
            function test_review_picker_focus_and_clear() {
                open(review);
                const choose = item(review, "chooseSubmissionsButton");
                verify(choose.activeFocus);
                mouseClick(choose);
                const picker = item(review, "submissionReviewPicker");
                tryCompare(picker, "opened", true);
                picker.reject();
                tryCompare(picker, "visible", false);
                verify(choose.activeFocus);
                review.service.loading = true;
                verify(!choose.enabled);
                verify(item(review, "submissionReviewEmptyState").visible);
                review.service.loading = false;
                review.service.review = {summary: { submitted: 1, valid: 0, invalid: 1 }, items: [{filename: "fixture.zip", valid: false, error: "Gói thử không hợp lệ"}]};
                waitForRendering(review.contentItem);
                verify(!item(review, "submissionReviewEmptyState").visible);
                mouseClick(item(review, "closeSubmissionReviewButton"));
                tryCompare(review, "visible", false);
                compare(review.service.review, null);
                verify(opener.activeFocus);
            }
            function test_settings_actions_and_tabs() {
                open(settings);
                mouseClick(item(settings, "theme_light"));
                compare(Studio.Theme.themeMode, "light");
                mouseClick(item(settings, "theme_dark"));
                compare(item(settings, "reducedMotionSwitch"), null);
                mouseClick(item(settings, "settingsSection-1"));
                compare(settings.sectionIndex, 1);
                const sections = item(settings, "settingsSections");
                const indicator = item(sections, "settingsSection-indicator");
                compare(sections.radius, Studio.Theme.shapeFull);
                compare(indicator.radius, Studio.Theme.shapeFull);
                fuzzyCompare(indicator.x, Studio.Theme.space4 + sections.slotWidth, 1);
                tryVerify(() => item(settings, "terminalChoice") !== null);
                const choice = item(settings, "terminalChoice");
                mouseClick(choice);
                tryCompare(choice.popup, "opened", true);
                keyClick(Qt.Key_Down);
                keyClick(Qt.Key_Return);
                compare(terminals.state.preferred, "konsole");
                tryCompare(choice.popup, "visible", false);
                waitForRendering(settings.contentItem);
                const before = terminals.refreshes;
                mouseClick(item(settings, "refreshTerminalsButton"));
                compare(terminals.refreshes, before + 1);
                item(settings, "settingsSection-1").forceActiveFocus();
                keyClick(Qt.Key_Left);
                compare(settings.sectionIndex, 0);
                mouseClick(item(settings, "doneSettingsButton"));
                tryCompare(settings, "visible", false);
                verify(opener.activeFocus);
            }
            function test_username_save_validation_and_reopen() {
                Studio.LabPreferences.setUsername("student");
                open(settings);
                mouseClick(item(settings, "settingsSection-2"));
                tryVerify(() => item(settings, "defaultLabUsername") !== null);
                const field = item(settings, "defaultLabUsername");
                const save = item(settings, "saveLabUsername");
                compare(field.text, "student");
                for (const invalid of ["", "root", "nobody", "ubuntu", "../alice", "alice;id", "Alice", "a b", "_apt", "alice\n", "sơn", "a".repeat(33)]) {
                    field.text = invalid;
                    verify(!save.enabled, invalid);
                    compare(Studio.LabPreferences.username, "student");
                }
                field.text = "alice_2";
                verify(save.enabled);
                compare(item(settings, "labUsernameHome").text, "/home/alice_2");
                mouseClick(save);
                compare(Studio.LabPreferences.username, "alice_2");
                mouseClick(item(settings, "settingsSection-0"));
                mouseClick(item(settings, "settingsSection-2"));
                tryVerify(() => item(settings, "defaultLabUsername") !== null);
                compare(item(settings, "defaultLabUsername").text, "alice_2");
                item(settings, "defaultLabUsername").text = "unsaved";
                settings.close();
                tryCompare(settings, "visible", false);
                compare(Studio.LabPreferences.username, "alice_2");
                open(settings);
                compare(item(settings, "defaultLabUsername").text, "alice_2");
                Studio.LabPreferences.setUsername("student");
            }
            function test_settings_tab_selection_follows_page() {
                open(settings);
                const sections = item(settings, "settingsSections");
                const indicator = item(sections, "settingsSection-indicator");
                mouseClick(item(settings, "settingsSection-1"));
                compare(sections.currentIndex, 1);
                settings.showSection(0);
                compare(sections.currentIndex, 0);
                verify(item(settings, "settingsSection-0").selected);
                fuzzyCompare(indicator.x, Studio.Theme.space4, 1);
                settings.showSection(1);
                compare(sections.currentIndex, 1);
                settings.close();
                tryCompare(settings, "visible", false);
                settings.sectionIndex = 0;
                open(settings);
                compare(sections.currentIndex, 0);
                fuzzyCompare(indicator.x, Studio.Theme.space4, 1);
            }
            function test_settings_tab_targets_and_insets() {
                open(settings);
                const sections = item(settings, "settingsSections");
                for (let index = 0; index < 3; index++) {
                    const tab = item(settings, "settingsSection-" + index);
                    verify(tab.width >= Studio.Theme.controlHeight);
                    verify(tab.height >= Studio.Theme.controlHeight);
                    const layer = findChild(tab, "segmentedStateLayer");
                    const bounds = layer.mapToItem(sections, 0, 0, layer.width, layer.height);
                    fuzzyCompare(bounds.y, Studio.Theme.space4, 1);
                    fuzzyCompare(sections.height - bounds.y - bounds.height, Studio.Theme.space4, 1);
                    mouseClick(tab, tab.width / 2, 1);
                    compare(settings.sectionIndex, index);
                }
            }
            function test_visual_data() {
                const rows = [];
                for (const kind of ["checkwork", "review", "settings", "terminal", "username"]) {
                    for (const variant of [
                        {tag: "dark", width: 1280, height: 820, theme: "dark", zoom: 100},
                        {tag: "light", width: 1280, height: 820, theme: "light", zoom: 100},
                        {tag: "compact", width: 380, height: 740, theme: "dark", zoom: 100},
                        {tag: "zoom150", width: 1280, height: 820, theme: "dark", zoom: 150},
                        {tag: "short", width: 960, height: 600, theme: "dark", zoom: 150}
                    ]) rows.push(Object.assign({}, variant, {tag: kind + "-" + variant.tag, kind: kind}));
                }
                return rows;
            }
            function test_visual(data) {
                window.width = data.width;
                window.height = data.height;
                Studio.Theme.themeMode = data.theme;
                Studio.Theme.setZoomPercent(data.zoom);
                waitForRendering(viewport);
                const dialog = data.kind === "checkwork" ? checkwork : data.kind === "review" ? review : settings;
                if (data.kind === "terminal") settings.sectionIndex = 1;
                if (data.kind === "username") settings.sectionIndex = 2;
                open(dialog);
                const surface = dialog.background as Studio.StudioPopupSurface;
                const heading = dialog.header as Studio.StudioDialogHeader;
                verify(surface && heading);
                compare(surface.color, Studio.Theme.surface);
                compare(surface.radius, 28);
                compare(heading.objectName, "studioDialogHeader");
                compare(dialog.footer.objectName, "studioDialogFooter");
                compare(heading.padding, 24);
                const close = heading.closeButton;
                verify(close.width >= 48 && close.height >= 48);
                const bounds = dialog.background.mapToItem(null, 0, 0, dialog.width, dialog.height);
                verify(bounds.x >= 0 && bounds.y >= 0);
                verify(bounds.x + bounds.width <= window.width + 1 && bounds.y + bounds.height <= window.height + 1);
                const footer = dialog.footer.mapToItem(null, 0, 0, dialog.footer.width, dialog.footer.height);
                verify(footer.y + footer.height <= bounds.y + bounds.height + 1);
                verify(dialog.contentItem.height > 0);
                const emptyName = data.kind === "checkwork" ? "checkworkEmptyState" : "submissionReviewEmptyState";
                if (data.kind === "checkwork" || data.kind === "review") {
                    const empty = item(dialog, emptyName);
                    verify(empty.height <= empty.parent.height, "empty state fits its viewport");
                    fuzzyCompare(empty.y + empty.height / 2, empty.parent.height / 2, 1);
                }
                if (checks.screenshotFolder)
                    grabImage(window.contentItem).save(checks.screenshotFolder + "/dialog-" + data.tag + ".png");
                mouseClick(opener);
                compare(outside.count, 0);
                if (dialog.visible) keyClick(Qt.Key_Escape);
                tryCompare(dialog, "visible", false);
            }
        }
    }
}
