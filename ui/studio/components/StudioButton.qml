import QtQuick
import QtQuick.Controls.Basic
import QtQuick.Layouts
import ".."
import ".." as Studio

Button {
    id: control

    property bool busy: false
    property bool danger: false
    readonly property color foreground: !enabled ? Qt.alpha(Studio.Theme.textOnSurface, Studio.Theme.disabledOpacity) : danger ? (flat || outlined ? Studio.Theme.error : Studio.Theme.textOnErrorContainer) : selected ? Studio.Theme.textOnPrimaryContainer : outlined ? Studio.Theme.primary : highlighted ? Studio.Theme.textOnPrimary : flat ? Studio.Theme.textOnSurface : Studio.Theme.textOnSecondaryContainer
    property string iconName: ""
    property bool iconOnly: false
    property int iconSize: Studio.Theme.iconSmall
    property bool leading: false
    property bool outlined: false
    property bool selected: false

    Accessible.name: text
    Accessible.description: busy ? "Đang xử lý" : ""
    enabled: !busy
    ToolTip.delay: 600
    ToolTip.text: text
    ToolTip.visible: iconOnly && (hovered || visualFocus)
    bottomPadding: 0
    focusPolicy: Qt.StrongFocus
    font.family: Studio.Theme.fontFamily
    font.pixelSize: Studio.Theme.labelLarge
    font.weight: Font.DemiBold
    hoverEnabled: true
    implicitHeight: Studio.Theme.controlHeight
    implicitWidth: Math.max(Studio.Theme.controlHeight, Math.ceil(implicitContentWidth) + leftPadding + rightPadding)
    leftPadding: Studio.Theme.space16
    rightPadding: Studio.Theme.space16
    topPadding: 0

    background: Rectangle {
        anchors.fill: parent
        anchors.margins: Studio.Theme.space4
        border.color: control.visualFocus ? Studio.Theme.primary : control.danger ? Studio.Theme.error : Studio.Theme.outline
        border.width: control.visualFocus ? Studio.Theme.focusWidth : (control.outlined ? Studio.Theme.borderWidth : 0)
        color: !control.enabled ? (control.flat || control.outlined ? Studio.Theme.transparent : Studio.Theme.surfaceContainerHigh) : control.danger ? (control.flat || control.outlined ? Studio.Theme.transparent : Studio.Theme.errorContainer) : control.selected ? Studio.Theme.primaryContainer : control.flat || control.outlined ? Studio.Theme.transparent : control.highlighted ? Studio.Theme.primary : Studio.Theme.secondaryContainer
        radius: control.down ? Studio.Theme.shapeMedium : height / 2

        Behavior on radius { NumberAnimation { duration: Studio.Theme.pressDuration; easing.type: Easing.OutCubic } }

        Rectangle {
            anchors.fill: parent
            color: control.foreground
            opacity: !control.enabled ? 0 : control.down ? Studio.Theme.pressedOpacity : control.hovered ? Studio.Theme.hoverOpacity : 0
            radius: parent.radius
            Behavior on opacity { NumberAnimation { duration: Studio.Theme.stateDuration } }
        }
    }
    contentItem: Item {
        implicitHeight: content.implicitHeight
        implicitWidth: content.implicitWidth

        RowLayout {
            id: content

            anchors.verticalCenter: parent.verticalCenter
            spacing: Studio.Theme.space8
            width: Math.min(Math.ceil(implicitWidth), parent.width)
            x: control.leading ? 0 : (parent.width - width) / 2

            Icon {
                Layout.alignment: Qt.AlignVCenter
                Layout.preferredHeight: control.iconSize
                Layout.preferredWidth: control.iconSize
                color: control.foreground
                name: control.iconName
                size: control.iconSize
                visible: control.iconName.length > 0
            }
            Text {
                Layout.alignment: Qt.AlignVCenter
                Layout.fillWidth: true
                Layout.minimumWidth: 0
                color: control.foreground
                elide: Text.ElideRight
                font: control.font
                text: control.text
                textFormat: Text.PlainText
                verticalAlignment: Text.AlignVCenter
                visible: !control.iconOnly && control.text.length > 0
            }
        }
    }
}
