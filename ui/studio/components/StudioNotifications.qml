import QtQuick
import ".." as Studio

Item {
    id: notifications

    required property var api
    property real availableHeight: 480
    property bool windowActive: true
    property int lifetime: 5000
    property bool backendError: false
    readonly property alias errorToast: failure
    readonly property alias noticeToast: notice
    readonly property real cardHeight: Math.min(240, (availableHeight - Studio.Theme.space8) / (failure.visible && notice.visible ? 2 : 1))

    objectName: "studioNotifications"
    height: stack.implicitHeight
    visible: failure.shown || failure.opacity > 0 || notice.shown || notice.opacity > 0

    function showError() {
        if (api.error) {
            backendError = true;
            failure.present(api.error);
        } else if (backendError) {
            failure.dismiss(false);
        }
    }

    Component.onCompleted: showError()
    Connections {
        target: Studio.StudioFeedback
        function onErrorRequested(message) {
            if (failure.shown && failure.displayMessage === message) return;
            notifications.backendError = false;
            failure.present(message);
        }
    }
    Connections {
        target: notifications.api
        function onErrorChanged() { notifications.showError(); }
        function onNotificationRequested(message, isFailure) {
            if (isFailure) {
                notifications.backendError = false;
                failure.present(message);
            } else {
                notice.present(message);
            }
        }
    }
    Column {
        id: stack
        width: parent.width
        spacing: Studio.Theme.space8
        move: Transition { NumberAnimation { properties: "y"; duration: Studio.Theme.stateDuration; easing.type: Easing.OutCubic } }

        Studio.StudioToast {
            id: failure
            objectName: "studioErrorToast"
            width: stack.width
            failure: true
            lifetime: notifications.lifetime
            maximumHeight: notifications.cardHeight
            windowActive: notifications.windowActive
            onDismissed: message => {
                if (notifications.backendError && notifications.api.error === message)
                    notifications.api.error = "";
            }
        }
        Studio.StudioToast {
            id: notice
            objectName: "studioNoticeToast"
            width: stack.width
            lifetime: notifications.lifetime
            maximumHeight: notifications.cardHeight
            windowActive: notifications.windowActive
        }
    }
}
