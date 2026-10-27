import QtQuick
import QtQuick.Controls.Material
import QtQuick.Layouts
import "../.."
import "../.." as Studio

ColumnLayout {
    id: sessionView
    readonly property bool compact: width < 800
    readonly property bool compactActions: width < 1000
    property int compactPane: 0
    property var session: null
    property var lab: null
    property var sessions: []
    property var sessionImports: []
    property var workspaces: ({})
    property var workspaceErrors: ({})
    property bool workspaceSupported: false
    property bool persistenceSupported: false
    property bool discardSupported: false
    property bool checkworkSupported: false
    property bool quizSupported: false
    property bool submissionSupported: false
    property string manual: ""
    property bool busy: false
    property bool moreActions: false
    readonly property string sessionState: session ? session.state : ""
    signal backRequested()
    signal reportsRequested(var selected)
    signal quizRequested(var selected)
    signal submissionRequested(var selected, var caller)
    signal sessionRequested(var selected)
    signal resetRequested(string sessionId)
    signal stopRequested(string sessionId)
    signal saveRequested(string sessionId)
    signal suspendRequested(string sessionId)
    signal resumeRequested(var selected)
    signal discardRequested(string sessionId)
    signal terminalRequested(var session, string node, int slot)
    signal allTerminalsRequested(var session)
    signal importFileRequested(string sessionId, string node)
    signal refreshFilesRequested(string node)
    signal importFolderRequested(string sessionId, string node)
    signal exportRequested(string sessionId, string node, string path, bool directory)
    spacing: Studio.Theme.space16

    EmptyState {
        Layout.fillWidth: true
        Layout.fillHeight: true
        visible: !sessionView.session && sessionView.sessions.length === 0
        title: "Chưa có phiên thực hành"
        description: "Mở bài từ thư viện để bắt đầu."
        actionText: "Về thư viện"
        onActionRequested: sessionView.backRequested()
    }
    StudioComboBox {
        implicitHeight: Studio.Theme.controlHeight
        Layout.fillWidth: true
        visible: sessionView.sessions.length > 1 || (!sessionView.session && sessionView.sessions.length > 0)
        model: sessionView.sessions.map(entry => entry.lab_id + " · " + entry.id.substring(0, 8) + " · " + entry.state)
        currentIndex: sessionView.session ? sessionView.sessions.findIndex(entry => entry.id === sessionView.session.id) : -1
        displayText: currentIndex < 0 ? "Chọn phiên thực hành" : currentText
        onActivated: sessionView.sessionRequested(sessionView.sessions[currentIndex])
    }
    RowLayout {
        visible: !!sessionView.session
        Layout.fillWidth: true
        spacing: Studio.Theme.space16
        SectionHeader {
            Layout.fillWidth: true
            title: sessionView.session ? sessionView.session.lab_name || sessionView.session.lab_id : ""
            subtitle: sessionView.session ? "Session " + sessionView.session.id.substring(0, 8) : ""
        }
        StatusBadge {
            text: ({RUNNING: "Đang chạy", SUSPENDED: "Đã tạm dừng", STOPPED: "Đã dừng", FAILED: "Lỗi"})[sessionView.sessionState] || sessionView.sessionState
            iconName: sessionView.sessionState === "RUNNING" ? "terminal" : sessionView.sessionState === "FAILED" ? "error"
                      : sessionView.session && sessionView.session.saved ? "bookmark" : "stop"
            bgColor: sessionView.sessionState === "RUNNING" ? Studio.Theme.successContainer : sessionView.sessionState === "FAILED" ? Studio.Theme.errorContainer : Studio.Theme.surfaceVariant
            textColor: sessionView.sessionState === "RUNNING" ? Studio.Theme.textOnSuccessContainer : sessionView.sessionState === "FAILED" ? Studio.Theme.textOnErrorContainer : Studio.Theme.textOnSurface
            dotColor: textColor
        }
    }
    Flow {
        visible: !!sessionView.session
        Layout.fillWidth: true
        Layout.preferredHeight: implicitHeight
        spacing: Studio.Theme.space8
        StudioButton {
            id: submitButton
            objectName: "practiceSubmitButton"
            iconName: "upload"
            text: "Nộp và kết thúc"
            highlighted: true
            visible: sessionView.moreActions && sessionView.submissionSupported && sessionView.sessionState === "RUNNING"
            enabled: !sessionView.busy
            onClicked: sessionView.submissionRequested(sessionView.session, submitButton)
        }
        StudioButton {
            objectName: "practiceReportsButton"
            iconName: "check_circle"
            text: sessionView.compactActions ? "Kết quả" : "Kết quả bài làm"
            visible: sessionView.checkworkSupported
            enabled: !!sessionView.session && !sessionView.busy
            onClicked: sessionView.reportsRequested(sessionView.session)
        }
        StudioButton {
            objectName: "practiceQuizButton"
            iconName: "help"
            text: "Câu hỏi"
            iconOnly: sessionView.compactActions
            visible: sessionView.quizSupported && sessionView.session && sessionView.session.quiz
                && sessionView.session.quiz !== "[]"
            enabled: !!sessionView.session && !sessionView.busy
            onClicked: sessionView.quizRequested(sessionView.session)
        }
        StudioButton {
            iconName: "play_arrow"; text: "Tiếp tục bài làm"
            highlighted: true
            visible: !!sessionView.session && !!sessionView.session.saved
                && (sessionView.session.state === "SUSPENDED" || sessionView.session.state === "STOPPED")
            enabled: sessionView.persistenceSupported && !sessionView.busy
            onClicked: sessionView.resumeRequested(sessionView.session)
        }
        StudioButton {
            iconName: "save"; text: "Lưu tiến độ"
            iconOnly: sessionView.compactActions
            visible: sessionView.persistenceSupported
            enabled: !!sessionView.session && sessionView.session.state === "RUNNING" && !sessionView.busy
            onClicked: sessionView.saveRequested(sessionView.session.id)
        }
        StudioButton {
            iconName: "pause"; text: "Tạm dừng"
            visible: sessionView.persistenceSupported
            enabled: !!sessionView.session && sessionView.session.state === "RUNNING" && !sessionView.busy
            onClicked: sessionView.suspendRequested(sessionView.session.id)
        }
        StudioButton {
            iconName: "restart_alt"; text: "Reset"
            visible: sessionView.moreActions
            enabled: !!sessionView.session && !sessionView.busy
            onClicked: sessionView.resetRequested(sessionView.session.id)
        }
        StudioButton {
            iconName: "stop"; text: "Dừng bài"
            danger: true
            enabled: !!sessionView.session && sessionView.session.state !== "STOPPED" && !sessionView.busy
            onClicked: sessionView.stopRequested(sessionView.session.id)
        }
        StudioButton {
            objectName: "discardCheckpointButton"
            iconName: "delete"; text: "Xóa bản lưu"
            danger: true
            visible: sessionView.moreActions && !!sessionView.session && !!sessionView.session.saved
            enabled: sessionView.discardSupported && !sessionView.busy
            onClicked: sessionView.discardRequested(sessionView.session.id)
        }
        StudioButton {
            objectName: "practiceMoreActions"
            text: sessionView.moreActions ? "Thu gọn" : "Thao tác khác"
            iconName: "more_horiz"
            iconOnly: sessionView.compactActions
            selected: sessionView.moreActions
            flat: true
            onClicked: sessionView.moreActions = !sessionView.moreActions
        }
    }
    InlineError {
        Layout.fillWidth: true
        message: sessionView.session ? sessionView.session.error || "" : ""
    }
    StudioTabs {
        objectName: "practicePaneTabs"
        Layout.fillWidth: true
        visible: !!sessionView.session && sessionView.compact
        entries: [{label: "Hướng dẫn", icon: "description"}, {label: "Máy và file", icon: "terminal"}]
        currentIndex: sessionView.compactPane
        itemPrefix: "practicePane-"
        onSelected: index => sessionView.compactPane = index
    }
    SplitView {
        id: workspace
        objectName: "practiceSplit"
        Layout.fillWidth: true
        Layout.fillHeight: true
        visible: !!sessionView.session
        orientation: Qt.Horizontal
        handle: StudioSplitHandle {}
        StudioSurface {
            objectName: "practiceDocumentPane"
            visible: !sessionView.compact || sessionView.compactPane === 0
            SplitView.fillWidth: true
            SplitView.minimumWidth: sessionView.compact ? 0 : 360
            radius: Studio.Theme.shapeExtraLarge
            color: Studio.Theme.surfaceContainerLow
            ColumnLayout {
                anchors.fill: parent
                anchors.margins: Studio.Theme.space16
                spacing: Studio.Theme.space16
                SectionHeader { title: "Hướng dẫn"; Layout.fillWidth: true }
                MarkdownView { Layout.fillWidth: true; Layout.fillHeight: true; markdown: sessionView.manual }
            }
        }
        StudioSurface {
            objectName: "practiceMachinesPane"
            visible: !sessionView.compact || sessionView.compactPane === 1
            SplitView.fillWidth: sessionView.compact
            SplitView.preferredWidth: workspace.width * 0.43
            SplitView.minimumWidth: sessionView.compact ? 0 : 320
            SplitView.maximumWidth: sessionView.compact ? workspace.width : workspace.width - 360 - Studio.Theme.space16
            radius: Studio.Theme.shapeExtraLarge
            color: Studio.Theme.surfaceContainerLow
            ScrollView {
                id: machines
                anchors.fill: parent
                anchors.margins: Studio.Theme.space16
                contentWidth: availableWidth
                clip: true
                ColumnLayout {
                    width: machines.availableWidth
                    spacing: Studio.Theme.space16
                    SectionHeader { title: "Máy và file"; Layout.fillWidth: true }
                    Repeater {
                        model: sessionView.session ? sessionView.session.environments || [] : []
                        SessionNodeCard {
                            required property var modelData
                            Layout.fillWidth: true
                            session: sessionView.session
                            nodeId: modelData[0]
                            imports: sessionView.sessionImports
                            busy: sessionView.busy
                            workspaceSupported: sessionView.workspaceSupported
                            liveWorkspace: sessionView.workspaces[nodeId] || null
                            workspaceError: sessionView.workspaceErrors[nodeId] || ""
                            onTerminalRequested: slot => sessionView.terminalRequested(sessionView.session, nodeId, slot)
                            onRefreshFilesRequested: sessionView.refreshFilesRequested(nodeId)
                            onImportFolderRequested: sessionView.importFolderRequested(sessionView.session.id, nodeId)
                            onExportRequested: (path, directory) => sessionView.exportRequested(sessionView.session.id, nodeId, path, directory)
                        }
                    }
                    SectionHeader { title: "Nhập file"; Layout.fillWidth: true }
                    StudioComboBox {
                        implicitHeight: Studio.Theme.controlHeight
                        id: importNode
                        Layout.fillWidth: true
                        model: sessionView.session ? (sessionView.session.environments || []).map(entry => entry[0]) : []
                        Accessible.name: "Máy nhận file"
                    }
                    StudioButton {
                        Layout.fillWidth: true
                        iconName: "upload"; text: "Chọn file từ VM"
                        enabled: !!sessionView.session && sessionView.session.state === "RUNNING" && importNode.currentIndex >= 0 && !sessionView.busy
                        onClicked: sessionView.importFileRequested(sessionView.session.id, importNode.currentText)
                    }
                    Repeater {
                        model: sessionView.sessionImports
                        Label {
                            required property var modelData
                            Layout.fillWidth: true
                            text: modelData.node + " · " + modelData.state + "\n" + (modelData.path || "")
                                + (modelData.error ? "\n" + modelData.error : "")
                            textFormat: Text.PlainText
                            color: modelData.state === "COMPLETE" ? Studio.Theme.textOnSurfaceVariant : Studio.Theme.error
                            font.pixelSize: Studio.Theme.bodySmall
                            wrapMode: Text.WrapAnywhere
                        }
                    }
                }
            }
        }
    }
}
