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
    readonly property var entries: (document.assessment || {}).goals || []
    readonly property var results: (document.assessment || {}).results || []
    readonly property var comparisons: ["string_equal", "string_diff", "string_contains", "string_start", "string_end", "integer_equal", "integer_greater", "integer_less", "hash_equal"]

    spacing: Studio.Theme.space12

    RowLayout {
        Layout.fillWidth: true

        SectionHeader {
            Layout.fillWidth: true
            subtitle: "So sánh Results để kiểm tra bài làm."
            title: "Goals"
            titleSize: Studio.Theme.titleMedium
        }
        StudioButton {
            enabled: page.entries.length < 32 && page.results.length > 0
            iconName: "add"
            text: "Thêm"
            objectName: "addAssessmentGoal"

            onClicked: page.editor.addNestedEntry("assessment", "goals", {
                id: Model.nextId(Labedit.assessmentEntries(page.document), "goal"),
                type: "compare", result: page.results[0].id,
                operator: "string_equal", expected: ""
            }, 32)
        }
    }
    Repeater {
        model: page.entries

        delegate: LabeditCard {
            id: goal

            required property int index
            required property var modelData

            Layout.fillWidth: true
            title: modelData.id
            fieldColumns: width >= 900 ? 3 : width >= 560 ? 2 : 1
            fieldsObjectName: "goalFields-" + index

            onRemoveRequested: page.editor.removeNestedEntry("assessment", "goals", index)

            Studio.EditorField {
                label: "Tên Goal"
                StudioTextField {
                    Accessible.name: placeholderText
                    Layout.fillWidth: true
                    placeholderText: "Mã mục tiêu"
                    text: goal.modelData.id

                    onEditingFinished: page.editor.updateNestedEntry("assessment", "goals", goal.index, "id", text.trim())
                }
            }

            Studio.EditorField {
                label: "Kiểu mục tiêu"
                StudioComboBox {
                    Accessible.name: "Kiểu mục tiêu"
                    Layout.fillWidth: true
                    currentIndex: goal.modelData.type === "compare" ? 1 : goal.modelData.type === "count" ? 2 : goal.modelData.type === "boolean" ? 3 : 0
                    model: ["Nhóm điều kiện", "So sánh giá trị", "Đếm điều kiện", "Biểu thức logic"]
                    objectName: "labedit-goal-type-" + goal.index

                    onActivated: page.editor.updateNestedEntry("assessment", "goals", goal.index, "type", currentIndex === 1 ? "compare" : currentIndex === 2 ? "count" : currentIndex === 3 ? "boolean" : "group")
                }
            }
            Studio.EditorField {
                label: "Cách kết hợp"
                visible: !goal.modelData.type || goal.modelData.type === "group"
                StudioComboBox {
                    Accessible.name: "Cách kết hợp"
                    Layout.fillWidth: true
                    currentIndex: goal.modelData.mode === "any" ? 1 : 0
                    model: ["Đạt tất cả điều kiện", "Đạt ít nhất một điều kiện"]

                    onActivated: page.editor.updateNestedEntry("assessment", "goals", goal.index, "mode", currentIndex === 0 ? "all" : "any")
                }
            }
            Studio.EditorField {
                label: "Phép so sánh"
                visible: goal.modelData.type === "compare"
                StudioComboBox {
                    Accessible.name: "Phép so sánh"
                    Layout.fillWidth: true
                    currentIndex: page.comparisons.indexOf(goal.modelData.operator || "")
                    model: ["Chuỗi bằng", "Chuỗi khác", "Chuỗi chứa", "Bắt đầu bằng", "Kết thúc bằng", "Số bằng", "Số lớn hơn", "Số nhỏ hơn", "Mã băm bằng"]

                    onActivated: page.editor.updateNestedEntry("assessment", "goals", goal.index, "operator", page.comparisons[currentIndex])
                }
            }
            Studio.EditorField {
                label: "Result"
                visible: goal.modelData.type === "compare"
                StudioComboBox {
                    Accessible.name: "Giá trị đầu tiên"
                    Layout.fillWidth: true
                    currentIndex: model.indexOf(goal.modelData.result || "")
                    model: page.results.map(entry => entry.id)

                    onActivated: page.editor.updateNestedEntry("assessment", "goals", goal.index, "result", currentText)
                }
            }
            Studio.EditorField {
                label: "Đối chiếu với"
                visible: goal.modelData.type === "compare"
                StudioComboBox {
                    Accessible.name: "Nguồn giá trị thứ hai"
                    Layout.fillWidth: true
                    currentIndex: goal.modelData.other ? 1 : 0
                    enabled: page.results.length > 0
                    model: ["Giá trị nhập", "Kết quả khác"]
                    objectName: "labedit-goal-source-" + goal.index

                    onActivated: if (currentIndex === 0)
                        page.editor.updateNestedEntry("assessment", "goals", goal.index, "other", null)
                    else
                        page.editor.updateNestedEntry("assessment", "goals", goal.index, "other", page.results.length > 1 ? page.results[1].id : page.results[0].id)
                }
            }
            Studio.EditorField {
                label: "Giá trị cần đạt"
                visible: goal.modelData.type === "compare" && !goal.modelData.other
                StudioTextField {
                    Accessible.name: placeholderText
                    Layout.fillWidth: true
                    placeholderText: "Giá trị kỳ vọng"
                    text: goal.modelData.expected === undefined ? "" : String(goal.modelData.expected)

                    onEditingFinished: page.editor.updateNestedEntry("assessment", "goals", goal.index, "expected", text)
                }
            }
            Studio.EditorField {
                label: "Result đối chiếu"
                visible: goal.modelData.type === "compare" && !!goal.modelData.other
                StudioComboBox {
                    Accessible.name: "Kết quả đối chiếu"
                    Layout.fillWidth: true
                    currentIndex: model.indexOf(goal.modelData.other || "")
                    model: page.results.map(entry => entry.id)

                    onActivated: page.editor.updateNestedEntry("assessment", "goals", goal.index, "other", currentText)
                }
            }
            Studio.EditorField {
                label: "Ngưỡng"
                visible: goal.modelData.type === "count"
                StudioTextField {
                    Accessible.name: placeholderText
                    Layout.fillWidth: true
                    placeholderText: "Đạt nhiều hơn số lượng này"
                    text: goal.modelData.threshold === undefined ? "0" : String(goal.modelData.threshold)

                    onEditingFinished: page.editor.updateNestedEntry("assessment", "goals", goal.index, "threshold", text)
                }
            }
            ColumnLayout {
                Layout.fillWidth: true
                Layout.columnSpan: goal.fieldColumns
                spacing: Studio.Theme.space8
                visible: goal.modelData.type === "boolean"

                StudioTextField {
                    id: exprField

                    Accessible.name: "Biểu thức logic"
                    Layout.fillWidth: true
                    placeholderText: "Biểu thức logic, ví dụ: goal1 and (goal2 or not goal3)"
                    text: goal.modelData.expression || ""

                    onEditingFinished: page.editor.updateNestedEntry("assessment", "goals", goal.index, "expression", text.trim())
                }
                Label {
                    color: Studio.Theme.textOnSurfaceVariant
                    font.pixelSize: Studio.Theme.bodySmall
                    text: "Toán tử: and, or, not, and_not, or_not, dấu ngoặc ( )"
                }
                Flow {
                    Layout.fillWidth: true
                    spacing: Studio.Theme.space4

                    Repeater {
                        model: ["and", "or", "not", "(", ")"]

                        delegate: StudioButton {
                            required property var modelData

                            flat: true
                            text: modelData

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

                            flat: true
                            outlined: true
                            text: modelData.id

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

                    delegate: Studio.StudioCheckBox {
                    id: condition

                    required property var modelData

                    Layout.fillWidth: true
                    checked: (goal.modelData.results || []).includes(modelData.id)
                    text: modelData.id
                    visible: goal.modelData.type !== "compare" && goal.modelData.type !== "boolean"

                    onToggled: {
                        const selected = (goal.modelData.results || []).filter(identifier => identifier !== condition.modelData.id);
                        if (checked)
                            selected.push(condition.modelData.id);
                        page.editor.updateNestedEntry("assessment", "goals", goal.index, "results", selected);
                    }
                }
            }
            Studio.EditorDisclosure {
                title: "Mô tả"
                Layout.columnSpan: goal.fieldColumns
                Studio.EditorField {
                    label: "Mô tả"
                    StudioTextField {
                        Accessible.name: placeholderText
                        Layout.fillWidth: true
                        placeholderText: "Mô tả mục tiêu"
                        text: goal.modelData.description || ""

                        onEditingFinished: page.editor.updateNestedEntry("assessment", "goals", goal.index, "description", text)
                    }
                }
            }
        }
    }
}
