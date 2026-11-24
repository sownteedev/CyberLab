import QtQuick
import QtQuick.Controls
import QtQuick.Layouts
import ".."
import ".." as Studio

Item {
    id: empty

    property string actionText: ""
    property bool compact: false
    property string description: ""
    property string iconName: "inventory_2"
    property bool prominent: false
    property string title: ""

    signal actionRequested

    Layout.alignment: Qt.AlignCenter
    implicitHeight: content.implicitHeight
    implicitWidth: content.implicitWidth

    ColumnLayout {
        id: content

        anchors.centerIn: parent
        objectName: "emptyStateContent"
        spacing: Studio.Theme.space8
        width: Math.min(Math.max(0, empty.width - Studio.Theme.space32), 420)

        Rectangle {
            Layout.alignment: Qt.AlignHCenter
            Layout.preferredHeight: empty.prominent ? 72 : Studio.Theme.iconLarge
            Layout.preferredWidth: empty.prominent ? 72 : Studio.Theme.iconLarge
            Layout.bottomMargin: empty.prominent ? Studio.Theme.space8 : 0
            color: empty.prominent ? Studio.Theme.primaryContainer : Studio.Theme.transparent
            radius: Studio.Theme.shapeExtraLarge
            visible: !empty.compact

            Icon {
                anchors.centerIn: parent
                color: empty.prominent ? Studio.Theme.textOnPrimaryContainer : Studio.Theme.primary
                name: empty.iconName
                size: empty.prominent ? 32 : Studio.Theme.iconLarge
            }
        }
        Label {
            Layout.fillWidth: true
            color: Studio.Theme.textOnSurface
            font.pixelSize: Studio.Theme.titleMedium
            font.weight: Font.DemiBold
            horizontalAlignment: Text.AlignHCenter
            text: empty.title
            wrapMode: Text.WordWrap
        }
        Label {
            Layout.fillWidth: true
            color: Studio.Theme.textOnSurfaceVariant
            font.pixelSize: Studio.Theme.bodyMedium
            horizontalAlignment: Text.AlignHCenter
            text: empty.description
            visible: empty.description.length > 0 && !empty.compact
            wrapMode: Text.WordWrap
        }
        StudioButton {
            Layout.alignment: Qt.AlignHCenter
            highlighted: true
            text: empty.actionText
            visible: empty.actionText.length > 0

            onClicked: empty.actionRequested()
        }
    }
}
