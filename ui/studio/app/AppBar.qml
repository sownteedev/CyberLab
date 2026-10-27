import QtQuick
import QtQuick.Controls.Basic
import QtQuick.Layouts
import ".."
import ".." as Studio

ToolBar {
    id: bar
    property string heading: ""
    property string subtitle: ""
    property bool connected: false
    property bool demo: false
    property bool busy: false
    property bool activity: busy
    property bool showCreate: true
    signal createRequested()
    signal refreshRequested()
    signal settingsRequested()
    implicitHeight: Studio.Theme.appBarHeight
    background: Rectangle { color: Studio.Theme.surface }
    RowLayout {
        anchors.fill: parent
        anchors.leftMargin: Studio.Theme.appBarInset
        anchors.rightMargin: Studio.Theme.appBarInset
        anchors.topMargin: Studio.Theme.appBarVerticalInset
        anchors.bottomMargin: Studio.Theme.appBarVerticalInset
        spacing: Studio.Theme.contentGap
        ColumnLayout {
            Layout.fillWidth: true
            Layout.minimumWidth: 0
            spacing: 2
            Label {
                Layout.fillWidth: true
                text: bar.heading
                color: Studio.Theme.textOnSurface
                font.pixelSize: Studio.Theme.titleLarge
                font.weight: Font.DemiBold
                elide: Text.ElideRight
            }
            Label {
                Layout.fillWidth: true
                text: bar.subtitle
                visible: bar.subtitle.length > 0 && bar.width >= Studio.Theme.compactBreakpoint
                color: Studio.Theme.textOnSurfaceVariant
                font.pixelSize: Studio.Theme.bodySmall
                elide: Text.ElideRight
            }
        }
        StatusBadge {
            text: bar.connected ? (bar.demo ? "Demo" : "Đã kết nối") : "Mất kết nối"
            iconName: bar.connected ? "check_circle" : "cloud_off"
            Accessible.description: "System D-Bus"
            bgColor: bar.connected ? Studio.Theme.successContainer : Studio.Theme.errorContainer
            dotColor: bar.connected ? Studio.Theme.success : Studio.Theme.error
            textColor: bar.connected ? Studio.Theme.textOnSuccessContainer : Studio.Theme.textOnErrorContainer
        }
        StudioIconButton {
            objectName: "openSettingsButton"
            iconName: "settings"
            description: "Cài đặt"
            onClicked: bar.settingsRequested()
        }
        StudioIconButton {
            iconName: "refresh"
            description: "Làm mới"
            enabled: !bar.busy
            onClicked: bar.refreshRequested()
        }
        StudioButton {
            visible: bar.showCreate
            text: "Tạo bài"
            iconName: "add"
            highlighted: true
            enabled: !bar.busy
            onClicked: bar.createRequested()
        }
    }
    LoadingState {
        objectName: "headerActivity"
        anchors.left: parent.left
        anchors.right: parent.right
        anchors.bottom: parent.bottom
        height: implicitHeight
        busy: bar.activity
    }
}
