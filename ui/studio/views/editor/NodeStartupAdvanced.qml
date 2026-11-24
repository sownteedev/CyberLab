import QtQuick
import QtQuick.Controls
import QtQuick.Layouts
import "../.." as Studio

ColumnLayout {
    id: panel
    required property var editor
    required property int nodeIndex
    required property bool custom
    readonly property var node: editor.document && editor.document.nodes[nodeIndex] ? editor.document.nodes[nodeIndex] : null
    readonly property var script: editor.startup.descriptor(node)
    signal modeRequested(int value)

    spacing: Studio.Theme.space8

    Label {
        visible: !!panel.script
        text: qsTr("Trình chạy script")
    }
    Studio.StudioComboBox {
        Layout.fillWidth: true
        Layout.maximumWidth: 320
        visible: !!panel.script
        Accessible.name: qsTr("Trình chạy script")
        objectName: "startupShell"
        model: ["/bin/sh", "/bin/bash"]
        currentIndex: panel.script && panel.script.shell.endsWith("bash") ? 1 : 0
        onActivated: index => panel.editor.change("nodes", panel.nodeIndex, "command", [model[index], panel.script.target])
    }
    Label {
        Layout.fillWidth: true
        visible: !!panel.script
        text: panel.script ? panel.script.source : ""
        color: Studio.Theme.textOnSurfaceVariant
        wrapMode: Text.WrapAnywhere
    }
    Studio.StudioToggle {
        Layout.fillWidth: true
        objectName: "startupCustomToggle"
        text: qsTr("Dùng lệnh tùy chỉnh")
        checked: panel.custom
        onClicked: {
            const requested = checked ? 2 : 0;
            checked = Qt.binding(() => panel.custom);
            panel.modeRequested(requested);
        }
    }
    Label {
        visible: panel.custom
        text: qsTr("Mỗi dòng một đối số")
    }
    Studio.StudioTextArea {
        property string editingNode: ""
        Layout.fillWidth: true
        visible: panel.custom
        Accessible.name: qsTr("Lệnh khởi động tùy chỉnh")
        objectName: "startupCustomCommand"
        text: panel.node ? (panel.node.command || []).join("\n") : ""
        wrapMode: TextEdit.WrapAnywhere
        onActiveFocusChanged: if (activeFocus) editingNode = panel.node.id
        onTextChanged: if (activeFocus && panel.node && editingNode === panel.node.id && text !== (panel.node.command || []).join("\n"))
            panel.editor.change("nodes", panel.nodeIndex, "command", text.split("\n").filter(value => value.length > 0))
    }
}
