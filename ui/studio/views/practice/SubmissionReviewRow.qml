pragma ComponentBehavior: Bound
import QtQuick
import QtQuick.Controls.Basic
import QtQuick.Layouts
import "../.."
import "../.." as Studio
import "../../models/Messages.js" as Messages
import "../../models/Checkwork.js" as Checkwork

StudioSurface {
    id: row

    required property var modelData
    readonly property bool passed: modelData.valid && modelData.status === "PASS"
    readonly property bool failed: modelData.valid && modelData.status === "FAIL"
    readonly property bool neutral: modelData.valid && !passed && !failed

    color: !modelData.valid || failed ? Studio.Theme.errorContainer : Studio.Theme.surfaceContainer
    implicitHeight: content.implicitHeight + Studio.Theme.space24

    RowLayout {
        id: content

        anchors.fill: parent
        anchors.margins: Studio.Theme.space12
        spacing: Studio.Theme.space12

        Icon {
            Layout.alignment: Qt.AlignTop
            color: row.passed ? Studio.Theme.success : row.failed ? Studio.Theme.error : row.neutral ? Studio.Theme.textOnSurfaceVariant : Studio.Theme.error
            name: row.passed ? "check_circle" : row.failed ? "cancel" : row.neutral ? "info" : "error"
            size: Studio.Theme.iconSmall
        }
        ColumnLayout {
            Layout.fillWidth: true
            Layout.minimumWidth: 0
            spacing: Studio.Theme.space4

            Label {
                Layout.fillWidth: true
                color: Studio.Theme.textOnSurface
                elide: Text.ElideMiddle
                font.pixelSize: Studio.Theme.titleSmall
                text: row.modelData.filename || ""
                textFormat: Text.PlainText
            }
            Label {
                Layout.fillWidth: true
                color: row.modelData.valid ? Studio.Theme.textOnSurfaceVariant : Studio.Theme.textOnErrorContainer
                elide: Text.ElideRight
                font.pixelSize: Studio.Theme.bodySmall
                text: row.modelData.valid ? (row.modelData.lab_name || "") + " · v" + (row.modelData.lab_version || "") : Messages.text(row.modelData.error)
                Studio.ErrorNotifier { message: !row.modelData.valid ? row.modelData.error || "" : "" }
                textFormat: Text.PlainText
            }
            Label {
                Layout.fillWidth: true
                color: Studio.Theme.textOnSurface
                font.pixelSize: Studio.Theme.bodySmall
                text: row.modelData.valid ? Checkwork.statusText(row.modelData.status) + " · Mục tiêu " + (row.modelData.goals ? row.modelData.goals.passed + "/" + row.modelData.goals.total : "0/0") + " · Điều kiện " + (row.modelData.results ? row.modelData.results.passed + "/" + row.modelData.results.total : "0/0") + (row.modelData.quiz ? " · Quiz " + row.modelData.quiz.correct + "/" + row.modelData.quiz.graded : "") : ""
                textFormat: Text.PlainText
                visible: row.modelData.valid
                wrapMode: Text.WordWrap
            }
            Label {
                Layout.fillWidth: true
                color: Studio.Theme.textOnSurfaceVariant
                font.pixelSize: Studio.Theme.bodySmall
                text: row.modelData.valid ? (row.modelData.created_at || "") + " · Bằng chứng: " + (row.modelData.evidence_count || 0) + (row.modelData.submission_ready ? " · Đủ file nộp" : " · Thiếu/lỗi file nộp") : ""
                textFormat: Text.PlainText
                visible: row.modelData.valid
                wrapMode: Text.WordWrap
            }
            Label {
                Layout.fillWidth: true
                ToolTip.text: text
                ToolTip.visible: digestHover.hovered
                color: Studio.Theme.textOnSurfaceVariant
                elide: Text.ElideMiddle
                font.pixelSize: Studio.Theme.labelSmall
                text: row.modelData.valid && row.modelData.lab_digest ? "Lab digest: " + row.modelData.lab_digest : ""
                textFormat: Text.PlainText
                visible: row.modelData.valid

                HoverHandler {
                    id: digestHover
                }
            }
        }
    }
}
