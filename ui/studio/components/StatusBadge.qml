import QtQuick
import QtQuick.Controls
import QtQuick.Layouts
import ".." as Studio

Rectangle {
    id: badge

    property color bgColor: Studio.Theme.successContainer
    property bool compact: false
    property string description: text
    property color dotColor: Studio.Theme.success
    property string iconName: "check_circle"
    property real iconSize: Studio.Theme.iconSmall
    property real maximumWidth: 360
    property string text: ""
    property color textColor: Studio.Theme.textOnSuccessContainer

    Accessible.description: description
    Accessible.name: text
    Accessible.role: Accessible.StaticText
    ToolTip.delay: 600
    ToolTip.text: description
    ToolTip.visible: hover.hovered && (compact || badgeText.truncated || description !== text)
    border.color: Studio.Theme.outlineVariant
    border.width: Studio.Theme.borderWidth
    color: bgColor
    implicitHeight: Studio.Theme.badgeHeight
    implicitWidth: compact ? implicitHeight : Math.min(maximumWidth, Math.ceil(badgeIcon.implicitWidth + badgeText.implicitWidth + Studio.Theme.space8 + Studio.Theme.space24))
    radius: Studio.Theme.shapeFull

    HoverHandler {
        id: hover
    }
    RowLayout {
        id: badgeRow

        anchors.fill: parent
        anchors.leftMargin: badge.compact ? Studio.Theme.space4 : Studio.Theme.space12
        anchors.rightMargin: badge.compact ? Studio.Theme.space4 : Studio.Theme.space12
        spacing: Studio.Theme.space8

        Studio.Icon {
            id: badgeIcon

            Layout.alignment: badge.compact ? Qt.AlignCenter : Qt.AlignVCenter
            color: badge.dotColor
            name: badge.iconName
            size: badge.iconSize
        }
        Label {
            id: badgeText

            Layout.alignment: Qt.AlignVCenter
            Layout.fillWidth: true
            Layout.minimumWidth: 0
            color: badge.textColor
            elide: Text.ElideRight
            font.pixelSize: Studio.Theme.labelSmall
            font.weight: Font.Medium
            text: badge.text
            visible: !badge.compact
        }
    }
}
