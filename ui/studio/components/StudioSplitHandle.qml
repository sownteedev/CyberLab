import QtQuick
import QtQuick.Controls.Basic
import ".."
import ".." as Studio

Rectangle {
    id: handle
    implicitWidth: Studio.Theme.space16
    color: Studio.Theme.transparent
    Rectangle {
        anchors.centerIn: parent
        width: Studio.Theme.space4
        height: Studio.Theme.controlHeight
        radius: Studio.Theme.shapeFull
        color: handle.SplitHandle.hovered || handle.SplitHandle.pressed ? Studio.Theme.primary : Studio.Theme.outlineVariant
    }
}
