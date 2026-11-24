pragma ComponentBehavior: Bound

import QtQuick
import QtQuick.Controls.Basic
import QtQuick.Layouts
import "../.." as Studio

Studio.StudioCard {
    id: pane

    required property var editor
    property real maximumListHeight: 480
    signal focusRequested(Item target)

    objectName: "savedDraftsCard"
    color: Studio.Theme.surfaceContainerLow
    radius: Studio.Theme.shapeExtraLarge
    implicitHeight: content.implicitHeight + Studio.Theme.space24 * 2

    ColumnLayout {
        id: content

        anchors.fill: parent
        anchors.margins: Studio.Theme.space24
        spacing: Studio.Theme.space24

        RowLayout {
            Layout.fillWidth: true
            Layout.minimumHeight: Studio.Theme.controlHeight
            objectName: "savedDraftsHeader"
            spacing: Studio.Theme.space8

            Label {
                Layout.fillWidth: true
                color: Studio.Theme.textOnSurface
                font.pixelSize: Studio.Theme.titleMedium
                font.weight: Font.DemiBold
                text: qsTr("Bản nháp của bạn")
                wrapMode: Text.WordWrap
            }
            Label {
                color: Studio.Theme.textOnSurfaceVariant
                font.pixelSize: Studio.Theme.labelLarge
                horizontalAlignment: Text.AlignHCenter
                leftPadding: Studio.Theme.space12
                rightPadding: Studio.Theme.space12
                topPadding: Studio.Theme.space4
                bottomPadding: Studio.Theme.space4
                objectName: "savedDraftsCount"
                text: pane.editor.drafts.length
                background: Rectangle {
                    color: Studio.Theme.surfaceContainer
                    radius: Studio.Theme.shapeFull
                }
            }
            Studio.StudioIconButton {
                description: qsTr("Làm mới danh sách nháp")
                enabled: !pane.editor.backend.busy
                iconName: "refresh"
                objectName: "refreshDraftsButton"
                onClicked: pane.editor.refresh()
                onActiveFocusChanged: if (activeFocus) pane.focusRequested(this)
            }
        }
        Item {
            Layout.fillWidth: true
            Layout.fillHeight: true
            implicitHeight: emptyState.implicitHeight + Studio.Theme.space32 * 2
            objectName: "draftListEmpty"
            visible: pane.editor.drafts.length === 0

            Studio.EmptyState {
                id: emptyState

                anchors.centerIn: parent
                width: parent.width
                prominent: true
                iconName: "edit"
                title: qsTr("Chưa có bản nháp")
            }
        }
        ListView {
            id: draftsList

            Layout.fillWidth: true
            Layout.preferredHeight: Math.min(pane.maximumListHeight, contentHeight)
            Layout.fillHeight: true
            clip: true
            interactive: contentHeight > height
            model: pane.editor.drafts
            objectName: "savedDraftsList"
            spacing: Studio.Theme.space8
            visible: count > 0

            ScrollBar.vertical: ScrollBar { }
            delegate: ItemDelegate {
                id: draftRow

                required property int index
                required property var modelData

                Accessible.name: qsTr("Mở bản nháp %1").arg(modelData.name || modelData.lab_id || modelData.id)
                enabled: !pane.editor.dirty && !pane.editor.backend.busy
                focusPolicy: Qt.StrongFocus
                implicitHeight: Studio.Theme.controlHeight + Studio.Theme.space32
                objectName: "savedDraft-" + modelData.id
                padding: Studio.Theme.space16
                width: draftsList.width

                background: Rectangle {
                    border.color: draftRow.visualFocus ? Studio.Theme.primary : "transparent"
                    border.width: draftRow.visualFocus ? Studio.Theme.focusWidth : Studio.Theme.borderWidth
                    color: Studio.Theme.surfaceContainer
                    radius: Studio.Theme.shapeLarge

                    Rectangle {
                        anchors.fill: parent
                        color: Studio.Theme.textOnSurface
                        radius: parent.radius
                        opacity: !draftRow.enabled ? 0 : draftRow.down ? 0.12 : draftRow.hovered ? 0.08 : 0
                        Behavior on opacity {
                            NumberAnimation { duration: Studio.Theme.stateDuration }
                        }
                    }
                }
                contentItem: RowLayout {
                    spacing: Studio.Theme.space16
                    opacity: draftRow.enabled ? 1 : 0.5

                    Rectangle {
                        Layout.preferredHeight: Studio.Theme.controlHeight - Studio.Theme.space8
                        Layout.preferredWidth: Studio.Theme.controlHeight - Studio.Theme.space8
                        color: Studio.Theme.surfaceContainerHigh
                        radius: Studio.Theme.shapeMedium

                        Studio.Icon {
                            anchors.centerIn: parent
                            name: "description"
                            color: Studio.Theme.primary
                            size: Studio.Theme.iconSmall
                        }
                    }
                    ColumnLayout {
                        Layout.fillWidth: true
                        Layout.minimumWidth: 0
                        spacing: Studio.Theme.space4

                        Label {
                            Layout.fillWidth: true
                            Layout.minimumWidth: 0
                            color: Studio.Theme.textOnSurface
                            elide: Text.ElideRight
                            font.pixelSize: Studio.Theme.titleSmall
                            font.weight: Font.DemiBold
                            text: draftRow.modelData.name || draftRow.modelData.lab_id || qsTr("Bản nháp")
                            textFormat: Text.PlainText
                        }
                        Label {
                            Layout.fillWidth: true
                            Layout.minimumWidth: 0
                            color: Studio.Theme.textOnSurfaceVariant
                            elide: Text.ElideRight
                            font.pixelSize: Studio.Theme.bodySmall
                            text: (draftRow.modelData.lab_id || qsTr("Nháp")) + " · " + draftRow.modelData.id.substring(0, 8)
                                + " · r" + draftRow.modelData.revision
                            textFormat: Text.PlainText
                        }
                    }
                    Studio.Icon {
                        color: Studio.Theme.textOnSurfaceVariant
                        name: "chevron_right"
                        size: Studio.Theme.iconSmall
                    }
                }
                onClicked: pane.editor.openDraft(modelData.id)
                onActiveFocusChanged: if (activeFocus) {
                    draftsList.positionViewAtIndex(index, ListView.Contain);
                    pane.focusRequested(draftRow);
                }
            }
        }
    }
}
