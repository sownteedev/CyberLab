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
        SectionHeader { Layout.fillWidth: true; title: "Tham số"; subtitle: page.entries.length + "/32"; titleSize: Studio.Theme.titleMedium }
        StudioButton {
            iconName: "add"; text: "Thêm"; enabled: page.entries.length < 32
            onClicked: page.editor.addEntry("parameters", {id: Model.nextId(page.entries, "param"), type: "text", "public": true}, 32)
        }
    }
    Label {
        Layout.fillWidth: true
        text: "Dùng {{param:ma-tham-so}} trong hostname, lệnh, file UTF-8, hướng dẫn và nội dung cần kiểm tra."
        wrapMode: Text.WordWrap; color: Studio.Theme.textOnSurfaceVariant; font.pixelSize: Studio.Theme.bodySmall
    }
    Repeater {
        model: page.entries
        delegate: LabeditCard {
            id: parameter
            required property var modelData
            required property int index
            Layout.fillWidth: true
            title: modelData.id
            onRemoveRequested: page.editor.removeEntry("parameters", index)
            GridLayout {
                Layout.fillWidth: true
                columns: width >= 520 ? 2 : 1
                StudioTextField {
                    Layout.fillWidth: true; text: parameter.modelData.id; placeholderText: "Mã tham số"; Accessible.name: placeholderText
                    onEditingFinished: page.editor.updateEntry("parameters", parameter.index, "id", text.trim())
                }
                StudioComboBox {
                    Layout.fillWidth: true; model: ["text", "integer", "boolean", "choice"]; Accessible.name: "Kiểu tham số"
                    currentIndex: model.indexOf(parameter.modelData.type)
                    onActivated: page.editor.updateEntry("parameters", parameter.index, "type", currentText)
                }
            }
            StudioTextField {
                Layout.fillWidth: true; text: parameter.modelData.description || ""; placeholderText: "Mô tả"; Accessible.name: placeholderText
                onEditingFinished: page.editor.updateEntry("parameters", parameter.index, "description", text)
            }
            StudioTextArea {
                Layout.fillWidth: true; Layout.preferredHeight: 80
                visible: parameter.modelData.type === "choice"
                text: (parameter.modelData.choices || []).join("\n")
                placeholderText: "Mỗi lựa chọn một dòng"; Accessible.name: placeholderText
                onActiveFocusChanged: if (!activeFocus) page.editor.updateEntry("parameters", parameter.index, "choices", text.split("\n").map(value => value.trim()).filter(Boolean))
            }
            CheckBox {
                text: "Cho phép nhập khi mở bài"; checked: parameter.modelData["public"] !== false
                onToggled: page.editor.updateEntry("parameters", parameter.index, "public", checked)
            }
            CheckBox {
                text: "Dùng giá trị mặc định (bỏ chọn để tự sinh)"
                checked: parameter.modelData.default !== undefined
                onToggled: page.editor.updateEntry("parameters", parameter.index, "default", !checked ? null
                    : parameter.modelData.type === "boolean" ? false : parameter.modelData.type === "integer" ? 0
                    : parameter.modelData.type === "choice" ? (parameter.modelData.choices || [])[0] : "")
            }
            StudioTextField {
                Layout.fillWidth: true
                visible: parameter.modelData.default !== undefined && ["text", "integer"].includes(parameter.modelData.type)
                text: parameter.modelData.default === undefined ? "" : String(parameter.modelData.default)
                placeholderText: "Giá trị mặc định"; Accessible.name: placeholderText
                onEditingFinished: page.editor.updateEntry("parameters", parameter.index, "default", text)
            }
            StudioComboBox {
                Layout.fillWidth: true
                visible: parameter.modelData.default !== undefined && ["boolean", "choice"].includes(parameter.modelData.type)
                model: parameter.modelData.type === "boolean" ? ["false", "true"] : parameter.modelData.choices || []
                currentIndex: model.indexOf(String(parameter.modelData.default))
                Accessible.name: "Giá trị mặc định"
                onActivated: page.editor.updateEntry("parameters", parameter.index, "default", currentText)
            }
        }
    }
    StudioButton { id: operations; text: "Phép sinh tham số nâng cao"; flat: true; checkable: true }
    Loader {
        Layout.fillWidth: true
        active: operations.checked
        visible: active
        sourceComponent: LabeditParameterOperations { editor: page.editor }
    }
}
