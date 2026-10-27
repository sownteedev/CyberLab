import QtQuick
import QtQuick.Controls.Basic
import QtQuick.Layouts
import ".."
import ".." as Studio

Dialog {
    id: dialog
    property string message: ""
    property string confirmText: "Xác nhận"
    property bool confirmEnabled: true
    property bool danger: false
    property Item cancelButton: null
    property Item actionButton: null
    font.family: Studio.Theme.fontFamily
    font.pixelSize: Studio.Theme.bodyMedium
    anchors.centerIn: parent
    modal: true
    focus: true
    closePolicy: Popup.CloseOnEscape
    onOpened: {
        if (dialog.parent && dialog.parent.Window.window) dialog.parent.Window.window.requestActivate();
        const target = (danger || (actionButton && !actionButton.enabled)) ? cancelButton : actionButton;
        if (target) target.forceActiveFocus(Qt.TabFocusReason);
    }
    width: Math.min(480, parent ? parent.width - Studio.Theme.space32 : 480)
    implicitHeight: header.implicitHeight + contentHeight + topPadding + bottomPadding + footer.implicitHeight
    contentHeight: Math.min(messageLabel.implicitHeight, Math.max(80,
        (parent ? parent.height : 640) - header.implicitHeight - footer.implicitHeight - padding * 2 - Studio.Theme.space32))
    padding: Studio.Theme.space24
    background: Rectangle {
        color: Studio.Theme.surfaceContainerHigh
        radius: Studio.Theme.shapeExtraLarge
    }
    Overlay.modal: Rectangle { color: Studio.Theme.scrim }
    enter: Transition { NumberAnimation { property: "opacity"; from: 0; to: 1; duration: Studio.Theme.enterDuration } }
    exit: Transition { NumberAnimation { property: "opacity"; to: 0; duration: Studio.Theme.exitDuration } }
    header: Label {
        text: dialog.title
        padding: Studio.Theme.space24
        bottomPadding: Studio.Theme.space16
        color: Studio.Theme.textOnSurface
        font.family: Studio.Theme.fontFamily
        font.pixelSize: Studio.Theme.titleLarge
        wrapMode: Text.WordWrap
    }
    contentItem: ScrollView {
        id: messageScroll
        contentWidth: availableWidth
        clip: true
        Label {
            id: messageLabel
            width: messageScroll.availableWidth
            text: dialog.message
            color: Studio.Theme.textOnSurfaceVariant
            wrapMode: Text.WrapAnywhere
            textFormat: Text.PlainText
            font.pixelSize: Studio.Theme.bodyMedium
        }
    }
    footer: RowLayout {
        spacing: Studio.Theme.space8
        Item { Layout.fillWidth: true }
        StudioButton {
            id: cancelBtn
            objectName: "confirmCancelButton"
            text: "Hủy"
            flat: true
            Layout.bottomMargin: Studio.Theme.space24
            onClicked: dialog.reject()
            Component.onCompleted: dialog.cancelButton = this
        }
        StudioButton {
            id: actionBtn
            objectName: "confirmActionButton"
            text: dialog.confirmText
            danger: dialog.danger
            highlighted: !danger
            enabled: dialog.confirmEnabled
            Layout.rightMargin: Studio.Theme.space24
            Layout.bottomMargin: Studio.Theme.space24
            onClicked: dialog.accept()
            Component.onCompleted: dialog.actionButton = this
        }
    }
}
