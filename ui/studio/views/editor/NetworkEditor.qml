import QtQuick
import QtQuick.Controls.Material
import QtQuick.Layouts
import "../.."
import "../.." as Studio
import "../../models/EditorModel.js" as Model

ColumnLayout {
    id: panel

    required property var editor
    property var network: editor.document && editor.document.networks[networkIndex] ? editor.document.networks[networkIndex] : null
    required property int networkIndex
    property bool advanced: false
    onNetworkIndexChanged: advanced = false

    enabled: !editor.backend.busy
    spacing: Studio.Theme.space16

    Label {
        text: "Tên mạng"
        color: Studio.Theme.textOnSurface
    }
    StudioTextField {
        Layout.fillWidth: true
        Accessible.name: "Tên mạng"
        objectName: "draftNetworkId"
        text: panel.network ? panel.network.id : ""

        onEditingFinished: panel.editor.change("networks", panel.networkIndex, "id", text)
    }
    Studio.StudioToggle {
        Layout.fillWidth: true
        objectName: "draftNetworkInternet"
        text: "Internet"
        visible: !!panel.editor.policy && !!panel.editor.policy.network_internet
        checked: Model.networkInternet(panel.editor.document, panel.network)
        onToggled: panel.editor.change("networks", panel.networkIndex, "internet", checked)
    }
    Label {
        text: "Dải địa chỉ IP (tùy chọn)"
        color: Studio.Theme.textOnSurface
    }
    StudioTextField {
        Layout.fillWidth: true
        Accessible.name: "Subnet IPv4"
        objectName: "draftNetworkSubnet"
        placeholderText: "Để trống: tự động · ví dụ 10.231.20.0/24"
        text: panel.network ? panel.network.subnet || "" : ""

        onEditingFinished: panel.editor.change("networks", panel.networkIndex, "subnet", text.trim())
    }
    InlineError {
        notifyError: false
        Layout.fillWidth: true
        message: panel.editor.report && !panel.editor.dirty ? (panel.editor.report.issues || []).filter(issue => issue.path.startsWith("/networks") || issue.stage === "lab").map(issue => issue.path + ": " + issue.message).join("\n") : ""
    }
    Label {
        visible: panel.advanced
        text: "IP cổng kết nối"
        color: Studio.Theme.textOnSurface
    }
    StudioTextField {
        Layout.fillWidth: true
        Accessible.name: "Bridge gateway"
        objectName: "draftNetworkGateway"
        visible: panel.advanced
        enabled: !!panel.network && !!panel.network.subnet
        placeholderText: "Mặc định: IP khả dụng đầu tiên trong dải mạng"
        text: panel.network ? panel.network.gateway || "" : ""

        onEditingFinished: panel.editor.change("networks", panel.networkIndex, "gateway", text.trim())
    }
    StudioButton {
        flat: true
        iconName: "settings"
        objectName: "networkAdvancedToggle"
        text: panel.advanced ? "Ẩn nâng cao" : "Nâng cao"
        onClicked: panel.advanced = !panel.advanced
    }
    StudioButton {
        danger: true
        flat: true
        iconName: "delete"
        text: "Xóa mạng khỏi nháp"

        onClicked: panel.editor.modify("networks", null, panel.networkIndex)
    }
}
