pragma ComponentBehavior: Bound

import QtQuick
import QtQuick.Controls.Basic
import QtQuick.Layouts
import QtCore
import Qt.labs.folderlistmodel
import ".." as Studio
import "../models/FilePickerPaths.js" as Paths
import "../models/Messages.js" as Messages

Studio.StudioDialog {
    id: dialog
    property string fileMode: "open"
    property bool folderOnly: false
    property url currentFolder: StandardPaths.writableLocation(StandardPaths.HomeLocation)
    property url selectedFile
    property var selectedFiles: []
    property url selectedFolder
    property var nameFilters: ["Tất cả file (*)"]
    property string defaultSuffix: ""
    property string acceptLabel: folderOnly ? "Chọn thư mục" : saving ? "Lưu" : "Mở"
    property string rejectLabel: "Hủy"
    property string fileName: ""
    property string errorText: ""
    property bool showHidden: false
    property int filterIndex: 0
    property var selection: []
    property string selectedDirectory: ""
    property url previewUrl: ""
    property string previewName: ""
    property bool previewDirectory: false
    property real previewSize: 0
    property var previewModified: null
    property Item returnFocus: null
    readonly property bool saving: fileMode === "save" && !folderOnly
    readonly property bool multiple: fileMode === "openMany" && !folderOnly
    readonly property var folderModel: folderLoader.item
    readonly property bool loading: !folderModel || folderModel.resetting || folderModel.status === FolderListModel.Loading
    readonly property int dotCount: {
        if (!folderModel) return 0;
        let count = 0;
        for (let index = 0; index < Math.min(2, folderModel.count); index++) {
            const name = folderModel.get(index, "fileName");
            if (name === "." || name === "..") count++;
        }
        return count;
    }
    readonly property bool validFolder: {
        if (loading || folderModel.status !== FolderListModel.Ready || !folderModel.count || !dotCount) return false;
        const firstFolder = Paths.fromPath(Paths.localPath(folderModel.get(0, "fileUrl")));
        return Paths.localPath(firstFolder) === Paths.localPath(currentFolder);
    }
    readonly property bool canChoose: validFolder && (folderOnly || (saving ? Paths.validName(fileName) : selection.length > 0))
    readonly property int entryCount: validFolder ? Math.max(0, folderModel.count - dotCount) : 0

    parent: Overlay.overlay
    anchors.centerIn: parent
    width: Math.min(1120, parent ? parent.width - Studio.Theme.space32 : 1120)
    height: Math.min(700, parent ? parent.height - Studio.Theme.space32 : 700)
    padding: Studio.Theme.space24
    font.family: Studio.Theme.fontFamily
    font.pixelSize: Studio.Theme.bodyMedium
    modal: true
    focus: true
    closePolicy: Popup.CloseOnEscape

    function clearSelection() {
        selection = [];
        selectedDirectory = "";
        previewUrl = "";
        previewName = "";
        previewDirectory = false;
        previewSize = 0;
        previewModified = null;
    }
    function navigate(folder) {
        if (!Paths.localPath(folder)) { errorText = "Chỉ chọn thư mục trên máy này."; return; }
        currentFolder = folder;
        location.text = Paths.localPath(currentFolder);
        clearSelection();
        errorText = "";
    }
    function selectEntry(url, directory, name) {
        const index = folderModel ? folderModel.indexOf(url) : -1;
        if (loading || !validFolder)
            return;
        if (index < dotCount || folderModel.isFolder(index) !== directory) {
            errorText = "Danh sách đã thay đổi. Hãy chọn lại.";
            return;
        }
        errorText = "";
        previewUrl = url;
        previewName = name;
        previewDirectory = directory;
        previewSize = index >= 0 ? folderModel.get(index, "fileSize") : 0;
        previewModified = index >= 0 ? folderModel.get(index, "fileModified") : null;
        const value = Paths.fromPath(Paths.localPath(url));
        selectedDirectory = directory ? value : "";
        if (directory) { selection = []; return; }
        if (saving) fileName = name;
        selection = multiple ? (selection.includes(value) ? selection.filter(entry => entry !== value) : selection.concat([value])) : [value];
    }
    function activateEntry(url, directory, name) {
        const index = folderModel ? folderModel.indexOf(url) : -1;
        if (loading || !validFolder)
            return;
        if (index < dotCount || folderModel.isFolder(index) !== directory) {
            errorText = "Danh sách đã thay đổi. Hãy chọn lại.";
            return;
        }
        if (directory) { navigate(url); return; }
        if (multiple) {
            const value = Paths.fromPath(Paths.localPath(url));
            if (!selection.includes(value)) selection = selection.concat([value]);
        } else { selectEntry(url, false, name); choose(); }
    }
    function choose() {
        if (!canChoose) return;
        if (folderOnly) {
            const selectedIndex = folderModel.indexOf(selectedDirectory);
            if (selectedDirectory && (selectedIndex < 0 || !folderModel.isFolder(selectedIndex))) {
                selectedDirectory = "";
                errorText = "Thư mục đã thay đổi. Hãy chọn lại.";
                return;
            }
            selectedFolder = selectedDirectory || currentFolder;
        }
        else if (saving) {
            const destination = Paths.destination(currentFolder, fileName, defaultSuffix);
            if (!destination) return;
            if (folderModel.indexOf(destination) >= 0) { errorText = "Tên này đã tồn tại. Chọn tên khác để không ghi đè."; return; }
            selectedFile = destination;
            selectedFiles = [destination];
        } else {
            const existing = selection.filter(url => {
                const index = folderModel.indexOf(url);
                return index >= 0 && !folderModel.isFolder(index);
            });
            if (existing.length !== selection.length) { selection = existing; errorText = "Danh sách file đã thay đổi. Hãy chọn lại."; return; }
            selectedFiles = selection.slice();
            selectedFile = selectedFiles[0];
        }
        accept();
    }
    onAboutToShow: {
        returnFocus = ApplicationWindow.window ? ApplicationWindow.window.activeFocusItem : null;
        clearSelection();
        errorText = "";
        if (saving && Paths.localPath(selectedFile)) {
            currentFolder = Paths.parentFolder(selectedFile);
            fileName = Paths.basename(selectedFile);
        }
        location.text = Paths.localPath(currentFolder);
    }
    onOpened: if (saving) filenameInput.forceActiveFocus(Qt.TabFocusReason); else fileList.focusList()
    onClosed: Qt.callLater(() => {
        if (!returnFocus || visible || !returnFocus.visible || !returnFocus.enabled) return;
        const window = returnFocus.Window.window;
        const focused = window ? window.activeFocusItem : null;
        if (!focused || focused === window.contentItem || focused === returnFocus || !focused.visible)
            returnFocus.forceActiveFocus(Qt.TabFocusReason);
    })
    onCurrentFolderChanged: clearSelection()
    onFilterIndexChanged: clearSelection()
    onShowHiddenChanged: clearSelection()

    Loader {
        id: folderLoader
        active: dialog.visible
        sourceComponent: Component {
            FolderListModel {
                property bool resetting: false
                property int resetRevision: 0

                onModelAboutToBeReset: {
                    resetRevision++;
                    resetting = true;
                }
                function finishReset() {
                    const revision = resetRevision;
                    Qt.callLater(() => {
                        if (revision === resetRevision) resetting = false;
                    });
                }
                onModelReset: finishReset()
                onStatusChanged: if (status !== FolderListModel.Loading) finishReset()

                folder: dialog.currentFolder
                nameFilters: Paths.filters(dialog.nameFilters[dialog.filterIndex])
                showFiles: !dialog.folderOnly
                showDirsFirst: true
                showDotAndDotDot: true
                showHidden: dialog.showHidden
                showOnlyReadable: true
                sortField: FolderListModel.Name
            }
        }
    }
    header: RowLayout {
        implicitHeight: Studio.Theme.appBarHeight
        spacing: Studio.Theme.space12
        Studio.Icon {
            Layout.leftMargin: Studio.Theme.space24
            name: dialog.saving ? "save" : "folder"
            color: Studio.Theme.primary
        }
        Label {
            Layout.fillWidth: true
            Layout.minimumWidth: 0
            text: dialog.title || (dialog.folderOnly ? "Chọn thư mục" : "Chọn file")
            color: Studio.Theme.textOnSurface
            font.pixelSize: Studio.Theme.titleLarge
            font.weight: Font.DemiBold
            elide: Text.ElideRight
        }
        Studio.StudioIconButton {
            Layout.rightMargin: Studio.Theme.space16
            iconName: "close"
            description: "Đóng hộp chọn file"
            onClicked: dialog.reject()
        }
    }
    contentItem: ColumnLayout {
        spacing: Studio.Theme.space12
        RowLayout {
            Layout.fillWidth: true
            spacing: Studio.Theme.space8
            Studio.StudioIconButton {
                objectName: "filePickerParent"
                iconName: "arrow_back"
                description: "Lên thư mục cha"
                enabled: Paths.localPath(dialog.currentFolder) !== "/"
                onClicked: dialog.navigate(Paths.parentFolder(dialog.currentFolder))
            }
            Studio.StudioTextField {
                id: location
                objectName: "filePickerPath"
                Layout.fillWidth: true
                Layout.minimumWidth: 0
                Accessible.name: "Đường dẫn thư mục"
                placeholderText: "Nhập đường dẫn rồi nhấn Enter"
                onAccepted: dialog.navigate(Paths.fromPath(text, StandardPaths.writableLocation(StandardPaths.HomeLocation)))
            }
            Studio.StudioIconButton {
                objectName: "filePickerHidden"
                iconName: "more_horiz"
                description: dialog.showHidden ? "Ẩn file ẩn" : "Hiện file ẩn"
                selected: dialog.showHidden
                onClicked: dialog.showHidden = !dialog.showHidden
            }
        }
        RowLayout {
            Layout.fillWidth: true
            spacing: Studio.Theme.space8

            Label {
                Layout.fillWidth: true
                color: Studio.Theme.textOnSurface
                font.pixelSize: Studio.Theme.titleSmall
                font.weight: Font.DemiBold
                text: dialog.folderOnly ? "Chọn vị trí thư mục" : dialog.saving ? "Lưu vào thư mục" : "Chọn mục trong thư mục"
            }
            Label {
                color: Studio.Theme.textOnSurfaceVariant
                font.pixelSize: Studio.Theme.bodySmall
                objectName: "filePickerCount"
                text: dialog.loading ? "Đang tải…" : dialog.entryCount + " mục"
            }
        }
        RowLayout {
            Layout.fillWidth: true
            Layout.fillHeight: true
            spacing: Studio.Theme.space16
            Studio.FilePickerPlaces {
                visible: dialog.width >= 760
                Layout.preferredWidth: 176
                Layout.fillWidth: false
                Layout.fillHeight: true
                currentFolder: dialog.currentFolder
                onFolderRequested: folder => dialog.navigate(folder)
            }
            Studio.FilePickerList {
                id: fileList
                Layout.fillWidth: true
                Layout.fillHeight: true
                model: dialog.validFolder ? dialog.folderModel : null
                selection: dialog.selection
                selectedDirectory: dialog.selectedDirectory
                loading: dialog.loading
                entryCount: dialog.entryCount
                onEntryPressed: (url, directory, name) => dialog.selectEntry(url, directory, name)
                onEntryActivated: (url, directory, name) => dialog.activateEntry(url, directory, name)
            }
            Studio.FilePickerPreview {
                visible: dialog.width >= 900
                Layout.preferredWidth: 244
                Layout.fillWidth: false
                Layout.fillHeight: true
                directory: dialog.previewDirectory
                fileName: dialog.previewName
                fileSize: dialog.previewSize
                fileUrl: dialog.previewUrl
                modified: dialog.previewModified
            }
        }
        Studio.StudioTextField {
            id: filenameInput
            objectName: "filePickerFilename"
            visible: dialog.saving
            Layout.fillWidth: true
            text: dialog.fileName
            Accessible.name: "Tên file mới"
            placeholderText: "Tên file mới"
            onTextEdited: { dialog.fileName = text; dialog.errorText = ""; }
            onAccepted: dialog.choose()
        }
        Studio.StudioComboBox {
            objectName: "filePickerFilter"
            visible: !dialog.folderOnly
            Layout.fillWidth: true
            model: dialog.nameFilters
            currentIndex: dialog.filterIndex
            Accessible.name: "Loại file"
            onActivated: dialog.filterIndex = currentIndex
        }
        Label {
            objectName: "filePickerError"
            id: fileError
            Layout.fillWidth: true
            visible: text.length > 0
            text: Messages.text(dialog.errorText) || (!dialog.loading && !dialog.validFolder ? "Không thể đọc thư mục. Kiểm tra đường dẫn hoặc quyền truy cập." : "")
            textFormat: Text.PlainText
            Studio.ErrorNotifier { message: fileError.text; active: dialog.opened }
            color: Studio.Theme.error
            wrapMode: Text.WordWrap
            font.pixelSize: Studio.Theme.bodySmall
        }
    }
    footer: RowLayout {
        spacing: Studio.Theme.space8
        Label {
            Layout.leftMargin: Studio.Theme.space24
            Layout.bottomMargin: Studio.Theme.space16
            Layout.fillWidth: true
            Layout.minimumWidth: 0
            text: dialog.multiple ? "Đã chọn " + dialog.selection.length + " file" : dialog.folderOnly ? "Chọn thư mục hoặc dùng thư mục hiện tại" : "File trên máy này"
            color: Studio.Theme.textOnSurfaceVariant
            font.pixelSize: Studio.Theme.bodySmall
            elide: Text.ElideRight
        }
        Studio.StudioButton {
            objectName: "filePickerCancel"
            Layout.bottomMargin: Studio.Theme.space16
            text: dialog.rejectLabel
            flat: true
            onClicked: dialog.reject()
        }
        Studio.StudioButton {
            objectName: "filePickerAccept"
            Layout.rightMargin: Studio.Theme.space24
            Layout.bottomMargin: Studio.Theme.space16
            text: dialog.acceptLabel
            highlighted: true
            enabled: dialog.canChoose
            onClicked: dialog.choose()
        }
    }
}
