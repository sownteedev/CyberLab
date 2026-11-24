import QtQuick
import QtQuick.Controls.Basic
import QtQuick.Layouts
import ".." as Studio
import "../models/Messages.js" as Messages

FocusScope {
    id: toast

    property bool failure: false
    property int lifetime: 5000
    property real maximumHeight: 240
    property string message: ""
    readonly property string displayMessage: Messages.text(message)
    property bool shown: false
    property bool windowActive: true
    readonly property bool reading: hover.hovered || activeFocus || !windowActive
    readonly property real slideOffset: slide.x
    readonly property string heading: failure ? "Không thể hoàn tất" : "Thông báo"
    signal dismissed(string message)

    function present(text) {
        const value = String(text || "");
        if (!value.trim()) return;
        message = value;
        body.cursorPosition = 0;
        body.deselect();
        const scrollArea = messageScroll.contentItem as Flickable;
        if (scrollArea) scrollArea.contentY = 0;
        shown = true;
        expiry.restart();
        if (typeof toast.Accessible.announce === "function")
            toast.Accessible.announce(heading + ". " + displayMessage);
    }
    function dismiss(manual) {
        if (!shown) return;
        expiry.stop();
        shown = false;
        if (manual) dismissed(message);
    }

    Accessible.role: failure ? Accessible.AlertMessage : Accessible.StaticText
    Accessible.name: heading
    Accessible.description: displayMessage
    implicitHeight: content.implicitHeight + Studio.Theme.space24
    height: implicitHeight
    opacity: 0
    state: shown ? "shown" : "hidden"
    visible: shown || opacity > 0
    transform: Translate { id: slide; x: toast.width + Studio.Theme.space32 }
    Keys.onEscapePressed: dismiss(true)

    states: [
        State {
            name: "shown"
            PropertyChanges { toast.opacity: 1; slide.x: 0 }
        },
        State {
            name: "hidden"
            PropertyChanges { toast.opacity: 0; slide.x: toast.width + Studio.Theme.space32 }
        }
    ]
    transitions: [
        Transition {
            from: "hidden"; to: "shown"
            ParallelAnimation {
                NumberAnimation { target: toast; property: "opacity"; duration: Studio.Theme.enterDuration; easing.type: Easing.OutCubic }
                NumberAnimation { target: slide; property: "x"; duration: Studio.Theme.enterDuration; easing.type: Easing.OutCubic }
            }
        },
        Transition {
            from: "shown"; to: "hidden"
            ParallelAnimation {
                NumberAnimation { target: toast; property: "opacity"; duration: Studio.Theme.exitDuration; easing.type: Easing.InCubic }
                NumberAnimation { target: slide; property: "x"; duration: Studio.Theme.exitDuration; easing.type: Easing.InCubic }
            }
        }
    ]

    Studio.StudioPopupSurface {
        anchors.fill: parent
        border.color: Qt.alpha(toast.failure ? Studio.Theme.error : Studio.Theme.primary, 0.3)
    }
    HoverHandler { id: hover }
    MouseArea {
        anchors.fill: parent
        acceptedButtons: Qt.AllButtons
        onPressed: event => event.accepted = true
        onWheel: event => event.accepted = true
    }
    RowLayout {
        id: content
        anchors.fill: parent
        anchors.margins: Studio.Theme.space12
        spacing: Studio.Theme.space12

        Rectangle {
            Layout.alignment: Qt.AlignTop
            Layout.preferredWidth: Studio.Theme.controlHeight - Studio.Theme.space8
            Layout.preferredHeight: Studio.Theme.controlHeight - Studio.Theme.space8
            radius: Studio.Theme.shapeMedium
            color: toast.failure ? Studio.Theme.errorContainer : Studio.Theme.primaryContainer
            Studio.Icon {
                anchors.centerIn: parent
                name: toast.failure ? "error" : "check_circle"
                color: toast.failure ? Studio.Theme.textOnErrorContainer : Studio.Theme.textOnPrimaryContainer
            }
        }
        ColumnLayout {
            Layout.fillWidth: true
            Layout.minimumWidth: 0
            spacing: Studio.Theme.space4
            Label {
                id: title
                Layout.fillWidth: true
                Layout.topMargin: Studio.Theme.space4
                text: toast.heading
                color: Studio.Theme.textOnSurface
                font.family: Studio.Theme.fontFamily
                font.pixelSize: Studio.Theme.titleSmall
                font.weight: Font.DemiBold
                elide: Text.ElideRight
            }
            ScrollView {
                id: messageScroll
                Layout.fillWidth: true
                Layout.preferredHeight: Math.min(body.implicitHeight, Math.max(32, toast.maximumHeight - Studio.Theme.space32 - title.implicitHeight))
                contentWidth: availableWidth
                clip: true
                ScrollBar.horizontal.policy: ScrollBar.AlwaysOff
                TextArea {
                    id: body
                    objectName: "toastMessage"
                    text: toast.displayMessage
                    textFormat: TextEdit.PlainText
                    readOnly: true
                    selectByMouse: true
                    activeFocusOnTab: true
                    padding: 0
                    wrapMode: TextEdit.Wrap
                    font.family: Studio.Theme.fontFamily
                    font.pixelSize: Studio.Theme.bodyMedium
                    color: Studio.Theme.textOnSurfaceVariant
                    selectionColor: Studio.Theme.primaryContainer
                    selectedTextColor: Studio.Theme.textOnPrimaryContainer
                    background: null
                    Accessible.name: toast.displayMessage
                }
            }
        }
        Studio.StudioIconButton {
            objectName: "toastClose"
            Layout.alignment: Qt.AlignTop
            iconName: "close"
            description: "Đóng thông báo"
            onClicked: toast.dismiss(true)
        }
    }
    Timer {
        id: expiry
        interval: toast.lifetime
        onTriggered: toast.dismiss(false)
    }
}
