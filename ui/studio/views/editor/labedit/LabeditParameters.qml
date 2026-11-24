pragma ComponentBehavior: Bound
import QtQuick
import QtQuick.Controls.Basic
import QtQuick.Layouts
import "../../.."
import "../../.." as Studio
import "../../../models/EditorModel.js" as Model

ColumnLayout {
    id: page

    required property var editor
    readonly property var entries: (editor.document || {}).parameters || []

    spacing: Studio.Theme.space12

    RowLayout {
        Layout.fillWidth: true

        SectionHeader {
            Layout.fillWidth: true
            subtitle: page.entries.length + "/32"
            title: "Tham số"
            titleSize: Studio.Theme.titleMedium
        }
        StudioButton {
            enabled: page.entries.length < 32
            iconName: "add"
            text: "Thêm"

            onClicked: page.editor.addEntry("parameters", {
                id: Model.nextId(page.entries, "param"),
                type: "text",
                "public": true
            }, 32)
        }
    }
    Label {
        Layout.fillWidth: true
        color: Studio.Theme.textOnSurfaceVariant
        font.pixelSize: Studio.Theme.bodySmall
        text: "Dùng {{param:ma-tham-so}} trong hostname, lệnh, file UTF-8, hướng dẫn và nội dung cần kiểm tra."
        wrapMode: Text.WordWrap
    }
    Repeater {
        model: page.entries

        delegate: LabeditCard {
            id: parameter

            required property int index
            required property var modelData

            Layout.fillWidth: true
            title: modelData.id

            onRemoveRequested: page.editor.removeEntry("parameters", index)

            GridLayout {
                Layout.fillWidth: true
                columns: width >= 520 ? 2 : 1

                StudioTextField {
                    Accessible.name: placeholderText
                    Layout.fillWidth: true
                    placeholderText: "Mã tham số"
                    text: parameter.modelData.id

                    onEditingFinished: page.editor.updateEntry("parameters", parameter.index, "id", text.trim())
                }
                StudioComboBox {
                    Accessible.name: "Kiểu tham số"
                    Layout.fillWidth: true
                    currentIndex: model.indexOf(parameter.modelData.type)
                    model: ["text", "integer", "boolean", "choice"]

                    onActivated: page.editor.updateEntry("parameters", parameter.index, "type", currentText)
                }
            }
            StudioTextField {
                Accessible.name: placeholderText
                Layout.fillWidth: true
                placeholderText: "Mô tả"
                text: parameter.modelData.description || ""

                onEditingFinished: page.editor.updateEntry("parameters", parameter.index, "description", text)
            }
            StudioTextArea {
                Accessible.name: placeholderText
                Layout.fillWidth: true
                Layout.preferredHeight: 80
                placeholderText: "Mỗi lựa chọn một dòng"
                text: (parameter.modelData.choices || []).join("\n")
                visible: parameter.modelData.type === "choice"

                onActiveFocusChanged: if (!activeFocus)
                    page.editor.updateEntry("parameters", parameter.index, "choices", text.split("\n").map(value => value.trim()).filter(Boolean))
            }
                Studio.StudioCheckBox {
                checked: parameter.modelData["public"] !== false
                text: "Cho phép nhập khi mở bài"

                onToggled: page.editor.updateEntry("parameters", parameter.index, "public", checked)
            }
                Studio.StudioCheckBox {
                checked: parameter.modelData.default !== undefined
                text: "Dùng giá trị mặc định (bỏ chọn để tự sinh)"

                onToggled: page.editor.updateEntry("parameters", parameter.index, "default", !checked ? null : parameter.modelData.type === "boolean" ? false : parameter.modelData.type === "integer" ? 0 : parameter.modelData.type === "choice" ? (parameter.modelData.choices || [])[0] : "")
            }
            StudioTextField {
                Accessible.name: placeholderText
                Layout.fillWidth: true
                placeholderText: "Giá trị mặc định"
                text: parameter.modelData.default === undefined ? "" : String(parameter.modelData.default)
                visible: parameter.modelData.default !== undefined && ["text", "integer"].includes(parameter.modelData.type)

                onEditingFinished: page.editor.updateEntry("parameters", parameter.index, "default", text)
            }
            StudioComboBox {
                Accessible.name: "Giá trị mặc định"
                Layout.fillWidth: true
                currentIndex: model.indexOf(String(parameter.modelData.default))
                model: parameter.modelData.type === "boolean" ? ["false", "true"] : parameter.modelData.choices || []
                visible: parameter.modelData.default !== undefined && ["boolean", "choice"].includes(parameter.modelData.type)

                onActivated: page.editor.updateEntry("parameters", parameter.index, "default", currentText)
            }
        }
    }
    StudioButton {
        id: operations

        checkable: true
        flat: true
        text: "Phép sinh tham số nâng cao"
    }
    Loader {
        Layout.fillWidth: true
        active: operations.checked
        visible: active

        sourceComponent: LabeditParameterOperations {
            editor: page.editor
        }
    }
}
