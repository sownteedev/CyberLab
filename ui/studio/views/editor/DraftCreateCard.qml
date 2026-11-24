pragma ComponentBehavior: Bound

import QtQuick
import QtQuick.Controls.Basic
import QtQuick.Layouts
import "../.." as Studio

Studio.StudioCard {
    id: card

    required property var editor
    signal focusRequested(Item target)

    color: Studio.Theme.surfaceContainerLow
    implicitHeight: form.implicitHeight + Studio.Theme.space24 * 2
    objectName: "newDraftCard"
    radius: Studio.Theme.shapeExtraLarge

    ColumnLayout {
        id: form

        anchors.fill: parent
        anchors.margins: Studio.Theme.space24
        spacing: Studio.Theme.space16

        RowLayout {
            Layout.fillWidth: true
            Layout.bottomMargin: Studio.Theme.space8
            Layout.minimumHeight: Studio.Theme.controlHeight
            objectName: "newDraftHeader"
            spacing: Studio.Theme.space12

            Rectangle {
                Layout.preferredWidth: Studio.Theme.controlHeight
                Layout.preferredHeight: Studio.Theme.controlHeight
                color: Studio.Theme.primaryContainer
                radius: Studio.Theme.shapeLarge

                Studio.Icon {
                    anchors.centerIn: parent
                    name: "add"
                    color: Studio.Theme.textOnPrimaryContainer
                }
            }
            Label {
                Layout.fillWidth: true
                color: Studio.Theme.textOnSurface
                font.pixelSize: Studio.Theme.titleMedium
                font.weight: Font.DemiBold
                text: qsTr("Tạo bài mới")
                wrapMode: Text.WordWrap
            }
        }
        ColumnLayout {
            Layout.fillWidth: true
            spacing: Studio.Theme.space8

            Label {
                color: Studio.Theme.textOnSurface
                font.pixelSize: Studio.Theme.labelLarge
                text: qsTr("Tên bài")
            }
            Studio.StudioTextField {
                id: newTitle

                Layout.fillWidth: true
                Accessible.name: qsTr("Tên bài mới")
                enabled: !card.editor.backend.busy
                objectName: "newDraftTitle"
                placeholderText: qsTr("Ví dụ: Mạng cơ bản")
                onAccepted: newId.forceActiveFocus(Qt.TabFocusReason)
                onActiveFocusChanged: if (activeFocus) card.focusRequested(newTitle)
            }
        }
        ColumnLayout {
            Layout.fillWidth: true
            spacing: Studio.Theme.space8

            Label {
                color: Studio.Theme.textOnSurface
                font.pixelSize: Studio.Theme.labelLarge
                text: qsTr("Mã bài")
            }
            Studio.StudioTextField {
                id: newId

                Layout.fillWidth: true
                Accessible.name: qsTr("Mã bài mới")
                enabled: !card.editor.backend.busy
                objectName: "newDraftId"
                placeholderText: qsTr("Ví dụ: mang-co-ban")
                onAccepted: if (createButton.enabled) createButton.clicked()
                onActiveFocusChanged: if (activeFocus) card.focusRequested(newId)
            }
        }
        ColumnLayout {
            Layout.fillWidth: true
            spacing: Studio.Theme.space8
            Label { text: qsTr("Chủ đề *"); color: Studio.Theme.textOnSurface; font.pixelSize: Studio.Theme.labelLarge }
            Studio.TopicPicker {
                id: topics
                Layout.fillWidth: true
                Layout.minimumWidth: 0
                objectName: "newDraftTopics"
                options: card.editor.policy ? card.editor.policy.topic_catalog || [] : []
                requiredSelection: true
                enabled: options.length > 0 && !card.editor.backend.busy && !card.editor.dirty
                onEdited: tags => selectedTags = tags
                onActiveFocusChanged: if (activeFocus) card.focusRequested(topics)
            }
        }
        ColumnLayout {
            Layout.fillWidth: true
            spacing: Studio.Theme.space8

            Label { text: qsTr("Độ khó *"); color: Studio.Theme.textOnSurface; font.pixelSize: Studio.Theme.labelLarge }
            Studio.StudioComboBox {
                id: difficulty

                Layout.fillWidth: true
                Layout.minimumWidth: 0
                Accessible.name: qsTr("Độ khó bài mới")
                objectName: "newDraftDifficulty"
                enabled: !card.editor.backend.busy && !card.editor.dirty
                textRole: "label"
                valueRole: "value"
                model: [
                    {label: qsTr("Chọn độ khó"), value: ""},
                    {label: qsTr("Dễ"), value: "easy"},
                    {label: qsTr("Trung bình"), value: "medium"},
                    {label: qsTr("Khó"), value: "hard"}
                ]
                onActiveFocusChanged: if (activeFocus) card.focusRequested(difficulty)
            }
        }
        Studio.StudioButton {
            id: createButton

            Layout.fillWidth: true
            Layout.topMargin: Studio.Theme.space8
            enabled: !!newId.text.trim() && !!newTitle.text.trim() && topics.selectedTags.length > 0 && !!difficulty.currentValue && !card.editor.dirty && !card.editor.backend.busy
            highlighted: true
            iconName: "add"
            objectName: "createDraftButton"
            text: qsTr("Tạo bản nháp")
            onClicked: card.editor.create(newId.text.trim(), newTitle.text.trim(), topics.selectedTags, difficulty.currentValue)
            onActiveFocusChanged: if (activeFocus) card.focusRequested(createButton)
        }
        Rectangle {
            Layout.fillWidth: true
            implicitHeight: Studio.Theme.borderWidth
            color: Studio.Theme.outlineVariant
            visible: card.editor.dirty
        }
        Label {
            Layout.fillWidth: true
            color: Studio.Theme.warning
            font.pixelSize: Studio.Theme.bodySmall
            objectName: "draftLandingHint"
            text: qsTr("Lưu thay đổi ở bài đang sửa trước khi tạo hoặc mở bản nháp khác.")
            visible: card.editor.dirty
            wrapMode: Text.WordWrap
        }
    }
}
