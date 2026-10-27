import QtQuick
import QtQuick.Controls.Material
import QtQuick.Layouts
import "../.."
import "../.." as Studio

ColumnLayout {
    id: panel
    required property var editor
    required property int networkIndex
    property var network: editor.document && editor.document.networks[networkIndex] ? editor.document.networks[networkIndex] : null
    spacing: Studio.Theme.space16
    enabled: !editor.backend.busy
    Label { text: "Mạng nội bộ"; font.bold: true }
    Label { text: "Mã mạng" }
    StudioTextField { Layout.fillWidth: true; text: panel.network ? panel.network.id : ""; onEditingFinished: panel.editor.change("networks", panel.networkIndex, "id", text) }
    Label { text: "Subnet IPv4" }
    StudioTextField { Layout.fillWidth: true; text: panel.network ? panel.network.subnet || "" : ""; placeholderText: "Để trống: tự động · ví dụ 10.231.20.0/24"; onEditingFinished: panel.editor.change("networks", panel.networkIndex, "subnet", text.trim()) }
    InlineError {
        Layout.fillWidth: true
        message: panel.editor.report && !panel.editor.dirty
            ? (panel.editor.report.issues || []).filter(issue => issue.path.startsWith("/networks") || issue.stage === "lab")
                .map(issue => issue.path + ": " + issue.message).join("\n") : ""
    }
    Label { text: "Bridge gateway" }
    StudioTextField { Layout.fillWidth: true; enabled: !!panel.network && !!panel.network.subnet; text: panel.network ? panel.network.gateway || "" : ""; placeholderText: "Mặc định địa chỉ đầu tiên trong subnet"; onEditingFinished: panel.editor.change("networks", panel.networkIndex, "gateway", text.trim()) }
    Label {
        Layout.fillWidth: true
        text: "Chỉ mạng nội bộ RFC1918 /16–/30. Gateway là bridge Docker, không phải máy router. Subnet trùng với Session khác sẽ bị từ chối."
        wrapMode: Text.WordWrap
        color: Studio.Theme.textOnSurfaceVariant
    }
    SectionHeader { title: "Máy kết nối"; titleSize: Studio.Theme.titleMedium; iconName: "lan"; Layout.fillWidth: true }
    Repeater {
        model: panel.network && panel.editor.document ? panel.editor.document.nodes.filter(node => node.networks.includes(panel.network.id)) : []
        Label {
            required property var modelData
            Layout.fillWidth: true
            text: modelData.id + " · " + ((modelData.addresses || {})[panel.network.id] || "IP tự động")
                + " · DNS: " + ((modelData.dns || []).join(", ") || "Nội bộ mặc định")
            wrapMode: Text.WrapAnywhere
            color: Studio.Theme.textOnSurfaceVariant
        }
    }
    Label {
        Layout.fillWidth: true
        text: "Chọn DNS và IP tĩnh trong Máy lab → Kết nối mạng."
        wrapMode: Text.WordWrap
        color: Studio.Theme.textOnSurfaceVariant
    }
    StudioButton { iconName: "delete"; text: "Xóa mạng khỏi nháp"; danger: true; onClicked: panel.editor.modify("networks", null, panel.networkIndex) }
}
