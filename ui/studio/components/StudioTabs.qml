pragma ComponentBehavior: Bound

import QtQuick
import QtQuick.Controls.Basic
import QtQuick.Layouts
import ".." as Studio

TabBar {
    id: tabs

    property var entries: []
    property string itemPrefix: "tab-"
    property Studio.StudioIconButton nextButton: Studio.StudioIconButton {
        anchors.right: parent.right
        anchors.verticalCenter: parent.verticalCenter
        description: "Mục tiếp theo"
        enabled: tabs.currentIndex < tabs.count - 1
        iconName: "chevron_right"
        objectName: tabs.itemPrefix + "next"
        parent: tabs
        visible: tabs.overflowing

        onClicked: tabs.choose(tabs.currentIndex + 1)
    }
    readonly property bool overflowing: contentItem.contentWidth > width
    property Studio.StudioIconButton previousButton: Studio.StudioIconButton {
        anchors.left: parent.left
        anchors.verticalCenter: parent.verticalCenter
        description: "Mục trước"
        enabled: tabs.currentIndex > 0
        iconName: "chevron_right"
        objectName: tabs.itemPrefix + "previous"
        parent: tabs
        rotation: 180
        visible: tabs.overflowing

        onClicked: tabs.choose(tabs.currentIndex - 1)
    }

    signal selected(int index)

    function choose(index) {
        const next = Math.max(0, Math.min(count - 1, index));
        setCurrentIndex(next);
        selected(next);
        if (itemAt(next))
            itemAt(next).forceActiveFocus(Qt.TabFocusReason);
    }

    clip: true
    contentItem.clip: true
    implicitHeight: Studio.Theme.controlHeight
    leftPadding: overflowing ? Studio.Theme.controlHeight : Studio.Theme.space4
    rightPadding: overflowing ? Studio.Theme.controlHeight : Studio.Theme.space4
    spacing: Studio.Theme.space4

    background: Rectangle {
        color: Studio.Theme.surfaceContainer
        radius: Studio.Theme.shapeMedium
    }

    Repeater {
        model: tabs.entries

        TabButton {
            id: tab

            required property int index
            required property var modelData

            Accessible.name: modelData.label
            ToolTip.delay: 600
            ToolTip.text: modelData.label
            ToolTip.visible: hovered || visualFocus
            bottomPadding: Studio.Theme.space8
            font.family: Studio.Theme.fontFamily
            font.pixelSize: Studio.Theme.labelLarge
            font.weight: checked ? Font.DemiBold : Font.Medium
            implicitHeight: Studio.Theme.controlHeight
            implicitWidth: Math.ceil(content.implicitWidth) + Studio.Theme.space24
            leftPadding: Studio.Theme.space12
            objectName: tabs.itemPrefix + index
            rightPadding: Studio.Theme.space12
            topPadding: Studio.Theme.space8
            width: implicitWidth

            background: Rectangle {
                anchors.fill: parent
                anchors.margins: Studio.Theme.space4
                border.color: Studio.Theme.primary
                border.width: tab.visualFocus ? Studio.Theme.focusWidth : 0
                color: tab.checked ? Studio.Theme.primaryContainer : tab.hovered ? Studio.Theme.surfaceContainerHigh : Studio.Theme.transparent
                radius: Studio.Theme.shapeSmall
            }
            contentItem: RowLayout {
                id: content

                spacing: Studio.Theme.space8

                Studio.Icon {
                    color: tab.checked ? Studio.Theme.textOnPrimaryContainer : Studio.Theme.textOnSurfaceVariant
                    name: tab.modelData.icon
                    size: Studio.Theme.iconSmall
                }
                Text {
                    color: tab.checked ? Studio.Theme.textOnPrimaryContainer : Studio.Theme.textOnSurfaceVariant
                    font: tab.font
                    text: tab.modelData.label
                }
            }

            Keys.onLeftPressed: tabs.choose(index - 1)
            Keys.onPressed: event => {
                if (event.key === Qt.Key_Home || event.key === Qt.Key_End) {
                    tabs.choose(event.key === Qt.Key_Home ? 0 : tabs.count - 1);
                    event.accepted = true;
                }
            }
            Keys.onRightPressed: tabs.choose(index + 1)
            onClicked: tabs.selected(index)
        }
    }
}
