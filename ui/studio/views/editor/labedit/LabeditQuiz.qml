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
    readonly property var groups: (editor.document || {}).quizzes
        || [{id: "default", title: "", items: (editor.document || {}).quiz || []}]
    readonly property bool legacy: !(editor.document || {}).quizzes
    spacing: Studio.Theme.space12

    RowLayout {
        Layout.fillWidth: true
        SectionHeader {
            Layout.fillWidth: true
            title: "Quiz"
            subtitle: page.groups.length + "/8 bộ"
            titleSize: Studio.Theme.titleMedium
        }
        StudioButton {
            iconName: "add"
            text: "Thêm bộ"
            enabled: page.groups.length < 8
            onClicked: page.editor.addQuizGroup({id: Model.nextId(page.groups, "quiz"), title: "", items: []}, 8)
        }
    }
    Label {
        Layout.fillWidth: true
        text: page.legacy ? "Quiz cũ sẽ được chuyển sang bộ mặc định khi bạn thêm hoặc chỉnh sửa."
            : "Mỗi bộ Quiz có thể chứa phần giới thiệu, câu chọn đáp án, Đúng/Sai, phản hồi và prerequisite."
        wrapMode: Text.WordWrap
        color: Studio.Theme.textOnSurfaceVariant
        font.pixelSize: Studio.Theme.bodySmall
    }
    Repeater {
        model: page.groups
        delegate: LabeditCard {
            id: groupCard
            required property var modelData
            required property int index
            readonly property var items: modelData.items || []
            Layout.fillWidth: true
            title: modelData.id || "Bộ Quiz"
            onRemoveRequested: page.editor.removeQuizGroup(index)

            RowLayout {
                Layout.fillWidth: true
                StudioTextField {
                    Layout.fillWidth: true
                    text: groupCard.modelData.id || ""
                    placeholderText: "Mã bộ Quiz"
                    Accessible.name: placeholderText
                    onEditingFinished: page.editor.updateQuizGroup(groupCard.index, "id", text.trim())
                }
                StudioTextField {
                    Layout.fillWidth: true
                    text: groupCard.modelData.title || ""
                    placeholderText: "Tiêu đề bộ Quiz"
                    Accessible.name: placeholderText
                    onEditingFinished: page.editor.updateQuizGroup(groupCard.index, "title", text)
                }
                StudioButton {
                    iconName: "add"
                    text: "Thêm mục"
                    enabled: groupCard.items.length < 64
                    onClicked: page.editor.addQuizItem(groupCard.index, {
                        id: Model.nextId(groupCard.items, "question"), type: "choice",
                        question: "", options: ["A", "B"]
                    }, 64)
                }
            }
            CheckBox {
                text: "Hoàn thành trước khi mở bài"
                checked: !!groupCard.modelData.pre_start
                onToggled: page.editor.updateQuizGroup(groupCard.index, "pre_start", checked)
            }
            Repeater {
                model: groupCard.items
                delegate: LabeditQuizItem {
                    required property var modelData
                    required property int index
                    editor: page.editor
                    groupIndex: groupCard.index
                    itemIndex: index
                    groupItems: groupCard.items
                    Layout.fillWidth: true
                }
            }
            EmptyState {
                Layout.fillWidth: true
                visible: groupCard.items.length === 0
                title: "Bộ Quiz trống"
                description: "Thêm phần giới thiệu hoặc câu hỏi để người học sử dụng."
            }
        }
    }
}
