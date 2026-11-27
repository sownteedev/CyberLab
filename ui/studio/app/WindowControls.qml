import QtQuick
import QtQuick.Layouts
import ".." as Studio

Rectangle {
    id: controls

    required property bool maximized

    signal closeRequested
    signal minimizeRequested
    signal maximizeRequested

    border.color: Studio.Theme.outlineVariant
    border.width: Studio.Theme.borderWidth
    color: Studio.Theme.surfaceContainerLow
    implicitHeight: Studio.Theme.controlHeight
    implicitWidth: buttons.implicitWidth
    objectName: "windowControls"
    radius: Studio.Theme.shapeFull

    RowLayout {
        id: buttons

        anchors.fill: parent
        spacing: Studio.Theme.space4

        Studio.StudioIconButton {
            Layout.preferredHeight: Studio.Theme.controlHeight
            Layout.preferredWidth: Studio.Theme.controlHeight
            description: "Thu nhỏ cửa sổ"
            iconName: "remove"
            iconSize: Studio.Theme.iconSmall
            objectName: "minimizeWindowButton"

            onClicked: controls.minimizeRequested()
        }
        Studio.StudioIconButton {
            Layout.preferredHeight: Studio.Theme.controlHeight
            Layout.preferredWidth: Studio.Theme.controlHeight
            description: controls.maximized ? "Khôi phục cửa sổ" : "Phóng to cửa sổ"
            iconName: controls.maximized ? "filter_none" : "crop_square"
            iconSize: Studio.Theme.iconSmall
            objectName: "maximizeWindowButton"

            onClicked: controls.maximizeRequested()
        }
        Studio.StudioIconButton {
            Layout.preferredHeight: Studio.Theme.controlHeight
            Layout.preferredWidth: Studio.Theme.controlHeight
            danger: hovered || visualFocus || down
            description: "Đóng cửa sổ"
            iconName: "close"
            iconSize: Studio.Theme.iconSmall
            objectName: "closeWindowButton"

            onClicked: controls.closeRequested()
        }
    }
}
