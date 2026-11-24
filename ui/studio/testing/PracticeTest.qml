import QtQuick
import QtQuick.Controls.Basic
import QtTest
import "../models/SessionFiles.js" as Files
import "../views/practice" as Practice
import ".." as Studio

Item {
    id: checks

    property string screenshotFolder: ""

    Component {
        id: nodeCardComponent
        Practice.SessionNodeCard { height: implicitHeight }
    }
    Component {
        id: nodeSignalSpy
        SignalSpy {}
    }

    function fixture(state, saved) {
        return { id: "fixture-session", lab_id: "fixture", lab_name: "Thực hành Linux cơ bản",
            state: state || "RUNNING", saved: saved === undefined ? true : saved,
            environments: [], nodes: [], quiz: '[{"id":"question"}]', error: "" };
    }

    ApplicationWindow {
        id: window

        width: 1280
        height: 800
        visible: true
        color: Studio.Theme.surface

        Studio.StudioViewport {
            hostWindow: window

            Studio.SessionView {
                id: practice

                anchors.fill: parent
                anchors.margins: Studio.Theme.contentInset
                manual: "# Làm quen với Linux\n\nĐọc hướng dẫn và thực hành trong máy lab.\n\nTạm dừng để lưu tiến độ khi cần nghỉ."
            }
        }
        SignalSpy { id: saveSpy; target: practice; signalName: "saveRequested" }
        SignalSpy { id: stopSpy; target: practice; signalName: "stopRequested" }
        SignalSpy { id: resetSpy; target: practice; signalName: "resetRequested" }
        SignalSpy { id: discardSpy; target: practice; signalName: "discardRequested" }
        SignalSpy { id: quizSpy; target: practice; signalName: "quizRequested" }
        SignalSpy { id: reportsSpy; target: practice; signalName: "reportsRequested" }
        SignalSpy { id: suspendSpy; target: practice; signalName: "suspendRequested" }
        SignalSpy { id: submitSpy; target: practice; signalName: "submissionRequested" }
        SignalSpy { id: resumeSpy; target: practice; signalName: "resumeRequested" }
        SignalSpy { id: terminalSpy; target: practice; signalName: "terminalRequested" }

        TestCase {
            name: "PracticeActions"
            when: window.visible

            function control(name) { return findChild(practice, name); }
            function menu() { return control("practiceActionsMenu"); }
            function openMenu() {
                mouseClick(control("practiceMoreActions"));
                tryCompare(menu(), "opened", true);
                waitForRendering(menu().contentItem);
            }
            function init() {
                Studio.Theme.reducedMotion = true;
                Studio.Theme.themeMode = "dark";
                Studio.Theme.setZoomPercent(100);
                window.width = 1280; window.height = 800;
                practice.visible = true;
                practice.busy = false;
                practice.desktopSupported = false;
                practice.persistenceSupported = true;
                practice.discardSupported = true;
                practice.checkworkSupported = true;
                practice.quizSupported = true;
                practice.submissionSupported = true;
                practice.compactPane = 0;
                practice.session = checks.fixture();
                practice.sessions = [practice.session];
                for (const spy of [saveSpy, stopSpy, resetSpy, discardSpy, quizSpy, reportsSpy, suspendSpy, submitSpy, resumeSpy, terminalSpy]) spy.clear();
                window.requestActivate();
                tryCompare(window, "active", true);
                waitForRendering(practice);
            }
            function cleanup() {
                menu().dismiss();
                tryCompare(menu(), "visible", false);
            }
            function test_main_actions_and_reports() {
                const bar = control("practiceActionBar");
                compare(bar.children.filter(item => item.visible && item.objectName).length, 3);
                verify(control("practiceReportsButton").parent !== bar);
                verify(control("practiceReportsButton").flat);
                mouseClick(control("practiceSubmitButton"));
                compare(submitSpy.count, 1);
                compare(submitSpy.signalArguments[0][0].id, "fixture-session");
                mouseClick(control("practiceSuspendButton"));
                compare(suspendSpy.count, 1);
                mouseClick(control("practiceReportsButton"));
                compare(reportsSpy.count, 1);
            }
            function test_machines_without_file_controls_data() {
                return [{tag: "desktop", width: 1280, height: 800}, {tag: "compact", width: 760, height: 700}];
            }
            function test_machines_without_file_controls(data) {
                window.width = data.width;
                window.height = data.height;
                const session = checks.fixture();
                session.nodes = [["client", ["lan"]], ["server", ["lan"]]];
                session.environments = session.nodes.map(node => [node[0], node[0], "student", 2000, 2000, "/home/student", "/bin/bash"]);
                session.files = [["client", ["/home/student/seed-only.txt"]], ["server", ["/home/student/start.sh"]]];
                session.seed_files = [["client", ["seed-only.txt", "scripts/start.sh"]], ["server", ["start.sh"]]];
                session.seed_directories = [["client", ["empty"]], ["server", []]];
                session.imports = [{node: "client", state: "COMPLETE", path: "/home/student/imported.txt"}];
                session.workspaces = [["client", "/home/student"], ["server", "/home/student"]];
                practice.session = session;
                practice.compactPane = 1;
                waitForRendering(practice);
                const filesToggle = control("nodeFilesToggle-client");
                verify(filesToggle !== null);
                mouseClick(filesToggle);
                const pane = control("practiceMachinesPane");
                const texts = [];
                function collect(item) {
                    if (typeof item.text === "string") texts.push(item.text);
                    if (typeof item.title === "string") texts.push(item.title);
                    for (const child of item.children || []) collect(child);
                }
                collect(pane);
                for (const removed of ["Làm mới file", "Nhập thư mục", "Xuất tất cả", "Nhập file", "Chọn file từ VM", "imported.txt", "File thực tế trong container"])
                    verify(!texts.some(text => text.includes(removed)), removed + " must not appear");
                verify(texts.includes("Máy thực hành"));
                verify(texts.includes("seed-only.txt"));
                verify(texts.includes("empty/"));
                const row = control("initialFile-client-scripts/start.sh");
                verify(row !== null && row.visible);
                compare(row.entry.depth, 1);
                verify(!row.canExport && !row.showMetadata);
                verify(!findChild(row, "exportTreeEntry").visible);
                const terminal = control("nodeTerminalButton-client-0");
                verify(terminal.visible && terminal.enabled);
                mouseClick(terminal);
                compare(terminalSpy.count, 1);
                compare(terminalSpy.signalArguments[0][1], "client");
                compare(terminalSpy.signalArguments[0][2], 0);
                practice.busy = true;
                verify(!terminal.enabled);
                practice.busy = false;
                compare(practice.session.files, session.files);
                if (checks.screenshotFolder) grabImage(window.contentItem).save(checks.screenshotFolder + "/machines-seed-files-" + data.tag + ".png");
            }
            function test_seed_tree_ignores_runtime_files_and_updates_on_session_change() {
                const session = checks.fixture();
                session.nodes = [["client", ["lan"]]];
                session.environments = [["client", "client", "student", 2000, 2000, "/home/student", "/bin/bash"]];
                session.seed_files = [["client", ["declared.txt"]]];
                session.files = [["client", ["/home/student/generated.txt"]]];
                session.workspaces = [["client", "/home/student"]];
                practice.session = session;
                waitForRendering(practice);
                verify(control("initialFile-client-declared.txt") !== null);
                compare(control("initialFile-client-generated.txt"), null);
                const next = JSON.parse(JSON.stringify(session));
                next.id = "other-session";
                next.seed_files = [["client", []]];
                practice.session = next;
                waitForRendering(practice);
                verify(!control("nodeInitialFiles-client").visible);
                compare(control("initialFile-client-declared.txt"), null);
                compare(control("initialFile-client-generated.txt"), null);
            }
            function nodeFixture() {
                const session = checks.fixture();
                session.nodes = [["visitor", ["guest", "audit"]]];
                session.environments = [["visitor", "visitor", "student", 2000, 2000, "/home/student", "/bin/bash"]];
                session.addresses = [["visitor", "audit", "10.241.30.3"], ["db", "audit", "10.241.30.2"]];
                session.terminal_counts = [["visitor", 2]];
                session.desktop_nodes = ["visitor"];
                session.gui_backends = {visitor: "xpra"};
                session.seed_files = [["visitor", ["tools/check-network.py", "network.json", "start.sh"]]];
                return session;
            }
            function makeNodeCard(width, session) {
                practice.visible = false;
                const card = createTemporaryObject(nodeCardComponent, window.contentItem, {
                    width: width, x: 16, y: 16, nodeId: "visitor",
                    session: session || nodeFixture(), desktopSupported: true
                });
                verify(card !== null);
                waitForRendering(card);
                return card;
            }
            function test_node_networks_include_automatic_addresses() {
                const card = makeNodeCard(600);
                const guest = findChild(card, "nodeNetwork-visitor-guest");
                const audit = findChild(card, "nodeNetwork-visitor-audit");
                verify(guest !== null && guest.visible);
                verify(audit !== null && audit.visible);
                compare(findChild(guest, "networkAddress").text, "IP tự động");
                compare(findChild(audit, "networkAddress").text, "10.241.30.3");
                const next = nodeFixture();
                next.addresses.push(["visitor", "guest", "172.25.0.2"]);
                card.session = next;
                tryCompare(findChild(findChild(card, "nodeNetwork-visitor-guest"), "networkAddress"), "text", "172.25.0.2");
            }
            function test_node_files_collapse_keyboard_and_session_change() {
                const card = makeNodeCard(600);
                const tree = findChild(card, "nodeInitialFiles-visitor");
                const toggle = findChild(card, "nodeFilesToggle-visitor");
                verify(toggle !== null && toggle.visible);
                verify(!tree.visible);
                const collapsedHeight = card.height;
                toggle.forceActiveFocus();
                keyClick(Qt.Key_Space);
                tryCompare(tree, "visible", true);
                tryVerify(() => card.height > collapsedHeight);
                verify(findChild(card, "initialFile-visitor-tools/check-network.py").visible);
                card.session = nodeFixture();
                verify(tree.visible, "Polling the same Session must not collapse files");
                const next = nodeFixture();
                next.id = "another-session";
                card.session = next;
                tryCompare(tree, "visible", false);
                next.seed_files = [["visitor", []]];
                card.session = JSON.parse(JSON.stringify(next));
                tryCompare(toggle, "visible", false);
            }
            function test_node_expansion_survives_practice_refresh() {
                practice.session = nodeFixture();
                practice.compactPane = 1;
                waitForRendering(practice);
                mouseClick(control("nodeFilesToggle-visitor"));
                tryCompare(control("nodeInitialFiles-visitor"), "visible", true);
                const refreshed = nodeFixture();
                refreshed.addresses.push(["visitor", "guest", "172.25.0.2"]);
                practice.session = refreshed;
                waitForRendering(practice);
                verify(control("nodeInitialFiles-visitor").visible);
                const next = nodeFixture();
                next.id = "another-session";
                practice.session = next;
                waitForRendering(practice);
                verify(!control("nodeInitialFiles-visitor").visible);
            }
            function test_node_card_layout_data() {
                return [{tag: "wide-dark", width: 960, theme: "dark"},
                    {tag: "narrow-dark", width: 288, theme: "dark"},
                    {tag: "wide-light", width: 960, theme: "light"}];
            }
            function test_node_card_layout(data) {
                Studio.Theme.themeMode = data.theme;
                const card = makeNodeCard(data.width);
                const terminal = findChild(card, "nodeTerminalButton-visitor-0");
                const gui = findChild(card, "nodeDesktopButton");
                verify(terminal.highlighted);
                const secondTerminal = findChild(card, "nodeTerminalButton-visitor-1");
                compare(secondTerminal.highlighted, terminal.highlighted);
                compare(secondTerminal.background.color, terminal.background.color);
                compare(secondTerminal.foreground, terminal.foreground);
                compare(gui.text, "Bật GUI");
                for (const name of ["nodeTerminalButton-visitor-0", "nodeTerminalButton-visitor-1", "nodeDesktopButton", "nodeNetwork-visitor-guest", "nodeNetwork-visitor-audit", "nodeFilesToggle-visitor"]) {
                    const item = findChild(card, name);
                    verify(item !== null && item.visible, name);
                    const position = item.mapToItem(card, 0, 0);
                    verify(position.x >= 0 && position.x + item.width <= card.width + 1, name + " fits horizontally");
                    verify(position.y >= 0 && position.y + item.height <= card.height + 1, name + " fits vertically");
                }
                if (checks.screenshotFolder) grabImage(card).save(checks.screenshotFolder + "/node-card-" + data.tag + ".png");
                verify(card.height < (data.width > 600 ? 230 : 450), "Card height: " + card.height);
                mouseClick(findChild(card, "nodeFilesToggle-visitor"));
                waitForRendering(card);
                if (checks.screenshotFolder) grabImage(card).save(checks.screenshotFolder + "/node-card-files-" + data.tag + ".png");
                card.busy = true;
                verify(!terminal.enabled && !gui.enabled);
                card.busy = false;
                const stopped = nodeFixture();
                stopped.state = "STOPPED";
                card.session = stopped;
                verify(!terminal.enabled && !gui.enabled);
            }
            function test_unknown_gui_backend_does_not_offer_reconnect() {
                const session = nodeFixture();
                delete session.gui_backends;
                const card = makeNodeCard(400, session);
                verify(!findChild(card, "nodeDesktopButton").visible);
                for (const backend of ["", "pending", "native-x11"]) {
                    card.session = Object.assign({}, session, {gui_backends: {visitor: backend}});
                    verify(!findChild(card, "nodeDesktopButton").visible);
                }
            }
            function test_native_gui_does_not_offer_reconnect() {
                const session = nodeFixture();
                session.gui_backends = {visitor: "native-x11"};
                session.prepared_gui_nodes = ["visitor"];
                const card = makeNodeCard(400, session);
                verify(!findChild(card, "nodeDesktopButton").visible);
                verify(findChild(card, "nodeTerminalButton-visitor-0").enabled);
                session.gui_backends = {visitor: "xpra"};
                session.gui_states = {visitor: "disconnected"};
                card.session = Object.assign({}, session);
                verify(findChild(card, "nodeDesktopButton").visible);
                compare(findChild(card, "nodeDesktopButton").text, "Kết nối lại GUI");
                card.session = Object.assign({}, session, {gui_backends: {visitor: "native-x11"}});
                verify(!findChild(card, "nodeDesktopButton").visible);
            }
            function test_node_gui_warning_remains_visible() {
                const session = nodeFixture();
                session.gui_backends = {visitor: "xpra"};
                session.gui_states = {visitor: "disconnected"};
                session.gui_warnings = {visitor: "Display connection unavailable"};
                session.prepared_gui_nodes = ["visitor"];
                const card = makeNodeCard(400, session);
                const status = findChild(card, "nodeGuiBackend");
                verify(status.visible);
                verify(status.text.includes("Display connection unavailable"));
                verify(status.text.includes("Xpra"));
                compare(findChild(card, "nodeDesktopButton").text, "Kết nối lại GUI");
            }
            function test_node_actions_dispatch_and_gui_capability() {
                const card = makeNodeCard(600);
                const terminals = createTemporaryObject(nodeSignalSpy, checks, {target: card, signalName: "terminalRequested"});
                const desktop = createTemporaryObject(nodeSignalSpy, checks, {target: card, signalName: "desktopRequested"});
                verify(terminals.valid && desktop.valid);
                mouseClick(findChild(card, "nodeTerminalButton-visitor-1"));
                compare(terminals.count, 1);
                compare(terminals.signalArguments[0][0], 1);
                const gui = findChild(card, "nodeDesktopButton");
                mouseClick(gui);
                compare(desktop.count, 1);
                card.busy = true;
                mouseClick(gui);
                compare(desktop.count, 1);
                card.busy = false;
                card.desktopSupported = false;
                verify(!gui.visible);
                card.desktopSupported = true;
                const next = nodeFixture();
                next.desktop_nodes = [];
                next.terminal_counts = [["visitor", 1]];
                card.session = next;
                verify(!gui.visible);
                compare(findChild(card, "nodeTerminalButton-visitor-0").text, "Terminal");
                compare(findChild(card, "nodeTerminalButton-visitor-1"), null);
            }
            function test_node_long_labels_fit_narrow_card() {
                const session = nodeFixture();
                session.nodes = [["visitor", ["a-very-long-network-name-for-testing"]]];
                session.environments[0][1] = "a-long-hostname-without-any-spaces";
                session.environments[0][5] = "/home/student/a-long-workspace-name";
                session.prepared_gui_nodes = ["visitor"];
                const card = makeNodeCard(288, session);
                const badge = findChild(card, "nodeNetwork-visitor-a-very-long-network-name-for-testing");
                verify(badge.width <= card.width - 32);
                const address = findChild(badge, "networkAddress");
                const position = address.mapToItem(badge, 0, 0);
                verify(position.x + address.width <= badge.width);
                verify(position.y + address.height <= badge.height);
                const gui = findChild(card, "nodeDesktopButton");
                const guiPosition = gui.mapToItem(card, 0, 0);
                verify(guiPosition.x + gui.width <= card.width);
            }
            function test_menu_does_not_reflow_and_restores_focus() {
                const pane = control("practiceSplit");
                const before = pane.y;
                openMenu();
                compare(pane.y, before);
                verify(menu().modal && !menu().dim);
                compare(menu().background.objectName, "studioPopupSurface");
                verify(menu().background.children.length > 0);
                keyClick(Qt.Key_Escape);
                tryCompare(menu(), "visible", false);
                verify(control("practiceMoreActions").activeFocus);
                compare(pane.y, before);
                compare(stopSpy.count, 0);
            }
            function test_dispatch_after_menu_close_data() {
                return [{tag:"save", button:"practiceSaveButton", spy:saveSpy},
                    {tag:"quiz", button:"practiceQuizButton", spy:quizSpy},
                    {tag:"reset", button:"practiceResetButton", spy:resetSpy},
                    {tag:"stop", button:"practiceStopButton", spy:stopSpy},
                    {tag:"discard", button:"discardCheckpointButton", spy:discardSpy}];
            }
            function test_dispatch_after_menu_close(data) {
                openMenu();
                mouseClick(control(data.button));
                tryCompare(menu(), "visible", false);
                compare(data.spy.count, 1);
                const argument = data.spy.signalArguments[0][0];
                compare(data.tag === "quiz" ? argument.id : argument, "fixture-session");
            }
            function test_capabilities_and_busy() {
                practice.submissionSupported = false;
                practice.persistenceSupported = false;
                practice.quizSupported = false;
                practice.discardSupported = false;
                practice.checkworkSupported = false;
                verify(!control("practiceSubmitButton").visible);
                verify(!control("practiceSuspendButton").visible);
                verify(!control("practiceReportsButton").visible);
                openMenu();
                verify(!control("practiceSaveButton").visible);
                verify(!control("practiceQuizButton").visible);
                verify(!control("discardCheckpointButton").visible);
                verify(control("practiceStopButton").enabled);
                practice.busy = true;
                tryCompare(menu(), "visible", false);
                verify(!control("practiceMoreActions").enabled);
                verify(!control("practiceResetButton").enabled);
            }
            function test_session_states_data() {
                return [{tag:"suspended",state:"SUSPENDED",saved:true,resume:true,stop:true},
                    {tag:"preparing",state:"PREPARING",saved:false,resume:false,stop:true},
                    {tag:"resetting",state:"RESETTING",saved:false,resume:false,stop:true},
                    {tag:"stopped-saved",state:"STOPPED",saved:true,resume:true,stop:false},
                    {tag:"stopped",state:"STOPPED",saved:false,resume:false,stop:false},
                    {tag:"failed",state:"FAILED",saved:true,resume:false,stop:true}];
            }
            function test_session_states(data) {
                practice.session = checks.fixture(data.state, data.saved);
                waitForRendering(practice);
                verify(!control("practiceSubmitButton").visible);
                verify(!control("practiceSuspendButton").visible);
                compare(control("practiceResumeButton").visible, data.resume);
                if (data.resume) {
                    mouseClick(control("practiceResumeButton"));
                    compare(resumeSpy.count, 1);
                }
                openMenu();
                verify(!control("practiceSaveButton").enabled);
                compare(control("practiceStopButton").enabled, data.stop);
                compare(control("discardCheckpointButton").visible, data.saved);
            }
            function test_switch_session_or_leave_cancels_menu() {
                openMenu();
                menu().pendingAction = "stop";
                practice.session = Object.assign({}, practice.session, {id:"other-session"});
                tryCompare(menu(), "visible", false);
                compare(stopSpy.count, 0);
                openMenu();
                menu().pendingAction = "reset";
                practice.visible = false;
                tryCompare(menu(), "visible", false);
                compare(resetSpy.count, 0);
            }
            function test_keyboard_and_outside_dismissal() {
                control("practiceMoreActions").forceActiveFocus(Qt.TabFocusReason);
                keyClick(Qt.Key_Space);
                tryCompare(menu(), "opened", true);
                keyClick(Qt.Key_Down);
                keyClick(Qt.Key_Return);
                tryCompare(menu(), "visible", false);
                compare(saveSpy.count, 1);
                openMenu();
                mouseClick(window.contentItem, window.width - 20, window.height - 20);
                tryCompare(menu(), "visible", false);
                compare(stopSpy.count, 0);
            }
            function test_busy_during_menu_exit_cancels_action() {
                Studio.Theme.reducedMotion = false;
                openMenu();
                mouseClick(control("practiceStopButton"));
                practice.busy = true;
                tryCompare(menu(), "visible", false);
                compare(stopSpy.count, 0);
            }
            function test_no_session_hides_controls() {
                practice.session = null;
                practice.sessions = [];
                waitForRendering(practice);
                verify(!control("practiceActionBar").visible);
                verify(!control("practiceReportsButton").visible);
                verify(!menu().visible);
            }
            function test_layout_data() {
                return [{tag:"desktop-dark",width:1280,height:800,zoom:100,theme:"dark"},
                    {tag:"desktop-light",width:1280,height:800,zoom:100,theme:"light"},
                    {tag:"compact",width:760,height:700,zoom:100,theme:"dark"},
                    {tag:"zoom150",width:1024,height:820,zoom:150,theme:"dark"}];
            }
            function test_layout(data) {
                window.width = data.width; window.height = data.height;
                Studio.Theme.setZoomPercent(data.zoom);
                Studio.Theme.themeMode = data.theme;
                waitForRendering(practice);
                const bar = control("practiceActionBar");
                compare(bar.height, Studio.Theme.controlHeight);
                if (checks.screenshotFolder) grabImage(window.contentItem).save(checks.screenshotFolder + "/practice-" + data.tag + ".png");
                openMenu();
                const origin = menu().contentItem.mapToItem(window.contentItem, 0, 0);
                verify(origin.x >= 0 && origin.y >= 0);
                verify(origin.x + menu().contentItem.width * Studio.Theme.zoomFactor <= window.width);
                if (checks.screenshotFolder) grabImage(window.contentItem).save(checks.screenshotFolder + "/menu-" + data.tag + ".png");
            }
            function test_tree_rows_hierarchy() {
                const sampleFiles = [
                    { path: ".config/Mousepad/accels.scm", kind: "file", size: 7182, live: true },
                    { path: ".config/dconf/user", kind: "file", size: 563, live: true },
                    { path: "welcome.txt", kind: "file", size: 35, live: true }
                ];
                const rows = Files.treeRows(sampleFiles);
                verify(rows.length >= 5);
                const configRow = rows.find(r => r.name === ".config/");
                const dconfRow = rows.find(r => r.name === "dconf/");
                const userRow = rows.find(r => r.name === "user");
                const mousepadRow = rows.find(r => r.name === "Mousepad/");
                const accelsRow = rows.find(r => r.name === "accels.scm");
                verify(configRow && dconfRow && userRow && mousepadRow && accelsRow);
                compare(configRow.depth, 0);
                compare(dconfRow.depth, 1);
                compare(mousepadRow.depth, 1);
                compare(userRow.depth, 2);
                compare(accelsRow.depth, 2);
                verify(dconfRow.depth < userRow.depth);
                verify(mousepadRow.depth < accelsRow.depth);
                compare(dconfRow.depth, mousepadRow.depth);
            }
        }
    }
}
