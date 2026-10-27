pragma ComponentBehavior: Bound

import QtQuick
import QtQuick.Controls.Basic
import QtQuick.Layouts
import ".."
import ".." as Studio

Rectangle {
    id: rail

    property int currentIndex: 0
    signal indexRequested(int index)

    implicitWidth: Studio.Theme.railWidth
    Layout.fillHeight: true
    radius: Studio.Theme.shapeExtraLarge
    color: Studio.Theme.surfaceContainer
    border.width: Studio.Theme.borderWidth
    border.color: Studio.Theme.outlineVariant

    ColumnLayout {
        anchors.fill: parent
        anchors.margins: Studio.Theme.space8
        spacing: Studio.Theme.space8

        Rectangle {
            Layout.alignment: Qt.AlignHCenter
            Layout.topMargin: Studio.Theme.space8
            Layout.bottomMargin: Studio.Theme.space12
            width: 48
            height: 48
            radius: Studio.Theme.shapeLarge
            color: Studio.Theme.surfaceContainerHigh
            border.width: Studio.Theme.borderWidth
            border.color: Studio.Theme.outlineVariant

            Icon {
                anchors.centerIn: parent
                name: "science"
                color: Studio.Theme.primary
                size: Studio.Theme.iconLarge
            }
        }

        Repeater {
            model: [
                { icon: "library_books", label: "Thư viện" },
                { icon: "terminal", label: "Thực hành" },
                { icon: "add", label: "Tạo bài" }
            ]

            delegate: Button {
                id: item
                required property int index
                required property var modelData
                objectName: "navigationItem-" + index

                Layout.fillWidth: true
                implicitHeight: Studio.Theme.rowHeight
                padding: 0
                flat: true
                Accessible.name: modelData.label
                Accessible.role: Accessible.PageTab
                Accessible.selected: item.index === rail.currentIndex
                ToolTip.visible: hovered || visualFocus
                ToolTip.delay: 600
                ToolTip.text: modelData.label
                focusPolicy: Qt.StrongFocus
                font.pixelSize: Studio.Theme.iconSize
                onClicked: rail.indexRequested(index)

                background: Rectangle {
                    radius: Studio.Theme.shapeLargeIncreased
                    border.width: item.visualFocus ? Studio.Theme.focusWidth : 0
                    border.color: Studio.Theme.primary
                    color: item.hovered && item.index !== rail.currentIndex ? Studio.Theme.surfaceContainerHigh : Studio.Theme.transparent
                }

                contentItem: ColumnLayout {
                    spacing: Studio.Theme.space4
                    Rectangle {
                        Layout.alignment: Qt.AlignHCenter
                        Layout.preferredWidth: 56
                        Layout.preferredHeight: 32
                        radius: Studio.Theme.shapeFull
                        color: item.index === rail.currentIndex ? Studio.Theme.primary : Studio.Theme.transparent
                        Icon {
                            anchors.centerIn: parent
                            name: item.modelData.icon
                            color: item.index === rail.currentIndex ? Studio.Theme.textOnPrimary : Studio.Theme.textOnSurfaceVariant
                        }
                    }
                    Label {
                        Layout.fillWidth: true
                        Layout.minimumWidth: 0
                        horizontalAlignment: Text.AlignHCenter
                        text: item.modelData.label
                        color: item.index === rail.currentIndex ? Studio.Theme.primary : Studio.Theme.textOnSurfaceVariant
                        font.pixelSize: Studio.Theme.labelSmall
                        font.weight: item.index === rail.currentIndex ? Font.DemiBold : Font.Normal
                        elide: Text.ElideRight
                    }
                }
            }
        }

        Item { Layout.fillHeight: true }

        Rectangle {
            Layout.alignment: Qt.AlignHCenter
            Layout.bottomMargin: Studio.Theme.space8
            width: 44
            height: 26
            radius: Studio.Theme.shapeFull
            color: Studio.Theme.surfaceContainerHigh
            border.width: Studio.Theme.borderWidth
            border.color: Studio.Theme.outlineVariant

            Label {
                anchors.centerIn: parent
                text: "VM"
                color: Studio.Theme.textOnSurfaceVariant
                font.pixelSize: Studio.Theme.labelSmall
                font.weight: Font.DemiBold
            }
        }
    }
}
