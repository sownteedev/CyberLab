import QtQuick
import QtQuick.Controls.Basic
import ".." as Studio

Dialog {
    parent: Overlay.overlay
    anchors.centerIn: parent
    modal: true
    dim: modal

    background: Studio.StudioPopupSurface {
        color: Studio.Theme.surface
        radius: Studio.Theme.dialogRadius
    }
    Overlay.modal: Rectangle {
        objectName: "studioDialogScrim"
        color: Studio.Theme.scrim
        Accessible.ignored: true

        Behavior on opacity {
            NumberAnimation {
                duration: Studio.Theme.stateDuration
                easing.type: Easing.OutCubic
            }
        }
    }
    enter: Transition {
        ParallelAnimation {
            NumberAnimation { property: "opacity"; from: 0; to: 1; duration: Studio.Theme.enterDuration; easing.type: Easing.OutCubic }
            NumberAnimation { property: "scale"; from: 0.98; to: 1; duration: Studio.Theme.enterDuration; easing.type: Easing.OutCubic }
        }
    }
    exit: Transition {
        NumberAnimation { property: "opacity"; from: 1; to: 0; duration: Studio.Theme.exitDuration; easing.type: Easing.InCubic }
    }
}
