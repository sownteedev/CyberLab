import QtQuick
import ".."
import ".." as Studio

StudioTextField {
    id: searchField

    leftPadding: Studio.Theme.controlHeight
    placeholderText: "Tìm bài lab"

    background: Rectangle {
        border.color: searchField.error ? Studio.Theme.error : searchField.activeFocus ? Studio.Theme.primary : Studio.Theme.outlineVariant
        border.width: searchField.activeFocus ? Studio.Theme.focusWidth : Studio.Theme.borderWidth
        color: Studio.Theme.surfaceContainerHigh
        radius: Studio.Theme.shapeFull
    }

    Icon {
        anchors.left: parent.left
        anchors.leftMargin: Studio.Theme.space16
        anchors.verticalCenter: parent.verticalCenter
        color: Studio.Theme.textOnSurfaceVariant
        name: "search"
    }
}
