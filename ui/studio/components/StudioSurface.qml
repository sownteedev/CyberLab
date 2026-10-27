import QtQuick
import ".."
import ".." as Studio

Rectangle {
    id: surface

    property bool interactive: false
    property bool selected: false
    property bool outlined: false
    activeFocusOnTab: interactive
    Accessible.role: interactive ? Accessible.Button : Accessible.Pane
    Accessible.onPressAction: if (interactive && enabled) clicked()
    Keys.onReturnPressed: if (interactive) clicked()
    Keys.onSpacePressed: if (interactive) clicked()

    radius: Studio.Theme.shapeLarge
    color: selected ? Studio.Theme.primaryContainer
                    : (interactive && mouse.containsMouse ? Studio.Theme.surfaceContainerHigh
                                                          : Studio.Theme.surfaceContainer)
    border.width: activeFocus ? Studio.Theme.focusWidth : Studio.Theme.borderWidth
    border.color: activeFocus ? Studio.Theme.primary : (selected ? Studio.Theme.primary : Studio.Theme.outlineVariant)

    MouseArea {
        id: mouse
        anchors.fill: parent
        enabled: surface.interactive
        hoverEnabled: surface.interactive
        cursorShape: surface.interactive ? Qt.PointingHandCursor : Qt.ArrowCursor
        onClicked: { surface.forceActiveFocus(Qt.MouseFocusReason); surface.clicked(); }
    }

    signal clicked()
}
