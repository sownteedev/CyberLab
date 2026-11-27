import QtQuick
import QtQuick.Controls
import QtQuick.Controls.Material
import Quickshell
import ".."
import ".." as Studio
import "../models/WindowMetrics.js" as WindowMetrics
import "../views/editor" as Editing

ApplicationWindow {
    id: window

    property bool allowClose: false
    signal closeAccepted
    required property var api
    readonly property var appearanceLoader: settingsLoader
    readonly property var capture: content
    readonly property bool confirmationOpened: windowDialogs.confirmationOpened
    required property var controller
    readonly property var desktopGeometry: WindowMetrics.initialSize(Screen.width, Screen.height, Screen.desktopAvailableWidth, Screen.desktopAvailableHeight)
    readonly property var editor: content.editor
    property bool smoke: false
    property int settingsSection: 0

    Studio.SystemUpdateService {
        id: systemUpdater
        automatic: !window.smoke && window.api.demo === false && !!window.api.prefix
        prefix: window.api.prefix || [Quickshell.env("CYBERLAB_STUDIO_PYTHON") || "/usr/bin/python3", "-m", "cyberlab_cli.main"]
        onNewVersion: window.api.notificationRequested(qsTr("Có bản CyberLab mới. Mở Cài đặt → Cập nhật để xem."), false)
        onErrorOccurred: message => window.api.reportError(message)
        onHandoffReady: {
            if (window.editor.dirty || window.api.busy || window.api.starting) {
                window.api.reportError(qsTr("Studio có thay đổi mới nên chưa đóng. Cửa sổ cập nhật sẽ chờ; hãy lưu nội dung trước."));
                return;
            }
            window.allowClose = true;
            window.close();
        }
    }
    function canUpdate() {
        if (editor.dirty) {
            api.reportError(qsTr("Hãy lưu hoặc bỏ thay đổi đang sửa trước khi cập nhật."));
            return false;
        }
        if (api.busy || api.starting || controller.sessions.some(session => session.state !== "STOPPED")) {
            api.reportError(qsTr("Hãy đợi thao tác hoàn tất và dừng các phiên thực hành trước khi cập nhật."));
            return false;
        }
        return true;
    }
    Studio.ConfirmDialog {
        id: updateConfirmation
        title: qsTr("Cập nhật CyberLab?")
        message: qsTr("Studio sẽ đóng và mở cửa sổ cập nhật riêng. Khi hoàn tất, chọn Khởi động lại CyberLab. Các bài đã lưu được giữ nguyên.")
        confirmText: qsTr("Tiếp tục cập nhật")
        confirmEnabled: !systemUpdater.handingOff
        onAccepted: if (window.canUpdate()) systemUpdater.begin()
    }

    Connections {
        target: window.controller
        function onPageChanged() {
            if (window.controller.page !== 2 && window.api.clearEditing) window.api.clearEditing();
        }
    }
    Editing.EditPasswordDialog {
        id: editPassword
        api: window.api
    }
    Connections {
        target: window.api
        ignoreUnknownSignals: true
        function onEditUnlockRequested(kind, identifier, message) { editPassword.showUnlock(kind, identifier, message); }
        function onEditUnlockDismissed() { editPassword.close(); }
    }

    function navigate(index) {
        if (api.busy || index === controller.page)
            return;
        if (controller.page === 2 && editor.dirty) {
            windowDialogs.confirmNavigation(index);
            return;
        }
        showPage(index);
    }
    function openSettings(section = 0) {
        settingsSection = section;
        settingsLoader.returnFocus = activeFocusItem;
        settingsLoader.active = true;
    }
    function showPage(index) {
        controller.manualGeneration += 1;
        controller.page = index;
        if (index === 0 && controller.selectedLab)
            controller.selectLab(controller.selectedLab);
        if (index === 1 && controller.selectedSession)
            controller.selectSession(controller.selectedSession);
        if (index === 2)
            editor.refresh();
    }

    Material.accent: Studio.Theme.primary
    Material.background: Studio.Theme.surfaceContainer
    Material.foreground: Studio.Theme.textOnSurface
    Material.primary: Studio.Theme.surface
    Material.theme: Studio.Theme.effectiveDark ? Material.Dark : Material.Light
    color: Studio.Theme.surface
    palette: Studio.Theme.controlPalette
    font.family: Studio.Theme.fontFamily
    font.pixelSize: Studio.Theme.bodyMedium
    flags: Qt.Window | Qt.FramelessWindowHint
    height: smoke ? (Number(Quickshell.env("CYBERLAB_STUDIO_SMOKE_HEIGHT")) || (Quickshell.env("CYBERLAB_STUDIO_SMOKE_COMPACT") === "1" ? 700 : 820)) : desktopGeometry.height
    minimumHeight: smoke ? 0 : desktopGeometry.minimumHeight
    minimumWidth: smoke ? 0 : desktopGeometry.minimumWidth
    title: "CyberLab Studio" + (api.demo ? " — DEMO" : "")
    visible: true
    width: smoke ? (Number(Quickshell.env("CYBERLAB_STUDIO_SMOKE_WIDTH")) || (Quickshell.env("CYBERLAB_STUDIO_SMOKE_COMPACT") === "1" ? 1024 : 1280)) : desktopGeometry.width

    header: Item {
        implicitHeight: appBar.implicitHeight * Studio.Theme.zoomFactor

        AppBar {
            id: appBar
            enabled: !systemUpdater.handingOff
            width: parent.width / Studio.Theme.zoomFactor
            scale: Studio.Theme.zoomFactor
            transformOrigin: Item.TopLeft
            activity: window.api.loading
            busy: window.api.busy
            connected: window.controller.connected
            currentIndex: window.controller.page
            demo: window.api.demo
            updateAvailable: systemUpdater.available
            windowMaximized: window.visibility === Window.Maximized

            onCloseRequested: window.close()
            onMinimizeRequested: window.showMinimized()
            onMoveRequested: window.startSystemMove()
            onNavigationRequested: index => window.navigate(index)
            onMaximizeRequested: {
                if (window.visibility === Window.Maximized)
                    window.showNormal();
                else
                    window.showMaximized();
            }
            onRefreshRequested: window.controller.refresh()
            onSettingsRequested: window.openSettings(systemUpdater.available ? 4 : 0)
        }
    }

    Component.onCompleted: {
        if (smoke)
            Studio.Theme.themeMode = Quickshell.env("CYBERLAB_STUDIO_SMOKE_LIGHT") === "1" ? "light" : "dark";
        controller.refresh();
    }
    onClosing: event => {
        if (systemUpdater.handingOff) {
            event.accepted = false;
        } else if (!window.allowClose && (window.editor.dirty || window.api.busy || window.api.starting)) {
            event.accepted = false;
            windowDialogs.confirmClose();
        } else {
            window.closeAccepted();
        }
    }

    WindowResizeHandles {
        parent: window.contentItem
        y: -window.header.height
        width: window.width
        height: window.height
        z: 100
        enabled: window.visibility === Window.Windowed
        onResizeRequested: edges => window.startSystemResize(edges)
    }

    StudioViewport {
        hostWindow: window

        StudioContent {
            id: content

            anchors.fill: parent
            api: window.api
            controller: window.controller
            enabled: !systemUpdater.handingOff
            dialogs: windowDialogs

            onShowPageRequested: index => window.showPage(index)
        }
        StudioDialogs {
            id: windowDialogs

            anchors.fill: parent
            api: window.api
            controller: window.controller
            editor: window.editor

            onCloseConfirmed: {
                window.allowClose = true;
                window.close();
            }
            onNavigationConfirmed: index => window.showPage(index)
        }
        Loader {
            id: settingsLoader

            property Item returnFocus: null

            active: false
            objectName: "settingsLoader"

            sourceComponent: Component {
                SettingsDialog {
                    sectionIndex: window.settingsSection
                    updater: systemUpdater
                    onUpdateRequested: if (window.canUpdate()) updateConfirmation.open()
                    returnFocus: settingsLoader.returnFocus
                    terminals: terminalStore
                    guiPreferences: guiStore

                    onClosed: Qt.callLater(() => settingsLoader.active = false)
                }
            }

            onLoaded: if (status === Loader.Ready)
                item.open()
        }
        TerminalPreferences {
            id: terminalStore

            backend: window.api
        }
        GuiPreferences {
            id: guiStore

            backend: window.api
        }
        Studio.StudioNotifications {
            parent: window.Overlay.overlay
            anchors.right: parent.right
            anchors.top: parent.top
            anchors.margins: Studio.Theme.space16
            width: Math.min(440, parent.width - Studio.Theme.space32)
            availableHeight: parent.height - Studio.Theme.space32
            windowActive: window.active
            api: window.api
            z: 1000
        }
    }
}
