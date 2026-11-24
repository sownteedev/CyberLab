pragma ComponentBehavior: Bound
import QtQuick
import QtQuick.Controls.Basic
import QtQuick.Layouts
import "../../models/DraftFiles.js" as Files
import "../.." as Studio
import "." as FileWorkspace

Frame {
    id: panel
    required property var editor
    property var pickerTarget: null
    property var pendingUpload: null
    property var pendingDelete: null
    readonly property bool compact: width < 580
    objectName: "draftResources"
    implicitHeight: compact ? 700 : 560
    padding: 8
    enabled: !editor.backend.busy
    background: Rectangle {
        color: Studio.Theme.surfaceContainer
        radius: Studio.Theme.shapeExtraLarge
    }

    function choose(url) {
        if (!pickerTarget || !editor.draft || pickerTarget.draftId !== editor.draft.id) {
            editor.showLocalError(qsTr("Bản nháp đã thay đổi. Chọn lại file."));
            return;
        }
        editor.attempt(() => {
            const value = url.toString();
            if (!value.startsWith("file:///")) throw new Error("Chỉ nhận file trên máy tính này.");
            const source = decodeURIComponent(value.substring(7));
            const name = source.split("/").filter(Boolean).pop();
            pendingUpload = Object.assign({}, pickerTarget, {source: source, name: name});
            const destination = pickerTarget.folder + (pickerTarget.folder ? "/" : "") + (pickerTarget.directory ? "" : name);
            if (editor.files.rows(pickerTarget.nodeId, Files.branch(pickerTarget.folder)).some(row => !destination || Files.within(row.path, destination) || Files.within(destination, row.path))) replacement.open();
            else upload();
        });
    }
    function upload() {
        const target = pendingUpload;
        pendingUpload = null;
        if (!target || !editor.draft || editor.draft.id !== target.draftId) return;
        editor.attempt(() => {
            editor.files.importLocal(target.source, target.nodeId, target.folder, target.directory);
        });
    }
    contentItem: SplitView {
        id: split
        orientation: panel.compact ? Qt.Vertical : Qt.Horizontal
        handle: Rectangle {
            implicitWidth: 12
            implicitHeight: 12
            color: "transparent"
            Rectangle {
                anchors.centerIn: parent
                width: panel.compact ? 32 : 4
                height: panel.compact ? 4 : 32
                radius: 2
                color: parent.SplitHandle.hovered || parent.SplitHandle.pressed ? Studio.Theme.primary : Studio.Theme.outlineVariant
            }
        }
        Studio.DraftFileTree {
            id: tree
            SplitView.preferredWidth: 272
            SplitView.minimumWidth: panel.compact ? 0 : 200
            SplitView.maximumWidth: panel.compact ? Infinity : Math.max(180, split.width * 0.55)
            SplitView.preferredHeight: 220
            SplitView.minimumHeight: 100
            editor: panel.editor
            onPropertiesRequested: (nodeId, path) => propertiesDialog.show(nodeId, path)
            onImportRequested: (nodeId, folder, directory) => {
                panel.pickerTarget = {nodeId: nodeId, folder: folder, directory: directory, draftId: panel.editor.draft.id};
                if (directory) folderPicker.open(); else filePicker.open();
            }
            onDeleteRequested: (nodeId, path) => {
                panel.pendingDelete = {nodeId: nodeId, path: path, draftId: panel.editor.draft.id,
                    definition: panel.editor.definition, revision: panel.editor.draft.revision};
                deletion.open();
            }
        }
        Pane {
            SplitView.fillWidth: true
            SplitView.fillHeight: true
            SplitView.minimumWidth: panel.compact ? 0 : 220
            padding: 4
            background: Rectangle { color: Studio.Theme.surfaceContainerLow; radius: Studio.Theme.shapeLarge }
            contentItem: ColumnLayout {
                spacing: 0
                Studio.DraftFileTabs {
                    Layout.fillWidth: true
                    Layout.preferredHeight: 56
                    files: panel.editor.files
                    visible: panel.editor.files.tabs.length > 0
                }
                Item {
                    Layout.fillWidth: true
                    Layout.fillHeight: true
                    Repeater {
                        model: panel.editor.files.tabs
                        delegate: Studio.DraftFileTextEditor {
                            required property var modelData
                            anchors.fill: parent
                            files: panel.editor.files
                            tab: modelData
                            visible: modelData.key === panel.editor.files.activeKey
                        }
                    }
                    Label {
                        anchors.centerIn: parent
                        width: Math.max(0, parent.width - 32)
                        horizontalAlignment: Text.AlignHCenter
                        wrapMode: Text.Wrap
                        color: Studio.Theme.textOnSurfaceVariant
                        visible: panel.editor.files.tabs.length === 0
                        text: panel.editor.document && panel.editor.document.nodes.length ? qsTr("Chọn file để sửa, hoặc nhấn + để tạo.") : qsTr("Thêm máy Lab trước khi tạo file.")
                    }
                }
            }
        }
    }
    FileWorkspace.DraftFileProperties {
        id: propertiesDialog
        editor: panel.editor
    }
    Connections {
        target: panel.editor
        function onDraftChanged() { tree.naming = null; tree.selection = null; tree.selectedKey = ""; }
    }
    Studio.ConfirmDialog {
        id: deletion
        parent: Overlay.overlay
        title: qsTr("Xóa khỏi máy này?")
        message: panel.pendingDelete ? panel.pendingDelete.nodeId + " / " + panel.pendingDelete.path : ""
        confirmText: qsTr("Xóa")
        danger: true
        objectName: "deleteSeedFileDialog"
        onAccepted: {
            const target = panel.pendingDelete;
            if (target && panel.editor.draft && target.draftId === panel.editor.draft.id) {
                if (target.definition !== panel.editor.definition || target.revision !== panel.editor.draft.revision)
                    panel.editor.showLocalError(qsTr("Bản nháp đã thay đổi. Xác nhận lại thao tác xóa."));
                else panel.editor.files.remove(target.nodeId, target.path);
            }
            panel.pendingDelete = null;
        }
        onRejected: panel.pendingDelete = null
    }
    Studio.ConfirmDialog {
        id: replacement
        objectName: "replaceSeedFilesDialog"
        parent: Overlay.overlay
        title: qsTr("Thay file trùng tên?")
        message: qsTr("Chỉ thay trong máy đang chọn. Các máy khác giữ nguyên.")
        confirmText: qsTr("Thêm và thay thế")
        onAccepted: panel.upload()
        onRejected: panel.pendingUpload = null
    }
    Studio.StudioFileDialog {
        id: filePicker
        objectName: "seedFilePicker"
        title: qsTr("Thêm file từ máy tính")
        returnFocus: tree
        onAccepted: panel.choose(selectedFile)
    }
    Studio.StudioFolderDialog {
        id: folderPicker
        objectName: "seedFolderPicker"
        title: qsTr("Thêm nội dung thư mục")
        returnFocus: tree
        onAccepted: panel.choose(selectedFolder)
    }
}
