import QtQuick
import QtQuick.Controls.Basic
import QtQuick.Layouts
import "../.."
import "../.." as Studio

ColumnLayout {
    id: appearance
    property bool showPreview: true
    spacing: Studio.Theme.space16

    function focusSelection() {
        const index = ["system", "light", "dark"].indexOf(Studio.Theme.themeMode);
        modes.itemAt(Math.max(0, index)).forceActiveFocus(Qt.TabFocusReason);
    }

    SectionHeader {
        Layout.fillWidth: true
        title: "Giao diện"
        subtitle: "Chọn cách CyberLab hiển thị trên VM của bạn."
    }
    ColumnLayout {
        Layout.fillWidth: true
        spacing: Studio.Theme.space8
        Label {
            text: "Chế độ màu"
            font.pixelSize: Studio.Theme.titleSmall
            font.weight: Font.DemiBold
            color: Studio.Theme.textOnSurface
        }
        RowLayout {
            Layout.fillWidth: true
            spacing: Studio.Theme.space8
            Repeater {
                id: modes
                model: [
                    { mode: "system", label: "Hệ thống", icon: "desktop_windows" },
                    { mode: "light", label: "Sáng", icon: "light_mode" },
                    { mode: "dark", label: "Tối", icon: "dark_mode" }
                ]
                StudioButton {
                    required property var modelData
                    objectName: "theme_" + modelData.mode
                    Layout.fillWidth: true
                    Layout.preferredWidth: 1
                    text: modelData.label
                    iconName: modelData.icon
                    selected: Studio.Theme.themeMode === modelData.mode
                    Accessible.role: Accessible.RadioButton
                    Accessible.checkable: true
                    Accessible.checked: selected
                    onClicked: Studio.Theme.themeMode = modelData.mode
                }
            }
        }
    }
    StudioSurface {
        objectName: "appearancePreview"
        visible: appearance.showPreview
        Layout.fillWidth: true
        implicitHeight: 120
        color: Studio.Theme.surfaceContainerLow
        radius: Studio.Theme.shapeLargeIncreased
        RowLayout {
            anchors.fill: parent
            anchors.margins: Studio.Theme.space24
            spacing: Studio.Theme.space16
            Rectangle {
                Layout.preferredWidth: Studio.Theme.rowHeight
                Layout.preferredHeight: Studio.Theme.rowHeight
                radius: Studio.Theme.shapeLargeIncreased
                color: Studio.Theme.primaryContainer
                Icon { anchors.centerIn: parent; name: "science"; size: Studio.Theme.iconLarge; color: Studio.Theme.textOnPrimaryContainer }
            }
            ColumnLayout {
                Layout.fillWidth: true
                spacing: Studio.Theme.space8
                Label {
                    Layout.fillWidth: true
                    text: "CyberLab Studio"
                    elide: Text.ElideRight
                    font.pixelSize: Studio.Theme.titleMedium
                    font.weight: Font.DemiBold
                    color: Studio.Theme.textOnSurface
                }
                Label {
                    Layout.fillWidth: true
                    text: Studio.Theme.effectiveDark ? "Inter · Giao diện tối" : "Inter · Giao diện sáng"
                    wrapMode: Text.WordWrap
                    color: Studio.Theme.textOnSurfaceVariant
                    font.pixelSize: Studio.Theme.bodyMedium
                }
            }
            Icon { name: "check_circle"; color: Studio.Theme.primary }
        }
    }
    StudioSurface {
        Layout.fillWidth: true
        implicitHeight: motionRow.implicitHeight + Studio.Theme.space32
        radius: Studio.Theme.shapeLargeIncreased
        color: Studio.Theme.surfaceContainerLow
        RowLayout {
            id: motionRow
            anchors.fill: parent
            anchors.margins: Studio.Theme.space16
            spacing: Studio.Theme.space16
            Icon { name: "animation"; color: Studio.Theme.primary }
            ColumnLayout {
                Layout.fillWidth: true
                spacing: Studio.Theme.space8
                Label { text: "Giảm chuyển động"; color: Studio.Theme.textOnSurface; font.pixelSize: Studio.Theme.titleSmall; font.weight: Font.DemiBold }
                Label {
                    Layout.fillWidth: true
                    text: "Tắt chuyển động và hiệu ứng hộp thoại."
                    wrapMode: Text.WordWrap
                    color: Studio.Theme.textOnSurfaceVariant
                    font.pixelSize: Studio.Theme.bodySmall
                }
            }
            Switch {
                id: motionSwitch
                objectName: "reducedMotionSwitch"
                implicitHeight: Studio.Theme.controlHeight
                implicitWidth: Studio.Theme.rowHeight
                checked: Studio.Theme.reducedMotion
                Accessible.name: "Giảm chuyển động"
                onToggled: Studio.Theme.reducedMotion = checked
                indicator: Rectangle {
                    anchors.centerIn: parent
                    width: 52; height: 32
                    radius: Studio.Theme.shapeFull
                    color: motionSwitch.checked ? Studio.Theme.primary : Studio.Theme.surfaceVariant
                    border.width: motionSwitch.visualFocus ? Studio.Theme.focusWidth : Studio.Theme.borderWidth
                    border.color: motionSwitch.visualFocus ? Studio.Theme.primary : Studio.Theme.outline
                    Rectangle {
                        x: motionSwitch.checked ? 24 : 4
                        y: 4; width: 24; height: 24
                        radius: Studio.Theme.shapeFull
                        color: motionSwitch.checked ? Studio.Theme.textOnPrimary : Studio.Theme.outline
                        Icon { anchors.centerIn: parent; name: "check"; size: Studio.Theme.iconSmall; color: Studio.Theme.primary; visible: motionSwitch.checked }
                        Behavior on x { enabled: !Studio.Theme.reducedMotion; NumberAnimation { duration: Studio.Theme.stateDuration } }
                    }
                }
            }
        }
    }
    Item { Layout.fillHeight: true }
    Label {
        Layout.fillWidth: true
        text: "Tự lưu cho tài khoản này. Không thay đổi bài lab."
        wrapMode: Text.WordWrap
        color: Studio.Theme.textOnSurfaceVariant
        font.pixelSize: Studio.Theme.bodySmall
    }
}
