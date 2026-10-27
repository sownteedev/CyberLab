import QtQuick
import QtQuick.Controls.Basic
import ".."
import ".." as Studio

Item {
    id: indicator
    property bool busy: false
    property bool revealed: false
    implicitHeight: 2
    clip: true
    onBusyChanged: {
        if (busy) delay.restart();
        else { delay.stop(); revealed = false; }
    }
    Timer {
        id: delay
        interval: 400
        running: indicator.busy
        onTriggered: indicator.revealed = indicator.busy
    }
    ProgressBar {
        anchors.fill: parent
        visible: indicator.revealed
        indeterminate: !Studio.Theme.reducedMotion
        value: 1
        palette.highlight: Studio.Theme.primary
        palette.dark: Studio.Theme.surfaceContainerHigh
        Accessible.name: "Thao tác đang thực hiện"
    }
}
