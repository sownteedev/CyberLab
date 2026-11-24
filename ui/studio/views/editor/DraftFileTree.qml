pragma ComponentBehavior: Bound
import QtQuick
import QtQuick.Controls.Basic
import QtQuick.Layouts
import "../../models/DraftFiles.js" as Files
import "../.." as Studio

Pane {
    id: tree
    required property var editor
    property var collapsed: ({})
    property var selection: null
    property var naming: null
    property string selectedKey: ""
    signal importRequested(string nodeId, string folder, bool directory)
    signal deleteRequested(string nodeId, string path)
    signal propertiesRequested(string nodeId, string path)
    padding: 8
    background: Rectangle { color: Studio.Theme.surfaceContainerLow; radius: Studio.Theme.shapeLarge }
    objectName: "seedFileTree"

    function followActive() {
        const active = editor.files.activeTab;
        if (!active) return;
        const expanded = Object.assign({}, collapsed);
        expanded[active.nodeId + ":"] = false;
        expanded[active.nodeId + ":" + Files.branch(active.path)] = false;
        const segments = active.path.split("/");
        for (let depth = 1; depth < segments.length; depth++)
            expanded[active.nodeId + ":" + segments.slice(0, depth).join("/")] = false;
        collapsed = expanded;
        const index = rows.findIndex(row => row.key === editor.files.activeKey);
        if (index < 0) return;
        choose(rows[index]);
        listing.currentIndex = index;
        listing.positionViewAtIndex(index, ListView.Contain);
    }
    Connections {
        target: tree.editor.files
        function onActiveKeyChanged() { Qt.callLater(tree.followActive); }
    }

    function toggle(row) {
        const offset = listing.contentY - listing.originY;
        const copy = Object.assign({}, collapsed);
        copy[row.key] = !copy[row.key];
        collapsed = copy;
        listing.currentIndex = rows.findIndex(entry => entry.key === row.key);
        listing.forceLayout();
        listing.contentY = listing.originY + Math.max(0, Math.min(offset, listing.contentHeight - listing.height));
    }
    function choose(row) {
        selection = row;
        selectedKey = row.key;
        editor.selectedNode = editor.document.nodes.findIndex(node => node.id === row.nodeId);
    }
    function focusName() {
        if (!naming || menu.visible) return;
        const index = rows.findIndex(row => row.nodeId === naming.nodeId && row.area === naming.area
            && (naming.action === "rename" ? row.path === naming.path : row.fresh));
        if (index < 0) return;
        listing.positionViewAtIndex(index, ListView.Contain);
        listing.forceLayout();
        const row = listing.itemAtIndex(index);
        if (row) row.focusName();
    }
    function begin(action) {
        const row = selection || rows[0];
        if (!row) return;
        const parent = row.kind === "directory" ? row.path : row.path.substring(0, Math.max(0, row.path.lastIndexOf("/")));
        const folder = row.path.includes("/") || row.kind === "directory" ? parent : "";
        if (row.area === "System" && !editor.files.setupSupported) return;
        naming = {nodeId: row.nodeId, area: row.area || "Home", folder: folder, path: row.path, action: action};
        if (action !== "rename") {
            const copy = Object.assign({}, collapsed);
            copy[row.nodeId + ":"] = false;
            copy[row.nodeId + ":" + naming.area] = false;
            copy[row.nodeId + ":" + folder] = false;
            collapsed = copy;
        }
        Qt.callLater(focusName);
    }
    function acceptName(name) {
        if (!naming || !name.trim()) return;
        editor.localError = "";
        if (naming.action === "rename") editor.files.rename(naming.nodeId, naming.path, name.trim());
        else editor.files.create(naming.nodeId, (naming.area === "System" && name.trim().startsWith("/") ? "" : naming.folder ? naming.folder.replace(/\/$/, "") + "/" : "") + name.trim(), naming.action === "folder");
        if (!editor.localError) naming = null;
        else {
            editor.backend.notify(editor.localError.replace(/^Error:\s*/, ""), true);
            editor.localError = "";
        }
    }
    function importHere(directory) {
        const row = selection || rows[0];
        if (!row) return;
        const folder = row.kind === "directory" ? row.path : row.path.substring(0, Math.max(0, row.path.lastIndexOf("/")));
        importRequested(row.nodeId, folder, directory);
    }
    readonly property var rows: {
        const result = [];
        if (!editor.document) return result;
        editor.document.nodes.forEach(node => {
            const root = {nodeId: node.id, path: "", name: node.id, key: node.id + ":", depth: 0, kind: "directory", root: true};
            result.push(root);
            if (collapsed[root.key]) return;
            ["Home", "System"].forEach(area => {
            const entries = editor.files.rows(node.id, area);
            const branch = {nodeId: node.id, path: area === "System" ? "/" : "", name: area, area: area,
                key: node.id + ":" + area, depth: 1, kind: "directory", root: true};
            result.push(branch);
            function children(parent, depth) {
                if (naming && naming.nodeId === node.id && naming.area === area && naming.folder === parent && naming.action !== "rename")
                    result.push({nodeId: node.id, area: area, path: "$new", key: node.id + ":$new", name: "", depth: depth, kind: naming.action === "folder" ? "directory" : "file", fresh: true});
                entries.filter(entry => (entry.path.substring(0, Math.max(0, entry.path.lastIndexOf("/"))) || (area === "System" ? "/" : "")) === parent)
                    .sort((first, second) => first.kind === second.kind ? first.path.localeCompare(second.path) : first.kind === "directory" ? -1 : 1)
                    .forEach(entry => {
                        const row = Object.assign({}, entry, {nodeId: node.id, area: area, name: entry.path.split("/").pop(), key: node.id + ":" + entry.path, depth: depth, root: false});
                        result.push(row);
                        if (entry.kind === "directory" && !collapsed[row.key]) children(entry.path, depth + 1);
                    });
            }
            if (!collapsed[branch.key]) children(branch.path, 2);
            });
        });
        return result;
    }
    contentItem: ColumnLayout {
    spacing: 4
    Label {
        Layout.fillWidth: true
        Layout.leftMargin: 8
        Layout.rightMargin: 8
        objectName: "setupFilesUnavailable"
        visible: !tree.editor.files.setupSupported
        text: qsTr("System và thuộc tính chưa khả dụng trên backend này. Khai báo cũ được giữ nguyên.")
        wrapMode: Text.WordWrap
        color: Studio.Theme.textOnSurfaceVariant
        font.pixelSize: Studio.Theme.bodySmall
    }
    RowLayout {
        Layout.fillWidth: true
        Layout.leftMargin: 8
        Label { Layout.fillWidth: true; text: qsTr("File"); color: Studio.Theme.textOnSurface; font.pixelSize: Studio.Theme.titleSmall; font.weight: Font.Medium }
        Studio.StudioIconButton {
            selected: true
            iconName: "add"
            description: qsTr("Thêm file hoặc thư mục")
            objectName: "fileTreeAdd"
            enabled: tree.rows.length > 0
            onClicked: menu.popup()
        }
    }
    ListView {
        id: listing
        Layout.fillWidth: true
        Layout.fillHeight: true
        clip: true
        model: tree.rows
        keyNavigationEnabled: true
        boundsBehavior: Flickable.StopAtBounds
        onHeightChanged: Qt.callLater(tree.followActive)
        ScrollBar.vertical: ScrollBar {}
        Keys.onPressed: event => {
            const row = tree.rows[currentIndex];
            if (!row) return;
            tree.choose(row);
            if (event.key === Qt.Key_F2 && !row.root) { tree.begin("rename"); event.accepted = true; }
            else if (event.key === Qt.Key_Delete && !row.root) { tree.deleteRequested(row.nodeId, row.path); event.accepted = true; }
            else if (event.key === Qt.Key_Return) {
                if (row.kind === "directory") tree.toggle(row);
                else tree.editor.files.open(row.nodeId, row.path);
                event.accepted = true;
            } else if ((event.key === Qt.Key_Left || event.key === Qt.Key_Right) && row.kind === "directory") {
                const collapse = event.key === Qt.Key_Left;
                if (!!tree.collapsed[row.key] !== collapse) tree.toggle(row);
                event.accepted = true;
            }
        }
        delegate: Item {
            id: rowItem
            required property var modelData
            required property int index
            readonly property bool editing: !!tree.naming && tree.naming.nodeId === modelData.nodeId
                && (modelData.fresh || (tree.naming.action === "rename" && tree.naming.path === modelData.path))
            width: listing.width
            height: 48
            readonly property bool selected: tree.selectedKey === modelData.key
            function focusName() {
                if (!editing || nameInput.activeFocus) return;
                nameInput.forceActiveFocus();
                nameInput.selectAll();
            }
            Rectangle {
                anchors.fill: parent
                anchors.topMargin: 2
                anchors.bottomMargin: 2
                radius: Studio.Theme.shapeFull
                color: rowItem.selected ? Studio.Theme.secondaryContainer
                    : pointer.containsMouse ? Studio.Theme.surfaceContainerHigh : "transparent"
                border.width: listing.activeFocus && listing.currentIndex === rowItem.index ? 2 : 0
                border.color: Studio.Theme.primary
                Behavior on color { ColorAnimation { duration: Studio.Theme.stateDuration } }
            }
            MouseArea {
                id: pointer
                anchors.fill: parent
                hoverEnabled: true
                acceptedButtons: Qt.LeftButton | Qt.RightButton
                onClicked: mouse => {
                    tree.choose(rowItem.modelData);
                    listing.currentIndex = rowItem.index;
                    listing.forceActiveFocus();
                    if (mouse.button === Qt.RightButton) menu.popup();
                    else if (rowItem.modelData.kind === "directory") tree.toggle(rowItem.modelData);
                    else tree.editor.files.open(rowItem.modelData.nodeId, rowItem.modelData.path);
                }
            }
            RowLayout {
                anchors.fill: parent
                anchors.leftMargin: 12 + Math.min(rowItem.modelData.depth, 6) * 12
                anchors.rightMargin: 4
                spacing: 8
                Studio.Icon {
                    name: rowItem.modelData.kind === "directory" ? "chevron_right" : "description"
                    rotation: rowItem.modelData.kind === "directory" && !tree.collapsed[rowItem.modelData.key] ? 90 : 0
                    color: rowItem.selected ? Studio.Theme.textOnSecondaryContainer : Studio.Theme.textOnSurfaceVariant
                    size: 20
                }
                Label {
                    Layout.fillWidth: true
                    visible: !rowItem.editing
                    text: rowItem.modelData.name
                    textFormat: Text.PlainText
                    elide: Text.ElideRight
                    color: rowItem.selected ? Studio.Theme.textOnSecondaryContainer : Studio.Theme.textOnSurface
                    font.bold: !!rowItem.modelData.root
                    font.pixelSize: Studio.Theme.bodyMedium
                }
                Studio.StudioTextField {
                    id: nameInput
                    Layout.fillWidth: true
                    Layout.preferredHeight: 40
                    visible: rowItem.editing
                    objectName: rowItem.editing ? "fileTreeName" : ""
                    text: rowItem.modelData.fresh ? "" : rowItem.modelData.name
                    placeholderText: tree.naming && tree.naming.area === "System" && tree.naming.folder === "/"
                        ? qsTr("/etc/demo.conf") : rowItem.modelData.kind === "directory" ? qsTr("Tên thư mục") : qsTr("Tên file")
                    onVisibleChanged: if (visible) Qt.callLater(tree.focusName)
                    Component.onCompleted: if (visible) Qt.callLater(tree.focusName)
                    onAccepted: tree.acceptName(text)
                    Keys.onEscapePressed: tree.naming = null
                }
                Studio.StudioIconButton {
                    Layout.preferredWidth: 48
                    Layout.minimumWidth: 48
                    Layout.maximumWidth: 48
                    Layout.preferredHeight: 48
                    visible: !rowItem.editing
                    iconSize: 20
                    iconName: "more_horiz"
                    description: qsTr("Thao tác với %1").arg(rowItem.modelData.name)
                    onClicked: { tree.choose(rowItem.modelData); menu.popup(); }
                }
            }
        }
    }
    }
    component FileMenuItem: MenuItem {
        id: action
        implicitHeight: visible ? 48 : 0
        leftPadding: 16
        rightPadding: 16
        contentItem: Text {
            text: action.text
            font.family: Studio.Theme.fontFamily
            font.pixelSize: Studio.Theme.bodyMedium
            color: action.enabled ? Studio.Theme.textOnSurface : Studio.Theme.textOnSurfaceVariant
            verticalAlignment: Text.AlignVCenter
        }
        background: Rectangle {
            radius: Studio.Theme.shapeSmall
            color: action.highlighted ? Studio.Theme.secondaryContainer : "transparent"
        }
    }
    component FileMenuSeparator: MenuSeparator {
        padding: 4
        contentItem: Rectangle { implicitHeight: 1; color: Studio.Theme.outlineVariant }
    }
    Menu {
        id: menu
        onClosed: Qt.callLater(tree.focusName)
        objectName: "fileTreeMenu"
        width: 256
        padding: 8
        background: Rectangle { color: Studio.Theme.surfaceContainerHigh; radius: Studio.Theme.shapeMedium; border.color: Studio.Theme.outlineVariant }
        FileMenuItem { objectName: "fileTreeNewFile"; text: qsTr("File mới"); onTriggered: tree.begin("file") }
        FileMenuItem { objectName: "fileTreeNewDirectory"; text: qsTr("Thư mục mới"); onTriggered: tree.begin("folder") }
        FileMenuSeparator {}
        FileMenuItem { text: qsTr("Thêm file từ máy tính…"); onTriggered: tree.importHere(false) }
        FileMenuItem { text: qsTr("Thêm thư mục từ máy tính…"); onTriggered: tree.importHere(true) }
        FileMenuSeparator { visible: !!tree.selection && !tree.selection.root }
        FileMenuItem { text: qsTr("Đổi tên"); visible: !!tree.selection && !tree.selection.root; onTriggered: tree.begin("rename") }
        FileMenuItem { objectName: "fileTreeProperties"; text: qsTr("Thuộc tính"); visible: !!tree.selection && !tree.selection.root; enabled: tree.editor.files.setupSupported; onTriggered: tree.propertiesRequested(tree.selection.nodeId, tree.selection.path) }
        FileMenuItem { text: qsTr("Xóa"); visible: !!tree.selection && !tree.selection.root; onTriggered: tree.deleteRequested(tree.selection.nodeId, tree.selection.path) }
    }
}
