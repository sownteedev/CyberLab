pragma ComponentBehavior: Bound
import QtQuick
import QtQuick.Controls.Basic
import QtQuick.Layouts
import "../.."
import "../.." as Studio
import "../../models/Checkwork.js" as Checks
import "../../models/Messages.js" as Messages

ScrollView {
    id: details

    property var report: null

    clip: true
    contentWidth: availableWidth

    ColumnLayout {
        spacing: Studio.Theme.space12
        width: details.availableWidth

        SectionHeader {
            Layout.fillWidth: true
            iconName: details.report ? Checks.statusIcon(details.report.status) : "description"
            subtitle: details.report ? details.report.lab_name + " · v" + details.report.lab_version : "Chọn một báo cáo hoặc kiểm tra bài đang chạy."
            title: details.report ? Checks.statusText(details.report.status) : "Chưa có kết quả"
            titleSize: Studio.Theme.titleMedium
        }
        Repeater {
            model: details.report ? (details.report.goals || []).concat(details.report.results || []) : []

            delegate: StudioSurface {
                id: criterion

                required property var modelData

                Layout.fillWidth: true
                color: Studio.Theme.surfaceContainer
                implicitHeight: criterionContent.implicitHeight + Studio.Theme.space24

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
                            color: Studio.Theme.textOnSurface
                            font.pixelSize: Studio.Theme.bodyMedium
                            text: criterion.modelData.description || criterion.modelData.id
                            textFormat: Text.PlainText
                            wrapMode: Text.Wrap
                        }
                        StatusBadge {
                            iconName: Checks.statusIcon(criterion.modelData.status)
                            text: Checks.statusText(criterion.modelData.status)
                        }
                    }
                    Label {
                        Layout.fillWidth: true
                        color: Studio.Theme.textOnSurfaceVariant
                        font.pixelSize: Studio.Theme.bodySmall
                        text: (criterion.modelData.node || "") + " / " + (criterion.modelData.path || "")
                        textFormat: Text.PlainText
                        visible: !!criterion.modelData.node
                        wrapMode: Text.WrapAnywhere
                    }
                    Label {
                        id: capturedValue

                        readonly property string formatted: criterion.modelData.value === undefined || criterion.modelData.value === null ? "" : JSON.stringify(criterion.modelData.value)

                        Layout.fillWidth: true
                        color: Studio.Theme.textOnSurfaceVariant
                        elide: Text.ElideRight
                        font.pixelSize: Studio.Theme.bodySmall
                        maximumLineCount: 4
                        objectName: "checkwork-value-" + criterion.modelData.id
                        text: "Giá trị thu được: " + capturedValue.formatted.slice(0, 512) + (capturedValue.formatted.length > 512 ? "…" : "")
                        textFormat: Text.PlainText
                        visible: criterion.modelData.value !== undefined && criterion.modelData.value !== null
                        wrapMode: Text.WrapAnywhere
                    }
                    Label {
                        Layout.fillWidth: true
                        color: Studio.Theme.textOnSurfaceVariant
                        font.pixelSize: Studio.Theme.bodySmall
                        text: criterion.modelData.status === "FAIL" && criterion.modelData.hint ? criterion.modelData.hint : Messages.text(criterion.modelData.message)
                        Studio.ErrorNotifier { message: criterion.modelData.status === "ERROR" ? criterion.modelData.message || "" : "" }
                        textFormat: Text.PlainText
                        visible: text.length > 0
                        wrapMode: Text.Wrap
                    }
                    Studio.EditorDisclosure {
                        id: timelineDetails
                        title: "Mốc thời gian · " + (criterion.modelData.instances || []).length
                        iconName: "description"
                        visible: (criterion.modelData.instances || []).length > 0
                        objectName: "checkwork-instances-" + criterion.modelData.id
                        Repeater {
                            model: timelineDetails.expanded ? criterion.modelData.instances || [] : []
                            delegate: Label {
                                required property var modelData
                                Layout.fillWidth: true
                                color: Studio.Theme.textOnSurfaceVariant
                                font.pixelSize: Studio.Theme.bodySmall
                                text: (modelData.timestamp || (modelData.start + " → " + (modelData.end || "chưa kết thúc")))
                                    + (modelData.clock === "capture-local" ? " (giờ bản ghi)" : "")
                                    + " · " + String(modelData.value).slice(0, 512)
                                textFormat: Text.PlainText
                                wrapMode: Text.WrapAnywhere
                            }
                        }
                    }
                }
            }
        }
        SectionHeader {
            Layout.fillWidth: true
            subtitle: details.report && details.report.quiz ? details.report.quiz.created_at : ""
            title: "Câu hỏi đã nộp"
            titleSize: Studio.Theme.titleMedium
            visible: !!details.report && !!details.report.quiz
        }
        Repeater {
            model: details.report && details.report.quiz ? details.report.quiz.questions || [] : []

            delegate: Label {
                required property var modelData

                Layout.fillWidth: true
                color: Studio.Theme.textOnSurfaceVariant
                font.pixelSize: Studio.Theme.bodySmall
                text: modelData.id + " · " + Checks.statusText(modelData.status) + (modelData.selected === null ? "" : " · Lựa chọn " + (modelData.selected + 1)) + (modelData.explanation ? "\n" + modelData.explanation : "")
                textFormat: Text.PlainText
                wrapMode: Text.WordWrap
            }
        }
        SectionHeader {
            Layout.fillWidth: true
            title: "File bài nộp"
            titleSize: Studio.Theme.titleMedium
            visible: !!details.report && (details.report.artifacts || []).length > 0
        }
        Repeater {
            model: details.report ? details.report.artifacts || [] : []

            delegate: Label {
                required property var modelData

                Layout.fillWidth: true
                color: Studio.Theme.textOnSurfaceVariant
                font.pixelSize: Studio.Theme.bodySmall
                text: modelData.node + " / " + modelData.path + " — " + Checks.statusText(modelData.status)
                textFormat: Text.PlainText
                wrapMode: Text.WrapAnywhere
            }
        }
        Label {
            Layout.fillWidth: true
            color: Studio.Theme.error
            font.pixelSize: Studio.Theme.bodySmall
            text: "Bằng chứng chưa đầy đủ. Gói xuất sẽ ghi rõ file thiếu hoặc lỗi thu thập."
            visible: !!details.report && details.report.submission_ready === false
            wrapMode: Text.WordWrap
        }
    }
}
