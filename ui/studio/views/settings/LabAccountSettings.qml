import QtQuick
import QtQuick.Controls.Basic
import QtQuick.Layouts
import "../.." as Studio
import "../../models/NodeDefaults.js" as Defaults

ColumnLayout {
    id: page

    readonly property bool valid: Defaults.validUsername(username.text)
    property bool saved: false

    function focusSelection() {
        username.text = Studio.LabPreferences.username;
        saved = false;
        username.forceActiveFocus(Qt.TabFocusReason);
    }
    function save() {
        if (Studio.LabPreferences.setUsername(username.text))
            saved = true;
    }

    spacing: Studio.Theme.space16

    Studio.StudioSurface {
        Layout.fillWidth: true
        color: Studio.Theme.surfaceContainerLow
        implicitHeight: form.implicitHeight + Studio.Theme.space32

        ColumnLayout {
            id: form

            anchors.fill: parent
            anchors.margins: Studio.Theme.space16
            spacing: Studio.Theme.space12

            Label {
                Layout.fillWidth: true
                color: Studio.Theme.textOnSurface
                font.pixelSize: Studio.Theme.titleSmall
                font.weight: Font.DemiBold
                text: qsTr("Tài khoản trong máy Ubuntu")
                wrapMode: Text.WordWrap
            }
            Label {
                Layout.fillWidth: true
                color: Studio.Theme.textOnSurfaceVariant
                text: qsTr("Dùng khi thêm máy Ubuntu mới hoặc chuyển môi trường của máy sang Ubuntu. Không đổi tài khoản Arch, bài đã lưu hay phiên đang chạy.")
                wrapMode: Text.WordWrap
            }
            Label {
                text: qsTr("Username mặc định")
                color: Studio.Theme.textOnSurface
            }
            Studio.StudioTextField {
                id: username

                Accessible.name: qsTr("Username mặc định cho máy Ubuntu mới")
                Layout.fillWidth: true
                Layout.minimumWidth: 0
                objectName: "defaultLabUsername"
                text: Studio.LabPreferences.username
                placeholderText: "student"
                selectByMouse: true
                onTextEdited: page.saved = false
                onAccepted: if (page.valid) page.save()
            }
            Label {
                Layout.fillWidth: true
                color: page.valid ? Studio.Theme.textOnSurfaceVariant : Studio.Theme.error
                text: qsTr("1–32 ký tự: bắt đầu bằng chữ thường a–z, sau đó dùng chữ thường, số, _ hoặc -. Không dùng tên tài khoản hệ thống như root, nobody, ubuntu.")
                wrapMode: Text.WordWrap
                objectName: "labUsernameRules"
            }
            Label {
                Layout.fillWidth: true
                color: Studio.Theme.primary
                font.family: Studio.Theme.monoFamily
                text: page.valid ? "/home/" + username.text : ""
                visible: page.valid
                objectName: "labUsernameHome"
                wrapMode: Text.WrapAnywhere
            }
            Studio.StudioButton {
                text: qsTr("Lưu username")
                iconName: "save"
                highlighted: true
                enabled: page.valid && username.text !== Studio.LabPreferences.username
                objectName: "saveLabUsername"
                onClicked: page.save()
            }
            Label {
                Layout.fillWidth: true
                color: Studio.Theme.textOnSurfaceVariant
                visible: page.saved || Studio.LabPreferences.invalidStoredValue
                text: Studio.LabPreferences.invalidStoredValue
                    ? qsTr("Username đã lưu không hợp lệ. Tạm dùng student; nhập và lưu tên mới để sửa.")
                    : qsTr("Đã lưu. Máy Ubuntu mới sẽ dùng username này.")
                wrapMode: Text.WordWrap
                objectName: "labUsernameStatus"
            }
        }
    }
}
