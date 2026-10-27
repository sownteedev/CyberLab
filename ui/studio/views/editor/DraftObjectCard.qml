import QtQuick
import QtQuick.Controls
import QtQuick.Layouts
import "../.."
import "../.." as Studio

StudioCard {
    id: card

    required property string title
    required property string subtitle
    required property string detail
    property string iconName: "terminal"

    hoverable: true
    outlined: !selected
    implicitHeight: content.implicitHeight + Studio.Theme.space16 * 2
    opacity: enabled ? 1 : 0.6
    Accessible.role: Accessible.RadioButton
    Accessible.name: title
    Accessible.description: subtitle + ". " + detail
    Accessible.checkable: true
    Accessible.checked: selected

    ColumnLayout {
        id: content
        anchors.left: parent.left
        anchors.right: parent.right
        anchors.top: parent.top
        anchors.margins: Studio.Theme.space16
        spacing: Studio.Theme.space8

        RowLayout {
            Layout.fillWidth: true
            Label {
                Layout.fillWidth: true
                text: card.title
                textFormat: Text.PlainText
                color: card.selected ? Studio.Theme.textOnPrimaryContainer : Studio.Theme.textOnSurface
                font.pixelSize: Studio.Theme.titleMedium
                font.weight: Font.DemiBold
                elide: Text.ElideRight
            }
            Icon {
                name: card.selected ? "check_circle" : card.iconName
                Layout.preferredWidth: Studio.Theme.iconSize
                color: card.selected ? Studio.Theme.textOnPrimaryContainer : Studio.Theme.textOnSurfaceVariant
            }
        }
        Label {
            Layout.fillWidth: true
            text: card.subtitle
            textFormat: Text.PlainText
            color: card.selected ? Studio.Theme.textOnPrimaryContainer : Studio.Theme.textOnSurfaceVariant
            font.pixelSize: Studio.Theme.bodySmall
            elide: Text.ElideMiddle
        }
        Label {
            Layout.fillWidth: true
            text: card.detail
            textFormat: Text.PlainText
            color: card.selected ? Studio.Theme.textOnPrimaryContainer : Studio.Theme.textOnSurfaceVariant
            font.pixelSize: Studio.Theme.bodySmall
            elide: Text.ElideRight
        }
    }
}
