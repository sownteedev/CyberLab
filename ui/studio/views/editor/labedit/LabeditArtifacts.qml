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

    readonly property var document: editor.document || {}
    required property var editor
    readonly property var entries: (document.assessment || {}).artifacts || []
    readonly property var nodeIds: (document.nodes || []).map(node => node.id)

    spacing: Studio.Theme.space12

    RowLayout {
        Layout.fillWidth: true

        SectionHeader {
            Layout.fillWidth: true
            subtitle: page.entries.length + "/64"
            title: "Bằng chứng bài nộp"
            titleSize: Studio.Theme.titleMedium
        }
        StudioButton {
            enabled: page.entries.length < 64 && page.nodeIds.length > 0
            iconName: "add"
            text: "Thêm"

            onClicked: page.editor.addNestedEntry("assessment", "artifacts", {
                id: Model.nextId(Labedit.assessmentEntries(page.document), "artifact"),
                node: page.nodeIds[0],
                path: "answer.txt",
                required: true
            }, 64)
        }
    }
    Label {
        Layout.fillWidth: true
        color: Studio.Theme.textOnSurfaceVariant
        font.pixelSize: Studio.Theme.bodySmall
        text: "Đường dẫn tính từ home/workspace của máy. Khai báo thư mục sẽ lấy cả file con và thư mục rỗng."
        wrapMode: Text.WordWrap
    }
    Repeater {
        model: page.entries

        delegate: LabeditCard {
            id: artifact

            required property int index
            required property var modelData

            Layout.fillWidth: true
            title: modelData.id

            onRemoveRequested: page.editor.removeNestedEntry("assessment", "artifacts", index)

            StudioTextField {
                Accessible.name: placeholderText
                Layout.fillWidth: true
                placeholderText: "Mã bằng chứng"
                text: artifact.modelData.id

                onEditingFinished: page.editor.updateNestedEntry("assessment", "artifacts", artifact.index, "id", text.trim())
            }
            StudioComboBox {
                Accessible.name: "Máy chứa file"
                Layout.fillWidth: true
                currentIndex: model.indexOf(artifact.modelData.node)
                model: page.nodeIds

                onActivated: page.editor.updateNestedEntry("assessment", "artifacts", artifact.index, "node", currentText)
            }
            StudioTextField {
                Accessible.name: placeholderText
                Layout.fillWidth: true
                placeholderText: "File hoặc thư mục, ví dụ answers"
                text: artifact.modelData.path

                onEditingFinished: page.editor.updateNestedEntry("assessment", "artifacts", artifact.index, "path", text.trim())
            }
            StudioTextField {
                Accessible.name: placeholderText
                Layout.fillWidth: true
                placeholderText: "Tên hiển thị"
                text: artifact.modelData.label || ""

                onEditingFinished: page.editor.updateNestedEntry("assessment", "artifacts", artifact.index, "label", text)
            }
                Studio.StudioCheckBox {
                checked: artifact.modelData.required !== false
                text: "Bắt buộc có trong bài nộp"

                onToggled: page.editor.updateNestedEntry("assessment", "artifacts", artifact.index, "required", checked)
            }
        }
    }
}
