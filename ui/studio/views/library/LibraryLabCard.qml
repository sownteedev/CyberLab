pragma ComponentBehavior: Bound

import QtQuick
import QtQuick.Controls.Basic
import QtQuick.Layouts
import "../.." as Studio

Studio.StudioSurface {
    id: card

    required property var lab
    property bool running: false
    readonly property color accent: Studio.Theme.primary

    objectName: "libraryLab-" + lab.id
    implicitHeight: content.implicitHeight + Studio.Theme.space24
    interactive: true
    color: selected ? Qt.tint(Studio.Theme.surfaceContainer, Qt.alpha(accent, 0.10))
        : hover.hovered ? Studio.Theme.surfaceContainerHigh : Studio.Theme.surfaceContainer
    border.color: activeFocus ? accent : selected ? Qt.alpha(accent, 0.65) : Studio.Theme.outlineVariant
    border.width: activeFocus || selected ? Studio.Theme.focusWidth : Studio.Theme.borderWidth
    radius: selected ? Studio.Theme.shapeExtraLarge : Studio.Theme.shapeLarge
    Behavior on radius { NumberAnimation { duration: Studio.Theme.spatialDuration; easing.type: Easing.OutCubic } }
    Behavior on color { ColorAnimation { duration: Studio.Theme.stateDuration } }
    Accessible.name: lab.name + ", " + lab.nodes.length + " máy, " + lab.networks.length + " mạng"
    Accessible.description: avatar.description + ", " + (lab.tags || []).map(tag => (lab.tag_labels || {})[tag] || tag).join(", ")
    ToolTip.delay: 700
    ToolTip.text: lab.name + "\n" + avatar.description + "\n" + lab.id + " · v" + lab.version
    ToolTip.visible: hover.hovered

    HoverHandler { id: hover }

    ColumnLayout {
        id: content
        anchors.fill: parent
        anchors.margins: Studio.Theme.space12
        spacing: Studio.Theme.space12

        RowLayout {
            Layout.fillWidth: true
            spacing: Studio.Theme.space12
            Studio.DifficultyChip {
                id: avatar
                objectName: "libraryDifficultyAvatar-" + card.lab.id
                Layout.alignment: Qt.AlignTop
                Layout.preferredWidth: 44
                Layout.preferredHeight: 44
                compact: true
                difficulty: card.lab.difficulty || ""
                iconName: card.running ? "terminal" : "science"
                iconSize: Studio.Theme.iconSize
                radius: width / 2
                border.width: 0
                ToolTip.visible: false
            }
            ColumnLayout {
                Layout.fillWidth: true
                Layout.minimumWidth: 0
                spacing: Studio.Theme.space4
                Label {
                    Layout.fillWidth: true
                    Layout.minimumWidth: 0
                    color: Studio.Theme.textOnSurface
                    font.family: Studio.Theme.fontFamily
                    font.pixelSize: Studio.Theme.titleSmall
                    font.weight: Font.DemiBold
                    text: card.lab.name
                    textFormat: Text.PlainText
                    elide: Text.ElideRight
                }
                Label {
                    Layout.fillWidth: true
                    Layout.minimumWidth: 0
                    color: Studio.Theme.textOnSurfaceVariant
                    font.pixelSize: Studio.Theme.bodySmall
                    text: card.lab.nodes.length + " máy · " + card.lab.networks.length + " mạng"
                    elide: Text.ElideRight
                }
            }
            Studio.Icon {
                Layout.alignment: Qt.AlignTop
                Layout.topMargin: Studio.Theme.space12
                name: card.running ? "play_arrow" : "chevron_right"
                color: card.running ? Studio.Theme.success : card.selected ? card.accent : Studio.Theme.textOnSurfaceVariant
                size: 16
            }
        }
        Flow {
            id: topics
            objectName: "libraryCardTopics"
            Layout.fillWidth: true
            Layout.preferredHeight: childrenRect.height
            spacing: Studio.Theme.space8
            visible: (card.lab.tags || []).length > 0
            Repeater {
                model: (card.lab.tags || []).slice(0, 2)
                delegate: Studio.TopicChip {
                    required property string modelData
                    objectName: "libraryRowTopic-" + card.lab.id + "-" + modelData
                    topicId: modelData
                    text: (card.lab.tag_labels || {})[modelData] || modelData
                    maximumWidth: topics.width
                    radius: Studio.Theme.shapeSmall
                }
            }
            Label {
                height: Studio.Theme.badgeHeight
                verticalAlignment: Text.AlignVCenter
                color: Studio.Theme.textOnSurfaceVariant
                font.pixelSize: Studio.Theme.labelSmall
                text: "+" + ((card.lab.tags || []).length - 2)
                visible: (card.lab.tags || []).length > 2
            }
        }
    }
}
