import QtQuick
import QtQuick.Controls.Basic
import ".." as Studio

Item {
    id: viewport

    required property Window hostWindow
    readonly property Item popupOverlay: hostWindow.Overlay.overlay

    objectName: "studioViewport"
    width: parent.width / Studio.Theme.zoomFactor
    height: parent.height / Studio.Theme.zoomFactor
    scale: Studio.Theme.zoomFactor
    transformOrigin: Item.TopLeft

    Binding {
        target: viewport.popupOverlay
        property: "scale"
        value: Studio.Theme.zoomFactor
    }
    Binding {
        target: viewport.popupOverlay
        property: "transformOrigin"
        value: Item.TopLeft
    }
    Binding {
        target: viewport.popupOverlay
        property: "width"
        value: viewport.hostWindow.width / Studio.Theme.zoomFactor
        delayed: true
    }
    Binding {
        target: viewport.popupOverlay
        property: "height"
        value: viewport.hostWindow.height / Studio.Theme.zoomFactor
        delayed: true
    }
    Shortcut {
        sequences: ["Ctrl+-"]
        context: Qt.ApplicationShortcut
        enabled: viewport.hostWindow.active
        onActivated: Studio.Theme.setZoomPercent(Studio.Theme.zoomPercent - 10)
    }
    Shortcut {
        sequences: ["Ctrl++", "Ctrl+=", "Ctrl+Shift++", "Ctrl+Shift+="]
        context: Qt.ApplicationShortcut
        enabled: viewport.hostWindow.active
        onActivated: Studio.Theme.setZoomPercent(Studio.Theme.zoomPercent + 10)
    }
    Shortcut {
        sequence: "Ctrl+0"
        context: Qt.ApplicationShortcut
        enabled: viewport.hostWindow.active
        onActivated: Studio.Theme.setZoomPercent(100)
    }
}
