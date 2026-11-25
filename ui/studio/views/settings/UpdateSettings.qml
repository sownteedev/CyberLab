import QtQuick
import QtQuick.Controls.Basic
import QtQuick.Layouts
import "../.." as Studio

ColumnLayout {
    id: page
    required property var updater
    signal updateRequested()
    function focusSelection() { checkButton.forceActiveFocus(Qt.TabFocusReason); }
    spacing: Studio.Theme.space16
    Studio.StudioSurface {
        Layout.fillWidth: true
        color: Studio.Theme.surfaceContainerLow
        implicitHeight: details.implicitHeight + Studio.Theme.space32
        ColumnLayout {
            id: details
            anchors.fill: parent
            anchors.margins: Studio.Theme.space16
            spacing: Studio.Theme.space16
            RowLayout {
                Layout.fillWidth: true
                spacing: Studio.Theme.space16
                Studio.Icon { name: page.updater.available ? "download" : "refresh"; size: 32; color: Studio.Theme.primary }
                ColumnLayout {
                    Layout.fillWidth: true
                    spacing: Studio.Theme.space4
                    Label {
                        objectName: "updateStatus"
                        Layout.fillWidth: true
                        text: page.updater.checking ? qsTr("Đang kiểm tra…") : page.updater.problem ? qsTr("Chưa kiểm tra được")
                            : page.updater.available ? qsTr("Có bản cập nhật")
                            : page.updater.checked && !page.updater.installedCommit ? qsTr("Chưa xác định phiên bản")
                            : page.updater.checked ? qsTr("Bạn đang dùng bản mới nhất") : qsTr("Cập nhật CyberLab")
                        font.pixelSize: Studio.Theme.titleMedium
                        font.weight: Font.DemiBold
                        color: Studio.Theme.textOnSurface
                        wrapMode: Text.WordWrap
                    }
                    Label {
                        Layout.fillWidth: true
                        text: page.updater.installedCommit ? qsTr("Đang cài · %1").arg(page.updater.installedCommit.slice(0, 12)) : qsTr("Bản cài chưa ghi nhận commit")
                        color: Studio.Theme.textOnSurfaceVariant
                        font.pixelSize: Studio.Theme.bodySmall
                        wrapMode: Text.WordWrap
                    }
                    Label {
                        Layout.fillWidth: true
                        visible: page.updater.available
                        text: qsTr("Bản mới · %1").arg(page.updater.latestCommit.slice(0, 12))
                        color: Studio.Theme.primary
                        font.pixelSize: Studio.Theme.bodySmall
                        wrapMode: Text.WordWrap
                    }
                }
            }
            Label {
                Layout.fillWidth: true
                text: page.updater.checked && !page.updater.installedCommit
                    ? qsTr("Chưa thể so sánh bản cài này với GitHub.")
                    : qsTr("Lưu nội dung đang sửa và dừng các bài trước khi cập nhật.")
                color: Studio.Theme.textOnSurfaceVariant
                wrapMode: Text.WordWrap
            }
            GridLayout {
                Layout.fillWidth: true
                columns: page.width < 440 ? 1 : 2
                columnSpacing: Studio.Theme.space8
                rowSpacing: Studio.Theme.space8
                Studio.StudioButton {
                    id: checkButton
                    objectName: "checkSystemUpdate"
                    text: qsTr("Kiểm tra cập nhật")
                    iconName: "refresh"
                    outlined: true
                    enabled: !page.updater.checking && !page.updater.handingOff
                    onClicked: page.updater.check(true)
                }
                Studio.StudioButton {
                    objectName: "installSystemUpdate"
                    visible: page.updater.available
                    text: page.updater.handingOff ? qsTr("Đang mở…") : qsTr("Cập nhật ngay")
                    iconName: "download"
                    highlighted: true
                    enabled: !page.updater.checking && !page.updater.handingOff
                    onClicked: page.updateRequested()
                }
            }
        }
    }
    Label {
        Layout.fillWidth: true
        text: qsTr("Nguồn: sownteedev/CyberLab · master")
        color: Studio.Theme.textOnSurfaceVariant
        font.pixelSize: Studio.Theme.bodySmall
        wrapMode: Text.WordWrap
    }
}
