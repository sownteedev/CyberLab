pragma ComponentBehavior: Bound

import QtQuick
import QtQuick.Controls.Material
import QtQuick.Layouts
import "../.."
import "../.." as Studio

ScrollView {
    id: landing
    objectName: "draftLanding"
    required property var editor
    signal resumeRequested()
    clip: true
    contentWidth: availableWidth

    ColumnLayout {
        width: landing.availableWidth
        spacing: Studio.Theme.space16

        StudioButton {
            iconName: "arrow_back"; text: "Trở lại bài đang sửa"
            visible: !!landing.editor.draft
            flat: true
            enabled: !landing.editor.backend.busy
            onClicked: landing.resumeRequested()
        }

        GridLayout {
            Layout.fillWidth: true
            columns: width >= 800 ? 2 : 1
            columnSpacing: Studio.Theme.space24
            rowSpacing: Studio.Theme.space16

            StudioCard {
                objectName: "newDraftCard"
                Layout.fillWidth: true
                Layout.fillHeight: true
                Layout.preferredWidth: 420
                implicitHeight: createForm.implicitHeight + Studio.Theme.space24 * 2

                ColumnLayout {
                    id: createForm
                    anchors.left: parent.left
                    anchors.right: parent.right
                    anchors.top: parent.top
                    anchors.margins: Studio.Theme.space24
                    spacing: Studio.Theme.space16

                    SectionHeader {
                        Layout.fillWidth: true
                        title: "Tạo bài mới"
                        subtitle: "Bắt đầu với tên và mã bài."
                    }
                    ColumnLayout {
                        Layout.fillWidth: true
                        spacing: Studio.Theme.space8
                        Label {
                            text: "Tên bài"
                            color: Studio.Theme.textOnSurface
                            font.pixelSize: Studio.Theme.labelLarge
                        }
                        StudioTextField {
                            id: newTitle
                            objectName: "newDraftTitle"
                            Layout.fillWidth: true
                            placeholderText: "Ví dụ: Mạng cơ bản"
                            Accessible.name: "Tên bài mới"
                            enabled: !landing.editor.backend.busy
                            onAccepted: newId.forceActiveFocus(Qt.TabFocusReason)
                        }
                    }
                    ColumnLayout {
                        Layout.fillWidth: true
                        spacing: Studio.Theme.space8
                        Label {
                            text: "Mã bài"
                            color: Studio.Theme.textOnSurface
                            font.pixelSize: Studio.Theme.labelLarge
                        }
                        StudioTextField {
                            id: newId
                            objectName: "newDraftId"
                            Layout.fillWidth: true
                            placeholderText: "Ví dụ: mang-co-ban"
                            Accessible.name: "Mã bài mới"
                            enabled: !landing.editor.backend.busy
                            onAccepted: if (createButton.enabled) createButton.clicked()
                        }
                        Label {
                            Layout.fillWidth: true
                            text: "Mã dùng để nhận diện bài trong thư viện."
                            color: Studio.Theme.textOnSurfaceVariant
                            font.pixelSize: Studio.Theme.bodySmall
                            wrapMode: Text.WordWrap
                        }
                    }
                    StudioButton {
                        id: createButton
                        objectName: "createDraftButton"
                        Layout.fillWidth: true
                        iconName: "add"; text: "Tạo bản nháp"
                        highlighted: true
                        enabled: !!newId.text.trim() && !!newTitle.text.trim()
                            && !landing.editor.dirty && !landing.editor.backend.busy
                        onClicked: landing.editor.create(newId.text.trim(), newTitle.text.trim())
                    }
                    Label {
                        Layout.fillWidth: true
                        text: "Sau đó thêm máy, mạng, file và hướng dẫn."
                        color: Studio.Theme.textOnSurfaceVariant
                        font.pixelSize: Studio.Theme.bodySmall
                        wrapMode: Text.WordWrap
                    }
                }
            }

            StudioCard {
                objectName: "savedDraftsCard"
                Layout.fillWidth: true
                Layout.fillHeight: true
                Layout.preferredWidth: 540
                implicitHeight: draftsColumn.implicitHeight + Studio.Theme.space24 * 2

                ColumnLayout {
                    id: draftsColumn
                    anchors.fill: parent
                    anchors.margins: Studio.Theme.space24
                    spacing: Studio.Theme.space16

                    RowLayout {
                        Layout.fillWidth: true
                        Layout.maximumHeight: implicitHeight
                        SectionHeader {
                            Layout.fillWidth: true
                            title: "Bản nháp đã lưu"
                            subtitle: "Chọn một bài để tiếp tục chỉnh sửa."
                        }
                        StudioIconButton {
                            iconName: "refresh"
                            description: "Làm mới danh sách nháp"
                            enabled: !landing.editor.backend.busy
                            onClicked: landing.editor.refresh()
                        }
                    }
                    Item {
                        objectName: "draftListEmpty"
                        Layout.fillWidth: true
                        Layout.fillHeight: true
                        Layout.preferredHeight: 232
                        visible: landing.editor.drafts.length === 0
                        EmptyState {
                            anchors.centerIn: parent
                            width: parent.width
                            title: "Chưa có bản nháp"
                            description: "Bản nháp bạn tạo sẽ xuất hiện ở đây."
                        }
                    }
                    ListView {
                        id: draftsList
                        objectName: "savedDraftsList"
                        Layout.fillWidth: true
                        Layout.fillHeight: true
                        Layout.preferredHeight: Math.min(320, contentHeight)
                        visible: count > 0
                        clip: true
                        spacing: Studio.Theme.space8
                        model: landing.editor.drafts
                        ScrollBar.vertical: ScrollBar {}
                        delegate: ItemDelegate {
                            id: draftRow
                            required property var modelData
                            width: draftsList.width
                            implicitHeight: Studio.Theme.controlHeight + Studio.Theme.space24
                            padding: Studio.Theme.space16
                            enabled: !landing.editor.dirty && !landing.editor.backend.busy
                            Accessible.name: "Mở bản nháp " + (modelData.name || modelData.lab_id || modelData.id)
                            onClicked: landing.editor.openDraft(modelData.id)
                            background: Rectangle {
                                radius: Studio.Theme.shapeLarge
                                color: draftRow.hovered || draftRow.down ? Studio.Theme.secondaryContainer : Studio.Theme.surfaceContainerHigh
                                border.width: draftRow.visualFocus ? Studio.Theme.focusWidth : Studio.Theme.borderWidth
                                border.color: draftRow.visualFocus ? Studio.Theme.primary : Studio.Theme.outlineVariant
                            }
                            contentItem: RowLayout {
                                spacing: Studio.Theme.space12
                                Rectangle {
                                    Layout.preferredWidth: 40
                                    Layout.preferredHeight: 40
                                    radius: Studio.Theme.shapeMedium
                                    color: Studio.Theme.surfaceContainer
                                    border.width: Studio.Theme.borderWidth
                                    border.color: Studio.Theme.outlineVariant
                                    Icon {
                                        anchors.centerIn: parent
                                        name: "edit"
                                        size: Studio.Theme.iconSmall
                                        color: Studio.Theme.primary
                                    }
                                }
                                ColumnLayout {
                                    Layout.fillWidth: true
                                    spacing: 2
                                    Label {
                                        Layout.fillWidth: true
                                        text: draftRow.modelData.name || draftRow.modelData.lab_id || "Bản nháp"
                                        textFormat: Text.PlainText
                                        color: Studio.Theme.textOnSurface
                                        font.pixelSize: Studio.Theme.titleSmall
                                        font.weight: Font.DemiBold
                                        elide: Text.ElideRight
                                    }
                                    Label {
                                        Layout.fillWidth: true
                                        text: (draftRow.modelData.lab_id || "Nháp") + " · " + draftRow.modelData.id.substring(0, 8)
                                        textFormat: Text.PlainText
                                        color: Studio.Theme.textOnSurfaceVariant
                                        font.pixelSize: Studio.Theme.bodySmall
                                        elide: Text.ElideRight
                                    }
                                }
                                Icon {
                                    name: "chevron_right"
                                    size: Studio.Theme.iconSmall
                                    color: Studio.Theme.textOnSurfaceVariant
                                }
                            }
                        }
                    }
                }
            }
        }
    }
}
