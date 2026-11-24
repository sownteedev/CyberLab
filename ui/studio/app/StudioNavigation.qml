pragma ComponentBehavior: Bound

import QtQuick
import QtQuick.Controls.Basic
import QtQuick.Layouts
import ".." as Studio

Rectangle {
    id: navigation

    property int currentIndex: 0
    property bool ready: false
    property real selectionPosition: currentIndex
    readonly property real slotWidth: (width - Studio.Theme.space8) / 3
    signal indexRequested(int index)

    function focusItem(index) {
        const next = (index + destinations.count) % destinations.count;
        destinations.itemAt(next).forceActiveFocus(Qt.TabFocusReason);
    }

    Accessible.role: Accessible.PageTabList
    Accessible.name: "Điều hướng chính"
    color: Studio.Theme.surfaceContainer
    border.width: Studio.Theme.borderWidth
    border.color: Studio.Theme.outlineVariant
    radius: Studio.Theme.shapeFull
    implicitHeight: Studio.Theme.controlHeight
    implicitWidth: Studio.Theme.navigationItemWidth * 3 + Studio.Theme.space8
    objectName: "studioNavigation"

    Component.onCompleted: ready = true
    Behavior on selectionPosition {
        enabled: navigation.ready && !Studio.Theme.reducedMotion
        NumberAnimation { duration: 260; easing.type: Easing.OutCubic }
    }

    Rectangle {
        objectName: "navigationIndicator"
        x: Studio.Theme.space4 + navigation.selectionPosition * navigation.slotWidth
        y: Studio.Theme.space4
        width: navigation.slotWidth
        height: navigation.height - Studio.Theme.space8
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
            model: [
                { icon: "library_books", label: "Thư viện" },
                { icon: "terminal", label: "Thực hành" },
                { icon: "add", label: "Tạo bài" }
            ]

            Button {
                id: destination
                required property int index
                required property var modelData
                readonly property bool selected: index === navigation.currentIndex

                Layout.fillWidth: true
                Layout.minimumWidth: Studio.Theme.controlHeight
                Layout.preferredWidth: Studio.Theme.navigationItemWidth
                implicitHeight: Studio.Theme.controlHeight
                padding: Studio.Theme.space8
                focusPolicy: Qt.StrongFocus
                hoverEnabled: true
                objectName: "navigationItem-" + index
                Accessible.name: modelData.label
                Accessible.role: Accessible.PageTab
                Accessible.selected: selected

                background: Item {
                    Rectangle {
                        anchors.fill: parent
                        anchors.topMargin: Studio.Theme.space4
                        anchors.bottomMargin: Studio.Theme.space4
                        objectName: "navigationStateLayer"
                        radius: Studio.Theme.shapeFull
                        color: Studio.Theme.textOnSurface
                        opacity: !destination.enabled ? 0 : destination.down ? 0.12 : destination.hovered ? 0.08 : 0

                        Behavior on opacity {
                            NumberAnimation { duration: Studio.Theme.stateDuration; easing.type: Easing.OutCubic }
                        }
                    }
                    Rectangle {
                        anchors.fill: parent
                        anchors.topMargin: Studio.Theme.space4
                        anchors.bottomMargin: Studio.Theme.space4
                        radius: Studio.Theme.shapeFull
                        color: Studio.Theme.transparent
                        border.width: destination.visualFocus ? Studio.Theme.focusWidth : 0
                        border.color: Studio.Theme.primary
                    }
                }
                contentItem: RowLayout {
                    spacing: Studio.Theme.space8

                    Item { Layout.fillWidth: true }
                    Studio.Icon {
                        size: Studio.Theme.iconSmall
                        name: destination.modelData.icon
                        color: destination.selected ? Studio.Theme.textOnPrimaryContainer : Studio.Theme.textOnSurfaceVariant
                        visible: navigation.width >= Studio.Theme.navigationItemWidth * 3
                    }
                    Label {
                        text: destination.modelData.label
                        color: destination.selected ? Studio.Theme.textOnPrimaryContainer : Studio.Theme.textOnSurfaceVariant
                        font.family: Studio.Theme.fontFamily
                        font.pixelSize: Studio.Theme.labelLarge
                        font.weight: Font.DemiBold
                    }
                    Item { Layout.fillWidth: true }
                }

                Keys.onLeftPressed: navigation.focusItem(index - 1)
                Keys.onRightPressed: navigation.focusItem(index + 1)
                Keys.onPressed: event => {
                    if (event.key === Qt.Key_Home || event.key === Qt.Key_End) {
                        navigation.focusItem(event.key === Qt.Key_Home ? 0 : destinations.count - 1);
                        event.accepted = true;
                    }
                }
                onClicked: navigation.indexRequested(index)
            }
        }
    }
}
