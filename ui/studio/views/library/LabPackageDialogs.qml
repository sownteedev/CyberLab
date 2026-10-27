import QtQuick
import QtCore
import QtQuick.Dialogs as Native
import "../.."
import "../../models/LocalFiles.js" as LocalFiles

Item {
    id: dialogs
    required property var api
    required property var editor
    property var target: null
    readonly property alias service: transfer
    signal draftOpened()

    function importPackage() {
        if (!transfer.canImport) {
            if (editor.dirty) api.notify("Lưu thay đổi bản nháp trước khi nhập bài khác.", false);
            return;
        }
        input.open();
    }
    function exportPackage(selected, kind) {
        if (!selected || api.busy) return;
        target = {kind: kind, id: selected.id, revision: selected.revision};
        const name = kind === "draft" ? "ban-nhap" : selected.id;
        output.selectedFile = StandardPaths.writableLocation(StandardPaths.HomeLocation).toString()
            + "/" + encodeURIComponent(name) + ".cyberlab";
        output.open();
    }
    LabPackageService {
        id: transfer
        api: dialogs.api
        editor: dialogs.editor
        onDraftOpened: dialogs.draftOpened()
    }
    Native.FileDialog {
        id: input
        objectName: "importLabPackagePicker"
        title: "Nhập gói vào bản nháp"
        fileMode: Native.FileDialog.OpenFile
        nameFilters: ["Gói bài lab (*.cyberlab *.zip *.tar *.tar.gz *.tgz)", "Bài lab CyberLab (*.cyberlab)", "Bài lab Labtainer (*.zip *.tar *.tar.gz *.tgz)", "Tất cả file (*.*)"]
        onAccepted: {
            const path = LocalFiles.path(selectedFile);
            if (!path) { dialogs.api.error = "Chỉ nhập file trong VM."; return; }
            transfer.importPackage(path);
        }
    }
    Native.FileDialog {
        id: output
        objectName: "exportLabPackagePicker"
        title: "Xuất gói thành file mới (không ghi đè)"
        fileMode: Native.FileDialog.SaveFile
        nameFilters: ["Bài lab CyberLab (*.cyberlab)"]
        defaultSuffix: "cyberlab"
        onAccepted: {
            const path = LocalFiles.path(selectedFile);
            if (!path) { dialogs.api.error = "Chỉ xuất file trong VM."; return; }
            transfer.exportPackage(dialogs.target, path);
        }
    }
}
