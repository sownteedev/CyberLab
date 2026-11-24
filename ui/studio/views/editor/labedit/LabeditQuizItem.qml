pragma ComponentBehavior: Bound
import QtQuick
import QtQuick.Controls.Basic
import QtQuick.Layouts
import "../../.."
import "../../.." as Studio

LabeditCard {
    id: itemCard

    required property var editor
    required property int groupIndex
    required property var groupItems
    required property int itemIndex
    readonly property string itemType: modelData.type || "choice"
    required property var modelData
    readonly property var prerequisites: groupItems.filter((entry, entryIndex) => entryIndex < itemCard.itemIndex && (entry.type || "choice") !== "preface" && entry.id !== itemCard.modelData.id)

    Layout.fillWidth: true
    title: itemType === "preface" ? "Giới thiệu" : "Câu " + (itemIndex + 1)

    onRemoveRequested: editor.removeQuizItem(groupIndex, itemIndex)


    StudioComboBox {
        Accessible.name: "Dạng mục Quiz"
        Layout.fillWidth: true
        currentIndex: Math.max(0, ["choice", "true_false", "preface"].indexOf(itemCard.itemType))
        model: ["Chọn đáp án", "Đúng / Sai", "Giới thiệu"]
        objectName: "quiz-type-" + itemCard.groupIndex + "-" + itemCard.itemIndex

        onActivated: itemCard.editor.updateQuizItem(itemCard.groupIndex, itemCard.itemIndex, "type", ["choice", "true_false", "preface"][currentIndex])
    }
    StudioTextArea {
        Accessible.name: placeholderText
        Layout.fillWidth: true
        Layout.preferredHeight: itemCard.itemType === "preface" ? 132 : 104
        placeholderText: "Nội dung dẫn nhập"
        text: itemCard.modelData.text || ""
        visible: itemCard.itemType === "preface"

        onActiveFocusChanged: if (!activeFocus)
            itemCard.editor.updateQuizItem(itemCard.groupIndex, itemCard.itemIndex, "text", text)
    }
    StudioTextField {
        Accessible.name: placeholderText
        Layout.fillWidth: true
        placeholderText: "Nội dung câu hỏi"
        text: itemCard.modelData.question || ""
        visible: itemCard.itemType !== "preface"

        onEditingFinished: itemCard.editor.updateQuizItem(itemCard.groupIndex, itemCard.itemIndex, "question", text)
    }
    StudioTextArea {
        Accessible.name: placeholderText
        Layout.fillWidth: true
        Layout.preferredHeight: 104
        placeholderText: "Từ 2 đến 8 lựa chọn, mỗi dòng một lựa chọn"
        text: (itemCard.modelData.options || []).join("\n")
        visible: itemCard.itemType === "choice"

        onActiveFocusChanged: if (!activeFocus)
            itemCard.editor.updateQuizItem(itemCard.groupIndex, itemCard.itemIndex, "options", text.split("\n").map(value => value.trim()).filter(Boolean))
    }
    StudioComboBox {
        Accessible.name: "Đáp án đúng"
        Layout.fillWidth: true
        currentIndex: itemCard.modelData.answer === undefined ? 0 : itemCard.modelData.answer + 1
        model: ["Không chấm đáp án"].concat((itemCard.modelData.options || []).map((value, optionIndex) => (optionIndex + 1) + ". " + value))
        visible: itemCard.itemType === "choice"

        onActivated: itemCard.editor.updateQuizItem(itemCard.groupIndex, itemCard.itemIndex, "answer", currentIndex === 0 ? null : currentIndex - 1)
    }
    StudioComboBox {
        Accessible.name: "Đáp án Đúng/Sai"
        Layout.fillWidth: true
        currentIndex: itemCard.modelData.answer === undefined ? 0 : itemCard.modelData.answer + 1
        model: ["Không chấm đáp án", "Sai", "Đúng"]
        visible: itemCard.itemType === "true_false"

        onActivated: itemCard.editor.updateQuizItem(itemCard.groupIndex, itemCard.itemIndex, "answer", currentIndex === 0 ? null : currentIndex - 1)
    }



    StudioTextField {
        Accessible.name: placeholderText
        Layout.fillWidth: true
        placeholderText: "Giải thích đáp án (tùy chọn)"
        text: itemCard.modelData.explanation || ""
        visible: itemCard.itemType !== "preface"

        onEditingFinished: itemCard.editor.updateQuizItem(itemCard.groupIndex, itemCard.itemIndex, "explanation", text)
    }
    Studio.EditorDisclosure {
        title: "Nâng cao"
        StudioTextField {
            Accessible.name: placeholderText
            Layout.fillWidth: true
            placeholderText: "Mã mục"
            text: itemCard.modelData.id || ""

            onEditingFinished: itemCard.editor.updateQuizItem(itemCard.groupIndex, itemCard.itemIndex, "id", text.trim())
        }
        StudioComboBox {
            Accessible.name: "Câu hỏi phụ thuộc"
            Layout.fillWidth: true
            currentIndex: itemCard.modelData.prerequisite ? Math.max(0, model.indexOf(itemCard.modelData.prerequisite)) : 0
            model: ["Không có câu phụ thuộc"].concat(itemCard.prerequisites.map(entry => entry.id))
            visible: itemCard.itemType !== "preface" && itemCard.prerequisites.length > 0

            onActivated: itemCard.editor.updateQuizItem(itemCard.groupIndex, itemCard.itemIndex, "prerequisite", currentIndex === 0 ? null : model[currentIndex])
        }
        StudioTextField {
            Accessible.name: placeholderText
            Layout.fillWidth: true
            placeholderText: "Phản hồi khi đúng (tùy chọn)"
            text: itemCard.modelData.right_response || ""
            visible: itemCard.itemType !== "preface"

            onEditingFinished: itemCard.editor.updateQuizItem(itemCard.groupIndex, itemCard.itemIndex, "right_response", text)
        }
        StudioTextField {
            Accessible.name: placeholderText
            Layout.fillWidth: true
            placeholderText: "Phản hồi khi sai (tùy chọn)"
            text: itemCard.modelData.wrong_response || ""
            visible: itemCard.itemType !== "preface"

            onEditingFinished: itemCard.editor.updateQuizItem(itemCard.groupIndex, itemCard.itemIndex, "wrong_response", text)
        }
    }
}
