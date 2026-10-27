import QtQuick
import QtQuick.Controls.Basic
import QtQuick.Layouts
import "../.."
import "../.." as Studio

ColumnLayout {
    id: review
    required property var editor
    readonly property bool current: !!editor.report && !!editor.draft && !editor.dirty
        && editor.report.revision === editor.draft.revision && editor.report.digest === editor.draft.digest
    spacing: Studio.Theme.space16
    SectionHeader { Layout.fillWidth: true; title: "Kiểm tra"; subtitle: "Cấu hình và xuất bản" }
    Repeater {
        model: [{title: "Schema", stages: ["syntax", "schema"]},
                {title: "Policy", stages: ["policy"]},
                {title: "Cấu hình Lab", stages: ["lab"]}]
        ColumnLayout {
            id: checkRow
            required property var modelData
            readonly property var issues: review.current ? (review.editor.report.issues || []).filter(issue => modelData.stages.includes(issue.stage)) : []
            Layout.fillWidth: true
            spacing: Studio.Theme.space4
            Label {
                Layout.fillWidth: true
                text: checkRow.modelData.title
                color: Studio.Theme.textOnSurface
                font.pixelSize: Studio.Theme.titleSmall
                font.weight: Font.DemiBold
            }
            Label {
                Layout.fillWidth: true
                text: !review.current ? "Chưa kiểm tra bản hiện tại" : checkRow.issues.length ? "Không hợp lệ"
                    : review.editor.report.valid ? "Hợp lệ" : "Chưa xác nhận đầy đủ"
                color: checkRow.issues.length ? Studio.Theme.error : Studio.Theme.textOnSurfaceVariant
                font.pixelSize: Studio.Theme.bodySmall
                wrapMode: Text.WordWrap
            }
            Repeater {
                model: checkRow.issues
                InlineError {
                    required property var modelData
                    Layout.fillWidth: true
                    message: modelData.path + ": " + modelData.message
                }
            }
        }
    }
    Label {
        text: "Tài nguyên"
        color: Studio.Theme.textOnSurface
        font.pixelSize: Studio.Theme.titleSmall
        font.weight: Font.DemiBold
    }
    Label {
        Layout.fillWidth: true
        text: review.current && review.editor.report.valid
            ? "Tài nguyên hợp lệ trong snapshot đã kiểm tra."
            : "Chưa xác nhận tài nguyên. Daemon gộp lỗi ánh xạ/tài nguyên vào bước cấu hình Lab."
        color: Studio.Theme.textOnSurfaceVariant
        font.pixelSize: Studio.Theme.bodySmall
        wrapMode: Text.WordWrap
    }
    Label {
        text: "Runtime"
        color: Studio.Theme.textOnSurface
        font.pixelSize: Studio.Theme.titleSmall
        font.weight: Font.DemiBold
    }
    Label {
        Layout.fillWidth: true
        text: review.editor.runtimeReport && review.editor.runtimeReport.ready
            ? "Đã xác minh runtime: container và tài nguyên sẵn sàng."
            : review.editor.runtimeReport && !review.editor.runtimeReport.ready
            ? "Kiểm tra runtime không đạt. Kiểm tra cấu hình image/account hoặc tài nguyên."
            : "Chưa xác minh runtime. Bấm nút dưới để kiểm tra container thực tế."
        color: review.editor.runtimeReport && review.editor.runtimeReport.ready ? Studio.Theme.success
            : review.editor.runtimeReport ? Studio.Theme.error : Studio.Theme.warning
        font.pixelSize: Studio.Theme.bodySmall
        wrapMode: Text.WordWrap
    }
    Repeater {
        model: review.editor.runtimeReport && review.editor.runtimeReport.issues ? review.editor.runtimeReport.issues : []
        InlineError {
            required property var modelData
            Layout.fillWidth: true
            message: modelData.path + ": " + modelData.message
        }
    }
    StudioButton {
        Layout.fillWidth: true
        text: "Kiểm tra runtime"
        enabled: !!review.editor.document && !review.editor.backend.busy
        onClicked: review.editor.checkRuntime()
    }
    Label {
        Layout.fillWidth: true
        text: review.editor.draft ? "Revision " + review.editor.draft.revision + "\n" + review.editor.draft.digest : "Chưa có bản nháp"
        textFormat: Text.PlainText
        color: Studio.Theme.textOnSurfaceVariant
        font.pixelSize: Studio.Theme.bodySmall
        wrapMode: Text.WrapAnywhere
    }
    StudioButton {
        Layout.fillWidth: true
        text: "Kiểm tra bản nháp"
        enabled: !!review.editor.document && !review.editor.backend.busy
        onClicked: review.editor.validate()
    }
    StudioButton {
        Layout.fillWidth: true
        visible: !review.editor.isInstalledEdit
        text: "Xem lại để xuất bản"
        highlighted: true
        enabled: review.current && review.editor.report.valid && !review.editor.backend.busy
        onClicked: review.editor.reviewPublication()
    }
    StudioButton {
        Layout.fillWidth: true
        visible: review.editor.isInstalledEdit
        text: "Cập nhật bài đã cài đặt"
        highlighted: true
        enabled: review.current && review.editor.report.valid && !review.editor.backend.busy
        onClicked: review.editor.reviewUpdate()
    }
    Label {
        Layout.fillWidth: true
        text: "Chỉ xuất bản đúng revision/digest đã duyệt; không ghi đè bài có sẵn."
        color: Studio.Theme.textOnSurfaceVariant
        font.pixelSize: Studio.Theme.bodySmall
        wrapMode: Text.WordWrap
    }
}
