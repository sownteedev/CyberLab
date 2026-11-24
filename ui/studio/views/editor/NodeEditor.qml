import QtQuick
import QtQuick.Controls
import QtQuick.Layouts
import "../../models/NodeDefaults.js" as Defaults
import "../.."
import "../.." as Studio

ColumnLayout {
    id: panel
    objectName: "nodeConfigurationPanel"

    property bool advanced: false
    required property var editor
    readonly property var images: Defaults.profiles(editor.policy)
    readonly property var node: editor.document && editor.document.nodes[nodeIndex] ? editor.document.nodes[nodeIndex] : null
    required property int nodeIndex
    readonly property string contextKey: (editor.draft ? editor.draft.id : "") + ":" + (node ? node.id : "")
    property var pendingImage: null
    property var pendingRemoval: null
    readonly property int terminalMaximum: Defaults.terminalCapacity(editor.document, nodeIndex, editor.policy)

    enabled: !editor.backend.busy
    spacing: Studio.Theme.space12

    onNodeIndexChanged: advanced = false
    onContextKeyChanged: advanced = false

    GridLayout {
        Layout.fillWidth: true
        columnSpacing: Studio.Theme.space16
        columns: panel.width >= 620 ? 2 : 1
        rowSpacing: Studio.Theme.space12

        ColumnLayout {
            Layout.fillWidth: true
            Layout.preferredWidth: 240
            Layout.minimumWidth: 0
            spacing: Studio.Theme.space8

            Label {
                text: "Tên máy"
            }
            StudioTextField {
                Accessible.name: "Tên máy"
                Layout.fillWidth: true
                objectName: "basicNodeName"
                text: panel.node ? panel.node.id : ""

                onEditingFinished: panel.editor.change("nodes", panel.nodeIndex, "id", text.trim())
            }
        }
        ColumnLayout {
            Layout.fillWidth: true
            Layout.preferredWidth: 240
            Layout.minimumWidth: 0
            spacing: Studio.Theme.space8

            Label {
                text: "Môi trường"
            }
            StudioComboBox {
                id: imageChoice

                Accessible.name: "Môi trường của máy"
                Layout.fillWidth: true
                currentIndex: panel.node ? panel.images.findIndex(entry => entry.image === panel.node.image) : -1
                displayText: currentIndex < 0 ? (panel.node ? panel.node.image || "Chọn môi trường" : "Chọn môi trường") : currentText
                model: panel.images
                objectName: "basicNodeImage"
                textRole: "label"

                onActivated: {
                    const image = panel.images[currentIndex].image;
                    if (!panel.node || image === panel.node.image)
                        return;
                    panel.pendingImage = {
                        image: image,
                        nodeId: panel.node.id,
                        draftId: panel.editor.draft.id
                    };
                    imageChange.open();
                }
            }
        }
        NodeAccountEditor {
            Layout.fillWidth: true
            Layout.preferredWidth: 240
            Layout.minimumWidth: 0
            editor: panel.editor
            nodeIndex: panel.nodeIndex
        }
        ColumnLayout {
            Layout.fillWidth: true
            Layout.preferredWidth: 240
            Layout.minimumWidth: 0
            spacing: Studio.Theme.space8

            Label {
                text: "Terminal"
            }
            GridLayout {
                Layout.fillWidth: true
                columns: width >= 280 ? 2 : 1
                columnSpacing: Studio.Theme.space12
                rowSpacing: Studio.Theme.space8
                EditorNumberField {
                    Accessible.name: "Số terminal"
                    from: 1
                    implicitHeight: Studio.Theme.controlHeight
                    objectName: "basicTerminalCount"
                    to: Math.max(panel.node ? panel.node.terminal_count || 1 : 1, panel.terminalMaximum)
                    value: panel.node ? panel.node.terminal_count || 1 : 1

                    onValueModified: panel.editor.change("nodes", panel.nodeIndex, "terminal_count", value)
                }
                StudioToggle {
                    Layout.fillWidth: true
                    checked: !!panel.node && (panel.editor.document.terminals || []).includes(panel.node.id)
                    text: "Tự mở"

                    onToggled: panel.editor.autoOpen(panel.node.id, checked)
                }
            }
        }
    }
    Label {
        Layout.fillWidth: true
        color: Studio.Theme.textOnSurfaceVariant
        text: "Môi trường chưa có cấu hình sẵn. Mở Nâng cao để kiểm tra lệnh và tài khoản."
        visible: !!panel.node && !(Defaults.profile(panel.editor.policy, panel.node.image) || {}).command
        wrapMode: Text.WordWrap
    }
    Studio.NodeNetworkList {
        editor: panel.editor
        nodeIndex: panel.nodeIndex
    }
    StudioButton {
        flat: true
        iconName: "settings"
        objectName: "nodeAdvancedToggle"
        text: panel.advanced ? "Ẩn nâng cao" : "Nâng cao"

        onClicked: panel.advanced = !panel.advanced
    }
    Loader {
        Layout.fillWidth: true
        active: panel.advanced
        visible: active

        sourceComponent: NodeAdvancedEditor {
            editor: panel.editor
            nodeIndex: panel.nodeIndex
        }
    }
    StudioButton {
        danger: true
        flat: true
        iconName: "delete"
        text: "Xóa máy"

        onClicked: {
            if (!panel.node || !panel.editor.draft)
                return;
            panel.pendingRemoval = {
                nodeId: panel.node.id,
                draftId: panel.editor.draft.id
            };
            removeMachine.open();
        }
    }
    ConfirmDialog {
        id: imageChange

        confirmEnabled: !panel.editor.backend.busy
        confirmText: "Đổi môi trường"
        message: "Tài khoản và tài nguyên theo môi trường mới. Script và file đã thêm vẫn được giữ."
        objectName: "changeNodeImageDialog"
        parent: Overlay.overlay
        title: "Đổi môi trường của máy?"

        onAccepted: {
            const pending = panel.pendingImage;
            if (!pending || !panel.editor.draft || pending.draftId !== panel.editor.draft.id)
                return;
            const index = panel.editor.document.nodes.findIndex(entry => entry.id === pending.nodeId);
            if (index >= 0)
                panel.editor.selectImage(index, pending.image);
        }
        onClosed: imageChoice.currentIndex = Qt.binding(() => panel.node ? panel.images.findIndex(entry => entry.image === panel.node.image) : -1)
    }
    ConfirmDialog {
        id: removeMachine

        confirmEnabled: !panel.editor.backend.busy
        confirmText: "Xóa máy"
        danger: true
        message: panel.pendingRemoval ? "Xóa cấu hình " + panel.pendingRemoval.nodeId + ". Tài nguyên gốc vẫn được giữ trong bản nháp." : ""
        parent: Overlay.overlay
        title: "Xóa máy khỏi bản nháp?"

        onAccepted: {
            const target = panel.pendingRemoval;
            if (!target || !panel.editor.draft || target.draftId !== panel.editor.draft.id)
                return;
            const index = panel.editor.document.nodes.findIndex(entry => entry.id === target.nodeId);
            if (index >= 0)
                panel.editor.modify("nodes", null, index);
        }
    }
}
