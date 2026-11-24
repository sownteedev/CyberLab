import QtQuick
import QtQuick.Controls.Basic
import QtQuick.Layouts
import "../.." as Studio

Frame {
    id: card

    default property alias fields: fields.data
    property string title: ""
    property string description: ""
    property string iconName: ""

    implicitWidth: 320
    padding: width < 400 ? Studio.Theme.space16 : Studio.Theme.space24
    background: Rectangle {
        color: Studio.Theme.surfaceContainerLow
        border.color: Studio.Theme.outlineVariant
        border.width: Studio.Theme.borderWidth
        radius: Studio.Theme.shapeExtraLarge
    }
    contentItem: ColumnLayout {
        spacing: Studio.Theme.space16

        RowLayout {
            Layout.fillWidth: true
            spacing: Studio.Theme.space12
            visible: card.title.length > 0

            Rectangle {
                Layout.preferredWidth: 40
                Layout.preferredHeight: 40
                radius: Studio.Theme.shapeLarge
                color: Studio.Theme.primaryContainer
                visible: card.iconName.length > 0
                Studio.Icon {
                    anchors.centerIn: parent
                    name: card.iconName
                    color: Studio.Theme.textOnPrimaryContainer
                    size: Studio.Theme.iconSmall
                }
            }
            ColumnLayout {
                Layout.fillWidth: true
                spacing: Studio.Theme.space4

                Label {
                    Layout.fillWidth: true
                    color: Studio.Theme.textOnSurface
                    font.pixelSize: Studio.Theme.titleMedium
                    font.weight: Font.DemiBold
                    text: card.title
                    textFormat: Text.PlainText
                    wrapMode: Text.WordWrap
                }
                Label {
                    Layout.fillWidth: true
                    color: Studio.Theme.textOnSurfaceVariant
                    font.pixelSize: Studio.Theme.bodySmall
                    text: card.description
                    textFormat: Text.PlainText
                    visible: text.length > 0
                    wrapMode: Text.WordWrap
                }
            }
        }
        ColumnLayout {
            id: fields
            Layout.fillWidth: true
            spacing: Studio.Theme.space16
        }
    }
}
