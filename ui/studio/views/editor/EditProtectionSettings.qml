import QtQuick
import QtQuick.Controls.Basic
import QtQuick.Layouts
import "../.." as Studio

RowLayout {
    id: settings
    required property var editor
    spacing: Studio.Theme.space12
    Label {
        Layout.fillWidth: true
        wrapMode: Text.WordWrap
        text: qsTr("Khóa chỉnh sửa") + " · " + (settings.editor.draft && settings.editor.draft.edit_protected ? qsTr("Đang khóa") : qsTr("Chưa khóa"))
        color: Studio.Theme.textOnSurface
    }
    Studio.StudioButton {
        objectName: "editProtectionSettings"
        text: qsTr("Thiết lập")
        enabled: !!settings.editor.draft && !settings.editor.backend.busy
        onClicked: passwordDialog.showSettings("draft", settings.editor.draft.id, !!settings.editor.draft.edit_protected)
    }
    Studio.EditPasswordDialog {
        id: passwordDialog
        api: settings.editor.backend
        onProtectionChanged: protectedResource => {
            if (settings.editor.draft && passwordDialog.resource && settings.editor.draft.id === passwordDialog.resource.id)
                settings.editor.draft = Object.assign({}, settings.editor.draft, {edit_protected: protectedResource});
            settings.editor.refresh();
        }
    }
    Connections {
        target: settings.editor.backend
        ignoreUnknownSignals: true
        function onEditUnlockDismissed() { passwordDialog.close(); }
    }
}
