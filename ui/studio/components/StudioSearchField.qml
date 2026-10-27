import QtQuick
import ".."
import ".." as Studio

StudioTextField {
    id: searchField
    placeholderText: "Tìm bài lab"
    leftPadding: Studio.Theme.controlHeight
    background: Rectangle {
        radius: Studio.Theme.shapeFull
        color: Studio.Theme.surfaceContainerHigh
        border.width: searchField.activeFocus ? Studio.Theme.focusWidth : Studio.Theme.borderWidth
        border.color: searchField.error ? Studio.Theme.error : searchField.activeFocus ? Studio.Theme.primary : Studio.Theme.outlineVariant
    }
    Icon {
        anchors.left: parent.left
        anchors.leftMargin: Studio.Theme.space16
        anchors.verticalCenter: parent.verticalCenter
        name: "search"
        color: Studio.Theme.textOnSurfaceVariant
    }
}
