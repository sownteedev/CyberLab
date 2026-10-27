import QtQuick
import QtQuick.Controls
import QtQuick.Layouts
import ".."
import ".." as Studio

Item {
    id: empty

    property string title: ""
    property string description: ""
    property string actionText: ""
    signal actionRequested()

    Layout.alignment: Qt.AlignCenter
    implicitWidth: content.implicitWidth
    implicitHeight: content.implicitHeight

    ColumnLayout {
        id: content
        objectName: "emptyStateContent"
        anchors.centerIn: parent
        width: Math.min(Math.max(0, empty.width - Studio.Theme.space32), 420)
        spacing: Studio.Theme.space8

        Icon {
            Layout.alignment: Qt.AlignHCenter
            name: "inventory_2"
            size: Studio.Theme.iconLarge
            color: Studio.Theme.primary
        }
        Label {
            Layout.fillWidth: true
            text: empty.title
            color: Studio.Theme.textOnSurface
            font.pixelSize: Studio.Theme.titleMedium
            font.weight: Font.DemiBold
            horizontalAlignment: Text.AlignHCenter
        }
        Label {
            Layout.fillWidth: true
            visible: empty.description.length > 0
            text: empty.description
            color: Studio.Theme.textOnSurfaceVariant
            font.pixelSize: Studio.Theme.bodyMedium
            horizontalAlignment: Text.AlignHCenter
            wrapMode: Text.WordWrap
        }
        StudioButton {
            Layout.alignment: Qt.AlignHCenter
            visible: empty.actionText.length > 0
            text: empty.actionText
            highlighted: true
            onClicked: empty.actionRequested()
        }
    }
}
