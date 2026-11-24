pragma ComponentBehavior: Bound

import QtQuick
import QtQuick.Controls.Basic
import QtQuick.Layouts
import ".." as Studio

Rectangle {
    id: tabs

    property var entries: []
    property string itemPrefix: "tab-"
    property int currentIndex: 0
    property bool ready: false
    property real selectionPosition: currentIndex
    readonly property real slotWidth: entries.length > 0 ? (width - Studio.Theme.space8) / entries.length : 0

    signal selected(int index)

    function choose(index) {
        const next = Math.max(0, Math.min(entries.length - 1, index));
        if (next < 0)
            return;
        selected(next);
        const target = destinations.itemAt(next);
        if (target)
            target.forceActiveFocus(Qt.TabFocusReason);
    }

    Accessible.name: "Các mục cài đặt"
    Accessible.role: Accessible.PageTabList
    color: Studio.Theme.surfaceContainer
    border.color: Studio.Theme.outlineVariant
    border.width: Studio.Theme.borderWidth
    radius: Studio.Theme.shapeFull
    implicitHeight: Studio.Theme.controlHeight
    implicitWidth: Math.max(Studio.Theme.controlHeight * entries.length + Studio.Theme.space8, Studio.Theme.navigationItemWidth * entries.length + Studio.Theme.space8)
    objectName: "studioSegmentedTabs"

    Component.onCompleted: ready = true

    Behavior on selectionPosition {
        enabled: tabs.ready && !Studio.Theme.reducedMotion

        NumberAnimation {
            duration: 260
            easing.type: Easing.OutCubic
        }
    }

    Rectangle {
        id: indicator

        objectName: tabs.itemPrefix + "indicator"
        x: Studio.Theme.space4 + tabs.selectionPosition * tabs.slotWidth
        y: Studio.Theme.space4
        width: tabs.slotWidth
        height: tabs.height - Studio.Theme.space8
        radius: Studio.Theme.shapeFull
        color: Studio.Theme.primaryContainer
    }

    RowLayout {
        anchors.fill: parent
        anchors.leftMargin: Studio.Theme.space4
        anchors.rightMargin: Studio.Theme.space4
        spacing: 0

        Repeater {
            id: destinations

            model: tabs.entries

            Button {
                id: destination

                required property int index
                required property var modelData
                readonly property bool selected: index === tabs.currentIndex

                Layout.fillWidth: true
                Layout.minimumWidth: Studio.Theme.controlHeight
                Layout.preferredWidth: tabs.slotWidth
                implicitHeight: Studio.Theme.controlHeight
                Accessible.name: modelData.label
                Accessible.role: Accessible.PageTab
                Accessible.selected: selected
                focusPolicy: Qt.StrongFocus
                hoverEnabled: true
                objectName: tabs.itemPrefix + index
                padding: Studio.Theme.space8

                background: Item {
                    Rectangle {
                        anchors.fill: parent
                        anchors.topMargin: Studio.Theme.space4
                        anchors.bottomMargin: Studio.Theme.space4
                        objectName: "segmentedStateLayer"
                        radius: Studio.Theme.shapeFull
                        color: Studio.Theme.textOnSurface
                        opacity: !destination.enabled ? 0 : destination.down ? 0.12 : destination.hovered ? 0.08 : 0

                        Behavior on opacity {
                            NumberAnimation {
                                duration: Studio.Theme.stateDuration
                                easing.type: Easing.OutCubic
                            }
                        }
                    }
                    Rectangle {
                        anchors.fill: parent
                        anchors.topMargin: Studio.Theme.space4
                        anchors.bottomMargin: Studio.Theme.space4
                        color: Studio.Theme.transparent
                        radius: Studio.Theme.shapeFull
                        border.color: Studio.Theme.primary
                        border.width: destination.visualFocus ? Studio.Theme.focusWidth : 0
                    }
                }
                contentItem: RowLayout {
                    spacing: Studio.Theme.space8

                    Item { Layout.fillWidth: true }
                    Studio.Icon {
                        color: destination.selected ? Studio.Theme.textOnPrimaryContainer : Studio.Theme.textOnSurfaceVariant
                        name: destination.modelData.icon
                        size: Studio.Theme.iconSmall
                    }
                    Label {
                        color: destination.selected ? Studio.Theme.textOnPrimaryContainer : Studio.Theme.textOnSurfaceVariant
                        font.family: Studio.Theme.fontFamily
                        font.pixelSize: Studio.Theme.labelLarge
                        font.weight: Font.DemiBold
                        text: destination.modelData.label
                    }
                    Item { Layout.fillWidth: true }
                }

                Keys.onLeftPressed: tabs.choose(index - 1)
                Keys.onRightPressed: tabs.choose(index + 1)
                Keys.onPressed: event => {
                    if (event.key === Qt.Key_Home || event.key === Qt.Key_End) {
                        tabs.choose(event.key === Qt.Key_Home ? 0 : tabs.entries.length - 1);
                        event.accepted = true;
                    }
                }
                onClicked: tabs.choose(index)
            }
        }
    }
}
