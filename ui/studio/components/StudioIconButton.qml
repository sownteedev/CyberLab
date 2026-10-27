import QtQuick
import QtQuick.Controls.Basic
import ".."
import ".." as Studio

StudioButton {
    id: control
    property string description: ""
    iconSize: Studio.Theme.iconSize
    implicitWidth: Studio.Theme.controlHeight
    leftPadding: Studio.Theme.space12
    rightPadding: Studio.Theme.space12
    flat: true
    Accessible.name: description
    ToolTip.visible: (hovered || visualFocus) && description.length > 0
    ToolTip.delay: 600
    ToolTip.timeout: 4000
    ToolTip.text: description
}
