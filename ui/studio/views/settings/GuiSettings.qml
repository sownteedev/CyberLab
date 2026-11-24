import QtQuick
import QtQuick.Controls.Basic
import QtQuick.Layouts
import "../.." as Studio

ColumnLayout {
    id: panel

    required property var preferences

    function focusSelection() { backendChoice.forceActiveFocus(Qt.TabFocusReason); }

    spacing: Studio.Theme.space16

    Studio.SectionHeader {
        Layout.fillWidth: true
        title: qsTr("Cửa sổ ứng dụng trong Lab")
    }
    Studio.StudioComboBox {
        id: backendChoice

        Layout.fillWidth: true
        objectName: "guiBackendChoice"
        Accessible.name: qsTr("Cách hiển thị ứng dụng GUI")
        model: [qsTr("Tự động: trực tiếp / Xpra"), qsTr("Luôn dùng Xpra")]
        currentIndex: panel.preferences.state.preferred === "xpra" ? 1 : 0
        enabled: !panel.preferences.busy
        onActivated: panel.preferences.select(currentIndex === 1 ? "xpra" : "auto")
    }
    Label {
        Layout.fillWidth: true
        objectName: "guiBackendStatus"
        color: Studio.Theme.textOnSurface
        text: panel.preferences.state.host.ready ? (panel.preferences.state.host.backend === "native-x11" ? (panel.preferences.state.host.display_server === "Xwayland" ? qsTr("Sẵn sàng: XWayland trực tiếp") : qsTr("Sẵn sàng: Native X11")) : qsTr("Sẵn sàng: Xpra")) : qsTr("Chưa kết nối GUI")
        wrapMode: Text.WordWrap
    }
    Label {
        Layout.fillWidth: true
        color: Studio.Theme.textOnSurfaceVariant
        text: qsTr("Kết nối trực tiếp chia sẻ X server với ứng dụng X11 trên desktop. Chỉ dùng với Lab đáng tin cậy; chọn Xpra để cách ly hiển thị.")
        wrapMode: Text.WordWrap
    }
    Label {
        Layout.fillWidth: true
        color: Studio.Theme.textOnSurfaceVariant
        text: qsTr("Thay đổi áp dụng khi bắt đầu, tiếp tục hoặc làm lại phiên; không chuyển backend hay đóng cửa sổ đang mở.")
        wrapMode: Text.WordWrap
    }
    Studio.InlineError {
        Layout.fillWidth: true
        message: panel.preferences.error || panel.preferences.state.warning || panel.preferences.state.host.fallback_reason || ""
    }
    Studio.StudioButton {
        objectName: "refreshGuiBackend"
        text: qsTr("Kiểm tra lại")
        enabled: !panel.preferences.busy
        onClicked: panel.preferences.refresh()
    }
}
