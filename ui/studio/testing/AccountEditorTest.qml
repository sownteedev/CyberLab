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
                const item = findChild(panel, name);
                verify(item !== null, name);
                const position = item.mapToItem(scroll.contentItem, 0, 0);
                scroll.contentItem.contentY = Math.max(0, Math.min(scroll.contentItem.contentHeight - scroll.height,
                    scroll.contentItem.contentY + position.y - scroll.height / 3));
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
                verify(!toggle.checked);
                if (toggle.checked) mouseClick(toggle);
                mouseClick(toggle);
                const input = findChild(panel, "newAccountName");
                input.text = "alice";
                findChild(panel, "addAccount").click();
                compare(service.document.nodes[0].setup.users[0].password_hash, "!");
                compare(service.document.nodes[0].setup.users[0].sudo, "disabled");
                compare(service.document.nodes[0].setup.users[0].uid, 3000);
                verify(service.dirty);
            }
            function test_password_is_masked_blank_and_cleared_on_node_change() {
                mouseClick(findChild(panel, "mainOpenPassword"));
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
                const toggle = control("extraAccountsToggle");
                if (!toggle.checked) mouseClick(toggle);
                typeName("newAccountGroup", "team");
                mouseClick(control("addAccountGroup"));
                compare(service.document.nodes[0].setup.groups[0].name, "team");
                typeName("newAccountName", "alice");
                mouseClick(control("addAccount"));
                compare(service.document.nodes[0].setup.users[0].name, "alice");
                typeName("accountName-alice", "ally");
                keyClick(Qt.Key_Return);
                compare(service.document.nodes[0].setup.users[0].name, "ally");
                compare(service.document.nodes[0].setup.users[0].uid, 3001);
                typeName("accountGroupName-team", "staff");
                keyClick(Qt.Key_Return);
                compare(service.document.nodes[0].setup.groups[0].name, "staff");
                mouseClick(control("accountMembership-ally-staff"));
                compare(service.document.nodes[0].setup.users[0].groups[0], "staff");
                mouseClick(control("removeAccountGroup-staff"));
                compare(service.document.nodes[0].setup.groups.length, 1);
                if (!service.localError) service.accountChange(0, "removeGroup", "staff");
                verify(service.localError.length > 0);
                mouseClick(control("accountMembership-ally-staff"));
                mouseClick(control("removeAccountGroup-staff"));
                if (service.document.nodes[0].setup.groups.length) service.accountChange(0, "removeGroup", "staff");
                compare(service.document.nodes[0].setup.groups.length, 0);
                mouseClick(control("removeAccount-ally"));
                compare(service.document.nodes[0].setup.users.length, 0);
                compare(service.document.nodes[0].user.name, "student");
            }
            function test_password_popup_submit_and_cancel() {
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
                compare(findChild(panel, "mainAccountPassword").text, "");
                compare(backend.requests.length, 1);
            }
            function test_password_uses_backend_utf8_byte_limit() {
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
                const toggle = control("extraAccountsToggle");
                if (!toggle.checked) mouseClick(toggle);
                scroll.contentItem.contentY = 0;
                wait(70);
                if (checks.screenshotFolder) grabImage(window.contentItem).save(checks.screenshotFolder + "/accounts-" + data.tag + ".png");
                verify(panel.width <= scroll.availableWidth + 1);
                mouseClick(control("mainOpenPassword"));
                const popup = findChild(panel, "mainPasswordDialog");
                tryCompare(popup, "opened", true);
                wait(30);
                if (checks.screenshotFolder) grabImage(window.contentItem).save(checks.screenshotFolder + "/account-password-" + data.tag + ".png");
                verify(popup.width <= window.width);
                keyClick(Qt.Key_Escape);
            }
        }
    }
}
