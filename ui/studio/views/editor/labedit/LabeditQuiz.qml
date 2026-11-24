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
    readonly property var groups: (editor.document || {}).quizzes || [
        {
            id: "default",
            title: "",
            pre_start: !((editor.document || {}).quiz || []).length,
            items: (editor.document || {}).quiz || []
        }
    ]
    readonly property bool legacy: !(editor.document || {}).quizzes

    spacing: Studio.Theme.space12

    RowLayout {
        Layout.fillWidth: true

        SectionHeader {
            Layout.fillWidth: true
            subtitle: page.groups.length + "/8 bộ"
            title: "Quiz"
            titleSize: Studio.Theme.titleMedium
        }
        StudioButton {
            enabled: page.groups.length < 8
            iconName: "add"
            text: "Thêm bộ"
            objectName: "addQuizGroup"

            onClicked: page.editor.addQuizGroup({
                id: Model.nextId(page.groups, "quiz"),
                title: "",
                pre_start: true,
                items: []
            }, 8)
        }
    }
    Label {
        Layout.fillWidth: true
        color: Studio.Theme.textOnSurfaceVariant
        font.pixelSize: Studio.Theme.bodySmall
        text: "Trả lời, xem đáp án rồi vào thực hành."
        wrapMode: Text.WordWrap
    }
    Repeater {
        model: page.groups

        delegate: LabeditCard {
            id: groupCard

            required property int index
            readonly property var items: modelData.items || []
            required property var modelData

            Layout.fillWidth: true
            title: modelData.title || "Bộ câu hỏi " + (index + 1)

            onRemoveRequested: page.editor.removeQuizGroup(index)

            GridLayout {
                Layout.fillWidth: true
                columns: width >= 560 ? 2 : 1
                StudioTextField {
                    Accessible.name: placeholderText
                    Layout.fillWidth: true
                    placeholderText: "Tiêu đề bộ Quiz"
                    text: groupCard.modelData.title || ""

                    onEditingFinished: page.editor.updateQuizGroup(groupCard.index, "title", text)
                }
                StudioButton {
                    enabled: groupCard.items.length < 64
                    iconName: "add"
                    text: "Thêm câu"
                    objectName: "addQuizQuestion-" + groupCard.index

                    onClicked: page.editor.addQuizItem(groupCard.index, {
                        id: Model.nextId(groupCard.items, "question"),
                        type: "choice",
                        question: "",
                        options: ["A", "B"], answer: 0
                    }, 64)
                }
            }
                Studio.StudioCheckBox {
                checked: !!groupCard.modelData.pre_start
                text: "Hiện trước khi thực hành"

                onToggled: page.editor.updateQuizGroup(groupCard.index, "pre_start", checked)
            }
            Repeater {
                model: groupCard.items

                delegate: LabeditQuizItem {
                    required property int index
                    modelData: groupCard.items[index]

                    Layout.fillWidth: true
                    editor: page.editor
                    groupIndex: groupCard.index
                    groupItems: groupCard.items
                    itemIndex: index
                }
            }
            EmptyState {
                Layout.fillWidth: true
                title: "Bộ Quiz trống"
                visible: groupCard.items.length === 0
            }
            Studio.EditorDisclosure {
                title: "Mã bộ câu hỏi"
                StudioTextField {
                    Accessible.name: "Mã bộ câu hỏi"
                    Layout.fillWidth: true
                    text: groupCard.modelData.id || ""
                    onEditingFinished: page.editor.updateQuizGroup(groupCard.index, "id", text.trim())
                }
            }
        }
    }
}
