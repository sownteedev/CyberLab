import QtQuick
import QtQuick.Controls.Basic
import QtCore
import QtTest
import ".." as Studio

Item {
    id: checks
    property string screenshotFolder: ""

    ApplicationWindow {
        id: window
        width: 1280
        height: 820
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
                onSettingsRequested: settings.open()
            }
        }
        Studio.StudioViewport {
            id: viewport
            hostWindow: window

            Studio.StudioTextField {
                id: editor
                x: 24; y: 100; width: 300
                text: "Bản nháp chưa lưu"
            }
            Studio.StudioButton {
                id: outside
                x: 16; y: 16
                text: "Nội dung phía sau"
            }
            Studio.StudioComboBox {
                id: choices
                x: 24; y: 200; width: 280
                model: ["Tự động", "Terminal 1", "Terminal 2"]
            }
            Studio.StudioToast {
                id: toast
                anchors.right: parent.right
                anchors.top: parent.top
                anchors.margins: 16
                width: Math.min(440, parent.width - 32)
                lifetime: 0
                failure: true
            }
            Studio.SettingsDialog {
                id: settings
                terminals: QtObject {
                    function refresh() {}
                }
                closePolicy: Popup.CloseOnEscape
            }
            Studio.StudioFileDialog {
                id: filePicker
                title: "Chọn file"
                currentFolder: StandardPaths.writableLocation(StandardPaths.HomeLocation)
            }
        }
        Loader {
            id: preferences
            active: false
            sourceComponent: Component { Studio.AppearanceStore {} }
        }
        Settings {
            id: stored
            location: StandardPaths.writableLocation(StandardPaths.ConfigLocation) + "/cyberlab/studio.ini"
            property int settingsVersion: 1
            property int zoomPercent: 100
            property bool reducedMotion: false
        }
        SignalSpy { id: outsideClick; target: outside; signalName: "clicked" }
        SignalSpy { id: moveRequested; target: bar; signalName: "moveRequested" }

        TestCase {
            name: "StudioZoom"
            when: window.visible

            function test_old_motion_preference_is_ignored() {
                stored.reducedMotion = true;
                stored.setValue("reducedMotion", true);
                stored.sync();
                compare(stored.value("reducedMotion"), true);
                Studio.Theme.reducedMotion = false;
                preferences.active = true;
                tryCompare(preferences, "status", Loader.Ready);
                verify(!Studio.Theme.reducedMotion);
                preferences.active = false;
                stored.reducedMotion = false;
                stored.setValue("reducedMotion", false);
                stored.sync();
            }

            function init() {
                Studio.Theme.reducedMotion = true;
                Studio.Theme.themeMode = "dark";
                Studio.Theme.setZoomPercent(100);
                window.width = 1280;
                window.height = 820;
                window.requestActivate();
                tryCompare(window, "active", true);
                editor.forceActiveFocus();
                outsideClick.clear();
                moveRequested.clear();
                waitForRendering(viewport);
            }
            function cleanup() {
                filePicker.reject();
                settings.close();
                choices.popup.close();
                toast.dismiss(false);
                preferences.active = false;
                Studio.Theme.setZoomPercent(100);
            }
            function sceneRect(item) {
                return item.mapToItem(null, 0, 0, item.width, item.height);
            }
            function checkGeometry() {
                const factor = Studio.Theme.zoomFactor;
                tryVerify(() => Math.abs(viewport.popupOverlay.width * factor - window.width) < 1);
                tryVerify(() => Math.abs(viewport.popupOverlay.height * factor - window.height) < 1);
                fuzzyCompare(sceneRect(bar).width, window.width, 1);
                fuzzyCompare(window.header.height, bar.implicitHeight * factor, 1);
                fuzzyCompare(sceneRect(viewport).width, window.width, 1);
                fuzzyCompare(sceneRect(viewport).height + window.header.height, window.height, 1);
                fuzzyCompare(sceneRect(editor).width, editor.width * factor, 1);
                const overlayRect = sceneRect(viewport.popupOverlay);
                fuzzyCompare(overlayRect.x, 0, 1);
                fuzzyCompare(overlayRect.y, 0, 1);
                fuzzyCompare(overlayRect.width, window.width, 1);
                fuzzyCompare(overlayRect.height, window.height, 1);
            }
            function test_shortcuts_preserve_editor() {
                keyClick(Qt.Key_Minus, Qt.ControlModifier);
                compare(Studio.Theme.zoomPercent, 90);
                keyClick(Qt.Key_Equal, Qt.ControlModifier);
                compare(Studio.Theme.zoomPercent, 100);
                keyClick(Qt.Key_Plus, Qt.ControlModifier);
                compare(Studio.Theme.zoomPercent, 110);
                keyClick(Qt.Key_Plus, Qt.ControlModifier | Qt.ShiftModifier);
                compare(Studio.Theme.zoomPercent, 120);
                keyClick(Qt.Key_0, Qt.ControlModifier);
                compare(Studio.Theme.zoomPercent, 100);
                for (let index = 0; index < 20; index++) keyClick(Qt.Key_Minus, Qt.ControlModifier);
                compare(Studio.Theme.zoomPercent, 70);
                for (let index = 0; index < 20; index++) keyClick(Qt.Key_Equal, Qt.ControlModifier);
                compare(Studio.Theme.zoomPercent, 150);
                compare(editor.text, "Bản nháp chưa lưu");
                verify(editor.activeFocus);
            }
            function test_layout_data() {
                return [
                    { tag: "small", zoom: 70, width: 1280, height: 820 },
                    { tag: "normal", zoom: 100, width: 1280, height: 820 },
                    { tag: "large", zoom: 150, width: 1280, height: 820 },
                    { tag: "compact-large", zoom: 150, width: 960, height: 600 }
                ];
            }
            function test_layout(data) {
                Studio.Theme.setZoomPercent(data.zoom);
                window.width = data.width;
                window.height = data.height;
                waitForRendering(viewport);
                checkGeometry();
                mouseClick(outside);
                compare(outsideClick.count, 1);
                toast.present("Toàn bộ giao diện và thông báo dùng cùng mức thu phóng.");
                tryCompare(toast, "opacity", 1);
                const toastRect = sceneRect(toast);
                fuzzyCompare(toastRect.x + toastRect.width, window.width - 16 * Studio.Theme.zoomFactor, 1);
                if (checks.screenshotFolder)
                    grabImage(window.contentItem.parent).save(checks.screenshotFolder + "/zoom-" + data.tag + ".png");
                window.width += 137;
                window.height += 73;
                waitForRendering(viewport);
                checkGeometry();
            }
            function test_modal_zoom_scrim_and_settings() {
                settings.open();
                tryCompare(settings, "opened", true);
                keyClick(Qt.Key_Minus, Qt.ControlModifier);
                compare(Studio.Theme.zoomPercent, 90);
                mouseClick(findChild(settings.contentItem, "zoomInButton"));
                compare(Studio.Theme.zoomPercent, 100);
                for (const zoom of [70, 150, 100]) {
                    Studio.Theme.setZoomPercent(zoom);
                    waitForRendering(viewport);
                    checkGeometry();
                    const dialogRect = sceneRect(settings.background);
                    fuzzyCompare(dialogRect.x + dialogRect.width / 2, window.width / 2, 1);
                    fuzzyCompare(dialogRect.y + dialogRect.height / 2, window.height / 2, 1);
                    const scrim = findChild(viewport.popupOverlay, "studioDialogScrim");
                    verify(scrim);
                    const scrimRect = sceneRect(scrim);
                    fuzzyCompare(scrimRect.width, window.width, 1);
                    fuzzyCompare(scrimRect.height, window.height, 1);
                    window.width -= 17;
                    window.height -= 11;
                    waitForRendering(viewport);
                    checkGeometry();
                    const resizedRect = sceneRect(settings.background);
                    fuzzyCompare(resizedRect.x + resizedRect.width / 2, window.width / 2, 1);
                    fuzzyCompare(resizedRect.y + resizedRect.height / 2, window.height / 2, 1);
                    mouseClick(outside, 1, 1);
                    compare(outsideClick.count, 0);
                    if (checks.screenshotFolder)
                        grabImage(window.contentItem.parent).save(checks.screenshotFolder + "/zoom-dialog-" + zoom + ".png");
                }
                keyClick(Qt.Key_Equal, Qt.ControlModifier);
                compare(Studio.Theme.zoomPercent, 110);
                mouseClick(findChild(settings.contentItem, "zoomResetButton"));
                compare(Studio.Theme.zoomPercent, 100);
                mouseClick(findChild(settings.header, "closeSettingsButton"));
                tryCompare(settings, "visible", false);
            }
            function test_combobox_coordinates() {
                for (const zoom of [70, 150]) {
                    Studio.Theme.setZoomPercent(zoom);
                    waitForRendering(viewport);
                    mouseClick(choices);
                    tryCompare(choices.popup, "opened", true);
                    const rect = sceneRect(choices.popup.background);
                    const controlRect = sceneRect(choices);
                    fuzzyCompare(rect.x, controlRect.x, 1);
                    fuzzyCompare(rect.width, controlRect.width, 1);
                    fuzzyCompare(rect.y, controlRect.y + controlRect.height + 8 * Studio.Theme.zoomFactor, 1);
                    keyClick(Qt.Key_Down);
                    keyClick(Qt.Key_Return);
                    tryCompare(choices.popup, "visible", false);
                }
            }
            function test_file_picker_zoom_layout() {
                for (const zoom of [70, 100, 150]) {
                    Studio.Theme.setZoomPercent(zoom);
                    filePicker.open();
                    tryCompare(filePicker, "opened", true);
                    tryCompare(filePicker, "validFolder", true);
                    waitForRendering(viewport);
                    const rect = sceneRect(filePicker.background);
                    verify(rect.x >= 0 && rect.y >= 0);
                    verify(rect.x + rect.width <= window.width + 1);
                    verify(rect.y + rect.height <= window.height + 1);
                    const grid = findChild(filePicker.contentItem, "filePickerEntries");
                    verify(grid.width >= 132 && grid.height >= 48);
                    const cancel = findChild(filePicker.footer, "filePickerCancel");
                    const button = sceneRect(cancel);
                    verify(button.y + button.height <= rect.y + rect.height);
                    mouseClick(cancel);
                    tryCompare(filePicker, "visible", false);
                }
            }
            function test_scaled_topbar_drag_and_control_exclusion() {
                let expected = 0;
                for (const zoom of [70, 100, 150]) {
                    Studio.Theme.setZoomPercent(zoom);
                    waitForRendering(viewport);
                    const brand = findChild(bar, "cyberlabBrand");
                    mouseDrag(brand, brand.width / 2, brand.height / 2, 25, 0);
                    compare(moveRequested.count, ++expected);
                    mouseClick(findChild(bar, "navigationItem-1"));
                    mouseClick(findChild(bar, "maximizeWindowButton"));
                    compare(moveRequested.count, expected);
                }
            }
            function test_preferences_reload_and_invalid_value() {
                preferences.active = true;
                tryCompare(preferences, "status", Loader.Ready);
                Studio.Theme.setZoomPercent(80);
                preferences.active = false;
                wait(0);
                Studio.Theme.setZoomPercent(100);
                preferences.active = true;
                tryCompare(preferences, "status", Loader.Ready);
                compare(Studio.Theme.zoomPercent, 80);
                preferences.active = false;
                wait(0);
                stored.setValue("zoomPercent", 999);
                stored.sync();
                preferences.active = true;
                tryCompare(preferences, "status", Loader.Ready);
                compare(Studio.Theme.zoomPercent, 100);
            }
        }
    }
}
