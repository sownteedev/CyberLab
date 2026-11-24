import QtQuick
import QtQuick.Controls.Basic
import QtTest
import ".." as Studio

Item {
    id: checks
    property string screenshotFolder: ""
    property int page: 0
    property bool acceptNavigation: true

    ApplicationWindow {
        id: window
        width: 1280
        height: 600
        visible: true
        color: Studio.Theme.surface
        header: Studio.AppBar {
            id: bar
            currentIndex: checks.page
            connected: true
            onNavigationRequested: index => { if (checks.acceptNavigation) checks.page = index; }
        }
        SignalSpy { id: navigationSpy; target: bar; signalName: "navigationRequested" }
        SignalSpy { id: settingsSpy; target: bar; signalName: "settingsRequested" }
        SignalSpy { id: refreshSpy; target: bar; signalName: "refreshRequested" }
        SignalSpy { id: maximizeSpy; target: bar; signalName: "maximizeRequested" }
        SignalSpy { id: closeSpy; target: bar; signalName: "closeRequested" }
        SignalSpy { id: moveSpy; target: bar; signalName: "moveRequested" }

        TestCase {
            name: "StudioNavigation"
            when: window.visible

            function tab(index) { return findChild(bar, "navigationItem-" + index); }
            function init() {
                Studio.Theme.themeMode = "dark";
                Studio.Theme.reducedMotion = true;
                checks.page = 0;
                checks.acceptNavigation = true;
                bar.busy = false;
                bar.connected = true;
                window.width = 1280;
                window.requestActivate();
                tryCompare(window, "active", true);
                navigationSpy.clear(); settingsSpy.clear(); refreshSpy.clear();
                maximizeSpy.clear(); closeSpy.clear(); moveSpy.clear();
                waitForRendering(bar);
            }
            function test_selection_tracks_accepted_route_only() {
                checks.acceptNavigation = false;
                mouseClick(tab(1));
                compare(navigationSpy.count, 1);
                compare(navigationSpy.signalArguments[0][0], 1);
                compare(bar.currentIndex, 0);
                verify(tab(0).Accessible.selected && !tab(1).Accessible.selected);
                checks.page = 1;
                verify(tab(1).Accessible.selected && !tab(0).Accessible.selected);
                checks.acceptNavigation = true;
                mouseClick(tab(2));
                compare(bar.currentIndex, 2);
                verify(tab(2).Accessible.selected);
                mouseClick(tab(0));
                compare(bar.currentIndex, 0);
            }
            function test_brand_description_stays_fixed_across_pages() {
                const description = findChild(bar, "cyberlabDescription");
                for (const width of [1280, 1100, 1000, 640, 520]) {
                    window.width = width;
                    waitForRendering(bar);
                    for (let index = 0; index < 3; index++) {
                        mouseClick(tab(index));
                        compare(bar.currentIndex, index);
                        compare(description.text, "Không gian thực hành");
                        verify(description.visible);
                        verify(!description.truncated);
                    }
                }
            }
            function test_keyboard_navigation() {
                tab(0).forceActiveFocus(Qt.TabFocusReason);
                keyClick(Qt.Key_Right);
                verify(tab(1).activeFocus);
                compare(navigationSpy.count, 0);
                keyClick(Qt.Key_Space);
                compare(bar.currentIndex, 1);
                keyClick(Qt.Key_End);
                verify(tab(2).activeFocus);
                keyClick(Qt.Key_Space);
                compare(bar.currentIndex, 2);
                keyClick(Qt.Key_Home);
                verify(tab(0).activeFocus);
                keyClick(Qt.Key_Left);
                verify(tab(2).activeFocus);
                keyClick(Qt.Key_Tab);
                verify(findChild(bar, "openSettingsButton").activeFocus);
            }
            function test_indicator_slides_and_retargets() {
                const navigation = findChild(bar, "studioNavigation");
                compare(navigation.implicitWidth, 440);
                compare(navigation.selectionPosition, 0);
                Studio.Theme.reducedMotion = false;
                mouseClick(tab(2));
                tryVerify(() => navigation.selectionPosition > 0 && navigation.selectionPosition < 2);
                wait(60);
                verify(navigation.selectionPosition < 2);
                mouseClick(tab(0));
                tryCompare(navigation, "selectionPosition", 0, 600);
                mouseClick(tab(1));
                tryCompare(navigation, "selectionPosition", 1, 600);
                const indicator = findChild(navigation, "navigationIndicator");
                fuzzyCompare(indicator.x, 4 + navigation.slotWidth, 0.1);
            }
            function test_indicator_reduced_motion_and_resize() {
                const navigation = findChild(bar, "studioNavigation");
                mouseClick(tab(2));
                compare(navigation.selectionPosition, 2);
                window.width = 380;
                waitForRendering(bar);
                const indicator = findChild(navigation, "navigationIndicator");
                const buttonPosition = tab(2).mapToItem(navigation, 0, 4);
                fuzzyCompare(indicator.x, buttonPosition.x, 1);
                fuzzyCompare(indicator.width, tab(2).width, 1);
                checks.acceptNavigation = false;
                mouseClick(tab(0));
                compare(navigation.selectionPosition, 2);
            }
            function test_hover_has_no_brightness_flash_data() {
                return [{ tag: "light", theme: "light" }, { tag: "dark", theme: "dark" }];
            }
            function test_hover_has_no_brightness_flash(data) {
                Studio.Theme.themeMode = data.theme;
                Studio.Theme.reducedMotion = false;
                mouseMove(window.contentItem, 8, 200);
                wait(180);
                const button = tab(1);
                const sampleX = Math.round(button.width - 12);
                function sample() {
                    const layer = findChild(button, "navigationStateLayer") || button.background;
                    const tint = layer.color;
                    const opacity = tint.a * layer.opacity;
                    const surface = Studio.Theme.surfaceContainer;
                    return ["r", "g", "b"].map(channel => Math.round(255 * (tint[channel] * opacity + surface[channel] * (1 - opacity))));
                }
                const idle = sample();
                mouseMove(button, sampleX, 24);
                verify(button.hovered);
                const samples = [];
                for (let frame = 0; frame < 24; frame++) {
                    wait(8);
                    samples.push(sample());
                }
                const hovered = sample();
                mouseMove(window.contentItem, 8, 200);
                for (let frame = 0; frame < 24; frame++) {
                    wait(8);
                    samples.push(sample());
                }
                for (const color of samples) {
                    for (let channel = 0; channel < 3; channel++) {
                        const low = Math.min(idle[channel], hovered[channel]) - 2;
                        const high = Math.max(idle[channel], hovered[channel]) + 2;
                        verify(color[channel] >= low && color[channel] <= high,
                            "hover channel " + channel + " flashes to " + color[channel] + "; stable range " + low + ".." + high);
                    }
                }
            }
            function test_selection_keeps_label_geometry() {
                const button = tab(1);
                const label = button.contentItem.children.find(child => typeof child.text === "string");
                verify(label);
                const before = label.mapToItem(button, 0, 0, label.width, label.height);
                mouseClick(button);
                waitForRendering(bar);
                const after = label.mapToItem(button, 0, 0, label.width, label.height);
                fuzzyCompare(after.x, before.x, 0.1);
                fuzzyCompare(after.width, before.width, 0.1);
            }
            function test_press_keeps_hover_layer_over_sliding_selection() {
                const button = tab(1);
                const layer = findChild(button, "navigationStateLayer");
                verify(layer);
                mouseMove(button);
                compare(layer.opacity, 0.08);
                Studio.Theme.reducedMotion = false;
                mousePress(button);
                tryCompare(layer, "opacity", 0.12);
                mouseRelease(button);
                compare(bar.currentIndex, 1);
                tryCompare(layer, "opacity", 0.08);
                compare(layer.color, Studio.Theme.textOnSurface);
                for (let index = 0; index < 8; index++) {
                    mouseMove(tab(index % 3));
                    wait(8);
                }
                mouseMove(button);
                tryCompare(layer, "opacity", 0.08);
                mouseMove(window.contentItem, 8, 200);
                tryCompare(layer, "opacity", 0);
            }
            function test_busy_keeps_window_controls_available() {
                bar.busy = true;
                for (let index = 0; index < 3; index++) {
                    verify(!tab(index).enabled);
                    mouseClick(tab(index));
                }
                compare(navigationSpy.count, 0);
                verify(!findChild(bar, "refreshButton").enabled);
                mouseClick(findChild(bar, "openSettingsButton"));
                mouseClick(findChild(bar, "maximizeWindowButton"));
                mouseClick(findChild(bar, "closeWindowButton"));
                compare(settingsSpy.count, 1);
                compare(maximizeSpy.count, 1);
                compare(closeSpy.count, 1);
                compare(moveSpy.count, 0);
            }
            function test_topbar_drag_does_not_capture_buttons() {
                const brand = findChild(bar, "cyberlabBrand");
                mouseDrag(brand, brand.width / 2, brand.height / 2, 30, 8);
                compare(moveSpy.count, 1);
                const spacer = findChild(bar, "topbarSpacer");
                const position = spacer.mapToItem(bar, spacer.width / 2, 0);
                mouseDrag(bar, position.x, bar.height / 2, 24, 6);
                compare(moveSpy.count, 2);
                mouseClick(brand, 10, 10, Qt.RightButton);
                compare(moveSpy.count, 2);
                for (const name of ["navigationItem-0", "navigationItem-1", "navigationItem-2", "openSettingsButton", "refreshButton", "maximizeWindowButton", "closeWindowButton"]) {
                    const control = findChild(bar, name);
                    mouseClick(control);
                    compare(moveSpy.count, 2, name + " must not move the window");
                    mouseDrag(control, control.width / 2, control.height / 2, 12, 0);
                    compare(moveSpy.count, 2, name + " drag must stay on its control");
                }
                bar.busy = true;
                mouseClick(tab(0));
                mouseClick(findChild(bar, "refreshButton"));
                compare(moveSpy.count, 2, "disabled controls must not become drag regions");
                window.width = 640;
                waitForRendering(bar);
                mouseDrag(brand, brand.width / 2, brand.height / 2, 25, 8);
                compare(moveSpy.count, 3);
            }
            function test_equal_capsule_insets_data() {
                return [{tag: "desktop", width: 1440}, {tag: "laptop", width: 1024}, {tag: "narrow", width: 380}];
            }
            function test_equal_capsule_insets(data) {
                window.width = data.width;
                waitForRendering(bar);
                const navigation = findChild(bar, "studioNavigation");
                const indicator = findChild(navigation, "navigationIndicator");
                fuzzyCompare(indicator.x, indicator.y, 1);
                fuzzyCompare(navigation.height - indicator.y - indicator.height, indicator.y, 1);
                mouseClick(tab(2));
                fuzzyCompare(navigation.width - indicator.x - indicator.width, indicator.y, 1);
                const controls = findChild(bar, "windowControls");
                const maximize = findChild(controls, "maximizeWindowButton").background;
                const close = findChild(controls, "closeWindowButton").background;
                const first = maximize.mapToItem(controls, 0, 0, maximize.width, maximize.height);
                const last = close.mapToItem(controls, 0, 0, close.width, close.height);
                fuzzyCompare(first.x, first.y, 1);
                fuzzyCompare(controls.height - first.y - first.height, first.x, 1);
                fuzzyCompare(controls.width - last.x - last.width, first.x, 1);
            }
            function test_header_actions_and_status() {
                mouseClick(findChild(bar, "refreshButton"));
                compare(refreshSpy.count, 1);
                const status = findChild(bar, "connectionStatus");
                bar.connected = false;
                compare(status.Accessible.name, "Mất kết nối");
                window.width = 640;
                tryCompare(status, "compact", true);
                compare(status.Accessible.name, "Mất kết nối");
                bar.connected = true;
                compare(status.Accessible.name, "Đã kết nối");
            }
            function test_visual_data() {
                return [
                    { tag: "desktop-dark", width: 1440, theme: "dark" },
                    { tag: "desktop-light", width: 1440, theme: "light" },
                    { tag: "laptop", width: 1024, theme: "dark" },
                    { tag: "minimum-desktop", width: 960, theme: "dark" },
                    { tag: "breakpoint", width: 880, theme: "dark" },
                    { tag: "two-rows", width: 879, theme: "dark" },
                    { tag: "compact", width: 640, theme: "light" },
                    { tag: "narrow", width: 380, theme: "dark" },
                    { tag: "minimum", width: 320, theme: "dark" }
                ];
            }
            function test_visual(data) {
                window.width = data.width;
                Studio.Theme.themeMode = data.theme;
                waitForRendering(bar);
                const navigation = findChild(bar, "studioNavigation");
                const expectedHeight = Studio.Theme.appBarHeight + (bar.compact ? Studio.Theme.controlHeight + Studio.Theme.space8 : 0);
                compare(bar.height, expectedHeight);
                for (const name of ["navigationItem-0", "navigationItem-1", "navigationItem-2", "openSettingsButton", "refreshButton", "maximizeWindowButton", "closeWindowButton"]) {
                    const control = findChild(bar, name);
                    const position = control.mapToItem(bar, 0, 0);
                    verify(control.visible, name);
                    verify(control.width >= 48 && control.height >= 48, name + " hit target");
                    verify(position.x >= 0 && position.x + control.width <= bar.width + 1, name + " horizontal bounds");
                    verify(position.y >= 0 && position.y + control.height <= bar.height + 1, name + " vertical bounds");
                }
                const navigationPosition = navigation.mapToItem(bar, 0, 0);
                const settingsPosition = findChild(bar, "openSettingsButton").mapToItem(bar, 0, 0);
                verify(bar.compact ? navigationPosition.y >= settingsPosition.y + 48 : navigationPosition.x + navigation.width <= settingsPosition.x);
                const brand = findChild(bar, "cyberlabBrand");
                tryCompare(brand, "status", Image.Ready);
                if (checks.screenshotFolder)
                    grabImage(window.contentItem.parent).save(checks.screenshotFolder + "/navigation-" + data.tag + ".png");
                mouseClick(tab(1));
                compare(bar.currentIndex, 1);
                mouseClick(tab(2));
                compare(bar.currentIndex, 2);
            }
        }
    }
}
