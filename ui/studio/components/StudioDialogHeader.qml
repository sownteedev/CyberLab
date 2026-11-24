import QtQuick
import QtQuick.Controls.Basic
import QtQuick.Layouts
import ".." as Studio

Control {
    id: header

    readonly property alias closeButton: closeButton
    property string closeDescription: qsTr("Đóng hộp thoại")
    property string closeObjectName: "closeDialogButton"
    property string iconName: ""
    property string subtitle: ""
    property string title: ""

    signal closeRequested

    implicitHeight: implicitContentHeight + topPadding + bottomPadding
    padding: Studio.Theme.space24
    bottomPadding: Studio.Theme.space16
    objectName: "studioDialogHeader"

    contentItem: RowLayout {
        spacing: Studio.Theme.space16

        Rectangle {
            Layout.preferredWidth: Studio.Theme.controlHeight
            Layout.preferredHeight: Studio.Theme.controlHeight
            color: Studio.Theme.primaryContainer
            radius: Studio.Theme.shapeLargeIncreased
            visible: header.width >= 440 && header.iconName.length > 0

            Studio.Icon {
                anchors.centerIn: parent
                color: Studio.Theme.textOnPrimaryContainer
                name: header.iconName
            }
        }
        ColumnLayout {
            Layout.fillWidth: true
            Layout.minimumWidth: 0
            spacing: Studio.Theme.space4

            Label {
                Layout.fillWidth: true
                color: Studio.Theme.textOnSurface
                font.family: Studio.Theme.fontFamily
                font.pixelSize: Studio.Theme.headlineMedium
                font.weight: Font.DemiBold
                objectName: "dialogHeadline"
                text: header.title
                wrapMode: Text.WordWrap
            }
            Label {
                Layout.fillWidth: true
                color: Studio.Theme.textOnSurfaceVariant
                font.family: Studio.Theme.fontFamily
                font.pixelSize: Studio.Theme.bodyMedium
                text: header.subtitle
                visible: text.length > 0
                wrapMode: Text.WordWrap
            }
        }
        Studio.StudioIconButton {
            id: closeButton

            Layout.alignment: Qt.AlignTop
            description: header.closeDescription
            iconName: "close"
            objectName: header.closeObjectName

            onClicked: header.closeRequested()
        }
    }
}
