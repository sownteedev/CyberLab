import QtQuick
import QtQuick.Controls
import QtQuick.Controls.Material
import Quickshell
import ".."
import ".." as Studio
import "../models/WindowMetrics.js" as WindowMetrics

ApplicationWindow {
    id: window
    required property var api
    required property var controller
    property bool smoke: false
    property bool allowClose: false
    readonly property var editor: content.editor
    readonly property var capture: content
    readonly property var appearanceLoader: settingsLoader
    readonly property bool confirmationOpened: windowDialogs.confirmationOpened
    readonly property var desktopGeometry: WindowMetrics.initialSize(Screen.width, Screen.height,
        Screen.desktopAvailableWidth, Screen.desktopAvailableHeight)

    width: smoke ? (Number(Quickshell.env("CYBERLAB_STUDIO_SMOKE_WIDTH")) || (Quickshell.env("CYBERLAB_STUDIO_SMOKE_COMPACT") === "1" ? 1024 : 1280)) : desktopGeometry.width
    height: smoke ? (Number(Quickshell.env("CYBERLAB_STUDIO_SMOKE_HEIGHT")) || (Quickshell.env("CYBERLAB_STUDIO_SMOKE_COMPACT") === "1" ? 700 : 820)) : desktopGeometry.height
    minimumWidth: smoke ? 0 : desktopGeometry.minimumWidth
    minimumHeight: smoke ? 0 : desktopGeometry.minimumHeight
    visible: true
    title: "CyberLab Studio" + (api.demo ? " — DEMO" : "")
    Material.theme: Studio.Theme.effectiveDark ? Material.Dark : Material.Light
    Material.accent: Studio.Theme.primary
    Material.primary: Studio.Theme.surface
    Material.foreground: Studio.Theme.textOnSurface
    Material.background: Studio.Theme.surfaceContainer
    font.family: Studio.Theme.fontFamily
    font.pixelSize: Studio.Theme.bodyMedium
    color: Studio.Theme.surface

    function navigate(index) {
        if (api.busy || index === controller.page) return;
        if (controller.page === 2 && editor.dirty) {
            windowDialogs.confirmNavigation(index);
            return;
        }
        showPage(index);
    }
    function showPage(index) {
        controller.manualGeneration += 1;
        controller.page = index;
        if (index === 0 && controller.selectedLab) controller.selectLab(controller.selectedLab);
        if (index === 1 && controller.selectedSession) controller.selectSession(controller.selectedSession);
        if (index === 2) editor.refresh();
    }
    function openSettings() {
        settingsLoader.returnFocus = activeFocusItem;
        settingsLoader.active = true;
    }

    onClosing: event => {
        if (!window.allowClose && (window.editor.dirty || window.api.busy)) {
            event.accepted = false;
            windowDialogs.confirmClose();
        }
    }
    Component.onCompleted: {
        if (smoke) Studio.Theme.themeMode = Quickshell.env("CYBERLAB_STUDIO_SMOKE_LIGHT") === "1" ? "light" : "dark";
        controller.refresh();
    }

    header: AppBar {
        heading: window.controller.page === 0 ? "Thư viện" : (window.controller.page === 1 ? "Thực hành" : "Tạo bài")
        subtitle: window.controller.page === 0 ? "Chọn một bài lab để bắt đầu thực hành"
            : (window.controller.page === 1 ? "Theo dõi phiên và tài nguyên đang chạy" : "Tạo một bài lab mới trong VM")
        connected: window.controller.connected
        demo: window.api.demo
        busy: window.api.busy
        activity: window.api.loading
        showCreate: window.controller.page !== 2
        onCreateRequested: window.navigate(2)
        onRefreshRequested: window.controller.refresh()
        onSettingsRequested: window.openSettings()
    }
    StudioContent {
        id: content
        anchors.fill: parent
        api: window.api
        controller: window.controller
        dialogs: windowDialogs
        onNavigationRequested: index => window.navigate(index)
        onShowPageRequested: index => window.showPage(index)
    }
    StudioDialogs {
        id: windowDialogs
        anchors.fill: parent
        api: window.api
        controller: window.controller
        editor: window.editor
        onNavigationConfirmed: index => window.showPage(index)
        onCloseConfirmed: { window.allowClose = true; window.close(); }
    }
    Loader {
        id: settingsLoader
        objectName: "settingsLoader"
        property Item returnFocus: null
        active: false
        sourceComponent: Component {
            SettingsDialog {
                returnFocus: settingsLoader.returnFocus
                onClosed: Qt.callLater(() => settingsLoader.active = false)
            }
        }
        onLoaded: if (status === Loader.Ready) item.open()
    }
}
