import QtQuick
import QtQuick.Controls.Basic
import QtQuick.Layouts
import ".."
import ".." as Studio

Button {
    id: control
    property bool danger: false
    property bool busy: false
    property bool selected: false
    property string iconName: ""
    property bool outlined: false
    property bool leading: false
    property int iconSize: Studio.Theme.iconSmall
    property bool iconOnly: false
    readonly property color foreground: !enabled ? Qt.alpha(Studio.Theme.textOnSurface, 0.38)
        : danger ? (flat ? Studio.Theme.error : Studio.Theme.textOnErrorContainer)
        : selected ? Studio.Theme.textOnPrimaryContainer
        : highlighted ? Studio.Theme.textOnPrimary : flat ? Studio.Theme.textOnSurface : Studio.Theme.textOnSecondaryContainer
    implicitHeight: Studio.Theme.controlHeight
    implicitWidth: Math.max(Studio.Theme.controlHeight, Math.ceil(implicitContentWidth) + leftPadding + rightPadding)
    leftPadding: Studio.Theme.space16
    rightPadding: Studio.Theme.space16
    topPadding: 0
    bottomPadding: 0
    font.family: Studio.Theme.fontFamily
    font.pixelSize: Studio.Theme.labelLarge
    font.weight: Font.DemiBold
    focusPolicy: Qt.StrongFocus
    hoverEnabled: true
    Accessible.name: text
    ToolTip.visible: iconOnly && (hovered || visualFocus)
    ToolTip.delay: 600
    ToolTip.text: text
    background: Rectangle {
        anchors.fill: parent
        anchors.margins: Studio.Theme.space4
        radius: Studio.Theme.shapeFull
        color: !control.enabled ? Studio.Theme.surfaceContainerHigh
            : control.danger ? (control.flat ? Studio.Theme.transparent : Studio.Theme.errorContainer)
            : control.selected ? Studio.Theme.primaryContainer
            : control.highlighted ? Studio.Theme.primary
            : control.flat ? (control.hovered ? Studio.Theme.surfaceContainerHigh : Studio.Theme.transparent)
                           : Studio.Theme.secondaryContainer
        border.color: control.visualFocus ? Studio.Theme.primary : Studio.Theme.outlineVariant
        border.width: control.visualFocus ? Studio.Theme.focusWidth : (control.outlined || (!control.flat && !control.highlighted) ? Studio.Theme.borderWidth : 0)
        Rectangle {
            anchors.fill: parent
            radius: parent.radius
            color: control.foreground
            opacity: control.down ? 0.16 : control.hovered ? 0.08 : 0
        }
    }
    contentItem: Item {
        implicitWidth: content.implicitWidth
        implicitHeight: content.implicitHeight
        RowLayout {
            id: content
            anchors.verticalCenter: parent.verticalCenter
            x: control.leading ? 0 : (parent.width - width) / 2
            width: Math.min(Math.ceil(implicitWidth), parent.width)
            spacing: Studio.Theme.space8
            Icon {
                visible: control.iconName.length > 0
                name: control.iconName
                color: control.foreground
                size: control.iconSize
                Layout.preferredWidth: control.iconSize
                Layout.preferredHeight: control.iconSize
                Layout.alignment: Qt.AlignVCenter
            }
            Text {
                visible: !control.iconOnly && control.text.length > 0
                Layout.minimumWidth: 0
                Layout.fillWidth: true
                Layout.alignment: Qt.AlignVCenter
                text: control.text
                textFormat: Text.PlainText
                font: control.font
                color: control.foreground
                verticalAlignment: Text.AlignVCenter
                elide: Text.ElideRight
            }
        }
    }
}
