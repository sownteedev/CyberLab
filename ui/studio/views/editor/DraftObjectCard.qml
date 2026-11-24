import QtQuick
import QtQuick.Controls
import QtQuick.Layouts
import "../.."
import "../.." as Studio

StudioCard {
    id: card

    required property string detail
    property string iconName: "terminal"
    required property string subtitle
    required property string title

    Accessible.checkable: true
    Accessible.checked: selected
    Accessible.description: [subtitle, detail].filter(value => value.length > 0).join(". ")
    Accessible.name: title
    Accessible.role: Accessible.RadioButton
    hoverable: true
    implicitHeight: content.implicitHeight + Studio.Theme.space16 * 2
    opacity: enabled ? 1 : 0.6
    outlined: !selected
    color: selected ? Studio.Theme.primaryContainer : Studio.Theme.surfaceContainerLow
    radius: Studio.Theme.shapeLarge

    HoverHandler { id: cardHover; enabled: card.enabled }
    Rectangle {
        anchors.fill: parent
        radius: card.radius
        color: card.selected ? Studio.Theme.textOnPrimaryContainer : Studio.Theme.textOnSurface
        opacity: cardHover.hovered ? 0.08 : 0
    }
    ColumnLayout {
        id: content

        anchors.left: parent.left
        anchors.margins: Studio.Theme.space16
        anchors.right: parent.right
        anchors.top: parent.top
        spacing: Studio.Theme.space8

        RowLayout {
            Layout.fillWidth: true

            Label {
                Layout.fillWidth: true
                color: card.selected ? Studio.Theme.textOnPrimaryContainer : Studio.Theme.textOnSurface
                elide: Text.ElideRight
                font.pixelSize: Studio.Theme.titleMedium
                font.weight: Font.DemiBold
                text: card.title
                textFormat: Text.PlainText
            }
            Icon {
                Layout.preferredWidth: Studio.Theme.iconSize
                color: card.selected ? Studio.Theme.textOnPrimaryContainer : Studio.Theme.textOnSurfaceVariant
                name: card.selected ? "check_circle" : card.iconName
            }
        }
        Label {
            Layout.fillWidth: true
            color: card.selected ? Studio.Theme.textOnPrimaryContainer : Studio.Theme.textOnSurfaceVariant
            elide: Text.ElideMiddle
            font.pixelSize: Studio.Theme.bodySmall
            text: card.subtitle
            textFormat: Text.PlainText
            visible: text.length > 0
        }
        Label {
            Layout.fillWidth: true
            color: card.selected ? Studio.Theme.textOnPrimaryContainer : Studio.Theme.textOnSurfaceVariant
            elide: Text.ElideRight
            font.pixelSize: Studio.Theme.bodySmall
            text: card.detail
            textFormat: Text.PlainText
            visible: text.length > 0
        }
    }
}
