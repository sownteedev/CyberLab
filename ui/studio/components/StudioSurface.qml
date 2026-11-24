import QtQuick
import ".."
import ".." as Studio

Rectangle {
    id: surface

    property bool interactive: false
    property bool outlined: false
    property bool selected: false

    signal clicked

    Accessible.role: interactive ? Accessible.Button : Accessible.Pane
    activeFocusOnTab: interactive
    border.color: activeFocus ? Studio.Theme.primary : (selected ? Studio.Theme.primary : Studio.Theme.outlineVariant)
    border.width: activeFocus ? Studio.Theme.focusWidth : Studio.Theme.borderWidth
    color: selected ? Studio.Theme.primaryContainer : (interactive && mouse.containsMouse ? Studio.Theme.surfaceContainerHigh : Studio.Theme.surfaceContainer)
    radius: Studio.Theme.shapeLarge

    Accessible.onPressAction: if (interactive && enabled)
        clicked()
    Keys.onReturnPressed: if (interactive)
        clicked()
    Keys.onSpacePressed: if (interactive)
        clicked()

    MouseArea {
        id: mouse

        anchors.fill: parent
        cursorShape: surface.interactive ? Qt.PointingHandCursor : Qt.ArrowCursor
        enabled: surface.interactive
        hoverEnabled: surface.interactive

        onClicked: {
            surface.forceActiveFocus(Qt.MouseFocusReason);
            surface.clicked();
        }
    }
}
