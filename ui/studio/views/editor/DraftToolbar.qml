pragma ComponentBehavior: Bound

import QtQuick
import QtQuick.Controls.Basic
import QtQuick.Layouts
import "../.." as Studio

Control {
    id: toolbar

    required property var editor
    readonly property bool compact: width < 760
    readonly property alias exportAction: exportAction
    readonly property alias menu: actionsMenu
    signal chooseRequested
    signal validateRequested
    signal publishRequested
    signal exportRequested
    signal reloadRequested
    signal deleteRequested

    objectName: "draftEditActions"
    padding: Studio.Theme.space8
    implicitHeight: contentItem.implicitHeight + padding * 2
    onVisibleChanged: if (!visible) actionsMenu.close()

    contentItem: GridLayout {
        columns: toolbar.compact ? 1 : 2
        columnSpacing: Studio.Theme.space16
        rowSpacing: Studio.Theme.space8

        RowLayout {
            Layout.fillWidth: true
            Layout.minimumWidth: 0
            spacing: Studio.Theme.space8

            Studio.StudioIconButton {
                description: qsTr("Bản nháp / Tạo mới")
                enabled: !toolbar.editor.backend.busy
                iconName: "arrow_back"
                objectName: "chooseDraftButton"
                onClicked: toolbar.chooseRequested()
            }
            ColumnLayout {
                Layout.fillWidth: true
                Layout.minimumWidth: 0
                spacing: Studio.Theme.space4

                Label {
                    Layout.fillWidth: true
                    Layout.minimumWidth: 0
                    color: Studio.Theme.textOnSurface
                    elide: Text.ElideRight
                    font.pixelSize: Studio.Theme.titleLarge
                    font.weight: Font.DemiBold
                    text: toolbar.editor.document ? toolbar.editor.document.metadata.name : qsTr("Bản nháp")
                    textFormat: Text.PlainText
                }
                Label {
                    Layout.fillWidth: true
                    color: toolbar.editor.dirty ? Studio.Theme.warning : Studio.Theme.textOnSurfaceVariant
                    font.pixelSize: Studio.Theme.bodySmall
                    text: toolbar.editor.dirty ? qsTr("Có thay đổi chưa lưu") : qsTr("Đã lưu bản nháp")
                }
            }
        }
        RowLayout {
            Layout.fillWidth: toolbar.compact
            Layout.alignment: Qt.AlignRight
            spacing: Studio.Theme.space4

            Studio.StudioButton {
                enabled: !!toolbar.editor.draft && toolbar.editor.dirty && !toolbar.editor.backend.busy
                flat: true
                iconName: "save"
                iconOnly: toolbar.width < 460
                objectName: "saveDraftButton"
                text: qsTr("Lưu nháp")
                onClicked: toolbar.editor.save()
            }
            Studio.StudioButton {
                enabled: !!toolbar.editor.document && !toolbar.editor.backend.busy
                iconName: "check_circle"
                iconOnly: toolbar.width < 460
                objectName: "validateDraftButton"
                text: qsTr("Kiểm tra")
                onClicked: toolbar.validateRequested()
            }
            Studio.StudioButton {
                Layout.fillWidth: toolbar.compact
                Layout.minimumWidth: 0
                enabled: !!toolbar.editor.document && !!toolbar.editor.draft && !toolbar.editor.backend.busy
                highlighted: true
                iconName: "check"
                objectName: "publishDraftButton"
                text: toolbar.editor.isInstalledEdit ? qsTr("Cập nhật bài") : qsTr("Lưu vào thư viện")
                onClicked: toolbar.publishRequested()
            }
            Studio.StudioIconButton {
                id: more
                description: qsTr("Thao tác với bản nháp")
                iconName: "more_horiz"
                objectName: "draftActionsButton"
                selected: actionsMenu.opened
                onClicked: actionsMenu.open()
            }
        }
    }
    Menu {
        id: actionsMenu
        property string pending: ""
        parent: more
        objectName: "draftActionsMenu"
        popupType: Popup.Item
        modal: true
        dim: true
        padding: Studio.Theme.space8
        margins: Studio.Theme.space8
        width: Math.min(280, toolbar.width)
        x: more.width - width
        y: more.height + Studio.Theme.space4
        background: Studio.StudioPopupSurface { color: Studio.Theme.surface; radius: Studio.Theme.shapeLarge }
        Overlay.modal: Rectangle { color: Studio.Theme.scrim; Accessible.ignored: true }
        onClosed: {
            const action = pending;
            pending = "";
            if (!toolbar.visible)
                return;
            more.forceActiveFocus(Qt.PopupFocusReason);
            if (action === "export") toolbar.exportRequested();
            if (action === "reload") toolbar.reloadRequested();
            if (action === "delete") toolbar.deleteRequested();
        }
        DraftAction {
            id: exportAction
            enabled: !!toolbar.editor.document && !toolbar.editor.dirty && !toolbar.editor.backend.busy
            visible: toolbar.editor.backend.capabilities.includes("lab-package-export")
            iconName: "upload"
            objectName: "exportDraftPackageButton"
            text: qsTr("Xuất gói bản nháp")
            onTriggered: actionsMenu.pending = "export"
        }
        DraftAction {
            enabled: !!toolbar.editor.draft && !toolbar.editor.backend.busy
            iconName: "refresh"
            objectName: "reloadDraftButton"
            text: qsTr("Tải lại bản đã lưu")
            onTriggered: actionsMenu.pending = "reload"
        }
        DraftAction {
            enabled: !!toolbar.editor.draft && !toolbar.editor.backend.busy
            danger: true
            iconName: "delete"
            objectName: "deleteDraftButton"
            text: qsTr("Xóa bản nháp")
            onTriggered: actionsMenu.pending = "delete"
        }
    }
    component DraftAction: MenuItem {
        id: action
        required property string iconName
        property bool danger: false
        implicitHeight: visible ? Studio.Theme.controlHeight : 0
        padding: Studio.Theme.space12
        background: Rectangle {
            color: action.highlighted || action.down ? Studio.Theme.surfaceContainerHigh : Studio.Theme.transparent
            radius: Studio.Theme.shapeSmall
            border.width: action.visualFocus ? Studio.Theme.focusWidth : 0
            border.color: Studio.Theme.primary
        }
        contentItem: RowLayout {
            spacing: Studio.Theme.space12
            opacity: action.enabled ? 1 : 0.38
            Studio.Icon { name: action.iconName; color: action.danger ? Studio.Theme.error : Studio.Theme.textOnSurfaceVariant; size: Studio.Theme.iconSmall }
            Label {
                Layout.fillWidth: true
                color: action.danger ? Studio.Theme.error : Studio.Theme.textOnSurface
                text: action.text
                font.pixelSize: Studio.Theme.bodyMedium
                elide: Text.ElideRight
            }
        }
    }
}
