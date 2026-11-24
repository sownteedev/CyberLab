pragma ComponentBehavior: Bound

import QtQuick
import ".." as Studio

Rectangle {
    id: surface

    color: Studio.Theme.surfaceContainerHigh
    radius: Studio.Theme.shapeExtraLarge
    border.width: Studio.Theme.borderWidth
    border.color: Qt.alpha(Studio.Theme.outline, 0.18)
    Accessible.ignored: true
    objectName: "studioPopupSurface"

    Repeater {
        model: 16

        Rectangle {
            required property int index
            readonly property real spread: (index + 1) * Studio.Theme.popupShadowExtent / 16

            x: -spread
            y: Studio.Theme.popupShadowOffset - spread
            width: surface.width + spread * 2
            height: surface.height + spread * 2
            radius: surface.radius + spread
            color: Qt.alpha(Studio.Theme.popupShadow, Studio.Theme.popupShadowOpacity * Math.pow(1 - index / 16, 1.5))
            z: -1
            antialiasing: true
            Accessible.ignored: true
        }
    }
}
