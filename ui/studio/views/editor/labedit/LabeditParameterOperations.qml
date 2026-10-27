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
    readonly property var document: editor.document || {}
    readonly property var operations: document.parameterizations || []
    readonly property var nodeIds: document.nodes || []
    spacing: Studio.Theme.space12
    RowLayout {
        Layout.fillWidth: true
        SectionHeader { Layout.fillWidth: true; title: "Thay thế khi tạo phiên"; subtitle: page.operations.length + "/64"; titleSize: Studio.Theme.titleMedium }
        StudioButton {
            iconName: "add"; text: "Thêm"; enabled: page.operations.length < 64 && page.nodeIds.length > 0
            onClicked: page.editor.addEntry("parameterizations", {
                id: Model.nextId(page.operations, "replace"), operation: "rand_replace", node: page.nodeIds[0].id,
                path: "config.txt", token: "TOKEN", lower: 1, upper: 100, step: 1
            }, 64)
        }
    }
    Label {
        Layout.fillWidth: true
        text: "Tham số hóa chỉ thay đổi file seed đã khai báo; không chạy script và không đọc file ngoài workspace."
        wrapMode: Text.WordWrap; color: Studio.Theme.textOnSurfaceVariant; font.pixelSize: Studio.Theme.bodySmall
    }
    Repeater {
        model: page.operations
        delegate: LabeditCard {
            id: operation
            required property var modelData
            required property int index
            Layout.fillWidth: true; title: modelData.id
            onRemoveRequested: page.editor.removeEntry("parameterizations", operation.index)
            GridLayout {
                Layout.fillWidth: true
                columns: width >= 520 ? 2 : 1
                StudioTextField {
                    Layout.fillWidth: true; text: operation.modelData.id; placeholderText: "Mã phép thay thế"; Accessible.name: placeholderText
                    onEditingFinished: page.editor.updateEntry("parameterizations", operation.index, "id", text.trim())
                }
                StudioComboBox {
                    Layout.fillWidth: true; model: ["rand_replace", "rand_replace_unique", "hash_replace", "hash_create", "clone_replace"]; Accessible.name: "Phép tham số hóa"
                    currentIndex: model.indexOf(operation.modelData.operation)
                    onActivated: page.editor.updateEntry("parameterizations", operation.index, "operation", currentText)
                }
                StudioComboBox {
                    Layout.fillWidth: true; model: page.nodeIds.map(node => node.id); Accessible.name: "Máy nhận thay thế"
                    currentIndex: model.indexOf(operation.modelData.node)
                    onActivated: page.editor.updateEntry("parameterizations", operation.index, "node", currentText)
                }
                StudioTextField {
                    Layout.fillWidth: true; text: operation.modelData.path || ""; placeholderText: "Đường dẫn seed, ví dụ exercises/config.txt"; Accessible.name: placeholderText
                    onEditingFinished: page.editor.updateEntry("parameterizations", operation.index, "path", text.trim())
                }
            }
            StudioTextField {
                Layout.fillWidth: true; visible: ["rand_replace", "hash_replace", "rand_replace_unique", "clone_replace"].includes(operation.modelData.operation)
                text: operation.modelData.token || ""; placeholderText: "Token cần thay, ví dụ PORT hoặc SECRET"; Accessible.name: placeholderText
                onEditingFinished: page.editor.updateEntry("parameterizations", operation.index, "token", text)
            }
            StudioTextField {
                Layout.fillWidth: true; visible: ["hash_replace", "hash_create"].includes(operation.modelData.operation)
                text: operation.modelData.value || ""; placeholderText: "Chuỗi đầu vào hash (có thể dùng {{param:id}})"; Accessible.name: placeholderText
                onEditingFinished: page.editor.updateEntry("parameterizations", operation.index, "value", text)
            }
            GridLayout {
                Layout.fillWidth: true; visible: ["rand_replace", "rand_replace_unique"].includes(operation.modelData.operation); columns: width >= 520 ? 3 : 1
                StudioTextField {
                    Layout.fillWidth: true; text: operation.modelData.lower === undefined ? "0" : String(operation.modelData.lower); placeholderText: "Từ"; Accessible.name: placeholderText
                    onEditingFinished: page.editor.updateEntry("parameterizations", operation.index, "lower", text)
                }
                StudioTextField {
                    Layout.fillWidth: true; text: operation.modelData.upper === undefined ? "100" : String(operation.modelData.upper); placeholderText: "Đến"; Accessible.name: placeholderText
                    onEditingFinished: page.editor.updateEntry("parameterizations", operation.index, "upper", text)
                }
                StudioTextField {
                    Layout.fillWidth: true; text: operation.modelData.step === undefined ? "1" : String(operation.modelData.step); placeholderText: "Bước"; Accessible.name: placeholderText
                    onEditingFinished: page.editor.updateEntry("parameterizations", operation.index, "step", text)
                }
            }
        }
    }
}
