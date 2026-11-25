import QtQuick
import QtQuick.Controls.Basic
import QtQuick.Layouts
import "../../models/AccountModel.js" as Accounts
import "../.." as Studio

Studio.StudioDialog {
    id: manager

    required property var editor
    required property int nodeIndex
    required property string contextKey
    readonly property var node: editor.document && editor.document.nodes[nodeIndex] ? editor.document.nodes[nodeIndex] : null
    readonly property var setup: node && node.setup ? node.setup : ({})
    readonly property bool editable: !editor.backend.busy && !editor.accountPasswordPending
    property int section: 0
    property int expandedAccount: -1
    property var pendingRemoval: null

    objectName: "accountManagerDialog"
    width: Math.min(720, parent ? parent.width - Studio.Theme.space32 : 720)
    height: Math.min(740, parent ? parent.height - Studio.Theme.space32 : 740)
    padding: width < 440 ? Studio.Theme.space16 : Studio.Theme.space24
    focus: true
    closePolicy: Popup.CloseOnEscape

    onContextKeyChanged: close()
    onOpened: {
        if (parent && parent.Window.window) parent.Window.window.requestActivate();
        section = 0;
        expandedAccount = -1;
        newAccount.forceActiveFocus(Qt.TabFocusReason);
    }
    onClosed: {
        newAccount.clear();
        newGroup.clear();
        removal.close();
        pendingRemoval = null;
    }

    function addAccount() {
        if (!addUser.enabled) return;
        editor.accountChange(nodeIndex, "addUser", newAccount.text.trim());
        if (!editor.localError) {
            newAccount.clear();
            expandedAccount = (setup.users || []).length - 1;
            Qt.callLater(() => list.contentItem.contentY = Math.max(0, list.contentItem.contentHeight - list.availableHeight));
        }
    }

    function addGroup() {
        if (!addTeam.enabled) return;
        editor.accountChange(nodeIndex, "addGroup", newGroup.text.trim());
        if (!editor.localError) newGroup.clear();
    }

    function requestRemoval(name, group) {
        pendingRemoval = {name: name, group: group, context: contextKey};
        removal.open();
    }

    header: Studio.StudioDialogHeader {
        title: qsTr("Tài khoản và nhóm")
        subtitle: manager.node ? qsTr("Máy %1").arg(manager.node.id) : ""
        onCloseRequested: manager.close()
    }
    contentItem: ColumnLayout {
        spacing: Studio.Theme.space16
        Studio.StudioSegmentedTabs {
            Layout.fillWidth: true
            Layout.minimumWidth: 0
            Accessible.name: qsTr("Quản lý tài khoản và nhóm")
            itemPrefix: "accountsTab-"
            entries: [
                {label: qsTr("Tài khoản (%1)").arg(1 + (manager.setup.users || []).length), icon: "person"},
                {label: qsTr("Nhóm (%1)").arg((manager.setup.groups || []).length), icon: "group"}
            ]
            currentIndex: manager.section
            onSelected: index => {
                manager.section = index;
                list.contentItem.contentY = 0;
            }
        }
        RowLayout {
            Layout.fillWidth: true
            visible: manager.section === 0
            spacing: Studio.Theme.space8
            Studio.StudioTextField {
                id: newAccount
                objectName: "newAccountName"
                Layout.fillWidth: true
                Layout.minimumWidth: 0
                enabled: manager.editable
                maximumLength: 32
                placeholderText: qsTr("Tên tài khoản mới")
                Accessible.name: placeholderText
                onAccepted: manager.addAccount()
            }
            Studio.StudioButton {
                id: addUser
                objectName: "addAccount"
                text: qsTr("Thêm")
                iconName: "add"
                highlighted: true
                Accessible.name: qsTr("Thêm tài khoản")
                enabled: manager.editable && newAccount.text.trim().length > 0 && (manager.setup.users || []).length < 32
                onClicked: manager.addAccount()
            }
        }
        RowLayout {
            Layout.fillWidth: true
            visible: manager.section === 1
            spacing: Studio.Theme.space8
            Studio.StudioTextField {
                id: newGroup
                objectName: "newAccountGroup"
                Layout.fillWidth: true
                Layout.minimumWidth: 0
                enabled: manager.editable
                maximumLength: 32
                placeholderText: qsTr("Tên nhóm mới")
                Accessible.name: placeholderText
                onAccepted: manager.addGroup()
            }
            Studio.StudioButton {
                id: addTeam
                objectName: "addAccountGroup"
                text: qsTr("Thêm")
                iconName: "add"
                highlighted: true
                Accessible.name: qsTr("Thêm nhóm")
                enabled: manager.editable && newGroup.text.trim().length > 0 && (manager.setup.groups || []).length < 32
                onClicked: manager.addGroup()
            }
        }
        Label {
            Layout.fillWidth: true
            visible: (manager.section === 0 ? (manager.setup.users || []).length : (manager.setup.groups || []).length) >= 32
            text: manager.section === 0 ? qsTr("Đã đủ 32 tài khoản phụ.") : qsTr("Đã đủ 32 nhóm.")
            color: Studio.Theme.textOnSurfaceVariant
            wrapMode: Text.WordWrap
        }
        ScrollView {
            id: list
            objectName: "accountsScroll"
            Layout.fillWidth: true
            Layout.fillHeight: true
            clip: true
            contentWidth: availableWidth
            ColumnLayout {
                width: list.availableWidth
                spacing: Studio.Theme.space12
                Rectangle {
                    Layout.fillWidth: true
                    implicitHeight: mainAccountContent.implicitHeight + Studio.Theme.space24
                    visible: manager.visible && manager.section === 0
                    radius: Studio.Theme.shapeLarge
                    color: Studio.Theme.surfaceContainerLow
                    border.width: Studio.Theme.borderWidth
                    border.color: Studio.Theme.outlineVariant
                    ColumnLayout {
                        id: mainAccountContent
                        width: parent.width - Studio.Theme.space24
                        anchors.centerIn: parent
                        spacing: Studio.Theme.space12
                        RowLayout {
                            Layout.fillWidth: true
                            spacing: Studio.Theme.space12
                            Studio.Icon { name: "person"; color: Studio.Theme.primary }
                            ColumnLayout {
                                Layout.fillWidth: true
                                Layout.minimumWidth: 0
                                spacing: Studio.Theme.space4
                                Label {
                                    objectName: "mainAccountName"
                                    Layout.fillWidth: true
                                    text: manager.node && manager.node.user ? manager.node.user.name : ""
                                    elide: Text.ElideRight
                                    font.weight: Font.DemiBold
                                    color: Studio.Theme.textOnSurface
                                }
                                Label {
                                    text: qsTr("Tài khoản chính")
                                    font.pixelSize: Studio.Theme.bodySmall
                                    color: Studio.Theme.textOnSurfaceVariant
                                }
                            }
                        }
                        Studio.AccountCredentials {
                            Layout.fillWidth: true
                            editor: manager.editor
                            nodeIndex: manager.nodeIndex
                            accountName: manager.node && manager.node.user ? manager.node.user.name : ""
                            contextKey: manager.contextKey + ":" + (manager.editor.draft ? manager.editor.draft.revision : "")
                            mainAccount: true
                            showSudo: false
                            sudoMode: manager.setup.sudo || "passwordless"
                            passwordState: manager.setup.password_hash || ""
                        }
                    }
                }
                Rectangle {
                    Layout.fillWidth: true
                    implicitHeight: emptyContent.implicitHeight + Studio.Theme.space32 * 2
                    visible: !(manager.section === 0 ? (manager.setup.users || []).length : (manager.setup.groups || []).length)
                    color: Studio.Theme.surfaceContainerLow
                    radius: Studio.Theme.shapeLarge
                    ColumnLayout {
                        id: emptyContent
                        anchors.centerIn: parent
                        width: parent.width - Studio.Theme.space32
                        spacing: Studio.Theme.space12
                        Studio.Icon {
                            Layout.alignment: Qt.AlignHCenter
                            name: manager.section === 0 ? "person" : "group"
                            color: Studio.Theme.primary
                            size: Studio.Theme.space32
                        }
                        Label {
                            Layout.fillWidth: true
                            text: manager.section === 0 ? qsTr("Chưa có tài khoản phụ") : qsTr("Chưa có nhóm bổ sung")
                            horizontalAlignment: Text.AlignHCenter
                            wrapMode: Text.WordWrap
                            color: Studio.Theme.textOnSurfaceVariant
                        }
                    }
                }
                Repeater {
                    model: manager.section === 0 ? manager.setup.users || [] : []
                    delegate: Rectangle {
                        id: accountRow
                        required property var modelData
                        required property int index
                        readonly property bool expanded: manager.expandedAccount === index
                        Layout.fillWidth: true
                        implicitHeight: accountContent.implicitHeight + Studio.Theme.space24
                        radius: Studio.Theme.shapeLarge
                        color: Studio.Theme.surfaceContainerLow
                        border.width: Studio.Theme.borderWidth
                        border.color: Studio.Theme.outlineVariant
                        ColumnLayout {
                            id: accountContent
                            width: parent.width - Studio.Theme.space24
                            anchors.centerIn: parent
                            spacing: Studio.Theme.space12
                            RowLayout {
                                Layout.fillWidth: true
                                Studio.StudioButton {
                                    Layout.fillWidth: true
                                    Layout.minimumWidth: 0
                                    objectName: "expandAccount-" + accountRow.modelData.name
                                    text: accountRow.modelData.name
                                    iconName: "person"
                                    leading: true
                                    flat: true
                                    Accessible.description: accountRow.expanded ? qsTr("Thu gọn tài khoản") : qsTr("Mở cài đặt tài khoản")
                                    contentItem: RowLayout {
                                        spacing: Studio.Theme.space12
                                        Studio.Icon { name: "person"; color: Studio.Theme.primary }
                                        Label {
                                            Layout.fillWidth: true
                                            Layout.minimumWidth: 0
                                            text: accountRow.modelData.name
                                            elide: Text.ElideRight
                                            color: Studio.Theme.textOnSurface
                                            font.weight: Font.DemiBold
                                        }
                                        Studio.Icon {
                                            name: "chevron_right"
                                            size: Studio.Theme.iconSmall
                                            rotation: accountRow.expanded ? 90 : 0
                                            color: Studio.Theme.textOnSurfaceVariant
                                            Behavior on rotation { NumberAnimation { duration: Studio.Theme.stateDuration } }
                                        }
                                    }
                                    onClicked: manager.expandedAccount = accountRow.expanded ? -1 : accountRow.index
                                }
                                Studio.StudioIconButton {
                                    objectName: "removeAccount-" + accountRow.modelData.name
                                    iconName: "delete"
                                    description: qsTr("Xóa tài khoản %1").arg(accountRow.modelData.name)
                                    danger: true
                                    enabled: manager.editable
                                    onClicked: manager.requestRemoval(accountRow.modelData.name, false)
                                }
                            }
                            ColumnLayout {
                                visible: accountRow.expanded
                                Layout.fillWidth: true
                                spacing: Studio.Theme.space12
                                RowLayout {
                                    Layout.fillWidth: true
                                    Label { text: qsTr("Tên tài khoản"); color: Studio.Theme.textOnSurfaceVariant }
                                    Item { Layout.fillWidth: true }
                                    Label {
                                        text: "UID " + accountRow.modelData.uid + " · GID " + accountRow.modelData.gid
                                        color: Studio.Theme.textOnSurfaceVariant
                                        font.pixelSize: Studio.Theme.bodySmall
                                    }
                                }
                                Studio.AccountNameField {
                                    Layout.fillWidth: true
                                    enabled: manager.editable
                                    editor: manager.editor
                                    nodeIndex: manager.nodeIndex
                                    accountName: accountRow.modelData.name
                                    contextKey: manager.contextKey
                                }
                                Studio.AccountCredentials {
                                    Layout.fillWidth: true
                                    editor: manager.editor
                                    nodeIndex: manager.nodeIndex
                                    accountName: accountRow.modelData.name
                                    contextKey: manager.contextKey + ":" + (manager.editor.draft ? manager.editor.draft.revision : "")
                                    sudoMode: accountRow.modelData.sudo || "disabled"
                                    passwordState: accountRow.modelData.password_hash || "!"
                                }
                                Label {
                                    visible: membership.count > 0
                                    text: qsTr("Thuộc nhóm")
                                    color: Studio.Theme.textOnSurfaceVariant
                                }
                                GridLayout {
                                    Layout.fillWidth: true
                                    columns: width >= 480 ? 2 : 1
                                    columnSpacing: Studio.Theme.space12
                                    rowSpacing: 0
                                    Repeater {
                                        id: membership
                                        model: manager.node ? Accounts.groupNames(manager.node).filter(name => name !== accountRow.modelData.name) : []
                                        delegate: Studio.StudioCheckBox {
                                            required property string modelData
                                            objectName: "accountMembership-" + accountRow.modelData.name + "-" + modelData
                                            Layout.fillWidth: true
                                            Layout.minimumWidth: 0
                                            enabled: manager.editable
                                            text: modelData
                                            checked: (accountRow.modelData.groups || []).includes(modelData)
                                            onToggled: {
                                                const groups = accountRow.modelData.groups || [];
                                                manager.editor.accountChange(manager.nodeIndex, "groups", accountRow.modelData.name,
                                                    checked ? groups.concat([modelData]) : groups.filter(name => name !== modelData));
                                            }
                                        }
                                    }
                                }
                            }
                        }
                    }
                }
                Repeater {
                    model: manager.section === 1 ? manager.setup.groups || [] : []
                    delegate: Rectangle {
                        id: groupRow
                        required property var modelData
                        Layout.fillWidth: true
                        implicitHeight: groupContent.implicitHeight + Studio.Theme.space24
                        color: Studio.Theme.surfaceContainerLow
                        radius: Studio.Theme.shapeLarge
                        RowLayout {
                            id: groupContent
                            width: parent.width - Studio.Theme.space24
                            anchors.centerIn: parent
                            spacing: Studio.Theme.space8
                            ColumnLayout {
                                Layout.fillWidth: true
                                Layout.minimumWidth: 0
                                spacing: Studio.Theme.space4
                                Label {
                                    text: "GID " + groupRow.modelData.gid
                                    font.pixelSize: Studio.Theme.bodySmall
                                    color: Studio.Theme.textOnSurfaceVariant
                                }
                                Studio.AccountNameField {
                                    Layout.fillWidth: true
                                    Layout.minimumWidth: 0
                                    enabled: manager.editable
                                    editor: manager.editor
                                    nodeIndex: manager.nodeIndex
                                    accountName: groupRow.modelData.name
                                    contextKey: manager.contextKey
                                    groupName: true
                                }
                            }
                            Studio.StudioIconButton {
                                objectName: "removeAccountGroup-" + groupRow.modelData.name
                                iconName: "delete"
                                description: qsTr("Xóa nhóm %1").arg(groupRow.modelData.name)
                                danger: true
                                enabled: manager.editable
                                onClicked: manager.requestRemoval(groupRow.modelData.name, true)
                            }
                        }
                    }
                }
            }
        }
    }
    footer: Studio.StudioDialogFooter {
        contentItem: RowLayout {
            Item { Layout.fillWidth: true }
            Studio.StudioButton {
                text: qsTr("Đóng")
                onClicked: manager.close()
            }
        }
    }
    Studio.ConfirmDialog {
        id: removal
        objectName: "removeAccountDialog"
        danger: true
        title: manager.pendingRemoval && manager.pendingRemoval.group ? qsTr("Xóa nhóm?") : qsTr("Xóa tài khoản?")
        message: manager.pendingRemoval ? qsTr("Xóa “%1” khỏi cấu hình máy này?").arg(manager.pendingRemoval.name) : ""
        confirmText: qsTr("Xóa")
        confirmEnabled: manager.editable
        onAccepted: {
            const pending = manager.pendingRemoval;
            if (!pending || pending.context !== manager.contextKey) return;
            manager.editor.accountChange(manager.nodeIndex, pending.group ? "removeGroup" : "removeUser", pending.name);
            if (!manager.editor.localError && !pending.group) manager.expandedAccount = -1;
        }
    }
}
