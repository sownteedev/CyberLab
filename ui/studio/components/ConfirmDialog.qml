import QtQuick
import QtQuick.Controls.Basic
import QtQuick.Layouts
import ".."
import ".." as Studio

Studio.StudioDialog {
    id: dialog

    property Item actionButton: null
    property Item cancelButton: null
    property bool confirmEnabled: true
    property string confirmText: "Xác nhận"
    property bool danger: false
    property string message: ""

    anchors.centerIn: parent
    closePolicy: Popup.CloseOnEscape
    contentHeight: Math.min(messageLabel.implicitHeight, Math.max(80, (parent ? parent.height : 640) - header.implicitHeight - footer.implicitHeight - padding * 2 - Studio.Theme.space32))
    focus: true
    font.family: Studio.Theme.fontFamily
    font.pixelSize: Studio.Theme.bodyMedium
    implicitHeight: header.implicitHeight + contentHeight + topPadding + bottomPadding + footer.implicitHeight
    modal: true
    padding: Studio.Theme.space24
    width: Math.min(480, parent ? parent.width - Studio.Theme.space32 : 480)

    contentItem: ScrollView {
        id: messageScroll

        clip: true
        contentWidth: availableWidth

        Label {
            id: messageLabel

            color: Studio.Theme.textOnSurfaceVariant
            font.pixelSize: Studio.Theme.bodyMedium
            text: dialog.message
            textFormat: Text.PlainText
            width: messageScroll.availableWidth
            wrapMode: Text.WrapAnywhere
        }
    }
    footer: RowLayout {
        spacing: Studio.Theme.space8

        Item {
            Layout.fillWidth: true
        }
        StudioButton {
            id: cancelBtn

            Layout.bottomMargin: Studio.Theme.space24
            flat: true
            objectName: "confirmCancelButton"
            text: "Hủy"

            Component.onCompleted: dialog.cancelButton = this
            onClicked: dialog.reject()
        }
        StudioButton {
            id: actionBtn

            Layout.bottomMargin: Studio.Theme.space24
            Layout.rightMargin: Studio.Theme.space24
            danger: dialog.danger
            enabled: dialog.confirmEnabled
            highlighted: !danger
            objectName: "confirmActionButton"
            text: dialog.confirmText

            Component.onCompleted: dialog.actionButton = this
            onClicked: dialog.accept()
        }
    }
    header: Label {
        bottomPadding: Studio.Theme.space16
        color: Studio.Theme.textOnSurface
        font.family: Studio.Theme.fontFamily
        font.pixelSize: Studio.Theme.titleLarge
        padding: Studio.Theme.space24
        text: dialog.title
        wrapMode: Text.WordWrap
    }

    onOpened: {
        if (dialog.parent && dialog.parent.Window.window)
            dialog.parent.Window.window.requestActivate();
        const target = (danger || (actionButton && !actionButton.enabled)) ? cancelButton : actionButton;
        if (target)
            target.forceActiveFocus(Qt.TabFocusReason);
    }
}
