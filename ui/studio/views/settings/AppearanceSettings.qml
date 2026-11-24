import QtQuick
import QtQuick.Controls.Basic
import QtQuick.Layouts
import "../.."
import "../.." as Studio

ColumnLayout {
    id: appearance

    function focusSelection() {
        const index = ["system", "light", "dark"].indexOf(Studio.Theme.themeMode);
        modes.itemAt(Math.max(0, index)).forceActiveFocus(Qt.TabFocusReason);
    }

    spacing: Studio.Theme.space16

    StudioSurface {
        Layout.fillWidth: true
        color: Studio.Theme.surfaceContainerLow
        implicitHeight: colorOptions.implicitHeight + Studio.Theme.space32

        ColumnLayout {
            id: colorOptions

            anchors.fill: parent
            anchors.margins: Studio.Theme.space16
            spacing: Studio.Theme.space8

            Label {
                color: Studio.Theme.textOnSurface
                font.pixelSize: Studio.Theme.titleSmall
                font.weight: Font.DemiBold
                text: "Chế độ màu"
            }
            RowLayout {
                Layout.fillWidth: true
                spacing: Studio.Theme.space8

                Repeater {
                    id: modes

                    model: [
                        {
                            mode: "system",
                            label: "Hệ thống",
                            icon: "desktop_windows"
                        },
                        {
                            mode: "light",
                            label: "Sáng",
                            icon: "light_mode"
                        },
                        {
                            mode: "dark",
                            label: "Tối",
                            icon: "dark_mode"
                        }
                    ]

                    StudioButton {
                        required property var modelData

                        Accessible.checkable: true
                        Accessible.checked: selected
                        Accessible.role: Accessible.RadioButton
                        Layout.fillWidth: true
                        Layout.preferredWidth: 1
                        leftPadding: appearance.width >= 380 ? Studio.Theme.space16 : Studio.Theme.space8
                        rightPadding: leftPadding
                        flat: true
                        iconName: appearance.width >= 380 ? modelData.icon : ""
                        objectName: "theme_" + modelData.mode
                        selected: Studio.Theme.themeMode === modelData.mode
                        text: modelData.label

                        onClicked: Studio.Theme.themeMode = modelData.mode
                    }
                }
            }
        }
    }
    StudioSurface {
        Layout.fillWidth: true
        color: Studio.Theme.surfaceContainerLow
        implicitHeight: zoomOptions.implicitHeight + Studio.Theme.space32

        ColumnLayout {
            id: zoomOptions

            anchors.fill: parent
            anchors.margins: Studio.Theme.space16
            spacing: Studio.Theme.space8

            Label {
                color: Studio.Theme.textOnSurface
                font.pixelSize: Studio.Theme.titleSmall
                font.weight: Font.DemiBold
                text: "Thu phóng ứng dụng"
            }
            RowLayout {
                Layout.fillWidth: true
                spacing: Studio.Theme.space8

                Item {
                    Layout.fillWidth: true
                    visible: appearance.width >= 460
                }
                StudioButton {
                    Accessible.name: "Thu nhỏ ứng dụng"
                    enabled: Studio.Theme.zoomPercent > Studio.Theme.minimumZoom
                    flat: true
                    objectName: "zoomOutButton"
                    text: "−"
                    onClicked: Studio.Theme.setZoomPercent(Studio.Theme.zoomPercent - 10)
                }
                Label {
                    Layout.fillWidth: appearance.width < 460
                    Layout.preferredWidth: Studio.Theme.rowHeight
                    horizontalAlignment: Text.AlignHCenter
                    color: Studio.Theme.textOnSurface
                    font.pixelSize: Studio.Theme.titleMedium
                    font.weight: Font.DemiBold
                    text: Studio.Theme.zoomPercent + "%"
                    objectName: "zoomPercentage"
                }
                StudioButton {
                    Accessible.name: "Phóng to ứng dụng"
                    enabled: Studio.Theme.zoomPercent < Studio.Theme.maximumZoom
                    flat: true
                    objectName: "zoomInButton"
                    text: "+"
                    onClicked: Studio.Theme.setZoomPercent(Studio.Theme.zoomPercent + 10)
                }
                StudioButton {
                    Accessible.name: "Khôi phục thu phóng 100%"
                    enabled: Studio.Theme.zoomPercent !== 100
                    flat: true
                    objectName: "zoomResetButton"
                    text: "100%"
                    onClicked: Studio.Theme.setZoomPercent(100)
                }
                Item {
                    Layout.fillWidth: true
                    visible: appearance.width >= 460
                }
            }
            Label {
                Layout.fillWidth: true
                color: Studio.Theme.textOnSurfaceVariant
                font.pixelSize: Studio.Theme.bodySmall
                text: "Ctrl + − / + để thu phóng · Ctrl + 0 để đặt lại"
                wrapMode: Text.WordWrap
            }
        }
    }
}
