pragma ComponentBehavior: Bound
import QtQuick
import QtQuick.Controls.Basic
import QtQuick.Layouts
import "../.."
import "../.." as Studio

StudioSurface {
    id: row
    required property var modelData
    readonly property bool passed: modelData.valid && modelData.status === "PASS"
    implicitHeight: content.implicitHeight + Studio.Theme.space24
    color: modelData.valid ? Studio.Theme.surfaceContainer : Studio.Theme.errorContainer

    RowLayout {
        id: content
        anchors.fill: parent
        anchors.margins: Studio.Theme.space12
        spacing: Studio.Theme.space12
        Icon {
            Layout.alignment: Qt.AlignTop
            name: row.passed ? "check_circle" : row.modelData.valid ? "warning" : "error"
            size: Studio.Theme.iconSmall
            color: row.passed ? Studio.Theme.success : row.modelData.valid ? Studio.Theme.warning : Studio.Theme.error
        }
        ColumnLayout {
            Layout.fillWidth: true
            Layout.minimumWidth: 0
            spacing: Studio.Theme.space4
            Label {
                Layout.fillWidth: true
                text: row.modelData.filename || ""
                textFormat: Text.PlainText
                color: Studio.Theme.textOnSurface
                font.pixelSize: Studio.Theme.titleSmall
                elide: Text.ElideMiddle
            }
            Label {
                Layout.fillWidth: true
                text: row.modelData.valid ? (row.modelData.lab_name || "") + " · v" + (row.modelData.lab_version || "") : (row.modelData.error || "")
                textFormat: Text.PlainText
                color: row.modelData.valid ? Studio.Theme.textOnSurfaceVariant : Studio.Theme.textOnErrorContainer
                font.pixelSize: Studio.Theme.bodySmall
                elide: Text.ElideRight
            }
            Label {
                Layout.fillWidth: true
                visible: row.modelData.valid
                text: row.modelData.valid ? (row.modelData.status || "") + " · Mục tiêu "
                    + (row.modelData.goals ? row.modelData.goals.passed + "/" + row.modelData.goals.total : "0/0")
                    + " · Điều kiện "
                    + (row.modelData.results ? row.modelData.results.passed + "/" + row.modelData.results.total : "0/0")
                    + (row.modelData.quiz ? " · Quiz " + row.modelData.quiz.correct + "/" + row.modelData.quiz.graded : "") : ""
                textFormat: Text.PlainText
                color: Studio.Theme.textOnSurface
                font.pixelSize: Studio.Theme.bodySmall
                wrapMode: Text.WordWrap
            }
            Label {
                Layout.fillWidth: true
                visible: row.modelData.valid
                text: row.modelData.valid ? (row.modelData.created_at || "") + " · Bằng chứng: " + (row.modelData.evidence_count || 0)
                    + (row.modelData.submission_ready ? " · Đủ file nộp" : " · Thiếu/lỗi file nộp") : ""
                textFormat: Text.PlainText
                color: Studio.Theme.textOnSurfaceVariant
                font.pixelSize: Studio.Theme.bodySmall
                wrapMode: Text.WordWrap
            }
            Label {
                Layout.fillWidth: true
                visible: row.modelData.valid
                text: row.modelData.valid && row.modelData.lab_digest ? "Lab digest: " + row.modelData.lab_digest : ""
                textFormat: Text.PlainText
                color: Studio.Theme.textOnSurfaceVariant
                font.pixelSize: Studio.Theme.labelSmall
                elide: Text.ElideMiddle
                ToolTip.visible: digestHover.hovered
                ToolTip.text: text
                HoverHandler { id: digestHover }
            }
        }
    }
}
