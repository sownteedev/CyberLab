import QtQuick
import QtQuick.Controls.Basic
import QtTest
import ".." as Studio

Item {
    id: checks
    property string screenshotFolder: ""
ApplicationWindow {
    id: window
    width: 1080
    height: 740
    visible: true
    color: Studio.Theme.surface
    QtObject {
        id: backend
        property bool busy: false
        property var capabilities: ["authoring"]
        property var requests: []
        property var callbacks: []
        property var notices: []
        property string error: ""
        signal notificationRequested(string message, bool isFailure)
        function request(argv, callback, input) { requests = requests.concat([{argv: argv, input: input}]); callbacks = callbacks.concat([callback]); }
        function notify(message, failed) { notices = notices.concat([{message: message, failed: failed}]); notificationRequested(message, failed); }
    }
    Studio.DraftService { id: editor; backend: backend }
    Studio.DraftResources { id: resources; anchors.fill: parent; anchors.margins: 16; editor: editor }
    Studio.StudioNotifications { id: notifications; api: backend; anchors.right: parent.right; anchors.top: parent.top; width: 420; z: 10 }
    TestCase {
        name: "FileWorkspace"
        when: window.visible
        function init() {
            backend.capabilities = ["authoring", "machine-setup-v1"];
            Studio.Theme.themeMode = "dark";
            window.width = 1080;
            backend.requests = [];
            backend.callbacks = [];
            backend.notices = [];
            notifications.errorToast.dismiss(false);
            const tree = findChild(resources, "seedFileTree");
            tree.collapsed = {};
            const properties = findChild(resources, "filePropertiesDialog");
            if (properties) { properties.close(); tryCompare(properties, "visible", false); }
            tree.naming = null;
            findChild(tree, "fileTreeMenu").close();
            editor.adopt({id: "fixture", revision: 1, digest: "one", assets: [], definition: JSON.stringify({
                nodes: [{id: "client", command: ["sleep", "infinity"]}, {id: "server", command: ["sleep", "infinity"]}],
                networks: [], metadata: {id: "fixture", name: "Fixture"}, terminals: []
            })}, false);
            editor.localError = "";
            editor.policy = {home_directory_target: true};
            window.requestActivate();
            tryCompare(window, "active", true);
        }
        function test_home_system_branches_and_properties() {
            const document = JSON.parse(editor.definition);
            document.nodes[0].user = {name: "student", uid: 2000, gid: 2000};
            document.nodes[0].setup = {users: [{name: "mary", uid: 3001, gid: 3001}], groups: [{name: "team", gid: 3100}], future: true};
            editor.commit(document);
            editor.files.create("client", "note.py", false);
            editor.files.edit("client", "note.py", "print('home')");
            editor.files.create("client", "/shared_stuff/note.py", false);
            editor.files.edit("client", "/shared_stuff/note.py", "print('system')");
            compare(editor.files.tabs.length, 2);
            compare(editor.files.buffers[editor.files.source("client", "note.py")].text, "print('home')");
            compare(editor.files.buffers[editor.files.source("client", "/shared_stuff/note.py")].text, "print('system')");
            const tree = findChild(resources, "seedFileTree");
            verify(tree.rows.some(row => row.name === "Home"));
            verify(tree.rows.some(row => row.name === "System"));
            const properties = findChild(resources, "filePropertiesDialog");
            verify(properties);
            properties.show("client", "/shared_stuff/note.py");
            tryCompare(properties, "opened", true);
            compare(properties.mode, "0644");
            verify(properties.ownerChoices.includes("mary"));
            verify(properties.groupChoices.includes("team"));
            properties.mode = "0600";
            properties.owner = "mary";
            properties.group = "team";
            properties.applyChanges();
            compare(editor.document.nodes[0].setup.files[0].mode, "0600");
            verify(editor.document.nodes[0].setup.future);
            editor.files.rename("client", "/shared_stuff/note.py", "renamed.py");
            compare(editor.localError, "");
            compare(editor.files.activeTab.path, "/shared_stuff/renamed.py");
            compare(editor.files.buffers[editor.files.source("client", "/shared_stuff/renamed.py")].text, "print('system')");
        }
        function test_setup_capability_unavailable_preserves_data() {
            editor.files.create("client", "/etc/demo.conf", false);
            const definition = editor.definition;
            backend.capabilities = ["authoring"];
            verify(!editor.files.setupSupported);
            editor.files.create("client", "/etc/other.conf", false);
            verify(editor.localError.length > 0);
            compare(editor.definition, definition);
            editor.save();
            compare(backend.requests.length, 0);
            compare(editor.files.rows("client", "System").filter(row => row.kind === "file").length, 1);
            verify(findChild(resources, "setupFilesUnavailable").visible);
        }
        function test_properties_octal_controls_and_stale_popup() {
            editor.files.create("client", "/shared_stuff", true);
            const properties = findChild(resources, "filePropertiesDialog");
            properties.show("client", "/shared_stuff");
            tryCompare(properties, "opened", true);
            const modeInput = findChild(properties, "filePropertyMode");
            properties.toggleBit(1024, true);
            compare(properties.mode, "2755");
            compare(modeInput.text, "2755");
            properties.mode = "3770";
            verify(properties.bitEnabled(512));
            verify(!properties.bitEnabled(4));
            properties.mode = "4755";
            verify(!findChild(properties, "filePropertySave").enabled);
            properties.mode = "2770";
            properties.applyChanges();
            compare(editor.document.nodes[0].setup.files[0].mode, "2770");
            properties.show("client", "/shared_stuff");
            editor.files.create("client", "other.txt", false);
            properties.mode = "0700";
            properties.applyChanges();
            verify(properties.error.length > 0);
            compare(editor.document.nodes[0].setup.files[0].mode, "2770");
            properties.close();
        }
        function test_setup_mouse_keyboard_screenshots_data() {
            return [{tag: "dark", theme: "dark", width: 1080}, {tag: "light", theme: "light", width: 1080},
                {tag: "narrow", theme: "dark", width: 460}];
        }
        function test_setup_mouse_keyboard_screenshots(data) {
            window.width = data.width;
            Studio.Theme.themeMode = data.theme;
            const document = JSON.parse(editor.definition);
            document.nodes = [{id: "client", user: {name: "student", uid: 2000, gid: 2000},
                setup: {users: [{name: "mary", uid: 3001, gid: 3001}], groups: [{name: "team", gid: 3100}]}}];
            editor.commit(document);
            const tree = findChild(resources, "seedFileTree");
            const listing = tree.contentItem.children.find(child => typeof child.positionViewAtEnd === "function");
            function clickRow(key, button) {
                const index = tree.rows.findIndex(row => row.key === key);
                verify(index >= 0, key);
                listing.positionViewAtIndex(index, ListView.Contain);
                listing.forceLayout();
                const row = listing.itemAtIndex(index);
                verify(row);
                mouseClick(listing, 70, row.y - listing.contentY + 24, button);
            }
            function typeInto(field, text) {
                mouseClick(field);
                keyClick(Qt.Key_A, Qt.ControlModifier);
                for (const character of text) keyClick(character);
            }
            function createWithMenu(root, name) {
                clickRow(root, Qt.RightButton);
                const menu = findChild(tree, "fileTreeMenu");
                tryCompare(menu, "opened", true);
                wait(80);
                mouseClick(findChild(tree, "fileTreeNewFile"));
                tryVerify(() => findChild(tree, "fileTreeName") !== null);
                const input = findChild(tree, "fileTreeName");
                tryCompare(input, "activeFocus", true);
                for (const character of name) keyClick(character);
                keyClick(Qt.Key_Return);
                wait(80);
                compare(editor.localError, "");
            }
            wait(100);
            createWithMenu("client:Home", "notes.py");
            let code = findChild(resources, "fileText-client:notes.py");
            verify(code);
            typeInto(code, "print(1)");
            createWithMenu("client:System", "/shared_stuff/notes.py");
            code = findChild(resources, "fileText-client:/shared_stuff/notes.py");
            verify(code);
            typeInto(code, "print(2)");
            compare(editor.files.buffers[editor.files.source("client", "notes.py")].text, "print(1)");
            compare(editor.files.buffers[editor.files.source("client", "/shared_stuff/notes.py")].text, "print(2)");
            verify(findChild(resources, "fileTabLabel-client:/shared_stuff/notes.py").text.includes("System"));
            wait(180);
            if (checks.screenshotFolder) grabImage(window.contentItem).save(checks.screenshotFolder + "/setup-files-" + data.tag + ".png");
            clickRow("client:/shared_stuff/notes.py", Qt.RightButton);
            tryCompare(findChild(tree, "fileTreeMenu"), "opened", true);
            wait(80);
            if (checks.screenshotFolder) grabImage(window.contentItem).save(checks.screenshotFolder + "/setup-menu-" + data.tag + ".png");
            mouseClick(findChild(tree, "fileTreeProperties"));
            compare(editor.localError, "");
            const properties = findChild(resources, "filePropertiesDialog");
            tryCompare(properties, "opened", true);
            const owner = findChild(properties, "filePropertyOwner");
            mouseClick(owner);
            tryCompare(owner.popup, "opened", true);
            keyClick(Qt.Key_End);
            keyClick(Qt.Key_Return);
            tryCompare(owner.popup, "visible", false);
            compare(properties.owner, "mary");
            const group = findChild(properties, "filePropertyGroup");
            mouseClick(group);
            tryCompare(group.popup, "opened", true);
            keyClick(Qt.Key_End);
            keyClick(Qt.Key_Return);
            tryCompare(group.popup, "visible", false);
            compare(properties.group, "team");
            const octal = findChild(properties, "filePropertyMode");
            typeInto(octal, "0600");
            compare(properties.mode, "0600");
            // Exercise the same permission action used by the visible checkbox.
            properties.toggleBit(32, true);
            compare(properties.mode, "0640");
            compare(octal.text, "0640");
            wait(180);
            if (checks.screenshotFolder) grabImage(window.contentItem).save(checks.screenshotFolder + "/setup-properties-" + data.tag + ".png");
            mouseClick(findChild(properties, "filePropertySave"));
            tryCompare(properties, "visible", false);
            compare(editor.document.nodes[0].setup.files[0].mode, "0640");
            compare(editor.document.nodes[0].setup.files[0].owner, "mary");
            compare(editor.files.buffers[editor.files.source("client", "/shared_stuff/notes.py")].text, "print(2)");
        }
        function test_system_import_and_directory_child_override() {
            const document = JSON.parse(editor.definition);
            document.nodes[0].user = {name: "student", uid: 2000, gid: 2000};
            document.nodes[0].setup = {files: [{source: "assets/project", target: "/srv/project", owner: "root", group: "root", mode: "2770"}]};
            editor.adopt({id: "fixture", revision: 1, assets: [{path: "assets/project", kind: "directory"},
                {path: "assets/project/one.py", kind: "file"}], definition: JSON.stringify(document)}, false);
            editor.files.setEntry("assets/project/one.py", {text: "old", ready: true, dirty: false});
            editor.files.open("client", "/srv/project/one.py");
            editor.files.properties("client", "/srv/project/one.py", {owner: "student", group: "student", mode: "0600"});
            compare(editor.localError, "");
            compare(editor.document.nodes[0].setup.files.length, 2);
            editor.files.edit("client", "/srv/project/one.py", "print('unsaved')");
            editor.files.importLocal("/fake/import.py", "client", "/srv/project", false);
            backend.callbacks[0]({resources: [{path: "two.py", kind: "file", content: {text: "print('two')"}}]}, "");
            compare(editor.localError, "");
            compare(editor.files.buffers[editor.files.source("client", "/srv/project/one.py")].text, "print('unsaved')");
            compare(editor.files.buffers[editor.files.source("client", "/srv/project/two.py")].text, "print('two')");
            editor.save();
            const payload = JSON.parse(backend.requests[1].input);
            compare(payload.entries[editor.files.source("client", "/srv/project/one.py")].text, "print('unsaved')");
            verify(JSON.parse(payload.definition).nodes[0].setup.files.some(entry => entry.mode === "0600"));
        }
        function test_create_edit_rename_and_atomic_save() {
            editor.files.create("client", "scripts", true);
            editor.files.create("client", "scripts/hello.sh", false);
            wait(80);
            verify(findChild(resources, "seedFileTree"));
            const text = findChild(resources, "fileText-client:scripts/hello.sh");
            verify(text);
            editor.files.edit("client", "scripts/hello.sh", "echo hello\n");
            editor.files.rename("client", "scripts", "bin");
            compare(editor.files.activeTab.path, "bin/hello.sh");
            const source = editor.files.source("client", "bin/hello.sh");
            compare(editor.files.buffers[source].text, "echo hello\n");
            verify(editor.dirty);
            editor.save();
            compare(backend.requests[0].argv[1], "save-workspace");
            compare(JSON.parse(backend.requests[0].input).entries[source].text, "echo hello\n");
            backend.callbacks[0](null, "Conflict");
            verify(editor.dirty);
            compare(editor.files.buffers[source].text, "echo hello\n");
        }
        function test_invalid_name_pops_up_without_losing_input() {
            const tree = findChild(resources, "seedFileTree");
            tree.choose(tree.rows[0]);
            tree.begin("file");
            wait(40);
            const input = findChild(tree, "fileTreeName");
            verify(input.visible, "Name input must be the visible creation row");
            input.text = "hello world.py";
            tree.acceptName(input.text);
            compare(backend.notices.length, 1);
            verify(backend.notices[0].failed);
            verify(!backend.notices[0].message.startsWith("Error:"));
            verify(notifications.errorToast.shown);
            wait(250);
            if (checks.screenshotFolder) grabImage(window.contentItem).save(checks.screenshotFolder + "/file-name-popup.png");
            compare(editor.localError, "");
            verify(tree.naming !== null);
            compare(input.text, "hello world.py");
            tree.acceptName("hello.py");
            compare(tree.naming, null);
            verify(editor.files.rows("client").some(row => row.path === "hello.py"));
            tree.choose(tree.rows[0]);
            tree.begin("file");
            tree.acceptName("hello.py");
            compare(backend.notices.length, 2);
            verify(tree.naming !== null);
            tree.naming = null;
        }
        function test_new_name_takes_focus_after_menu_closes_data() {
            return [
                {tag: "file", action: 0, name: "note.txt", belowFold: false},
                {tag: "folder", action: 1, name: "examples", belowFold: false},
                {tag: "below-fold", action: 0, name: "bottom.txt", belowFold: true}
            ];
        }
        function test_new_name_takes_focus_after_menu_closes(data) {
            const tree = findChild(resources, "seedFileTree");
            if (data.belowFold) {
                for (let index = 0; index < 25; index++) editor.files.create("client", "folder-" + index, true);
                tree.choose(tree.rows.find(row => row.key === "server:"));
            } else tree.choose(tree.rows[0]);
            mouseClick(findChild(tree, "fileTreeAdd"));
            const menu = findChild(tree, "fileTreeMenu");
            tryCompare(menu, "opened", true);
            wait(80);
            mouseClick(menu.itemAt(data.action));
            tryCompare(menu, "visible", false);
            tryVerify(() => tree.naming !== null);
            tryVerify(() => findChild(tree, "fileTreeName") !== null);
            const input = findChild(tree, "fileTreeName");
            verify(input);
            tryCompare(input, "activeFocus", true);
            const fieldPosition = input.mapToItem(tree, 0, 0);
            verify(fieldPosition.y >= 0 && fieldPosition.y + input.height <= tree.height,
                   "The focused name field must also be visible without manually scrolling");
            for (const character of data.name) keyClick(character);
            compare(input.text, data.name);
            keyClick(Qt.Key_Return);
            compare(tree.naming, null);
            verify(editor.files.rows(data.belowFold ? "server" : "client").some(row => row.path === data.name));
        }
        function test_drag_selection_scrolls_horizontally_data() {
            return [{tag: "right-edge", direction: 1}, {tag: "left-outside", direction: -1}];
        }
        function test_drag_selection_scrolls_horizontally(data) {
            const source = "0123456789 ".repeat(80) + "\nsecond line\n";
            editor.files.create("client", "wide.txt", false);
            editor.files.edit("client", "wide.txt", source);
            wait(80);
            const code = findChild(resources, "fileText-client:wide.txt");
            let scroll = code.parent;
            while (scroll && typeof scroll.contentX !== "number") scroll = scroll.parent;
            verify(scroll && scroll.contentWidth > scroll.width * 2);
            scroll.contentX = 500;
            const startX = scroll.width / 2;
            const targetX = data.direction > 0 ? scroll.width - 2 : -10;
            mousePress(scroll, startX, 25);
            try {
                mouseMove(scroll, targetX, 25, 30);
                const offset = scroll.contentX;
                const selectedStart = code.selectionStart;
                const selectedEnd = code.selectionEnd;
                tryVerify(() => data.direction * (scroll.contentX - offset) > 30, 1500,
                          "Holding selection at the edge must keep scrolling without more mouse motion");
                verify(data.direction > 0 ? code.selectionEnd > selectedEnd : code.selectionStart < selectedStart,
                       "Auto-scroll must extend the text selection");
                mouseMove(scroll, scroll.width / 2, 25, 20);
                wait(40);
                const centered = scroll.contentX;
                wait(80);
                compare(scroll.contentX, centered);
                mouseMove(scroll, targetX, 25, 20);
            } finally {
                mouseRelease(scroll, targetX, 25);
            }
            wait(80);
            const stopped = scroll.contentX;
            wait(120);
            compare(scroll.contentX, stopped);
            compare(code.text, source);
            verify(code.selectedText.length > 0);
            verify(scroll.contentX >= 0 && scroll.contentX <= scroll.contentWidth - scroll.width);
        }
        function test_hover_and_click_near_edge_do_not_auto_scroll() {
            editor.files.create("client", "wide.txt", false);
            editor.files.edit("client", "wide.txt", "text ".repeat(300));
            wait(80);
            const code = findChild(resources, "fileText-client:wide.txt");
            let scroll = code.parent;
            while (scroll && typeof scroll.contentX !== "number") scroll = scroll.parent;
            scroll.contentX = 300;
            code.forceActiveFocus();
            mouseMove(scroll, scroll.width - 2, 25);
            wait(100);
            compare(scroll.contentX, 300);
            mousePress(scroll, scroll.width - 2, 25);
            try {
                wait(100);
                compare(scroll.contentX, 300);
            } finally {
                mouseRelease(scroll, scroll.width - 2, 25);
            }
        }
        function test_python_highlighting_preserves_plain_text_and_undo() {
            const source = "# Greeting\nimport sys\n\ndef greet(name):\n    return f\"Hello {name}\"\n\nprint(greet(42))\n";
            editor.files.create("client", "hello.py", false);
            editor.files.edit("client", "hello.py", source);
            wait(100);
            const code = findChild(resources, "fileText-client:hello.py");
            const syntax = findChild(resources, "fileSyntax-client:hello.py");
            const numbers = findChild(resources, "fileLines-client:hello.py");
            verify(syntax, "Code has a syntax color layer");
            verify(numbers);
            verify(String(numbers.color) !== String(syntax.color));
            verify(syntax.text.includes("<font color="));
            compare(code.text, source);
            code.forceActiveFocus();
            code.cursorPosition = code.length;
            keyClick(Qt.Key_X);
            compare(editor.files.buffers[editor.files.source("client", "hello.py")].text, source + "x");
            keyClick(Qt.Key_Z, Qt.ControlModifier);
            compare(code.text, source);
            verify(code.canRedo);
            const markup = syntax.text;
            Studio.Theme.themeMode = "light";
            wait(100);
            verify(syntax.text !== markup);
            compare(code.text, source);
            verify(code.canRedo);
            if (checks.screenshotFolder) grabImage(window.contentItem).save(checks.screenshotFolder + "/syntax-python-light.png");
            Studio.Theme.themeMode = "dark";
            wait(250);
            if (checks.screenshotFolder) grabImage(window.contentItem).save(checks.screenshotFolder + "/syntax-python-dark.png");
            code.select(0, 10);
            compare(code.selectedText, source.substring(0, 10));
            if (checks.screenshotFolder) grabImage(window.contentItem).save(checks.screenshotFolder + "/syntax-selection.png");
            code.deselect();
            editor.files.rename("client", "hello.py", "hello.txt");
            wait(80);
            verify(!findChild(resources, "fileSyntax-client:hello.txt").visible);
            compare(findChild(resources, "fileText-client:hello.txt").text, source);
        }
        function test_syntax_languages_and_geometry_data() {
            return [
                {tag: "python-tabs", path: "tabs.py", text: "\tprint(42)"},
                {tag: "python-unicode", path: "unicode.py", text: "print('Tiếng Việt 😀')"},
                {tag: "python-multiline", path: "multi.py", text: 'text = """first\n# inside string\nlast"""\n'},
                {tag: "shell", path: "start.sh", text: '#!/bin/sh\necho "$HOME"\n'},
                {tag: "json", path: "config.json", text: '{"port": 8080, "enabled": true}'},
                {tag: "yaml", path: "config.yaml", text: "port: 8080\nenabled: true\n"},
                {tag: "javascript", path: "main.js", text: 'const answer = 42; // hello\n'},
                {tag: "markdown", path: "guide.md", text: '# Hello\n**Bold** and `code`\n'},
                {tag: "hostile", path: "markup.py", text: '# <img src="file:///etc/passwd">\nprint("<b>&nbsp;</b>")\n'}
            ];
        }
        function test_syntax_languages_and_geometry(data) {
            editor.files.create("client", data.path, false);
            editor.files.edit("client", data.path, data.text);
            wait(100);
            const code = findChild(resources, "fileText-client:" + data.path);
            const syntax = findChild(resources, "fileSyntax-client:" + data.path);
            verify(syntax.text.includes("<font color="), data.tag);
            compare(code.text, data.text);
            if (!data.text.includes("\n"))
                verify(Math.abs(syntax.implicitWidth - (code.positionToRectangle(code.length).x - code.leftPadding)) < 2, "Color and caret geometry match: " + data.tag);
            if (data.tag === "hostile") verify(!syntax.text.includes("<img"));
        }
        function test_syntax_maximum_text() {
            const large = 'print("Hello") # comment\n'.repeat(2700).slice(0, 65536);
            editor.files.create("client", "large.py", false);
            editor.files.edit("client", "large.py", large);
            wait(20);
            const syntax = findChild(resources, "fileSyntax-client:large.py");
            tryVerify(() => syntax.text.includes("<font color="), 5000);
            compare(findChild(resources, "fileText-client:large.py").text, large);
            editor.files.edit("client", "large.py", large.replace(/Hello/g, "World"));
            wait(100);
            editor.files.edit("client", "large.py", "print('latest')\n");
            Studio.Theme.themeMode = "light";
            tryVerify(() => syntax.text.includes("latest"), 5000);
            verify(!syntax.text.includes("World"));
            verify(!syntax.text.includes("Hello"));
            compare(findChild(resources, "fileText-client:large.py").text, "print('latest')\n");
        }
        function test_close_tab_preserves_unsaved_buffer() {
            editor.files.create("client", "one.txt", false);
            editor.files.edit("client", "one.txt", "keep me");
            editor.files.close(editor.files.activeKey);
            verify(editor.dirty);
            editor.files.open("client", "one.txt");
            compare(editor.files.buffers[editor.files.source("client", "one.txt")].text, "keep me");
        }
        function test_material_tabs_keep_names_and_close_targets_readable() {
            editor.files.create("client", "start-client.sh", false);
            wait(80);
            const label = findChild(resources, "fileTabLabel-client:start-client.sh");
            verify(label, "File tabs expose their label");
            compare(label.text, "start-client.sh");
            verify(!label.truncated, "Ordinary filenames must not be elided");
            const close = findChild(resources, "fileTabClose-client:start-client.sh");
            verify(close.width >= 48 && close.height >= 48);
            const tab = findChild(resources, "fileTab-client:start-client.sh");
            const position = close.mapToItem(tab, 0, 0);
            verify(position.x + close.width <= tab.width);
            editor.files.create("server", "start-client.sh", false);
            wait(80);
            verify(findChild(resources, "fileTabLabel-client:start-client.sh").text.includes("client"), "Duplicate filenames include the machine");
            const activate = findChild(resources, "fileTabSelect-client:start-client.sh");
            activate.forceActiveFocus();
            keyClick(Qt.Key_Space);
            compare(editor.files.activeKey, "client:start-client.sh");
            findChild(resources, "fileTabClose-client:start-client.sh").forceActiveFocus();
            keyClick(Qt.Key_Space);
            compare(editor.files.tabs.length, 1);
            verify(editor.files.buffers[editor.files.source("client", "start-client.sh")]);
        }
        function test_tabs_scroll_to_active_and_disambiguate_folders() {
            editor.files.create("client", "first", true);
            editor.files.create("client", "second", true);
            editor.files.create("client", "first/config.yaml", false);
            editor.files.create("client", "second/config.yaml", false);
            wait(80);
            compare(findChild(resources, "fileTabLabel-client:first/config.yaml").text, "client / first/config.yaml");
            window.width = 460;
            for (let index = 0; index < 6; index++) editor.files.create("server", "settings-" + index + ".txt", false);
            wait(80);
            const tabs = findChild(resources, "fileTabs");
            verify(tabs.contentItem.contentX > 0);
            editor.files.activeKey = "client:first/config.yaml";
            wait(80);
            compare(tabs.contentItem.contentX, 0);
            compare(findChild(resources, "seedFileTree").selectedKey, editor.files.activeKey);
            findChild(resources, "fileTabSelect-server:settings-5.txt").forceActiveFocus();
            wait(80);
            verify(tabs.contentItem.contentX > 0, "Keyboard focus must stay visible in the tab strip");
        }
        function test_startup_uses_same_buffer() {
            editor.startup.create(editor.document.nodes[0]);
            const script = editor.startup.descriptor(editor.document.nodes[0]);
            editor.files.open("client", script.target);
            editor.files.edit("client", script.target, "echo edited\n");
            const current = editor.startup.descriptor(editor.document.nodes[0]);
            compare(editor.startup.entries[current.source].text, "echo edited\n");
            editor.startup.edit(editor.document.nodes[0], "echo startup\n");
            compare(editor.files.buffers[current.source].text, "echo startup\n");
        }
        function test_activating_tab_reveals_collapsed_machine_and_folder() {
            editor.files.create("client", "folder", true);
            editor.files.create("client", "folder/one.txt", false);
            editor.files.create("server", "two.txt", false);
            wait(60);
            const tree = findChild(resources, "seedFileTree");
            tree.collapsed = {"client:": true, "client:folder": true};
            tree.choose(tree.rows.find(row => row.key === "server:"));
            editor.files.activeKey = "client:folder/one.txt";
            wait(60);
            compare(tree.selectedKey, "client:folder/one.txt");
            compare(editor.selectedNode, 0);
            verify(tree.rows.some(row => row.key === editor.files.activeKey));
            tree.begin("file");
            compare(tree.naming.nodeId, "client");
            compare(tree.naming.folder, "folder");
            tree.naming = null;
        }
        function test_expanding_bottom_folder_preserves_viewport_data() {
            return [
                {tag: "mouse", keyboard: false, activeFile: false, width: 1080},
                {tag: "keyboard", keyboard: true, activeFile: false, width: 1080},
                {tag: "another-file-open", keyboard: false, activeFile: true, width: 1080},
                {tag: "compact", keyboard: false, activeFile: false, width: 460}
            ];
        }
        function test_expanding_bottom_folder_preserves_viewport(data) {
            window.width = data.width;
            const assets = [];
            const nodes = ["client", "app", "db", "visitor"].map(nodeId => {
                const source = "assets/editor/" + nodeId;
                ["tools/check-network.py", "tools/serve.py", "network.json", "start.sh"].forEach(path => {
                    assets.push({path: source + "/" + path, kind: "file", size: 0});
                });
                return {id: nodeId, command: ["sleep", "infinity"], files: [{source: source, target: "."}]};
            });
            editor.adopt({id: "four-machines", revision: 1, assets: assets, definition: JSON.stringify({
                nodes: nodes, networks: [], metadata: {id: "four-machines", name: "Four machines"}, terminals: []
            })}, false);
            const tree = findChild(resources, "seedFileTree");
            const listing = tree.contentItem.children.find(child => typeof child.positionViewAtEnd === "function");
            verify(listing);
            if (data.activeFile) {
                editor.files.setEntry("assets/editor/client/network.json", {text: "{}", ready: true, dirty: false});
                editor.files.open("client", "network.json");
            }
            wait(80);
            tree.collapsed = {"visitor:tools": true};
            wait(40);
            listing.positionViewAtEnd();
            listing.forceLayout();
            const folderIndex = tree.rows.findIndex(row => row.key === "visitor:tools");
            listing.positionViewAtIndex(folderIndex, ListView.Contain);
            listing.forceLayout();
            const folder = listing.itemAtIndex(folderIndex);
            verify(folder);
            const before = listing.contentY - listing.originY;
            const rowY = folder.y - listing.contentY;
            verify(before > 100, "Fixture must be scrolled away from the beginning");
            if (data.keyboard) {
                listing.currentIndex = folderIndex;
                listing.forceActiveFocus();
                keyClick(Qt.Key_Right);
            } else {
                mouseClick(listing, 55, rowY + 24);
            }
            wait(80);
            verify(!tree.collapsed["visitor:tools"]);
            compare(tree.selectedKey, "visitor:tools");
            compare(listing.currentIndex, tree.rows.findIndex(row => row.key === "visitor:tools"));
            verify(Math.abs(listing.contentY - listing.originY - before) < 1,
                   "Expanding a folder must preserve the scroll offset");
            verify(Math.abs(listing.itemAtIndex(folderIndex).y - listing.contentY - rowY) < 1,
                   "The clicked folder must stay under the pointer");
            if (checks.screenshotFolder && data.tag === "mouse")
                grabImage(window.contentItem).save(checks.screenshotFolder + "/tree-expanded-bottom.png");
            listing.positionViewAtEnd();
            listing.forceLayout();
            if (data.keyboard) {
                keyClick(Qt.Key_Left);
            } else {
                listing.positionViewAtIndex(folderIndex, ListView.Contain);
                listing.forceLayout();
                mouseClick(listing, 55, listing.itemAtIndex(folderIndex).y - listing.contentY + 24);
            }
            wait(80);
            verify(tree.collapsed["visitor:tools"]);
            compare(listing.currentIndex, tree.rows.findIndex(row => row.key === "visitor:tools"));
            verify(Math.abs(listing.contentY - listing.originY - before) < 1,
                   "Collapsing at the end must clamp to the new end, not jump to the beginning");
        }
        function test_documentation_edit_does_not_change_shared_machine_file() {
            const document = JSON.parse(editor.definition);
            document.documentation = "assets/shared.md";
            document.nodes[0].files = [{source: "assets/shared.md", target: "README.md"}];
            editor.adopt({id: "shared", revision: 2, assets: [{path: "assets/shared.md", kind: "file"}], definition: JSON.stringify(document)}, false);
            backend.callbacks[0]({content: "original"}, "");
            editor.files.editDocumentation("new guide");
            verify(editor.document.documentation !== "assets/shared.md");
            compare(editor.files.source("client", "README.md"), "assets/shared.md");
            compare(editor.files.buffers["assets/shared.md"].text, "original");
            compare(editor.documentationText, "new guide");
        }
        function test_tree_inline_name_keyboard_and_tabs() {
            const tree = findChild(resources, "seedFileTree");
            tree.choose(tree.rows[0]);
            tree.begin("folder");
            wait(40);
            const naming = findChild(tree, "fileTreeName");
            verify(naming);
            tree.acceptName("scripts");
            compare(editor.localError, "");
            tree.choose(tree.rows.find(row => row.path === "scripts"));
            tree.begin("file");
            tree.acceptName("hello.sh");
            wait(60);
            const code = findChild(resources, "fileText-client:scripts/hello.sh");
            verify(code);
            code.forceActiveFocus();
            tryCompare(code, "activeFocus", true);
            keyClick(Qt.Key_E);
            keyClick(Qt.Key_C);
            keyClick(Qt.Key_H);
            keyClick(Qt.Key_O);
            compare(editor.files.buffers[editor.files.source("client", "scripts/hello.sh")].text, "echo");
            keyClick(Qt.Key_Tab);
            verify(code.text.endsWith("    "));
            const indented = code.text;
            keyClick(Qt.Key_Z, Qt.ControlModifier);
            verify(code.text !== indented);
            keyClick(Qt.Key_Z, Qt.ControlModifier | Qt.ShiftModifier);
            compare(code.text, indented);
            editor.files.create("server", "config.yaml", false);
            editor.files.activeKey = "client:scripts/hello.sh";
            wait(30);
            compare(findChild(resources, "fileText-client:scripts/hello.sh").text, indented);
            verify(editor.dirty);
        }
        function test_z_layout_and_screenshots() {
            editor.files.create("client", "scripts", true);
            editor.files.create("client", "scripts/start.sh", false);
            editor.files.edit("client", "scripts/start.sh", "#!/bin/sh\nset -eu\n\necho 'Welcome to CyberLab'\n");
            editor.files.create("client", "data", true);
            editor.files.create("server", "config.yaml", false);
            editor.files.edit("server", "config.yaml", "port: 8080\nhost: localhost\n");
            editor.files.activeKey = "client:scripts/start.sh";
            window.width = 1080;
            wait(100);
            if (checks.screenshotFolder) grabImage(window.contentItem).save(checks.screenshotFolder + "/files-wide.png");
            Studio.Theme.themeMode = "light";
            wait(150);
            if (checks.screenshotFolder) grabImage(window.contentItem).save(checks.screenshotFolder + "/files-light.png");
            const menu = findChild(resources, "fileTreeMenu");
            menu.popup(80, 90);
            wait(150);
            if (checks.screenshotFolder) grabImage(window.contentItem).save(checks.screenshotFolder + "/files-menu.png");
            menu.close();
            Studio.Theme.themeMode = "dark";
            window.width = 460;
            wait(200);
            const tree = findChild(resources, "seedFileTree");
            verify(tree.width <= resources.width);
            const code = findChild(resources, "fileText-client:scripts/start.sh");
            verify(code.width > 100);
            if (checks.screenshotFolder) grabImage(window.contentItem).save(checks.screenshotFolder + "/files-narrow.png");
            window.width = 1080;
        }
    }
}
}
