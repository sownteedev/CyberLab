import QtQuick
import QtQuick.Controls.Basic
import QtQuick.Layouts
import "../../.."
import "../../.." as Studio

Frame {
    id: card
    property string title: ""
    default property alias fields: fields.data
    signal removeRequested()
    padding: Studio.Theme.space12
    background: Rectangle { radius: Studio.Theme.shapeMedium; color: Studio.Theme.surfaceContainer }
    contentItem: ColumnLayout {
        spacing: Studio.Theme.space8
        RowLayout {
            Layout.fillWidth: true
            Label {
                Layout.fillWidth: true
                Layout.minimumWidth: 0
                text: card.title
                textFormat: Text.PlainText
                elide: Text.ElideRight
                font.pixelSize: Studio.Theme.titleSmall
                color: Studio.Theme.textOnSurface
            }
            StudioIconButton { iconName: "delete"; description: "Xóa " + card.title; onClicked: card.removeRequested() }
        }
        ColumnLayout { id: fields; Layout.fillWidth: true; spacing: Studio.Theme.space8 }
    }
}
