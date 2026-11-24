import QtQuick
import QtQuick.Controls.Basic
import QtQuick.Layouts
import QtTest
import ".." as Studio
import "../views/editor" as Editor

Item {
    id: checks
    property string screenshotFolder: ""
    QtObject {
        id: backend
        property var requests: []
        property var callbacks: []
        function request(argv, callback) {
            requests = requests.concat([argv]);
            callbacks = callbacks.concat([callback]);
        }
        function reply(index, result, error) { callbacks[index](result, error || ""); }
    }
    QtObject {
        id: editor
        property var backend: backend
        property var draft: ({id: "fixture", revision: 1})
        property var document: ({nodes: []})
        property var policy: ({software_preparation: true, software_catalog: {
            max_packages: 32, resources: {memory_mb: 2048, cpu_millicores: 2000},
            applications: [{id: "wireshark", name: "Wireshark", command: "wireshark"}, {id: "firefox", name: "Firefox", command: "firefox"}],
            packages: [{id: "openssh-client", name: "SSH client", description: "Kết nối SSH", keywords: "remote"},
                       {id: "nano", name: "Nano", description: "Soạn thảo trong terminal", keywords: "editor"},
                       {id: "python3", name: "Python", description: "Chạy chương trình Python", keywords: "script"}]
        }})
        property bool dirty: false
        property int documentGeneration: 0
        function commit(value) { document = value; dirty = true; ++documentGeneration; }
        function change(section, index, field, value) {
            const copy = JSON.parse(JSON.stringify(document));
            copy[section][index][field] = value;
            commit(copy);
        }
        function save(callback) { draft = {id: draft.id, revision: draft.revision + 1}; dirty = false; callback(); }
        function adopt(result, preserve) {
            draft = {id: result.id, revision: result.revision};
            if (!preserve) { document = JSON.parse(result.definition); dirty = false; }
        }
    }
    ApplicationWindow {
        id: window
        width: 620
        height: 850
        visible: true
        color: Studio.Theme.surface
        Flickable {
            anchors.fill: parent
            contentHeight: column.implicitHeight
            clip: true
            ColumnLayout {
                id: column
                width: parent.width
                Editor.NodeSoftwareEditor { id: panel; editor: editor; nodeIndex: 0 }
            }
        }
    }
    TestCase {
        name: "NodeSoftwareEditor"
        when: windowShown
        function test_optionalPreparationHint() {
            compare(control("softwarePreparationHint").text, "Cài sẵn để khởi động nhanh hơn.");
            verify(control("prepareNodeSoftware").visible);
        }
        function node() { return {id: "client", image: "cyberlab/ubuntu:24.04-1", resources: {memory_mb: 512, cpu_millicores: 1000}}; }
        function control(name) { const item = findChild(panel, name); verify(item !== null, name); return item; }
        function job(state) { return {id: "job", draft: editor.draft.id, revision: editor.draft.revision, node: "client", state: state, progress: 50}; }
        function choose(name) { const item = control(name); item.toggle(); item.toggled(); }
        function chooseApp(name) { choose("softwareApp-" + name); }
        function choosePackage(name) { choose("softwarePackage-" + name); }
        function repositoryFixture() {
            return [{id: "wireshark", name: "wireshark", description: "network traffic analyzer", application: true},
                    {id: "openssh-client", name: "openssh-client", description: "secure shell client"},
                    {id: "nano", name: "nano", description: "small text editor"},
                    {id: "python3", name: "python3", description: "interactive high-level language"}];
        }
        function test_selected_rows_have_no_persistent_background_data() {
            return [{tag: "dark", mode: "dark"}, {tag: "light", mode: "light"}];
        }
        function test_selected_rows_have_no_persistent_background(data) {
            const previousMode = Studio.Theme.themeMode;
            Studio.Theme.themeMode = data.mode;
            try {
                for (const name of ["softwareApp-wireshark", "softwarePackage-openssh-client"]) {
                    choose(name);
                    const item = control(name);
                    verify(item.checked);
                    mouseMove(window.contentItem, window.width - 2, window.height - 2);
                    item.focus = false;
                    tryCompare(item, "hovered", false);
                    compare(item.background.color.a, 0);
                    if (checks.screenshotFolder) {
                        waitForRendering(window.contentItem);
                        grabImage(window.contentItem).save(checks.screenshotFolder + "/selected-" + data.mode + "-" + name + ".png");
                    }
                    choose(name);
                    verify(!control(name).checked);
                }
            } finally {
                Studio.Theme.themeMode = previousMode;
            }
        }
        function enableSearch() { editor.policy = Object.assign({}, editor.policy, {software_search: true}); }
        function replySearch(index, state, packages) { backend.reply(index, {state: state, total: packages.length, packages: packages}); }
        function test_repository_is_only_source_of_choices() {
            control("softwareRepositorySearch").results = [];
            compare(control("softwarePicker").matches, []);
            control("softwareRepositorySearch").results = [{id: "iputils-ping", name: "iputils-ping", description: "ICMP echo tool"}];
            compare(control("softwarePicker").matches.length, 1);
            compare(control("softwarePicker").matches[0].name, "iputils-ping");
            compare(findChild(panel, "softwareApp-firefox"), null);
            choosePackage("iputils-ping");
            compare(editor.document.nodes[0].software.packages, ["iputils-ping"]);
            compare(control("selectedPackage-iputils-ping").text, "iputils-ping");
        }
        function test_opening_picker_browses_repository() {
            enableSearch();
            tryCompare(backend, "requests", [["draft", "software-search", ""]]);
            replySearch(0, "ready", [{id: "nano", name: "nano", description: "small editor"}]);
            compare(control("softwarePicker").matches.length, 1);
            compare(control("softwarePicker").matches[0].name, "nano");
        }
        function test_firefox_sources_remain_distinct_and_use_reviewed_recipe() {
            const ubuntu = {id: "firefox", name: "firefox", description: "Transitional browser", source: "ubuntu", installable: false, unavailable_reason: "snap"};
            const mozilla = {id: "firefox", name: "firefox", description: "Firefox web browser", source: "mozilla", installable: true, application: true};
            control("softwareRepositorySearch").results = [mozilla, ubuntu];
            wait(30);
            verify(!control("softwarePackage-firefox").enabled);
            verify(control("softwareApp-firefox").enabled);
            verify(control("softwareAvailability-ubuntu-firefox").text.includes("Snap"));
            compare(control("softwareSource-mozilla-firefox").text, "Mozilla APT");
            control("softwarePicker").select(ubuntu, true);
            compare(editor.document.nodes[0].software, undefined);
            verify(panel.problem.includes("Snap"));
            chooseApp("firefox");
            compare(editor.document.nodes[0].software.apps, ["firefox"]);
            compare(editor.document.nodes[0].software.packages, []);
            verify(!control("softwarePackage-firefox").checked);
            verify(control("selectedApp-firefox").text.includes("Mozilla"));
            if (checks.screenshotFolder) {
                waitForRendering(window.contentItem);
                grabImage(window.contentItem).save(checks.screenshotFolder + "/firefox-sources.png");
            }
            control("selectedApp-firefox").clicked();
            compare(editor.document.nodes[0].software.apps, []);
        }
        function test_partial_source_failure_keeps_results_and_offers_retry() {
            enableSearch();
            control("softwarePackageSearch").text = "firefox";
            tryCompare(control("softwareRepositorySearch"), "inFlight", true);
            backend.reply(0, {state: "ready", total: 1, packages: [{id: "firefox", name: "firefox", source: "ubuntu", installable: false, unavailable_reason: "snap"}], source_errors: ["mozilla"]});
            wait(30);
            compare(control("softwareRepositorySearch").sourceErrors, ["mozilla"]);
            verify(control("softwareSearchRetry").visible);
            compare(control("softwarePicker").matches.length, 1);
            control("softwareSearchRetry").clicked();
            compare(backend.requests[1], ["draft", "software-search", "firefox", "--refresh"]);
            replySearch(1, "ready", []);
            compare(control("softwareRepositorySearch").sourceErrors, []);
        }
        function test_saved_external_app_is_preserved_but_not_offered() {
            const machine = node();
            machine.software = {gui: true, apps: ["firefox"], packages: ["obsolete-package"]};
            editor.document = {nodes: [machine]};
            compare(control("selectedApp-firefox").text, "firefox · Mozilla");
            compare(control("selectedPackage-obsolete-package").text, "obsolete-package");
            compare(findChild(panel, "softwareApp-firefox"), null);
            verify(!editor.dirty);
            control("selectedApp-firefox").clicked();
            compare(editor.document.nodes[0].software.apps, []);
            compare(editor.document.nodes[0].software.packages, ["obsolete-package"]);
        }
        function init() {
            editor.policy = Object.assign({}, editor.policy, {software_search: false});
            control("softwarePicker").reset();
            editor.draft = {id: "fixture", revision: 1};
            editor.document = {nodes: [node(), Object.assign(node(), {id: "second"})]};
            editor.dirty = false;
            panel.nodeIndex = 0;
            window.width = 620;
            wait(30);
            backend.requests = [];
            backend.callbacks = [];
            control("softwareRepositorySearch").results = repositoryFixture();
            wait(30);
        }
        function test_gui_is_default_without_switch() {
            verify(control("softwarePackageSearch").visible);
            compare(findChild(panel, "softwareBrowseToggle"), null);
            compare(findChild(panel, "softwarePackagesInput"), null);
            compare(findChild(panel, "nodeGuiEnabled"), null);
            compare(findChild(panel, "softwareGuiDefault"), null);
            verify(!control("softwarePreparationStatus").visible);
            verify(control("prepareNodeSoftware").enabled);
            compare(editor.document.nodes[0].software, undefined);
            verify(!editor.dirty, "Opening old drafts must not silently migrate them");
        }
        function test_prepare_gui_without_selecting_packages() {
            panel.prepare();
            verify(editor.document.nodes[0].software.gui);
            compare(editor.document.nodes[0].software.apps, []);
            compare(editor.document.nodes[0].software.packages, []);
            compare(editor.document.nodes[0].resources.memory_mb, 2048);
            compare(backend.requests[0][1], "software-prepare");
            compare(backend.requests[0][5], String(editor.draft.revision));
        }
        function test_legacy_prepared_environment_is_invalidated_when_enabling_gui() {
            const machine = node();
            machine.software = {gui: false, apps: [], packages: ["nano"], environment: "sha256:legacy"};
            editor.document = {nodes: [machine]};
            choosePackage("python3");
            verify(editor.document.nodes[0].software.gui);
            compare(editor.document.nodes[0].software.environment, undefined);
            compare(editor.document.nodes[0].software.packages, ["nano", "python3"]);
        }
        function test_unsupported_machine_and_missing_policy_do_not_prepare() {
            editor.document = {nodes: [Object.assign(node(), {image: "busybox:1.37.0"})]};
            wait(20);
            verify(!control("softwarePicker").visible);
            panel.prepare();
            compare(backend.requests.length, 0);
            const policy = editor.policy;
            editor.policy = null;
            wait(20);
            panel.prepare();
            compare(backend.requests.length, 0);
            editor.policy = policy;
        }
        function test_legacy_package_only_image_needs_gui_preparation() {
            const machine = node();
            machine.software = {gui: false, apps: [], packages: ["nano"], environment: "sha256:legacy"};
            editor.document = {nodes: [machine]};
            wait(20);
            compare(backend.requests[0][1], "software-plan");
            backend.reply(0, {ready: true});
            verify(!panel.ready);
            verify(control("prepareNodeSoftware").enabled);
            panel.prepare();
            verify(editor.document.nodes[0].software.gui);
            compare(editor.document.nodes[0].software.environment, undefined);
            compare(backend.requests[1][1], "software-prepare");
        }
        function test_gui_enabled_with_software_and_preserves_packages() {
            chooseApp("wireshark");
            choosePackage("nano");
            verify(editor.document.nodes[0].software.gui);
            compare(editor.document.nodes[0].resources.memory_mb, 2048);
            compare(editor.document.nodes[0].software.apps, ["wireshark"]);
            compare(editor.document.nodes[0].software.packages, ["nano"]);
        }
        function test_mouse_and_keyboard() {
            window.requestActivate();
            mouseClick(control("softwareApp-wireshark"));
            compare(editor.document.nodes[0].software.apps, ["wireshark"]);
            control("softwarePackage-python3").forceActiveFocus();
            tryCompare(control("softwarePackage-python3"), "activeFocus", true);
            keyClick(Qt.Key_Space);
            compare(editor.document.nodes[0].software.packages, ["python3"]);
            verify(editor.document.nodes[0].software.gui);
        }
        function test_packages_only_and_limit() {
            choosePackage("nano");
            verify(editor.document.nodes[0].software.gui);
            compare(editor.document.nodes[0].resources.memory_mb, 2048);
            const machine = node();
            machine.software = {gui: false, apps: [], packages: Array.from({length: 32}, (_, index) => "pkg" + index)};
            editor.document = {nodes: [machine]};
            choosePackage("nano");
            compare(editor.document.nodes[0].software.packages.length, 32);
            verify(!control("softwarePackage-nano").checked);
            verify(panel.problem.length > 0);
        }
        function test_selected_remain_visible_when_filtering() {
            choosePackage("python3");
            control("softwarePackageSearch").text = "soan thao";
            control("softwareRepositorySearch").results = repositoryFixture().filter(entry => entry.id === "nano");
            wait(20);
            verify(control("softwarePackage-nano").visible);
            verify(control("selectedPackage-python3").visible);
            control("selectedPackage-python3").clicked();
            compare(editor.document.nodes[0].software.packages, []);
            verify(editor.document.nodes[0].software.gui);
        }
        function test_gui_does_not_reduce_resources() {
            const machine = node();
            machine.resources = {memory_mb: 4096, cpu_millicores: 4000};
            editor.document = {nodes: [machine]};
            choosePackage("nano");
            compare(editor.document.nodes[0].resources.memory_mb, 4096);
            compare(editor.document.nodes[0].resources.cpu_millicores, 4000);
        }
        function test_legacy_gui_only_and_unknown_package() {
            const machine = node();
            machine.software = {gui: true, apps: [], packages: ["mousepad"]};
            editor.document = {nodes: [machine]};
            verify(control("selectedPackage-mousepad").visible);
            control("selectedPackage-mousepad").clicked();
            verify(editor.document.nodes[0].software.gui);
            compare(editor.document.nodes[0].software.packages, []);
        }
        function test_search_debounces_and_selects_remote_package() {
            enableSearch();
            control("softwarePackageSearch").text = "mou";
            wait(80);
            control("softwarePackageSearch").text = "mouse";
            tryCompare(backend, "requests", [["draft", "software-search", "mouse"]]);
            replySearch(0, "ready", [{id: "mousepad", name: "mousepad", description: "Simple text editor"}]);
            wait(20);
            choosePackage("mousepad");
            compare(editor.document.nodes[0].software.packages, ["mousepad"]);
            verify(editor.document.nodes[0].software.gui);
        }
        function test_old_search_reply_is_ignored() {
            enableSearch();
            control("softwarePackageSearch").text = "mouse";
            tryCompare(control("softwareRepositorySearch"), "inFlight", true);
            control("softwarePackageSearch").text = "editor";
            wait(400);
            compare(backend.requests.length, 2);
            replySearch(1, "ready", [{id: "gedit", name: "gedit", description: "Text editor"}]);
            replySearch(0, "ready", [{id: "mousepad", name: "mousepad", description: "Text editor"}]);
            compare(control("softwareRepositorySearch").results[0].id, "gedit");
        }
        function test_search_loading_poll_and_failure_keeps_selection() {
            choosePackage("nano");
            enableSearch();
            control("softwarePackageSearch").text = "editor";
            tryCompare(control("softwareRepositorySearch"), "inFlight", true);
            replySearch(0, "loading", []);
            verify(control("softwareRepositorySearch").loading);
            tryVerify(() => backend.requests.length === 2, 2500);
            backend.reply(1, null, "offline");
            compare(control("softwareRepositorySearch").state, "error");
            compare(editor.document.nodes[0].software.packages, ["nano"]);
            control("softwareSearchRetry").clicked();
            compare(backend.requests[2], ["draft", "software-search", "editor", "--refresh"]);
            replySearch(2, "ready", []);
        }
        function test_switch_node_clears_search_and_ignores_reply() {
            enableSearch();
            control("softwarePackageSearch").text = "mouse";
            tryCompare(control("softwareRepositorySearch"), "inFlight", true);
            panel.nodeIndex = 1;
            replySearch(0, "ready", [{id: "mousepad", name: "mousepad"}]);
            compare(control("softwarePackageSearch").text, "");
            compare(control("softwareRepositorySearch").results, []);
            compare(editor.document.nodes[1].software, undefined);
        }
        function test_preparing_disables_changes() {
            choosePackage("nano");
            panel.job = job("PREPARING");
            verify(control("softwarePreparationStatus").visible);
            compare(control("softwarePreparationStatus").text, "Đang cài phần mềm…");
            verify(!control("softwarePackageSearch").enabled);
            verify(!control("prepareNodeSoftware").enabled);
            control("softwarePicker").select({id: "python3"}, true);
            compare(editor.document.nodes[0].software.packages, ["nano"]);
            panel.job = null;
        }
        function test_cached_ready_applies_without_poll() {
            chooseApp("wireshark");
            panel.prepare();
            compare(backend.requests[0][1], "software-prepare");
            backend.reply(0, job("READY"));
            compare(backend.requests[1][1], "software-apply");
            const copy = JSON.parse(JSON.stringify(editor.document));
            copy.nodes[0].software.environment = "sha256:fixture";
            backend.reply(1, {id: "fixture", revision: 3, definition: JSON.stringify(copy)});
            wait(20);
            const last = backend.requests.length - 1;
            compare(backend.requests[last][1], "software-plan");
            backend.reply(last, {ready: true});
            verify(panel.ready);
            compare(control("prepareNodeSoftware").text, "Đã cài");
            verify(!control("softwarePreparationStatus").visible);
        }
        function test_failure_status_remains_visible() {
            panel.problem = "Không thể cài phần mềm.";
            verify(control("softwarePreparationStatus").visible);
            compare(control("softwarePreparationStatus").text, panel.problem);
            panel.problem = "";
            panel.job = Object.assign(job("FAILED"), {error: "Không thể tải gói phần mềm."});
            verify(control("softwarePreparationStatus").visible);
            compare(control("softwarePreparationStatus").text, panel.job.error);
            panel.job = Object.assign(job("FAILED"), {error: "Software preparation interrupted; retry when storage is available"});
            compare(control("softwarePreparationStatus").text, "Cài phần mềm bị gián đoạn. Hãy kiểm tra dung lượng lưu trữ rồi thử lại.");
            verify(!panel.preparing);
            verify(panel.editable);
            verify(control("prepareNodeSoftware").enabled);
            panel.job = null;
        }
        function test_switching_node_discards_old_reply_but_keeps_declarations() {
            chooseApp("wireshark");
            panel.prepare();
            const old = job("READY");
            panel.nodeIndex = 1;
            backend.reply(0, old);
            compare(panel.job, null);
            compare(editor.document.nodes[0].software.apps, ["wireshark"]);
            compare(editor.document.nodes[1].software, undefined);
        }
        function test_imported_image_is_not_assumed_ready() {
            const machine = node();
            machine.software = {gui: true, apps: ["firefox"], packages: [], environment: "sha256:elsewhere"};
            editor.document = {nodes: [machine]};
            wait(20);
            compare(backend.requests[0][1], "software-plan");
            backend.reply(0, {ready: false});
            verify(!panel.ready);
            verify(!control("softwarePreparationStatus").visible);
            verify(control("prepareNodeSoftware").enabled);
        }
        function test_reopened_ready_job_and_unsaved_edits() {
            chooseApp("wireshark");
            editor.dirty = false;
            wait(20);
            backend.reply(0, {ready: false, latest_job: job("READY")});
            compare(backend.requests[1][1], "software-apply");
            const prepared = JSON.parse(JSON.stringify(editor.document));
            prepared.nodes[0].software.environment = "sha256:fixture";
            editor.change("nodes", 0, "hostname", "keep-me");
            backend.reply(1, {id: "fixture", revision: 2, definition: JSON.stringify(prepared)});
            compare(editor.document.nodes[0].hostname, "keep-me");
            verify(editor.dirty);
        }
        function test_compact_layout() {
            compare(findChild(panel, "softwareGuiDefault"), null);
            chooseApp("wireshark");
            choosePackage("python3");
            window.width = 360;
            waitForPolish(column);
            wait(30);
            for (const name of ["softwarePackageSearch", "softwareResults", "prepareNodeSoftware"]) {
                const item = control(name);
                const bounds = item.mapToItem(window.contentItem, 0, 0, item.width, item.height);
                verify(bounds.x >= 0 && bounds.x + bounds.width <= window.width + 1, name);
            }
            if (checks.screenshotFolder) grabImage(window.contentItem).save(checks.screenshotFolder + "/software-compact.png");
            window.width = 620;
            waitForPolish(column);
            wait(30);
            if (checks.screenshotFolder) grabImage(window.contentItem).save(checks.screenshotFolder + "/software-expanded.png");
        }
    }
}
