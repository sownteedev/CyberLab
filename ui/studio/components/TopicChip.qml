import QtQuick
import ".." as Studio

Studio.StatusBadge {
    property string topicId: ""
    readonly property var appearance: Studio.TopicStyle.appearance(topicId)

    iconName: appearance.icon
    textColor: appearance.foreground
    dotColor: appearance.foreground
    bgColor: appearance.background
    border.color: Qt.alpha(textColor, 0.22)
}
