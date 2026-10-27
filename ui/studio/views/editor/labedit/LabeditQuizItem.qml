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
    required property int itemIndex
    required property var modelData
    required property var groupItems
    readonly property string itemType: modelData.type || "choice"
    readonly property var prerequisites: groupItems.filter((entry, entryIndex) =>
        entryIndex < itemCard.itemIndex && (entry.type || "choice") !== "preface"
            && entry.id !== itemCard.modelData.id)
    Layout.fillWidth: true
    title: modelData.id || "Mục Quiz"
    onRemoveRequested: editor.removeQuizItem(groupIndex, itemIndex)

    StudioTextField {
        Layout.fillWidth: true
        text: itemCard.modelData.id || ""
        placeholderText: "Mã mục"
        Accessible.name: placeholderText
        onEditingFinished: itemCard.editor.updateQuizItem(itemCard.groupIndex, itemCard.itemIndex, "id", text.trim())
    }
    StudioComboBox {
        Layout.fillWidth: true
        objectName: "quiz-type-" + itemCard.groupIndex + "-" + itemCard.itemIndex
        model: ["choice", "true_false", "preface"]
        currentIndex: Math.max(0, model.indexOf(itemCard.itemType))
        Accessible.name: "Dạng mục Quiz"
        onActivated: itemCard.editor.updateQuizItem(itemCard.groupIndex, itemCard.itemIndex, "type", model[currentIndex])
    }
    StudioTextArea {
        Layout.fillWidth: true
        Layout.preferredHeight: itemCard.itemType === "preface" ? 132 : 104
        visible: itemCard.itemType === "preface"
        text: itemCard.modelData.text || ""
        placeholderText: "Nội dung dẫn nhập"
        Accessible.name: placeholderText
        onActiveFocusChanged: if (!activeFocus) itemCard.editor.updateQuizItem(itemCard.groupIndex, itemCard.itemIndex, "text", text)
    }
    StudioTextField {
        Layout.fillWidth: true
        visible: itemCard.itemType !== "preface"
        text: itemCard.modelData.question || ""
        placeholderText: "Nội dung câu hỏi"
        Accessible.name: placeholderText
        onEditingFinished: itemCard.editor.updateQuizItem(itemCard.groupIndex, itemCard.itemIndex, "question", text)
    }
    StudioTextArea {
        Layout.fillWidth: true
        Layout.preferredHeight: 104
        visible: itemCard.itemType === "choice"
        text: (itemCard.modelData.options || []).join("\n")
        placeholderText: "Từ 2 đến 8 lựa chọn, mỗi dòng một lựa chọn"
        Accessible.name: placeholderText
        onActiveFocusChanged: if (!activeFocus) itemCard.editor.updateQuizItem(itemCard.groupIndex, itemCard.itemIndex, "options", text.split("\n").map(value => value.trim()).filter(Boolean))
    }
    StudioComboBox {
        Layout.fillWidth: true
        visible: itemCard.itemType === "choice"
        model: ["Không chấm đáp án"].concat((itemCard.modelData.options || []).map((value, optionIndex) => (optionIndex + 1) + ". " + value))
        currentIndex: itemCard.modelData.answer === undefined ? 0 : itemCard.modelData.answer + 1
        Accessible.name: "Đáp án đúng"
        onActivated: itemCard.editor.updateQuizItem(itemCard.groupIndex, itemCard.itemIndex, "answer", currentIndex === 0 ? null : currentIndex - 1)
    }
    StudioComboBox {
        Layout.fillWidth: true
        visible: itemCard.itemType === "true_false"
        model: ["Không chấm đáp án", "Sai", "Đúng"]
        currentIndex: itemCard.modelData.answer === undefined ? 0 : itemCard.modelData.answer + 1
        Accessible.name: "Đáp án Đúng/Sai"
        onActivated: itemCard.editor.updateQuizItem(itemCard.groupIndex, itemCard.itemIndex, "answer", currentIndex === 0 ? null : currentIndex - 1)
    }
    StudioComboBox {
        Layout.fillWidth: true
        visible: itemCard.itemType !== "preface" && itemCard.prerequisites.length > 0
        model: ["Không có câu phụ thuộc"].concat(itemCard.prerequisites.map(entry => entry.id))
        currentIndex: itemCard.modelData.prerequisite ? Math.max(0, model.indexOf(itemCard.modelData.prerequisite)) : 0
        Accessible.name: "Câu hỏi phụ thuộc"
        onActivated: itemCard.editor.updateQuizItem(itemCard.groupIndex, itemCard.itemIndex, "prerequisite", currentIndex === 0 ? null : model[currentIndex])
    }
    StudioTextField {
        Layout.fillWidth: true
        visible: itemCard.itemType !== "preface"
        text: itemCard.modelData.right_response || ""
        placeholderText: "Phản hồi khi đúng (tùy chọn)"
        Accessible.name: placeholderText
        onEditingFinished: itemCard.editor.updateQuizItem(itemCard.groupIndex, itemCard.itemIndex, "right_response", text)
    }
    StudioTextField {
        Layout.fillWidth: true
        visible: itemCard.itemType !== "preface"
        text: itemCard.modelData.wrong_response || ""
        placeholderText: "Phản hồi khi sai (tùy chọn)"
        Accessible.name: placeholderText
        onEditingFinished: itemCard.editor.updateQuizItem(itemCard.groupIndex, itemCard.itemIndex, "wrong_response", text)
    }
    StudioTextField {
        Layout.fillWidth: true
        visible: itemCard.itemType !== "preface"
        text: itemCard.modelData.explanation || ""
        placeholderText: "Giải thích mặc định"
        Accessible.name: placeholderText
        onEditingFinished: itemCard.editor.updateQuizItem(itemCard.groupIndex, itemCard.itemIndex, "explanation", text)
    }
}
