import QtQuick
import QtQuick.Controls.Basic
import QtTest
import ".." as Studio

Item {
    id: checks

    property string screenshotFolder: ""
    readonly property var fixture: ({id: "fixture-session", state: "RUNNING", desktop_nodes: ["client"], nodes: [["client", []]], environments: [["client", "client", "student", 2000, 2000, "/home/student", "/bin/bash"]]})

    QtObject {
        id: api
        property bool busy: false
        property var capabilities: ["seamless-apps"]
        property bool ready: false
        property bool failPreparation: false
        property bool viewerReady: true
        property string hostCode: "xpra-missing"
        property var calls: []
        property string error: ""
        function request(arguments, callback) {
            calls = calls.concat([arguments]);
            if (arguments[0] === "desktop-status") callback({ready: ready, viewer_ready: viewerReady, host: {code: hostCode}}, "");
            else if (arguments[0] === "prepare-desktop") callback({ready: !failPreparation}, failPreparation ? "failed" : "");
            else callback({opened: true}, "");
        }
        function notify(message, failure) { }
    }
    ApplicationWindow {
        id: window
        width: 900
        height: 720
        visible: true
        color: Studio.Theme.surface

        Studio.SessionNodeCard {
            id: card
            x: 24
            y: 24
            width: 600
            session: checks.fixture
            nodeId: "client"
            desktopSupported: true
            onDesktopRequested: desktop.openFor(card.session, card.nodeId)
        }
        Studio.DesktopDialog { id: desktop; api: api }

        TestCase {
            name: "IsolatedDesktopUI"
            when: window.visible
            function confirmation() { return findChild(desktop, "desktopPreparationConfirmation"); }
            function button() { return findChild(card, "nodeDesktopButton"); }
            function init() {
                Studio.Theme.reducedMotion = true;
                api.busy = false;
                api.calls = [];
                api.ready = false;
                api.failPreparation = false;
                api.viewerReady = true;
                api.hostCode = "xpra-missing";
                api.error = "";
                api.capabilities = ["seamless-apps"];
                card.session = checks.fixture;
                card.desktopSupported = true;
                card.busy = false;
                window.requestActivate();
                waitForRendering(card);
            }
            function cleanup() {
                confirmation().close();
                tryCompare(confirmation(), "visible", false);
            }
            function test_requires_confirmation_before_installing() {
                mouseClick(button());
                tryCompare(confirmation(), "opened", true);
                compare(api.calls.length, 1);
                compare(api.calls[0][0], "desktop-status");
                verify(confirmation().message.includes("không cài ứng dụng lên máy thật"));
                if (checks.screenshotFolder) grabImage(window.contentItem).save(checks.screenshotFolder + "/desktop-prepare.png");
                confirmation().reject();
                compare(api.calls.length, 1);
            }
            function test_install_then_open_only_on_success_data() { return [{tag: "success", failed: false}, {tag: "failed", failed: true}]; }
            function test_install_then_open_only_on_success(data) {
                api.failPreparation = data.failed;
                mouseClick(button());
                tryCompare(confirmation(), "opened", true);
                confirmation().accept();
                compare(api.calls[1], ["prepare-desktop", "fixture-session", "client", "--yes"]);
                compare(api.calls.length, data.failed ? 2 : 3);
                if (!data.failed) compare(api.calls[2], ["open-desktop", "fixture-session", "client"]);
            }
            function test_ready_machine_does_not_reinstall() {
                api.ready = true;
                mouseClick(button());
                compare(api.calls.length, 2);
                compare(api.calls[1][0], "open-desktop");
                verify(!confirmation().opened);
            }
            function test_missing_wayland_display_does_not_install_guest_packages() {
                api.viewerReady = false;
                api.hostCode = "xwayland-unavailable";
                mouseClick(button());
                compare(api.calls.length, 1);
                verify(api.error.includes("XWayland"));
                verify(!confirmation().opened);
            }
            function test_missing_viewer_does_not_install_guest_packages() {
                api.viewerReady = false;
                mouseClick(button());
                compare(api.calls.length, 1);
                verify(api.error.includes("Xpra"));
                verify(!confirmation().opened);
            }
            function test_capability_and_state_guards() {
                card.desktopSupported = false;
                verify(!button().visible);
                card.desktopSupported = true;
                card.session = Object.assign({}, checks.fixture, {desktop_nodes: []});
                verify(!button().visible);
                card.session = Object.assign({}, checks.fixture, {state: "STOPPED"});
                verify(!button().enabled);
                desktop.openFor(card.session, "client");
                compare(api.calls.length, 0);
                card.session = checks.fixture;
                card.busy = true;
                verify(!button().enabled);
            }
        }
    }
}
