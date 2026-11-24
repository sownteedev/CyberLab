pragma ComponentBehavior: Bound

import QtQuick
import QtQuick.Controls.Basic
import QtQuick.Layouts
import "../.." as Studio

Menu {
    id: menu

    property bool busy: false
    property bool discardSupported: false
    property bool persistenceSupported: false
    property bool quizSupported: false
    property var session: null
    readonly property string targetId: session ? session.id : ""
    property string openedFor: ""
    property string pendingAction: ""

    signal actionRequested(string action, string sessionId)

    function dismiss() {
        pendingAction = "";
        close();
    }
    function allowed(action) {
        if (!session || busy) return false;
        if (action === "save") return persistenceSupported && session.state === "RUNNING";
        if (action === "quiz") return quizSupported && !!session.quiz && session.quiz !== "[]";
        if (action === "discard") return discardSupported && !!session.saved;
        if (action === "stop") return ["PREPARING", "RESETTING", "RUNNING", "SUSPENDED", "FAILED"].includes(session.state);
        return action === "reset" && !starting && ["RUNNING", "SUSPENDED", "STOPPED", "FAILED"].includes(session.state);
    }

    property bool starting: false

    objectName: "practiceActionsMenu"
    popupType: Popup.Item
    modal: true
    dim: false
    focus: true
    padding: Studio.Theme.space8
    margins: Studio.Theme.space8
    closePolicy: Popup.CloseOnEscape | Popup.CloseOnPressOutside

    onTargetIdChanged: dismiss()
    onBusyChanged: if (busy) dismiss()
    onAboutToShow: {
        openedFor = targetId;
        pendingAction = "";
    }
    onClosed: {
        const action = pendingAction;
        pendingAction = "";
        if (parent && parent.visible) parent.forceActiveFocus(Qt.PopupFocusReason);
        if (openedFor === targetId && allowed(action)) actionRequested(action, openedFor);
    }

    background: Studio.StudioPopupSurface {
        color: Studio.Theme.surface
        radius: Studio.Theme.shapeLarge
        border.width: Studio.Theme.borderWidth
        border.color: Qt.alpha(Studio.Theme.outline, 0.18)
    }
    enter: Transition {
        NumberAnimation { property: "opacity"; from: 0; to: 1; duration: Studio.Theme.reducedMotion ? 0 : Studio.Theme.enterDuration }
    }
    exit: Transition {
        NumberAnimation { property: "opacity"; to: 0; duration: Studio.Theme.reducedMotion ? 0 : Studio.Theme.exitDuration }
    }

    MenuAction {
        actionKey: "save"
        iconName: "save"
        objectName: "practiceSaveButton"
        text: qsTr("Lưu tiến độ")
        visible: menu.persistenceSupported
    }
    MenuAction {
        actionKey: "quiz"
        iconName: "help"
        objectName: "practiceQuizButton"
        text: qsTr("Câu hỏi")
        visible: menu.quizSupported && !!menu.session && !!menu.session.quiz && menu.session.quiz !== "[]"
    }
    MenuSeparator {
        visible: menu.persistenceSupported || quizActionVisible
        readonly property bool quizActionVisible: menu.quizSupported && !!menu.session && !!menu.session.quiz && menu.session.quiz !== "[]"
        height: visible ? Studio.Theme.space16 : 0
        topPadding: (Studio.Theme.space16 - 1) / 2
        bottomPadding: topPadding
        contentItem: Rectangle {
            implicitHeight: 1
            color: Studio.Theme.outlineVariant
        }
    }
    MenuAction {
        actionKey: "reset"
        danger: true
        iconName: "restart_alt"
        objectName: "practiceResetButton"
        text: qsTr("Làm lại từ đầu")
    }
    MenuAction {
        actionKey: "stop"
        danger: true
        iconName: "stop"
        objectName: "practiceStopButton"
        text: qsTr("Dừng không lưu thay đổi mới")
    }
    MenuAction {
        actionKey: "discard"
        danger: true
        iconName: "delete"
        objectName: "discardCheckpointButton"
        text: qsTr("Xóa bản lưu")
        visible: menu.discardSupported && !!menu.session && !!menu.session.saved
    }

    component MenuAction: MenuItem {
        id: entry

        required property string actionKey
        required property string iconName
        property bool danger: false

        enabled: visible && menu.allowed(actionKey)
        implicitHeight: visible ? Math.max(Studio.Theme.controlHeight, implicitContentHeight + topPadding + bottomPadding) : 0
        leftPadding: Studio.Theme.space12
        rightPadding: Studio.Theme.space12
        onTriggered: menu.pendingAction = actionKey

        background: Rectangle {
            color: entry.highlighted || entry.down ? Studio.Theme.secondaryContainer : Studio.Theme.transparent
            radius: Studio.Theme.shapeSmall
            border.width: entry.visualFocus ? Studio.Theme.focusWidth : 0
            border.color: Studio.Theme.primary
        }
        contentItem: RowLayout {
            spacing: Studio.Theme.space12
            opacity: entry.enabled ? 1 : 0.38

            Studio.Icon {
                name: entry.iconName
                color: entry.danger ? Studio.Theme.error : Studio.Theme.textOnSurfaceVariant
                size: Studio.Theme.iconSmall
            }
            Label {
                Layout.fillWidth: true
                color: entry.danger ? Studio.Theme.error : Studio.Theme.textOnSurface
                font.family: Studio.Theme.fontFamily
                font.pixelSize: Studio.Theme.bodyMedium
                text: entry.text
                wrapMode: Text.WordWrap
            }
        }
    }
}
