import QtQuick
import "../.." as Studio

Studio.StudioTextField {
    id: field
    required property var editor
    required property int nodeIndex
    required property string accountName
    required property string contextKey
    property bool groupName: false
    property string editingContext: ""
    property string editingName: ""
    objectName: (groupName ? "accountGroupName-" : "accountName-") + accountName
    text: accountName
    maximumLength: 32
    Accessible.name: groupName ? qsTr("Tên nhóm") : qsTr("Tên tài khoản")
    onActiveFocusChanged: if (activeFocus) {
        editingContext = contextKey;
        editingName = accountName;
    }
    onEditingFinished: {
        if (contextKey !== editingContext || editingName !== accountName || text === accountName) return;
        editor.accountChange(nodeIndex, groupName ? "renameGroup" : "renameUser", accountName, text);
        text = Qt.binding(() => field.accountName);
    }
}
