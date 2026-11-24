import QtQuick
import QtQuick.Controls.Basic
import ".."
import ".." as Studio

TextArea {
    id: field

    Accessible.name: placeholderText
    color: Studio.Theme.textOnSurface
    font.family: Studio.Theme.monoFamily
    font.pixelSize: Studio.Theme.bodyMedium
    padding: Studio.Theme.space16
    placeholderTextColor: Studio.Theme.textOnSurfaceVariant
    selectByMouse: true
    selectedTextColor: Studio.Theme.textOnPrimaryContainer
    selectionColor: Studio.Theme.primaryContainer

    background: Rectangle {
        border.color: field.activeFocus ? Studio.Theme.primary : Studio.Theme.outline
        border.width: field.activeFocus ? Studio.Theme.focusWidth : Studio.Theme.borderWidth
        color: Studio.Theme.surfaceContainerHigh
        radius: Studio.Theme.shapeSmall
    }
}
