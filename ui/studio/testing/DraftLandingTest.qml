import QtQuick
import QtQuick.Controls.Basic
import QtTest
import ".." as Studio

Item {
    id: checks

    property string screenshotFolder: ""
    readonly property var topicChoices: [
        {id: "linux", label: "Linux"}, {id: "scripting", label: "Lập trình & Script"},
        {id: "networking", label: "Mạng máy tính"}, {id: "network-services", label: "Dịch vụ mạng"},
        {id: "network-security", label: "Bảo mật mạng"}, {id: "system-security", label: "Bảo mật hệ thống"},
        {id: "web-security", label: "Bảo mật Web"}, {id: "databases", label: "Cơ sở dữ liệu"},
        {id: "cryptography", label: "Mật mã học"}, {id: "software-security", label: "An toàn phần mềm"},
        {id: "forensics", label: "Điều tra & Ứng cứu"}, {id: "containers", label: "Container"}
    ]
    function fixtures(count) {
        return Array.from({length: count}, (_, index) => ({
            id: "fixture-" + (index + 1), lab_id: "mang-co-ban-" + (index + 1),
            name: index === 0 ? "Mạng cơ bản" : "Bài thực hành mạng " + (index + 1), revision: 1
        }));
    }
    QtObject {
        id: backend
        property bool busy: false
    }
    QtObject {
        id: editor
        readonly property var backend: checks.backendObject
        property bool dirty: false
        property var draft: null
        property var drafts: []
        property var created: []
        property string opened: ""
        property int refreshes: 0
        property var policy: ({topic_catalog: checks.topicChoices})
        function create(identifier, title, tags, difficulty) { created = [identifier, title, tags, difficulty]; }
        function openDraft(identifier) { opened = identifier; }
        function refresh() { refreshes++; }
    }
    readonly property var backendObject: backend

    ApplicationWindow {
        id: window

        width: 1280
        height: 820
        visible: true
        color: Studio.Theme.surface
        font.family: Studio.Theme.fontFamily
        header: Item {
            implicitHeight: bar.implicitHeight * Studio.Theme.zoomFactor

            Studio.AppBar {
                id: bar
                width: window.width / Studio.Theme.zoomFactor
                scale: Studio.Theme.zoomFactor
                transformOrigin: Item.TopLeft
                currentIndex: 2
                connected: true
            }
        }
        Studio.StudioViewport {
            id: viewport
            hostWindow: window

            Studio.DraftLanding {
                id: landing
                anchors.fill: parent
                anchors.margins: Studio.Theme.contentInset
                anchors.topMargin: 0
                editor: editor
            }
        }
        SignalSpy { id: resumeSpy; target: landing; signalName: "resumeRequested" }
        TestCase {
            name: "StudioDraftLanding"
            when: window.visible

            function control(name) { return findChild(landing, name); }
            function test_hint_only_when_changes_need_saving() {
                const hint = control("draftLandingHint");
                const card = control("newDraftCard");
                verify(!hint.visible);
                const cleanHeight = card.implicitHeight;
                editor.dirty = true;
                tryCompare(hint, "visible", true);
                verify(hint.text.includes("Lưu thay đổi"));
                tryVerify(() => card.implicitHeight > cleanHeight);
                editor.dirty = false;
                tryCompare(hint, "visible", false);
                tryCompare(card, "implicitHeight", cleanHeight);
            }
            function init() {
                Studio.Theme.reducedMotion = true;
                Studio.Theme.themeMode = "dark";
                Studio.Theme.setZoomPercent(100);
                window.width = 1280;
                window.height = 820;
                backend.busy = false;
                editor.dirty = false;
                editor.draft = null;
                editor.drafts = checks.fixtures(1);
                editor.created = [];
                editor.opened = "";
                editor.refreshes = 0;
                control("newDraftTitle").text = "";
                control("newDraftId").text = "";
                control("newDraftTopics").selectedTags = [];
                const difficulty = control("newDraftDifficulty");
                if (difficulty) difficulty.currentIndex = 0;
                landing.contentItem.contentY = 0;
                resumeSpy.clear();
                window.requestActivate();
                tryCompare(window, "active", true);
                landing.forceActiveFocus();
                mouseMove(window.contentItem, window.width - 2, window.height - 90);
                waitForRendering(landing);
            }
            function test_form_validation_and_enter() {
                const title = control("newDraftTitle");
                const identifier = control("newDraftId");
                const create = control("createDraftButton");
                verify(!create.enabled);
                title.text = "   ";
                identifier.text = "  ";
                identifier.forceActiveFocus();
                keyClick(Qt.Key_Return);
                compare(editor.created.length, 0);
                title.text = "  Bài mới  ";
                verify(!create.enabled);
                identifier.text = "  bai-moi  ";
                verify(!create.enabled);
                control("newDraftTopics").selectedTags = ["linux"];
                verify(!create.enabled, "A new draft requires an explicit difficulty");
                const difficulty = control("newDraftDifficulty");
                verify(difficulty !== null);
                difficulty.currentIndex = 2;
                verify(create.enabled);
                title.forceActiveFocus();
                keyClick(Qt.Key_Return);
                verify(identifier.activeFocus);
                keyClick(Qt.Key_Return);
                compare(editor.created, ["bai-moi", "Bài mới", ["linux"], "medium"]);
                editor.created = [];
                mouseClick(create);
                compare(editor.created, ["bai-moi", "Bài mới", ["linux"], "medium"]);
            }
            function cleanup() {
                control("newDraftTopics").dialog.close();
                tryCompare(control("newDraftTopics").dialog, "visible", false);
            }
            function test_topic_picker_apply_and_cancel() {
                const picker = control("newDraftTopics");
                mouseClick(picker);
                tryCompare(picker.dialog, "opened", true);
                verify(!findChild(picker.dialog, "applyTopics").enabled);
                tryVerify(() => findChild(picker.dialog.contentItem, "topic-linux") !== null);
                waitForRendering(picker.dialog.contentItem);
                mouseClick(findChild(picker.dialog.contentItem, "topic-linux"));
                compare(picker.dialog.pendingTags, ["linux"]);
                picker.dialog.reject();
                tryCompare(picker.dialog, "visible", false);
                compare(picker.selectedTags, []);
                mouseClick(picker);
                tryCompare(picker.dialog, "opened", true);
                waitForRendering(picker.dialog.contentItem);
                if (checks.screenshotFolder) grabImage(window.contentItem).save(checks.screenshotFolder + "/topic-picker.png");
                mouseClick(findChild(picker.dialog.contentItem, "topic-linux"));
                tryCompare(picker.dialog, "pendingTags", ["linux"]);
                waitForRendering(picker.dialog.contentItem);
                mouseClick(findChild(picker.dialog, "applyTopics"));
                compare(picker.selectedTags, ["linux"]);
            }
            function test_topic_picker_responsive_data() {
                return [{tag: "desktop", width: 1280, zoom: 100}, {tag: "compact", width: 380, zoom: 100}, {tag: "zoom150", width: 1000, zoom: 150}];
            }
            function test_topic_picker_responsive(data) {
                window.width = data.width;
                Studio.Theme.setZoomPercent(data.zoom);
                const picker = control("newDraftTopics");
                picker.forceActiveFocus(Qt.TabFocusReason);
                waitForRendering(landing);
                keyClick(Qt.Key_Space);
                tryCompare(picker.dialog, "opened", true);
                waitForRendering(picker.dialog.contentItem);
                const last = findChild(picker.dialog.contentItem, "topic-containers");
                last.forceActiveFocus(Qt.TabFocusReason);
                waitForRendering(picker.dialog.contentItem);
                keyClick(Qt.Key_Space);
                compare(picker.dialog.pendingTags, ["containers"]);
                const bounds = last.mapToItem(picker.dialog.contentItem, 0, 0, last.width, last.height);
                if (checks.screenshotFolder) grabImage(window.contentItem.parent).save(checks.screenshotFolder + "/topics-" + data.tag + ".png");
                verify(bounds.y >= -1 && bounds.y + bounds.height <= picker.dialog.contentItem.height + 1,
                       JSON.stringify({bounds: bounds, height: picker.dialog.contentItem.height, offset: picker.dialog.contentItem.contentItem.contentY}));
                picker.dialog.reject();
                compare(picker.selectedTags, []);
            }
            function test_open_refresh_and_keyboard() {
                const row = control("savedDraft-fixture-1");
                mouseClick(row);
                compare(editor.opened, "fixture-1");
                editor.opened = "";
                row.forceActiveFocus();
                keyClick(Qt.Key_Space);
                compare(editor.opened, "fixture-1");
                mouseClick(control("refreshDraftsButton"));
                compare(editor.refreshes, 1);
                compare(control("savedDraftsCount").text, "1");
            }
            function test_busy_and_unsaved_work_guards() {
                editor.draft = {id: "fixture-1"};
                control("newDraftTitle").text = "Bài mới";
                control("newDraftId").text = "bai-moi";
                backend.busy = true;
                for (const name of ["newDraftTitle", "newDraftId", "createDraftButton", "savedDraft-fixture-1", "refreshDraftsButton", "resumeDraftButton"])
                    verify(!control(name).enabled, name);
                backend.busy = false;
                editor.dirty = true;
                verify(!control("createDraftButton").enabled);
                verify(!control("savedDraft-fixture-1").enabled);
                verify(control("draftLandingHint").text.includes("Lưu thay đổi"));
                mouseClick(control("resumeDraftButton"));
                compare(resumeSpy.count, 1);
                verify(editor.dirty);
                compare(editor.created.length, 0);
                compare(editor.opened, "");
            }
            function test_empty_state_and_aligned_cards() {
                const form = control("newDraftCard");
                const saved = control("savedDraftsCard");
                verify(landing.wide);
                verify(form.width > 380);
                verify(saved.height < form.height);
                editor.drafts = [];
                waitForRendering(landing);
                verify(control("draftListEmpty").visible);
                verify(!control("savedDraftsList").visible);
                compare(control("savedDraftsCount").text, "0");
                fuzzyCompare(form.height, form.implicitHeight, 1);
            }
            function test_creation_card_height_independent_of_draft_count() {
                const form = control("newDraftCard");
                const saved = control("savedDraftsCard");
                const originalHeight = form.height;
                for (const count of [0, 1, 6, 60]) {
                    editor.drafts = checks.fixtures(count);
                    waitForRendering(landing);
                    fuzzyCompare(form.height, originalHeight, 1);
                    fuzzyCompare(form.y, saved.y, 1);
                    if (count >= 6) verify(saved.height > form.height);
                }
            }
            function test_many_drafts_remain_scrollable() {
                editor.drafts = checks.fixtures(60);
                const list = control("savedDraftsList");
                tryCompare(list, "count", 60);
                waitForRendering(list);
                verify(list.interactive && list.contentHeight > list.height);
                list.positionViewAtIndex(59, ListView.End);
                list.forceLayout();
                tryVerify(() => control("savedDraft-fixture-60") !== null);
                const last = control("savedDraft-fixture-60");
                last.forceActiveFocus();
                waitForRendering(list);
                mouseClick(last);
                compare(editor.opened, "fixture-60");
                compare(editor.drafts.length, 60);
            }
            function test_focus_scrolls_at_high_zoom() {
                window.width = 400;
                window.height = 600;
                Studio.Theme.setZoomPercent(150);
                waitForRendering(viewport);
                verify(!landing.wide);
                verify(landing.contentHeight > landing.height);
                const identifier = control("newDraftId");
                identifier.forceActiveFocus(Qt.TabFocusReason);
                waitForRendering(landing);
                const bounds = identifier.mapToItem(landing, 0, 0, identifier.width, identifier.height);
                verify(bounds.y >= 0);
                verify(bounds.y + bounds.height <= landing.availableHeight + 1);
            }
            function test_visual_data() {
                return [
                    {tag: "desktop-dark", width: 1280, height: 820, theme: "dark", zoom: 100, count: 5},
                    {tag: "desktop-light", width: 1280, height: 820, theme: "light", zoom: 100, count: 3},
                    {tag: "empty", width: 1280, height: 820, theme: "dark", zoom: 100, count: 0},
                    {tag: "many", width: 1280, height: 820, theme: "dark", zoom: 100, count: 60},
                    {tag: "compact", width: 380, height: 740, theme: "dark", zoom: 100, count: 2},
                    {tag: "zoom150", width: 1280, height: 820, theme: "dark", zoom: 150, count: 3},
                    {tag: "short", width: 960, height: 600, theme: "dark", zoom: 150, count: 1},
                    {tag: "wide", width: 2000, height: 980, theme: "dark", zoom: 100, count: 3},
                    {tag: "zoom70", width: 1280, height: 820, theme: "light", zoom: 70, count: 3},
                    {tag: "unsaved", width: 1280, height: 820, theme: "dark", zoom: 100, count: 2, dirty: true},
                    {tag: "return-five", width: 1480, height: 1005, theme: "dark", zoom: 100, count: 5, current: true}
                ];
            }
            function test_visual(data) {
                window.width = data.width;
                window.height = data.height;
                Studio.Theme.themeMode = data.theme;
                Studio.Theme.setZoomPercent(data.zoom);
                editor.drafts = checks.fixtures(data.count);
                editor.dirty = !!data.dirty;
                editor.draft = data.dirty || data.current ? {id: "fixture-1"} : null;
                waitForRendering(viewport);
                const page = control("draftLandingPage");
                const form = control("newDraftCard");
                const saved = control("savedDraftsCard");
                fuzzyCompare(page.width, landing.availableWidth - Studio.Theme.space24, 1);
                if (data.tag === "wide") {
                    verify(page.width > 1700);
                    verify(form.width > 500);
                    verify(saved.width > 900);
                }
                fuzzyCompare(page.x, (landing.availableWidth - page.width) / 2, 1);
                compare(form.color, Studio.Theme.surfaceContainerLow);
                if (landing.wide) {
                    fuzzyCompare(form.y, saved.y, 1);
                    fuzzyCompare(form.height, form.implicitHeight, 1);
                    const createHeader = control("newDraftHeader");
                    const savedHeader = control("savedDraftsHeader");
                    fuzzyCompare(createHeader.mapToItem(page, 0, 0).y, savedHeader.mapToItem(page, 0, 0).y, 1);
                    fuzzyCompare(createHeader.height, savedHeader.height, 1);
                    fuzzyCompare(saved.x - form.x - form.width, Studio.Theme.space24, 1);
                } else {
                    fuzzyCompare(saved.y - form.y - form.height, Studio.Theme.space24, 1);
                }
                fuzzyCompare(control("createDraftButton").width, control("newDraftTitle").width, 1);
                for (const name of ["newDraftTitle", "newDraftId", "createDraftButton"]) {
                    const target = control(name);
                    const bounds = target.mapToItem(page, 0, 0, target.width, target.height);
                    verify(bounds.x >= 0 && bounds.x + bounds.width <= page.width + 1, name);
                    verify(target.height >= Studio.Theme.controlHeight, name);
                }
                if (checks.screenshotFolder)
                    grabImage(window.contentItem.parent).save(checks.screenshotFolder + "/landing-" + data.tag + ".png");
            }
        }
    }
}
