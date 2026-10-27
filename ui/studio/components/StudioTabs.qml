pragma ComponentBehavior: Bound

import QtQuick
import QtQuick.Controls.Basic
import QtQuick.Layouts
import ".." as Studio

TabBar {
    id: tabs
    property var entries: []
    property string itemPrefix: "tab-"
    readonly property bool overflowing: contentItem.contentWidth > width
    signal selected(int index)
    implicitHeight: Studio.Theme.controlHeight
    leftPadding: overflowing ? Studio.Theme.controlHeight : Studio.Theme.space4
    rightPadding: overflowing ? Studio.Theme.controlHeight : Studio.Theme.space4
    spacing: Studio.Theme.space4
    clip: true
    contentItem.clip: true
    background: Rectangle { radius: Studio.Theme.shapeMedium; color: Studio.Theme.surfaceContainer }
    function choose(index) {
        const next = Math.max(0, Math.min(count - 1, index));
        setCurrentIndex(next);
        selected(next);
        if (itemAt(next)) itemAt(next).forceActiveFocus(Qt.TabFocusReason);
    }
    property Studio.StudioIconButton previousButton: Studio.StudioIconButton {
        parent: tabs
        objectName: tabs.itemPrefix + "previous"
        anchors.left: parent.left
        anchors.verticalCenter: parent.verticalCenter
        visible: tabs.overflowing
        enabled: tabs.currentIndex > 0
        rotation: 180
        iconName: "chevron_right"
        description: "Mục trước"
        onClicked: tabs.choose(tabs.currentIndex - 1)
    }
    property Studio.StudioIconButton nextButton: Studio.StudioIconButton {
        parent: tabs
        objectName: tabs.itemPrefix + "next"
        anchors.right: parent.right
        anchors.verticalCenter: parent.verticalCenter
        visible: tabs.overflowing
        enabled: tabs.currentIndex < tabs.count - 1
        iconName: "chevron_right"
        description: "Mục tiếp theo"
        onClicked: tabs.choose(tabs.currentIndex + 1)
    }
    Repeater {
        model: tabs.entries
        TabButton {
            id: tab
            required property int index
            required property var modelData
            objectName: tabs.itemPrefix + index
            width: implicitWidth
            implicitWidth: Math.ceil(content.implicitWidth) + Studio.Theme.space24
            implicitHeight: Studio.Theme.controlHeight
            leftPadding: Studio.Theme.space12
            rightPadding: Studio.Theme.space12
            topPadding: Studio.Theme.space8
            bottomPadding: Studio.Theme.space8
            font.family: Studio.Theme.fontFamily
            font.pixelSize: Studio.Theme.labelLarge
            font.weight: checked ? Font.DemiBold : Font.Medium
            Accessible.name: modelData.label
            ToolTip.visible: hovered || visualFocus
            ToolTip.delay: 600
            ToolTip.text: modelData.label
            onClicked: tabs.selected(index)
            Keys.onLeftPressed: tabs.choose(index - 1)
            Keys.onRightPressed: tabs.choose(index + 1)
            Keys.onPressed: event => {
                if (event.key === Qt.Key_Home || event.key === Qt.Key_End) {
                    tabs.choose(event.key === Qt.Key_Home ? 0 : tabs.count - 1);
                    event.accepted = true;
                }
            }
            contentItem: RowLayout {
                id: content
                spacing: Studio.Theme.space8
                Studio.Icon {
                    name: tab.modelData.icon
                    size: Studio.Theme.iconSmall
                    color: tab.checked ? Studio.Theme.textOnPrimaryContainer : Studio.Theme.textOnSurfaceVariant
                }
                Text {
                    text: tab.modelData.label
                    font: tab.font
                    color: tab.checked ? Studio.Theme.textOnPrimaryContainer : Studio.Theme.textOnSurfaceVariant
                }
            }
            background: Rectangle {
                anchors.fill: parent
                anchors.margins: Studio.Theme.space4
                radius: Studio.Theme.shapeSmall
                color: tab.checked ? Studio.Theme.primaryContainer
                    : tab.hovered ? Studio.Theme.surfaceContainerHigh : Studio.Theme.transparent
                border.width: tab.visualFocus ? Studio.Theme.focusWidth : 0
                border.color: Studio.Theme.primary
            }
        }
    }
}
