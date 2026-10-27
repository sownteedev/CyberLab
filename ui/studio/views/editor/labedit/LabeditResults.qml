pragma ComponentBehavior: Bound
import QtQuick
import QtQuick.Controls.Basic
import QtQuick.Layouts
import "../../.."
import "../../.." as Studio
import "../../../models/EditorModel.js" as Model
import "../../../models/LabeditModel.js" as Labedit

ColumnLayout {
    id: page
    required property var editor
    readonly property var document: editor.document || {}
    readonly property var entries: (document.assessment || {}).results || []
    readonly property var nodeIds: (document.nodes || []).map(node => node.id)
    readonly property var operators: ["exists", "contains", "equals", "line_contains", "regex", "size_less_than", "size_equals", "line_count_equals", "sha256_equals", "md5_equals", "string_count_equals", "field_equals"]
    readonly property var operatorLabels: ["File/thư mục tồn tại", "Nội dung chứa", "Nội dung bằng", "Có dòng chứa", "Khớp regex", "Dung lượng nhỏ hơn", "Dung lượng bằng", "Số dòng bằng", "SHA-256 bằng", "MD5 bằng", "Đếm chuỗi", "Trích xuất trường bằng"]
    readonly property var fieldTypes: ["token", "parens", "quotes", "slash", "group"]
    readonly property var lineTypes: ["line", "starts_with", "contains", "regex", "previous_starts_with"]

    spacing: Studio.Theme.space12
    RowLayout {
        Layout.fillWidth: true
        SectionHeader { Layout.fillWidth: true; title: "Điều kiện kiểm tra"; subtitle: page.entries.length + "/64"; titleSize: Studio.Theme.titleMedium }
        StudioButton {
            iconName: "add"; text: "Thêm"; enabled: page.entries.length < 64 && page.nodeIds.length > 0
            onClicked: page.editor.addNestedEntry("assessment", "results", {
                id: Model.nextId(Labedit.assessmentEntries(page.document), "result"), node: page.nodeIds[0], path: "answer.txt", operator: "exists"
            }, 64)
        }
    }
    Repeater {
        model: page.entries
        delegate: LabeditCard {
            id: result
            required property var modelData
            required property int index
            Layout.fillWidth: true; title: modelData.id
            onRemoveRequested: page.editor.removeNestedEntry("assessment", "results", index)
            StudioTextField {
                Layout.fillWidth: true; text: result.modelData.id; placeholderText: "Mã điều kiện"; Accessible.name: placeholderText
                onEditingFinished: page.editor.updateNestedEntry("assessment", "results", result.index, "id", text.trim())
            }
            StudioTextField {
                Layout.fillWidth: true; text: result.modelData.description || ""; placeholderText: "Yêu cầu hiển thị cho người học"; Accessible.name: placeholderText
                onEditingFinished: page.editor.updateNestedEntry("assessment", "results", result.index, "description", text)
            }
            StudioComboBox {
                Layout.fillWidth: true; model: page.nodeIds; currentIndex: model.indexOf(result.modelData.node); Accessible.name: "Máy cần kiểm tra"
                onActivated: page.editor.updateNestedEntry("assessment", "results", result.index, "node", currentText)
            }
            StudioTextField {
                Layout.fillWidth: true; text: result.modelData.path; placeholderText: "Đường dẫn trong home/workspace"; Accessible.name: placeholderText
                onEditingFinished: page.editor.updateNestedEntry("assessment", "results", result.index, "path", text.trim())
            }
            StudioComboBox {
                Layout.fillWidth: true
                model: page.operatorLabels
                currentIndex: page.operators.indexOf(result.modelData.operator); Accessible.name: "Phép kiểm tra"
                objectName: "labedit-result-operator-" + result.index
                onActivated: page.editor.updateNestedEntry("assessment", "results", result.index, "operator", page.operators[currentIndex])
            }
            StudioTextField {
                Layout.fillWidth: true; visible: result.modelData.operator !== "exists" && result.modelData.operator !== "field_equals"
                text: result.modelData.expected === undefined ? "" : String(result.modelData.expected)
                placeholderText: "Giá trị cần đạt"; Accessible.name: placeholderText
                onEditingFinished: page.editor.updateNestedEntry("assessment", "results", result.index, "expected", text)
            }
            StudioTextField {
                Layout.fillWidth: true
                visible: result.modelData.operator === "string_count_equals"
                text: result.modelData.field_id === undefined ? "" : String(result.modelData.field_id)
                placeholderText: "Chuỗi cần đếm"
                Accessible.name: placeholderText
                onEditingFinished: page.editor.updateNestedEntry("assessment", "results", result.index, "field_id", text)
            }
            StudioComboBox {
                Layout.fillWidth: true
                visible: result.modelData.operator === "field_equals"
                model: page.fieldTypes
                currentIndex: Math.max(0, page.fieldTypes.indexOf(result.modelData.field_type))
                Accessible.name: "Kiểu trường cần lấy"
                onActivated: page.editor.updateNestedEntry("assessment", "results", result.index, "field_type", currentText)
            }
            StudioTextField {
                Layout.fillWidth: true
                visible: result.modelData.operator === "field_equals"
                text: result.modelData.field_id === undefined ? "" : String(result.modelData.field_id)
                placeholderText: result.modelData.field_type === "group" ? "Số group regex, bắt đầu từ 0" : "Số trường, ALL hoặc LAST"
                Accessible.name: placeholderText
                onEditingFinished: page.editor.updateNestedEntry("assessment", "results", result.index, "field_id", text)
            }
            StudioComboBox {
                Layout.fillWidth: true
                visible: result.modelData.operator === "field_equals"
                model: page.lineTypes
                currentIndex: Math.max(0, page.lineTypes.indexOf(result.modelData.line_type))
                Accessible.name: "Kiểu chọn dòng"
                onActivated: page.editor.updateNestedEntry("assessment", "results", result.index, "line_type", currentText)
            }
            StudioTextField {
                Layout.fillWidth: true
                visible: result.modelData.operator === "field_equals"
                text: result.modelData.line_id === undefined ? "" : String(result.modelData.line_id)
                placeholderText: result.modelData.line_type === "line" ? "Số dòng bắt đầu từ 1" : "Chuỗi hoặc regex chọn dòng"
                Accessible.name: placeholderText
                onEditingFinished: page.editor.updateNestedEntry("assessment", "results", result.index, "line_id", text)
            }
            StudioTextField {
                Layout.fillWidth: true
                visible: result.modelData.operator === "field_equals"
                text: result.modelData.expected === undefined ? "" : String(result.modelData.expected)
                placeholderText: "Giá trị trường cần đạt"; Accessible.name: placeholderText
                onEditingFinished: page.editor.updateNestedEntry("assessment", "results", result.index, "expected", text)
            }
            StudioTextField {
                Layout.fillWidth: true; text: result.modelData.hint || ""; placeholderText: "Gợi ý khi chưa đạt"; Accessible.name: placeholderText
                onEditingFinished: page.editor.updateNestedEntry("assessment", "results", result.index, "hint", text)
            }
        }
    }
}
