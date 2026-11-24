import QtQuick
import QtQuick.Controls
import QtQuick.Layouts
import "../../models/NodeDefaults.js" as Defaults
import "../../models/StartupModel.js" as Startup
import "../.." as Studio

ColumnLayout {
    id: panel
    required property var editor
    required property int nodeIndex
    readonly property var node: editor.document && editor.document.nodes[nodeIndex] ? editor.document.nodes[nodeIndex] : null
    readonly property var script: editor.startup.descriptor(node)
    readonly property var entry: script ? editor.startup.entries[script.source] || null : null
    readonly property var defaultCommand: (node ? Defaults.profile(editor.policy, node.image) || {} : {}).command || []
    readonly property bool shared: !!script && Startup.shared(editor.document, node.id, script.source, script.target)
    readonly property int mode: script ? 1 : !node || JSON.stringify(node.command || []) === JSON.stringify(defaultCommand) ? 0 : 2
    property string importNode: ""
    property string importDraft: ""
    property bool advanced: false
    property var pendingMode: null
    readonly property string contextKey: (editor.draft ? editor.draft.id : "") + ":" + (node ? node.id : "")

    function applyMode(value) {
        if (!node || editor.backend.busy) return;
        if (value === 2) editor.startup.useCustom(node);
        else if (value === 1) editor.startup.useScript(node, mode === 2);
        else editor.startup.useDefault(node, defaultCommand);
    }
    function requestMode(value) {
        if (!node || !editor.draft || editor.backend.busy) return;
        if ((mode === 2 && value === 1) || (mode === 1 && value === 2)) {
            pendingMode = {draftId: editor.draft.id, revision: editor.draft.revision, nodeId: node.id,
                definition: editor.definition, value: value};
            replaceMode.open();
        } else applyMode(value);
    }

    enabled: !editor.backend.busy
    spacing: Studio.Theme.space12
    onVisibleChanged: if (visible) editor.startup.load(node)
    onScriptChanged: if (visible) editor.startup.load(node)
    onContextKeyChanged: {
        advanced = false;
        pendingMode = null;
        replaceMode.close();
    }
    Connections {
        target: panel.editor.backend
        function onBusyChanged() {
            if (!panel.editor.backend.busy && panel.visible) panel.editor.startup.load(panel.node);
        }
    }

    Studio.StudioToggle {
        id: scriptToggle
        Layout.fillWidth: true
        objectName: "startupScriptToggle"
        text: qsTr("Chạy script khi khởi động")
        checked: !!panel.script
        onClicked: {
            const requested = checked ? 1 : 0;
            checked = Qt.binding(() => !!panel.script);
            panel.requestMode(requested);
        }
    }
    Label {
        Layout.fillWidth: true
        visible: panel.mode === 2
        text: qsTr("Đang dùng lệnh tùy chỉnh.")
        color: Studio.Theme.textOnSurfaceVariant
        wrapMode: Text.WordWrap
    }
    RowLayout {
        Layout.fillWidth: true
        visible: !!panel.script
        Label {
            Layout.fillWidth: true
            text: panel.script ? panel.script.target : ""
            textFormat: Text.PlainText
            color: Studio.Theme.textOnSurfaceVariant
            font.family: Studio.Theme.monoFamily
            font.pixelSize: Studio.Theme.bodySmall
            elide: Text.ElideMiddle
        }
        Studio.StudioButton {
            text: qsTr("Chọn file…")
            iconName: "upload"
            objectName: "importStartupScript"
            onClicked: {
                panel.importNode = panel.node.id;
                panel.importDraft = panel.editor.draft.id;
                picker.open();
            }
        }
    }
    Studio.InlineError {
        Layout.fillWidth: true
        message: panel.entry ? panel.entry.error || "" : ""
    }
    Studio.StudioButton {
        visible: !!panel.entry && !!panel.entry.error
        text: qsTr("Tải lại script")
        onClicked: panel.editor.startup.retry(panel.node)
    }
    Label {
        Layout.fillWidth: true
        visible: panel.shared
        text: qsTr("Script dùng chung. Tạo bản riêng để sửa.")
        wrapMode: Text.WordWrap
    }
    Studio.StudioButton {
        visible: panel.shared
        enabled: !!panel.entry && panel.entry.ready
        text: qsTr("Tạo bản riêng")
        onClicked: panel.editor.startup.create(panel.node, panel.entry.text)
    }
    Studio.StartupCodeEditor {
        Layout.fillWidth: true
        Layout.preferredHeight: 300
        visible: !!panel.script
        entry: panel.entry
        contextKey: panel.contextKey + ":" + (panel.script ? panel.script.source : "")
        readOnly: panel.shared
        onEdited: text => panel.editor.startup.edit(panel.node, text)
    }
    Studio.StudioButton {
        flat: true
        iconName: "settings"
        objectName: "startupAdvancedToggle"
        text: qsTr("Tùy chọn khởi động")
        selected: panel.advanced
        onClicked: panel.advanced = !panel.advanced
    }
    Studio.NodeStartupAdvanced {
        Layout.fillWidth: true
        visible: panel.advanced
        editor: panel.editor
        nodeIndex: panel.nodeIndex
        custom: panel.mode === 2
        onModeRequested: value => panel.requestMode(value)
    }
    Studio.ConfirmDialog {
        id: replaceMode
        objectName: "startupReplaceModeDialog"
        parent: Overlay.overlay
        title: qsTr("Đổi cách khởi động?")
        message: panel.pendingMode && panel.pendingMode.value === 1
            ? qsTr("Máy sẽ chạy script thay cho lệnh tùy chỉnh.")
            : qsTr("Máy sẽ chạy lệnh tùy chỉnh thay cho script. Nội dung script được giữ lại.")
        confirmText: qsTr("Đổi")
        confirmEnabled: !panel.editor.backend.busy
        onAccepted: {
            const pending = panel.pendingMode;
            if (!pending || !panel.editor.draft || !panel.node || pending.draftId !== panel.editor.draft.id
                    || pending.nodeId !== panel.node.id || pending.revision !== panel.editor.draft.revision
                    || pending.definition !== panel.editor.definition) return;
            panel.applyMode(pending.value);
        }
        onClosed: panel.pendingMode = null
    }
    Studio.StudioFileDialog {
        id: picker
        title: qsTr("Chọn script khởi động")
        nameFilters: ["Shell script (*.sh)"]
        onAccepted: {
            if (!panel.editor.draft || panel.editor.draft.id !== panel.importDraft || !panel.node || panel.node.id !== panel.importNode) return;
            const url = selectedFile.toString();
            if (url.startsWith("file:///")) panel.editor.startup.importFile(panel.node, decodeURIComponent(url.substring(7)));
        }
    }
}
