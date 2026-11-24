import QtQuick
import QtQuick.Controls.Basic
import ".."
import ".." as Studio

Rectangle {
    id: handle

    color: Studio.Theme.transparent
    implicitWidth: Studio.Theme.space16

    Rectangle {
        anchors.centerIn: parent
        color: handle.SplitHandle.hovered || handle.SplitHandle.pressed ? Studio.Theme.primary : Studio.Theme.outlineVariant
        height: Studio.Theme.controlHeight
        radius: Studio.Theme.shapeFull
        width: Studio.Theme.space4
    }
}
