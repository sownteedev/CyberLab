import QtQuick
import QtQuick.Controls
import ".."
import ".." as Studio

Rectangle {
    id: errorView

    property string message: ""
    property bool dismissible: false
    signal dismissed()

    visible: message.length > 0
    implicitHeight: visible ? Math.max(label.implicitHeight + Studio.Theme.space32, Studio.Theme.rowHeight) : 0
    radius: Studio.Theme.shapeSmall
    color: Studio.Theme.errorContainer
    Icon {
        anchors.left: parent.left
        anchors.top: parent.top
        anchors.margins: Studio.Theme.space16
        name: "error"
        color: Studio.Theme.textOnErrorContainer
    }

    Label {
        id: label
        anchors.left: parent.left
        anchors.right: parent.right
        anchors.top: parent.top
        anchors.margins: Studio.Theme.space16
        anchors.leftMargin: Studio.Theme.controlHeight + Studio.Theme.space8
        anchors.rightMargin: errorView.dismissible ? Studio.Theme.controlHeight : Studio.Theme.space16
        text: errorView.message
        color: Studio.Theme.textOnErrorContainer
        font.pixelSize: Studio.Theme.bodySmall
        wrapMode: Text.WordWrap
        textFormat: Text.PlainText
    }
    StudioIconButton {
        anchors.right: parent.right
        anchors.top: parent.top
        visible: errorView.dismissible
        iconName: "close"
        description: "Đóng thông báo lỗi"
        danger: true
        onClicked: errorView.dismissed()
    }
}
