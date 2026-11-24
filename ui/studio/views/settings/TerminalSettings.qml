import QtQuick
import QtQuick.Controls.Basic
import QtQuick.Layouts
import "../.."
import "../.." as Studio
import "../../models/Messages.js" as Messages

ColumnLayout {
    id: panel

    readonly property var choices: [
        {
            id: "auto",
            name: "Tự động"
        }
    ].concat(state.options)
    required property var preferences
    readonly property string selectionReason: ({
            preference: "Lựa chọn của bạn trong CyberLab",
            xdg: "Mặc định hệ thống (XDG)",
            environment: "Mặc định từ biến TERMINAL",
            alternative: "Mặc định hệ thống (x-terminal-emulator)",
            fallback: "Tự chọn từ các terminal đang có",
            unavailable: "Chưa tìm thấy terminal tương thích"
        })[state.source] || ""
    readonly property var state: preferences.state
    readonly property string warningText: state.warnings.map(code => ({
                "invalid-config": "Không đọc được cấu hình terminal. CyberLab đang tạm dùng Tự động; chọn lại để lưu cấu hình hợp lệ.",
                "missing-preferred": "Terminal đã lưu (" + state.preferred + ") không còn khả dụng. Lựa chọn vẫn được giữ; tạm dùng terminal khác.",
                "xdg-unavailable": "Không xác định được terminal tương thích từ XDG; đang dùng cách nhận diện dự phòng.",
                "no-terminal": "Chưa có terminal phù hợp. Bạn có thể bổ sung Xfce Terminal hoặc dùng cyberlab terminal trong một TTY."
            })[code] || code).join("\n")

    function focusSelection() {
        if (terminalChoice.visible && terminalChoice.enabled)
            terminalChoice.forceActiveFocus(Qt.TabFocusReason);
        else
            refreshButton.forceActiveFocus(Qt.TabFocusReason);
    }

    spacing: Studio.Theme.space16

    StudioSurface {
        Layout.fillWidth: true
        color: Studio.Theme.surfaceContainerLow
        implicitHeight: selectedTerminal.implicitHeight + Studio.Theme.space32

        RowLayout {
            id: selectedTerminal

            anchors.fill: parent
            anchors.margins: Studio.Theme.space16
            spacing: Studio.Theme.space16

            Icon {
                color: Studio.Theme.primary
                name: "terminal"
                size: Studio.Theme.iconLarge
            }
            ColumnLayout {
                Layout.fillWidth: true
                spacing: Studio.Theme.space8

                Label {
                    Layout.fillWidth: true
                    color: Studio.Theme.textOnSurface
                    font.pixelSize: Studio.Theme.titleLarge
                    font.weight: Font.DemiBold
                    objectName: "selectedTerminalName"
                    text: !panel.preferences.loaded ? "Đang nhận diện terminal…" : panel.state.selected ? panel.state.selected.name : "Chưa có terminal"
                    wrapMode: Text.Wrap
                }
                Label {
                    Layout.fillWidth: true
                    color: Studio.Theme.textOnSurfaceVariant
                    objectName: "terminalSelectionReason"
                    text: panel.preferences.loaded ? panel.selectionReason : ""
                    wrapMode: Text.Wrap
                }
            }
        }
    }
    StudioComboBox {
        id: terminalChoice

        Accessible.name: "Ứng dụng terminal cho CyberLab"
        Layout.fillWidth: true
        currentIndex: panel.choices.findIndex(option => option.id === panel.state.preferred)
        displayText: currentIndex < 0 ? "Đã lưu: " + panel.state.preferred + " (không khả dụng)" : currentText
        enabled: !panel.preferences.busy
        model: panel.choices
        objectName: "terminalChoice"
        textRole: "name"
        visible: panel.state.options.length > 1

        onActivated: panel.preferences.select(panel.choices[currentIndex].id)
    }
    Label {
        Layout.fillWidth: true
        color: Studio.Theme.textOnSurfaceVariant
        text: "Lựa chọn dùng chung cho Studio và CLI, chỉ áp dụng cho cửa sổ mở tiếp theo. Các terminal đang chạy không thay đổi."
        wrapMode: Text.Wrap
    }
    Label {
        Layout.fillWidth: true
        color: Studio.Theme.error
        objectName: "terminalWarning"
        text: Messages.text(panel.preferences.error || panel.warningText)
        textFormat: Text.PlainText
        Studio.ErrorNotifier { message: panel.preferences.error }
        visible: text.length > 0
        wrapMode: Text.Wrap
    }
    RowLayout {
        Layout.fillWidth: true
        spacing: Studio.Theme.space8

        StudioButton {
            id: refreshButton

            enabled: !panel.preferences.busy
            iconName: "refresh"
            objectName: "refreshTerminalsButton"
            text: panel.preferences.busy ? "Đang nhận diện…" : "Quét lại"

            onClicked: panel.preferences.refresh()
        }
        StudioButton {
            enabled: !panel.preferences.busy
            objectName: "automaticTerminalButton"
            text: "Dùng tự động"
            visible: panel.state.preferred !== "auto" || panel.state.warnings.includes("invalid-config")

            onClicked: panel.preferences.select("auto")
        }
        Item {
            Layout.fillWidth: true
        }
    }
}
