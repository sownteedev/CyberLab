import QtQuick
import QtQuick.Controls.Basic
import QtCore
import "../.."
import "../../models/LocalFiles.js" as LocalFiles

Item {
    id: dialog

    required property var api
    readonly property bool confirmationOpened: confirmation.opened
    property string outputPath: ""
    property Item returnFocus: null
    property var target: null

    signal settled

    function openFor(session, caller) {
        if (!service.supported || api.busy || !session || session.state !== "RUNNING")
            return;
        target = {
            id: session.id,
            state: session.state,
            lab_id: session.lab_id
        };
        returnFocus = caller || null;
        outputPath = "";
        picker.selectedFile = StandardPaths.writableLocation(StandardPaths.HomeLocation).toString() + "/" + encodeURIComponent(session.lab_id + "-" + session.id.substring(0, 8) + "-" + Date.now()) + ".cyberlab-submission.zip";
        picker.open();
    }
    function restoreFocus() {
        if (returnFocus)
            returnFocus.forceActiveFocus(Qt.TabFocusReason);
    }

    SubmissionService {
        id: service

        api: dialog.api

        onSettled: dialog.settled()
    }
    StudioFileDialog {
        id: picker

        defaultSuffix: "zip"
        fileMode: "save"
        nameFilters: ["Bài nộp CyberLab (*.zip)"]
        objectName: "submitSessionPicker"
        title: "Lưu bài nộp thành file mới"

        onAccepted: {
            dialog.outputPath = LocalFiles.path(selectedFile);
            if (!dialog.outputPath) {
                dialog.api.notify("Chọn nơi lưu trên máy này.", true);
                dialog.restoreFocus();
                return;
            }
            if (dialog.Window.window)
                dialog.Window.window.requestActivate();
            confirmation.open();
        }
        onRejected: dialog.restoreFocus()
    }
    ConfirmDialog {
        id: confirmation

        confirmEnabled: service.supported && !dialog.api.busy && !service.submitting
        confirmText: "Nộp và kết thúc"
        message: "Ngừng thao tác và chờ cài đặt gói hoàn tất trước khi nộp. Tiến độ được lưu trên máy này để làm tiếp; chỉ bằng chứng đã khai báo được đưa vào file bài nộp, không kèm toàn bộ máy lab." + "\n\nKhông tự gửi lên máy chủ. Phiên chỉ dừng sau khi ghi file thành công. Không ghi đè file có sẵn.\n" + dialog.outputPath
        objectName: "submitSessionConfirmation"
        title: "Nộp bài và kết thúc?"

        onAccepted: service.submit(dialog.target, dialog.outputPath)
        onClosed: dialog.restoreFocus()
    }
}
