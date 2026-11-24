import QtQuick
import QtQuick.Controls.Material
import QtQuick.Layouts
import "../.."
import "../.." as Studio

ColumnLayout {
    id: sessionView

    property bool busy: false
    property bool starting: false
    property bool checkworkSupported: false
    readonly property bool compact: width < 800
    property int compactPane: 0
    property bool discardSupported: false
    property var lab: null
    property string manual: ""
    property bool persistenceSupported: false
    property bool quizSupported: false
    property var session: null
    readonly property string sessionState: session ? session.state : ""
    property var sessions: []
    property bool submissionSupported: false

    signal allTerminalsRequested(var session)
    signal backRequested
    signal discardRequested(string sessionId)
    signal quizRequested(var selected)
    signal reportsRequested(var selected)
    signal resetRequested(string sessionId)
    signal resumeRequested(var selected)
    signal saveRequested(string sessionId)
    signal sessionRequested(var selected)
    signal stopRequested(string sessionId)
    signal submissionRequested(var selected, var caller)
    signal suspendRequested(string sessionId)
    signal terminalRequested(var session, string node, int slot)
    signal desktopRequested(var session, string node)
    property bool desktopSupported: false

    function stateText(value) {
        return ({PREPARING: "Đang khởi động", RESETTING: "Đang khởi động", STOPPING: "Đang dừng",
            RUNNING: "Đang chạy", SUSPENDED: "Đã tạm dừng", STOPPED: "Đã dừng", FAILED: "Lỗi"})[value] || value;
    }

    spacing: Studio.Theme.space16

    onVisibleChanged: if (!visible) actionsMenu.dismiss()

    EmptyState {
        Layout.fillHeight: true
        Layout.fillWidth: true
        actionText: "Về thư viện"
        title: "Chưa có phiên thực hành"
        visible: !sessionView.session && sessionView.sessions.length === 0

        onActionRequested: sessionView.backRequested()
    }
    StudioComboBox {
        Layout.fillWidth: true
        currentIndex: sessionView.session ? sessionView.sessions.findIndex(entry => entry.id === sessionView.session.id) : -1
        displayText: currentIndex < 0 ? "Chọn phiên thực hành" : currentText
        implicitHeight: Studio.Theme.controlHeight
        model: sessionView.sessions.map(entry => entry.lab_id + " · " + entry.id.substring(0, 8) + " · " + sessionView.stateText(entry.state))
        visible: sessionView.sessions.length > 1 || (!sessionView.session && sessionView.sessions.length > 0)

        onActivated: sessionView.sessionRequested(sessionView.sessions[currentIndex])
    }
    RowLayout {
        Layout.fillWidth: true
        spacing: Studio.Theme.space16
        visible: !!sessionView.session

        SectionHeader {
            Layout.fillWidth: true
            Layout.minimumWidth: 0
            subtitle: sessionView.session ? "Session " + sessionView.session.id.substring(0, 8) : ""
            title: sessionView.session ? sessionView.session.lab_name || sessionView.session.lab_id : ""
        }
        StudioButton {
            enabled: !!sessionView.session && !sessionView.busy
            flat: true
            iconName: "check_circle"
            iconOnly: sessionView.compact
            objectName: "practiceReportsButton"
            text: qsTr("Kết quả bài làm")
            visible: sessionView.checkworkSupported

            onClicked: sessionView.reportsRequested(sessionView.session)
        }
        StatusBadge {
            bgColor: sessionView.sessionState === "RUNNING" ? Studio.Theme.successContainer : sessionView.sessionState === "FAILED" ? Studio.Theme.errorContainer : Studio.Theme.surfaceVariant
            dotColor: textColor
            iconName: sessionView.sessionState === "RUNNING" ? "terminal" : sessionView.sessionState === "FAILED" ? "error" : sessionView.session && sessionView.session.saved ? "bookmark" : "stop"
            text: sessionView.stateText(sessionView.sessionState)
            textColor: sessionView.sessionState === "RUNNING" ? Studio.Theme.textOnSuccessContainer : sessionView.sessionState === "FAILED" ? Studio.Theme.textOnErrorContainer : Studio.Theme.textOnSurface
        }
    }
    Flow {
        objectName: "practiceActionBar"
        Layout.fillWidth: true
        Layout.preferredHeight: implicitHeight
        spacing: Studio.Theme.space8
        visible: !!sessionView.session

        StudioButton {
            id: submitButton

            enabled: !sessionView.busy
            highlighted: true
            iconName: "upload"
            objectName: "practiceSubmitButton"
            text: "Nộp và kết thúc"
            visible: sessionView.submissionSupported && sessionView.sessionState === "RUNNING"

            onClicked: sessionView.submissionRequested(sessionView.session, submitButton)
        }
        StudioButton {
            enabled: sessionView.persistenceSupported && !sessionView.busy && !sessionView.starting
            highlighted: true
            iconName: "play_arrow"
            objectName: "practiceResumeButton"
            text: "Tiếp tục bài làm"
            visible: !!sessionView.session && !!sessionView.session.saved && (sessionView.session.state === "SUSPENDED" || sessionView.session.state === "STOPPED")

            onClicked: sessionView.resumeRequested(sessionView.session)
        }
        StudioButton {
            enabled: !!sessionView.session && sessionView.session.state === "RUNNING" && !sessionView.busy
            Accessible.description: qsTr("Lưu tiến độ và tạm dừng phiên thực hành")
            ToolTip.text: qsTr("Lưu tiến độ và tạm dừng")
            ToolTip.visible: hovered || visualFocus
            iconName: "pause"
            objectName: "practiceSuspendButton"
            text: "Tạm dừng"
            visible: sessionView.persistenceSupported && sessionView.sessionState === "RUNNING"

            onClicked: sessionView.suspendRequested(sessionView.session.id)
        }
        StudioIconButton {
            id: moreButton

            description: qsTr("Thao tác khác")
            enabled: !!sessionView.session && !sessionView.busy
            iconName: "more_horiz"
            objectName: "practiceMoreActions"
            selected: actionsMenu.opened

            onClicked: actionsMenu.open()
        }
    }
    SessionActionsMenu {
        id: actionsMenu

        parent: moreButton
        busy: sessionView.busy
        starting: sessionView.starting
        discardSupported: sessionView.discardSupported
        persistenceSupported: sessionView.persistenceSupported
        quizSupported: sessionView.quizSupported
        session: sessionView.session
        width: Math.min(360, sessionView.width)
        x: moreButton.width - width
        y: moreButton.height + Studio.Theme.space4

        onActionRequested: (action, identifier) => {
            if (action === "save") sessionView.saveRequested(identifier);
            else if (action === "reset") sessionView.resetRequested(identifier);
            else if (action === "stop") sessionView.stopRequested(identifier);
            else if (action === "discard") sessionView.discardRequested(identifier);
            else if (action === "quiz") sessionView.quizRequested(sessionView.session);
        }
    }
    InlineError {
        Layout.fillWidth: true
        message: sessionView.session ? sessionView.session.error || "" : ""
    }
    StudioTabs {
        Layout.fillWidth: true
        currentIndex: sessionView.compactPane
        entries: [
            {
                label: "Hướng dẫn",
                icon: "description"
            },
            {
                label: "Máy thực hành",
                icon: "terminal"
            }
        ]
        itemPrefix: "practicePane-"
        objectName: "practicePaneTabs"
        visible: !!sessionView.session && sessionView.compact

        onSelected: index => sessionView.compactPane = index
    }
    SplitView {
        id: workspace

        Layout.fillHeight: true
        Layout.fillWidth: true
        objectName: "practiceSplit"
        orientation: Qt.Horizontal
        visible: !!sessionView.session

        handle: StudioSplitHandle {
        }

        StudioSurface {
            SplitView.fillWidth: true
            SplitView.minimumWidth: sessionView.compact ? 0 : 360
            color: Studio.Theme.surfaceContainerLow
            objectName: "practiceDocumentPane"
            radius: Studio.Theme.shapeExtraLarge
            visible: !sessionView.compact || sessionView.compactPane === 0

            ColumnLayout {
                anchors.fill: parent
                anchors.margins: Studio.Theme.space16
                spacing: Studio.Theme.space16

                SectionHeader {
                    Layout.fillWidth: true
                    title: "Hướng dẫn"
                }
                MarkdownView {
                    Layout.fillHeight: true
                    Layout.fillWidth: true
                    markdown: sessionView.manual
                }
            }
        }
        StudioSurface {
            SplitView.fillWidth: sessionView.compact
            SplitView.maximumWidth: sessionView.compact ? workspace.width : workspace.width - 360 - Studio.Theme.space16
            SplitView.minimumWidth: sessionView.compact ? 0 : 320
            SplitView.preferredWidth: workspace.width * 0.43
            color: Studio.Theme.surfaceContainerLow
            objectName: "practiceMachinesPane"
            radius: Studio.Theme.shapeExtraLarge
            visible: !sessionView.compact || sessionView.compactPane === 1

            ScrollView {
                id: machines

                anchors.fill: parent
                anchors.margins: Studio.Theme.space16
                clip: true
                contentWidth: availableWidth

                ColumnLayout {
                    spacing: Studio.Theme.space16
                    width: machines.availableWidth

                    SectionHeader {
                        Layout.fillWidth: true
                        title: "Máy thực hành"
                    }
                    Repeater {
                        model: sessionView.session ? sessionView.session.environments || [] : []

                        SessionNodeCard {
                            required property var modelData

                            Layout.fillWidth: true
                            busy: sessionView.busy
                            nodeId: modelData[0]
                            desktopSupported: sessionView.desktopSupported
                            session: sessionView.session
                            onTerminalRequested: slot => sessionView.terminalRequested(sessionView.session, nodeId, slot)
                            onDesktopRequested: sessionView.desktopRequested(sessionView.session, nodeId)
                        }
                    }
                }
            }
        }
    }
}
