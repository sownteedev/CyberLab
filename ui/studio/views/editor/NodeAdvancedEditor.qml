import QtQuick
import QtQuick.Controls.Material
import QtQuick.Layouts
import "../.."
import "../.." as Studio

ColumnLayout {
    id: panel
    required property var editor
    required property int nodeIndex
    property var node: editor.document && editor.document.nodes[nodeIndex] ? editor.document.nodes[nodeIndex] : null
    spacing: Studio.Theme.space16
    enabled: !editor.backend.busy

    ColumnLayout {
        Layout.fillWidth: true
        spacing: Studio.Theme.space8
        Label { Layout.fillWidth: true; text: panel.node ? panel.node.image : ""; wrapMode: Text.WrapAnywhere; color: Studio.Theme.textOnSurfaceVariant }
        Label { text: "Hostname" }
        StudioTextField { Layout.fillWidth: true; text: panel.node ? panel.node.hostname || "" : ""; placeholderText: "Mặc định theo mã máy"; onEditingFinished: panel.editor.change("nodes", panel.nodeIndex, "hostname", text) }
        Label { text: "Bộ nhớ (MiB)" }
        SpinBox {
            implicitHeight: Studio.Theme.controlHeight
            from: 64; to: 512; stepSize: 16
            value: panel.node && panel.node.resources ? panel.node.resources.memory_mb : 128
            onValueModified: panel.editor.change("nodes", panel.nodeIndex, "resources",
                Object.assign({}, panel.node.resources || {}, {memory_mb: value}))
        }
        Label { text: "CPU (millicores)" }
        SpinBox {
            implicitHeight: Studio.Theme.controlHeight
            from: 100; to: 1000; stepSize: 100
            value: panel.node && panel.node.resources ? panel.node.resources.cpu_millicores : 500
            onValueModified: panel.editor.change("nodes", panel.nodeIndex, "resources",
                Object.assign({}, panel.node.resources || {}, {cpu_millicores: value}))
        }
        Label { text: "Nhân bản container (Clone)" }
        SpinBox {
            implicitHeight: Studio.Theme.controlHeight
            from: 1; to: 4
            value: panel.node ? panel.node.clone || 1 : 1
            onValueModified: panel.editor.change("nodes", panel.nodeIndex, "clone", value)
        }
        Label { text: "Nhóm terminal" }
        StudioTextField {
            Layout.fillWidth: true
            placeholderText: "Ví dụ: client"
            text: panel.node ? panel.node.terminal_group || "" : ""
            onEditingFinished: panel.editor.change("nodes", panel.nodeIndex, "terminal_group", text.trim())
        }
        Label { text: "Tiêu đề terminal" }
        StudioTextField {
            Layout.fillWidth: true
            placeholderText: "Ví dụ: client@lab"
            text: panel.node ? panel.node.terminal_title || "" : ""
            onEditingFinished: panel.editor.change("nodes", panel.nodeIndex, "terminal_title", text.trim())
        }
        Label { text: "Alias nội bộ (cách nhau bằng dấu phẩy)" }
        StudioTextField {
            Layout.fillWidth: true
            placeholderText: "client-box"
            text: panel.node ? (panel.node.aliases || []).join(", ") : ""
            onEditingFinished: panel.editor.change("nodes", panel.nodeIndex, "aliases",
                text.split(",").map(value => value.trim()).filter(Boolean))
        }
        Label { text: "Hosts bổ sung (host=IPv4, cách nhau bằng dấu phẩy)" }
        StudioTextField {
            Layout.fillWidth: true
            placeholderText: "server=10.0.0.2"
            text: panel.node ? Object.keys(panel.node.extra_hosts || {}).map(host => host + "=" + panel.node.extra_hosts[host]).join(", ") : ""
            onEditingFinished: {
                const hosts = {};
                text.split(",").map(value => value.trim()).filter(Boolean).forEach(item => {
                    const parts = item.split("=");
                    if (parts.length === 2) hosts[parts[0].trim()] = parts[1].trim();
                });
                panel.editor.change("nodes", panel.nodeIndex, "extra_hosts", hosts);
            }
        }
        Label { text: "Chờ node (cách nhau bằng dấu phẩy)" }
        StudioTextField {
            Layout.fillWidth: true
            placeholderText: "server"
            text: panel.node ? (panel.node.wait_for || []).join(", ") : ""
            onEditingFinished: panel.editor.change("nodes", panel.nodeIndex, "wait_for",
                text.split(",").map(value => value.trim()).filter(Boolean))
        }
    }
    Label { text: "Lệnh chạy (mỗi dòng là một đối số, không qua shell)"; Layout.fillWidth: true; wrapMode: Text.WordWrap }
    StudioTextArea {
        Layout.fillWidth: true
        text: panel.node ? (panel.node.command || []).join("\n") : ""
        wrapMode: Text.WrapAnywhere
        onActiveFocusChanged: if (!activeFocus && panel.node) panel.editor.change("nodes", panel.nodeIndex, "command", text.split("\n").filter(value => value.length > 0))
    }
    SectionHeader { title: "Tài khoản"; Layout.fillWidth: true }
    CheckBox {
        implicitHeight: Studio.Theme.controlHeight
        text: "Tài khoản tùy chỉnh đã có trong image"
        checked: !!panel.node && !!panel.node.user
        onToggled: panel.editor.change("nodes", panel.nodeIndex, "user", checked
            ? {name: "", uid: 1000, gid: 1000, home: "/home/", shell: "/bin/sh"} : null)
    }
    Label {
        Layout.fillWidth: true
        text: "Chỉ dùng tài khoản đã có trong image. Kiểm tra runtime trước khi lưu vào thư viện."
        wrapMode: Text.WordWrap
        color: Studio.Theme.textOnSurfaceVariant
    }
    ColumnLayout {
        visible: !!panel.node && !!panel.node.user
        Layout.fillWidth: true
        spacing: Studio.Theme.space8
        Label { text: "User" }
        StudioTextField { Layout.fillWidth: true; text: panel.node && panel.node.user ? panel.node.user.name : ""; onEditingFinished: panel.editor.userField(panel.nodeIndex, "name", text) }
        Label { text: "UID / GID" }
        Flow {
            Layout.fillWidth: true
            Layout.preferredHeight: implicitHeight
            spacing: Studio.Theme.space8
            SpinBox {
                implicitHeight: Studio.Theme.controlHeight; from: 1000; to: 60000; editable: true; value: panel.node && panel.node.user ? panel.node.user.uid : 2000; onValueModified: panel.editor.userField(panel.nodeIndex, "uid", value) }
            SpinBox {
                implicitHeight: Studio.Theme.controlHeight; from: 1000; to: 60000; editable: true; value: panel.node && panel.node.user ? panel.node.user.gid : 2000; onValueModified: panel.editor.userField(panel.nodeIndex, "gid", value) }
        }
        Label { text: "Home" }
        Label { Layout.fillWidth: true; wrapMode: Text.WrapAnywhere; text: panel.node && panel.node.user ? panel.node.user.home : "" }
        Label { text: "Shell" }
        StudioComboBox {
            implicitHeight: Studio.Theme.controlHeight; model: ["/bin/sh", "/bin/bash"]; currentIndex: panel.node && panel.node.user ? model.indexOf(panel.node.user.shell) : 0; onActivated: panel.editor.userField(panel.nodeIndex, "shell", currentText) }
    }
    Label { text: "DNS nội bộ (IP cách nhau bằng dấu phẩy)"; Layout.fillWidth: true; wrapMode: Text.WordWrap }
    StudioTextField {
        Layout.fillWidth: true
        text: panel.node ? (panel.node.dns || []).join(", ") : ""
        onEditingFinished: panel.editor.change("nodes", panel.nodeIndex, "dns", text.split(",").map(value => value.trim()).filter(Boolean))
    }
}
