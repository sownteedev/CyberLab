pragma ComponentBehavior: Bound

import QtQuick
import QtQuick.Controls.Basic
import QtQuick.Layouts
import "../.." as Studio

Studio.StudioDialog {
    id: dialog

    required property var editor
    readonly property var choices: editor.editChoice ? editor.editChoice.drafts : []

    objectName: "editingDraftDialog"
    title: qsTr("Tiếp tục bản nháp")
    width: Math.min(600, parent ? parent.width - Studio.Theme.space32 : 600)
    height: Math.min(header.implicitHeight + footer.implicitHeight + padding * 2 + choicesList.contentHeight,
                     540, parent ? parent.height - Studio.Theme.space32 : 540)
    padding: Studio.Theme.space24
    focus: true
    closePolicy: dialog.editor.backend.busy ? Popup.NoAutoClose : Popup.CloseOnEscape
    onClosed: editor.cancelEditChoice()
    onOpened: Qt.callLater(() => {
        const first = choicesList.itemAtIndex(0);
        if (first) first.forceActiveFocus(Qt.TabFocusReason);
    })

    Connections {
        target: dialog.editor
        function onEditChoiceChanged() {
            if (!dialog.editor.editChoice && dialog.opened) dialog.close();
        }
    }
    header: Studio.StudioDialogHeader {
        title: dialog.title
        subtitle: qsTr("Bài này có nhiều bản nháp. Chọn bản muốn tiếp tục; không bản nào bị xóa hay ghi đè.")
        iconName: "edit"
        onCloseRequested: if (!dialog.editor.backend.busy) dialog.reject()
    }
    contentItem: ListView {
        id: choicesList

        clip: true
        spacing: Studio.Theme.space8
        model: dialog.choices
        ScrollBar.vertical: ScrollBar { }
        delegate: ItemDelegate {
            id: row
            required property var modelData
            width: choicesList.width
            implicitHeight: rowContent.implicitHeight + Studio.Theme.space24
            padding: Studio.Theme.space12
            enabled: !dialog.editor.backend.busy && !dialog.editor.dirty
            objectName: "editingDraft-" + modelData.id
            Accessible.name: modelData.name + ", " + modelData.id.substring(0, 8) + ", revision " + modelData.revision
            onClicked: dialog.editor.chooseEditingDraft(modelData.id, false)
            onActiveFocusChanged: if (activeFocus) choicesList.positionViewAtIndex(index, ListView.Contain)
            required property int index

            background: Rectangle {
                radius: Studio.Theme.shapeMedium
                color: row.down ? Studio.Theme.primaryContainer : row.hovered ? Studio.Theme.surfaceContainerHigh : Studio.Theme.surfaceContainer
                border.color: row.visualFocus ? Studio.Theme.primary : "transparent"
                border.width: Studio.Theme.focusWidth
            }
            contentItem: ColumnLayout {
                id: rowContent
                spacing: Studio.Theme.space4
                Label {
                    Layout.fillWidth: true
                    text: row.modelData.name
                    textFormat: Text.PlainText
                    color: Studio.Theme.textOnSurface
                    font.weight: Font.DemiBold
                    wrapMode: Text.WordWrap
                }
                Label {
                    Layout.fillWidth: true
                    text: qsTr("Mã nháp: %1 · Revision %2").arg(row.modelData.id.substring(0, 8)).arg(row.modelData.revision)
                    color: Studio.Theme.textOnSurfaceVariant
                    wrapMode: Text.WordWrap
                }
                Label {
                    Layout.fillWidth: true
                    visible: row.modelData.based_on_current === false
                    text: qsTr("Bài trong thư viện đã thay đổi từ khi tạo nháp này. Nội dung nháp vẫn được giữ.")
                    color: Studio.Theme.warning
                    wrapMode: Text.WordWrap
                }
            }
        }
    }
    footer: Studio.StudioDialogFooter {
        contentItem: Flow {
            spacing: Studio.Theme.space8
            Studio.StudioButton {
                text: qsTr("Tạo bản nháp riêng")
                flat: true
                objectName: "newSeparateEditingDraft"
                enabled: !dialog.editor.backend.busy && !dialog.editor.dirty
                onClicked: newDraft.open()
            }
            Studio.StudioButton {
                text: qsTr("Hủy")
                objectName: "cancelEditingDraft"
                enabled: !dialog.editor.backend.busy
                onClicked: dialog.reject()
            }
        }
    }
    Studio.ConfirmDialog {
        id: newDraft
        objectName: "newEditingDraftConfirmation"
        title: qsTr("Tạo thêm bản nháp?")
        message: qsTr("Sao chép bài hiện có trong thư viện thành một bản nháp riêng. Các bản nháp cũ được giữ nguyên.")
        confirmText: qsTr("Tạo bản nháp riêng")
        confirmEnabled: !dialog.editor.backend.busy && !dialog.editor.dirty
        onAccepted: dialog.editor.chooseEditingDraft("", true)
    }
}
