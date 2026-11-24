import QtQuick
import QtQuick.Controls.Basic
import QtQuick.Layouts
import "../../.."
import "../../.." as Studio

Frame {
    id: card

    default property alias fields: fields.data
    property string title: ""
    property int fieldColumns: 1
    property string fieldsObjectName: ""

    signal removeRequested

    padding: Studio.Theme.space16

    background: Rectangle {
        color: Studio.Theme.surfaceContainer
        radius: Studio.Theme.shapeLarge
        border.color: Studio.Theme.outlineVariant
        border.width: Studio.Theme.borderWidth
    }
    contentItem: ColumnLayout {
        spacing: Studio.Theme.space16

        RowLayout {
            Layout.fillWidth: true

            Label {
                Layout.fillWidth: true
                Layout.minimumWidth: 0
                color: Studio.Theme.textOnSurface
                elide: Text.ElideRight
                font.pixelSize: Studio.Theme.titleSmall
                text: card.title
                textFormat: Text.PlainText
            }
            StudioIconButton {
                description: "Xóa " + card.title
                iconName: "delete"

                onClicked: card.removeRequested()
            }
        }
        GridLayout {
            id: fields

            Layout.fillWidth: true
            columns: card.fieldColumns
            columnSpacing: Studio.Theme.space12
            rowSpacing: Studio.Theme.space8
            objectName: card.fieldsObjectName
        }
    }
}
