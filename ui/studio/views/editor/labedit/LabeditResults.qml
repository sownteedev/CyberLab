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
    readonly property var entries: (document.assessment || {}).results || []
    readonly property var fieldTypes: ["token", "parens", "quotes", "slash", "group"]
    readonly property var collectionTypes: ["token", "parens", "quotes", "slash", "group", "search", "line_count", "checksum", "size", "time_delim", "contains", "file_regex", "string_count", "command_count", "param"]
    readonly property var collectionLabels: ["TOKEN · Tách từ", "PARENS · Ngoặc đơn", "QUOTES · Nháy kép", "SLASH · Tách dấu /", "GROUP · Nhóm regex", "SEARCH · Mẫu tìm kiếm", "LINE_COUNT · Số dòng", "CHECKSUM · MD5", "SIZE · Số byte", "TIME_DELIM · Khoảng thực thi", "CONTAINS · Chứa chuỗi", "FILE_REGEX · Khớp regex", "STRING_COUNT · Đếm chuỗi", "COMMAND_COUNT · Đếm lệnh", "PARAM · Tham số lệnh"]
    readonly property var lineTypes: ["line", "starts_with", "contains", "regex", "previous_starts_with"]
    readonly property var nodeIds: (document.nodes || []).map(node => node.id)
    readonly property var operatorLabels: ["File/thư mục tồn tại", "Nội dung chứa", "Nội dung bằng", "Có dòng chứa", "Khớp regex", "Dung lượng nhỏ hơn", "Dung lượng bằng", "Số dòng bằng", "SHA-256 bằng", "MD5 bằng", "Đếm chuỗi", "Trích xuất và so sánh", "Trích xuất giá trị (cũ)", "Thu thập Result"]
    readonly property var operators: ["exists", "contains", "equals", "line_contains", "regex", "size_less_than", "size_equals", "line_count_equals", "sha256_equals", "md5_equals", "string_count_equals", "field_equals", "extract", "collect"]

    spacing: Studio.Theme.space12

    RowLayout {
        Layout.fillWidth: true

        SectionHeader {
            Layout.fillWidth: true
            subtitle: "Lấy giá trị từ file để dùng trong Goals."
            title: "Results"
            titleSize: Studio.Theme.titleMedium
        }
        StudioButton {
            enabled: page.entries.length < 64 && page.nodeIds.length > 0
            iconName: "add"
            text: "Thêm"
            objectName: "addAssessmentResult"

            onClicked: page.editor.addNestedEntry("assessment", "results", {
                id: Model.nextId(Labedit.assessmentEntries(page.document), "result"),
                node: page.nodeIds[0],
                path: "answer.txt",
                operator: "collect",
                field_type: "token", field_id: "ALL", line_type: "none"
            }, 64)
        }
    }
        Studio.StudioCheckBox {
        checked: (page.document.settings || {}).checkwork === true
        text: "Cho phép tự kiểm tra bài làm"
        objectName: "assessmentCheckworkEnabled"
        onToggled: page.editor.changePath(["settings", "checkwork"], checked)
    }
    Repeater {
        model: page.entries

        delegate: LabeditCard {
            id: result

            required property int index
            required property var modelData

            Layout.fillWidth: true
            title: modelData.id
            fieldColumns: width >= 900 ? 3 : width >= 560 ? 2 : 1
            fieldsObjectName: "resultFields-" + index
            readonly property bool extracts: ["extract", "field_equals"].includes(modelData.operator)
            readonly property bool collects: modelData.operator === "collect"
            readonly property bool selectsLine: extracts || (collects && ["token", "parens", "quotes", "slash", "group", "search"].includes(modelData.field_type))
            readonly property bool hasField: extracts || (collects && !["line_count", "checksum", "size", "time_delim"].includes(modelData.field_type))
            readonly property var availableLines: collects ? ["none"].concat(page.lineTypes) : page.lineTypes

            onRemoveRequested: page.editor.removeNestedEntry("assessment", "results", index)

            Studio.EditorField {
                label: "Tên Result"
                StudioTextField {
                    Accessible.name: placeholderText
                    Layout.fillWidth: true
                    placeholderText: "Tên Result"
                    text: result.modelData.id

                    onEditingFinished: page.editor.updateNestedEntry("assessment", "results", result.index, "id", text.trim())
                }
            }

            Studio.EditorField {
                label: "Máy"
                StudioComboBox {
                    Accessible.name: "Máy cần kiểm tra"
                    Layout.fillWidth: true
                    currentIndex: model.indexOf(result.modelData.node)
                    model: page.nodeIds

                    onActivated: page.editor.updateNestedEntry("assessment", "results", result.index, "node", currentText)
                }
            }
            Studio.EditorField {
                label: result.collects && result.modelData.field_type === "time_delim" ? "Tên chương trình đã ghi stdout" : "File trong home/workspace"
                StudioTextField {
                    Accessible.name: placeholderText
                    Layout.fillWidth: true
                    placeholderText: "Đường dẫn trong home/workspace"
                    text: result.modelData.path

                    onEditingFinished: page.editor.updateNestedEntry("assessment", "results", result.index, "path", text.trim())
                }
            }
            Studio.EditorField {
                label: "Cách lấy kết quả"
                StudioComboBox {
                    Accessible.name: "Phép kiểm tra"
                    Layout.fillWidth: true
                    currentIndex: page.operators.indexOf(result.modelData.operator)
                    model: page.operatorLabels
                    objectName: "labedit-result-operator-" + result.index

                    onActivated: page.editor.updateNestedEntry("assessment", "results", result.index, "operator", page.operators[currentIndex])
                }
            }
            Studio.EditorField {
                label: "Giá trị cần đạt"
                visible: !["exists", "extract", "field_equals", "collect"].includes(result.modelData.operator)
                StudioTextField {
                    Accessible.name: placeholderText
                    Layout.fillWidth: true
                    placeholderText: "Giá trị cần đạt"
                    text: result.modelData.expected === undefined ? "" : String(result.modelData.expected)

                    onEditingFinished: page.editor.updateNestedEntry("assessment", "results", result.index, "expected", text)
                }
            }
            Studio.EditorField {
                label: "Chuỗi cần đếm"
                visible: result.modelData.operator === "string_count_equals"
                StudioTextField {
                    Accessible.name: placeholderText
                    Layout.fillWidth: true
                    placeholderText: "Chuỗi cần đếm"
                    text: result.modelData.field_id === undefined ? "" : String(result.modelData.field_id)

                    onEditingFinished: page.editor.updateNestedEntry("assessment", "results", result.index, "field_id", text)
                }
            }
            Studio.EditorField {
                label: "Kiểu trường"
                visible: result.extracts || result.collects
                StudioComboBox {
                    Accessible.name: "Kiểu trường cần lấy"
                    Layout.fillWidth: true
                    currentIndex: Math.max(0, (result.collects ? page.collectionTypes : page.fieldTypes).indexOf(result.modelData.field_type))
                    model: result.collects ? page.collectionLabels : ["Tách theo khoảng trắng", "Trong ngoặc đơn", "Trong dấu nháy", "Giữa dấu /", "Nhóm regex"]
                    objectName: "labedit-result-field-type-" + result.index

                    onActivated: page.editor.updateNestedEntry("assessment", "results", result.index, "field_type", (result.collects ? page.collectionTypes : page.fieldTypes)[currentIndex])
                }
            }
            Studio.EditorField {
                label: "Trường / Field ID"
                visible: result.hasField
                StudioTextField {
                    Accessible.name: placeholderText
                    Layout.fillWidth: true
                    placeholderText: result.modelData.field_type === "group" ? "Số group regex, bắt đầu từ 0"
                        : result.modelData.field_type === "search" ? "Ví dụ: frame.number=={:d}"
                        : result.modelData.field_type === "param" ? "0: tên lệnh; 1, 2…: tham số"
                        : ["contains", "file_regex", "string_count", "command_count"].includes(result.modelData.field_type) ? "Chuỗi, regex hoặc lệnh cần tìm"
                        : "Số trường, ALL hoặc LAST"
                    objectName: "labedit-result-field-id-" + result.index
                    text: result.modelData.field_id === undefined ? "" : String(result.modelData.field_id)

                    onEditingFinished: page.editor.updateNestedEntry("assessment", "results", result.index, "field_id", text)
                }
            }
            Studio.EditorField {
                label: "Chọn dòng"
                visible: result.selectsLine
                StudioComboBox {
                    Accessible.name: "Kiểu chọn dòng"
                    Layout.fillWidth: true
                    currentIndex: Math.max(0, result.availableLines.indexOf(result.modelData.line_type))
                    model: (result.collects ? ["NONE · Toàn bộ nội dung"] : []).concat(["Theo số dòng", "Bắt đầu bằng", "Có chứa", "Khớp regex", "Dòng trước chuỗi"])
                    objectName: "labedit-result-line-type-" + result.index

                    onActivated: page.editor.updateNestedEntry("assessment", "results", result.index, "line_type", result.availableLines[currentIndex])
                }
            }
            Studio.EditorField {
                label: "Dòng"
                visible: result.selectsLine && result.modelData.line_type !== "none"
                StudioTextField {
                    Accessible.name: placeholderText
                    Layout.fillWidth: true
                    placeholderText: result.modelData.line_type === "line" ? "Số dòng bắt đầu từ 1" : "Chuỗi hoặc regex chọn dòng"
                    text: result.modelData.line_id === undefined ? "" : String(result.modelData.line_id)

                    onEditingFinished: page.editor.updateNestedEntry("assessment", "results", result.index, "line_id", text)
                }
            }
            Studio.EditorField {
                label: "Mốc thời gian"
                visible: result.collects && ["contains", "file_regex", "search"].includes(result.modelData.field_type)
                StudioComboBox {
                    Accessible.name: "Mốc thời gian của Result"
                    Layout.fillWidth: true
                    model: ["File · Kiểm tra một lần", "LOG_TS · Từng sự kiện", "LOG_RANGE · Khoảng giữa sự kiện"]
                    currentIndex: Math.max(0, ["file", "log_ts", "log_range"].indexOf(result.modelData.timestamp_type || "file"))
                    objectName: "labedit-result-timestamp-" + result.index
                    onActivated: page.editor.updateNestedEntry("assessment", "results", result.index, "timestamp_type", ["file", "log_ts", "log_range"][currentIndex])
                }
            }
            Label {
                Layout.fillWidth: true
                Layout.columnSpan: result.fieldColumns
                visible: result.collects && (["param", "time_delim", "search"].includes(result.modelData.field_type) || ["log_ts", "log_range"].includes(result.modelData.timestamp_type))
                text: ["log_ts", "log_range"].includes(result.modelData.timestamp_type) ? "Log cần thời gian ISO-8601 kèm múi giờ; ví dụ 2026-11-21T10:00:00Z."
                    : result.modelData.field_type === "param" ? "Đọc file đã ghi PROGRAM_ARGUMENTS (...); chưa tự ghi lệnh terminal."
                    : result.modelData.field_type === "time_delim" ? "Đọc các file tên-lệnh.stdout.YYYYMMDDhhmmss trong workspace; chưa tự ghi stdout."
                    : "SEARCH hỗ trợ {}, {:d}, {:f}, {:w}, {:S}, {:s}, {:x}."
                color: Studio.Theme.textOnSurfaceVariant
                font.pixelSize: Studio.Theme.bodySmall
                wrapMode: Text.Wrap
                textFormat: Text.PlainText
            }
            Studio.EditorField {
                label: "Giá trị cần đạt"
                visible: result.modelData.operator === "field_equals"
                StudioTextField {
                    Accessible.name: placeholderText
                    Layout.fillWidth: true
                    placeholderText: "Giá trị trường cần đạt"
                    text: result.modelData.expected === undefined ? "" : String(result.modelData.expected)

                    onEditingFinished: page.editor.updateNestedEntry("assessment", "results", result.index, "expected", text)
                }
            }

            Studio.EditorDisclosure {
                title: "Mô tả và gợi ý"
                Layout.columnSpan: result.fieldColumns
                Studio.EditorField {
                    label: "Mô tả"
                    StudioTextField {
                        Accessible.name: placeholderText
                        Layout.fillWidth: true
                        placeholderText: "Yêu cầu hiển thị cho người học"
                        text: result.modelData.description || ""

                        onEditingFinished: page.editor.updateNestedEntry("assessment", "results", result.index, "description", text)
                    }
                }
                Studio.EditorField {
                    label: "Gợi ý"
                    StudioTextField {
                        Accessible.name: placeholderText
                        Layout.fillWidth: true
                        placeholderText: "Gợi ý khi chưa đạt"
                        text: result.modelData.hint || ""

                        onEditingFinished: page.editor.updateNestedEntry("assessment", "results", result.index, "hint", text)
                    }
                }
            }
        }
    }
}
