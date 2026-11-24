import QtQuick
import QtQuick.Controls.Basic
import QtTest
import ".." as Studio

Item {
    id: checks

    property string screenshotFolder: ""
    Component { id: preloadedLibrary; Studio.LibraryView { } }
    Component { id: topicIcon; Studio.Icon { } }
    readonly property var fixtures: Array.from({length: 12}, (_, index) => ({
        id: "fixture-" + (index + 1), name: "Bài thực hành " + (index + 1), version: "1.0.0",
        description: "Dữ liệu kiểm tra giao diện", networks: ["lan"], nodes: ["client"], environments: [], quiz: [],
        tags: index % 3 === 0 ? ["linux", "system-security"] : index % 3 === 1 ? ["networking"] : [],
        tag_labels: {linux: "Linux", "system-security": "Bảo mật hệ thống", networking: "Mạng máy tính"}
    }))

    ApplicationWindow {
        id: window

        width: 1280
        height: 800
        visible: true
        color: Studio.Theme.surface
        header: Item {
            implicitHeight: bar.implicitHeight * Studio.Theme.zoomFactor

            Studio.AppBar {
                id: bar
                width: parent.width / Studio.Theme.zoomFactor
                scale: Studio.Theme.zoomFactor
                transformOrigin: Item.TopLeft
                connected: true
            }
        }
        Studio.StudioViewport {
            hostWindow: window

            Studio.LibraryView {
                id: library

                anchors.fill: parent
                anchors.margins: Studio.Theme.contentInset
                anchors.topMargin: 0
                manual: "# Khám phá mạng riêng\n\nChọn bài lab và bắt đầu thực hành trong môi trường cách ly."

                onSelectLabRequested: lab => { selectedLab = lab; }
            }
        }
        SignalSpy { id: importSpy; target: library; signalName: "importPackageRequested" }
        SignalSpy { id: exportSpy; target: library; signalName: "exportPackageRequested" }
        SignalSpy { id: reportsSpy; target: library; signalName: "reportsRequested" }
        SignalSpy { id: reviewSpy; target: library; signalName: "reviewSubmissionsRequested" }
        SignalSpy { id: resumeSpy; target: library; signalName: "resumeSessionRequested" }
        SignalSpy { id: openSessionSpy; target: library; signalName: "openSessionRequested" }

        TestCase {
            name: "LibraryLayout"
            when: window.visible

            function control(name) { return findChild(library, name); }
            function menu() { return control("libraryToolsMenu"); }
            function openTools() {
                mouseClick(control("libraryToolsToggle"));
                tryCompare(menu(), "opened", true);
            }
            function init() {
                Studio.Theme.themeMode = "dark";
                Studio.Theme.reducedMotion = true;
                Studio.Theme.setZoomPercent(100);
                window.width = 1280;
                window.height = 800;
                library.labs = checks.fixtures;
                library.selectedLab = checks.fixtures[0];
                library.sessions = [];
                library.connected = true;
                library.busy = false;
                library.starting = false;
                library.packageSupported = true;
                library.reportsSupported = true;
                library.reviewSupported = true;
                library.showDetails = false;
                control("libraryToolbar").selectedTags = [];
                control("librarySearch").text = "";
                control("libraryToolbar").selectedDifficulty = "";
                window.requestActivate();
                tryCompare(window, "active", true);
                importSpy.clear(); exportSpy.clear(); reportsSpy.clear(); reviewSpy.clear();
                resumeSpy.clear();
                openSessionSpy.clear();
                mouseMove(window.contentItem, window.width - 10, window.height - 90);
                waitForRendering(library);
            }
            function cleanup() {
                control("libraryFilterDialog").close();
                menu().close();
                tryCompare(menu(), "visible", false);
            }
            function test_difficulty_combines_with_topics_and_search() {
                library.labs = [
                    Object.assign({}, checks.fixtures[0], {id: "easy-one", name: "Alpha", difficulty: "easy"}),
                    Object.assign({}, checks.fixtures[0], {id: "hard-one", name: "Alpha", difficulty: "hard"}),
                    Object.assign({}, checks.fixtures[1], {id: "hard-two", name: "Beta", difficulty: "hard"}),
                    Object.assign({}, checks.fixtures[0], {id: "legacy", name: "Alpha"})
                ];
                const difficulty = control("libraryToolbar");
                verify(difficulty !== null);
                difficulty.selectedDifficulty = "hard";
                compare(library.matchingLabs("").map(lab => lab.id), ["hard-one", "hard-two"]);
                control("libraryToolbar").selectedTags = ["linux"];
                compare(library.matchingLabs("alpha").map(lab => lab.id), ["hard-one"]);
                compare(library.matchingLabs("beta").length, 0);
                difficulty.selectedDifficulty = "unclassified";
                compare(library.matchingLabs("alpha").map(lab => lab.id), ["legacy"]);
                difficulty.selectedDifficulty = "";
                compare(library.matchingLabs("alpha").length, 3);
            }
            function test_unified_filter_button_opens_all_filters() {
                const button = control("libraryFilterButton");
                verify(button !== null, "One button should open both filters");
                mouseClick(button);
                const dialog = control("libraryFilterDialog");
                tryCompare(dialog, "opened", true);
                verify(findChild(dialog.contentItem, "difficulty-easy").visible);
                verify(findChild(dialog.contentItem, "topic-linux").visible);
                dialog.reject();
                tryCompare(dialog, "visible", false);
            }
            function test_filter_popup_apply_cancel_and_clear_both_filters() {
                const toolbar = control("libraryToolbar");
                const dialog = control("libraryFilterDialog");
                const button = control("libraryFilterButton");
                toolbar.query = "Bài";
                mouseClick(button);
                tryCompare(dialog, "opened", true);
                waitForRendering(dialog.contentItem);
                mouseClick(findChild(dialog.contentItem, "difficulty-hard"));
                mouseClick(findChild(dialog.contentItem, "topic-linux"));
                compare(toolbar.selectedTags, []);
                compare(toolbar.selectedDifficulty, "");
                mouseClick(findChild(dialog.footer, "applyLibraryFilters"));
                tryCompare(dialog, "visible", false);
                compare(toolbar.selectedTags, ["linux"]);
                compare(toolbar.selectedDifficulty, "hard");
                mouseClick(button);
                tryCompare(dialog, "opened", true);
                waitForRendering(dialog.contentItem);
                compare(dialog.pendingTags, ["linux"]);
                compare(dialog.pendingDifficulty, "hard");
                dialog.pendingTags = ["networking"];
                dialog.pendingDifficulty = "easy";
                dialog.reject();
                tryCompare(dialog, "visible", false);
                compare(toolbar.selectedTags, ["linux"]);
                compare(toolbar.selectedDifficulty, "hard");
                mouseClick(button);
                tryCompare(dialog, "opened", true);
                waitForRendering(dialog.contentItem);
                mouseClick(findChild(dialog.footer, "clearLibraryFilters"));
                tryCompare(dialog, "visible", false);
                compare(toolbar.selectedTags, []);
                compare(toolbar.selectedDifficulty, "");
                compare(toolbar.activeFilterCount, 0);
                compare(toolbar.query, "Bài");
            }
            function test_filter_popup_layout_data() {
                return [
                    {tag: "dark", width: 1280, height: 800, theme: "dark", zoom: 100},
                    {tag: "light", width: 1280, height: 800, theme: "light", zoom: 100},
                    {tag: "narrow", width: 380, height: 540, theme: "dark", zoom: 100},
                    {tag: "zoom", width: 1280, height: 800, theme: "light", zoom: 150}
                ];
            }
            function test_filter_popup_layout(data) {
                window.width = data.width;
                window.height = data.height;
                Studio.Theme.themeMode = data.theme;
                Studio.Theme.setZoomPercent(data.zoom);
                const tags = Array.from({length: 20}, (_, index) => "tag-" + index);
                library.labs = [Object.assign({}, checks.fixtures[0], {tags: tags})];
                mouseClick(control("libraryFilterButton"));
                const dialog = control("libraryFilterDialog");
                tryCompare(dialog, "opened", true);
                waitForRendering(dialog.contentItem);
                const bounds = dialog.contentItem.mapToItem(null, 0, 0, dialog.contentItem.width, dialog.contentItem.height);
                verify(bounds.x >= 0 && bounds.x + bounds.width <= window.width + 1);
                verify(bounds.y >= 0 && bounds.y + bounds.height <= window.height + 1);
                if (checks.screenshotFolder)
                    grabImage(window.contentItem.parent).save(checks.screenshotFolder + "/filter-popup-" + data.tag + ".png");
                const last = findChild(dialog.contentItem, "topic-tag-9");
                last.forceActiveFocus(Qt.TabFocusReason);
                tryVerify(() => {
                    const point = last.mapToItem(dialog.contentItem, 0, 0);
                    return point.y >= -1 && point.y + last.height <= dialog.contentItem.height + 1;
                });
                const apply = findChild(dialog.footer, "applyLibraryFilters");
                const buttonBounds = apply.mapToItem(null, 0, 0, apply.width, apply.height);
                verify(buttonBounds.x >= 0 && buttonBounds.x + buttonBounds.width <= window.width + 1);
                verify(buttonBounds.y >= 0 && buttonBounds.y + buttonBounds.height <= window.height + 1);
            }
            function test_filter_popup_handles_empty_catalog_and_navigation() {
                const dialog = control("libraryFilterDialog");
                library.labs = [];
                mouseClick(control("libraryFilterButton"));
                tryCompare(dialog, "opened", true);
                compare(dialog.topicOptions.length, 0);
                verify(findChild(dialog.contentItem, "difficulty-easy").enabled);
                dialog.pendingDifficulty = "easy";
                library.visible = false;
                tryCompare(dialog, "visible", false);
                compare(control("libraryToolbar").selectedDifficulty, "");
                library.visible = true;
            }
            function test_difficulty_badges_data() {
                return [
                    {tag: "easy", value: "easy", label: "Dễ"},
                    {tag: "medium", value: "medium", label: "Trung bình"},
                    {tag: "hard", value: "hard", label: "Khó"},
                    {tag: "legacy", value: "", label: "Chưa phân loại"}
                ];
            }
            function test_difficulty_badges(data) {
                library.labs = [Object.assign({}, checks.fixtures[0], {difficulty: data.value})];
                library.selectedLab = library.labs[0];
                waitForRendering(library);
                const header = control("libraryDetailDifficulty");
                const card = control("libraryLab-fixture-1");
                const avatar = control("libraryDifficultyAvatar-fixture-1");
                verify(header !== null && avatar !== null);
                compare(header.text, data.label);
                compare(control("libraryDifficulty-fixture-1"), null);
                verify(avatar.compact);
                compare(avatar.width, 44);
                compare(avatar.height, 44);
                for (const mode of ["dark", "light"]) {
                    Studio.Theme.themeMode = mode;
                    for (const running of [false, true]) {
                        card.running = running;
                        compare(avatar.text, data.label);
                        compare(avatar.textColor, header.textColor);
                        compare(avatar.color, header.bgColor);
                        compare(avatar.iconName, running ? "terminal" : "science");
                        verify(card.Accessible.description.indexOf(data.label) >= 0);
                    }
                }
            }
            function test_start_label_while_preparing() {
                const button = control("startLabButton");
                compare(button.text, "Bắt đầu");
                verify(button.enabled);
                library.starting = true;
                compare(button.text, "Đang chuẩn bị…");
                verify(!button.enabled);
                library.starting = false;
                compare(button.text, "Bắt đầu");
                verify(button.enabled);
            }
            function test_card_metadata_separated_from_topics_data() {
                return [
                    {tag: "dark", width: 1280, theme: "dark", zoom: 100, difficulty: ""},
                    {tag: "light", width: 1280, theme: "light", zoom: 100, difficulty: "medium"},
                    {tag: "narrow", width: 380, theme: "dark", zoom: 100, difficulty: "hard"},
                    {tag: "zoom", width: 1280, theme: "light", zoom: 150, difficulty: "easy"}
                ];
            }
            function test_card_metadata_separated_from_topics(data) {
                window.width = data.width;
                Studio.Theme.themeMode = data.theme;
                Studio.Theme.setZoomPercent(data.zoom);
                library.labs = [Object.assign({}, checks.fixtures[0], {
                    name: "Hai máy giao tiếp: ARP, ping và Wireshark",
                    difficulty: data.difficulty, nodes: ["client", "server"],
                    tags: ["networking", "linux"]
                })];
                library.selectedLab = library.labs[0];
                waitForRendering(library);
                const card = control("libraryLab-fixture-1");
                const difficulty = findChild(card, "libraryDifficultyAvatar-fixture-1");
                verify(difficulty !== null);
                const topics = findChild(card, "libraryCardTopics");
                const difficultyBounds = difficulty.mapToItem(card, 0, 0, difficulty.width, difficulty.height);
                const topicBounds = topics.mapToItem(card, 0, 0, topics.width, topics.height);
                verify(difficulty.parent !== topics, "Difficulty is metadata, not a topic");
                verify(topicBounds.y >= difficultyBounds.y + difficultyBounds.height + Studio.Theme.space8,
                    "Topic group needs breathing room below difficulty");
                verify(topics.spacing >= Studio.Theme.space8);
                verify(difficultyBounds.x >= 0 && difficultyBounds.x + difficultyBounds.width <= card.width);
                verify(topicBounds.y + topicBounds.height <= card.height);
                if (checks.screenshotFolder)
                    grabImage(window.contentItem.parent).save(checks.screenshotFolder + "/card-tags-" + data.tag + ".png");
            }
            function test_initial_catalog_before_toolbar_construction() {
                const loaded = createTemporaryObject(preloadedLibrary, window.contentItem, {
                    labs: checks.fixtures, width: 1280, height: 700
                });
                verify(loaded !== null);
                compare(loaded.topicOptions.length, 3);
                compare(loaded.matchingLabs("").length, 12);
            }
            function test_header_and_cards_adapt_data() {
                return [
                    {tag: "wide-dark", width: 1600, theme: "dark", zoom: 100},
                    {tag: "wide-light", width: 1600, theme: "light", zoom: 100},
                    {tag: "laptop", width: 960, theme: "dark", zoom: 100},
                    {tag: "phone", width: 380, theme: "dark", zoom: 100},
                    {tag: "zoom", width: 1280, theme: "dark", zoom: 150}
                ];
            }
            function test_header_and_cards_adapt(data) {
                window.width = data.width;
                Studio.Theme.themeMode = data.theme;
                Studio.Theme.setZoomPercent(data.zoom);
                library.labs = [Object.assign({}, checks.fixtures[0], {name: "Mạng nhiều vùng", tags: ["network-services"], tag_labels: {"network-services": "Dịch vụ mạng"}}), checks.fixtures[1]];
                library.selectedLab = library.labs[0];
                waitForRendering(library);
                const card = control("libraryLab-fixture-1");
                const topics = findChild(card, "libraryCardTopics");
                verify(topics !== null, "Topics need their own full-width row");
                const position = topics.mapToItem(card, 0, 0);
                verify(position.x <= Studio.Theme.space16);
                verify(topics.width >= card.width - Studio.Theme.space32);
                card.forceActiveFocus();
                keyClick(Qt.Key_Return);
                verify(library.showDetails);
                waitForRendering(library);
                const header = control("libraryHeader");
                verify(header !== null);
                const identity = control("libraryLabIdentity");
                const summary = control("libraryLabTags");
                const bounds = summary.mapToItem(header, 0, 0, summary.width, summary.height);
                verify(bounds.x >= 0 && bounds.x + bounds.width <= header.width + 1);
                verify(bounds.y >= 0 && bounds.y + bounds.height <= header.height + 1);
                if (header.width >= 640) {
                    verify(bounds.x >= identity.x + identity.width, "Summary belongs on the right on desktop");
                    verify(header.height <= 132, "Single-topic header should stay compact");
                } else {
                    verify(bounds.y >= identity.y + identity.height, "Summary must wrap below identity");
                }
                if (checks.screenshotFolder)
                    grabImage(window.contentItem.parent).save(checks.screenshotFolder + "/library-redesign-" + data.tag + ".png");
            }
            function test_card_click_keeps_session_navigation() {
                library.sessions = [{id: "running-fixture", lab_id: "fixture-2", state: "RUNNING"}];
                const card = control("libraryLab-fixture-2");
                verify(card.running);
                mouseClick(card);
                compare(library.selectedLab.id, "fixture-2");
                compare(openSessionSpy.count, 1);
                compare(openSessionSpy.signalArguments[0][0].id, "running-fixture");
                const chip = control("libraryRowTopic-fixture-1-linux");
                mouseClick(chip);
                compare(library.selectedLab.id, "fixture-1");
                compare(openSessionSpy.count, 1);
            }
            function test_header_long_title_and_missing_topics() {
                window.width = 380;
                library.selectedLab = Object.assign({}, checks.fixtures[0], {
                    name: "Thực hành cấu hình nhiều vùng mạng và kiểm tra dịch vụ trên hệ thống Linux",
                    tags: [], networks: [], nodes: ["client"]
                });
                library.showDetails = true;
                waitForRendering(library);
                const header = control("libraryHeader");
                const title = control("libraryLabTitle");
                verify(title.height > Studio.Theme.titleLarge);
                verify(!control("libraryNetworkCount").visible);
                compare(control("libraryNodeCount").text, "1 máy");
                library.sessions = [{id: "saved-fixture", lab_id: "fixture-1", state: "STOPPED", saved: true}];
                waitForRendering(library);
                const status = control("libraryLabStatus");
                compare(status.text, "Đã dừng · Có bản lưu");
                const bounds = status.mapToItem(header, 0, 0, status.width, status.height);
                verify(bounds.x >= 0 && bounds.x + bounds.width <= header.width);
                verify(bounds.y + bounds.height <= header.height);
            }
            function test_topic_chips_and_picker_share_visual_identity() {
                const chip = control("libraryTopic-linux");
                verify(chip !== null, "Header topic must be an icon chip");
                verify(chip.iconName.length > 0);
                verify(chip.textColor !== Studio.Theme.textOnSecondaryContainer);
                const rowChip = control("libraryRowTopic-fixture-1-linux");
                verify(rowChip !== null);
                compare(rowChip.textColor, chip.textColor);
                compare(rowChip.iconName, chip.iconName);
                verify(rowChip.width <= rowChip.maximumWidth);
                const picker = control("libraryFilterButton");
                const dialog = control("libraryFilterDialog");
                mouseClick(picker);
                tryCompare(dialog, "opened", true);
                waitForRendering(dialog.contentItem);
                const option = findChild(dialog.contentItem, "topic-linux");
                compare(option.iconName, chip.iconName);
                mouseClick(option);
                compare(option.iconName, chip.iconName);
                verify(option.selected);
            }
            function test_topic_palette_data() {
                return [
                    {tag: "dark", mode: "dark", width: 1280},
                    {tag: "light", mode: "light", width: 1280},
                    {tag: "compact", mode: "dark", width: 600}
                ];
            }
            function test_topic_palette(data) {
                Studio.Theme.themeMode = data.mode;
                window.width = data.width;
                const labels = {
                    linux: "Linux", scripting: "Lập trình & Script", networking: "Mạng máy tính",
                    "network-services": "Dịch vụ mạng", "network-security": "Bảo mật mạng",
                    "system-security": "Bảo mật hệ thống", "web-security": "Bảo mật Web",
                    databases: "Cơ sở dữ liệu", cryptography: "Mật mã học",
                    "software-security": "An toàn phần mềm", forensics: "Điều tra & Ứng cứu", containers: "Container"
                };
                const topicIds = Object.keys(labels);
                function luminance(hex) {
                    const channels = [1, 3, 5].map(offset => {
                        const value = parseInt(hex.substr(offset, 2), 16) / 255;
                        return value <= 0.04045 ? value / 12.92 : Math.pow((value + 0.055) / 1.055, 2.4);
                    });
                    return channels[0] * 0.2126 + channels[1] * 0.7152 + channels[2] * 0.0722;
                }
                for (const tag of topicIds) {
                    const style = Studio.TopicStyle.appearance(tag);
                    const ink = luminance(style.foreground), background = luminance(style.background);
                    verify((Math.max(ink, background) + 0.05) / (Math.min(ink, background) + 0.05) >= 4.5, tag + " contrast");
                    const icon = createTemporaryObject(topicIcon, window.contentItem, {name: style.icon});
                    verify(icon !== null);
                    tryCompare(icon, "status", Image.Ready);
                    icon.destroy();
                }
                library.labs = [Object.assign({}, checks.fixtures[0], {tags: topicIds, tag_labels: labels})];
                library.selectedLab = library.labs[0];
                library.showDetails = false;
                waitForRendering(library);
                if (checks.screenshotFolder)
                    grabImage(window.contentItem.parent).save(checks.screenshotFolder + "/topic-chips-" + data.tag + ".png");
                const picker = control("libraryFilterButton");
                const dialog = control("libraryFilterDialog");
                mouseClick(picker);
                tryCompare(dialog, "opened", true);
                dialog.pendingTags = ["linux", "network-services", "web-security"];
                waitForRendering(dialog.contentItem);
                if (checks.screenshotFolder)
                    grabImage(window.contentItem.parent).save(checks.screenshotFolder + "/topic-picker-" + data.tag + ".png");
                for (const tag of topicIds) {
                    const option = findChild(dialog.contentItem, "topic-" + tag);
                    verify(option.width <= dialog.contentItem.width);
                    compare(option.iconName, Studio.TopicStyle.appearance(tag).icon);
                }
            }
            function test_topic_filter_picker_cancel_apply_and_clear() {
                const picker = control("libraryFilterButton");
                const dialog = control("libraryFilterDialog");
                mouseClick(picker);
                tryCompare(dialog, "opened", true);
                waitForRendering(dialog.contentItem);
                mouseClick(findChild(dialog.contentItem, "topic-linux"));
                dialog.reject();
                tryCompare(dialog, "visible", false);
                compare(control("libraryToolbar").selectedTags, []);
                mouseClick(picker);
                tryCompare(dialog, "opened", true);
                waitForRendering(dialog.contentItem);
                mouseClick(findChild(dialog.contentItem, "topic-linux"));
                mouseClick(findChild(dialog.footer, "applyLibraryFilters"));
                tryCompare(dialog, "visible", false);
                compare(control("libraryToolbar").selectedTags, ["linux"]);
                compare(library.matchingLabs("").length, 4);
                mouseClick(picker);
                tryCompare(dialog, "opened", true);
                dialog.pendingTags = ["unknown"];
                dialog.accept();
                compare(control("libraryToolbar").selectedTags, []);
            }
            function test_topic_filter_combines_or_with_search_and_keeps_legacy() {
                library.labs = [
                    Object.assign({}, checks.fixtures[0], {tags: ["linux"], tag_labels: {linux: "Linux"}}),
                    Object.assign({}, checks.fixtures[1], {tags: ["networking"], tag_labels: {networking: "Mạng máy tính"}}),
                    checks.fixtures[2]
                ];
                const picker = control("libraryFilterButton");
                const dialog = control("libraryFilterDialog");
                compare(control("libraryToolbar").topicOptions.length, 2);
                compare(library.matchingLabs("").length, 3);
                control("libraryToolbar").selectedTags = ["linux"];
                compare(library.matchingLabs("").length, 1);
                control("libraryToolbar").selectedTags = ["linux", "networking"];
                compare(library.matchingLabs("").length, 2);
                compare(library.matchingLabs("2").length, 1);
                compare(library.matchingLabs("Linux").length, 1);
                control("libraryToolbar").selectedTags = [];
                compare(library.matchingLabs("").length, 3);
                control("libraryToolbar").selectedTags = ["networking"];
                library.labs = [library.labs[0]];
                compare(library.matchingLabs("").length, 1);
                compare(control("libraryToolbar").selectedTags, []);
            }
            function test_session_status_data() {
                return [
                    { tag: "running", state: "RUNNING", saved: false, label: "Đang chạy", resume: false },
                    { tag: "running-saved", state: "RUNNING", saved: true, label: "Đang chạy", resume: false },
                    { tag: "suspended", state: "SUSPENDED", saved: true, label: "Đã tạm dừng", resume: true },
                    { tag: "stopped-saved", state: "STOPPED", saved: true, label: "Đã dừng · Có bản lưu", resume: true },
                    { tag: "stopped-unsaved", state: "STOPPED", saved: false, label: "Sẵn sàng", resume: false }
                ];
            }
            function test_session_status(data) {
                library.sessions = [{id: "fixture-session", lab_id: "fixture-1", state: data.state, saved: data.saved}];
                compare(control("libraryLabStatus").text, data.label);
                const resume = control("resumeLabButton");
                compare(resume.visible, data.resume);
                if (data.resume) {
                    compare(resume.text, data.state === "STOPPED" ? "Tiếp tục bản đã lưu" : "Tiếp tục");
                    mouseClick(resume);
                    compare(resumeSpy.count, 1);
                    compare(resumeSpy.signalArguments[0][0].id, "fixture-session");
                    compare(resumeSpy.signalArguments[0][0].state, data.state);
                }
            }
            function test_stop_keeps_checkpoint_without_showing_suspended() {
                library.sessions = [{id: "fixture-session", lab_id: "fixture-1", state: "RUNNING", saved: true}];
                compare(control("libraryLabStatus").text, "Đang chạy");
                library.sessions = [{id: "fixture-session", lab_id: "fixture-1", state: "STOPPED", saved: true}];
                compare(control("libraryLabStatus").text, "Đã dừng · Có bản lưu");
                verify(control("resumeLabButton").visible);
                verify(!control("startLabButton").visible);
                library.selectedLab = checks.fixtures[1];
                compare(control("libraryLabStatus").text, "Sẵn sàng");
                verify(!control("resumeLabButton").visible);
                library.selectedLab = checks.fixtures[0];
                compare(control("libraryLabStatus").text, "Đã dừng · Có bản lưu");
                if (checks.screenshotFolder)
                    grabImage(window.contentItem).save(checks.screenshotFolder + "/stopped-with-checkpoint.png");
            }
            function test_sidebar_has_one_filter_button_next_to_search() {
                const toolbar = control("libraryToolbar");
                const list = control("libraryLabList");
                const button = control("libraryFilterButton");
                const search = control("librarySearch");
                compare(button.parent, search.parent);
                compare(button.mapToItem(toolbar, 0, 0).y, search.mapToItem(toolbar, 0, 0).y);
                verify(search.width >= 140);
                compare(control("libraryTopics"), null);
                compare(control("libraryDifficulty"), null);
                compare(toolbar.height, 104);
                compare(list.y - toolbar.y, 116);
                verify(list.height > library.height * 0.65);
                const before = list.y;
                openTools();
                compare(list.y, before);
                compare(menu().background.objectName, "studioPopupSurface");
                verify(menu().modal && menu().dim);
                keyClick(Qt.Key_Escape);
                tryCompare(menu(), "visible", false);
                verify(control("libraryToolsToggle").activeFocus);
                compare(list.y, before);
            }
            function test_splitter_resizes_and_keeps_both_panes_usable() {
                const handle = control("librarySplitHandle");
                verify(handle !== null, "Library needs a draggable split handle");
                const list = control("libraryList");
                const detail = control("libraryDetail");
                const original = list.width;
                mouseDrag(handle, handle.width / 2, handle.height / 2, 100, 0);
                tryVerify(() => list.width >= original + 80);
                const resized = list.width;
                window.width = 640;
                tryVerify(() => library.compact);
                waitForRendering(library);
                window.width = 1280;
                tryVerify(() => !library.compact);
                tryCompare(list, "width", resized);
                mouseDrag(handle, handle.width / 2, handle.height / 2, -600, 0);
                tryCompare(list, "width", 280);
                mouseDrag(handle, handle.width / 2, handle.height / 2, 600, 0);
                tryVerify(() => list.width <= 560 && detail.width >= 360);
                if (checks.screenshotFolder)
                    grabImage(window.contentItem.parent).save(checks.screenshotFolder + "/library-resized.png");
            }
            function test_filter_button_states_and_keyboard() {
                const toolbar = control("libraryToolbar");
                const button = control("libraryFilterButton");
                const dialog = control("libraryFilterDialog");
                for (const mode of ["dark", "light"]) {
                    Studio.Theme.themeMode = mode;
                    toolbar.selectedTags = ["linux"];
                    toolbar.selectedDifficulty = "easy";
                    compare(toolbar.activeFilterCount, 2);
                    compare(button.text, "Lọc (2)");
                    tryCompare(button.background, "color", Studio.Theme.primaryContainer);
                    if (checks.screenshotFolder)
                        grabImage(window.contentItem.parent).save(checks.screenshotFolder + "/filters-active-" + mode + ".png");
                    toolbar.selectedTags = [];
                    toolbar.selectedDifficulty = "";
                }
                button.forceActiveFocus(Qt.TabFocusReason);
                keyClick(Qt.Key_Space);
                tryCompare(dialog, "opened", true);
                const easy = findChild(dialog.contentItem, "difficulty-easy");
                easy.forceActiveFocus(Qt.TabFocusReason);
                keyClick(Qt.Key_Space);
                compare(dialog.pendingDifficulty, "easy");
                compare(toolbar.selectedDifficulty, "");
                keyClick(Qt.Key_Escape);
                tryCompare(dialog, "visible", false);
                tryCompare(button, "activeFocus", true);
                compare(toolbar.selectedDifficulty, "");
            }
            function test_transfer_actions() {
                const importButton = control("importLabPackageButton");
                const exportButton = control("exportLabPackageButton");
                compare(importButton.iconName, "download");
                compare(exportButton.iconName, "upload");
                compare(findChild(control("libraryToolbar"), "importLabPackageButton"), importButton);
                compare(findChild(control("libraryDetail"), "exportLabPackageButton"), exportButton);
                mouseClick(importButton);
                compare(importSpy.count, 1);
                mouseClick(exportButton);
                compare(exportSpy.count, 1);
                compare(exportSpy.signalArguments[0][0].id, "fixture-1");
                library.selectedLab = null;
                verify(!exportButton.visible);
            }
            function test_tools_dispatch_after_close_data() {
                return [{ tag: "reports", index: 0 }, { tag: "review", index: 1 }];
            }
            function test_tools_dispatch_after_close(data) {
                openTools();
                mouseClick(menu().itemAt(data.index));
                tryCompare(menu(), "visible", false);
                compare(reportsSpy.count, data.index === 0 ? 1 : 0);
                compare(reviewSpy.count, data.index === 1 ? 1 : 0);
                if (data.index === 1)
                    compare(reviewSpy.signalArguments[0][0], control("libraryToolsToggle"));
            }
            function test_keyboard_and_dismissal() {
                const tools = control("libraryToolsToggle");
                tools.forceActiveFocus(Qt.TabFocusReason);
                keyClick(Qt.Key_Space);
                tryCompare(menu(), "opened", true);
                keyClick(Qt.Key_Down);
                keyClick(Qt.Key_Return);
                tryCompare(menu(), "visible", false);
                compare(reportsSpy.count, 1);
                openTools();
                keyClick(Qt.Key_Escape);
                tryCompare(menu(), "visible", false);
                compare(reportsSpy.count, 1);
                verify(tools.activeFocus);
                openTools();
                mouseClick(library, library.width - 20, 240);
                tryCompare(menu(), "visible", false);
                compare(reviewSpy.count, 0);
            }
            function test_capability_gating() {
                library.reportsSupported = false;
                openTools();
                verify(!menu().itemAt(0).visible);
                compare(menu().itemAt(0).height, 0);
                verify(menu().itemAt(1).visible);
                verify(menu().height <= Studio.Theme.controlHeight + Studio.Theme.space16);
                keyClick(Qt.Key_Down);
                keyClick(Qt.Key_Return);
                tryCompare(menu(), "visible", false);
                compare(reviewSpy.count, 1);
                library.reviewSupported = false;
                library.packageSupported = false;
                verify(!control("libraryToolsToggle").visible);
                verify(!control("importLabPackageButton").visible);
                verify(!control("exportLabPackageButton").visible);
                compare(control("libraryToolbar").height, 104);
            }
            function test_disabled_actions_data() {
                return [{ tag: "busy", busy: true, connected: true }, { tag: "offline", busy: false, connected: false }];
            }
            function test_disabled_actions(data) {
                library.busy = data.busy;
                library.connected = data.connected;
                verify(!control("importLabPackageButton").enabled);
                verify(!control("exportLabPackageButton").enabled);
                openTools();
                verify(!menu().itemAt(0).enabled && !menu().itemAt(1).enabled);
                mouseClick(menu().itemAt(0));
                compare(reportsSpy.count, 0);
            }
            function test_search_and_empty_library() {
                control("librarySearch").text = "fixture-12";
                tryVerify(() => control("libraryLab-fixture-12") !== null);
                tryVerify(() => control("libraryLab-fixture-1") === null);
                waitForRendering(control("libraryLabList"));
                mouseClick(control("libraryLab-fixture-12"));
                compare(library.selectedLab.id, "fixture-12");
                control("librarySearch").text = "missing";
                tryCompare(control("libraryEmptyState"), "visible", true);
                library.labs = [];
                library.selectedLab = null;
                control("librarySearch").text = "";
                verify(control("libraryEmptyState").visible);
                verify(control("importLabPackageButton").enabled);
            }
            function test_empty_state_is_centered_data() {
                return [
                    { tag: "empty", filter: false, connected: true, width: 1280, zoom: 100 },
                    { tag: "filtered", filter: true, connected: true, width: 1280, zoom: 100 },
                    { tag: "offline", filter: false, connected: false, width: 1280, zoom: 100 },
                    { tag: "compact", filter: false, connected: true, width: 380, zoom: 100 },
                    { tag: "zoom", filter: true, connected: true, width: 1280, zoom: 150 }
                ];
            }
            function test_empty_state_is_centered(data) {
                window.width = data.width;
                library.connected = data.connected;
                Studio.Theme.setZoomPercent(data.zoom);
                if (data.filter)
                    control("librarySearch").text = "not-found";
                else {
                    library.labs = [];
                    library.selectedLab = null;
                }
                const empty = control("libraryEmptyState");
                const area = control("libraryLabList");
                tryCompare(empty, "visible", true);
                waitForRendering(area);
                const center = empty.mapToItem(area, empty.width / 2, empty.height / 2);
                fuzzyCompare(center.x, area.width / 2, 1);
                fuzzyCompare(center.y, area.height / 2, 1);
                verify(empty.height < area.height);
                if (checks.screenshotFolder)
                    grabImage(window.contentItem.parent).save(checks.screenshotFolder + "/library-empty-" + data.tag + ".png");
            }
            function test_layout_data() {
                return [
                    { tag: "desktop-dark", width: 1280, theme: "dark", zoom: 100 },
                    { tag: "desktop-light", width: 1280, theme: "light", zoom: 100 },
                    { tag: "laptop", width: 960, theme: "dark", zoom: 100 },
                    { tag: "compact", width: 640, theme: "light", zoom: 100 },
                    { tag: "narrow", width: 380, theme: "dark", zoom: 100 },
                    { tag: "zoom70", width: 1280, theme: "dark", zoom: 70 },
                    { tag: "zoom150", width: 1280, theme: "dark", zoom: 150 }
                ];
            }
            function test_layout(data) {
                window.width = data.width;
                Studio.Theme.themeMode = data.theme;
                Studio.Theme.setZoomPercent(data.zoom);
                waitForRendering(library);
                const toolbar = control("libraryToolbar");
                const list = control("libraryLabList");
                compare(toolbar.height, 104);
                compare(list.y - toolbar.y, 116);
                for (const name of ["importLabPackageButton", "libraryToolsToggle", "librarySearch", "libraryFilterButton"]) {
                    const button = control(name);
                    const bounds = button.mapToItem(toolbar, 0, 0, button.width, button.height);
                    verify(bounds.x >= 0 && bounds.x + bounds.width <= toolbar.width + 1, name);
                    verify(bounds.height >= 48, name);
                }
                if (checks.screenshotFolder)
                    grabImage(window.contentItem.parent).save(checks.screenshotFolder + "/library-" + data.tag + ".png");
                openTools();
                const popup = menu().contentItem;
                const bounds = popup.mapToItem(null, 0, 0, popup.width, popup.height);
                verify(bounds.x >= 0 && bounds.x + bounds.width <= window.width + 1, "menu horizontal bounds");
                verify(bounds.y >= 0 && bounds.y + bounds.height <= window.height + 1, "menu vertical bounds");
                if (checks.screenshotFolder)
                    grabImage(window.contentItem.parent).save(checks.screenshotFolder + "/library-menu-" + data.tag + ".png");
                menu().close();
                tryCompare(menu(), "visible", false);
                if (library.compact) {
                    library.showDetails = true;
                    waitForRendering(library);
                    const exportButton = control("exportLabPackageButton");
                    verify(exportButton.visible);
                    const bounds = exportButton.mapToItem(library, 0, 0, exportButton.width, exportButton.height);
                    verify(bounds.x >= 0 && bounds.x + bounds.width <= library.width + 1);
                    mouseClick(exportButton);
                    compare(exportSpy.count, 1);
                }
            }
        }
    }
}
