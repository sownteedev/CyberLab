import QtQuick
import QtQuick.Controls.Basic
import ".."
import ".." as Studio

TextArea {
    id: field
    color: Studio.Theme.textOnSurface
    placeholderTextColor: Studio.Theme.textOnSurfaceVariant
    selectionColor: Studio.Theme.primaryContainer
    selectedTextColor: Studio.Theme.textOnPrimaryContainer
    font.family: Studio.Theme.monoFamily
    font.pixelSize: Studio.Theme.bodyMedium
    padding: Studio.Theme.space16
    selectByMouse: true
    Accessible.name: placeholderText
    background: Rectangle {
        color: Studio.Theme.surfaceContainerHigh
        radius: Studio.Theme.shapeSmall
        border.color: field.activeFocus ? Studio.Theme.primary : Studio.Theme.outline
        border.width: field.activeFocus ? Studio.Theme.focusWidth : Studio.Theme.borderWidth
    }
}
