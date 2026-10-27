import QtQuick
import QtQuick.Controls.Basic
import QtQuick.Layouts
import QtQuick.Dialogs as Native
import "../.."
import "../.." as Studio
import "../../models/Checkwork.js" as Checks

Dialog {
    id: dialog
    objectName: "checkworkDialog"
    required property var service
    property var session: null
    property bool connected: false
    property string exportId: ""
    property string deleteId: ""
    property Item returnFocus: null
    readonly property bool canCheck: connected && session && session.state === "RUNNING"
        && session.checkwork_enabled === true && !service.api.busy && !service.checking
    parent: Overlay.overlay
    anchors.centerIn: parent
    width: Math.min(860, parent ? parent.width - Studio.Theme.space32 : 860)
    height: Math.min(640, parent ? parent.height - Studio.Theme.space32 : 640)
    padding: Studio.Theme.space16
    modal: true
    focus: true
    closePolicy: Popup.CloseOnEscape | Popup.CloseOnPressOutside
    onOpened: checkButton.forceActiveFocus(Qt.TabFocusReason)
    onClosed: if (returnFocus) returnFocus.forceActiveFocus(Qt.TabFocusReason)
    background: Rectangle { radius: Studio.Theme.shapeExtraLarge; color: Studio.Theme.surfaceContainerHigh }
    Overlay.modal: Rectangle { color: Studio.Theme.scrim }
    header: RowLayout {
        implicitHeight: Studio.Theme.appBarHeight
        Label {
            Layout.fillWidth: true
            Layout.leftMargin: Studio.Theme.space16
            text: "Kết quả bài làm"
            color: Studio.Theme.textOnSurface
            font.pixelSize: Studio.Theme.titleMedium
        }
        StudioIconButton {
            Layout.rightMargin: Studio.Theme.space8
            iconName: "close"
            description: "Đóng kết quả"
            onClicked: dialog.close()
        }
    }
    contentItem: ColumnLayout {
        spacing: Studio.Theme.space8
        InlineError { Layout.fillWidth: true; message: dialog.service.error }
        RowLayout {
            Layout.fillWidth: true
            StudioComboBox {
                id: history
                objectName: "checkworkHistory"
                Layout.fillWidth: true
                Layout.minimumWidth: 0
                model: dialog.service.reports.map(entry => Checks.historyLabel(entry))
                currentIndex: dialog.service.report ? dialog.service.reports.findIndex(entry => entry.id === dialog.service.report.id) : -1
                displayText: currentIndex < 0 ? "Chưa có lần kiểm tra nào" : currentText
                enabled: dialog.service.reports.length > 0 && !dialog.service.checking
                onActivated: dialog.service.selectReport(dialog.service.reports[currentIndex].id)
            }
            StudioIconButton {
                iconName: "refresh"
                description: "Tải lại lịch sử"
                enabled: dialog.connected && !dialog.service.loading && !dialog.service.checking
                onClicked: dialog.service.refresh()
            }
        }
        Label {
            Layout.fillWidth: true
            visible: dialog.session && !dialog.session.checkwork_enabled
            text: "Bài này chưa bật Checkwork. Có thể cấu hình trong trình tạo bài."
            color: Studio.Theme.textOnSurfaceVariant
            font.pixelSize: Studio.Theme.bodySmall
            wrapMode: Text.WordWrap
        }
        CheckworkDetails { Layout.fillWidth: true; Layout.fillHeight: true; report: dialog.service.report }
        Flow {
            Layout.fillWidth: true
            Layout.preferredHeight: implicitHeight
            spacing: Studio.Theme.space8
            StudioButton {
                id: checkButton
                objectName: "runCheckworkButton"
                iconName: "check_circle"
                text: "Kiểm tra bài làm"
                highlighted: true
                visible: dialog.session !== null
                enabled: dialog.canCheck
                onClicked: dialog.service.check()
            }
            StudioButton {
                objectName: "exportSubmissionButton"
                iconName: "download"
                text: "Xuất bài nộp"
                enabled: dialog.connected && !!dialog.service.report && !dialog.service.api.busy && !dialog.service.loading
                onClicked: { dialog.exportId = dialog.service.report.id; output.open(); }
            }
            StudioIconButton {
                iconName: "delete"
                description: "Xóa báo cáo đã chọn"
                enabled: dialog.connected && !!dialog.service.report && !dialog.service.api.busy && !dialog.service.loading
                onClicked: { dialog.deleteId = dialog.service.report.id; deletion.open(); }
            }
        }
    }
    ConfirmDialog {
        id: deletion
        title: "Xóa báo cáo?"
        message: "Xóa kết quả và bằng chứng của lần kiểm tra này. File trong máy lab và các lần kiểm tra khác vẫn được giữ."
        danger: true
        confirmText: "Xóa báo cáo"
        confirmEnabled: !dialog.service.api.busy
        onAccepted: dialog.service.remove(dialog.deleteId)
    }
    Native.FileDialog {
        id: output
        title: "Lưu bài nộp thành file ZIP mới (không ghi đè)"
        fileMode: Native.FileDialog.SaveFile
        defaultSuffix: "zip"
        nameFilters: ["Bài nộp CyberLab (*.zip)"]
        onAccepted: {
            const url = selectedFile.toString();
            if (!url.startsWith("file:///")) { dialog.service.error = "Chỉ xuất file trong VM."; return; }
            dialog.service.exportReport(dialog.exportId, decodeURIComponent(url.substring(7)));
        }
    }
}
