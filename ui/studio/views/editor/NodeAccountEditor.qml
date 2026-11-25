import QtQuick
import QtQuick.Controls
import QtQuick.Layouts
import "../../models/NodeDefaults.js" as Defaults
import "../.." as Studio

ColumnLayout {
    id: panel

    required property var editor
    required property int nodeIndex
    property Item managementHost: null
    readonly property var node: editor.document && editor.document.nodes[nodeIndex] ? editor.document.nodes[nodeIndex] : null
    readonly property var profile: node ? Defaults.profile(editor.policy, node.image) : null
    readonly property bool editable: !!profile && !!profile.workstation && !!profile.custom_username
    readonly property var accounts: Defaults.accountOptions(editor.policy, node)
    readonly property bool setupEnabled: editable && !!profile.machine_setup && !!editor.policy.machine_setup && editor.policy.machine_setup_version === 1
    readonly property var setup: node && node.setup ? node.setup : ({})
    readonly property string contextKey: (editor.draft ? editor.draft.id : "") + ":" + (node ? node.id : "")

    spacing: Studio.Theme.space8

    Label { text: panel.editable ? qsTr("Tên đăng nhập") : qsTr("Tài khoản") }
    Studio.StudioTextField {
        id: username

        property string editingNode: ""
        property string editingDraft: ""
        readonly property bool valid: Defaults.validUsername(text, panel.profile ? panel.profile.reserved_usernames : undefined)

        Accessible.name: qsTr("Username của máy Ubuntu")
        Layout.fillWidth: true
        objectName: "basicNodeUsername"
        visible: panel.editable
        text: panel.node && panel.node.user ? panel.node.user.name : "student"
        placeholderText: "student"
        error: visible && !valid

        onActiveFocusChanged: if (activeFocus) {
            editingNode = panel.node ? panel.node.id : "";
            editingDraft = panel.editor.draft ? panel.editor.draft.id : "";
        }
        onEditingFinished: {
            if (!panel.editable || !valid || !panel.node || panel.node.id !== editingNode
                    || !panel.editor.draft || panel.editor.draft.id !== editingDraft)
                return;
            const account = Defaults.defaultAccount(panel.profile, text);
            if (account && !Defaults.sameAccount(account, panel.node.user)) {
                if (panel.node.setup) panel.editor.accountChange(panel.nodeIndex, "renameMain", account.name);
                else panel.editor.change("nodes", panel.nodeIndex, "user", account);
                text = Qt.binding(() => panel.node && panel.node.user ? panel.node.user.name : "student");
            }
        }
    }
    Studio.StudioComboBox {
        Accessible.name: qsTr("Tài khoản có sẵn trong môi trường")
        Layout.fillWidth: true
        visible: !panel.editable
        currentIndex: panel.accounts.findIndex(option => panel.node && (panel.node.user ? Defaults.sameAccount(option.user, panel.node.user) : !option.user))
        model: panel.accounts
        objectName: "basicNodeAccount"
        textRole: "label"

        onActivated: panel.editor.change("nodes", panel.nodeIndex, "user", panel.accounts[currentIndex].user)
    }
    Label {
        Layout.fillWidth: true
        visible: panel.editable && !username.valid
        color: Studio.Theme.error
        font.pixelSize: Studio.Theme.bodySmall
        objectName: "basicNodeUsernameHint"
        text: qsTr("Dùng 1–32 ký tự a–z, số, _ hoặc -, bắt đầu bằng chữ thường; không dùng tên hệ thống như root.")
        wrapMode: Text.WordWrap
    }
    Label {
        visible: panel.setupEnabled
        text: qsTr("Quyền sudo")
        color: Studio.Theme.textOnSurface
    }
    Studio.StudioComboBox {
        Layout.fillWidth: true
        visible: panel.setupEnabled
        objectName: "mainAccountSudo"
        Accessible.name: qsTr("Quyền sudo của tài khoản chính")
        model: [qsTr("Không cho phép"), qsTr("Yêu cầu mật khẩu"), qsTr("Không cần mật khẩu")]
        currentIndex: ["disabled", "password", "passwordless"].indexOf(panel.setup.sudo || "passwordless")
        onActivated: panel.editor.accountChange(panel.nodeIndex, "sudo", panel.node.user.name, ["disabled", "password", "passwordless"][currentIndex])
    }
    Rectangle {
        parent: panel.managementHost || panel
        Layout.fillWidth: true
        implicitHeight: accountSummary.implicitHeight + Studio.Theme.space24
        visible: panel.setupEnabled
        radius: Studio.Theme.shapeMedium
        color: Studio.Theme.surfaceContainer
        RowLayout {
            id: accountSummary
            anchors.fill: parent
            anchors.margins: Studio.Theme.space12
            spacing: Studio.Theme.space12
            ColumnLayout {
                Layout.fillWidth: true
                Layout.minimumWidth: 0
                spacing: Studio.Theme.space4
                Label {
                    Layout.fillWidth: true
                    text: qsTr("Tài khoản và nhóm")
                    font.weight: Font.DemiBold
                    color: Studio.Theme.textOnSurface
                    wrapMode: Text.WordWrap
                }
                Label {
                    Layout.fillWidth: true
                    text: qsTr("%1 tài khoản phụ · %2 nhóm").arg((panel.setup.users || []).length).arg((panel.setup.groups || []).length)
                    color: Studio.Theme.textOnSurfaceVariant
                    font.pixelSize: Studio.Theme.bodySmall
                    wrapMode: Text.WordWrap
                }
            }
            Studio.StudioButton {
                objectName: "extraAccountsToggle"
                text: qsTr("Quản lý")
                iconName: "group"
                outlined: true
                Accessible.name: qsTr("Quản lý tài khoản và nhóm bổ sung")
                onClicked: accountManager.open()
            }
        }
    }
    Studio.AccountManagerDialog {
        id: accountManager
        editor: panel.editor
        nodeIndex: panel.nodeIndex
        contextKey: panel.contextKey
    }
}
