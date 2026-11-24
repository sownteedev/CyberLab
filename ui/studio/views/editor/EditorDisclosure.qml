import QtQuick
import QtQuick.Controls.Basic
import QtQuick.Layouts
import "../.." as Studio

ColumnLayout {
    id: section
    default property alias fields: fields.data
    property string title: ""
    property string iconName: "settings"
    property bool expanded: false
    Layout.fillWidth: true
    spacing: Studio.Theme.space8
    Studio.StudioButton {
        Layout.fillWidth: true
        objectName: section.objectName + "Toggle"
        flat: true
        leading: true
        checkable: true
        checked: section.expanded
        text: section.title
        iconName: section.iconName
        rightPadding: Studio.Theme.space32
        onClicked: section.expanded = checked
        Studio.Icon {
            anchors.right: parent.right
            anchors.rightMargin: Studio.Theme.space12
            anchors.verticalCenter: parent.verticalCenter
            size: Studio.Theme.iconSmall
            name: "chevron_right"
            color: Studio.Theme.textOnSurfaceVariant
            rotation: section.expanded ? 90 : 0
            Behavior on rotation { NumberAnimation { duration: Studio.Theme.stateDuration; easing.type: Easing.OutCubic } }
        }
    }
    ColumnLayout {
        id: fields
        Layout.fillWidth: true
        Layout.leftMargin: Studio.Theme.space12
        Layout.rightMargin: Studio.Theme.space12
        Layout.bottomMargin: Studio.Theme.space12
        spacing: Studio.Theme.space12
        visible: section.expanded
    }
    Rectangle {
        Layout.fillWidth: true
        implicitHeight: Studio.Theme.borderWidth
        color: Studio.Theme.outlineVariant
    }
}
