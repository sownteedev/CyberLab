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
        property bool busy: false
        property string error: ""
        signal notificationRequested(string message, bool failure)
        property var capabilities: ["authoring", "machine-setup-v1"]
        property var requests: []
        property var callbacks: []
        function request(argv, callback, input) {
            requests = requests.concat([{argv: argv, input: input || ""}]);
            callbacks = callbacks.concat([callback]);
        }
    }
    Studio.DraftService { id: service; backend: backend }
    ApplicationWindow {
        id: window
        visible: true
        color: Studio.Theme.surface
        width: 640
        height: 900
        palette: Studio.Theme.controlPalette
        ScrollView {
            id: scroll
            anchors.fill: parent
            anchors.margins: 16
            contentWidth: availableWidth
            Editor.NodeAccountEditor { id: panel; width: window.width - 32; editor: service; nodeIndex: service.selectedNode }
        }
        Studio.StudioNotifications {
            id: notices
            api: backend
            anchors.right: parent.right
            anchors.bottom: parent.bottom
            width: Math.min(440, window.width - 32)
            availableHeight: window.height
        }
        TestCase {
            name: "AccountEditor"
            when: window.visible
            function init() {
                const manager = findChild(panel, "accountManagerDialog");
                if (manager) {
                    manager.close();
                    tryCompare(manager, "visible", false);
                }
                Studio.Theme.reducedMotion = true;
                window.width = 640;
                window.height = 900;
                scroll.contentItem.contentY = 0;
                backend.requests = [];
                backend.callbacks = [];
                backend.busy = false;
                service.accountPasswordPending = false;
                const main = {name: "student", uid: 2000, gid: 2000, home: "/home/student", shell: "/bin/bash"};
                const node = {id: "desktop", image: "cyberlab/ubuntu:24.04-1", user: main};
                service.policy = {machine_setup: true, machine_setup_version: 1, allowed_images: [node.image], image_profiles: [
                    {image: node.image, workstation: true, custom_username: true, machine_setup: true, accounts: [main]}]};
                service.draft = {id: "fixture", revision: 2, digest: "fixture", assets: []};
                service.definition = JSON.stringify({metadata: {}, nodes: [node, Object.assign({}, node, {id: "second"})], networks: []});
                service.definitionDirty = false;
                service.documentationDirty = false;
                service.files.reset();
                service.selectedNode = 0;
                service.localError = "";
                notices.errorToast.dismiss(false);
                wait(0);
            }
            function result() {
                return {id: "fixture", revision: 3, digest: "new", assets: [], definition: service.definition};
            }
            function control(name) {
                const manager = findChild(panel, "accountManagerDialog");
                const item = (manager && manager.opened ? findChild(manager.contentItem, name) : null) || findChild(panel, name);
                verify(item !== null, name);
                wait(30);
                const viewport = manager && manager.opened ? findChild(manager, "accountsScroll") : scroll;
                const position = item.mapToItem(viewport.contentItem, 0, 0);
                viewport.contentItem.contentY = Math.max(0, Math.min(viewport.contentItem.contentHeight - viewport.height,
                    viewport.contentItem.contentY + position.y - viewport.height / 3));
                wait(10);
                return item;
            }
            function typeName(name, text) {
                const input = control(name);
                mouseClick(input);
                keyClick(Qt.Key_A, Qt.ControlModifier);
                for (let index = 0; index < text.length; index++) keyClick(text[index].toUpperCase().charCodeAt(0));
                compare(input.text, text);
                return input;
            }
            function test_collapsed_defaults_and_add_user() {
                const toggle = findChild(panel, "extraAccountsToggle");
                verify(toggle);
                const manager = findChild(panel, "accountManagerDialog");
                verify(manager !== null);
                verify(!manager.visible);
                verify(!toggle.checkable);
                mouseClick(toggle);
                tryCompare(manager, "opened", true);
                const input = findChild(panel, "newAccountName");
                input.text = "alice";
                findChild(panel, "addAccount").click();
                compare(service.document.nodes[0].setup.users[0].password_hash, "!");
                compare(service.document.nodes[0].setup.users[0].sudo, "disabled");
                compare(service.document.nodes[0].setup.users[0].uid, 3000);
                verify(service.dirty);
            }
            function chooseSection(manager, index) {
                wait(20);
                const button = findChild(manager.contentItem, "accountsTab-" + index);
                verify(button !== null);
                mouseClick(button);
                tryCompare(manager, "section", index);
                wait(20);
            }
            function openManager(tab) {
                mouseClick(control("extraAccountsToggle"));
                const manager = findChild(panel, "accountManagerDialog");
                tryCompare(manager, "opened", true);
                chooseSection(manager, tab || 0);
                return manager;
            }
            function test_manager_closes_on_context_change() {
                const manager = openManager();
                findChild(manager, "newAccountName").text = "unfinished";
                service.selectedNode = 1;
                tryCompare(manager, "visible", false);
                compare(findChild(manager, "newAccountName").text, "");
            }
            function test_enter_adds_and_escape_preserves_accounts() {
                const manager = openManager();
                typeName("newAccountName", "alice");
                keyClick(Qt.Key_Return);
                compare(service.document.nodes[0].setup.users[0].name, "alice");
                keyClick(Qt.Key_Escape);
                tryCompare(manager, "visible", false);
                compare(service.document.nodes[0].setup.users[0].name, "alice");
            }
            function test_invalid_and_duplicate_names_keep_input() {
                const manager = openManager();
                typeName("newAccountName", "root");
                mouseClick(control("addAccount"));
                verify(service.localError.length > 0);
                compare(control("newAccountName").text, "root");
                compare((service.document.nodes[0].setup || {}).users, undefined);
                notices.errorToast.dismiss(false);
                typeName("newAccountName", "alice");
                mouseClick(control("addAccount"));
                typeName("newAccountName", "alice");
                mouseClick(control("addAccount"));
                compare(service.document.nodes[0].setup.users.length, 1);
                compare(control("newAccountName").text, "alice");
            }
            function test_cancel_removal_and_nested_password() {
                service.accountChange(0, "addUser", "alice");
                service.definitionDirty = false;
                const manager = openManager();
                mouseClick(control("expandAccount-alice"));
                const passwordButton = control("openPassword-alice");
                mouseClick(passwordButton);
                let credentials = passwordButton.parent;
                while (credentials && credentials.passwordState === undefined) credentials = credentials.parent;
                verify(credentials !== null);
                const passwordPopup = findChild(credentials, "passwordDialog-alice");
                verify(passwordPopup !== null);
                tryCompare(passwordPopup, "opened", true);
                keyClick(Qt.Key_A);
                keyClick(Qt.Key_Escape);
                tryCompare(passwordPopup, "visible", false);
                verify(manager.opened);
                mouseClick(control("removeAccount-alice"));
                const confirmation = findChild(manager, "removeAccountDialog");
                tryCompare(confirmation, "opened", true);
                mouseClick(confirmation.cancelButton);
                compare(service.document.nodes[0].setup.users.length, 1);
                compare(backend.requests.length, 0);
            }
            function test_long_list_keeps_actions_visible_and_limits_count() {
                for (let index = 0; index < 32; index++) service.accountChange(0, "addUser", "learner" + index);
                const manager = openManager();
                findChild(manager.contentItem, "newAccountName").text = "extra";
                verify(!findChild(manager.contentItem, "addAccount").enabled);
                mouseClick(control("expandAccount-learner31"));
                verify(control("accountName-learner31").visible);
                verify(manager.height < window.height);
                chooseSection(manager, 1);
                compare(findChild(manager, "accountsScroll").contentItem.contentY, 0);
            }
            function test_small_window_and_group_empty_state() {
                window.width = 360;
                window.height = 520;
                const manager = openManager(1);
                verify(manager.width <= window.width - 16);
                verify(manager.height <= window.height - 16);
                const field = control("newAccountGroup");
                verify(field.visible);
                const position = field.mapToItem(window.contentItem, 0, 0);
                verify(position.x >= 0 && position.x + field.width <= window.width);
                verify(position.y >= 0 && position.y + field.height <= window.height);
                if (checks.screenshotFolder) grabImage(window.contentItem).save(checks.screenshotFolder + "/accounts-small-window.png");
            }
            function test_password_is_masked_blank_and_cleared_on_node_change() {
                openManager();
                mouseClick(control("mainOpenPassword"));
                const popup = findChild(panel, "mainPasswordDialog");
                tryCompare(popup, "opened", true);
                const input = findChild(panel, "mainAccountPassword");
                verify(input);
                compare(input.echoMode, TextInput.Password);
                compare(input.text, "");
                tryCompare(input, "activeFocus", true);
                input.text = "private-fixture";
                service.selectedNode = 1;
                wait(0);
                compare(input.text, "");
                tryCompare(popup, "visible", false);
            }
            function test_unsaved_definition_and_files_block_password() {
                service.definitionDirty = true;
                service.setAccountPassword(0, "student", "lock", "");
                compare(backend.requests.length, 0);
                verify(service.localError.length > 0);
                service.definitionDirty = false;
                service.files.pending = {"assets/unsaved": {text: "local"}};
                service.setAccountPassword(0, "student", "lock", "");
                compare(backend.requests.length, 0);
            }
            function test_secret_stdin_only_and_success_revision() {
                service.setAccountPassword(0, "student", "replace", "private-fixture");
                compare(backend.requests.length, 1);
                verify(JSON.stringify(backend.requests[0].argv).indexOf("private-fixture") < 0);
                compare(JSON.parse(backend.requests[0].input).password, "private-fixture");
                backend.callbacks[0](result(), "");
                compare(service.draft.revision, 3);
                verify(!service.accountPasswordPending);
            }
            function test_async_node_switch_even_back_rejects_late_adoption() {
                service.setAccountPassword(0, "student", "lock", "");
                service.selectedNode = 1;
                service.selectedNode = 0;
                backend.callbacks[0](result(), "");
                compare(service.draft.revision, 2);
                verify(service.localError.length > 0);
            }
            function test_async_edits_and_revision_are_preserved() {
                service.setAccountPassword(0, "student", "lock", "");
                service.definitionDirty = true;
                backend.callbacks[0](result(), "");
                compare(service.draft.revision, 2);
                verify(service.definitionDirty);
            }
            function test_async_revision_and_other_draft_are_preserved() {
                service.setAccountPassword(0, "student", "lock", "");
                service.draft = Object.assign({}, service.draft, {revision: 9});
                backend.callbacks[0](result(), "");
                compare(service.draft.revision, 9);
                service.setAccountPassword(0, "student", "lock", "");
                service.draft = Object.assign({}, service.draft, {id: "other"});
                backend.callbacks[1](result(), "");
                compare(service.draft.id, "other");
            }
            function test_password_error_does_not_surface_transport_text() {
                service.setAccountPassword(0, "student", "replace", "private-fixture");
                backend.callbacks[0](null, "unexpected private-fixture error");
                verify(service.localError.indexOf("private-fixture") < 0);
                verify(!service.accountPasswordPending);
            }
            function test_capability_gates_controls() {
                service.policy = Object.assign({}, service.policy, {machine_setup: false});
                wait(0);
                verify(!findChild(panel, "extraAccountsToggle").visible);
                service.setAccountPassword(0, "student", "lock", "");
                compare(backend.requests.length, 0);
            }
            function test_user_like_add_rename_membership_delete() {
                const manager = openManager(1);
                typeName("newAccountGroup", "team");
                mouseClick(control("addAccountGroup"));
                compare(service.document.nodes[0].setup.groups[0].name, "team");
                chooseSection(manager, 0);
                typeName("newAccountName", "alice");
                mouseClick(control("addAccount"));
                compare(service.document.nodes[0].setup.users[0].name, "alice");
                typeName("accountName-alice", "ally");
                keyClick(Qt.Key_Return);
                compare(service.document.nodes[0].setup.users[0].name, "ally");
                compare(service.document.nodes[0].setup.users[0].uid, 3001);
                chooseSection(manager, 1);
                typeName("accountGroupName-team", "staff");
                keyClick(Qt.Key_Return);
                compare(service.document.nodes[0].setup.groups[0].name, "staff");
                chooseSection(manager, 0);
                mouseClick(control("accountMembership-ally-staff"));
                compare(service.document.nodes[0].setup.users[0].groups[0], "staff");
                chooseSection(manager, 1);
                mouseClick(control("removeAccountGroup-staff"));
                const confirmation = findChild(manager, "removeAccountDialog");
                tryCompare(confirmation, "opened", true);
                mouseClick(confirmation.actionButton);
                compare(service.document.nodes[0].setup.groups.length, 1);
                verify(service.localError.length > 0);
                notices.errorToast.dismiss(false);
                chooseSection(manager, 0);
                mouseClick(control("accountMembership-ally-staff"));
                chooseSection(manager, 1);
                mouseClick(control("removeAccountGroup-staff"));
                tryCompare(confirmation, "opened", true);
                mouseClick(confirmation.actionButton);
                compare(service.document.nodes[0].setup.groups.length, 0);
                chooseSection(manager, 0);
                mouseClick(control("removeAccount-ally"));
                tryCompare(confirmation, "opened", true);
                mouseClick(confirmation.actionButton);
                compare(service.document.nodes[0].setup.users.length, 0);
                compare(service.document.nodes[0].user.name, "student");
            }
            function test_password_popup_submit_and_cancel() {
                const manager = openManager();
                mouseClick(control("mainOpenPassword"));
                const popup = findChild(panel, "mainPasswordDialog");
                tryCompare(popup, "opened", true);
                keyClick(Qt.Key_A);
                compare(findChild(panel, "mainAccountPassword").text, "a");
                mouseClick(findChild(popup, "confirmAccountPassword"));
                compare(JSON.parse(backend.requests[0].input).password, "a");
                compare(findChild(panel, "mainAccountPassword").text, "");
                backend.callbacks[0](result(), "");
                mouseClick(control("mainOpenPassword"));
                tryCompare(popup, "opened", true);
                keyClick(Qt.Key_B);
                keyClick(Qt.Key_Escape);
                tryCompare(popup, "visible", false);
                verify(manager.opened);
                compare(findChild(panel, "mainAccountPassword").text, "");
                compare(backend.requests.length, 1);
            }
            function test_password_uses_backend_utf8_byte_limit() {
                openManager();
                mouseClick(control("mainOpenPassword"));
                const popup = findChild(panel, "mainPasswordDialog");
                tryCompare(popup, "opened", true);
                const field = findChild(panel, "mainAccountPassword");
                field.text = Array(66).join("é");
                verify(findChild(popup, "passwordByteLimitError").visible);
                verify(!findChild(popup, "confirmAccountPassword").enabled);
            }
            function test_visuals_data() {
                return [{tag: "light", mode: "light", width: 640}, {tag: "dark", mode: "dark", width: 640},
                    {tag: "narrow-light", mode: "light", width: 360}, {tag: "narrow-dark", mode: "dark", width: 360}];
            }
            function test_visuals(data) {
                Studio.Theme.themeMode = data.mode;
                window.width = data.width;
                window.height = 1200;
                service.accountChange(0, "addGroup", "research");
                service.accountChange(0, "addUser", "alice");
                service.accountChange(0, "groups", "alice", ["research"]);
                service.definitionDirty = false;
                wait(30);
                if (checks.screenshotFolder) grabImage(window.contentItem).save(checks.screenshotFolder + "/accounts-summary-" + data.tag + ".png");
                const manager = openManager();
                mouseClick(control("expandAccount-alice"));
                scroll.contentItem.contentY = 0;
                wait(70);
                if (checks.screenshotFolder) grabImage(window.contentItem).save(checks.screenshotFolder + "/accounts-" + data.tag + ".png");
                verify(panel.width <= scroll.availableWidth + 1);
                verify(manager.width <= window.width);
                verify(manager.height <= window.height);
                chooseSection(manager, 1);
                if (checks.screenshotFolder) grabImage(window.contentItem).save(checks.screenshotFolder + "/account-groups-" + data.tag + ".png");
                chooseSection(manager, 0);
                mouseClick(control("mainOpenPassword"));
                const popup = findChild(panel, "mainPasswordDialog");
                tryCompare(popup, "opened", true);
                wait(30);
                if (checks.screenshotFolder) grabImage(window.contentItem).save(checks.screenshotFolder + "/account-password-" + data.tag + ".png");
                verify(popup.width <= window.width);
                keyClick(Qt.Key_Escape);
            }
            function test_main_password_belongs_to_manager() {
                verify(findChild(panel, "mainAccountSudo").visible);
                verify(!findChild(panel, "mainOpenPassword").visible);
                const manager = openManager();
                verify(findChild(manager.contentItem, "mainOpenPassword") !== null);
                compare(findChild(manager.contentItem, "mainAccountName").text, "student");
                verify(!service.dirty);
                mouseClick(control("mainOpenPassword"));
                const popup = findChild(panel, "mainPasswordDialog");
                tryCompare(popup, "opened", true);
                findChild(panel, "mainAccountPassword").text = "private-fixture";
                manager.close();
                tryCompare(popup, "visible", false);
                compare(findChild(panel, "mainAccountPassword").text, "");
                compare(backend.requests.length, 0);
            }
            function test_main_password_cleared_on_group_tab() {
                const manager = openManager();
                mouseClick(control("mainOpenPassword"));
                const popup = findChild(panel, "mainPasswordDialog");
                tryCompare(popup, "opened", true);
                findChild(panel, "mainAccountPassword").text = "private-fixture";
                manager.section = 1;
                tryCompare(popup, "visible", false);
                compare(findChild(panel, "mainAccountPassword").text, "");
            }
            function test_main_lock_password_uses_existing_request() {
                openManager();
                mouseClick(control("mainLockPassword"));
                compare(backend.requests.length, 1);
                const request = JSON.parse(backend.requests[0].input);
                compare(request.action, "lock");
                compare(request.account, "student");
            }
        }
    }
}
