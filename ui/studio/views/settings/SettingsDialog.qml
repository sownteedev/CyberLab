import QtQuick
import QtQuick.Controls.Basic
import QtQuick.Layouts
import "../.."
import "../.." as Studio

Dialog {
    id: dialog
    objectName: "settingsDialog"
    property Item returnFocus: null
    parent: Overlay.overlay
    anchors.centerIn: parent
    width: Math.min(Studio.Theme.settingsWidth, parent ? parent.width - Studio.Theme.space32 : Studio.Theme.settingsWidth)
    height: Math.min(Studio.Theme.settingsHeight, parent ? parent.height - Studio.Theme.space32 : Studio.Theme.settingsHeight)
    padding: Studio.Theme.space24
    font.family: Studio.Theme.fontFamily
    font.pixelSize: Studio.Theme.bodyMedium
    modal: true
    focus: true
    closePolicy: Popup.CloseOnEscape | Popup.CloseOnPressOutside
    onOpened: appearance.focusSelection()
    onClosed: if (returnFocus) returnFocus.forceActiveFocus(Qt.TabFocusReason)
    background: Rectangle { radius: Studio.Theme.shapeExtraLarge; color: Studio.Theme.surfaceContainerHigh }
    Overlay.modal: Rectangle { color: Studio.Theme.scrim }
    enter: Transition {
        ParallelAnimation {
            NumberAnimation { property: "opacity"; from: 0; to: 1; duration: Studio.Theme.enterDuration }
            NumberAnimation { property: "scale"; from: 0.98; to: 1; duration: Studio.Theme.enterDuration; easing.type: Easing.OutCubic }
        }
    }
    exit: Transition { NumberAnimation { property: "opacity"; from: 1; to: 0; duration: Studio.Theme.exitDuration } }
    header: RowLayout {
        implicitHeight: Studio.Theme.appBarHeight
        spacing: Studio.Theme.space16
        Label {
            Layout.fillWidth: true
            Layout.leftMargin: Studio.Theme.space24
            text: "Cài đặt"
            color: Studio.Theme.textOnSurface
            font.pixelSize: Studio.Theme.titleLarge
            font.weight: Font.DemiBold
        }
        StudioIconButton {
            objectName: "closeSettingsButton"
            Layout.rightMargin: Studio.Theme.space16
            iconName: "close"
            description: "Đóng cài đặt"
            onClicked: dialog.close()
        }
    }
    contentItem: RowLayout {
        spacing: Studio.Theme.space24
        ColumnLayout {
            visible: dialog.width >= 640
            Layout.preferredWidth: 144
            Layout.maximumWidth: 144
            Layout.fillHeight: true
            StudioButton {
                Layout.fillWidth: true
                text: "Giao diện"
                iconName: "palette"
                selected: true
                leading: true
                onClicked: appearance.focusSelection()
            }
            Item { Layout.fillHeight: true }
            Label { text: "CyberLab Studio"; color: Studio.Theme.textOnSurfaceVariant; font.pixelSize: Studio.Theme.bodySmall }
        }
        ScrollView {
            id: appearanceScroll
            Layout.fillWidth: true
            Layout.fillHeight: true
            contentWidth: availableWidth
            clip: true
            AppearanceSettings {
                id: appearance
                width: appearanceScroll.availableWidth
                height: Math.max(implicitHeight, appearanceScroll.availableHeight)
                showPreview: appearanceScroll.availableHeight >= 440
            }
        }
    }
}
