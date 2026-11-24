import QtQuick
import QtQuick.Controls.Basic
import "../.." as Studio

SpinBox {
    id: control
    implicitWidth: 148
    implicitHeight: Studio.Theme.controlHeight
    editable: true
    font.family: Studio.Theme.fontFamily
    font.pixelSize: Studio.Theme.bodyMedium
    palette.text: Studio.Theme.textOnSurface
    palette.buttonText: Studio.Theme.textOnSurface
    palette.base: Studio.Theme.surfaceContainerHigh
    palette.button: Studio.Theme.surfaceContainerHigh
    palette.mid: Studio.Theme.textOnSurfaceVariant
    palette.highlight: Studio.Theme.primary
    palette.highlightedText: Studio.Theme.textOnPrimary
    background: Rectangle {
        radius: Studio.Theme.shapeSmall
        color: Studio.Theme.surfaceContainerHigh
        border.width: control.activeFocus ? Studio.Theme.focusWidth : Studio.Theme.borderWidth
        border.color: control.activeFocus ? Studio.Theme.primary : Studio.Theme.outlineVariant
    }
    up.indicator: Rectangle {
        x: control.mirrored ? 0 : control.width - width
        implicitWidth: 40
        height: control.height
        radius: Studio.Theme.shapeSmall
        color: control.up.pressed ? Studio.Theme.secondaryContainer : Studio.Theme.transparent
        Text {
            anchors.centerIn: parent
            text: "+"
            font.pixelSize: Studio.Theme.iconSmall
            color: control.up.enabled ? Studio.Theme.primary : Studio.Theme.textOnSurfaceVariant
        }
    }
    down.indicator: Rectangle {
        x: control.mirrored ? control.width - width : 0
        implicitWidth: 40
        height: control.height
        radius: Studio.Theme.shapeSmall
        color: control.down.pressed ? Studio.Theme.secondaryContainer : Studio.Theme.transparent
        Text {
            anchors.centerIn: parent
            text: "-"
            font.pixelSize: Studio.Theme.iconSmall
            color: control.down.enabled ? Studio.Theme.primary : Studio.Theme.textOnSurfaceVariant
        }
    }
}
