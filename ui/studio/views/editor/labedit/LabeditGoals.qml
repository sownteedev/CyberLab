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
    readonly property var entries: (document.assessment || {}).goals || []
    readonly property var results: (document.assessment || {}).results || []
    spacing: Studio.Theme.space12
    RowLayout {
        Layout.fillWidth: true
        SectionHeader { Layout.fillWidth: true; title: "Mục tiêu"; subtitle: page.entries.length + "/32"; titleSize: Studio.Theme.titleMedium }
        StudioButton {
            iconName: "add"; text: "Thêm"; enabled: page.entries.length < 32 && page.results.length > 0
            onClicked: page.editor.addNestedEntry("assessment", "goals", {
                id: Model.nextId(Labedit.assessmentEntries(page.document), "goal"), results: [page.results[0].id], mode: "all"
            }, 32)
        }
    }
    Repeater {
        model: page.entries
        delegate: LabeditCard {
            id: goal
            required property var modelData
            required property int index
            Layout.fillWidth: true; title: modelData.id
            onRemoveRequested: page.editor.removeNestedEntry("assessment", "goals", index)
            StudioTextField {
                Layout.fillWidth: true; text: goal.modelData.id; placeholderText: "Mã mục tiêu"; Accessible.name: placeholderText
                onEditingFinished: page.editor.updateNestedEntry("assessment", "goals", goal.index, "id", text.trim())
            }
            StudioTextField {
                Layout.fillWidth: true; text: goal.modelData.description || ""; placeholderText: "Mô tả mục tiêu"; Accessible.name: placeholderText
                onEditingFinished: page.editor.updateNestedEntry("assessment", "goals", goal.index, "description", text)
            }
            StudioComboBox {
                objectName: "labedit-goal-type-" + goal.index
                Layout.fillWidth: true
                model: ["Nhóm điều kiện", "So sánh giá trị", "Đếm điều kiện", "Biểu thức logic"]
                currentIndex: goal.modelData.type === "compare" ? 1 : goal.modelData.type === "count" ? 2 : goal.modelData.type === "boolean" ? 3 : 0
                Accessible.name: "Kiểu mục tiêu"
                onActivated: page.editor.updateNestedEntry("assessment", "goals", goal.index, "type",
                    currentIndex === 1 ? "compare" : currentIndex === 2 ? "count" : currentIndex === 3 ? "boolean" : "group")
            }
            StudioComboBox {
                Layout.fillWidth: true; model: ["Đạt tất cả điều kiện", "Đạt ít nhất một điều kiện"]
                visible: !goal.modelData.type || goal.modelData.type === "group"
                currentIndex: goal.modelData.mode === "any" ? 1 : 0; Accessible.name: "Cách kết hợp"
                onActivated: page.editor.updateNestedEntry("assessment", "goals", goal.index, "mode", currentIndex === 0 ? "all" : "any")
            }
            StudioComboBox {
                Layout.fillWidth: true; visible: goal.modelData.type === "compare"
                model: ["string_equal", "string_diff", "string_contains", "string_start", "string_end", "integer_equal", "integer_greater", "integer_less", "hash_equal"]
                currentIndex: model.indexOf(goal.modelData.operator || "")
                Accessible.name: "Phép so sánh"
                onActivated: page.editor.updateNestedEntry("assessment", "goals", goal.index, "operator", currentText)
            }
            StudioComboBox {
                Layout.fillWidth: true; visible: goal.modelData.type === "compare"
                model: page.results.map(entry => entry.id)
                currentIndex: model.indexOf(goal.modelData.result || "")
                Accessible.name: "Giá trị đầu tiên"
                onActivated: page.editor.updateNestedEntry("assessment", "goals", goal.index, "result", currentText)
            }
            StudioComboBox {
                objectName: "labedit-goal-source-" + goal.index
                Layout.fillWidth: true; visible: goal.modelData.type === "compare"
                model: ["Giá trị nhập", "Kết quả khác"]
                enabled: page.results.length > 0
                currentIndex: goal.modelData.other ? 1 : 0
                Accessible.name: "Nguồn giá trị thứ hai"
                onActivated: if (currentIndex === 0) page.editor.updateNestedEntry("assessment", "goals", goal.index, "other", null)
                    else page.editor.updateNestedEntry("assessment", "goals", goal.index, "other", page.results.length > 1 ? page.results[1].id : page.results[0].id)
            }
            StudioTextField {
                Layout.fillWidth: true; visible: goal.modelData.type === "compare" && !goal.modelData.other
                text: goal.modelData.expected === undefined ? "" : String(goal.modelData.expected)
                placeholderText: "Giá trị kỳ vọng"; Accessible.name: placeholderText
                onEditingFinished: page.editor.updateNestedEntry("assessment", "goals", goal.index, "expected", text)
            }
            StudioComboBox {
                Layout.fillWidth: true; visible: goal.modelData.type === "compare" && !!goal.modelData.other
                model: page.results.map(entry => entry.id)
                currentIndex: model.indexOf(goal.modelData.other || "")
                Accessible.name: "Kết quả đối chiếu"
                onActivated: page.editor.updateNestedEntry("assessment", "goals", goal.index, "other", currentText)
            }
            StudioTextField {
                Layout.fillWidth: true; visible: goal.modelData.type === "count"
                text: goal.modelData.threshold === undefined ? "0" : String(goal.modelData.threshold)
                placeholderText: "Đạt nhiều hơn số lượng này"; Accessible.name: placeholderText
                onEditingFinished: page.editor.updateNestedEntry("assessment", "goals", goal.index, "threshold", text)
            }
            ColumnLayout {
                Layout.fillWidth: true
                visible: goal.modelData.type === "boolean"
                spacing: Studio.Theme.space8
                StudioTextField {
                    id: exprField
                    Layout.fillWidth: true
                    text: goal.modelData.expression || ""
                    placeholderText: "Biểu thức logic, ví dụ: goal1 and (goal2 or not goal3)"
                    Accessible.name: "Biểu thức logic"
                    onEditingFinished: page.editor.updateNestedEntry("assessment", "goals", goal.index, "expression", text.trim())
                }
                Label {
                    text: "Toán tử: and, or, not, and_not, or_not, dấu ngoặc ( )"
                    font.pixelSize: Studio.Theme.bodySmall
                    color: Studio.Theme.textOnSurfaceVariant
                }
                Flow {
                    Layout.fillWidth: true
                    spacing: Studio.Theme.space4
                    Repeater {
                        model: ["and", "or", "not", "(", ")"]
                        delegate: StudioButton {
                            required property var modelData
                            text: modelData
                            flat: true
                            onClicked: {
                                const current = exprField.text.trim();
                                const addition = (modelData === "(" || modelData === ")" || !current) ? modelData : (" " + modelData + " ");
                                const updated = current + addition;
                                exprField.text = updated;
                                page.editor.updateNestedEntry("assessment", "goals", goal.index, "expression", updated.trim());
                            }
                        }
                    }
                    Repeater {
                        model: page.results.concat(page.entries.slice(0, goal.index))
                        delegate: StudioButton {
                            required property var modelData
                            text: modelData.id
                            flat: true
                            outlined: true
                            onClicked: {
                                const current = exprField.text.trim();
                                const updated = current ? (current + " " + modelData.id) : modelData.id;
                                exprField.text = updated;
                                page.editor.updateNestedEntry("assessment", "goals", goal.index, "expression", updated.trim());
                            }
                        }
                    }
                }
            }
            Repeater {
                model: page.results
                delegate: CheckBox {
                    id: condition
                    required property var modelData
                    Layout.fillWidth: true
                    visible: goal.modelData.type !== "compare" && goal.modelData.type !== "boolean"
                    text: modelData.id
                    checked: (goal.modelData.results || []).includes(modelData.id)
                    onToggled: {
                        const selected = (goal.modelData.results || []).filter(identifier => identifier !== condition.modelData.id);
                        if (checked) selected.push(condition.modelData.id);
                        page.editor.updateNestedEntry("assessment", "goals", goal.index, "results", selected);
                    }
                }
            }
        }
    }
}
