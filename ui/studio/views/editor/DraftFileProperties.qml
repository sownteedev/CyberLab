pragma ComponentBehavior: Bound
import QtQuick
import QtQuick.Controls.Basic
import QtQuick.Layouts
import "../../models/DraftFiles.js" as Files
import "../.." as Studio

Studio.StudioDialog {
    id: dialog
    required property var editor
    property string nodeId: ""
    property string path: ""
    property string owner: ""
    property string group: ""
    property string mode: "0644"
    property bool directory: false
    property var ownerChoices: []
    property var groupChoices: []
    property string error: ""
    property string expectedDefinition: ""
    property string expectedDraft: ""
    property int expectedGeneration: -1
    readonly property bool validMode: /^[0-3][0-7]{3}$/.test(mode) && (directory || mode[0] === "0")
    objectName: "filePropertiesDialog"
    width: Math.min(520, parent ? parent.width - 32 : 520)
    height: Math.min(directory ? 700 : 640, parent ? parent.height - 32 : 640)
    padding: Studio.Theme.space24
    focus: true

    function show(node, target) {
        editor.attempt(() => {
            const values = editor.files.metadata(node, target);
            const choices = Files.identities(editor.document.nodes.find(entry => entry.id === node));
            nodeId = node;
            path = target;
            owner = values.owner;
            group = values.group;
            mode = values.mode;
            directory = values.kind === "directory";
            ownerChoices = choices.owners.includes(owner) ? choices.owners : choices.owners.concat([owner]);
            groupChoices = choices.groups.includes(group) ? choices.groups : choices.groups.concat([group]);
            error = "";
            expectedDefinition = editor.definition;
            expectedDraft = editor.draft.id;
            expectedGeneration = editor.files.generation;
            open();
        });
    }
    function bitEnabled(bit) { return validMode && (parseInt(mode, 8) & bit) !== 0; }
    function toggleBit(bit, enabled) {
        if (!validMode) return;
        const value = enabled ? parseInt(mode, 8) | bit : parseInt(mode, 8) & ~bit;
        mode = ("0000" + value.toString(8)).slice(-4);
    }
    function applyChanges() {
        if (!editor.draft || expectedDraft !== editor.draft.id || expectedDefinition !== editor.definition
            || expectedGeneration !== editor.files.generation) {
            error = qsTr("Bản nháp đã thay đổi. Mở lại thuộc tính.");
            return;
        }
        editor.localError = "";
        editor.files.properties(nodeId, path, {owner: owner, group: group, mode: mode});
        if (editor.localError) { error = editor.localError.replace(/^Error:\s*/, ""); return; }
        close();
    }
    header: Studio.StudioDialogHeader {
        title: qsTr("Thuộc tính")
        iconName: "description"
        onCloseRequested: dialog.close()
    }
    contentItem: ScrollView {
        id: scroll
        clip: true
        contentWidth: availableWidth
        ColumnLayout {
            width: scroll.availableWidth
            spacing: Studio.Theme.space12
            Label {
                Layout.fillWidth: true
                text: dialog.nodeId + " / " + (dialog.path.startsWith("/") ? "System" : "Home / ") + dialog.path
                textFormat: Text.PlainText
                wrapMode: Text.WrapAnywhere
                color: Studio.Theme.textOnSurfaceVariant
            }
            GridLayout {
                Layout.fillWidth: true
                columns: 2
                columnSpacing: Studio.Theme.space12
                rowSpacing: Studio.Theme.space8
                Label { text: qsTr("Chủ sở hữu"); color: Studio.Theme.textOnSurface }
                Label { text: qsTr("Nhóm"); color: Studio.Theme.textOnSurface }
                Studio.StudioComboBox {
                    Layout.fillWidth: true
                    Layout.preferredWidth: 1
                    objectName: "filePropertyOwner"
                    model: dialog.ownerChoices
                    currentIndex: dialog.ownerChoices.indexOf(dialog.owner)
                    onActivated: dialog.owner = dialog.ownerChoices[currentIndex]
                }
                Studio.StudioComboBox {
                    Layout.fillWidth: true
                    Layout.preferredWidth: 1
                    objectName: "filePropertyGroup"
                    model: dialog.groupChoices
                    currentIndex: dialog.groupChoices.indexOf(dialog.group)
                    onActivated: dialog.group = dialog.groupChoices[currentIndex]
                }
            }
            Repeater {
                model: [{name: qsTr("Chủ"), shift: 6}, {name: qsTr("Nhóm"), shift: 3}, {name: qsTr("Khác"), shift: 0}]
                delegate: RowLayout {
                    id: permissionRow
                    required property var modelData
                    Layout.fillWidth: true
                    spacing: 0
                    Label { Layout.preferredWidth: 64; text: permissionRow.modelData.name; color: Studio.Theme.textOnSurface }
                    Repeater {
                        model: [{name: "r", bit: 4}, {name: "w", bit: 2}, {name: "x", bit: 1}]
                        delegate: Item {
                            id: permissionControl
                            required property var modelData
                            readonly property int bit: modelData.bit << permissionRow.modelData.shift
                            objectName: "filePermissionCell-" + permissionControl.bit
                            Layout.fillWidth: true
                            implicitHeight: Studio.Theme.controlHeight
                            Studio.StudioCheckBox {
                                id: checkbox
                                objectName: "filePermission-" + permissionControl.bit
                                anchors.fill: parent
                                text: permissionControl.modelData.name
                                Accessible.name: permissionRow.modelData.name + " " + permissionControl.modelData.name
                                checked: dialog.bitEnabled(permissionControl.bit)
                                enabled: dialog.validMode
                                onClicked: dialog.toggleBit(permissionControl.bit, checked)
                            }
                        }
                    }
                }
            }
            RowLayout {
                visible: dialog.directory
                Studio.StudioCheckBox { text: "setgid"; checked: dialog.bitEnabled(1024); enabled: dialog.validMode; onClicked: dialog.toggleBit(1024, checked) }
                Studio.StudioCheckBox { text: "sticky"; checked: dialog.bitEnabled(512); enabled: dialog.validMode; onClicked: dialog.toggleBit(512, checked) }
            }
            Studio.StudioTextField {
                Layout.fillWidth: true
                objectName: "filePropertyMode"
                Accessible.name: qsTr("Quyền octal")
                placeholderText: "0644"
                text: dialog.mode
                maximumLength: 4
                onTextEdited: dialog.mode = text
            }
            Label {
                Layout.fillWidth: true
                text: !dialog.editor.files.setupSupported ? qsTr("Backend chưa hỗ trợ thiết lập máy. Khai báo được giữ nguyên.")
                    : dialog.error || (!dialog.validMode ? qsTr("Nhập 4 số octal. Không dùng setuid; setgid và sticky chỉ dành cho thư mục.") : "")
                visible: text.length > 0
                wrapMode: Text.WordWrap
                color: Studio.Theme.error
            }
        }
    }
    footer: Studio.StudioDialogFooter {
        contentItem: RowLayout {
            Item { Layout.fillWidth: true }
            Studio.StudioButton { text: qsTr("Hủy"); flat: true; onClicked: dialog.close() }
            Studio.StudioButton {
                text: qsTr("Lưu")
                objectName: "filePropertySave"
                highlighted: true
                enabled: dialog.validMode && dialog.editor.files.setupSupported && !dialog.editor.backend.busy
                onClicked: dialog.applyChanges()
            }
        }
    }
}
