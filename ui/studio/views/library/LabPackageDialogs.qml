import QtQuick
import QtCore
import "../.."
import "../../models/LocalFiles.js" as LocalFiles

Item {
    id: dialogs

    required property var api
    required property var editor
    readonly property alias service: transfer
    property var target: null

    signal draftOpened
    signal libraryReloadRequested

    function exportPackage(selected, kind) {
        if (!selected || api.busy)
            return;
        target = {
            kind: kind,
            id: selected.id,
            revision: selected.revision
        };
        const name = kind === "draft" ? "ban-nhap" : selected.id;
        output.selectedFile = StandardPaths.writableLocation(StandardPaths.HomeLocation).toString() + "/" + encodeURIComponent(name) + ".cyberlab";
        output.open();
    }
    function importPackage() {
        if (!transfer.canImport) {
            if (editor.dirty)
                api.notify("Lưu thay đổi bản nháp trước khi nhập bài khác.", false);
            return;
        }
        input.open();
    }

    LabPackageService {
        id: transfer

        api: dialogs.api
        editor: dialogs.editor

        onDraftOpened: dialogs.draftOpened()
        onLibraryReloadRequested: dialogs.libraryReloadRequested()
        onCompatibilityBlocked: report => {
            compatibility.report = report;
            compatibility.open();
        }
    }
    LabtainerCompatibilityDialog {
        id: compatibility
    }
    StudioFileDialog {
        id: input

        fileMode: "open"
        nameFilters: ["Gói bài lab (*.cyberlab *.zip *.tar *.tar.gz *.tgz)", "Bài lab CyberLab (*.cyberlab)", "Bài lab Labtainer (*.zip *.tar *.tar.gz *.tgz)", "Tất cả file (*.*)"]
        objectName: "importLabPackagePicker"
        title: "Nhập gói vào bản nháp"

        onAccepted: {
            const path = LocalFiles.path(selectedFile);
            if (!path) {
                dialogs.api.error = "Chỉ nhập file trong VM.";
                return;
            }
            transfer.importPackage(path);
        }
    }
    StudioFileDialog {
        id: output

        defaultSuffix: "cyberlab"
        fileMode: "save"
        nameFilters: ["Bài lab CyberLab (*.cyberlab)"]
        objectName: "exportLabPackagePicker"
        title: "Xuất gói thành file mới (không ghi đè)"

        onAccepted: {
            const path = LocalFiles.path(selectedFile);
            if (!path) {
                dialogs.api.error = "Chỉ xuất file trong VM.";
                return;
            }
            transfer.exportPackage(dialogs.target, path);
        }
    }
}
