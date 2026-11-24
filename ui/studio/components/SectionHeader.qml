import QtQuick
import QtQuick.Controls
import QtQuick.Layouts
import ".."
import ".." as Studio

RowLayout {
    id: header

    property string iconName: ""
    property string subtitle: ""
    property string title: ""
    property int titleSize: Studio.Theme.titleLarge

    spacing: Studio.Theme.space8

    Icon {
        Layout.alignment: Qt.AlignVCenter
        color: Studio.Theme.primary
        name: header.iconName
        visible: header.iconName.length > 0
    }
    ColumnLayout {
        Layout.fillWidth: true
        spacing: Studio.Theme.space4

        Label {
            id: titleLabel

            Layout.fillWidth: true
            Layout.minimumWidth: 0
            ToolTip.delay: 600
            ToolTip.text: header.title
            ToolTip.visible: titleHover.hovered && truncated
            color: Studio.Theme.textOnSurface
            elide: Text.ElideRight
            font.pixelSize: header.titleSize
            font.weight: Font.DemiBold
            text: header.title

            HoverHandler {
                id: titleHover
            }
        }
        Label {
            Layout.fillWidth: true
            color: Studio.Theme.textOnSurfaceVariant
            elide: Text.ElideRight
            font.pixelSize: Studio.Theme.bodySmall
            text: header.subtitle
            visible: header.subtitle.length > 0
        }
    }
}
