import QtQuick
import QtQuick.Controls
import QtQuick.Layouts
import "../../models/NodeDefaults.js" as Defaults
import "../../models/EditorModel.js" as Model
import "../.."
import "../.." as Studio

ColumnLayout {
    id: panel
    required property var editor
    required property int nodeIndex
    readonly property var node: editor.document && editor.document.nodes[nodeIndex] ? editor.document.nodes[nodeIndex] : null
    readonly property var images: Defaults.profiles(editor.policy)
    readonly property var accounts: Defaults.accountOptions(editor.policy, node)
    readonly property int terminalMaximum: Defaults.terminalCapacity(editor.document, nodeIndex, editor.policy)
    property bool advanced: false
    property var pendingImage: null
    property var pendingRemoval: null
    spacing: Studio.Theme.space12
    enabled: !editor.backend.busy
    onNodeIndexChanged: advanced = false

    GridLayout {
        Layout.fillWidth: true
        columns: panel.width >= 620 ? 2 : 1
        columnSpacing: Studio.Theme.space16
        rowSpacing: Studio.Theme.space12
        ColumnLayout {
            Layout.fillWidth: true
            spacing: Studio.Theme.space8
            Label { text: "Tên máy" }
            StudioTextField {
                objectName: "basicNodeName"
                Layout.fillWidth: true
                text: panel.node ? panel.node.id : ""
                Accessible.name: "Tên máy"
                onEditingFinished: panel.editor.change("nodes", panel.nodeIndex, "id", text.trim())
            }
        }
        ColumnLayout {
            Layout.fillWidth: true
            spacing: Studio.Theme.space8
            Label { text: "Môi trường" }
            StudioComboBox {
                id: imageChoice
                objectName: "basicNodeImage"
                Layout.fillWidth: true
                model: panel.images
                textRole: "label"
                currentIndex: panel.node ? panel.images.findIndex(entry => entry.image === panel.node.image) : -1
                displayText: currentIndex < 0 ? (panel.node ? panel.node.image || "Chọn môi trường" : "Chọn môi trường") : currentText
                Accessible.name: "Môi trường của máy"
                onActivated: {
                    const image = panel.images[currentIndex].image;
                    if (!panel.node || image === panel.node.image) return;
                    panel.pendingImage = {image: image, nodeId: panel.node.id, draftId: panel.editor.draft.id};
                    imageChange.open();
                }
            }
        }
        ColumnLayout {
            Layout.fillWidth: true
            spacing: Studio.Theme.space8
            Label { text: "Tài khoản" }
            StudioComboBox {
                objectName: "basicNodeAccount"
                Layout.fillWidth: true
                model: panel.accounts
                textRole: "label"
                currentIndex: panel.accounts.findIndex(option => panel.node && (panel.node.user
                    ? Defaults.sameAccount(option.user, panel.node.user) : !option.user))
                Accessible.name: "Tài khoản có sẵn trong môi trường"
                onActivated: panel.editor.change("nodes", panel.nodeIndex, "user", panel.accounts[currentIndex].user)
            }
        }
        ColumnLayout {
            Layout.fillWidth: true
            spacing: Studio.Theme.space8
            Label { text: "Terminal" }
            RowLayout {
                SpinBox {
                    objectName: "basicTerminalCount"
                    implicitHeight: Studio.Theme.controlHeight
                    from: 1; to: Math.max(panel.node ? panel.node.terminal_count || 1 : 1, panel.terminalMaximum)
                    value: panel.node ? panel.node.terminal_count || 1 : 1
                    Accessible.name: "Số terminal"
                    onValueModified: panel.editor.change("nodes", panel.nodeIndex, "terminal_count", value)
                }
                CheckBox {
                    text: "Tự mở"
                    checked: !!panel.node && (panel.editor.document.terminals || []).includes(panel.node.id)
                    onToggled: panel.editor.autoOpen(panel.node.id, checked)
                }
            }
        }
    }
    Label {
        Layout.fillWidth: true
        wrapMode: Text.WrapAnywhere
        text: panel.node ? "File của máy: " + Model.workspace(panel.node) + "/" : ""
        color: Studio.Theme.textOnSurfaceVariant
        font.pixelSize: Studio.Theme.bodySmall
    }
    Label {
        Layout.fillWidth: true
        visible: !!panel.node && !(Defaults.profile(panel.editor.policy, panel.node.image) || {}).command
        text: "Môi trường chưa có cấu hình sẵn. Mở Nâng cao để kiểm tra lệnh và tài khoản."
        color: Studio.Theme.textOnSurfaceVariant
        wrapMode: Text.WordWrap
    }
    Label { text: "Mạng"; font.weight: Font.Medium }
    Repeater {
        model: panel.editor.document ? panel.editor.document.networks : []
        RowLayout {
            id: connection
            required property var modelData
            Layout.fillWidth: true
            CheckBox {
                text: connection.modelData.id
                checked: !!panel.node && panel.node.networks.includes(connection.modelData.id)
                onToggled: panel.editor.attach(panel.nodeIndex, connection.modelData.id, checked,
                    checked ? Defaults.nextAddress(panel.editor.document, connection.modelData.id) : "")
            }
            StudioTextField {
                Layout.fillWidth: true
                Layout.maximumWidth: 280
                enabled: !!panel.node && panel.node.networks.includes(connection.modelData.id) && !!connection.modelData.subnet
                placeholderText: connection.modelData.subnet ? "Địa chỉ IP" : "IP tự động"
                text: panel.node ? (panel.node.addresses || {})[connection.modelData.id] || "" : ""
                Accessible.name: "IP trên mạng " + connection.modelData.id
                onEditingFinished: if (enabled) panel.editor.attach(panel.nodeIndex, connection.modelData.id, true, text.trim())
            }
        }
    }
    StudioButton {
        objectName: "nodeAdvancedToggle"
        text: panel.advanced ? "Ẩn nâng cao" : "Nâng cao"
        iconName: "settings"
        flat: true
        onClicked: panel.advanced = !panel.advanced
    }
    Loader {
        Layout.fillWidth: true
        active: panel.advanced
        visible: active
        sourceComponent: NodeAdvancedEditor { editor: panel.editor; nodeIndex: panel.nodeIndex }
    }
    StudioButton {
        text: "Xóa máy"
        iconName: "delete"
        flat: true
        danger: true
        onClicked: {
            if (!panel.node || !panel.editor.draft) return;
            panel.pendingRemoval = {nodeId: panel.node.id, draftId: panel.editor.draft.id};
            removeMachine.open();
        }
    }
    ConfirmDialog {
        id: imageChange
        objectName: "changeNodeImageDialog"
        parent: Overlay.overlay
        title: "Đổi môi trường của máy?"
        message: "Tài khoản và thư mục home sẽ theo môi trường mới. Lệnh tùy chỉnh và file đã thêm vẫn được giữ. Kiểm tra runtime trước khi dùng."
        confirmText: "Đổi môi trường"
        confirmEnabled: !panel.editor.backend.busy
        onClosed: imageChoice.currentIndex = Qt.binding(() => panel.node ? panel.images.findIndex(entry => entry.image === panel.node.image) : -1)
        onAccepted: {
            const pending = panel.pendingImage;
            if (!pending || !panel.editor.draft || pending.draftId !== panel.editor.draft.id) return;
            const index = panel.editor.document.nodes.findIndex(entry => entry.id === pending.nodeId);
            if (index >= 0) panel.editor.selectImage(index, pending.image);
        }
    }
    ConfirmDialog {
        id: removeMachine
        parent: Overlay.overlay
        title: "Xóa máy khỏi bản nháp?"
        message: panel.pendingRemoval ? "Xóa cấu hình " + panel.pendingRemoval.nodeId + ". Tài nguyên gốc vẫn được giữ trong bản nháp." : ""
        danger: true
        confirmText: "Xóa máy"
        confirmEnabled: !panel.editor.backend.busy
        onAccepted: {
            const target = panel.pendingRemoval;
            if (!target || !panel.editor.draft || target.draftId !== panel.editor.draft.id) return;
            const index = panel.editor.document.nodes.findIndex(entry => entry.id === target.nodeId);
            if (index >= 0) panel.editor.modify("nodes", null, index);
        }
    }
}
