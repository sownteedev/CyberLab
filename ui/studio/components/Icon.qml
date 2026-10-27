import QtQuick
import QtQuick.Controls.impl
import ".."
import ".." as Studio

Item {
    id: icon
    property string name: ""
    property int size: Studio.Theme.iconSize
    property color color: Studio.Theme.textOnSurface
    readonly property int status: image.status
    implicitWidth: size
    implicitHeight: size
    Accessible.ignored: true
    ColorImage {
        id: image
        anchors.fill: parent
        source: icon.name.length ? Qt.resolvedUrl("../assets/icons/" + icon.name + ".svg") : ""
        sourceSize: Qt.size(icon.size, icon.size)
        fillMode: Image.PreserveAspectFit
        color: icon.color
    }
}
