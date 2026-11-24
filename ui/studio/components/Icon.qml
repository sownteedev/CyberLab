import QtQuick
import QtQuick.Controls.impl
import ".."
import ".." as Studio

Item {
    id: icon

    property color color: Studio.Theme.textOnSurface
    property string name: ""
    property int size: Studio.Theme.iconSize
    readonly property int status: image.status

    Accessible.ignored: true
    implicitHeight: size
    implicitWidth: size

    ColorImage {
        id: image

        anchors.fill: parent
        color: icon.color
        fillMode: Image.PreserveAspectFit
        source: icon.name.length ? Qt.resolvedUrl("../assets/icons/" + icon.name + ".svg") : ""
        sourceSize: Qt.size(icon.size, icon.size)
    }
}
