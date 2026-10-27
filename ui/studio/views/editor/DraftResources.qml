import QtQuick
import QtQuick.Controls
import QtQuick.Layouts
import QtQuick.Dialogs
import "../../models/EditorModel.js" as Model
import "../../models/SessionFiles.js" as Files
import "../.."
import "../.." as Studio

ColumnLayout {
    id: panel
    required property var editor
    readonly property var selectedNode: editor.document ? editor.document.nodes[editor.selectedNode] || null : null
    readonly property var assets: editor.draft ? editor.draft.assets : []
    readonly property var rows: selectedNode ? Files.treeRows(Model.previewFiles(selectedNode, assets)) : []
    property bool advanced: false
    property var pickerTarget: null
    property var pendingUpload: null
    property var pendingDelete: null
    spacing: Studio.Theme.space12
    enabled: !editor.backend.busy

    function pick(folder) {
        if (!selectedNode || !editor.draft) return;
        pickerTarget = {draftId: editor.draft.id, nodeId: selectedNode.id, folder: folder,
            subfolder: advanced ? subfolder.text.trim() : ""};
        if (folder) folderPicker.open(); else filePicker.open();
    }
    function choose(url) {
        editor.attempt(() => {
            const value = url.toString();
            const target = pickerTarget;
            if (!target || !editor.draft || target.draftId !== editor.draft.id) throw new Error("Bản nháp đã thay đổi. Chọn lại file.");
            if (!value.startsWith("file:///")) throw new Error("Chỉ nhận file trong VM.");
            const source = decodeURIComponent(value.substring(7));
            const name = source.split("/").filter(Boolean).pop();
            const plan = Model.homeUpload(editor.document, target.nodeId, name, target.folder, target.subfolder, assets);
            pendingUpload = Object.assign({}, target, {source: source, name: name, destination: plan.destination});
            const existing = assets.some(asset => asset.path === plan.logical || (target.folder && asset.path.startsWith(plan.logical + "/")));
            if (existing) replacement.open(); else upload();
        });
    }
    function upload() {
        const target = pendingUpload;
        pendingUpload = null;
        if (!target || !editor.draft || editor.draft.id !== target.draftId) return;
        editor.uploadHome(target.source, target.nodeId, target.name, target.folder, target.subfolder);
    }
    SectionHeader { title: "File ban đầu"; Layout.fillWidth: true }
    StudioComboBox {
        objectName: "seedFileNode"
        Layout.fillWidth: true
        Layout.maximumWidth: 420
        model: panel.editor.document ? panel.editor.document.nodes.map(node => node.id) : []
        currentIndex: panel.selectedNode ? panel.editor.selectedNode : -1
        Accessible.name: "Máy nhận file"
        onActivated: panel.editor.selectedNode = currentIndex
    }
    Label {
        Layout.fillWidth: true
        text: panel.selectedNode ? Model.workspace(panel.selectedNode) + "/" : "Thêm máy trước khi đưa file vào bài."
        font.family: Studio.Theme.monoFamily
        color: Studio.Theme.textOnSurfaceVariant
        wrapMode: Text.WrapAnywhere
    }
    Flow {
        Layout.fillWidth: true
        Layout.preferredHeight: implicitHeight
        spacing: Studio.Theme.space8
        StudioButton {
            objectName: "addSeedFile"
            text: "Thêm file"; iconName: "add"
            enabled: !!panel.selectedNode && !!panel.editor.policy && panel.editor.policy.home_directory_target === true
            onClicked: panel.pick(false)
        }
        StudioButton {
            objectName: "addSeedFolder"
            text: "Thêm thư mục"; iconName: "folder"
            enabled: !!panel.selectedNode && !!panel.editor.policy && panel.editor.policy.home_directory_target === true
            onClicked: panel.pick(true)
        }
    }
    Label {
        Layout.fillWidth: true
        text: "Thư mục: chép nội dung vào home, giữ các thư mục con. Chỉ thay đổi bản nháp."
        wrapMode: Text.WordWrap
        font.pixelSize: Studio.Theme.bodySmall
        color: Studio.Theme.textOnSurfaceVariant
    }
    Label {
        visible: !panel.rows.length
        text: "Chưa có file."
        color: Studio.Theme.textOnSurfaceVariant
    }
    ColumnLayout {
        Layout.fillWidth: true
        spacing: 0
        Repeater {
            model: panel.rows
            RowLayout {
                id: fileRow
                required property var modelData
                Layout.fillWidth: true
                TreeRow { Layout.fillWidth: true; entry: fileRow.modelData; showMetadata: false }
                StudioIconButton {
                    objectName: "deleteSeed-" + fileRow.modelData.path
                    iconName: "delete"
                    description: "Xóa " + fileRow.modelData.path + " khỏi máy"
                    visible: !fileRow.modelData.isDirectory
                    onClicked: {
                        panel.pendingDelete = {draftId: panel.editor.draft.id, nodeId: panel.selectedNode.id, path: fileRow.modelData.path};
                        deletion.open();
                    }
                }
            }
        }
    }
    StudioButton {
        objectName: "fileAdvancedToggle"
        text: panel.advanced ? "Ẩn nâng cao" : "Nâng cao"
        iconName: "settings"
        flat: true
        onClicked: panel.advanced = !panel.advanced
    }
    ColumnLayout {
        visible: panel.advanced
        Layout.fillWidth: true
        Label { text: "Thêm vào thư mục con" }
        StudioTextField { id: subfolder; Layout.fillWidth: true; placeholderText: "Để trống để dùng home" }
        Loader {
            Layout.fillWidth: true
            active: panel.advanced
            sourceComponent: DraftFileAdvanced { editor: panel.editor; node: panel.selectedNode }
        }
    }
    ConfirmDialog {
        id: replacement
        objectName: "replaceSeedFilesDialog"
        parent: Overlay.overlay
        title: "Thêm vào vị trí đã có file?"
        message: panel.pendingUpload ? panel.pendingUpload.destination + "\nFile trùng sẽ được thay trong bản nháp; các file khác vẫn giữ. Bài đã xuất bản không đổi." : ""
        confirmText: "Thêm và thay file trùng"
        confirmEnabled: !panel.editor.backend.busy
        onAccepted: panel.upload()
        onRejected: panel.pendingUpload = null
    }
    ConfirmDialog {
        id: deletion
        objectName: "deleteSeedFileDialog"
        parent: Overlay.overlay
        title: "Xóa file khỏi bản nháp?"
        message: panel.pendingDelete ? panel.pendingDelete.nodeId + " / " + panel.pendingDelete.path + "\nKhông xóa file nguồn trên VM hoặc bài đã xuất bản." : ""
        danger: true
        confirmText: "Xóa file"
        confirmEnabled: !panel.editor.backend.busy
        onAccepted: {
            const target = panel.pendingDelete;
            if (target && panel.editor.draft && target.draftId === panel.editor.draft.id)
                panel.editor.removeHomeFile(target.nodeId, target.path);
            panel.pendingDelete = null;
        }
    }
    FileDialog { id: filePicker; objectName: "seedFilePicker"; title: "Thêm file vào máy"; onAccepted: panel.choose(selectedFile) }
    FolderDialog { id: folderPicker; objectName: "seedFolderPicker"; title: "Thêm nội dung thư mục vào máy"; onAccepted: panel.choose(selectedFolder) }
}
