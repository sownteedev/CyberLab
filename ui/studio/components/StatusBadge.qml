import QtQuick
import QtQuick.Controls
import QtQuick.Layouts
import ".."
import ".." as Studio

Rectangle {
    id: badge
    property string text: ""
    property string description: text
    property string iconName: "check_circle"
    property color dotColor: Studio.Theme.success
    property color textColor: Studio.Theme.textOnSuccessContainer
    property color bgColor: Studio.Theme.successContainer
    property real maximumWidth: 360

    radius: Studio.Theme.shapeFull
    implicitHeight: Studio.Theme.badgeHeight
    implicitWidth: Math.min(maximumWidth, Math.ceil(badgeIcon.implicitWidth + badgeText.implicitWidth + Studio.Theme.space8 + Studio.Theme.space24))
    Accessible.role: Accessible.StaticText
    Accessible.name: text
    Accessible.description: description
    ToolTip.visible: hover.hovered && (badgeText.truncated || description !== text)
    ToolTip.delay: 600
    ToolTip.text: description
    HoverHandler { id: hover }
    color: bgColor
    border.width: Studio.Theme.borderWidth
    border.color: Studio.Theme.outlineVariant

    RowLayout {
        id: badgeRow
        anchors.fill: parent
        anchors.leftMargin: Studio.Theme.space12
        anchors.rightMargin: Studio.Theme.space12
        spacing: Studio.Theme.space8
        Icon {
            id: badgeIcon
            name: badge.iconName
            size: Studio.Theme.iconSmall
            Layout.alignment: Qt.AlignVCenter
            color: badge.dotColor
        }
        Label {
            id: badgeText
            Layout.fillWidth: true
            Layout.minimumWidth: 0
            Layout.alignment: Qt.AlignVCenter
            text: badge.text
            font.pixelSize: Studio.Theme.labelSmall
            font.weight: Font.Medium
            color: badge.textColor
            elide: Text.ElideRight
        }
    }
}
