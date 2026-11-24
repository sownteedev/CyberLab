import QtQuick
import QtQuick.Controls.Basic
import QtTest
import ".." as Studio

Item {
    id: checks

    property string screenshotFolder: ""
    QtObject {
        id: api
        property string selected: "auto"
        property int scans: 0
        property string displayServer: "Xorg"
        function request(arguments, callback) {
            if (arguments.length > 1)
                selected = arguments[2];
            scans++;
            callback({ preferred: selected, warning: "", host: { ready: true, backend: selected === "xpra" ? "xpra" : "native-x11", display_server: displayServer, fallback_reason: "" } }, "");
        }
    }
    Studio.GuiPreferences { id: preferences; backend: api }
    ApplicationWindow {
        id: window
        width: 540
        height: 640
        visible: true
        Studio.GuiSettings { id: panel; width: parent.width - 32; x: 16; y: 16; preferences: preferences }
        TestCase {
            name: "GuiBackendSettings"
            when: windowShown
            function init() { api.displayServer = "Xorg"; preferences.select("auto"); }
            function test_wayland_reports_direct_connection() {
                api.displayServer = "Xwayland";
                preferences.refresh();
                verify(findChild(panel, "guiBackendStatus").text.includes("XWayland"));
                preferences.select("xpra");
                verify(findChild(panel, "guiBackendStatus").text.includes("Xpra"));
            }
            function test_default_auto_uses_safe_backend() {
                compare(findChild(panel, "guiBackendChoice").currentIndex, 0);
                verify(findChild(panel, "guiBackendStatus").text.includes("Native X11"));
            }
            function test_selection_persists_across_refresh() {
                preferences.select("xpra");
                preferences.refresh();
                compare(findChild(panel, "guiBackendChoice").currentIndex, 1);
                verify(findChild(panel, "guiBackendStatus").text.includes("Xpra"));
            }
            function test_rescan_and_small_width() {
                const previous = api.scans;
                mouseClick(findChild(panel, "refreshGuiBackend"));
                compare(api.scans, previous + 1);
                window.width = 360;
                wait(50);
                verify(panel.implicitHeight > 0);
                verify(findChild(panel, "guiBackendChoice").width <= panel.width);
                window.width = 540;
            }
        }
    }
}
