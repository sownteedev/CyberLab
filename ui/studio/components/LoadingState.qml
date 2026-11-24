import QtQuick
import QtQuick.Controls.Basic
import ".."
import ".." as Studio

Item {
    id: indicator

    property bool busy: false
    property bool revealed: false

    clip: true
    implicitHeight: 2

    onBusyChanged: {
        if (busy)
            delay.restart();
        else {
            delay.stop();
            revealed = false;
        }
    }

    Timer {
        id: delay

        interval: 400
        running: indicator.busy

        onTriggered: indicator.revealed = indicator.busy
    }
    ProgressBar {
        Accessible.name: "Thao tác đang thực hiện"
        anchors.fill: parent
        indeterminate: !Studio.Theme.reducedMotion
        palette.dark: Studio.Theme.surfaceContainerHigh
        palette.highlight: Studio.Theme.primary
        value: 1
        visible: indicator.revealed
    }
}
