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
    readonly property var entries: (document.assessment || {}).artifacts || []
    readonly property var nodeIds: (document.nodes || []).map(node => node.id)
    spacing: Studio.Theme.space12
    RowLayout {
        Layout.fillWidth: true
        SectionHeader { Layout.fillWidth: true; title: "Bằng chứng bài nộp"; subtitle: page.entries.length + "/64"; titleSize: Studio.Theme.titleMedium }
        StudioButton {
            iconName: "add"; text: "Thêm"; enabled: page.entries.length < 64 && page.nodeIds.length > 0
            onClicked: page.editor.addNestedEntry("assessment", "artifacts", {
                id: Model.nextId(Labedit.assessmentEntries(page.document), "artifact"), node: page.nodeIds[0], path: "answer.txt", required: true
            }, 64)
        }
    }
    Label {
        Layout.fillWidth: true; text: "Đường dẫn tính từ home/workspace của máy. Khai báo thư mục sẽ lấy cả file con và thư mục rỗng."
        wrapMode: Text.WordWrap; color: Studio.Theme.textOnSurfaceVariant; font.pixelSize: Studio.Theme.bodySmall
    }
    Repeater {
        model: page.entries
        delegate: LabeditCard {
            id: artifact
            required property var modelData
            required property int index
            Layout.fillWidth: true; title: modelData.id
            onRemoveRequested: page.editor.removeNestedEntry("assessment", "artifacts", index)
            StudioTextField {
                Layout.fillWidth: true; text: artifact.modelData.id; placeholderText: "Mã bằng chứng"; Accessible.name: placeholderText
                onEditingFinished: page.editor.updateNestedEntry("assessment", "artifacts", artifact.index, "id", text.trim())
            }
            StudioComboBox {
                Layout.fillWidth: true; model: page.nodeIds; currentIndex: model.indexOf(artifact.modelData.node); Accessible.name: "Máy chứa file"
                onActivated: page.editor.updateNestedEntry("assessment", "artifacts", artifact.index, "node", currentText)
            }
            StudioTextField {
                Layout.fillWidth: true; text: artifact.modelData.path; placeholderText: "File hoặc thư mục, ví dụ answers"; Accessible.name: placeholderText
                onEditingFinished: page.editor.updateNestedEntry("assessment", "artifacts", artifact.index, "path", text.trim())
            }
            StudioTextField {
                Layout.fillWidth: true; text: artifact.modelData.label || ""; placeholderText: "Tên hiển thị"; Accessible.name: placeholderText
                onEditingFinished: page.editor.updateNestedEntry("assessment", "artifacts", artifact.index, "label", text)
            }
            CheckBox {
                text: "Bắt buộc có trong bài nộp"; checked: artifact.modelData.required !== false
                onToggled: page.editor.updateNestedEntry("assessment", "artifacts", artifact.index, "required", checked)
            }
        }
    }
}
