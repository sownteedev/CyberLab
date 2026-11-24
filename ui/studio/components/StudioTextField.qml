import QtQuick
import QtQuick.Controls.Basic
import ".."
import ".." as Studio

TextField {
    id: field

    property bool error: false
    hoverEnabled: true

    Accessible.name: placeholderText
    bottomPadding: 0
    color: Studio.Theme.textOnSurface
    font.family: Studio.Theme.fontFamily
    font.pixelSize: Studio.Theme.bodyMedium
    implicitHeight: Studio.Theme.controlHeight
    leftPadding: Studio.Theme.space16
    placeholderTextColor: Studio.Theme.textOnSurfaceVariant
    rightPadding: Studio.Theme.space16
    selectByMouse: true
    selectedTextColor: Studio.Theme.textOnPrimaryContainer
    selectionColor: Studio.Theme.primaryContainer
    topPadding: 0

    background: Rectangle {
        border.color: field.error ? Studio.Theme.error : field.activeFocus ? Studio.Theme.primary : Studio.Theme.outline
        border.width: field.activeFocus ? Studio.Theme.focusWidth : Studio.Theme.borderWidth
        color: Studio.Theme.surfaceContainerHigh
        radius: Studio.Theme.shapeMedium
        Rectangle {
            anchors.fill: parent
            color: Studio.Theme.textOnSurface
            opacity: field.enabled && field.hovered ? Studio.Theme.hoverOpacity : 0
            radius: parent.radius
            Behavior on opacity { NumberAnimation { duration: Studio.Theme.stateDuration } }
        }
    }
}
