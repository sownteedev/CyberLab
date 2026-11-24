import QtQuick
import QtQuick.Controls.Basic
import QtQuick.Layouts
import "../.." as Studio

Studio.StudioDialog {
    id: dialog
    required property var api
    property var resource: null
    property bool settings: false
    property bool protectedResource: false
    property bool removing: false
    property bool pending: false
    property bool succeeded: false
    property string problem: ""
    property int generation: 0
    signal protectionChanged(bool protectedResource)

    function showUnlock(kind, identifier, message) {
        settings = false;
        resource = {kind: kind, id: identifier};
        problem = "";
        open();
    }
    function showSettings(kind, identifier, protectedValue) {
        settings = true;
        protectedResource = protectedValue;
        removing = false;
        resource = {kind: kind, id: identifier};
        problem = "";
        open();
    }
    function submit() {
        if (pending || !resource) return;
        if ((!settings || protectedResource) && !currentPassword.text.length) return;
        if (settings && !removing && (!newPassword.text.length || newPassword.text !== confirmation.text)) {
            problem = qsTr("Nhập mật khẩu mới và xác nhận giống nhau.");
            confirmation.forceActiveFocus();
            return;
        }
        pending = true;
        problem = "";
        const attempt = generation;
        const current = currentPassword.text;
        const replacement = removing ? "" : newPassword.text;
        currentPassword.text = "";
        newPassword.text = "";
        confirmation.text = "";
        const completed = (result, error) => {
            if (attempt !== generation) return;
            pending = false;
            if (error) {
                problem = error;
                Qt.callLater(() => (currentPassword.visible ? currentPassword : newPassword).forceActiveFocus());
                return;
            }
            succeeded = true;
            if (settings) protectionChanged(!!result.edit_protected);
            accept();
        };
        if (settings) api.setEditPassword(resource, current, replacement, completed);
        else api.unlockEditing(current, completed);
    }

    objectName: "editPasswordDialog"
    title: settings ? qsTr("Bảo vệ bài") : qsTr("Mở khóa chỉnh sửa")
    width: Math.min(520, parent ? parent.width - Studio.Theme.space32 : 520)
    height: Math.min(implicitHeight, parent ? parent.height - Studio.Theme.space32 : implicitHeight)
    padding: 0
    spacing: 0
    font.family: Studio.Theme.fontFamily
    focus: true
    closePolicy: pending ? Popup.NoAutoClose : Popup.CloseOnEscape
    onOpened: {
        succeeded = false;
        Qt.callLater(() => (currentPassword.visible ? currentPassword : newPassword).forceActiveFocus());
    }
    onClosed: {
        generation++;
        pending = false;
        currentPassword.text = "";
        newPassword.text = "";
        confirmation.text = "";
        if (!settings && !succeeded) api.cancelEditUnlock();
        resource = null;
    }
    header: Studio.StudioDialogHeader {
        title: dialog.title
        subtitle: dialog.settings ? qsTr("Mật khẩu chỉ dùng khi sửa bài.") : qsTr("Nhập mật khẩu để tiếp tục sửa bài.")
        iconName: "lock"
        closeButton.enabled: !dialog.pending
        onCloseRequested: if (!dialog.pending) dialog.reject()
    }
    contentItem: Flickable {
        id: formViewport
        implicitWidth: dialog.width
        implicitHeight: contentHeight
        contentWidth: width
        contentHeight: contentColumn.implicitHeight + Studio.Theme.space16
        clip: true
        boundsBehavior: Flickable.StopAtBounds
        flickableDirection: Flickable.VerticalFlick
        interactive: contentHeight > height
        ScrollBar.vertical: ScrollBar { policy: ScrollBar.AsNeeded }

        ColumnLayout {
            id: contentColumn
            x: Studio.Theme.space24
            y: Studio.Theme.space8
            width: Math.max(0, dialog.width - Studio.Theme.space24 * 2)
            spacing: Studio.Theme.space16

        ColumnLayout {
            Layout.fillWidth: true
            visible: !dialog.settings || dialog.protectedResource
            spacing: Studio.Theme.space8

            Label {
                Layout.fillWidth: true
                color: Studio.Theme.textOnSurfaceVariant
                font.pixelSize: Studio.Theme.labelLarge
                font.weight: Font.DemiBold
                text: dialog.settings ? qsTr("Mật khẩu hiện tại") : qsTr("Mật khẩu")
            }
            Studio.StudioTextField {
                id: currentPassword
                objectName: "editCurrentPassword"
                Layout.fillWidth: true
                enabled: !dialog.pending
                echoMode: TextInput.Password
                inputMethodHints: Qt.ImhHiddenText | Qt.ImhNoPredictiveText | Qt.ImhSensitiveData
                placeholderText: qsTr("Nhập mật khẩu")
                Accessible.name: placeholderText
                onAccepted: dialog.submit()
            }
        }

        Studio.StudioCheckBox {
            objectName: "editRemoveProtection"
            Layout.fillWidth: true
            visible: dialog.settings && dialog.protectedResource
            enabled: !dialog.pending
            text: qsTr("Gỡ khóa chỉnh sửa")
            checked: dialog.removing
            onToggled: dialog.removing = checked
        }

        ColumnLayout {
            Layout.fillWidth: true
            visible: dialog.settings && !dialog.removing
            spacing: Studio.Theme.space12

            ColumnLayout {
                Layout.fillWidth: true
                spacing: Studio.Theme.space8
                Label {
                    Layout.fillWidth: true
                    color: Studio.Theme.textOnSurfaceVariant
                    font.pixelSize: Studio.Theme.labelLarge
                    font.weight: Font.DemiBold
                    text: qsTr("Mật khẩu mới")
                }
                Studio.StudioTextField {
                    id: newPassword
                    objectName: "editNewPassword"
                    Layout.fillWidth: true
                    enabled: !dialog.pending
                    echoMode: TextInput.Password
                    inputMethodHints: Qt.ImhHiddenText | Qt.ImhNoPredictiveText | Qt.ImhSensitiveData
                    placeholderText: qsTr("Nhập mật khẩu mới")
                    Accessible.name: placeholderText
                    onAccepted: confirmation.forceActiveFocus()
                }
            }
            ColumnLayout {
                Layout.fillWidth: true
                spacing: Studio.Theme.space8
                Label {
                    Layout.fillWidth: true
                    color: Studio.Theme.textOnSurfaceVariant
                    font.pixelSize: Studio.Theme.labelLarge
                    font.weight: Font.DemiBold
                    text: qsTr("Xác nhận mật khẩu")
                }
                Studio.StudioTextField {
                    id: confirmation
                    objectName: "editConfirmPassword"
                    Layout.fillWidth: true
                    enabled: !dialog.pending
                    echoMode: TextInput.Password
                    inputMethodHints: Qt.ImhHiddenText | Qt.ImhNoPredictiveText | Qt.ImhSensitiveData
                    placeholderText: qsTr("Nhập lại mật khẩu mới")
                    Accessible.name: placeholderText
                    onAccepted: dialog.submit()
                }
            }
        }

        Label {
            Layout.fillWidth: true
            visible: dialog.settings
            wrapMode: Text.WordWrap
            color: Studio.Theme.textOnSurfaceVariant
            font.pixelSize: Studio.Theme.bodySmall
            text: dialog.removing ? qsTr("Sau khi gỡ, mọi người đều có thể sửa bài.") : qsTr("Áp dụng ngay. Không thể khôi phục mật khẩu đã quên.")
        }

        Rectangle {
            Layout.fillWidth: true
            implicitHeight: errorMessage.implicitHeight + Studio.Theme.space16
            visible: !!dialog.problem
            color: Qt.alpha(Studio.Theme.error, 0.08)
            radius: Studio.Theme.shapeSmall

            RowLayout {
                id: errorMessage
                anchors.fill: parent
                anchors.margins: Studio.Theme.space8
                spacing: Studio.Theme.space8

                Studio.Icon {
                    Layout.alignment: Qt.AlignTop
                    name: "error"
                    size: Studio.Theme.iconSmall
                    color: Studio.Theme.error
                }
                Label {
                    Layout.fillWidth: true
                    color: Studio.Theme.error
                    text: dialog.problem
                    textFormat: Text.PlainText
                    wrapMode: Text.WordWrap
                    Accessible.role: Accessible.AlertMessage
                }
            }
        }
        }
    }
    footer: Control {
        objectName: "studioDialogFooter"
        implicitHeight: implicitContentHeight + topPadding + bottomPadding
        padding: Studio.Theme.space24
        topPadding: Studio.Theme.space16
        contentItem: RowLayout {
        spacing: Studio.Theme.space8
        Item { Layout.fillWidth: true }
        Studio.StudioButton {
            text: qsTr("Hủy")
            flat: true
            enabled: !dialog.pending
            onClicked: dialog.reject()
        }
        Studio.StudioButton {
            objectName: "editPasswordSubmit"
            text: dialog.settings ? (dialog.removing ? qsTr("Gỡ khóa") : qsTr("Lưu mật khẩu")) : qsTr("Mở khóa")
            busy: dialog.pending
            highlighted: true
            enabled: !dialog.pending
            onClicked: dialog.submit()
        }
        }
    }
}
