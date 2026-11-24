import QtQuick
import QtQuick.Controls.Basic
import ".." as Studio

CheckBox {
    id: control

    focusPolicy: Qt.StrongFocus
    hoverEnabled: true
    font.family: Studio.Theme.fontFamily
    font.pixelSize: Studio.Theme.bodyMedium
    implicitHeight: Math.max(Studio.Theme.controlHeight, implicitContentHeight + topPadding + bottomPadding)
    padding: Studio.Theme.space8
    spacing: Studio.Theme.space12
    Accessible.name: text

    indicator: Rectangle {
        implicitWidth: 20
        implicitHeight: 20
        x: control.mirrored ? control.width - width - control.rightPadding : control.leftPadding
        y: (control.height - height) / 2
        radius: control.down ? 6 : Studio.Theme.shapeExtraSmall
        color: control.checkState !== Qt.Unchecked ? Studio.Theme.primary : "transparent"
        border.width: control.checkState === Qt.Unchecked ? 2 : 0
        border.color: Studio.Theme.outline
        opacity: control.enabled ? 1 : Studio.Theme.disabledOpacity
        Behavior on radius { NumberAnimation { duration: Studio.Theme.pressDuration } }
        Studio.Icon {
            anchors.centerIn: parent
            name: "check"
            size: 16
            color: Studio.Theme.textOnPrimary
            visible: control.checkState === Qt.Checked
        }
        Rectangle {
            anchors.centerIn: parent
            width: 10
            height: 2
            color: Studio.Theme.textOnPrimary
            visible: control.checkState === Qt.PartiallyChecked
        }
    }
    contentItem: Text {
        text: control.text
        textFormat: Text.PlainText
        font: control.font
        color: Studio.Theme.textOnSurface
        opacity: control.enabled ? 1 : Studio.Theme.disabledOpacity
        verticalAlignment: Text.AlignVCenter
        wrapMode: Text.Wrap
        leftPadding: control.mirrored ? 0 : control.indicator.width + control.spacing
        rightPadding: control.mirrored ? control.indicator.width + control.spacing : 0
    }
    background: Rectangle {
        radius: Studio.Theme.shapeMedium
        color: Qt.alpha(Studio.Theme.primary, !control.enabled ? 0 : control.down ? Studio.Theme.pressedOpacity : control.hovered ? Studio.Theme.hoverOpacity : 0)
        border.width: control.visualFocus ? Studio.Theme.focusWidth : 0
        border.color: Studio.Theme.primary
    }
}
