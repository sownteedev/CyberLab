import QtQuick
import QtQuick.Controls
import QtQuick.Layouts
import ".."
import ".." as Studio

RowLayout {
    id: header

    property string title: ""
    property string subtitle: ""
    property string iconName: ""
    property int titleSize: Studio.Theme.titleLarge

    spacing: Studio.Theme.space8
    Icon { visible: header.iconName.length > 0; name: header.iconName; color: Studio.Theme.primary; Layout.alignment: Qt.AlignVCenter }

    ColumnLayout {
        Layout.fillWidth: true
        spacing: Studio.Theme.space4
        Label {
            id: titleLabel
            Layout.fillWidth: true
            Layout.minimumWidth: 0
            text: header.title
            color: Studio.Theme.textOnSurface
            font.pixelSize: header.titleSize
            font.weight: Font.DemiBold
            elide: Text.ElideRight
            ToolTip.visible: titleHover.hovered && truncated
            ToolTip.delay: 600
            ToolTip.text: header.title
            HoverHandler { id: titleHover }
        }
        Label {
            Layout.fillWidth: true
            visible: header.subtitle.length > 0
            text: header.subtitle
            color: Studio.Theme.textOnSurfaceVariant
            font.pixelSize: Studio.Theme.bodySmall
            elide: Text.ElideRight
        }
    }
}
