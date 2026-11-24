pragma ComponentBehavior: Bound

import QtQuick
import QtQuick.Controls.Basic
import QtQuick.Layouts
import "../.." as Studio

GridLayout {
    id: overview
    required property var editor
    columns: width >= 820 ? 2 : 1
    columnSpacing: Studio.Theme.space24
    rowSpacing: Studio.Theme.space24

    Studio.DraftFormCard {
        Layout.fillWidth: true
        Layout.preferredWidth: 600
        Layout.minimumWidth: 0
        Layout.alignment: Qt.AlignTop
        title: qsTr("Thông tin bài lab")
        iconName: "edit"
        objectName: "draftMetadataCard"

        ColumnLayout {
            Layout.fillWidth: true
            spacing: Studio.Theme.space8
            Label { color: Studio.Theme.textOnSurface; text: qsTr("Tên bài") }
            Studio.StudioTextField {
                Layout.fillWidth: true
                Accessible.name: qsTr("Tên bài")
                objectName: "draftMetadataName"
                text: overview.editor.document ? overview.editor.document.metadata.name : ""
                onEditingFinished: overview.editor.change("metadata", 0, "name", text)
            }
        }
        GridLayout {
            Layout.fillWidth: true
            columns: width >= 460 ? 2 : 1
            columnSpacing: Studio.Theme.space16
            rowSpacing: Studio.Theme.space16

            ColumnLayout {
                Layout.fillWidth: true
                spacing: Studio.Theme.space8
                Label { color: Studio.Theme.textOnSurface; text: qsTr("Mã bài") }
                Studio.StudioTextField {
                    Layout.fillWidth: true
                    Accessible.name: qsTr("Mã bài")
                    objectName: "draftMetadataId"
                    text: overview.editor.document ? overview.editor.document.metadata.id : ""
                    onEditingFinished: overview.editor.change("metadata", 0, "id", text.trim())
                }
            }
            ColumnLayout {
                Layout.fillWidth: true
                spacing: Studio.Theme.space8
                Label { color: Studio.Theme.textOnSurface; text: qsTr("Phiên bản nội dung") }
                Studio.StudioTextField {
                    Layout.fillWidth: true
                    Accessible.name: qsTr("Phiên bản nội dung")
                    objectName: "draftMetadataVersion"
                    text: overview.editor.document ? overview.editor.document.metadata.version : ""
                    onEditingFinished: overview.editor.change("metadata", 0, "version", text)
                }
            }
        }
        ColumnLayout {
            Layout.fillWidth: true
            spacing: Studio.Theme.space8
            Label { text: qsTr("Chủ đề *"); color: Studio.Theme.textOnSurface }
            Studio.TopicPicker {
                Layout.fillWidth: true
                Layout.minimumWidth: 0
                objectName: "draftMetadataTopics"
                options: overview.editor.policy ? overview.editor.policy.topic_catalog || [] : []
                selectedTags: overview.editor.document ? overview.editor.document.metadata.tags || [] : []
                requiredSelection: true
                onEdited: tags => overview.editor.change("metadata", 0, "tags", tags)
            }
        }
        ColumnLayout {
            Layout.fillWidth: true
            spacing: Studio.Theme.space8

            Label { text: qsTr("Độ khó"); color: Studio.Theme.textOnSurface }
            Studio.StudioComboBox {
                Layout.fillWidth: true
                Layout.minimumWidth: 0
                Accessible.name: qsTr("Độ khó bài lab")
                objectName: "draftMetadataDifficulty"
                textRole: "label"
                valueRole: "value"
                model: [
                    {label: qsTr("Chưa phân loại"), value: ""},
                    {label: qsTr("Dễ"), value: "easy"},
                    {label: qsTr("Trung bình"), value: "medium"},
                    {label: qsTr("Khó"), value: "hard"}
                ]
                currentIndex: ["", "easy", "medium", "hard"].indexOf(overview.editor.document ? overview.editor.document.metadata.difficulty || "" : "")
                onActivated: index => overview.editor.change("metadata", 0, "difficulty", model[index].value || undefined)
            }
        }
    }
    Studio.DraftFormCard {
        Layout.fillWidth: true
        Layout.preferredWidth: 300
        Layout.minimumWidth: 0
        Layout.alignment: Qt.AlignTop
        title: qsTr("Nội dung bài")
        objectName: "draftContentsCard"

        Repeater {
            model: [
                {section: 1, icon: "terminal", label: qsTr("%1 máy lab").arg(overview.editor.document ? overview.editor.document.nodes.length : 0)},
                {section: 2, icon: "lan", label: qsTr("%1 mạng nội bộ").arg(overview.editor.document ? overview.editor.document.networks.length : 0)},
                {section: 3, icon: "folder", label: qsTr("File ban đầu")},
                {section: 4, icon: "description", label: qsTr("Hướng dẫn thực hành")}
            ]
            Studio.StudioButton {
                required property var modelData
                Layout.fillWidth: true
                Layout.minimumWidth: 0
                flat: true
                leading: true
                iconName: modelData.icon
                text: modelData.label
                objectName: "draftOverviewLink-" + modelData.section
                onClicked: overview.editor.section = modelData.section
            }
        }
    }
    Studio.DraftFormCard {
        Layout.fillWidth: true
        Layout.preferredWidth: 300
        Layout.minimumWidth: 0
        Layout.alignment: Qt.AlignTop
        title: qsTr("Bảo vệ bài")
        iconName: "lock"
        objectName: "draftProtectionCard"

        Studio.EditProtectionSettings {
            Layout.fillWidth: true
            editor: overview.editor
        }
    }
}
