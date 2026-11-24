import QtQuick
import QtQuick.Controls
import QtQuick.Layouts
import "../../models/NodeDefaults.js" as Defaults
import "../../models/AccountModel.js" as Accounts
import "../.." as Studio

ColumnLayout {
    id: panel

    required property var editor
    required property int nodeIndex
    readonly property var node: editor.document && editor.document.nodes[nodeIndex] ? editor.document.nodes[nodeIndex] : null
    readonly property var profile: node ? Defaults.profile(editor.policy, node.image) : null
    readonly property bool editable: !!profile && !!profile.workstation && !!profile.custom_username
    readonly property var accounts: Defaults.accountOptions(editor.policy, node)
    readonly property bool setupEnabled: editable && !!profile.machine_setup && !!editor.policy.machine_setup && editor.policy.machine_setup_version === 1
    readonly property var setup: node && node.setup ? node.setup : ({})
    readonly property string contextKey: (editor.draft ? editor.draft.id : "") + ":" + (node ? node.id : "")
    onContextKeyChanged: {
        extras.checked = false;
        newAccount.clear();
        newGroup.clear();
    }

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
    Studio.AccountCredentials {
        Layout.fillWidth: true
        visible: panel.setupEnabled
        editor: panel.editor
        nodeIndex: panel.nodeIndex
        accountName: panel.node && panel.node.user ? panel.node.user.name : ""
        contextKey: panel.contextKey + ":" + (panel.editor.draft ? panel.editor.draft.revision : "")
        mainAccount: true
        sudoMode: panel.setup.sudo || "passwordless"
        passwordState: panel.setup.password_hash || ""
    }
    Studio.StudioCheckBox {
        id: extras
        objectName: "extraAccountsToggle"
        Layout.fillWidth: true
        visible: panel.setupEnabled
        text: qsTr("Tài khoản và nhóm bổ sung")
    }
    ColumnLayout {
        Layout.fillWidth: true
        visible: panel.setupEnabled && extras.checked
        spacing: Studio.Theme.space12
        Label {
            Layout.fillWidth: true
            text: qsTr("Tối đa 32 tài khoản và 32 nhóm. Nhóm riêng được tạo tự động; UID/GID ổn định từ 3000 đến 59999.")
            color: Studio.Theme.textOnSurfaceVariant
            wrapMode: Text.WordWrap
        }
        Studio.StudioTextField {
            id: newAccount
            objectName: "newAccountName"
            Layout.fillWidth: true
            maximumLength: 32
            placeholderText: qsTr("Tên tài khoản mới")
        }
        Studio.StudioButton {
            objectName: "addAccount"
            text: qsTr("Thêm tài khoản")
            enabled: newAccount.text.length > 0 && (panel.setup.users || []).length < 32 && !panel.editor.accountPasswordPending
            onClicked: {
                panel.editor.accountChange(panel.nodeIndex, "addUser", newAccount.text);
                if (!panel.editor.localError) newAccount.clear();
            }
        }
        Studio.StudioTextField {
            id: newGroup
            objectName: "newAccountGroup"
            Layout.fillWidth: true
            maximumLength: 32
            placeholderText: qsTr("Tên nhóm mới")
        }
        Studio.StudioButton {
            objectName: "addAccountGroup"
            text: qsTr("Thêm nhóm")
            enabled: newGroup.text.length > 0 && (panel.setup.groups || []).length < 32 && !panel.editor.accountPasswordPending
            onClicked: {
                panel.editor.accountChange(panel.nodeIndex, "addGroup", newGroup.text);
                if (!panel.editor.localError) newGroup.clear();
            }
        }
        Repeater {
            model: panel.setup.users || []
            delegate: ColumnLayout {
                id: accountRow
                required property var modelData
                Layout.fillWidth: true
                spacing: Studio.Theme.space8
                Studio.AccountNameField {
                    Layout.fillWidth: true
                    editor: panel.editor
                    nodeIndex: panel.nodeIndex
                    accountName: accountRow.modelData.name
                    contextKey: panel.contextKey
                }
                Label {
                    Layout.fillWidth: true
                    text: "UID " + accountRow.modelData.uid + " / GID " + accountRow.modelData.gid
                    font.bold: true
                    color: Studio.Theme.textOnSurface
                    wrapMode: Text.WordWrap
                }
                Studio.AccountCredentials {
                    Layout.fillWidth: true
                    editor: panel.editor
                    nodeIndex: panel.nodeIndex
                    accountName: accountRow.modelData.name
                    contextKey: panel.contextKey + ":" + (panel.editor.draft ? panel.editor.draft.revision : "")
                    sudoMode: accountRow.modelData.sudo || "disabled"
                    passwordState: accountRow.modelData.password_hash || "!"
                }
                Label { text: qsTr("Nhóm bổ sung"); color: Studio.Theme.textOnSurface }
                Repeater {
                    model: panel.node ? Accounts.groupNames(panel.node).filter(name => name !== accountRow.modelData.name) : []
                    delegate: Studio.StudioCheckBox {
                        required property string modelData
                        objectName: "accountMembership-" + accountRow.modelData.name + "-" + modelData
                        Layout.fillWidth: true
                        text: modelData
                        checked: (accountRow.modelData.groups || []).includes(modelData)
                        onToggled: {
                            const groups = accountRow.modelData.groups || [];
                            panel.editor.accountChange(panel.nodeIndex, "groups", accountRow.modelData.name,
                                checked ? groups.concat([modelData]) : groups.filter(name => name !== modelData));
                        }
                    }
                }
                Studio.StudioButton {
                    objectName: "removeAccount-" + accountRow.modelData.name
                    text: qsTr("Xóa tài khoản")
                    danger: true
                    outlined: true
                    onClicked: panel.editor.accountChange(panel.nodeIndex, "removeUser", accountRow.modelData.name)
                }
            }
        }
        Label { text: qsTr("Nhóm bổ sung"); font.bold: true; color: Studio.Theme.textOnSurface }
        Repeater {
            model: panel.setup.groups || []
            delegate: RowLayout {
                id: groupRow
                required property var modelData
                Layout.fillWidth: true
                Studio.AccountNameField {
                    Layout.fillWidth: true
                    Layout.minimumWidth: 0
                    editor: panel.editor
                    nodeIndex: panel.nodeIndex
                    accountName: groupRow.modelData.name
                    contextKey: panel.contextKey
                    groupName: true
                }
                Label {
                    text: "GID " + groupRow.modelData.gid
                    color: Studio.Theme.textOnSurface
                    wrapMode: Text.WordWrap
                }
                Studio.StudioButton {
                    objectName: "removeAccountGroup-" + groupRow.modelData.name
                    text: qsTr("Xóa nhóm")
                    danger: true
                    outlined: true
                    onClicked: panel.editor.accountChange(panel.nodeIndex, "removeGroup", groupRow.modelData.name)
                }
            }
        }
    }
}
