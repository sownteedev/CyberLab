import QtQuick
import QtQuick.Controls.Basic
import ".." as Studio

Switch {
    id: control

    Accessible.name: text
    focusPolicy: Qt.StrongFocus
    hoverEnabled: true
    padding: 6
    spacing: Studio.Theme.space12
    implicitWidth: Math.max(implicitContentWidth, implicitIndicatorWidth) + leftPadding + rightPadding
    implicitHeight: Math.max(Studio.Theme.controlHeight, implicitContentHeight + topPadding + bottomPadding)
    font.family: Studio.Theme.fontFamily
    font.pixelSize: Studio.Theme.bodyMedium

    indicator: Rectangle {
        implicitWidth: 52
        implicitHeight: 32
        x: control.mirrored ? control.leftPadding : control.width - width - control.rightPadding
        y: (control.height - height) / 2
        radius: height / 2
        opacity: control.enabled ? 1 : Studio.Theme.disabledOpacity
        color: control.checked ? Studio.Theme.primary : Studio.Theme.surfaceContainerHigh
        border.color: Studio.Theme.outline
        border.width: control.checked ? 0 : 2

        Rectangle {
            anchors.fill: parent
            anchors.margins: -3
            radius: 17
            color: "transparent"
            border.color: Studio.Theme.primary
            border.width: Studio.Theme.focusWidth
            visible: control.visualFocus
        }
        Rectangle {
            objectName: "toggleHandle"
            width: control.down ? 26 : control.checked ? 24 : 16
            height: width
            radius: width / 2
            x: 4 + control.visualPosition * (parent.width - width - 8)
            y: (parent.height - height) / 2
            color: control.checked ? Studio.Theme.textOnPrimary : Studio.Theme.outline
            Behavior on x { enabled: !control.pressed; NumberAnimation { duration: Studio.Theme.stateDuration; easing.type: Easing.OutCubic } }
            Behavior on width { NumberAnimation { duration: Studio.Theme.pressDuration; easing.type: Easing.OutCubic } }
            Studio.Icon {
                anchors.centerIn: parent
                name: "check"
                size: 16
                color: Studio.Theme.primary
                visible: control.checked
            }
        }
    }
    contentItem: Text {
        text: control.text
        textFormat: Text.PlainText
        font: control.font
        color: Studio.Theme.textOnSurface
        opacity: control.enabled ? 1 : Studio.Theme.disabledOpacity
        verticalAlignment: Text.AlignVCenter
        wrapMode: Text.WordWrap
        leftPadding: control.mirrored ? control.indicator.width + control.spacing : 0
        rightPadding: control.mirrored ? 0 : control.indicator.width + control.spacing
    }
    background: Rectangle {
        radius: Studio.Theme.shapeMedium
        color: Qt.alpha(Studio.Theme.primary, !control.enabled ? 0 : control.down ? Studio.Theme.pressedOpacity : control.hovered ? Studio.Theme.hoverOpacity : 0)
        Behavior on color { ColorAnimation { duration: Studio.Theme.stateDuration } }
    }
}
