import QtQuick
import QtQuick.Controls.Basic
import QtQuick.Layouts
import "../.." as Studio

ColumnLayout {
    id: field
    default property alias controls: controls.data
    property string label: ""
    Layout.fillWidth: true
    Layout.minimumWidth: 0
    Layout.preferredWidth: 240
    spacing: Studio.Theme.space8
    Label {
        Layout.fillWidth: true
        text: field.label
        textFormat: Text.PlainText
        color: Studio.Theme.textOnSurfaceVariant
        font.pixelSize: Studio.Theme.bodySmall
        wrapMode: Text.WordWrap
    }
    ColumnLayout {
        id: controls
        Layout.fillWidth: true
        spacing: Studio.Theme.space8
    }
}
