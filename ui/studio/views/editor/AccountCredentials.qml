import QtQuick
import QtQuick.Controls.Basic
import QtQuick.Layouts
import "../.." as Studio

ColumnLayout {
    id: credentials
    required property var editor
    required property int nodeIndex
    required property string accountName
    required property string contextKey
    property bool mainAccount: false
    property bool showSudo: true
    property string sudoMode: "disabled"
    property string passwordState: "!"
    readonly property bool passwordReady: !editor.dirty && !editor.accountPasswordPending && !editor.backend.busy
    readonly property int passwordByteLength: utf8ByteLength(password.text)
    readonly property bool passwordValid: passwordByteLength > 0 && passwordByteLength <= 128
    spacing: Studio.Theme.space8
    onContextKeyChanged: dismissPassword()
    onAccountNameChanged: dismissPassword()
    onVisibleChanged: if (!visible) dismissPassword()
    onPasswordReadyChanged: if (!passwordReady) dismissPassword()

    function dismissPassword() {
        password.clear();
        passwordDialog.close();
    }

    function applyPassword(action) {
        const secret = password.text;
        dismissPassword();
        editor.setAccountPassword(nodeIndex, accountName, action, secret);
    }

    function utf8ByteLength(value) {
        let bytes = 0;
        for (let index = 0; index < value.length; index += 1) {
            let code = value.charCodeAt(index);
            if (code >= 0xD800 && code <= 0xDBFF) {
                const low = value.charCodeAt(index + 1);
                if (low >= 0xDC00 && low <= 0xDFFF) {
                    code = 0x10000 + ((code - 0xD800) << 10) + low - 0xDC00;
                    index += 1;
                } else {
                    return 0;
                }
            } else if (code >= 0xDC00 && code <= 0xDFFF) {
                return 0;
            }
            bytes += code < 0x80 ? 1 : code < 0x800 ? 2 : code < 0x10000 ? 3 : 4;
        }
        return bytes;
    }

    Label { visible: credentials.showSudo; text: qsTr("Quyền sudo"); color: Studio.Theme.textOnSurface }
    Studio.StudioComboBox {
        visible: credentials.showSudo
        Layout.fillWidth: true
        objectName: credentials.showSudo ? (credentials.mainAccount ? "mainAccountSudo" : "extraAccountSudo-" + credentials.accountName) : ""
        model: [qsTr("Không cho phép"), qsTr("Yêu cầu mật khẩu"), qsTr("Không cần mật khẩu")]
        currentIndex: ["disabled", "password", "passwordless"].indexOf(credentials.sudoMode)
        onActivated: credentials.editor.accountChange(credentials.nodeIndex, "sudo", credentials.accountName, ["disabled", "password", "passwordless"][currentIndex])
    }
    Label {
        Layout.fillWidth: true
        text: credentials.passwordState === "!" ? qsTr("Mật khẩu đang khóa") : credentials.passwordState ? qsTr("Đã đặt mật khẩu") : qsTr("Mật khẩu mặc định")
        color: Studio.Theme.textOnSurfaceVariant
        font.pixelSize: Studio.Theme.bodySmall
        wrapMode: Text.WordWrap
    }
    GridLayout {
        Layout.fillWidth: true
        columns: credentials.width >= 340 ? 2 : 1
        columnSpacing: Studio.Theme.space8
        rowSpacing: 0
        Studio.StudioButton {
            Layout.fillWidth: false
            iconName: "lock"
            text: qsTr("Đặt mật khẩu")
            objectName: credentials.mainAccount ? "mainOpenPassword" : "openPassword-" + credentials.accountName
            enabled: credentials.passwordReady
            onClicked: passwordDialog.open()
        }
        Studio.StudioButton {
            Layout.fillWidth: false
            text: qsTr("Khóa mật khẩu")
            objectName: credentials.mainAccount ? "mainLockPassword" : "lockPassword-" + credentials.accountName
            flat: true
            enabled: credentials.passwordReady && credentials.passwordState !== "!"
            onClicked: credentials.applyPassword("lock")
        }
    }
    Label {
        Layout.fillWidth: true
        visible: credentials.editor.dirty
        text: qsTr("Lưu thay đổi trước khi đặt hoặc khóa mật khẩu.")
        color: Studio.Theme.textOnSurfaceVariant
        font.pixelSize: Studio.Theme.bodySmall
        wrapMode: Text.WordWrap
    }
    Label {
        Layout.fillWidth: true
        visible: credentials.sudoMode === "password" && credentials.passwordState === "!"
        text: qsTr("Cần đặt mật khẩu để dùng sudo yêu cầu mật khẩu.")
        color: Studio.Theme.textOnSurfaceVariant
        wrapMode: Text.WordWrap
    }
    Studio.StudioDialog {
        id: passwordDialog
        objectName: credentials.mainAccount ? "mainPasswordDialog" : "passwordDialog-" + credentials.accountName
        width: Math.min(480, parent ? parent.width - Studio.Theme.space32 : 480)
        padding: Studio.Theme.space24
        focus: true
        closePolicy: Popup.CloseOnEscape
        header: Studio.StudioDialogHeader {
            title: qsTr("Đặt mật khẩu")
            subtitle: credentials.accountName
            onCloseRequested: passwordDialog.reject()
        }
        contentItem: ColumnLayout {
            spacing: Studio.Theme.space12
            Label {
                Layout.fillWidth: true
                text: qsTr("Chỉ nhập mật khẩu mới. Mật khẩu hiện tại không được hiển thị.")
                color: Studio.Theme.textOnSurfaceVariant
                wrapMode: Text.WordWrap
            }
            Studio.StudioTextField {
                id: password
                Layout.fillWidth: true
                Layout.minimumWidth: 0
                objectName: credentials.mainAccount ? "mainAccountPassword" : "extraAccountPassword-" + credentials.accountName
                placeholderText: qsTr("Mật khẩu mới")
                echoMode: TextInput.Password
                inputMethodHints: Qt.ImhSensitiveData | Qt.ImhNoPredictiveText | Qt.ImhNoAutoUppercase
                maximumLength: 128
                enabled: credentials.passwordReady
                onAccepted: if (credentials.passwordReady && credentials.passwordValid) credentials.applyPassword("replace")
            }
            Label {
                Layout.fillWidth: true
                text: qsTr("Tối đa 128 byte UTF-8, không chứa ký tự xuống dòng.")
                color: Studio.Theme.textOnSurfaceVariant
                wrapMode: Text.WordWrap
            }
            Label {
                objectName: "passwordByteLimitError"
                Layout.fillWidth: true
                visible: password.text.length > 0 && !credentials.passwordValid
                text: qsTr("Mật khẩu vượt quá 128 byte UTF-8.")
                color: Studio.Theme.error
                wrapMode: Text.WordWrap
            }
        }
        footer: Studio.StudioDialogFooter {
            contentItem: RowLayout {
                Item { Layout.fillWidth: true }
                Studio.StudioButton { text: qsTr("Hủy"); flat: true; onClicked: passwordDialog.reject() }
                Studio.StudioButton {
                    text: qsTr("Đặt mật khẩu")
                    objectName: "confirmAccountPassword"
                    highlighted: true
                    enabled: credentials.passwordReady && credentials.passwordValid
                    onClicked: credentials.applyPassword("replace")
                }
            }
        }
        onOpened: {
            if (parent && parent.Window.window) parent.Window.window.requestActivate();
            password.forceActiveFocus(Qt.TabFocusReason);
        }
        onClosed: password.clear()
    }
}
