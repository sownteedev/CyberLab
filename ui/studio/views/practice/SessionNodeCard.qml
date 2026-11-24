import QtQuick
import QtQuick.Controls.Basic
import QtQuick.Layouts
import "../../models/SessionFiles.js" as Files
import "../.."
import "../.." as Studio
import "../../models/Messages.js" as Messages

StudioSurface {
    id: card

    property bool busy: false
    property bool desktopSupported: false
    property bool filesExpanded: false
    readonly property var environment: (session.environments || []).find(entry => entry[0] === nodeId)
    readonly property var initialFiles: Files.treeRows(Files.filesForNode(session, [], nodeId))
    readonly property var networks: ((session.nodes || []).find(entry => entry[0] === nodeId) || ["", []])[1]
    readonly property string identity: session.id + ":" + nodeId
    required property string nodeId
    required property var session
    readonly property var terminal: (session.terminal_counts || []).find(entry => entry[0] === nodeId)
    signal terminalRequested(int slot)
    signal desktopRequested

    onIdentityChanged: filesExpanded = false

    color: Studio.Theme.surfaceContainer
    implicitHeight: contents.implicitHeight + Studio.Theme.space32

    ColumnLayout {
        id: contents

        anchors.left: parent.left
        anchors.margins: Studio.Theme.space16
        anchors.right: parent.right
        anchors.top: parent.top
        spacing: Studio.Theme.space12

        GridLayout {
            id: header

            Layout.fillWidth: true
            columns: width >= 640 ? 2 : 1
            columnSpacing: Studio.Theme.space16
            rowSpacing: Studio.Theme.space8

            RowLayout {
                Layout.fillWidth: true
                Layout.minimumWidth: 0
                spacing: Studio.Theme.space12

                Rectangle {
                    Layout.preferredWidth: 40
                    Layout.preferredHeight: 40
                    radius: Studio.Theme.shapeMedium
                    color: Studio.Theme.primaryContainer

                    Icon {
                        anchors.centerIn: parent
                        name: "terminal"
                        color: Studio.Theme.textOnPrimaryContainer
                        size: Studio.Theme.iconSmall
                    }
                }
                ColumnLayout {
                    Layout.fillWidth: true
                    Layout.minimumWidth: 0
                    spacing: Studio.Theme.space4

                    Label {
                        Layout.fillWidth: true
                        text: card.environment ? card.environment[2] + "@" + card.environment[1] : card.nodeId
                        textFormat: Text.PlainText
                        color: Studio.Theme.textOnSurface
                        font.pixelSize: Studio.Theme.titleMedium
                        font.weight: Font.DemiBold
                        wrapMode: Text.WrapAnywhere
                    }
                    Label {
                        Layout.fillWidth: true
                        visible: !!card.environment
                        text: card.environment ? card.environment[5] : ""
                        textFormat: Text.PlainText
                        color: Studio.Theme.textOnSurfaceVariant
                        font.pixelSize: Studio.Theme.bodySmall
                        wrapMode: Text.WrapAnywhere
                    }
                }
            }
            Flow {
                id: actions

                readonly property real naturalWidth: {
                    let total = 0;
                    for (const item of children) {
                        if (item.visible && item.implicitWidth > 0)
                            total += item.implicitWidth + spacing;
                    }
                    return Math.max(0, total - spacing);
                }

                Layout.fillWidth: header.columns === 1
                Layout.preferredWidth: header.columns === 2 ? Math.min(naturalWidth, header.width * 0.65) : -1
                Layout.preferredHeight: implicitHeight
                spacing: Studio.Theme.space4

                Repeater {
                    model: card.terminal ? card.terminal[1] : 1

                    StudioButton {
                        required property int index

                        objectName: "nodeTerminalButton-" + card.nodeId + "-" + index
                        enabled: card.session.state === "RUNNING" && !card.busy
                        highlighted: true
                        iconName: "terminal"
                        text: (card.terminal ? card.terminal[1] : 1) > 1 ? "Terminal " + (index + 1) : "Terminal"
                        onClicked: card.terminalRequested(index)
                    }
                }

                StudioButton {
                    objectName: "nodeDesktopButton"
                    visible: card.desktopSupported && (card.session.desktop_nodes || []).includes(card.nodeId)
                             && (card.session.gui_backends || {})[card.nodeId] === "xpra"
                    enabled: card.session.state === "RUNNING" && !card.busy
                    flat: true
                    outlined: true
                    iconName: "desktop_windows"
                    text: (card.session.prepared_gui_nodes || []).includes(card.nodeId) ? qsTr("Kết nối lại GUI") : qsTr("Bật GUI")
                    ToolTip.text: qsTr("Bật hiển thị cửa sổ, rồi chạy ứng dụng trong terminal.")
                    ToolTip.visible: hovered || visualFocus
                    Accessible.description: ToolTip.text
                    onClicked: card.desktopRequested()
                }
            }
        }
        Flow {
            id: networkFlow

            Layout.fillWidth: true
            Layout.preferredHeight: implicitHeight
            visible: card.networks.length > 0
            spacing: Studio.Theme.space8

            Repeater {
                model: card.networks

                Rectangle {
                    id: networkBadge

                    required property string modelData
                    readonly property var address: (card.session.addresses || []).find(entry => entry[0] === card.nodeId && entry[1] === modelData)
                    objectName: "nodeNetwork-" + card.nodeId + "-" + modelData
                    width: Math.min(networkFlow.width, networkContent.implicitWidth + Studio.Theme.space24)
                    height: networkContent.implicitHeight + Studio.Theme.space16
                    radius: Studio.Theme.shapeSmall
                    color: Studio.Theme.surfaceContainerHigh
                    Accessible.role: Accessible.StaticText
                    Accessible.name: modelData + ": " + networkAddress.text

                    RowLayout {
                        id: networkContent

                        anchors.centerIn: parent
                        width: parent.width - Studio.Theme.space24
                        spacing: Studio.Theme.space8

                        Label {
                            Layout.maximumWidth: networkContent.width * 0.45
                            text: networkBadge.modelData
                            textFormat: Text.PlainText
                            color: Studio.Theme.textOnSurfaceVariant
                            font.pixelSize: Studio.Theme.labelMedium
                            wrapMode: Text.WrapAnywhere
                        }
                        Label {
                            id: networkAddress

                            objectName: "networkAddress"
                            Layout.fillWidth: true
                            text: networkBadge.address ? networkBadge.address[2] : qsTr("IP tự động")
                            textFormat: Text.PlainText
                            color: networkBadge.address ? Studio.Theme.network : Studio.Theme.textOnSurfaceVariant
                            font.family: networkBadge.address ? Studio.Theme.monoFamily : Studio.Theme.fontFamily
                            font.pixelSize: Studio.Theme.bodySmall
                            wrapMode: Text.WrapAnywhere
                        }
                    }
                }
            }
        }
        Label {
            Layout.fillWidth: true
            objectName: "nodeGuiBackend"
            visible: card.session.state === "RUNNING" && !!(card.session.gui_backends || {})[card.nodeId]
            color: (card.session.gui_warnings || {})[card.nodeId] ? Studio.Theme.error : Studio.Theme.textOnSurfaceVariant
            font.pixelSize: Studio.Theme.bodySmall
            textFormat: Text.PlainText
            text: ((card.session.gui_states || {})[card.nodeId] === "disconnected" ? qsTr("Chưa kết nối GUI · ") : "")
                  + ((card.session.gui_backends || {})[card.nodeId] === "native-x11" ? qsTr("X11 trực tiếp") : qsTr("Xpra"))
                  + ((card.session.gui_warnings || {})[card.nodeId] ? " · " + Messages.text(card.session.gui_warnings[card.nodeId]) : "")
            Studio.ErrorNotifier { message: (card.session.gui_warnings || {})[card.nodeId] || "" }
            wrapMode: Text.WordWrap
        }
        Rectangle {
            Layout.fillWidth: true
            implicitHeight: Studio.Theme.borderWidth
            visible: filesToggle.visible
            color: Studio.Theme.outlineVariant
        }
        StudioButton {
            id: filesToggle

            Layout.fillWidth: true
            objectName: "nodeFilesToggle-" + card.nodeId
            visible: card.initialFiles.length > 0
            flat: true
            leading: true
            checkable: true
            checked: card.filesExpanded
            iconName: "folder"
            text: qsTr("File của bài") + " · " + card.initialFiles.filter(entry => !entry.isDirectory).length
            rightPadding: Studio.Theme.space32
            Accessible.description: checked ? qsTr("Thu gọn cây file") : qsTr("Mở cây file")
            onClicked: card.filesExpanded = checked

            Icon {
                anchors.right: parent.right
                anchors.rightMargin: Studio.Theme.space12
                anchors.verticalCenter: parent.verticalCenter
                name: "chevron_right"
                color: Studio.Theme.textOnSurfaceVariant
                size: Studio.Theme.iconSmall
                rotation: card.filesExpanded ? 90 : 0
            }
        }
        ColumnLayout {
            Layout.fillWidth: true
            objectName: "nodeInitialFiles-" + card.nodeId
            visible: card.initialFiles.length > 0 && card.filesExpanded
            spacing: 0

            Repeater {
                model: card.initialFiles

                TreeRow {
                    required property var modelData
                    Layout.fillWidth: true
                    objectName: "initialFile-" + card.nodeId + "-" + modelData.path
                    entry: modelData
                    showMetadata: false
                    canExport: false
                }
            }
        }
    }
}
