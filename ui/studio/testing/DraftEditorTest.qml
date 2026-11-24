import QtQuick
import QtQuick.Controls.Basic
import QtTest
import ".." as Studio
import "../models/NodeDefaults.js" as NodeDefaults
import "../models/EditorModel.js" as Model
import "../models/StartupModel.js" as Startup

Item {
    id: checks
    property string screenshotFolder: ""
    readonly property var service: draftEditor.service
    readonly property var backendObject: backend

    function snapshot() {
        return {
            id: "fixture-editor", revision: 3, digest: "fixture-digest", assets: [],
            definition: JSON.stringify({
                schema_version: 1,
                metadata: {id: "mang-co-ban", name: "Mạng cơ bản", version: "1.0", tags: ["linux"]},
                nodes: [{id: "client", image: "fixture:latest", command: ["sleep", "infinity"], networks: ["lan"], terminal_count: 1}],
                networks: [{id: "lan", subnet: "10.90.0.0/24"}], terminals: ["client"]
            })
        };
    }
    function checkUbuntuDefaults() {
        const user = {name: "student", uid: 2000, gid: 2000, home: "/home/student", shell: "/bin/bash"};
        const policy = {allowed_images: ["cyberlab/ubuntu:24.04-1"], image_profiles: [{
            image: "cyberlab/ubuntu:24.04-1", label: "Ubuntu", workstation: true,
            command: ["sleep", "infinity"], accounts: [user], resources: {memory_mb: 512, cpu_millicores: 1000}
        }]};
        const node = NodeDefaults.newNode({nodes: [], networks: []}, policy, "client");
        return {node: node, accounts: NodeDefaults.accountOptions(policy, node)};
    }
    QtObject {
        id: backend
        property bool busy: false
        property var capabilities: ["authoring", "lab-package-export"]
        property var requests: []
        property var callbacks: []
        property var notices: []
        function request(argv, callback, input) {
            requests = requests.concat([{argv: argv, input: input || ""}]);
            callbacks = callbacks.concat([callback]);
        }
        function reply(index, result, error) { callbacks[index](result, error || ""); }
        function notify(message, failed) { notices = notices.concat([{message: message, failed: failed}]); }
    }
    ApplicationWindow {
        id: window
        width: 1280
        height: 820
        visible: true
        color: Studio.Theme.surface
        palette: Studio.Theme.controlPalette
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
            Studio.DraftEditor {
                id: draftEditor
                anchors.fill: parent
                anchors.margins: Studio.Theme.contentInset
                anchors.topMargin: 0
                backend: checks.backendObject
            }
        }
        SignalSpy { id: exportSpy; target: draftEditor; signalName: "exportPackageRequested" }
        SignalSpy { id: backSpy; target: draftEditor; signalName: "backRequested" }
        SignalSpy { id: errorEvents; target: Studio.StudioFeedback; signalName: "errorRequested" }
        TestCase {
            name: "StudioDraftEditor"
            when: window.visible

            function test_overview_has_labels_without_redundant_explanations() {
                compare(control("draftMetadataCard").description, "");
                compare(control("draftContentsCard").description, "");
                verify(control("draftMetadataName").visible);
                verify(control("draftMetadataId").visible);
                verify(control("draftMetadataTopics").visible);
                verify(control("draftOverviewLink-1").visible);
                verify(control("draftProtectionCard").visible);
                verify(control("editProtectionSettings").visible);
            }

            function test_difficulty_overview_preserves_legacy_until_explicit_choice() {
                const difficulty = control("draftMetadataDifficulty");
                verify(difficulty !== null);
                compare(difficulty.currentValue, "");
                verify(!Object.prototype.hasOwnProperty.call(checks.service.document.metadata, "difficulty"));
                verify(!checks.service.dirty);
                difficulty.activated(3);
                compare(checks.service.document.metadata.difficulty, "hard");
                verify(checks.service.dirty);
                compare(checks.service.document.metadata.tags, ["linux"]);
                difficulty.activated(0);
                verify(!Object.prototype.hasOwnProperty.call(JSON.parse(checks.service.definition).metadata, "difficulty"));
                compare(checks.service.document.metadata.name, "Mạng cơ bản");
            }

            function test_difficulty_overview_tracks_loaded_document() {
                const loaded = checks.snapshot();
                const document = JSON.parse(loaded.definition);
                document.metadata.difficulty = "medium";
                loaded.definition = JSON.stringify(document);
                checks.service.adopt(loaded, false);
                compare(control("draftMetadataDifficulty").currentValue, "medium");
                verify(!checks.service.dirty);
                checks.service.adopt(checks.snapshot(), false);
                compare(control("draftMetadataDifficulty").currentValue, "");
            }

            function test_toolbar_tooltip_inherits_window_theme() {
                const button = control("chooseDraftButton");
                const tooltip = button.ToolTip.toolTip;
                button.ToolTip.show(button.description);
                try {
                    tryCompare(tooltip, "opened", true);
                    for (const mode of ["dark", "light"]) {
                        Studio.Theme.themeMode = mode;
                        tryCompare(tooltip.background, "color", Studio.Theme.surfaceContainerHigh);
                        compare(tooltip.contentItem.color, Studio.Theme.textOnSurface);
                    }
                } finally {
                    button.ToolTip.hide();
                }
            }

            function test_assessment_three_sections_preserve_advanced_data() {
                const document = checks.service.document;
                document.settings = {checkwork: true, master_seed: 42};
                document.assessment = {results: [{id: "result1", node: "client", path: "answer.txt", operator: "exists"}], goals: []};
                checks.service.commit(document);
                checks.service.section = 6;
                settle();
                const tabs = control("labeditCategory");
                verify(tabs.entries !== undefined, "Results, Goals and Quiz must be visible tabs");
                compare(tabs.entries.map(entry => entry.label).join(","), "Results,Goals,Quiz");
                for (let index = 0; index < 3; index++) {
                    tabs.selected(index);
                    settle();
                }
                compare(checks.service.document.settings.master_seed, 42);
                compare(checks.service.document.assessment.results[0].operator, "exists");
                verify(!control("labeditAdvanced").expanded);
            }
            function test_new_quiz_is_preparation_by_default() {
                checks.service.section = 6;
                settle();
                const tabs = control("labeditCategory");
                verify(tabs.entries !== undefined);
                tabs.selected(2);
                settle();
                control("addQuizQuestion-0").clicked();
                verify(checks.service.document.quizzes[0].pre_start);
                compare(checks.service.document.quizzes[0].items[0].answer, 0);
                checks.service.updateQuizItem(0, 0, "question", "Lệnh nào hiển thị địa chỉ mạng?");
                checks.service.updateQuizItem(0, 0, "options", ["ip addr", "mkdir"]);
                settle();
                if (checks.screenshotFolder)
                    grabImage(window.contentItem).save(checks.screenshotFolder + "/quiz-authoring.png");
                control("addQuizGroup").clicked();
                const groups = checks.service.document.quizzes;
                verify(groups[groups.length - 1].pre_start);
            }
            function test_legacy_quiz_stays_optional_on_open_and_edit() {
                const document = checks.service.document;
                document.quiz = [{id: "old", type: "choice", question: "Old question", options: ["A", "B"], answer: 1}];
                checks.service.commit(document);
                const before = checks.service.definition;
                checks.service.section = 6;
                control("labeditCategory").selected(2);
                settle();
                compare(checks.service.definition, before);
                checks.service.updateQuizItem(0, 0, "question", "Edited question");
                verify(!checks.service.document.quizzes[0].pre_start);
                compare(checks.service.document.quizzes[0].items[0].answer, 1);
            }
            function test_extract_selectors_and_goal_references() {
                checks.service.section = 6;
                settle();
                control("addAssessmentResult").clicked();
                checks.service.updateNestedEntry("assessment", "results", 0, "field_id", "2");
                compare(checks.service.document.assessment.results[0].field_id, 2);
                checks.service.updateNestedEntry("assessment", "results", 0, "field_type", "group");
                compare(checks.service.document.assessment.results[0].line_type, "regex");
                checks.service.updateNestedEntry("assessment", "results", 0, "line_type", "line");
                compare(checks.service.document.assessment.results[0].field_type, "token");
                compare(checks.service.document.assessment.results[0].expected, undefined);
                control("labeditCategory").selected(1);
                settle();
                control("addAssessmentGoal").clicked();
                checks.service.updateNestedEntry("assessment", "results", 0, "id", "renamed");
                compare(checks.service.document.assessment.goals[0].result, "renamed");
                checks.service.removeNestedEntry("assessment", "results", 0);
                compare(checks.service.document.assessment.results.length, 1);
                verify(checks.service.localError.length > 0);
            }
            function test_result_goal_layout_data() {
                return [{tag: "wide", width: 1280}, {tag: "narrow", width: 520}];
            }
            function test_collection_types_and_conditional_fields() {
                checks.service.section = 6;
                settle();
                control("addAssessmentResult").clicked();
                const types = ["token", "parens", "quotes", "slash", "group", "search", "line_count", "checksum", "size", "time_delim", "contains", "file_regex", "string_count", "command_count", "param"];
                for (let index = 0; index < types.length; index++) {
                    const picker = control("labedit-result-field-type-0");
                    picker.currentIndex = index;
                    picker.activated(index);
                    settle();
                    compare(checks.service.document.assessment.results[0].field_type, types[index]);
                    compare(control("labedit-result-field-id-0").visible, !["line_count", "checksum", "size", "time_delim"].includes(types[index]));
                    compare(control("labedit-result-line-type-0").visible, ["token", "parens", "quotes", "slash", "group", "search"].includes(types[index]));
                    compare(control("labedit-result-timestamp-0").visible, ["contains", "file_regex", "search"].includes(types[index]));
                }
            }
            function test_result_goal_layout(data) {
                window.width = data.width;
                checks.service.section = 6;
                settle();
                verify(control("addAssessmentResult") !== null);
                control("addAssessmentResult").clicked();
                compare(checks.service.document.assessment.results[0].operator, "collect");
                compare(checks.service.document.assessment.results[0].expected, undefined);
                for (let category = 0; category < 2; category++) {
                    control("labeditCategory").selected(category);
                    settle();
                    if (category === 1) control("addAssessmentGoal").clicked();
                    settle();
                    const grid = control(category === 0 ? "resultFields-0" : "goalFields-0");
                    verify(grid !== null);
                    compare(grid.columns, data.width > 900 ? 3 : 1);
                    contained(grid, control("draftSectionContent"));
                    if (checks.screenshotFolder)
                        grabImage(window.contentItem).save(checks.screenshotFolder + "/assessment-" + category + "-" + data.tag + ".png");
                }
            }
            function test_each_invalid_edit_reports_even_when_message_is_unchanged() {
                errorEvents.clear();
                checks.service.change("nodes", 0, "id", "INVALID");
                tryCompare(errorEvents, "count", 1);
                checks.service.change("nodes", 0, "id", "INVALID AGAIN");
                tryCompare(errorEvents, "count", 2);
                compare(checks.service.document.nodes[0].id, "client");
            }
            function test_library_save_does_not_start_runtime_data() {
                return [{tag: "new", installed: false}, {tag: "update", installed: true}];
            }
            function test_library_save_does_not_start_runtime(data) {
                if (data.installed) checks.service.adopt(editingSnapshot("fixture-editor"), false);
                backend.requests = [];
                backend.callbacks = [];
                checks.service.prepareLibrarySave();
                compare(backend.requests.length, 1);
                compare(backend.requests[0].argv[1], "check");
                backend.reply(0, {valid: true, revision: checks.service.draft.revision, digest: checks.service.draft.digest, issues: []});
                compare(backend.requests.length, 1, "Saving must not run containers or install packages");
                const review = data.installed ? checks.service.updateReview : checks.service.publicationReview;
                verify(review !== null);
                compare(review.digest, checks.service.draft.digest);
            }
            function test_library_save_ignores_changed_revision() {
                checks.service.prepareLibrarySave();
                backend.reply(0, {valid: true, revision: checks.service.draft.revision - 1, digest: checks.service.draft.digest, issues: []});
                compare(checks.service.publicationReview, null);
                compare(checks.service.updateReview, null);
                compare(backend.requests.length, 1);
            }
            function test_report_is_not_replayed_when_switching_review_surfaces() {
                errorEvents.clear();
                checks.service.report = {valid: false, revision: checks.service.draft.revision, digest: checks.service.draft.digest,
                    issues: [{stage: "lab", path: "/", message: "Duplicate node address on a network"}]};
                tryCompare(errorEvents, "count", 1);
                checks.service.section = 5;
                settle();
                checks.service.section = 2;
                settle();
                compare(errorEvents.count, 1);
                checks.service.report = {valid: false, revision: checks.service.draft.revision, digest: checks.service.draft.digest,
                    issues: [{stage: "lab", path: "/", message: "Duplicate node address on a network"}]};
                tryCompare(errorEvents, "count", 2);
            }

            function test_ubuntu_profile_uses_student_home_and_no_nobody_choice() {
                const result = checks.checkUbuntuDefaults();
                compare(result.node.user.home, "/home/student");
                compare(result.node.user.shell, "/bin/bash");
                compare(result.node.resources.memory_mb, 512);
                compare(result.accounts.length, 1);
                compare(result.accounts[0].user.name, "student");
            }
            function test_new_ubuntu_gui_default_and_image_switch() {
                const user = {name: "student", uid: 2000, gid: 2000, home: "/home/student", shell: "/bin/bash"};
                const policy = {software_preparation: true, software_catalog: {resources: {memory_mb: 2048, cpu_millicores: 2000}},
                    allowed_images: ["cyberlab/ubuntu:24.04-1", "busybox:1.37.0"], image_profiles: [
                        {image: "cyberlab/ubuntu:24.04-1", workstation: true, command: ["sleep", "infinity"], accounts: [user], resources: {memory_mb: 512, cpu_millicores: 1000}},
                        {image: "busybox:1.37.0", command: ["sleep", "3600"], accounts: [], resources: {memory_mb: 128, cpu_millicores: 500}}]};
                const node = NodeDefaults.newNode({nodes: [], networks: []}, policy, "client");
                verify(!!node.software && node.software.gui);
                compare(node.resources.memory_mb, 2048);
                const changed = NodeDefaults.changeImage({nodes: [node]}, 0, "busybox:1.37.0", policy);
                verify(!changed.nodes[0].software);
                compare(changed.nodes[0].resources.memory_mb, 128);
                verify(node.software.gui, "Changing image must not mutate the original");
                const back = NodeDefaults.changeImage(changed, 0, node.image, policy);
                verify(back.nodes[0].software.gui);
                node.software.packages = ["nano"];
                let rejected = false;
                try { NodeDefaults.changeImage({nodes: [node]}, 0, "busybox:1.37.0", policy); }
                catch (error) { rejected = true; }
                verify(rejected, "Do not silently discard selected packages");
            }
            function test_machine_network_cards_and_advanced_groups() {
                openUbuntuMachine();
                const next = Model.clone(checks.service.document);
                next.networks.push({id: "guest"});
                next.nodes[0].addresses = {lan: "10.90.0.2"};
                checks.service.commit(next);
                settle();
                verify(control("nodeNetworkToggle-lan") !== null);
                compare(control("nodeNetworkToggle-lan").Accessible.role, Accessible.CheckBox);
                compare(control("nodeNetworkAddressLabel-lan").text, "IP của máy");
                verify(control("nodeNetworkAddress-lan").visible);
                verify(!control("nodeNetworkAddress-guest").visible);
                control("nodeNetworkToggle-guest").toggle();
                control("nodeNetworkToggle-guest").toggled();
                settle();
                verify(checks.service.document.nodes[0].networks.includes("guest"));
                compare(checks.service.document.nodes[0].addresses.lan, "10.90.0.2");
                verify(control("nodeNetworkAutomatic-guest").visible);
                control("nodeAdvancedToggle").clicked();
                settle();
                verify(control("nodeResourceMemory").visible);
                verify(!control("nodeExtraHosts").visible);
                const definition = checks.service.definition;
                control("nodeNetworkAdvanced").expanded = true;
                settle();
                verify(control("nodeExtraHosts").visible);
                compare(checks.service.definition, definition);
                const flick = control("draftSectionScroll").contentItem;
                flick.contentY = Math.max(0, flick.contentHeight - flick.height);
                settle();
                if (checks.screenshotFolder) grabImage(window.contentItem).save(checks.screenshotFolder + "/machine-advanced.png");
            }
            function test_machine_redesign_layout_data() {
                return [{tag: "desktop", width: 1440, theme: "dark"},
                    {tag: "compact", width: 380, theme: "dark"},
                    {tag: "light", width: 1440, theme: "light"}];
            }
            function test_machine_redesign_layout(data) {
                openUbuntuMachine();
                window.width = data.width;
                Studio.Theme.themeMode = data.theme;
                const document = Model.clone(checks.service.document);
                document.networks.push({id: "backend", subnet: "10.90.10.0/28"}, {id: "guest"});
                document.nodes[0].addresses = {lan: "10.90.0.2"};
                checks.service.commit(document);
                settle();
                for (const name of ["basicNodeName", "basicNodeImage", "basicNodeUsername", "basicTerminalCount",
                    "nodeNetworkToggle-lan", "nodeNetworkAddress-lan", "nodeNetworkToggle-guest"])
                    contained(control(name), draftEditor);
                verify(control("nodeNetworkList") !== null);
                const first = control("nodeNetworkRow-lan");
                const second = control("nodeNetworkRow-backend");
                verify(second.y >= first.y + first.height, "Networks are a single compact list, not stretched cards");
                const flick = control("draftSectionScroll").contentItem;
                flick.contentY = Math.max(0, control("nodeConfigurationPanel").mapToItem(flick.contentItem, 0, 0).y - 70);
                settle();
                if (checks.screenshotFolder) grabImage(window.contentItem).save(checks.screenshotFolder + "/machine-configuration-" + data.tag + ".png");
                flick.contentY = Math.max(0, Math.min(flick.contentHeight - flick.height,
                    control("nodeNetworkList").mapToItem(flick.contentItem, 0, 0).y - 16));
                settle();
                if (checks.screenshotFolder) grabImage(window.contentItem).save(checks.screenshotFolder + "/machine-networks-" + data.tag + ".png");
                control("nodeAdvancedToggle").clicked();
                settle();
                for (const name of ["nodeResourceMemory", "nodeResourceCpu", "nodeNetworkAdvanced", "nodeAccountAdvanced"])
                    contained(control(name), draftEditor);
            }
            function test_machine_number_fields_keyboard_updates_document() {
                openUbuntuMachine();
                const terminals = control("basicTerminalCount");
                terminals.forceActiveFocus();
                keyClick(Qt.Key_Up);
                compare(checks.service.document.nodes[0].terminal_count, 2);
                control("nodeAdvancedToggle").clicked();
                settle();
                const memory = control("nodeResourceMemory");
                const previous = memory.value;
                memory.forceActiveFocus();
                keyClick(Qt.Key_Up);
                compare(checks.service.document.nodes[0].resources.memory_mb, previous + memory.stepSize);
            }
            function test_username_default_only_affects_new_ubuntu_nodes() {
                const user = {name: "student", uid: 2000, gid: 2000, home: "/home/student", shell: "/bin/bash"};
                const profile = {image: "cyberlab/ubuntu:24.04-1", label: "Ubuntu", workstation: true, custom_username: true,
                    command: ["sleep", "infinity"], accounts: [user]};
                const policy = {allowed_images: [profile.image], image_profiles: [profile]};
                const original = {nodes: [{id: "old", image: profile.image, user: user}], networks: []};
                const node = NodeDefaults.newNode(original, policy, "new", "alice");
                compare(node.user.name, "alice");
                compare(node.user.home, "/home/alice");
                compare(original.nodes[0].user.name, "student");
                compare(NodeDefaults.newNode(original, policy, "new", "root").user.name, "student");
                verify(!NodeDefaults.validUsername("alice\n"));
                verify(!NodeDefaults.validUsername("alice\r"));
                compare(NodeDefaults.changeImage(original, 0, profile.image, policy, "alice").nodes[0].user.name, "student");
                const switched = NodeDefaults.changeImage({nodes: [{id: "old", image: "busybox:1.37.0", command: ["sleep", "3600"]}], networks: []}, 0, profile.image, policy, "alice");
                compare(switched.nodes[0].user.home, "/home/alice");
                profile.custom_username = false;
                compare(NodeDefaults.newNode(original, policy, "new", "alice").user.name, "student");
            }

            function control(name) { return findChild(draftEditor, name); }
            function openUbuntuMachine() {
                const user = {name: "student", uid: 2000, gid: 2000, home: "/home/student", shell: "/bin/bash"};
                const profile = {image: "cyberlab/ubuntu:24.04-1", label: "Ubuntu", workstation: true, custom_username: true,
                    command: ["sleep", "infinity"], accounts: [user]};
                checks.service.policy = {allowed_images: [profile.image], image_profiles: [profile]};
                const snapshot = checks.snapshot();
                const document = JSON.parse(snapshot.definition);
                Object.assign(document.nodes[0], {image: profile.image, user: user, terminal_title: "student@client",
                    files: [{source: "assets/readme.txt", target: "readme.txt"}]});
                snapshot.definition = JSON.stringify(document);
                checks.service.adopt(snapshot, false);
                checks.service.section = 1;
                settle();
                return control("basicNodeUsername");
            }
            function typeUsername(field, value) {
                mouseClick(field);
                verify(field.activeFocus);
                keyClick(Qt.Key_A, Qt.ControlModifier);
                for (const character of value) keyClick(character);
            }
            function test_machine_username_is_editable_and_updates_home() {
                const field = openUbuntuMachine();
                verify(field.visible);
                verify(!control("basicNodeAccount").visible);
                typeUsername(field, "son");
                keyClick(Qt.Key_Return);
                compare(checks.service.document.nodes[0].user.name, "son");
                compare(checks.service.document.nodes[0].user.home, "/home/son");
                compare(checks.service.document.nodes[0].user.uid, 2000);
                compare(checks.service.document.nodes[0].terminal_title, "son@client");
                compare(checks.service.document.nodes[0].files[0].target, "readme.txt");
                verify(checks.service.dirty);
                compare(backend.requests.length, 0);
                compare(Studio.LabPreferences.username, "student");
                typeUsername(field, "alice");
                keyClick(Qt.Key_Tab);
                compare(checks.service.document.nodes[0].user.home, "/home/alice");
                if (checks.screenshotFolder)
                    grabImage(window.contentItem).save(checks.screenshotFolder + "/editor-username.png");
            }
            function test_machine_username_rejects_invalid_input_and_recovers() {
                const field = openUbuntuMachine();
                for (const invalid of ["root", "1alice", "alice smith", "a".repeat(33)]) {
                    typeUsername(field, invalid);
                    keyClick(Qt.Key_Return);
                    verify(field.error);
                    verify(control("basicNodeUsernameHint").visible);
                    compare(checks.service.document.nodes[0].user.name, "student");
                    verify(!checks.service.dirty);
                }
                typeUsername(field, "son_2");
                keyClick(Qt.Key_Tab);
                verify(!field.error);
                verify(!control("basicNodeUsernameHint").visible);
                compare(checks.service.document.nodes[0].user.name, "son_2");
            }
            function test_machine_account_selector_for_older_daemon_and_other_images() {
                checks.service.section = 1;
                settle();
                verify(!control("basicNodeUsername").visible);
                verify(control("basicNodeAccount").visible);
                openUbuntuMachine();
                const policy = JSON.parse(JSON.stringify(checks.service.policy));
                policy.image_profiles[0].custom_username = false;
                checks.service.policy = policy;
                settle();
                verify(!control("basicNodeUsername").visible);
                verify(control("basicNodeAccount").visible);
                compare(control("basicNodeAccount").currentText, "student");
            }
            function test_machine_username_does_not_rename_another_selected_node() {
                const field = openUbuntuMachine();
                checks.service.addMachine();
                checks.service.selectedNode = 0;
                settle();
                typeUsername(field, "alice");
                checks.service.selectedNode = 1;
                settle();
                keyClick(Qt.Key_Tab);
                compare(checks.service.document.nodes[1].user.name, "student");
                compare(field.text, "student");
            }
            function test_machine_username_compact_layout() {
                const field = openUbuntuMachine();
                verify(!control("basicNodeUsernameHint").visible);
                typeUsername(field, "root");
                window.width = 600;
                settle();
                verify(field.visible);
                contained(field, draftEditor);
                verify(control("basicNodeUsernameHint").visible);
                contained(control("basicNodeUsernameHint"), draftEditor);
                if (checks.screenshotFolder)
                    grabImage(window.contentItem).save(checks.screenshotFolder + "/editor-username-compact.png");
            }
            function startupSnapshot(shared) {
                const snapshot = checks.snapshot();
                const document = JSON.parse(snapshot.definition);
                document.nodes[0].command = ["/bin/bash", "start-client.sh"];
                document.nodes[0].files = [{source: "assets/start-client.sh", target: "start-client.sh"}];
                if (shared) document.nodes.push({id: "server", command: ["/bin/bash", "start-client.sh"], networks: [],
                    files: [{source: "assets/start-client.sh", target: "start-client.sh"}]});
                snapshot.definition = JSON.stringify(document);
                snapshot.assets = [{path: "assets/start-client.sh", kind: "file", size: 40}];
                return snapshot;
            }
            function test_startup_create_is_optional_and_uses_canonical_path() {
                compare(checks.service.startup.dirty, false);
                compare(checks.service.document.nodes[0].files, undefined);
                checks.service.startup.create(checks.service.document.nodes[0]);
                const node = checks.service.document.nodes[0];
                compare(node.command, ["/bin/sh", "start.sh"]);
                compare(node.files, [{source: "assets/startup/client/start.sh", target: "start.sh"}]);
                verify(checks.service.dirty);
                compare(backend.requests.length, 0);
            }
            function test_startup_save_and_export_package() {
                const snapshot = checks.snapshot();
                const document = JSON.parse(snapshot.definition);
                delete document.schema_version;
                document.apiVersion = "cyberlab.ptit/v1";
                document.kind = "Lab";
                document.metadata.version = "1.0.0";
                document.nodes[0].image = "busybox:1.37.0";
                document.networks = [{id: "lan"}];
                document.nodes[0].files = [{source: "assets/files/client", target: "."}];
                document.documentation = "assets/docs/guide.md";
                snapshot.assets = [{path: "assets/files/client/input.txt", kind: "file", size: 4}];
                snapshot.definition = JSON.stringify(document);
                checks.service.adopt(snapshot, false);
                backend.requests = []; backend.callbacks = [];
                checks.service.startup.create(checks.service.document.nodes[0]);
                checks.service.startup.edit(checks.service.document.nodes[0], "#!/bin/sh\nset -eu\nprintf ready > result.txt\n");
                const contents = checks.service.startup.entries["assets/startup/client/start.sh"].text;
                checks.service.save();
                compare(backend.requests[0].argv, ["draft", "save-workspace", snapshot.id, "-", "--revision", "3"]);
                const payload = JSON.parse(backend.requests[0].input);
                compare(payload.entries["assets/startup/client/start.sh"].text, contents);
                const saved = Object.assign({}, snapshot, {revision: 4, definition: payload.definition,
                    assets: snapshot.assets.concat([{path: "assets/startup/client/start.sh", kind: "file", size: contents.length}])});
                backend.reply(0, saved);
                verify(!checks.service.dirty);
                compare(checks.service.document.nodes[0].files.length, 2);
                verify(checks.service.files.rows("client").some(row => row.path === "start.sh"));
                console.log("STARTUP_AUTHORING_PACKAGE:" + JSON.stringify({definition: saved.definition,
                    assets: {"assets/startup/client/start.sh": contents, "assets/files/client/input.txt": "data", "assets/docs/guide.md": "# Practice\n"}}));
            }
            function test_startup_failed_upload_keeps_unsaved_text() {
                checks.service.startup.create(checks.service.document.nodes[0]);
                checks.service.save();
                backend.reply(0, null, "Conflict");
                verify(checks.service.startup.dirty);
                verify(checks.service.dirty);
                compare(backend.requests.length, 1);
                compare(checks.service.localError, "Conflict");
            }
            function test_startup_multiple_scripts_save_with_latest_revision() {
                checks.service.startup.create(checks.service.document.nodes[0]);
                checks.service.addMachine();
                checks.service.startup.create(checks.service.document.nodes[1]);
                checks.service.save();
                const payload = JSON.parse(backend.requests[0].input);
                compare(Object.keys(payload.entries).length, 2);
                backend.reply(0, null, "Conflict");
                verify(checks.service.startup.dirty);
                verify(checks.service.startup.entries["assets/startup/client/start.sh"].dirty);
                checks.service.save();
                compare(backend.requests[1].input, backend.requests[0].input);
                compare(backend.requests[1].argv.slice(-2), ["--revision", "3"]);
            }
            function test_startup_custom_command_survives_opening_tab() {
                checks.service.change("nodes", 0, "command", ["/usr/bin/custom", "--flag", "value with spaces"]);
                const definition = checks.service.definition;
                checks.service.section = 1;
                control("machineEditorTabs").selected(2);
                settle();
                verify(!control("startupScriptToggle").checked);
                verify(!control("startupCustomCommand").visible);
                control("startupAdvancedToggle").clicked();
                settle();
                verify(control("startupCustomCommand").visible);
                compare(control("startupCustomCommand").text, "/usr/bin/custom\n--flag\nvalue with spaces");
                compare(checks.service.definition, definition);
                compare(backend.requests.length, 0);
            }
            function test_startup_import_stale_definition_does_not_replace_command() {
                checks.service.startup.importFile(checks.service.document.nodes[0], "/tmp/start.sh");
                checks.service.change("nodes", 0, "command", ["sleep", "42"]);
                backend.reply(0, Object.assign({}, checks.snapshot(), {revision: 4, assets: [{path: "assets/startup/client/start.sh", kind: "file"}]}));
                compare(checks.service.document.nodes[0].command, ["sleep", "42"]);
                compare(backend.requests.length, 1);
                verify(checks.service.localError.length > 0);
            }
            function test_startup_load_error_can_retry_without_editing_empty_text() {
                checks.service.adopt(startupSnapshot(false), false);
                checks.service.startup.load(checks.service.document.nodes[0]);
                backend.reply(0, null, "Read failed");
                checks.service.startup.edit(checks.service.document.nodes[0], "replacement");
                verify(!checks.service.dirty);
                checks.service.startup.retry(checks.service.document.nodes[0]);
                backend.reply(1, {content: "#!/bin/bash\necho loaded\n"});
                compare(checks.service.startup.entries["assets/start-client.sh"].text, "#!/bin/bash\necho loaded\n");
                verify(!checks.service.dirty);
            }
            function test_startup_buffers_follow_nodes_and_rename() {
                checks.service.startup.create(checks.service.document.nodes[0]);
                checks.service.startup.edit(checks.service.document.nodes[0], "echo client\n");
                checks.service.addMachine();
                checks.service.startup.create(checks.service.document.nodes[1]);
                checks.service.startup.edit(checks.service.document.nodes[1], "echo server\n");
                checks.service.change("nodes", 0, "id", "renamed");
                compare(checks.service.startup.entries[checks.service.startup.descriptor(checks.service.document.nodes[0]).source].text, "echo client\n");
                compare(checks.service.startup.entries[checks.service.startup.descriptor(checks.service.document.nodes[1]).source].text, "echo server\n");
            }
            function test_startup_legacy_script_load_and_stale_reply() {
                checks.service.adopt(startupSnapshot(false), false);
                checks.service.startup.load(checks.service.document.nodes[0]);
                compare(backend.requests[0].argv[3], "assets/start-client.sh");
                checks.service.adopt(Object.assign({}, checks.snapshot(), {id: "different"}), false);
                backend.reply(0, {content: "old script"});
                compare(Object.keys(checks.service.startup.entries).length, 0);
                verify(!checks.service.dirty);
            }
            function test_startup_shared_script_requires_private_copy() {
                checks.service.adopt(startupSnapshot(true), false);
                checks.service.startup.load(checks.service.document.nodes[0]);
                backend.reply(0, {content: "#!/bin/bash\necho shared\n"});
                checks.service.startup.edit(checks.service.document.nodes[0], "changed");
                verify(!checks.service.startup.dirty);
                checks.service.startup.create(checks.service.document.nodes[0], checks.service.startup.entries["assets/start-client.sh"].text);
                compare(checks.service.document.nodes[0].command, ["/bin/bash", "start.sh"]);
                compare(checks.service.document.nodes[1].command, ["/bin/bash", "start-client.sh"]);
                compare(checks.service.startup.entries["assets/start-client.sh"].text, "#!/bin/bash\necho shared\n");
            }
            function test_startup_import_saves_mapping_and_command() {
                checks.service.startup.importFile(checks.service.document.nodes[0], "/tmp/start.sh");
                compare(backend.requests[0].argv, ["draft", "read-local", "/tmp/start.sh"]);
                backend.reply(0, {resources: [{path: "start.sh", kind: "file", content: {text: "#!/bin/bash\necho imported\n"}}]});
                compare(checks.service.document.nodes[0].command, ["/bin/bash", "start.sh"]);
                compare(checks.service.startup.entries["assets/startup/client/start.sh"].text, "#!/bin/bash\necho imported\n");
                verify(checks.service.dirty);
                checks.service.save();
                compare(backend.requests[1].argv[1], "save-workspace");
            }
            function test_startup_conflicting_names_and_mapping_limit() {
                const document = JSON.parse(checks.snapshot().definition);
                document.nodes[0].files = [{source: "assets/files/client", target: "."}];
                const assets = [{path: "assets/files/client/start.sh", kind: "file"}, {path: "assets/startup/client/start.sh", kind: "file"}];
                const plan = Startup.create(document, "client", assets);
                compare(plan.source, "assets/startup/client/start-1.sh");
                compare(plan.target, "start-1.sh");
                compare(plan.document.nodes[0].files[0], {source: "assets/files/client/start.sh", target: "start.sh"});
                const many = [];
                for (let index = 0; index < 16; index++) many.push({path: "assets/files/client/file" + index, kind: "file"});
                let rejected = false;
                try { Startup.create(document, "client", many); } catch (error) { rejected = true; }
                verify(rejected);
                compare(document.nodes[0].files, [{source: "assets/files/client", target: "."}]);
            }
            function test_startup_file_removal_is_blocked_and_new_files_still_work() {
                const snapshot = startupSnapshot(false);
                const document = JSON.parse(snapshot.definition);
                let rejected = false;
                try { Model.removeSeedFile(document, "client", "start-client.sh", snapshot.assets); } catch (error) { rejected = true; }
                verify(rejected);
                const plan = Model.homeUpload(document, "client", "input.txt", false, "", snapshot.assets);
                compare(plan.logical, "assets/files/client/input.txt");
                compare(plan.document.nodes[0].files[1], {source: plan.logical, target: "input.txt"});
                const folder = Model.homeUpload(document, "client", "folder", true, "", snapshot.assets.concat([
                    {path: "assets/files/client/data/file.txt", kind: "file"}]), true);
                compare(folder.document.nodes[0].files[1], {source: "assets/files/client/data", target: "data"});
            }
            function test_startup_keeps_legacy_file_replacement_working() {
                const snapshot = seedSnapshot();
                const plan = Startup.create(JSON.parse(snapshot.definition), "client", snapshot.assets);
                const assets = snapshot.assets.concat([{path: plan.source, kind: "file"}]);
                const upload = Model.homeUpload(plan.document, "client", "orders.csv", false, "", assets);
                compare(upload.logical, "assets/client/orders.csv");
                compare(upload.document, plan.document);
                let rejected = false;
                try { Model.homeUpload(plan.document, "client", plan.target, false, "", assets); } catch (error) { rejected = true; }
                verify(rejected);
            }
            function test_startup_default_mode_retains_script_asset() {
                checks.service.startup.create(checks.service.document.nodes[0]);
                checks.service.section = 1;
                control("machineEditorTabs").selected(2);
                settle();
                verify(control("startupScriptToggle").checked);
                clickStartup("startupScriptToggle");
                compare(checks.service.document.nodes[0].command, ["sleep", "infinity"]);
                compare(checks.service.document.nodes[0].files.length, 1);
                verify(checks.service.startup.dirty);
                clickStartup("startupScriptToggle");
                compare(checks.service.document.nodes[0].command, ["/bin/sh", "start.sh"]);
                compare(checks.service.document.nodes[0].files.length, 1);
            }
            function clickStartup(name) {
                control(name).forceActiveFocus();
                keyClick(Qt.Key_Space);
                settle();
            }
            function openStartup() {
                checks.service.section = 1;
                control("machineEditorTabs").selected(2);
                settle();
            }
            function test_startup_simple_default_has_no_technical_controls() {
                openStartup();
                verify(!control("startupScriptToggle").checked);
                verify(!control("startupScriptText").visible);
                verify(!control("importStartupScript").visible);
                verify(!control("startupShell").visible);
                verify(!control("startupCustomToggle").visible);
                verify(!checks.service.dirty);
                compare(backend.requests.length, 0);
                if (checks.screenshotFolder) grabImage(window.contentItem).save(checks.screenshotFolder + "/editor-startup-default.png");
                clickStartup("startupScriptToggle");
                verify(control("startupScriptToggle").checked);
                verify(control("startupScriptText").visible);
                verify(control("importStartupScript").visible);
                verify(!control("startupShell").visible);
            }
            function test_startup_advanced_does_not_change_script() {
                checks.service.startup.create(checks.service.document.nodes[0]);
                const definition = checks.service.definition;
                openStartup();
                control("startupAdvancedToggle").clicked();
                settle();
                verify(control("startupShell").visible);
                verify(control("startupCustomToggle").visible);
                compare(checks.service.definition, definition);
                control("startupAdvancedToggle").clicked();
                settle();
                verify(!control("startupShell").visible);
                compare(checks.service.definition, definition);
            }
            function test_startup_custom_to_script_cancel_and_restore() {
                const command = ["/usr/bin/custom", "--flag", "value with spaces"];
                checks.service.change("nodes", 0, "command", command);
                openStartup();
                clickStartup("startupScriptToggle");
                verify(control("startupReplaceModeDialog").visible);
                verify(!control("startupScriptToggle").checked);
                control("startupReplaceModeDialog").reject();
                settle();
                compare(checks.service.document.nodes[0].command, command);
                clickStartup("startupScriptToggle");
                control("startupReplaceModeDialog").accept();
                settle();
                verify(control("startupScriptToggle").checked);
                control("startupAdvancedToggle").clicked();
                settle();
                clickStartup("startupCustomToggle");
                verify(control("startupReplaceModeDialog").visible);
                control("startupReplaceModeDialog").reject();
                settle();
                verify(control("startupScriptToggle").checked);
                clickStartup("startupCustomToggle");
                control("startupReplaceModeDialog").accept();
                settle();
                compare(checks.service.document.nodes[0].command, command);
                verify(control("startupCustomCommand").visible);
                compare(checks.service.document.nodes[0].files.length, 1);
            }
            function test_startup_switch_failure_does_not_erase_custom_command() {
                const document = Model.clone(checks.service.document);
                const command = ["/usr/bin/custom", "--keep"];
                document.nodes[0].command = command;
                document.nodes[0].files = [];
                for (let index = 0; index < 16; index++) document.nodes[0].files.push({source: "assets/file" + index, target: "file" + index});
                checks.service.commit(document);
                openStartup();
                clickStartup("startupScriptToggle");
                control("startupReplaceModeDialog").accept();
                settle();
                compare(checks.service.document.nodes[0].command, command);
                verify(checks.service.localError.length > 0);
                verify(!control("startupScriptToggle").checked);
            }
            function test_startup_mode_confirmation_rejects_stale_document() {
                checks.service.change("nodes", 0, "command", ["custom"]);
                openStartup();
                clickStartup("startupScriptToggle");
                checks.service.change("nodes", 0, "command", ["new-command"]);
                control("startupReplaceModeDialog").accept();
                settle();
                compare(checks.service.document.nodes[0].command, ["new-command"]);
            }
            function test_startup_advanced_resets_when_switching_machine() {
                checks.service.addMachine();
                checks.service.selectedNode = 0;
                openStartup();
                control("startupAdvancedToggle").clicked();
                settle();
                verify(control("startupCustomToggle").visible);
                checks.service.selectedNode = 1;
                settle();
                verify(!control("startupCustomToggle").visible);
                compare(checks.service.document.nodes[1].command, ["sleep", "infinity"]);
            }
            function test_startup_editor_visual_data() {
                return [{tag: "desktop", width: 1280}, {tag: "compact", width: 600}];
            }
            function test_startup_editor_visual(data) {
                checks.service.startup.create(checks.service.document.nodes[0]);
                checks.service.section = 1;
                control("machineEditorTabs").selected(2);
                window.width = data.width;
                settle();
                verify(control("startupScriptText").visible);
                contained(control("startupScriptText"), draftEditor);
                verify(control("startupLineNumbers").visible);
                tryVerify(() => control("startupSyntax").text.length > 0);
                contained(control("startupScriptToggle"), draftEditor);
                verify(!control("startupShell").visible);
                verify(!control("startupCustomToggle").visible);
                const field = control("startupScriptText");
                field.forceActiveFocus();
                keyClick(Qt.Key_End, Qt.ControlModifier);
                keyClick("x");
                verify(checks.service.startup.entries["assets/startup/client/start.sh"].text.endsWith("x"));
                const flick = control("draftSectionScroll").contentItem;
                flick.contentY = Math.max(0, flick.contentHeight - flick.height);
                settle();
                if (checks.screenshotFolder) grabImage(window.contentItem).save(checks.screenshotFolder + "/editor-startup-" + data.tag + ".png");
            }
            function destination(index) { return findChild(control("draftSectionNavigation"), "draftSection-" + index); }
            function settle() { waitForPolish(viewport); wait(30); }
            function contained(item, container) {
                const bounds = item.mapToItem(container, 0, 0, item.width, item.height);
                verify(bounds.x >= -1, item.objectName + " left " + bounds.x);
                verify(bounds.x + bounds.width <= container.width + 1, item.objectName + " right");
            }
            function init() {
                Studio.Theme.reducedMotion = true;
                Studio.Theme.themeMode = "dark";
                Studio.Theme.setZoomPercent(100);
                window.width = 1280;
                window.height = 820;
                backend.busy = false;
                backend.capabilities = ["authoring", "lab-package-export"];
                checks.service.draft = null;
                checks.service.policy = {
                    topic_catalog: [{id: "linux", label: "Linux"}, {id: "networking", label: "Mạng máy tính"}],
                    allowed_images: ["fixture:latest"], max_nodes: 4, home_directory_target: true, network_internet: true,
                    max_terminal_slots_per_node: 4, max_terminal_slots_per_lab: 8,
                    image_profiles: [{image: "fixture:latest", label: "Linux thực hành", command: ["sleep", "infinity"], accounts: []}]
                };
                checks.service.adopt(checks.snapshot(), false);
                checks.service.section = 0;
                control("labeditCategory").selected(0);
                control("labeditAdvanced").expanded = false;
                checks.service.localError = "";
                checks.service.runtimeReport = null;
                checks.service.drafts = [];
                draftEditor.contentItem.choosingDraft = false;
                backend.requests = [];
                backend.callbacks = [];
                backend.notices = [];
                checks.service.cancelEditChoice();
                control("machineEditorTabs").selected(0);
                exportSpy.clear();
                backSpy.clear();
                window.requestActivate();
                tryCompare(window, "active", true);
                draftEditor.forceActiveFocus();
                mouseMove(window.contentItem, window.width - 2, window.height - 90);
                settle();
            }
            function cleanup() {
                const chooseDialog = control("chooseDraftConfirmation");
                if (chooseDialog) chooseDialog.close();
                control("draftEditActions").menu.close();
                draftEditor.contentItem.reviewDialog.close();
                for (const name of ["draftReloadDialog", "draftDeleteDialog", "draftPublicationDialog", "seedFilePicker", "seedFolderPicker", "replaceSeedFilesDialog", "deleteSeedFileDialog", "newEditingDraftConfirmation", "editingDraftDialog", "startupReplaceModeDialog"])
                    control(name).close();
                const updateDialog = findChild(draftEditor, "draftUpdateDialog");
                if (updateDialog) updateDialog.close();
                settle();
            }
            function editingSnapshot(identifier) {
                const snapshot = checks.snapshot();
                snapshot.id = identifier;
                snapshot.origin = {lab_id: "mang-co-ban", digest: "catalog-before"};
                return snapshot;
            }
            function test_choose_draft_without_changes() {
                mouseClick(control("chooseDraftButton"));
                settle();
                verify(control("draftLanding").visible);
                compare(backSpy.count, 0);
                compare(backend.requests.length, 0);
            }
            function test_choose_draft_cancel_preserves_changes() {
                checks.service.change("metadata", 0, "name", "Unsaved title");
                checks.service.files.create("client", "pending.py", false);
                checks.service.files.edit("client", "pending.py", "print('pending')");
                checks.service.files.editDocumentation("# Pending guide");
                const definition = checks.service.definition;
                verify(control("chooseDraftButton").enabled);
                mouseClick(control("chooseDraftButton"));
                const dialog = control("chooseDraftConfirmation");
                tryCompare(dialog, "opened", true);
                verify(!control("draftLanding").visible);
                if (checks.screenshotFolder)
                    grabImage(window.contentItem).save(checks.screenshotFolder + "/choose-draft-confirmation.png");
                mouseClick(dialog.cancelButton);
                tryCompare(dialog, "opened", false);
                compare(checks.service.definition, definition);
                compare(checks.service.documentationText, "# Pending guide");
                compare(checks.service.files.activeTab.path, "pending.py");
                verify(checks.service.dirty);
                compare(backSpy.count, 0);
                compare(backend.requests.length, 0);
                mouseClick(control("chooseDraftButton"));
                tryCompare(dialog, "opened", true);
                keyClick(Qt.Key_Escape);
                tryCompare(dialog, "opened", false);
                verify(checks.service.dirty);
                verify(!control("draftLanding").visible);
            }
            function test_choose_draft_discards_only_unsaved_changes() {
                checks.service.change("metadata", 0, "name", "Unsaved title");
                checks.service.files.create("client", "pending.py", false);
                checks.service.files.editDocumentation("# Pending guide");
                verify(control("chooseDraftButton").enabled);
                mouseClick(control("chooseDraftButton"));
                const dialog = control("chooseDraftConfirmation");
                tryCompare(dialog, "opened", true);
                backend.busy = true;
                verify(!dialog.actionButton.enabled);
                backend.busy = false;
                mouseClick(dialog.actionButton);
                settle();
                verify(control("draftLanding").visible);
                verify(!checks.service.dirty);
                compare(checks.service.draft.id, checks.snapshot().id);
                compare(checks.service.definition, checks.snapshot().definition);
                compare(checks.service.files.tabs.length, 0);
                compare(checks.service.documentationText, "");
                compare(backSpy.count, 0);
                compare(backend.requests.length, 0);
                mouseClick(control("resumeDraftButton"));
                settle();
                verify(!control("draftLanding").visible);
                verify(!checks.service.dirty);
            }
            function test_choose_draft_restores_saved_guide_and_opens_another() {
                const saved = checks.snapshot();
                const definition = JSON.parse(saved.definition);
                definition.documentation = "assets/docs/guide.md";
                saved.id = "saved-guide";
                saved.definition = JSON.stringify(definition);
                checks.service.adopt(saved, false);
                backend.reply(0, {content: "# Saved guide"});
                checks.service.files.editDocumentation("# Unsaved guide");
                mouseClick(control("chooseDraftButton"));
                const dialog = control("chooseDraftConfirmation");
                tryCompare(dialog, "opened", true);
                mouseClick(dialog.actionButton);
                settle();
                verify(control("draftLanding").visible);
                verify(!checks.service.dirty);
                compare(backend.requests[1].argv, ["draft", "asset", saved.id, definition.documentation, "--revision", "3", "--text"]);
                backend.reply(1, {content: "# Saved guide"});
                compare(checks.service.documentationText, "# Saved guide");
                checks.service.openDraft("another-draft");
                const another = checks.snapshot();
                another.id = "another-draft";
                backend.reply(2, another);
                settle();
                compare(checks.service.draft.id, "another-draft");
                verify(!control("draftLanding").visible);
                compare(backSpy.count, 0);
                verify(backend.requests.every(request => ["asset", "show"].includes(request.argv[1])));
            }
            function test_open_draft_starts_at_overview_data() {
                return [{tag: "same", identifier: "fixture-editor"}, {tag: "other", identifier: "another-draft"}];
            }
            function test_open_draft_starts_at_overview(data) {
                checks.service.section = 6;
                checks.service.openDraft(data.identifier);
                compare(checks.service.section, 6);
                const opened = checks.snapshot();
                opened.id = data.identifier;
                backend.reply(0, opened);
                compare(checks.service.section, 0);
                compare(checks.service.draft.id, data.identifier);
            }
            function test_failed_open_preserves_section() {
                checks.service.section = 4;
                checks.service.openDraft("another-draft");
                backend.reply(0, null, "Unavailable");
                compare(checks.service.section, 4);
                compare(checks.service.draft.id, "fixture-editor");
            }
            function test_reload_preserves_section() {
                checks.service.section = 2;
                draftEditor.contentItem.reloadRequested();
                backend.reply(0, checks.snapshot());
                compare(checks.service.section, 2);
            }
            function test_adopt_saved_draft_preserves_section() {
                checks.service.section = 6;
                checks.service.adopt(checks.snapshot(), false);
                compare(checks.service.section, 6);
            }
            function test_resume_starts_at_overview_without_discarding_edits() {
                checks.service.section = 4;
                checks.service.documentationText = "Chưa lưu";
                checks.service.documentationDirty = true;
                draftEditor.contentItem.choosingDraft = true;
                settle();
                control("resumeDraftButton").clicked();
                compare(checks.service.section, 0);
                verify(!draftEditor.contentItem.choosingDraft);
                verify(checks.service.dirty);
                compare(checks.service.documentationText, "Chưa lưu");
            }
            function showEditingChoices() {
                checks.service.editLab("mang-co-ban", () => {});
                compare(backend.requests[0].argv, ["draft", "edit", "mang-co-ban"]);
                backend.reply(0, {selection_required: true, lab_id: "mang-co-ban", drafts: [
                    {id: "draft-one", name: "Bài đang soạn", revision: 2, based_on_current: true},
                    {id: "draft-two", name: "Bản nháp giữ thay đổi riêng", revision: 5, based_on_current: false}
                ]});
                const dialog = control("editingDraftDialog");
                tryCompare(dialog, "opened", true);
                settle();
                tryCompare(dialog.contentItem, "count", 2);
                tryVerify(() => dialog.contentItem.itemAtIndex(0) !== null);
                return dialog;
            }
            function test_edit_single_result_opens_without_another_create() {
                let navigated = false;
                checks.service.editLab("mang-co-ban", () => navigated = true);
                backend.reply(0, editingSnapshot("existing"));
                compare(checks.service.draft.id, "existing");
                verify(navigated);
                compare(backend.requests.length, 1);
                verify(!control("editingDraftDialog").opened);
                checks.service.definitionDirty = true;
                checks.service.documentationText = "Chưa lưu";
                checks.service.documentationDirty = true;
                checks.service.section = 6;
                checks.service.editLab("mang-co-ban", () => {});
                compare(checks.service.section, 0);
                compare(backend.requests.length, 1);
                verify(checks.service.dirty);
                compare(checks.service.documentationText, "Chưa lưu");
            }
            function test_edit_other_lab_preserves_unsaved_work() {
                checks.service.definitionDirty = true;
                checks.service.editLab("different", () => {});
                compare(backend.requests.length, 0);
                compare(backend.notices.length, 1);
                verify(checks.service.dirty);
            }
            function test_edit_multiple_cancel_does_not_create_or_replace() {
                showEditingChoices();
                mouseClick(control("cancelEditingDraft"));
                tryCompare(control("editingDraftDialog"), "opened", false);
                compare(backend.requests.length, 1);
                compare(checks.service.draft.id, "fixture-editor");
                compare(checks.service.editChoice, null);
            }
            function test_edit_multiple_choose_exact_draft() {
                const dialog = showEditingChoices();
                mouseClick(dialog.contentItem.itemAtIndex(1));
                compare(backend.requests[1].argv, ["draft", "edit", "mang-co-ban", "--draft", "draft-two"]);
                backend.reply(1, editingSnapshot("draft-two"));
                compare(checks.service.draft.id, "draft-two");
                tryCompare(dialog, "opened", false);
                compare(backend.requests.length, 2);
            }
            function test_edit_new_requires_confirmation_and_keeps_choices_on_error() {
                showEditingChoices();
                mouseClick(control("newSeparateEditingDraft"));
                const confirmation = control("newEditingDraftConfirmation");
                tryCompare(confirmation, "opened", true);
                confirmation.reject();
                compare(backend.requests.length, 1);
                mouseClick(control("newSeparateEditingDraft"));
                tryCompare(confirmation, "opened", true);
                confirmation.accept();
                compare(backend.requests[1].argv, ["draft", "edit", "mang-co-ban", "--new"]);
                backend.reply(1, null, "quota reached");
                verify(control("editingDraftDialog").opened);
                compare(checks.service.draft.id, "fixture-editor");
            }
            function test_edit_reply_preserves_new_local_changes() {
                checks.service.editLab("mang-co-ban", () => {});
                checks.service.definitionDirty = true;
                backend.reply(0, editingSnapshot("existing"));
                compare(checks.service.draft.id, "fixture-editor");
                verify(checks.service.dirty);
            }
            function test_edit_choices_visual_data() {
                return [{tag: "desktop", width: 1280}, {tag: "compact", width: 480}, {tag: "short", width: 600, height: 520}];
            }
            function test_edit_choices_visual(data) {
                window.width = data.width;
                if (data.height) window.height = data.height;
                const dialog = showEditingChoices();
                verify(dialog.width <= window.width);
                verify(dialog.height <= viewport.height);
                const first = dialog.contentItem.itemAtIndex(0);
                verify(first.width > 0);
                if (checks.screenshotFolder)
                    grabImage(window.contentItem).save(checks.screenshotFolder + "/edit-choices-" + data.tag + ".png");
            }
            function test_edit_choices_keyboard_and_busy_guard() {
                const dialog = showEditingChoices();
                const first = dialog.contentItem.itemAtIndex(0);
                tryCompare(first, "activeFocus", true);
                backend.busy = true;
                verify(!first.enabled);
                verify(!control("newSeparateEditingDraft").enabled);
                checks.service.chooseEditingDraft("draft-one", false);
                compare(backend.requests.length, 1);
                backend.busy = false;
                first.forceActiveFocus(Qt.TabFocusReason);
                keyClick(Qt.Key_Space);
                compare(backend.requests[1].argv, ["draft", "edit", "mang-co-ban", "--draft", "draft-one"]);
            }
            function seedSnapshot() {
                const snapshot = checks.snapshot();
                const document = JSON.parse(snapshot.definition);
                document.nodes[0].files = [{source: "assets/client", target: "."}];
                snapshot.definition = JSON.stringify(document);
                snapshot.assets = [{path: "assets/client/orders.csv", kind: "file", size: 24}, {path: "assets/client/data/readme.txt", kind: "file", size: 12}];
                return snapshot;
            }
            function openSeedPicker(folder) {
                checks.service.section = 3;
                settle();
                control("seedFileTree").importRequested("client", "", folder);
                const picker = control(folder ? "seedFolderPicker" : "seedFilePicker");
                tryCompare(picker, "opened", true);
                return picker;
            }
            function test_seed_destination_and_validation() {
                checks.service.section = 3;
                settle();
                verify(control("seedFileTree").visible);
                compare(findChild(draftEditor, "seedFileSubfolder"), null);
                compare(findChild(draftEditor, "seedFileNode"), null);
                checks.service.files.create("client", "../bad", false);
                verify(checks.service.localError.length > 0);
                verify(!checks.service.dirty);
                backend.busy = true;
                verify(!control("draftResources").enabled);
            }
            function test_seed_file_upload_and_mapping_save() {
                const picker = openSeedPicker(false);
                picker.selectedFile = "file:///tmp/host%20files/orders.csv";
                picker.accept();
                compare(backend.requests[0].argv, ["draft", "read-local", "/tmp/host files/orders.csv"]);
                backend.reply(0, {resources: [{path: "orders.csv", kind: "file", content: {text: "orders"}}]});
                verify(checks.service.dirty);
                compare(checks.service.draft.revision, 3);
                checks.service.save();
                compare(backend.requests[1].argv[1], "save-workspace");
                const payload = JSON.parse(backend.requests[1].input);
                const source = checks.service.files.source("client", "orders.csv");
                compare(payload.entries[source].text, "orders");
                const saved = Object.assign({}, checks.snapshot(), {revision: 4, definition: payload.definition,
                    assets: Object.keys(payload.entries).map(path => ({path: path, kind: payload.entries[path].directory ? "directory" : "file"}))});
                backend.reply(1, saved);
                verify(!checks.service.dirty);
                compare(checks.service.draft.revision, 4);
            }
            function test_seed_folder_copies_contents_to_chosen_subfolder() {
                checks.service.section = 3;
                settle();
                control("seedFileTree").importRequested("client", "baitap", true);
                const picker = control("seedFolderPicker");
                tryCompare(picker, "opened", true);
                picker.selectedFolder = "file:///tmp/folder%20from%20host";
                picker.accept();
                compare(backend.requests[0].argv, ["draft", "read-local", "/tmp/folder from host", "--folder"]);
                backend.reply(0, {resources: [{path: "", kind: "directory", content: {directory: true}}, {path: "empty", kind: "directory", content: {directory: true}}]});
                verify(checks.service.files.rows("client").some(row => row.path === "baitap/empty"));
                verify(checks.service.dirty);
            }
            function test_seed_replace_cancel_then_confirm() {
                checks.service.adopt(seedSnapshot(), false);
                let picker = openSeedPicker(false);
                picker.selectedFile = "file:///tmp/orders.csv";
                picker.accept();
                const confirmation = control("replaceSeedFilesDialog");
                tryCompare(confirmation, "opened", true);
                compare(backend.requests.length, 0);
                confirmation.reject();
                verify(!checks.service.dirty);
                picker = openSeedPicker(false);
                picker.selectedFile = "file:///tmp/orders.csv";
                picker.accept();
                confirmation.accept();
                compare(backend.requests[0].argv[1], "read-local");
            }
            function test_seed_cancel_and_stale_draft() {
                const original = checks.service.definition;
                let picker = openSeedPicker(true);
                picker.reject();
                compare(checks.service.definition, original);
                compare(backend.requests.length, 0);
                picker = openSeedPicker(false);
                checks.service.draft = Object.assign({}, checks.service.draft, {id: "other-fixture"});
                picker.selectedFile = "file:///tmp/orders.csv";
                picker.accept();
                verify(checks.service.localError.includes("Bản nháp đã thay đổi"));
                compare(backend.requests.length, 0);
                compare(checks.service.definition, original);
            }
            function test_seed_existing_mapping_survives_simplification() {
                checks.service.adopt(seedSnapshot(), false);
                const original = checks.service.definition;
                checks.service.section = 3;
                settle();
                verify(checks.service.files.rows("client").some(row => row.path === "orders.csv"));
                verify(checks.service.files.rows("client").some(row => row.path === "data/readme.txt"));
                verify(!checks.service.dirty);
                control("seedFileTree").deleteRequested("client", "orders.csv");
                tryCompare(control("deleteSeedFileDialog"), "opened", true);
                control("deleteSeedFileDialog").reject();
                compare(backend.requests.length, 0);
                compare(checks.service.definition, original);
            }
            function test_shared_file_removal_data() {
                return [
                    {tag: "documentation-single", folder: false, shared: "documentation"},
                    {tag: "documentation-folder", folder: true, shared: "documentation"},
                    {tag: "other-node-single", folder: false, shared: "node"},
                    {tag: "other-node-folder", folder: true, shared: "node"},
                    {tag: "same-node-alias", folder: false, shared: "alias"}
                ];
            }
            function test_shared_file_removal(data) {
                const snapshot = checks.snapshot();
                const document = JSON.parse(snapshot.definition);
                if (data.shared === "documentation") document.documentation = "assets/docs/HUONG-DAN.md";
                document.nodes[0].files = data.folder ? [{source: "assets/docs", target: "."}] : [
                    {source: "assets/docs/HUONG-DAN.md", target: "HUONG-DAN.md"},
                    {source: "assets/docs/start-server.sh", target: "start-server.sh"}
                ];
                if (data.shared === "node") document.nodes.push({id: "other", networks: [], files: [{source: "assets/docs", target: "shared"}]});
                if (data.shared === "alias") document.nodes[0].files.push({source: "assets/docs/HUONG-DAN.md", target: "another.md"});
                snapshot.definition = JSON.stringify(document);
                snapshot.assets = [
                    {path: "assets/docs/HUONG-DAN.md", kind: "file", size: 20},
                    {path: "assets/docs/start-server.sh", kind: "file", size: 18}
                ];
                checks.service.adopt(snapshot, false);
                checks.service.section = 3;
                settle();
                control("seedFileTree").deleteRequested("client", "HUONG-DAN.md");
                tryCompare(control("deleteSeedFileDialog"), "opened", true);
                control("deleteSeedFileDialog").accept();
                const saved = checks.service.document;
                compare(saved.documentation, document.documentation);
                const paths = checks.service.files.rows("client").map(entry => entry.path);
                verify(!paths.includes("HUONG-DAN.md"));
                verify(paths.includes("start-server.sh"));
                if (data.shared === "alias") verify(paths.includes("another.md"));
                if (data.shared === "node") compare(saved.nodes[1], document.nodes[1]);
                compare(checks.service.draft.assets, snapshot.assets);
                verify(checks.service.localError === "");
                verify(checks.service.dirty);
                checks.service.save();
                compare(backend.requests[0].argv[1], "save-workspace");
                verify(backend.requests.every(entry => entry.argv[1] !== "remove-asset"));
            }
            function test_shared_nested_folder_removal_keeps_siblings_and_empty_folders() {
                const snapshot = seedSnapshot();
                const document = JSON.parse(snapshot.definition);
                document.documentation = "assets/client/data/readme.txt";
                document.nodes[0].files[0].target = "exercise";
                snapshot.assets.push({path: "assets/client/data/keep.txt", kind: "file", size: 12});
                snapshot.assets.push({path: "assets/client/empty", kind: "directory", size: 0});
                for (let index = 0; index < 25; index++)
                    snapshot.assets.push({path: "assets/client/other/file" + index, kind: "file", size: 12});
                const original = JSON.stringify(document);
                const plan = Model.removeSeedFile(document, "client", "exercise/data/readme.txt", snapshot.assets);
                compare(JSON.stringify(document), original);
                compare(plan.source, "");
                compare(plan.document.documentation, document.documentation);
                const expected = Model.previewFiles(document.nodes[0], snapshot.assets).filter(entry => entry.path !== "exercise/data/readme.txt").map(entry => entry.path).sort();
                compare(Model.previewFiles(plan.document.nodes[0], snapshot.assets).map(entry => entry.path).sort(), expected);
                verify(plan.document.nodes[0].files.length <= 16);
            }
            function test_shared_removal_over_limit_changes_nothing() {
                const snapshot = seedSnapshot();
                const document = JSON.parse(snapshot.definition);
                document.documentation = "assets/client/orders.csv";
                for (let index = 0; index < 17; index++)
                    snapshot.assets.push({path: "assets/client/file" + index, kind: "file", size: 12});
                const original = JSON.stringify(document);
                let problem = "";
                try { Model.removeSeedFile(document, "client", "orders.csv", snapshot.assets); }
                catch (error) { problem = String(error); }
                verify(problem.includes("Chưa thay đổi file nào"));
                compare(JSON.stringify(document), original);
            }
            function test_seed_delete_stale_confirmation_does_not_modify_new_definition() {
                checks.service.adopt(seedSnapshot(), false);
                checks.service.section = 3;
                settle();
                control("seedFileTree").deleteRequested("client", "orders.csv");
                tryCompare(control("deleteSeedFileDialog"), "opened", true);
                checks.service.change("metadata", 0, "name", "Changed after confirmation");
                const original = checks.service.definition;
                control("deleteSeedFileDialog").accept();
                compare(checks.service.definition, original);
                compare(backend.requests.length, 0);
                verify(checks.service.localError.includes("Bản nháp đã thay đổi"));
            }
            function test_unshared_seed_removal_still_removes_only_selected_asset() {
                const snapshot = seedSnapshot();
                checks.service.adopt(snapshot, false);
                checks.service.removeHomeFile("client", "orders.csv");
                compare(backend.requests[0].argv, ["draft", "remove-asset", "fixture-editor", "assets/client/orders.csv", "--revision", "3"]);
                compare(checks.service.document.nodes[0].files, [{source: "assets/client", target: "."}]);
            }
            function test_network_advanced_preserves_gateway() {
                const document = JSON.parse(checks.service.definition);
                document.networks[0].gateway = "10.90.0.1";
                checks.service.commit(document);
                const original = checks.service.definition;
                checks.service.section = 2;
                settle();
                verify(!control("draftNetworkGateway").visible);
                control("networkAdvancedToggle").clicked();
                settle();
                verify(control("draftNetworkGateway").visible);
                compare(control("draftNetworkGateway").text, "10.90.0.1");
                control("networkAdvancedToggle").clicked();
                compare(checks.service.definition, original);
            }
            function test_network_internet_toggle_and_legacy_defaults() {
                checks.service.section = 2;
                settle();
                const toggle = control("draftNetworkInternet");
                verify(toggle.visible);
                compare(toggle.checked, false);
                const document = JSON.parse(checks.service.definition);
                document.nodes[0].image = "cyberlab/ubuntu:24.04-1";
                checks.service.commit(document);
                settle();
                compare(toggle.checked, true);
                mouseClick(toggle);
                compare(checks.service.document.networks[0].internet, false);
                checks.service.change("networks", 0, "id", "renamed");
                compare(checks.service.document.networks[0].internet, false);
                compare(checks.service.document.nodes[0].networks, ["renamed"]);
                toggle.forceActiveFocus();
                keyClick(Qt.Key_Space);
                compare(checks.service.document.networks[0].internet, true);
                checks.service.change("networks", 0, "subnet", "");
                compare(checks.service.document.networks[0].internet, true);
                backend.busy = true;
                verify(!toggle.enabled);
            }
            function test_network_internet_hidden_on_older_daemon() {
                checks.service.policy = Object.assign({}, checks.service.policy, {network_internet: false});
                checks.service.change("networks", 0, "internet", false);
                const original = checks.service.definition;
                checks.service.section = 2;
                settle();
                verify(!control("draftNetworkInternet").visible);
                compare(checks.service.definition, original);
            }
            function test_network_internet_new_network_and_secondary_defaults() {
                const document = JSON.parse(checks.service.definition);
                document.nodes[0].image = "cyberlab/ubuntu:24.04-1";
                document.nodes[0].networks = ["lan", "backend"];
                document.networks.push({id: "backend"});
                verify(Model.networkInternet(document, document.networks[0]));
                verify(!Model.networkInternet(document, document.networks[1]));
                checks.service.section = 2;
                settle();
                mouseClick(control("addDraftNetwork"));
                compare(checks.service.document.networks[1].internet, true);
                verify(control("draftNetworkInternet").checked);
            }
            function test_sidebar_keyboard_and_metadata() {
                const title = control("draftMetadataName");
                verify(title !== null);
                title.forceActiveFocus();
                title.text = "Mạng nội bộ mới";
                keyClick(Qt.Key_Tab);
                compare(checks.service.document.metadata.name, "Mạng nội bộ mới");
                verify(checks.service.dirty);
                mouseClick(destination(1));
                compare(checks.service.section, 1);
                destination(1).forceActiveFocus();
                keyClick(Qt.Key_Down);
                compare(checks.service.section, 2);
                verify(destination(2).activeFocus);
                keyClick(Qt.Key_End);
                compare(checks.service.section, 6);
                keyClick(Qt.Key_Home);
                compare(checks.service.section, 0);
                compare(title.text, "Mạng nội bộ mới");
                compare(backend.requests.length, 0);
            }
            function test_machine_summary_and_draft_action_are_clear() {
                compare(control("saveDraftButton").text, "Lưu nháp");
                compare(control("publishDraftButton").text, "Lưu vào thư viện");
                checks.service.section = 1;
                settle();
                const card = control("draftNodeCard-0");
                compare(card.subtitle, "Linux thực hành · 1 terminal");
                compare(card.detail, "");
                verify(card.height <= 88, "Machine summary should leave room for editing");
                verify(card.Accessible.description.indexOf("fixture:latest") < 0);
                checks.service.policy = {allowed_images: ["fixture:latest"]};
                settle();
                verify(card.subtitle.indexOf("fixture:latest") >= 0, "Unknown environments must remain identifiable");
            }
            function test_form_actions_and_busy_guards() {
                mouseClick(control("draftOverviewLink-1"));
                settle();
                mouseClick(control("addDraftMachine"));
                compare(checks.service.document.nodes.length, 2);
                compare(checks.service.selectedNode, 1);
                verify(checks.service.dirty);
                mouseClick(control("saveDraftButton"));
                compare(backend.requests[0].argv, ["draft", "save-workspace", "fixture-editor", "-", "--revision", "3"]);
                compare(JSON.parse(JSON.parse(backend.requests[0].input).definition).nodes.length, 2);
                mouseClick(destination(2));
                settle();
                mouseClick(control("addDraftNetwork"));
                compare(checks.service.document.networks.length, 2);
                backend.busy = true;
                for (const name of ["saveDraftButton", "validateDraftButton", "publishDraftButton", "addDraftMachine", "addDraftNetwork"])
                    verify(!control(name).enabled, name);
                verify(!control("draftEditActions").exportAction.enabled);
            }
            function openActions() {
                mouseClick(control("draftActionsButton"));
                tryCompare(control("draftEditActions").menu, "opened", true);
                settle();
                return control("draftEditActions").menu;
            }
            function test_overflow_export_and_confirmation_cancel() {
                const menu = openActions();
                mouseClick(control("draftEditActions").exportAction);
                tryCompare(exportSpy, "count", 1);
                compare(exportSpy.signalArguments[0][0].id, "fixture-editor");
                checks.service.change("metadata", 0, "name", "Chưa lưu");
                openActions();
                verify(!control("draftEditActions").exportAction.enabled);
                mouseClick(findChild(menu, "reloadDraftButton"));
                tryCompare(control("draftReloadDialog"), "opened", true);
                keyClick(Qt.Key_Escape);
                tryCompare(control("draftReloadDialog"), "opened", false);
                verify(checks.service.dirty);
                compare(checks.service.document.metadata.name, "Chưa lưu");
                openActions();
                mouseClick(findChild(menu, "deleteDraftButton"));
                tryCompare(control("draftDeleteDialog"), "opened", true);
                keyClick(Qt.Key_Escape);
                compare(backend.requests.length, 0);
                backend.capabilities = ["authoring"];
                openActions();
                verify(!control("draftEditActions").exportAction.visible);
            }
            function prepareDeletedDraft() {
                checks.service.files.create("client", "practice.py", false);
                checks.service.files.edit("client", "practice.py", "print('practice')\n");
                checks.service.files.editDocumentation("# Practice\n");
                checks.service.startup.previousCommands = {client: ["sleep", "infinity"]};
                checks.service.runtimeReport = {valid: true};
                checks.service.publicationReview = {id: "fixture-editor"};
                checks.service.updateReview = {id: "fixture-editor"};
                checks.service.localError = "Previous error";
                verify(checks.service.dirty);
                backend.requests = [];
                backend.callbacks = [];
            }
            function test_delete_draft_clears_unsaved_workspace() {
                prepareDeletedDraft();
                checks.service.deleteDraft();
                compare(backend.requests[0].argv, ["draft", "delete", "fixture-editor", "--revision", "3"]);
                verify(checks.service.dirty);
                backend.reply(0, {deleted: true});
                compare(checks.service.draft, null);
                verify(!checks.service.dirty);
                compare(checks.service.files.buffers, {});
                compare(checks.service.files.pending, {});
                compare(checks.service.files.removals, []);
                compare(checks.service.files.tabs, []);
                compare(checks.service.files.activeKey, "");
                compare(checks.service.startup.previousCommands, {});
                compare(checks.service.documentationText, "");
                verify(checks.service.documentationReady);
                compare(checks.service.runtimeReport, null);
                compare(checks.service.publicationReview, null);
                compare(checks.service.updateReview, null);
                compare(checks.service.localError, "");
                checks.service.create("new-lab", "New Lab", ["linux"], "easy");
                compare(backend.requests[backend.requests.length - 1].argv, ["draft", "create", "new-lab", "--title", "New Lab", "--tag", "linux", "--difficulty", "easy"]);
            }
            function test_topics_required_for_create_and_library_save() {
                checks.service.create("new-lab", "New Lab", [], "easy");
                compare(backend.requests.length, 0);
                verify(checks.service.localError.includes("chủ đề"));
                checks.service.change("metadata", 0, "tags", []);
                checks.service.section = 5;
                checks.service.prepareLibrarySave();
                compare(backend.requests.length, 0);
                compare(checks.service.section, 0);
                verify(checks.service.localError.includes("chủ đề"));
                control("draftMetadataTopics").edited(["networking"]);
                compare(checks.service.document.metadata.tags, ["networking"]);
            }
            function test_create_from_topic_dialog_preserves_selected_tags() {
                draftEditor.contentItem.choosingDraft = true;
                control("newDraftTitle").text = "Bài mới";
                control("newDraftId").text = "new-lab";
                const picker = control("newDraftTopics");
                picker.selectedTags = [];
                picker.clicked();
                tryCompare(picker.dialog, "opened", true);
                findChild(picker.dialog.contentItem, "topic-linux").clicked();
                findChild(picker.dialog.contentItem, "topic-networking").clicked();
                compare(picker.dialog.pendingTags, ["linux", "networking"]);
                verify(findChild(picker.dialog.footer, "applyTopics").enabled);
                findChild(picker.dialog.footer, "applyTopics").clicked();
                tryCompare(picker.dialog, "visible", false);
                compare(picker.selectedTags, ["linux", "networking"]);
                control("newDraftDifficulty").currentIndex = 1;
                verify(control("createDraftButton").enabled);
                control("createDraftButton").clicked();
                compare(checks.service.localError, "");
                compare(backend.requests.length, 1);
                compare(backend.requests[0].argv, ["draft", "create", "new-lab", "--title", "Bài mới", "--tag", "linux", "--tag", "networking", "--difficulty", "easy"]);
                const created = checks.snapshot();
                created.id = "new-draft";
                backend.reply(0, created);
                compare(checks.service.draft.id, "new-draft");
                verify(!draftEditor.contentItem.showLanding);
            }
            function test_create_rejects_invalid_topic_values() {
                for (const tags of [undefined, null, "linux", {}, [], [null], [""], ["   "]]) {
                    checks.service.create("new-lab", "Bài mới", tags, "easy");
                    compare(backend.requests.length, 0);
                    verify(checks.service.localError.includes("chủ đề"));
                }
                checks.service.create("new-lab", "Bài mới", ["linux"], "easy");
                compare(checks.service.localError, "");
                compare(backend.requests.length, 1);
            }
            function test_local_error_only_opens_popup_without_moving_landing() {
                draftEditor.contentItem.choosingDraft = true;
                settle();
                const landing = control("draftLanding");
                const position = landing.y;
                const height = landing.height;
                errorEvents.clear();
                checks.service.create("new-lab", "Bài mới", [], "easy");
                tryCompare(errorEvents, "count", 1);
                settle();
                compare(landing.y, position);
                compare(landing.height, height);
            }
            function test_failed_delete_preserves_unsaved_workspace() {
                prepareDeletedDraft();
                const buffers = JSON.stringify(checks.service.files.buffers);
                const definition = checks.service.definition;
                checks.service.deleteDraft();
                backend.reply(0, null, "Delete failed");
                compare(checks.service.draft.id, "fixture-editor");
                verify(checks.service.dirty);
                compare(checks.service.definition, definition);
                compare(JSON.stringify(checks.service.files.buffers), buffers);
                compare(checks.service.documentationText, "# Practice\n");
                compare(backend.requests.length, 1);
            }
            function test_validation_revision_and_compact_dialog() {
                mouseClick(control("validateDraftButton"));
                compare(checks.service.section, 5);
                compare(backend.requests[0].argv, ["draft", "check", "fixture-editor", "--revision", "3"]);
                checks.service.report = {valid: true, revision: 2, digest: "fixture-digest", issues: []};
                verify(!control("reviewPublishButton").enabled);
                checks.service.report = {valid: true, revision: 3, digest: "fixture-digest", issues: []};
                checks.service.definitionDirty = false;
                compare(control("reviewPublishButton").enabled, true);
                checks.service.change("metadata", 0, "version", "2.0");
                verify(!control("reviewPublishButton").enabled);
                window.width = 640;
                settle();
                checks.service.definitionDirty = false;
                mouseClick(control("validateDraftButton"));
                tryCompare(draftEditor.contentItem.reviewDialog, "opened", true);
                const dialog = draftEditor.contentItem.reviewDialog;
                verify(dialog.dim && dialog.modal);
                verify(dialog.width <= window.Overlay.overlay.width && dialog.height <= window.Overlay.overlay.height);
                keyClick(Qt.Key_Escape);
                tryCompare(dialog, "opened", false);
            }
            function test_documentation_preserves_unsaved_text() {
                checks.service.section = 4;
                settle();
                const source = control("documentationSource");
                source.forceActiveFocus();
                source.text = "# Thực hành\n\nNội dung đang soạn.";
                verify(checks.service.documentationDirty);
                mouseClick(destination(1));
                mouseClick(destination(4));
                compare(source.text, "# Thực hành\n\nNội dung đang soạn.");
                compare(checks.service.documentationText, source.text);
                compare(backend.requests.length, 0);
            }
            function test_documentation_readable_spacing_and_safe_markup() {
                checks.service.section = 4;
                checks.service.documentationText = "# Overview\n\nFirst paragraph.\n\nSecond paragraph.\n\n## Network\n\n- First item\n- Second item\n\n```sh\necho ready\npwd\n```\n\n| Machine | Address |\n| --- | --- |\n| client | 10.1.0.2 |\n\n<img src=\"file:///missing.png\">\n\n![image](https://invalid.example/image.png)\n";
                control("documentationSource").text = checks.service.documentationText;
                settle();
                const text = findChild(control("documentationPreview"), "documentText");
                compare(text.textFormat, TextEdit.RichText);
                verify(!text.text.includes("<img"), "Markdown must not load embedded images or HTML resources");
                const plain = text.getText(0, text.length);
                verify(plain.includes("First paragraph.") && plain.includes("client") && plain.includes("echo ready"));
                verify(text.positionToRectangle(plain.indexOf("pwd")).y > text.positionToRectangle(plain.indexOf("echo ready")).y,
                       "Code-block line breaks must remain intact");
                const first = text.positionToRectangle(plain.indexOf("First paragraph."));
                const second = text.positionToRectangle(plain.indexOf("Second paragraph."));
                verify(second.y - first.y >= 32, "Paragraphs need breathing room beyond a single line");
                if (checks.screenshotFolder) grabImage(window.contentItem).save(checks.screenshotFolder + "/documentation-readable.png");
            }
            function test_documentation_linked_scroll() {
                checks.service.section = 4;
                checks.service.documentationText = Array.from({length: 40}, (_, index) =>
                    "## Section " + index + "\n\nParagraph for section " + index + ".\n\n```sh\necho " + index + "\n```\n").join("\n");
                control("documentationSource").text = checks.service.documentationText;
                checks.service.documentationDirty = false;
                settle();
                const source = control("documentationSourceScroll").contentItem;
                const preview = control("documentationPreview").contentItem;
                verify(source.contentHeight > source.height);
                verify(preview.contentHeight > preview.height);
                source.contentY = (source.contentHeight - source.height) * 0.55;
                settle();
                verify(Math.abs(preview.contentY / (preview.contentHeight - preview.height) - 0.55) < 0.02,
                       "Source scrolling must move the preview");
                preview.contentY = preview.contentHeight - preview.height;
                settle();
                verify(Math.abs(source.contentY / (source.contentHeight - source.height) - 1) < 0.02,
                       "Preview scrolling must move the source without a feedback loop");
                compare(checks.service.documentationDirty, false);
            }
            function test_compact_rail_and_no_draft() {
                window.width = 380;
                settle();
                const rail = control("draftSectionNavigation");
                verify(rail.visible && rail.compact);
                compare(rail.width, 72);
                compare(control("draftSectionSelector"), null);
                for (let index = 0; index < 7; index++) {
                    const tab = destination(index);
                    verify(tab.visible && tab.iconOnly);
                    verify(tab.width >= 48 && tab.height >= 48);
                    verify(tab.Accessible.name.length > 0);
                    contained(tab, rail);
                }
                destination(0).forceActiveFocus();
                keyClick(Qt.Key_Down);
                compare(checks.service.section, 1);
                verify(destination(1).activeFocus);
                mouseClick(destination(4));
                compare(checks.service.section, 4);
                verify(destination(4).selected);
                checks.service.draft = null;
                checks.service.definition = "";
                settle();
                verify(control("draftLandingPage").visible);
                verify(!control("draftEditActions").visible);
                verify(!rail.visible);
            }
            function test_rail_resize_preserves_section_and_work() {
                checks.service.section = 4;
                checks.service.documentationText = "# Chưa lưu";
                checks.service.documentationDirty = true;
                for (const width of [940, 1280, 600, 1440]) {
                    window.width = width;
                    settle();
                    const rail = control("draftSectionNavigation");
                    compare(rail.compact, draftEditor.width < Studio.Theme.editorRailBreakpoint);
                    compare(destination(4).iconOnly, rail.compact);
                    verify(destination(4).selected);
                    compare(checks.service.section, 4);
                    compare(checks.service.documentationText, "# Chưa lưu");
                    verify(checks.service.documentationDirty);
                }
                compare(backend.requests.length, 0);
            }
            function test_short_rail_keyboard_scroll() {
                window.width = 640;
                window.height = 600;
                Studio.Theme.setZoomPercent(150);
                settle();
                const rail = control("draftSectionNavigation");
                destination(0).forceActiveFocus();
                keyClick(Qt.Key_End);
                settle();
                compare(checks.service.section, 6);
                verify(destination(6).activeFocus);
                const last = destination(6).mapToItem(rail.contentItem, 0, 0, destination(6).width, destination(6).height);
                verify(last.y >= 0 && last.y + last.height <= rail.contentItem.height + 1);
                keyClick(Qt.Key_Home);
                settle();
                compare(checks.service.section, 0);
                const first = destination(0).mapToItem(rail.contentItem, 0, 0, destination(0).width, destination(0).height);
                verify(first.y >= 0 && first.y + first.height <= rail.contentItem.height + 1);
            }
            function test_sections_data() {
                const cases = [];
                for (const size of [{name: "desktop", width: 1440, zoom: 100}, {name: "compact", width: 380, zoom: 100}, {name: "zoom150", width: 1280, zoom: 150}]) {
                    for (let section = 0; section < 7; section++)
                        cases.push({tag: size.name + "-" + section, width: size.width, zoom: size.zoom, section: section});
                }
                cases.push({tag: "wide-light", width: 2000, zoom: 100, section: 0, light: true});
                for (let section = 0; section < 7; section++)
                    cases.push({tag: "expanded-" + section, width: 2000, height: 1200, zoom: 100, section: section, files: section === 3});
                cases.push({tag: "empty-machines", width: 1280, zoom: 100, section: 1, empty: true});
                cases.push({tag: "empty-networks", width: 1280, zoom: 100, section: 2, empty: true});
                cases.push({tag: "files-prepared", width: 1280, zoom: 100, section: 3, files: true});
                cases.push({tag: "files-prepared-compact", width: 380, zoom: 100, section: 3, files: true});
                cases.push({tag: "files-prepared-light", width: 1280, zoom: 100, section: 3, files: true, light: true});
                cases.push({tag: "software", width: 1280, zoom: 100, section: 1, software: true});
                cases.push({tag: "software-compact", width: 380, zoom: 100, section: 1, software: true});
                for (let category = 0; category < 3; category++)
                    cases.push({tag: "labedit-" + category, width: 1280, zoom: 100, section: 6, category: category});
                for (let advanced = 0; advanced < 3; advanced++)
                    cases.push({tag: "labedit-advanced-" + advanced, width: 1280, zoom: 100, section: 6, advanced: advanced});
                return cases;
            }
            function test_sections(data) {
                window.width = data.width;
                window.height = data.height || 820;
                Studio.Theme.setZoomPercent(data.zoom);
                Studio.Theme.themeMode = data.light ? "light" : "dark";
                if (data.files) {
                    checks.service.adopt(seedSnapshot(), false);
                }
                if (data.empty) {
                    const document = checks.service.document;
                    document.nodes = [];
                    document.networks = [];
                    checks.service.commit(document);
                }
                checks.service.section = data.section;
                if (data.software) {
                    checks.service.policy = Object.assign({}, checks.service.policy, {software_preparation: true, software_catalog: {
                        packages: [{id: "openssh-client", name: "SSH client", description: "Kết nối SSH"},
                                   {id: "python3", name: "Python", description: "Chạy chương trình Python"},
                                   {id: "nano", name: "Nano", description: "Soạn thảo trong terminal"}],
                        applications: [{id: "firefox", name: "Firefox"}, {id: "wireshark", name: "Wireshark"}]
                    }});
                    const document = JSON.parse(checks.service.definition);
                    document.nodes[0].image = "cyberlab/ubuntu:24.04-1";
                    checks.service.commit(document);
                    control("machineEditorTabs").selected(1);
                }
                checks.service.documentationText = "# Mạng cơ bản\n\n## Mục tiêu\n- Quan sát kết nối giữa các máy.\n- Ghi lại kết quả thực hành.\n\n```sh\nip address\n```";
                control("documentationSource").text = checks.service.documentationText;
                if (data.category !== undefined) {
                    const selector = control("labeditCategory");
                    selector.selected(data.category);
                }
                if (data.advanced !== undefined) {
                    control("labeditAdvanced").expanded = true;
                    control("labeditAdvancedCategory").currentIndex = data.advanced;
                }
                settle();
                const content = control("draftSectionContent");
                compare(content.width, Math.max(0, control("draftSectionSurface").width - Studio.Theme.space16));
                contained(content, control("draftSectionSurface"));
                for (const name of ["saveDraftButton", "validateDraftButton", "publishDraftButton", "draftActionsButton"])
                    contained(control(name), draftEditor);
                if (data.section === 0) {
                    contained(control("draftMetadataCard"), content);
                    contained(control("draftContentsCard"), content);
                    contained(control("draftMetadataName"), control("draftMetadataCard"));
                }
                if (data.section === 4) {
                    verify(control("documentationSourcePane").visible);
                    contained(control("documentationSplit"), content);
                }
                if (data.section === 3) {
                    for (const name of ["seedFileTree", "fileTreeAdd"])
                        contained(control(name), content);
                }
                if (checks.screenshotFolder)
                    grabImage(window.contentItem).save(checks.screenshotFolder + "/editor-" + data.tag + ".png");
                compare(backend.requests.length, 0);
            }
            function test_file_workspace_follows_viewport_height() {
                window.width = 2000;
                checks.service.section = 3;
                checks.service.files.create("client", "hello.py", false);
                checks.service.files.edit("client", "hello.py", "def greet(name):\n    print(f'Hello, {name}')\n\ngreet('CyberLab')\n");
                for (const height of [1200, 900, 1400, 650]) {
                    window.height = height;
                    settle();
                    const scroll = control("draftSectionScroll");
                    const resources = control("draftResources");
                    compare(resources.height, Math.max(resources.implicitHeight, scroll.availableHeight - Studio.Theme.space24));
                    contained(resources, control("draftSectionContent"));
                    const text = control("fileText-client:hello.py");
                    verify(text.visible);
                    verify(text.width > 1000);
                    if (height === 1200 && checks.screenshotFolder)
                        grabImage(window.contentItem).save(checks.screenshotFolder + "/editor-expanded-python.png");
                }
            }
        }
    }
}
