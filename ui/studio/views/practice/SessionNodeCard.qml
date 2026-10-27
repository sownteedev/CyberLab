import QtQuick
import QtQuick.Controls.Basic
import QtQuick.Layouts
import "../../models/SessionFiles.js" as Files
import "../.."
import "../.." as Studio

StudioSurface {
    id: card
    required property var session
    required property string nodeId
    property var imports: []
    property bool busy: false
    property bool workspaceSupported: false
    property var liveWorkspace: null
    property string workspaceError: ""
    readonly property var environment: (session.environments || []).find(entry => entry[0] === nodeId)
    readonly property var terminal: (session.terminal_counts || []).find(entry => entry[0] === nodeId)
    readonly property var files: Files.treeRows(liveWorkspace ? Files.liveFiles(liveWorkspace) : Files.filesForNode(session, imports, nodeId))
    signal terminalRequested(int slot)
    signal refreshFilesRequested()
    signal importFolderRequested()
    signal exportRequested(string path, bool directory)
    implicitHeight: contents.implicitHeight + Studio.Theme.space32
    color: Studio.Theme.surfaceContainerHigh
    ColumnLayout {
        id: contents
        anchors.left: parent.left
        anchors.right: parent.right
        anchors.top: parent.top
        anchors.margins: Studio.Theme.space16
        spacing: Studio.Theme.space16
        SectionHeader {
            Layout.fillWidth: true
            iconName: "terminal"
            titleSize: Studio.Theme.titleMedium
            title: card.environment ? card.environment[2] + "@" + card.environment[1] : card.nodeId
            subtitle: card.nodeId + " · " + (card.terminal ? card.terminal[1] : 1) + " terminal"
        }
        Label {
            Layout.fillWidth: true
            text: "Home: " + (card.environment ? card.environment[5] : "—")
            textFormat: Text.PlainText
            color: Studio.Theme.textOnSurfaceVariant
            font.pixelSize: Studio.Theme.bodySmall
            wrapMode: Text.WrapAnywhere
        }
        Repeater {
            model: (card.session.addresses || []).filter(entry => entry[0] === card.nodeId)
            Label {
                required property var modelData
                Layout.fillWidth: true
                text: modelData[1] + " · " + modelData[2]
                color: Studio.Theme.network
                font.pixelSize: Studio.Theme.bodySmall
                wrapMode: Text.WrapAnywhere
            }
        }
        Label {
            Layout.fillWidth: true
            text: "Mạng: " + ((card.session.nodes || []).find(entry => entry[0] === card.nodeId) || ["", []])[1].join(", ")
            color: Studio.Theme.textOnSurfaceVariant
            font.pixelSize: Studio.Theme.bodySmall
            wrapMode: Text.WrapAnywhere
        }
        Flow {
            Layout.fillWidth: true
            Layout.preferredHeight: implicitHeight
            spacing: Studio.Theme.space8
            Repeater {
                model: card.terminal ? card.terminal[1] : 1
                StudioButton {
                    required property int index
                    iconName: "terminal"
                    text: "Terminal " + (index + 1)
                    enabled: card.session.state === "RUNNING" && !card.busy
                    onClicked: card.terminalRequested(index)
                }
            }
        }
        Label {
            Layout.fillWidth: true
            text: Files.workspacePath(card.session, card.nodeId) + "/"
            textFormat: Text.PlainText
                color: Studio.Theme.network
            font.family: Studio.Theme.monoFamily
            font.pixelSize: Studio.Theme.bodySmall
            wrapMode: Text.WrapAnywhere
        }
        Repeater {
            model: card.files
            TreeRow {
                required property var modelData
                Layout.fillWidth: true
                entry: modelData
                canExport: card.session.state === "RUNNING" && !card.busy && card.workspaceError.length === 0
                onExportRequested: (path, directory) => card.exportRequested(path, directory)
            }
        }
        Label {
            Layout.fillWidth: true
            visible: card.files.length === 0
            text: card.liveWorkspace ? "Vùng làm việc đang trống." : "Chưa ghi nhận file ban đầu hoặc file nhập."
            color: Studio.Theme.textOnSurfaceVariant
            font.pixelSize: Studio.Theme.bodySmall
            wrapMode: Text.WordWrap
        }
        Label {
            Layout.fillWidth: true
            text: card.workspaceError || (card.liveWorkspace ? "File thực tế trong container. Nhấn Làm mới sau khi sửa bằng terminal."
                  : "Danh sách từ cấu hình và lịch sử nhập, chưa đọc filesystem trực tiếp.")
            color: Studio.Theme.textOnSurfaceVariant
            font.pixelSize: Studio.Theme.bodySmall
            wrapMode: Text.WordWrap
        }
        Flow {
            visible: card.workspaceSupported
            Layout.fillWidth: true
            Layout.preferredHeight: implicitHeight
            spacing: Studio.Theme.space8
            StudioButton {
                iconName: "refresh"; text: "Làm mới file"
                enabled: card.session.state === "RUNNING" && !card.busy
                onClicked: card.refreshFilesRequested()
            }
            StudioButton {
                iconName: "upload"; text: "Nhập thư mục"
                enabled: card.session.state === "RUNNING" && !card.busy
                onClicked: card.importFolderRequested()
            }
            StudioButton {
                iconName: "download"; text: "Xuất tất cả"
                enabled: card.session.state === "RUNNING" && !card.busy
                onClicked: card.exportRequested(".", true)
            }
        }
    }
}
