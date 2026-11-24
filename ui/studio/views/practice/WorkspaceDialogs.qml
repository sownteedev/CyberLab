import QtQuick
import "../.."

Item {
    id: dialogs

    required property var api
    required property var controller
    property bool exportDirectory: true
    property string exportPath: "."
    property string nodeId: ""
    property string sessionId: ""

    function exportFiles(session, node, path, directory) {
        sessionId = session;
        nodeId = node;
        exportPath = path;
        exportDirectory = directory;
        output.open();
    }
    function importFile(session, node) {
        sessionId = session;
        nodeId = node;
        input.open();
    }
    function importFolder(session, node) {
        sessionId = session;
        nodeId = node;
        folder.open();
    }
    function localPath(url) {
        const value = url.toString();
        if (!value.startsWith("file:///")) {
            api.error = "Chỉ nhận đường dẫn cục bộ trong VM.";
            return "";
        }
        return decodeURIComponent(value.substring(7));
    }

    StudioFileDialog {
        id: input

        title: "Chọn file đưa vào máy lab"

        onAccepted: {
            const path = dialogs.localPath(selectedFile);
            if (!path)
                return;
            const session = dialogs.sessionId;
            const node = dialogs.nodeId;
            dialogs.api.request(["import-file", session, node, path], (result, error) => {
                if (!error) {
                    if (result.state === "COMPLETE")
                        dialogs.controller.notice = "Đã đưa file vào " + result.path;
                    else
                        dialogs.api.error = "Nhập file thất bại: " + result.error;
                    if (dialogs.controller.selectedSession && dialogs.controller.selectedSession.id === session) {
                        dialogs.controller.refreshImports(session);
                        dialogs.controller.refreshWorkspaces(node);
                    }
                }
            });
        }
    }
    StudioFolderDialog {
        id: folder

        title: "Nhập thư mục vào máy lab (tối đa 4 MiB, không ghi đè)"

        onAccepted: {
            const path = dialogs.localPath(selectedFolder);
            if (!path)
                return;
            const session = dialogs.sessionId;
            const node = dialogs.nodeId;
            dialogs.api.request(["import-folder", session, node, path], (result, error) => {
                if (!error && result.state === "COMPLETE")
                    dialogs.controller.notice = "Đã nhập thư mục: " + result.path;
                if (dialogs.controller.selectedSession && dialogs.controller.selectedSession.id === session) {
                    dialogs.controller.refreshImports(session);
                    dialogs.controller.refreshWorkspaces(node);
                }
            });
        }
    }
    StudioFileDialog {
        id: output

        defaultSuffix: dialogs.exportDirectory ? "tar" : ""
        fileMode: "save"
        title: dialogs.exportDirectory ? "Lưu thư mục thành file .tar mới" : "Lưu file về VM (không ghi đè)"

        onAccepted: {
            const path = dialogs.localPath(selectedFile);
            if (!path)
                return;
            dialogs.api.request([dialogs.exportDirectory ? "export-folder" : "export-file", dialogs.sessionId, dialogs.nodeId, dialogs.exportPath, path], (result, error) => {
                if (!error)
                    dialogs.controller.notice = "Đã lưu: " + result.destination;
            });
        }
    }
}
