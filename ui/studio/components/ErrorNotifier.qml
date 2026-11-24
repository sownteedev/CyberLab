import QtQuick
import ".." as Studio

Item {
    id: notifier
    property string message: ""
    property bool active: true
    property string reported: ""

    function schedule() {
        if (!message) reported = "";
        if (visible && active && message && message !== reported) deferred.restart();
    }

    onMessageChanged: schedule()
    onActiveChanged: schedule()
    onVisibleChanged: schedule()
    Component.onCompleted: schedule()

    Timer {
        id: deferred
        interval: 0
        onTriggered: {
            if (!notifier.visible || !notifier.active || !notifier.message || notifier.message === notifier.reported) return;
            notifier.reported = notifier.message;
            Studio.StudioFeedback.report(notifier.message);
        }
    }
}
