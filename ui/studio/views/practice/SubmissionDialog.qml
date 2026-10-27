import QtQuick
import QtQuick.Controls.Basic
import QtQuick.Dialogs as Native
import QtCore
import "../.."
import "../../models/LocalFiles.js" as LocalFiles

Item {
    id: dialog
    required property var api
    property var target: null
    property string outputPath: ""
    property Item returnFocus: null
    readonly property bool confirmationOpened: confirmation.opened
    signal settled()

    function restoreFocus() {
        if (returnFocus) returnFocus.forceActiveFocus(Qt.TabFocusReason);
    }
    function openFor(session, caller) {
        if (!service.supported || api.busy || !session || session.state !== "RUNNING") return;
        target = {id: session.id, state: session.state, lab_id: session.lab_id};
        returnFocus = caller || null;
        outputPath = "";
        picker.selectedFile = StandardPaths.writableLocation(StandardPaths.HomeLocation).toString()
            + "/" + encodeURIComponent(session.lab_id + "-" + session.id.substring(0, 8) + "-" + Date.now())
            + ".cyberlab-submission.zip";
        picker.open();
    }

    SubmissionService { id: service; api: dialog.api; onSettled: dialog.settled() }
    Native.FileDialog {
        id: picker
        objectName: "submitSessionPicker"
        title: "Lưu bài nộp thành file mới"
        fileMode: Native.FileDialog.SaveFile
        nameFilters: ["Bài nộp CyberLab (*.zip)"]
        defaultSuffix: "zip"
        onRejected: dialog.restoreFocus()
        onAccepted: {
            dialog.outputPath = LocalFiles.path(selectedFile);
            if (!dialog.outputPath) {
                dialog.api.notify("Chọn nơi lưu trong máy ảo.", true);
                dialog.restoreFocus();
                return;
            }
            if (dialog.Window.window) dialog.Window.window.requestActivate();
            confirmation.open();
        }
    }
    ConfirmDialog {
        id: confirmation
        objectName: "submitSessionConfirmation"
        title: "Nộp bài và kết thúc?"
        message: "Ngừng thao tác trong terminal trước khi nộp. Workspace được lưu để làm tiếp; chỉ các file đã khai báo được đưa vào bài nộp."
            + "\n\nPhiên chỉ dừng sau khi ghi file thành công. Không ghi đè file có sẵn.\n" + dialog.outputPath
        confirmText: "Nộp và kết thúc"
        confirmEnabled: service.supported && !dialog.api.busy && !service.submitting
        onAccepted: service.submit(dialog.target, dialog.outputPath)
        onClosed: dialog.restoreFocus()
    }
}
