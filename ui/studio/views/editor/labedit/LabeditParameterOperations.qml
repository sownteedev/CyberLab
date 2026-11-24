pragma ComponentBehavior: Bound
import QtQuick
import QtQuick.Controls.Basic
import QtQuick.Layouts
import "../../.."
import "../../.." as Studio
import "../../../models/EditorModel.js" as Model

ColumnLayout {
    id: page

    readonly property var document: editor.document || {}
    required property var editor
    readonly property var nodeIds: document.nodes || []
    readonly property var operations: document.parameterizations || []

    spacing: Studio.Theme.space12

    RowLayout {
        Layout.fillWidth: true

        SectionHeader {
            Layout.fillWidth: true
            subtitle: page.operations.length + "/64"
            title: "Thay thế khi tạo phiên"
            titleSize: Studio.Theme.titleMedium
        }
        StudioButton {
            enabled: page.operations.length < 64 && page.nodeIds.length > 0
            iconName: "add"
            text: "Thêm"

            onClicked: page.editor.addEntry("parameterizations", {
                id: Model.nextId(page.operations, "replace"),
                operation: "rand_replace",
                node: page.nodeIds[0].id,
                path: "config.txt",
                token: "TOKEN",
                lower: 1,
                upper: 100,
                step: 1
            }, 64)
        }
    }
    Label {
        Layout.fillWidth: true
        color: Studio.Theme.textOnSurfaceVariant
        font.pixelSize: Studio.Theme.bodySmall
        text: "Tham số hóa chỉ thay đổi file seed đã khai báo; không chạy script và không đọc file ngoài workspace."
        wrapMode: Text.WordWrap
    }
    Repeater {
        model: page.operations

        delegate: LabeditCard {
            id: operation

            required property int index
            required property var modelData

            Layout.fillWidth: true
            title: modelData.id

            onRemoveRequested: page.editor.removeEntry("parameterizations", operation.index)

            GridLayout {
                Layout.fillWidth: true
                columns: width >= 520 ? 2 : 1

                StudioTextField {
                    Accessible.name: placeholderText
                    Layout.fillWidth: true
                    placeholderText: "Mã phép thay thế"
                    text: operation.modelData.id

                    onEditingFinished: page.editor.updateEntry("parameterizations", operation.index, "id", text.trim())
                }
                StudioComboBox {
                    Accessible.name: "Phép tham số hóa"
                    Layout.fillWidth: true
                    currentIndex: model.indexOf(operation.modelData.operation)
                    model: ["rand_replace", "rand_replace_unique", "hash_replace", "hash_create", "clone_replace"]

                    onActivated: page.editor.updateEntry("parameterizations", operation.index, "operation", currentText)
                }
                StudioComboBox {
                    Accessible.name: "Máy nhận thay thế"
                    Layout.fillWidth: true
                    currentIndex: model.indexOf(operation.modelData.node)
                    model: page.nodeIds.map(node => node.id)

                    onActivated: page.editor.updateEntry("parameterizations", operation.index, "node", currentText)
                }
                StudioTextField {
                    Accessible.name: placeholderText
                    Layout.fillWidth: true
                    placeholderText: "Đường dẫn seed, ví dụ exercises/config.txt"
                    text: operation.modelData.path || ""

                    onEditingFinished: page.editor.updateEntry("parameterizations", operation.index, "path", text.trim())
                }
            }
            StudioTextField {
                Accessible.name: placeholderText
                Layout.fillWidth: true
                placeholderText: "Token cần thay, ví dụ PORT hoặc SECRET"
                text: operation.modelData.token || ""
                visible: ["rand_replace", "hash_replace", "rand_replace_unique", "clone_replace"].includes(operation.modelData.operation)

                onEditingFinished: page.editor.updateEntry("parameterizations", operation.index, "token", text)
            }
            StudioTextField {
                Accessible.name: placeholderText
                Layout.fillWidth: true
                placeholderText: "Chuỗi đầu vào hash (có thể dùng {{param:id}})"
                text: operation.modelData.value || ""
                visible: ["hash_replace", "hash_create"].includes(operation.modelData.operation)

                onEditingFinished: page.editor.updateEntry("parameterizations", operation.index, "value", text)
            }
            GridLayout {
                Layout.fillWidth: true
                columns: width >= 520 ? 3 : 1
                visible: ["rand_replace", "rand_replace_unique"].includes(operation.modelData.operation)

                StudioTextField {
                    Accessible.name: placeholderText
                    Layout.fillWidth: true
                    placeholderText: "Từ"
                    text: operation.modelData.lower === undefined ? "0" : String(operation.modelData.lower)

                    onEditingFinished: page.editor.updateEntry("parameterizations", operation.index, "lower", text)
                }
                StudioTextField {
                    Accessible.name: placeholderText
                    Layout.fillWidth: true
                    placeholderText: "Đến"
                    text: operation.modelData.upper === undefined ? "100" : String(operation.modelData.upper)

                    onEditingFinished: page.editor.updateEntry("parameterizations", operation.index, "upper", text)
                }
                StudioTextField {
                    Accessible.name: placeholderText
                    Layout.fillWidth: true
                    placeholderText: "Bước"
                    text: operation.modelData.step === undefined ? "1" : String(operation.modelData.step)

                    onEditingFinished: page.editor.updateEntry("parameterizations", operation.index, "step", text)
                }
            }
        }
    }
}
