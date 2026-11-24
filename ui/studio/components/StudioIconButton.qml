import QtQuick
import QtQuick.Controls.Basic
import ".."
import ".." as Studio

StudioButton {
    id: control

    property string description: ""

    Accessible.name: description
    ToolTip.delay: 600
    ToolTip.text: description
    ToolTip.timeout: 4000
    ToolTip.visible: (hovered || visualFocus) && description.length > 0
    flat: true
    iconSize: Studio.Theme.iconSize
    implicitWidth: Studio.Theme.controlHeight
    leftPadding: Studio.Theme.space12
    rightPadding: Studio.Theme.space12
}
