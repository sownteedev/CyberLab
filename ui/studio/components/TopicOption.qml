import QtQuick
import QtQuick.Controls.Basic
import QtQuick.Layouts
import ".." as Studio

Studio.StudioButton {
    id: option

    property string topicId: ""
    readonly property var appearance: Studio.TopicStyle.appearance(topicId)

    iconName: appearance.icon
    implicitHeight: 56
    Accessible.role: Accessible.CheckBox
    Accessible.checkable: true
    Accessible.checked: selected

    background: Rectangle {
        anchors.fill: parent
        anchors.margins: Studio.Theme.space4
        radius: Studio.Theme.shapeMedium
        color: option.selected ? option.appearance.background : Studio.Theme.surfaceContainerHigh
        border.color: option.visualFocus ? Studio.Theme.primary : option.selected
            ? option.appearance.foreground : Studio.Theme.outlineVariant
        border.width: option.visualFocus ? Studio.Theme.focusWidth : Studio.Theme.borderWidth

        Rectangle {
            anchors.fill: parent
            radius: parent.radius
            color: option.appearance.foreground
            opacity: option.down ? 0.16 : option.hovered ? 0.08 : 0
        }
    }
    contentItem: RowLayout {
        spacing: Studio.Theme.space8
        Rectangle {
            Layout.preferredWidth: 30
            Layout.preferredHeight: 30
            radius: Studio.Theme.shapeSmall
            color: option.appearance.background
            Studio.Icon {
                anchors.centerIn: parent
                name: option.iconName
                color: option.appearance.foreground
                size: Studio.Theme.iconSmall
            }
        }
        Label {
            Layout.fillWidth: true
            Layout.minimumWidth: 0
            text: option.text
            textFormat: Text.PlainText
            color: option.selected ? option.appearance.foreground : Studio.Theme.textOnSurface
            font: option.font
            elide: Text.ElideRight
        }
        Studio.Icon {
            name: "check_circle"
            color: option.appearance.foreground
            size: Studio.Theme.iconSmall
            opacity: option.selected ? 1 : 0
        }
    }
}
