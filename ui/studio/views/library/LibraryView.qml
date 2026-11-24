import QtQuick
import QtQuick.Controls
import QtQuick.Layouts
import "../.."
import "../.." as Studio

ColumnLayout {
    id: libraryView

    property bool busy: false
    property bool starting: false
    readonly property bool compact: width < 720
    property bool connected: false
    readonly property bool deletionBlocked: !!selectedLab && sessions.some(session => session.lab_id === selectedLab.id && session.state !== "STOPPED")
    property bool deletionSupported: false
    readonly property bool hasQuiz: {
        try {
            const value = selectedLab ? selectedLab.quiz : [];
            const items = Array.isArray(value) ? value : JSON.parse(value || "[]");
            return Array.isArray(items) && items.length > 0;
        } catch (error) {
            return false;
        }
    }
    property var labs: []
    readonly property var topicOptions: {
        const labels = {};
        for (const lab of labs)
            for (const tag of lab.tags || []) labels[tag] = (lab.tag_labels || {})[tag] || tag;
        return Object.keys(labels).map(tag => ({id: tag, label: labels[tag]})).sort((left, right) => left.label.localeCompare(right.label));
    }
    onTopicOptionsChanged: {
        if (toolbar && Array.isArray(toolbar.selectedTags))
            toolbar.selectedTags = toolbar.selectedTags.filter(tag => topicOptions.some(option => option.id === tag));
    }
    readonly property int listWidth: Math.round(Math.min(Studio.Theme.libraryWidth, Math.max(280, width * 0.26)))
    property string manual: ""
    property bool packageSupported: false
    property bool quizSupported: false
    property bool reportsSupported: false
    property bool reviewSupported: false
    property var selectedLab: null
    readonly property var resumableSession: selectedLab ? suspendedSession(selectedLab.id) : null
    property var sessions: []
    property bool showDetails: false

    signal cloneLabRequested(var lab)
    signal deleteLabRequested(var lab)
    signal editLabRequested(var lab)
    signal exportPackageRequested(var lab)
    signal importPackageRequested
    signal openSessionRequested(var session)
    signal quizRequested(var lab)
    signal reportsRequested
    signal resumeSessionRequested(var session)
    signal reviewSubmissionsRequested(Item caller)
    signal selectLabRequested(var lab)
    signal startLabRequested(var lab)

    function matchingLabs(query) {
        const value = (query || "").trim().toLowerCase();
        return labs.filter(lab => (!toolbar.selectedTags.length || toolbar.selectedTags.some(tag => (lab.tags || []).includes(tag)))
            && (!toolbar.selectedDifficulty || (lab.difficulty || "unclassified") === toolbar.selectedDifficulty)
            && (!value || (lab.name + " " + lab.id + " " + (lab.tags || []).map(tag => (lab.tag_labels || {})[tag] || tag).join(" ")).toLowerCase().includes(value)));
    }
    function runningSession(labId) {
        if (!sessions || !labId)
            return null;
        return sessions.find(session => session.lab_id === labId && session.state === "RUNNING") || null;
    }
    function suspendedSession(labId) {
        if (!sessions || !labId)
            return null;
        return sessions.find(session => session.lab_id === labId && session.saved && (session.state === "SUSPENDED" || session.state === "STOPPED")) || null;
    }

    spacing: Studio.Theme.contentGap

    StudioTabs {
        Layout.fillWidth: true
        currentIndex: libraryView.showDetails ? 1 : 0
        entries: [
            {
                label: "Bài lab",
                icon: "library_books"
            },
            {
                label: "Hướng dẫn",
                icon: "description"
            }
        ]
        itemPrefix: "libraryPane-"
        objectName: "libraryPaneTabs"
        visible: libraryView.compact

        onSelected: index => libraryView.showDetails = index === 1
    }
    SplitView {
        id: librarySplit
        Layout.fillHeight: true
        Layout.fillWidth: true
        objectName: "librarySplit"
        orientation: Qt.Horizontal
        handle: Studio.StudioSplitHandle {
            objectName: "librarySplitHandle"
            HoverHandler { cursorShape: Qt.SplitHCursor }
        }
        ColumnLayout {
            implicitWidth: libraryView.listWidth
            SplitView.fillWidth: libraryView.compact
            SplitView.maximumWidth: libraryView.compact ? Infinity : Math.min(560, librarySplit.width - 360 - Studio.Theme.space16)
            SplitView.minimumWidth: libraryView.compact ? 0 : 280
            objectName: "libraryList"
            spacing: Studio.Theme.contentGap
            visible: !libraryView.compact || !libraryView.showDetails

            Studio.LibraryToolbar {
                id: toolbar

                Layout.fillWidth: true
                busy: libraryView.busy
                connected: libraryView.connected
                labCount: libraryView.labs.length
                topicOptions: libraryView.topicOptions
                packageSupported: libraryView.packageSupported
                reportsSupported: libraryView.reportsSupported
                reviewSupported: libraryView.reviewSupported

                onImportRequested: libraryView.importPackageRequested()
                onReportsRequested: libraryView.reportsRequested()
                onReviewRequested: caller => libraryView.reviewSubmissionsRequested(caller)
            }
            Item {
                Layout.fillHeight: true
                Layout.fillWidth: true
                objectName: "libraryLabList"

                ScrollView {
                    id: libraryScroll

                    anchors.fill: parent
                    clip: true
                    visible: !libraryEmpty.visible

                    ColumnLayout {
                        spacing: Studio.Theme.space8
                        width: libraryScroll.availableWidth

                        Repeater {
                            model: libraryView.matchingLabs(toolbar.query)

                            Studio.LibraryLabCard {
                                required property var modelData
                                Layout.fillWidth: true
                                lab: modelData
                                running: !!libraryView.runningSession(modelData.id)
                                selected: !!libraryView.selectedLab && libraryView.selectedLab.id === modelData.id

                                onClicked: {
                                    libraryView.showDetails = true;
                                    libraryView.selectLabRequested(modelData);
                                    const active = libraryView.runningSession(modelData.id);
                                    if (active)
                                        libraryView.openSessionRequested(active);
                                }
                            }
                        }
                    }
                }
                EmptyState {
                    id: libraryEmpty

                    anchors.centerIn: parent
                    width: parent.width
                    objectName: "libraryEmptyState"
                    description: libraryView.connected ? "Thử đổi từ khóa tìm kiếm hoặc tạo một bài lab mới." : "Kiểm tra cyberlabd và System D-Bus rồi làm mới."
                    title: libraryView.connected ? "Không tìm thấy bài lab" : "Chưa kết nối daemon"
                    visible: libraryView.matchingLabs(toolbar.query).length === 0
                }
            }
        }
        StudioSurface {
            SplitView.fillWidth: true
            SplitView.minimumWidth: libraryView.compact ? 0 : 360
            color: Studio.Theme.surfaceContainerLow
            objectName: "libraryDetail"
            radius: Studio.Theme.shapeExtraLarge
            visible: !libraryView.compact || libraryView.showDetails

            ColumnLayout {
                anchors.fill: parent
                anchors.margins: Studio.Theme.space16
                spacing: Studio.Theme.space16

                LibraryLabHeader {
                    Layout.fillWidth: true
                    lab: libraryView.selectedLab
                    running: !!libraryView.selectedLab && !!libraryView.runningSession(libraryView.selectedLab.id)
                    savedState: libraryView.resumableSession ? libraryView.resumableSession.state : ""
                    visible: !!libraryView.selectedLab
                }
                EmptyState {
                    Layout.fillHeight: true
                    Layout.fillWidth: true
                    title: "Chọn một bài lab"
                    visible: !libraryView.selectedLab
                }
                MarkdownView {
                    Layout.fillHeight: true
                    Layout.fillWidth: true
                    markdown: libraryView.manual
                    objectName: "libraryDocument"
                    visible: !!libraryView.selectedLab
                }
                GridLayout {
                    id: libraryActions

                    Layout.fillWidth: true
                    columnSpacing: Studio.Theme.space8
                    columns: width >= 480 ? 2 : 1
                    objectName: "libraryActions"
                    rowSpacing: Studio.Theme.space4

                    RowLayout {
                        Layout.fillWidth: true
                        spacing: Studio.Theme.space8

                        StudioButton {
                            enabled: !libraryView.busy
                            highlighted: true
                            iconName: "terminal"
                            text: "Mở bài"
                            visible: !!libraryView.selectedLab && !!libraryView.runningSession(libraryView.selectedLab.id)

                            onClicked: libraryView.openSessionRequested(libraryView.runningSession(libraryView.selectedLab.id))
                        }
                        StudioButton {
                            enabled: libraryView.connected && !libraryView.busy && !libraryView.starting
                            highlighted: true
                            iconName: "play_arrow"
                            objectName: "resumeLabButton"
                            text: libraryView.resumableSession && libraryView.resumableSession.state === "STOPPED" ? "Tiếp tục bản đã lưu" : "Tiếp tục"
                            visible: !!libraryView.selectedLab && !libraryView.runningSession(libraryView.selectedLab.id) && !!libraryView.suspendedSession(libraryView.selectedLab.id)

                            onClicked: libraryView.resumeSessionRequested(libraryView.suspendedSession(libraryView.selectedLab.id))
                        }
                        StudioButton {
                            enabled: libraryView.connected && !libraryView.busy && !libraryView.starting
                            highlighted: true
                            iconName: "play_arrow"
                            objectName: "startLabButton"
                            text: libraryView.starting ? "Đang chuẩn bị…" : "Bắt đầu"
                            visible: !!libraryView.selectedLab && !libraryView.runningSession(libraryView.selectedLab.id) && !libraryView.suspendedSession(libraryView.selectedLab.id)

                            onClicked: libraryView.startLabRequested(libraryView.selectedLab)
                        }
                        StudioIconButton {
                            description: "Mở bản lưu"
                            enabled: !libraryView.busy
                            iconName: "bookmark"
                            visible: !!libraryView.selectedLab && !!libraryView.suspendedSession(libraryView.selectedLab.id)

                            onClicked: libraryView.openSessionRequested(libraryView.suspendedSession(libraryView.selectedLab.id))
                        }
                        StudioButton {
                            enabled: libraryView.connected && !libraryView.busy
                            iconName: "help"
                            objectName: "labQuizButton"
                            text: "Câu hỏi"
                            visible: libraryView.quizSupported && libraryView.hasQuiz

                            onClicked: libraryView.quizRequested(libraryView.selectedLab)
                        }
                        Item {
                            Layout.fillWidth: true
                        }
                    }
                    RowLayout {
                        Layout.alignment: libraryActions.columns === 2 ? Qt.AlignRight : Qt.AlignLeft
                        spacing: Studio.Theme.space8

                        StudioButton {
                            enabled: libraryView.connected && !libraryView.busy
                            flat: true
                            iconName: "edit"
                            text: "Sửa"
                            visible: !!libraryView.selectedLab

                            onClicked: libraryView.editLabRequested(libraryView.selectedLab)
                        }
                        StudioIconButton {
                            description: "Nhân bản bài lab"
                            enabled: libraryView.connected && !libraryView.busy
                            iconName: "content_copy"
                            visible: !!libraryView.selectedLab

                            onClicked: libraryView.cloneLabRequested(libraryView.selectedLab)
                        }
                        StudioIconButton {
                            id: exportPackageButton

                            description: "Xuất bài lab thành gói offline"
                            enabled: libraryView.connected && !libraryView.busy
                            iconName: "upload"
                            objectName: "exportLabPackageButton"
                            visible: libraryView.packageSupported && !!libraryView.selectedLab

                            onClicked: {
                                forceActiveFocus();
                                libraryView.exportPackageRequested(libraryView.selectedLab);
                            }
                        }
                        StudioIconButton {
                            danger: true
                            description: "Xóa bài lab"
                            enabled: libraryView.connected && !libraryView.busy && libraryView.deletionSupported && !libraryView.deletionBlocked
                            iconName: "delete"
                            objectName: "deleteLabButton"
                            visible: !!libraryView.selectedLab

                            onClicked: libraryView.deleteLabRequested(libraryView.selectedLab)
                        }
                    }
                }
                Label {
                    Layout.fillWidth: true
                    color: Studio.Theme.textOnSurfaceVariant
                    font.pixelSize: Studio.Theme.bodySmall
                    text: !libraryView.deletionSupported ? "Cần cập nhật daemon để xóa bài." : "Dừng mọi phiên của bài (kể cả phiên lỗi) trước khi xóa."
                    visible: !!libraryView.selectedLab && libraryView.connected && (!libraryView.deletionSupported || libraryView.deletionBlocked)
                    wrapMode: Text.WordWrap
                }
            }
        }
    }
}
