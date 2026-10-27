import QtQuick
import QtQuick.Controls.Basic
import ".."
import ".." as Studio

TextField {
    id: field
    property bool error: false
    implicitHeight: Studio.Theme.controlHeight
    leftPadding: Studio.Theme.space16
    rightPadding: Studio.Theme.space16
    topPadding: 0
    bottomPadding: 0
    color: Studio.Theme.textOnSurface
    selectionColor: Studio.Theme.primaryContainer
    selectedTextColor: Studio.Theme.textOnPrimaryContainer
    placeholderTextColor: Studio.Theme.textOnSurfaceVariant
    font.family: Studio.Theme.fontFamily
    font.pixelSize: Studio.Theme.bodyMedium
    selectByMouse: true
    Accessible.name: placeholderText
    background: Rectangle {
        radius: Studio.Theme.shapeMedium
        color: Studio.Theme.surfaceContainerHigh
        border.width: field.activeFocus ? Studio.Theme.focusWidth : Studio.Theme.borderWidth
        border.color: field.error ? Studio.Theme.error : field.activeFocus ? Studio.Theme.primary : Studio.Theme.outlineVariant
    }
}
