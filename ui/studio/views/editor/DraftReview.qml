pragma ComponentBehavior: Bound

import QtQuick
import QtQuick.Controls.Basic
import QtQuick.Layouts
import "../.." as Studio
import "../../models/Messages.js" as Messages

ColumnLayout {
    id: review
    required property var editor
    readonly property bool current: !!editor.report && !!editor.draft && !editor.dirty && editor.report.revision === editor.draft.revision && editor.report.digest === editor.draft.digest
    spacing: Studio.Theme.space16

    Studio.DraftFormCard {
        Layout.fillWidth: true
        title: qsTr("Cấu hình bản nháp")
        iconName: "check_circle"

        Repeater {
            model: [
                {title: qsTr("Định dạng cấu hình"), stages: ["syntax", "schema"]},
                {title: qsTr("Giới hạn cho phép"), stages: ["policy"]},
                {title: qsTr("Cấu hình Lab"), stages: ["lab"]}
            ]
            ColumnLayout {
                id: checkRow
                required property var modelData
                readonly property var issues: review.current ? (review.editor.report.issues || []).filter(issue => modelData.stages.includes(issue.stage)) : []
                Layout.fillWidth: true
                spacing: Studio.Theme.space8

                RowLayout {
                    Layout.fillWidth: true
                    spacing: Studio.Theme.space12
                    Studio.Icon {
                        name: review.current && !checkRow.issues.length && review.editor.report.valid ? "check_circle" : "description"
                        color: checkRow.issues.length ? Studio.Theme.error : review.current && review.editor.report.valid ? Studio.Theme.success : Studio.Theme.textOnSurfaceVariant
                        size: Studio.Theme.iconSmall
                    }
                    ColumnLayout {
                        Layout.fillWidth: true
                        spacing: Studio.Theme.space4
                        Label { color: Studio.Theme.textOnSurface; text: checkRow.modelData.title; font.weight: Font.DemiBold }
                        Label {
                            Layout.fillWidth: true
                            color: checkRow.issues.length ? Studio.Theme.error : Studio.Theme.textOnSurfaceVariant
                            font.pixelSize: Studio.Theme.bodySmall
                            text: !review.current ? qsTr("Chưa kiểm tra bản hiện tại") : checkRow.issues.length ? qsTr("Không hợp lệ") : review.editor.report.valid ? qsTr("Hợp lệ") : qsTr("Chưa xác nhận đầy đủ")
                            wrapMode: Text.WordWrap
                        }
                    }
                }
                Repeater {
                    model: checkRow.issues
                    Studio.InlineError {
                        required property var modelData
                        Layout.fillWidth: true
                        message: Messages.issue(modelData)
                        notifyError: false
                    }
                }
            }
        }
        Studio.StudioButton {
            Layout.alignment: Qt.AlignRight
            enabled: !!review.editor.document && !review.editor.backend.busy
            iconName: "check_circle"
            objectName: "reviewValidateButton"
            text: qsTr("Kiểm tra bản nháp")
            onClicked: review.editor.validate()
        }
    }
    Studio.DraftFormCard {
        Layout.fillWidth: true
        title: qsTr("Môi trường chạy")
        iconName: "terminal"
        Label {
            Layout.fillWidth: true
            color: review.editor.runtimeReport && review.editor.runtimeReport.ready ? Studio.Theme.success : review.editor.runtimeReport ? Studio.Theme.error : Studio.Theme.warning
            text: review.editor.runtimeReport && review.editor.runtimeReport.ready ? qsTr("Môi trường sẵn sàng.") : review.editor.runtimeReport ? qsTr("Môi trường chưa sẵn sàng. Xem lỗi bên dưới.") : qsTr("Chưa kiểm tra môi trường chạy.")
            wrapMode: Text.WordWrap
        }
        Repeater {
            model: review.editor.runtimeReport && review.editor.runtimeReport.issues ? review.editor.runtimeReport.issues : []
            Studio.InlineError {
                required property var modelData
                Layout.fillWidth: true
                message: Messages.issue(modelData)
                notifyError: false
            }
        }
        Studio.StudioButton {
            Layout.alignment: Qt.AlignRight
            enabled: !!review.editor.document && !review.editor.backend.busy
            iconName: "terminal"
            objectName: "reviewRuntimeButton"
            text: qsTr("Kiểm tra môi trường")
            onClicked: review.editor.checkRuntime()
        }
    }
    Studio.DraftFormCard {
        Layout.fillWidth: true
        title: review.editor.isInstalledEdit ? qsTr("Cập nhật bài trong thư viện") : qsTr("Sẵn sàng đưa vào thư viện")
        iconName: "inventory_2"
        Studio.StudioButton {
            Layout.alignment: Qt.AlignRight
            Layout.maximumWidth: parent.width
            enabled: review.current && review.editor.report.valid && !review.editor.backend.busy
            highlighted: true
            objectName: "reviewPublishButton"
            text: review.editor.isInstalledEdit ? qsTr("Xem lại để cập nhật") : qsTr("Xem lại để xuất bản")
            onClicked: {
                if (review.editor.isInstalledEdit) review.editor.reviewUpdate();
                else review.editor.reviewPublication();
            }
        }
        Label {
            Layout.fillWidth: true
            color: Studio.Theme.textOnSurfaceVariant
            font.pixelSize: Studio.Theme.bodySmall
            text: review.editor.draft ? "Revision " + review.editor.draft.revision + " · " + review.editor.draft.digest : qsTr("Chưa có bản nháp")
            textFormat: Text.PlainText
            wrapMode: Text.WrapAnywhere
        }
    }
}
