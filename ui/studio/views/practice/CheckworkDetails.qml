pragma ComponentBehavior: Bound
import QtQuick
import QtQuick.Controls.Basic
import QtQuick.Layouts
import "../.."
import "../.." as Studio
import "../../models/Checkwork.js" as Checks

ScrollView {
    id: details
    property var report: null
    clip: true
    contentWidth: availableWidth

    ColumnLayout {
        width: details.availableWidth
        spacing: Studio.Theme.space12
        SectionHeader {
            Layout.fillWidth: true
            title: details.report ? Checks.statusText(details.report.status) : "Chưa có kết quả"
            titleSize: Studio.Theme.titleMedium
            iconName: details.report ? Checks.statusIcon(details.report.status) : "description"
            subtitle: details.report ? details.report.lab_name + " · v" + details.report.lab_version : "Chọn một báo cáo hoặc kiểm tra bài đang chạy."
        }
        Label {
            Layout.fillWidth: true
            text: "Kết quả tự kiểm tra tại thời điểm thu thập; không phải điểm thi được xác thực."
            color: Studio.Theme.textOnSurfaceVariant
            font.pixelSize: Studio.Theme.bodySmall
            wrapMode: Text.WordWrap
        }
        Repeater {
            model: details.report ? (details.report.goals || []).concat(details.report.results || []) : []
            delegate: StudioSurface {
                id: criterion
                required property var modelData
                Layout.fillWidth: true
                implicitHeight: criterionContent.implicitHeight + Studio.Theme.space24
                color: Studio.Theme.surfaceContainer
                ColumnLayout {
                    id: criterionContent
                    anchors.fill: parent
                    anchors.margins: Studio.Theme.space12
                    spacing: Studio.Theme.space4
                    RowLayout {
                        Layout.fillWidth: true
                        Label {
                            Layout.fillWidth: true
                            Layout.minimumWidth: 0
                            text: criterion.modelData.description || criterion.modelData.id
                            textFormat: Text.PlainText
                            wrapMode: Text.Wrap
                            color: Studio.Theme.textOnSurface
                            font.pixelSize: Studio.Theme.bodyMedium
                        }
                        StatusBadge {
                            text: Checks.statusText(criterion.modelData.status)
                            iconName: Checks.statusIcon(criterion.modelData.status)
                        }
                    }
                    Label {
                        Layout.fillWidth: true
                        visible: !!criterion.modelData.node
                        text: (criterion.modelData.node || "") + " / " + (criterion.modelData.path || "")
                        textFormat: Text.PlainText
                        wrapMode: Text.WrapAnywhere
                        color: Studio.Theme.textOnSurfaceVariant
                        font.pixelSize: Studio.Theme.bodySmall
                    }
                    Label {
                        id: capturedValue
                        readonly property string formatted: criterion.modelData.value === undefined || criterion.modelData.value === null
                            ? "" : JSON.stringify(criterion.modelData.value)
                        objectName: "checkwork-value-" + criterion.modelData.id
                        Layout.fillWidth: true
                        visible: criterion.modelData.value !== undefined && criterion.modelData.value !== null
                        text: "Giá trị thu được: " + capturedValue.formatted.slice(0, 512)
                            + (capturedValue.formatted.length > 512 ? "…" : "")
                        textFormat: Text.PlainText
                        wrapMode: Text.WrapAnywhere
                        maximumLineCount: 4
                        elide: Text.ElideRight
                        color: Studio.Theme.textOnSurfaceVariant
                        font.pixelSize: Studio.Theme.bodySmall
                    }
                    Label {
                        Layout.fillWidth: true
                        text: criterion.modelData.status === "FAIL" && criterion.modelData.hint
                            ? criterion.modelData.hint : criterion.modelData.message || ""
                        textFormat: Text.PlainText
                        visible: text.length > 0
                        wrapMode: Text.Wrap
                        color: Studio.Theme.textOnSurfaceVariant
                        font.pixelSize: Studio.Theme.bodySmall
                    }
                }
            }
        }
        SectionHeader {
            Layout.fillWidth: true
            visible: !!details.report && !!details.report.quiz
            title: "Câu hỏi đã nộp"
            titleSize: Studio.Theme.titleMedium
            subtitle: details.report && details.report.quiz ? details.report.quiz.created_at : ""
        }
        Repeater {
            model: details.report && details.report.quiz ? details.report.quiz.questions || [] : []
            delegate: Label {
                required property var modelData
                Layout.fillWidth: true
                text: modelData.id + " · " + Checks.statusText(modelData.status)
                    + (modelData.selected === null ? "" : " · Lựa chọn " + (modelData.selected + 1))
                    + (modelData.explanation ? "\n" + modelData.explanation : "")
                textFormat: Text.PlainText
                wrapMode: Text.WordWrap
                color: Studio.Theme.textOnSurfaceVariant
                font.pixelSize: Studio.Theme.bodySmall
            }
        }
        SectionHeader {
            Layout.fillWidth: true
            visible: !!details.report && (details.report.artifacts || []).length > 0
            title: "File bài nộp"
            titleSize: Studio.Theme.titleMedium
        }
        Repeater {
            model: details.report ? details.report.artifacts || [] : []
            delegate: Label {
                required property var modelData
                Layout.fillWidth: true
                text: modelData.node + " / " + modelData.path + " — " + Checks.statusText(modelData.status)
                textFormat: Text.PlainText
                wrapMode: Text.WrapAnywhere
                color: Studio.Theme.textOnSurfaceVariant
                font.pixelSize: Studio.Theme.bodySmall
            }
        }
        Label {
            Layout.fillWidth: true
            visible: !!details.report && details.report.submission_ready === false
            text: "Bằng chứng chưa đầy đủ. Gói xuất sẽ ghi rõ file thiếu hoặc lỗi thu thập."
            wrapMode: Text.WordWrap
            color: Studio.Theme.error
            font.pixelSize: Studio.Theme.bodySmall
        }
    }
}
