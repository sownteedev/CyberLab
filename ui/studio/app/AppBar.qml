import QtQuick
import QtQuick.Controls.Basic
import QtQuick.Layouts
import ".." as Studio

ToolBar {
    id: bar

    property bool activity: busy
    property bool busy: false
    property bool connected: false
    readonly property bool compact: width < Studio.Theme.compactBreakpoint
    property int currentIndex: 0
    property bool demo: false
    property bool windowMaximized: false
    property bool updateAvailable: false

    signal closeRequested
    signal minimizeRequested
    signal navigationRequested(int index)
    signal maximizeRequested
    signal moveRequested
    signal refreshRequested
    signal settingsRequested

    implicitHeight: Studio.Theme.appBarHeight + (compact ? Studio.Theme.controlHeight + Studio.Theme.space8 : 0)

    background: Rectangle {
        color: Studio.Theme.surface
    }

    MouseArea {
        id: dragArea

        anchors.fill: parent
        acceptedButtons: Qt.LeftButton
        objectName: "topbarDragArea"

        onPressed: event => {
            const navigationPoint = navigation.mapFromItem(dragArea, event.x, event.y);
            const actionsPoint = headerActions.mapFromItem(dragArea, event.x, event.y);
            if (navigation.contains(navigationPoint) || headerActions.contains(actionsPoint)) {
                event.accepted = false;
                return;
            }
            bar.moveRequested();
        }
    }
    GridLayout {
        id: headerLayout
        anchors.bottomMargin: Studio.Theme.appBarVerticalInset
        anchors.fill: parent
        anchors.leftMargin: bar.compact ? Studio.Theme.space8 : Studio.Theme.appBarInset
        anchors.rightMargin: bar.compact ? Studio.Theme.space8 : Studio.Theme.appBarInset
        anchors.topMargin: Studio.Theme.appBarVerticalInset
        columns: 4
        columnSpacing: bar.compact ? Studio.Theme.space8 : Studio.Theme.contentGap
        rowSpacing: Studio.Theme.space8

        RowLayout {
            Layout.row: 0
            Layout.column: 0
            Layout.columnSpan: bar.compact ? 3 : 1
            Layout.fillWidth: bar.compact
            Layout.minimumWidth: Studio.Theme.controlHeight - Studio.Theme.space8
            Layout.preferredWidth: bar.width >= 1000 || bar.compact ? 200 : Studio.Theme.controlHeight - Studio.Theme.space8
            spacing: Studio.Theme.space8

            Image {
                Layout.preferredWidth: Studio.Theme.controlHeight - Studio.Theme.space8
                Layout.preferredHeight: Studio.Theme.controlHeight - Studio.Theme.space8
                Accessible.name: "CyberLab Studio"
                Accessible.role: Accessible.Graphic
                objectName: "cyberlabBrand"
                source: "../assets/branding/cyberlab-studio.svg"
                sourceSize: Qt.size(96, 96)
                fillMode: Image.PreserveAspectFit
            }
            ColumnLayout {
                Layout.fillWidth: true
                Layout.minimumWidth: 0
                spacing: 2
                visible: bar.width >= 1000 || (bar.compact && bar.width >= 520)

                Label {
                    Layout.fillWidth: true
                    color: Studio.Theme.textOnSurface
                    elide: Text.ElideRight
                    font.family: Studio.Theme.fontFamily
                    font.pixelSize: Studio.Theme.titleMedium
                    font.weight: Font.DemiBold
                    text: "CyberLab"
                }
                Label {
                    Layout.fillWidth: true
                    color: Studio.Theme.textOnSurfaceVariant
                    elide: Text.ElideRight
                    font.family: Studio.Theme.fontFamily
                    font.pixelSize: Studio.Theme.bodySmall
                    objectName: "cyberlabDescription"
                    text: qsTr("Không gian thực hành")
                }
            }
        }
        Studio.StudioNavigation {
            id: navigation
            Layout.row: bar.compact ? 1 : 0
            Layout.column: bar.compact ? 0 : 1
            Layout.columnSpan: bar.compact ? 4 : 1
            Layout.alignment: Qt.AlignHCenter
            Layout.preferredWidth: Math.min(implicitWidth, headerLayout.width)
            currentIndex: bar.currentIndex
            enabled: !bar.busy

            onIndexRequested: index => bar.navigationRequested(index)
        }
        Item {
            objectName: "topbarSpacer"
            Layout.row: 0
            Layout.column: 2
            Layout.fillWidth: true
            visible: !bar.compact
        }
        RowLayout {
            id: headerActions
            Layout.row: 0
            Layout.column: 3
            spacing: bar.compact ? Studio.Theme.space4 : Studio.Theme.space8

            Studio.StatusBadge {
                visible: bar.width >= 360
                Accessible.description: "System D-Bus"
                bgColor: bar.connected ? Studio.Theme.successContainer : Studio.Theme.errorContainer
                compact: bar.width < 1100
                dotColor: bar.connected ? Studio.Theme.success : Studio.Theme.error
                iconName: bar.connected ? "check_circle" : "cloud_off"
                objectName: "connectionStatus"
                text: bar.connected ? (bar.demo ? "Demo" : "Đã kết nối") : "Mất kết nối"
                textColor: bar.connected ? Studio.Theme.textOnSuccessContainer : Studio.Theme.textOnErrorContainer
            }
            Studio.StudioIconButton {
                description: bar.updateAvailable ? qsTr("Cài đặt · Có bản cập nhật") : qsTr("Cài đặt")
                iconName: "settings"
                objectName: "openSettingsButton"

                onClicked: bar.settingsRequested()
                Rectangle {
                    anchors.right: parent.right
                    anchors.top: parent.top
                    anchors.margins: 5
                    width: 9; height: 9; radius: 5
                    color: Studio.Theme.primary
                    border.color: Studio.Theme.surface
                    border.width: 2
                    visible: bar.updateAvailable
                    Accessible.ignored: true
                }
            }
            Studio.StudioIconButton {
                description: "Làm mới"
                enabled: !bar.busy
                iconName: "refresh"
                objectName: "refreshButton"

                onClicked: bar.refreshRequested()
            }
            Studio.WindowControls {
                maximized: bar.windowMaximized

                onCloseRequested: bar.closeRequested()
                onMinimizeRequested: bar.minimizeRequested()
                onMaximizeRequested: bar.maximizeRequested()
            }
        }
    }
    Studio.LoadingState {
        anchors.bottom: parent.bottom
        anchors.left: parent.left
        anchors.right: parent.right
        busy: bar.activity
        height: implicitHeight
        objectName: "headerActivity"
    }
}
