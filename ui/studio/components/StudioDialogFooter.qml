import QtQuick
import QtQuick.Controls.Basic
import ".." as Studio

Control {
    implicitHeight: implicitContentHeight + topPadding + bottomPadding
    padding: Studio.Theme.space24
    topPadding: Studio.Theme.space16
    objectName: "studioDialogFooter"

    background: Rectangle {
        height: 1
        color: Studio.Theme.outlineVariant
    }
}
