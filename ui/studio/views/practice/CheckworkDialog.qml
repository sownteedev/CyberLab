import QtQuick
import QtQuick.Controls.Basic
import QtQuick.Layouts
import "../.."
import "../.." as Studio
import "../../models/Checkwork.js" as Checks

Studio.StudioDialog {
    id: dialog

    readonly property bool canCheck: connected && session && session.state === "RUNNING" && session.checkwork_enabled === true && !service.api.busy && !service.checking
    property bool connected: false
    property string deleteId: ""
    property string exportId: ""
    property Item returnFocus: null
    required property var service
    property var session: null

    anchors.centerIn: parent
    closePolicy: Popup.CloseOnEscape | Popup.CloseOnPressOutside
    focus: true
    height: Math.min(640, parent ? parent.height - Studio.Theme.space32 : 640)
    modal: true
    objectName: "checkworkDialog"
    padding: Studio.Theme.space24
    topPadding: Studio.Theme.space8
    bottomPadding: Studio.Theme.space16
    parent: Overlay.overlay
    title: qsTr("Kết quả bài làm")
    width: Math.min(860, parent ? parent.width - Studio.Theme.space32 : 860)

    contentItem: ColumnLayout {
        spacing: Studio.Theme.space12

        InlineError {
            Layout.fillWidth: true
            message: dialog.service.error
        }
        RowLayout {
            Layout.fillWidth: true

            StudioComboBox {
                id: history

                Layout.fillWidth: true
                Layout.minimumWidth: 0
                currentIndex: dialog.service.report ? dialog.service.reports.findIndex(entry => entry.id === dialog.service.report.id) : -1
                displayText: currentIndex < 0 ? "Chưa có lần kiểm tra nào" : currentText
                enabled: dialog.service.reports.length > 0 && !dialog.service.checking
                model: dialog.service.reports.map(entry => Checks.historyLabel(entry))
                objectName: "checkworkHistory"

                onActivated: dialog.service.selectReport(dialog.service.reports[currentIndex].id)
            }
            StudioIconButton {
                id: refreshButton

                description: "Tải lại lịch sử"
                enabled: dialog.connected && !dialog.service.loading && !dialog.service.checking
                iconName: "refresh"
                objectName: "refreshCheckworkButton"

                onClicked: dialog.service.refresh()
            }
        }
        Label {
            Layout.fillWidth: true
            color: Studio.Theme.textOnSurfaceVariant
            font.pixelSize: Studio.Theme.bodySmall
            text: "Bài này chưa bật Checkwork. Có thể cấu hình trong trình tạo bài."
            visible: dialog.session && !dialog.session.checkwork_enabled
            wrapMode: Text.WordWrap
        }
        Item {
            Layout.fillHeight: true
            Layout.fillWidth: true
            objectName: "checkworkResultArea"

            CheckworkDetails {
                anchors.fill: parent
                report: dialog.service.report
                visible: !!dialog.service.report
            }
            EmptyState {
                anchors.centerIn: parent
                width: parent.width
                compact: parent.height < 120
                description: dialog.service.loading || dialog.service.checking ? qsTr("Kết quả sẽ xuất hiện khi hoàn tất.") : dialog.session ? qsTr("Kiểm tra bài đang chạy để xem kết quả và bằng chứng.") : qsTr("Kết quả sẽ được lưu tại đây sau khi bạn kiểm tra một bài thực hành.")
                iconName: dialog.service.loading || dialog.service.checking ? "refresh" : "description"
                objectName: "checkworkEmptyState"
                prominent: parent.height >= 200
                title: dialog.service.checking ? qsTr("Đang kiểm tra bài làm") : dialog.service.loading ? qsTr("Đang tải kết quả") : qsTr("Chưa có kết quả")
                visible: !dialog.service.report
            }
            LoadingState {
                anchors.left: parent.left
                anchors.right: parent.right
                anchors.top: parent.top
                busy: dialog.service.checking || dialog.service.loading
            }
        }
        Label {
            Layout.fillWidth: true
            color: Studio.Theme.textOnSurfaceVariant
            font.pixelSize: Studio.Theme.bodySmall
            text: qsTr("Kết quả tự kiểm tra tại thời điểm thu thập, không phải điểm thi được xác thực.")
            wrapMode: Text.WordWrap
        }
    }
    footer: Studio.StudioDialogFooter {
        contentItem: GridLayout {
            id: reportActions

            columns: width >= 520 ? 2 : 1
            columnSpacing: Studio.Theme.space8
            rowSpacing: Studio.Theme.space4

            RowLayout {
                Layout.fillWidth: true
                visible: !!dialog.service.report
                spacing: Studio.Theme.space8

                StudioButton {
                    enabled: dialog.connected && !!dialog.service.report && !dialog.service.api.busy && !dialog.service.loading
                    flat: true
                    iconName: "upload"
                    objectName: "exportSubmissionButton"
                    text: "Xuất bài nộp"

                    onClicked: {
                        dialog.exportId = dialog.service.report.id;
                        output.open();
                    }
                }
                StudioIconButton {
                    danger: true
                    description: "Xóa báo cáo đã chọn"
                    enabled: dialog.connected && !!dialog.service.report && !dialog.service.api.busy && !dialog.service.loading
                    iconName: "delete"
                    objectName: "deleteReportButton"

                    onClicked: {
                        dialog.deleteId = dialog.service.report.id;
                        deletion.open();
                    }
                }
            }
            RowLayout {
                Layout.fillWidth: true
                Layout.columnSpan: dialog.service.report ? 1 : reportActions.columns
                spacing: Studio.Theme.space8

                Item { Layout.fillWidth: true }
                StudioButton {
                    flat: true
                    objectName: "closeCheckworkAction"
                    text: qsTr("Đóng")
                    onClicked: dialog.close()
                }
                StudioButton {
                    id: checkButton

                    enabled: dialog.canCheck
                    highlighted: true
                    iconName: "check_circle"
                    objectName: "runCheckworkButton"
                    text: "Kiểm tra bài làm"
                    visible: dialog.session !== null

                    onClicked: dialog.service.check()
                }
            }
        }
    }
    header: Studio.StudioDialogHeader {
        id: dialogHeader

        title: dialog.title
        subtitle: qsTr("Xem lịch sử kiểm tra và xuất bằng chứng bài làm.")
        iconName: "description"
        closeDescription: qsTr("Đóng kết quả")
        closeObjectName: "closeCheckworkButton"
        onCloseRequested: dialog.close()
    }

    onClosed: if (returnFocus)
        returnFocus.forceActiveFocus(Qt.TabFocusReason)
    onOpened: (checkButton.visible && checkButton.enabled ? checkButton : history.enabled ? history : dialogHeader.closeButton).forceActiveFocus(Qt.TabFocusReason)

    ConfirmDialog {
        id: deletion
        objectName: "deleteReportConfirmation"

        confirmEnabled: !dialog.service.api.busy
        confirmText: "Xóa báo cáo"
        danger: true
        message: "Xóa kết quả và bằng chứng của lần kiểm tra này. File trong máy lab và các lần kiểm tra khác vẫn được giữ."
        title: "Xóa báo cáo?"

        onAccepted: dialog.service.remove(dialog.deleteId)
    }
    Studio.StudioFileDialog {
        id: output
        objectName: "exportSubmissionPicker"

        defaultSuffix: "zip"
        fileMode: "save"
        nameFilters: ["Bài nộp CyberLab (*.zip)"]
        title: "Lưu bài nộp thành file ZIP mới (không ghi đè)"

        onAccepted: {
            const url = selectedFile.toString();
            if (!url.startsWith("file:///")) {
                dialog.service.error = "Chỉ xuất file trong VM.";
                return;
            }
            dialog.service.exportReport(dialog.exportId, decodeURIComponent(url.substring(7)));
        }
    }
}
