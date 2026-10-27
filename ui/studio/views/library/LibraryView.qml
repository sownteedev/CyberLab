import QtQuick
import QtQuick.Controls
import QtQuick.Layouts
import "../.."
import "../.." as Studio

GridLayout {
    id: libraryView

    property var labs: []
    property var sessions: []
    property var selectedLab: null
    property string manual: ""
    property bool connected: false
    property bool busy: false
    property bool toolsExpanded: false
    property bool deletionSupported: false
    property bool reportsSupported: false
    property bool packageSupported: false
    property bool reviewSupported: false
    property bool quizSupported: false
    readonly property bool compact: width < 720
    property bool showDetails: false
    readonly property bool hasQuiz: {
        try {
            const value = selectedLab ? selectedLab.quiz : [];
            const items = Array.isArray(value) ? value : JSON.parse(value || "[]");
            return Array.isArray(items) && items.length > 0;
        } catch (error) { return false; }
    }
    readonly property bool deletionBlocked: !!selectedLab && sessions.some(session => session.lab_id === selectedLab.id && session.state !== "STOPPED")
    readonly property int listWidth: Math.round(Math.min(Studio.Theme.libraryWidth, Math.max(240, width * 0.26)))

    signal selectLabRequested(var lab)
    signal startLabRequested(var lab)
    signal quizRequested(var lab)
    signal openSessionRequested(var session)
    signal resumeSessionRequested(var session)
    signal cloneLabRequested(var lab)
    signal editLabRequested(var lab)
    signal deleteLabRequested(var lab)
    signal reportsRequested()
    signal importPackageRequested()
    signal exportPackageRequested(var lab)
    signal reviewSubmissionsRequested(Item caller)

    columns: compact ? 1 : 2
    columnSpacing: Studio.Theme.contentGap
    rowSpacing: Studio.Theme.contentGap

    function runningSession(labId) {
        if (!sessions || !labId) return null;
        return sessions.find(session => session.lab_id === labId && session.state === "RUNNING") || null;
    }

    function suspendedSession(labId) {
        if (!sessions || !labId) return null;
        return sessions.find(session => session.lab_id === labId && session.saved
            && (session.state === "SUSPENDED" || session.state === "STOPPED")) || null;
    }

    function matchingLabs(query) {
        const value = (query || "").trim().toLowerCase();
        return labs.filter(lab => !value || (lab.name + " " + lab.id).toLowerCase().includes(value));
    }

    StudioTabs {
        objectName: "libraryPaneTabs"
        Layout.fillWidth: true
        visible: libraryView.compact
        entries: [{label: "Bài lab", icon: "library_books"}, {label: "Hướng dẫn", icon: "description"}]
        currentIndex: libraryView.showDetails ? 1 : 0
        itemPrefix: "libraryPane-"
        onSelected: index => libraryView.showDetails = index === 1
    }
    ColumnLayout {
        objectName: "libraryList"
        visible: !libraryView.compact || !libraryView.showDetails
        Layout.fillWidth: libraryView.compact
        Layout.fillHeight: true
        Layout.preferredWidth: libraryView.compact ? -1 : libraryView.listWidth
        Layout.maximumWidth: libraryView.compact ? Infinity : libraryView.listWidth
        Layout.minimumWidth: libraryView.compact ? 0 : libraryView.listWidth
        spacing: Studio.Theme.contentGap

        SectionHeader {
            Layout.fillWidth: true
            title: "Bài lab"
            titleSize: Studio.Theme.titleMedium
            subtitle: libraryView.labs.length + " bài"
        }

        RowLayout {
            Layout.fillWidth: true
            visible: libraryView.packageSupported
            spacing: Studio.Theme.space8
            StudioButton {
                id: importPackageButton
                objectName: "importLabPackageButton"
                Layout.fillWidth: true
                text: "Nhập gói"
                iconName: "upload"
                flat: true
                visible: libraryView.packageSupported
                enabled: libraryView.connected && !libraryView.busy
                onClicked: {
                    importPackageButton.forceActiveFocus();
                    libraryView.importPackageRequested();
                }
            }
            StudioIconButton {
                id: exportPackageButton
                objectName: "exportLabPackageButton"
                iconName: "download"
                description: "Xuất bài lab thành gói offline"
                visible: libraryView.packageSupported && !!libraryView.selectedLab
                enabled: libraryView.connected && !libraryView.busy
                onClicked: {
                    exportPackageButton.forceActiveFocus();
                    libraryView.exportPackageRequested(libraryView.selectedLab);
                }
            }
        }

        StudioSearchField {
            id: search
            objectName: "librarySearch"
            Layout.fillWidth: true
            placeholderText: "Tìm theo tên hoặc mã bài"
        }

        StudioButton {
            objectName: "libraryToolsToggle"
            Layout.fillWidth: true
            text: libraryView.toolsExpanded ? "Ẩn công cụ" : "Công cụ"
            iconName: "settings"
            flat: true
            visible: libraryView.reportsSupported || libraryView.reviewSupported
            onClicked: libraryView.toolsExpanded = !libraryView.toolsExpanded
        }
        StudioButton {
            objectName: "libraryReportsButton"
            Layout.fillWidth: true
            text: "Kết quả đã lưu"
            iconName: "description"
            flat: true
            leading: true
            visible: libraryView.toolsExpanded && libraryView.reportsSupported
            enabled: libraryView.connected && !libraryView.busy
            onClicked: libraryView.reportsRequested()
        }
        StudioButton {
            id: reviewSubmissionsButton
            Layout.fillWidth: true
            text: "Duyệt bài nộp"
            objectName: "reviewSubmissionsButton"
            iconName: "inventory_2"
            flat: true
            visible: libraryView.toolsExpanded && libraryView.reviewSupported
            enabled: libraryView.connected && !libraryView.busy
            onClicked: {
                if (Window.window) Window.window.requestActivate();
                reviewSubmissionsButton.forceActiveFocus();
                libraryView.reviewSubmissionsRequested(reviewSubmissionsButton);
            }
        }

        ScrollView {
            id: libraryScroll
            Layout.fillWidth: true
            Layout.fillHeight: true
            clip: true

            ColumnLayout {
                width: libraryScroll.availableWidth
                spacing: Studio.Theme.space8

                Repeater {
                    model: libraryView.matchingLabs(search.text)

                    StudioSurface {
                        id: labCard
                        required property var modelData

                        Layout.fillWidth: true
                        implicitHeight: labContent.implicitHeight + Studio.Theme.space24
                        interactive: true
                        selected: libraryView.selectedLab && libraryView.selectedLab.id === modelData.id
                        color: selected ? Studio.Theme.secondaryContainer : Studio.Theme.surfaceContainer
                        Accessible.name: modelData.name
                        ToolTip.visible: cardHover.hovered
                        ToolTip.delay: 700
                        ToolTip.text: modelData.name + "\n" + modelData.id + " · v" + modelData.version
                        HoverHandler { id: cardHover }
                        onClicked: {
                            libraryView.showDetails = true;
                            libraryView.selectLabRequested(modelData);
                            const active = libraryView.runningSession(modelData.id);
                            if (active) libraryView.openSessionRequested(active);
                        }

                        RowLayout {
                            id: labContent
                            anchors.fill: parent
                            anchors.margins: Studio.Theme.space12
                            spacing: Studio.Theme.space12

                            Rectangle {
                                Layout.preferredWidth: 40
                                Layout.preferredHeight: 40
                                radius: Studio.Theme.shapeMedium
                                color: labCard.selected ? Studio.Theme.primary : (cardHover.hovered ? Studio.Theme.surfaceContainerHighest : Studio.Theme.surfaceContainerHigh)
                                border.width: Studio.Theme.borderWidth
                                border.color: labCard.selected ? Studio.Theme.primary : Studio.Theme.outlineVariant

                                Icon {
                                    anchors.centerIn: parent
                                    name: libraryView.runningSession(labCard.modelData.id) ? "terminal" : "science"
                                    size: Studio.Theme.iconSmall
                                    color: labCard.selected ? Studio.Theme.textOnPrimary : Studio.Theme.primary
                                }
                            }

                            ColumnLayout {
                                Layout.fillWidth: true
                                spacing: 2
                                Label {
                                    Layout.fillWidth: true
                                    text: labCard.modelData.name
                                    color: Studio.Theme.textOnSurface
                                    font.pixelSize: Studio.Theme.titleSmall
                                    font.weight: Font.DemiBold
                                    elide: Text.ElideRight
                                }
                                Label {
                                    Layout.fillWidth: true
                                    text: labCard.modelData.nodes.length + " máy · " + labCard.modelData.networks.length
                                        + " mạng"
                                    color: Studio.Theme.textOnSurfaceVariant
                                    font.pixelSize: Studio.Theme.bodySmall
                                    elide: Text.ElideRight
                                }
                            }

                            Icon {
                                name: libraryView.runningSession(labCard.modelData.id) ? "play_arrow" : "chevron_right"
                                size: Studio.Theme.iconSmall
                                color: libraryView.runningSession(labCard.modelData.id) ? Studio.Theme.success : Studio.Theme.textOnSurfaceVariant
                            }
                        }
                    }
                }

                EmptyState {
                    Layout.fillWidth: true
                    Layout.fillHeight: true
                    visible: libraryView.matchingLabs(search.text).length === 0
                    title: libraryView.connected ? "Không tìm thấy bài lab" : "Chưa kết nối daemon"
                    description: libraryView.connected ? "Thử đổi từ khóa tìm kiếm hoặc tạo một bài lab mới." : "Kiểm tra cyberlabd và System D-Bus rồi làm mới."
                }
            }
        }
    }

    StudioSurface {
        objectName: "libraryDetail"
        visible: !libraryView.compact || libraryView.showDetails
        Layout.fillWidth: true
        Layout.fillHeight: true
        Layout.minimumWidth: libraryView.compact ? 0 : 360
        radius: Studio.Theme.shapeExtraLarge
        color: Studio.Theme.surfaceContainerLow

        ColumnLayout {
            anchors.fill: parent
            anchors.margins: Studio.Theme.space16
            spacing: Studio.Theme.space16

            LibraryLabHeader {
                visible: !!libraryView.selectedLab
                Layout.fillWidth: true
                lab: libraryView.selectedLab
                running: !!libraryView.selectedLab && !!libraryView.runningSession(libraryView.selectedLab.id)
                saved: !!libraryView.selectedLab && !!libraryView.suspendedSession(libraryView.selectedLab.id)
            }

            EmptyState {
                Layout.fillWidth: true
                Layout.fillHeight: true
                visible: !libraryView.selectedLab
                title: "Chọn một bài lab"
                description: "Hướng dẫn và thông tin môi trường sẽ hiển thị tại đây."
            }

            MarkdownView {
                objectName: "libraryDocument"
                visible: !!libraryView.selectedLab
                Layout.fillWidth: true
                Layout.fillHeight: true
                markdown: libraryView.manual
            }

            GridLayout {
                objectName: "libraryActions"
                id: libraryActions
                Layout.fillWidth: true
                columns: width >= 480 ? 2 : 1
                columnSpacing: Studio.Theme.space8
                rowSpacing: Studio.Theme.space4
                RowLayout {
                    Layout.fillWidth: true
                    spacing: Studio.Theme.space8
                    StudioButton {
                        visible: !!libraryView.selectedLab && !!libraryView.runningSession(libraryView.selectedLab.id)
                        iconName: "terminal"; text: "Mở bài"
                        highlighted: true
                        enabled: !libraryView.busy
                        onClicked: libraryView.openSessionRequested(libraryView.runningSession(libraryView.selectedLab.id))
                    }
                    StudioButton {
                        visible: !!libraryView.selectedLab && !libraryView.runningSession(libraryView.selectedLab.id) && !!libraryView.suspendedSession(libraryView.selectedLab.id)
                        iconName: "play_arrow"; text: "Tiếp tục"
                        highlighted: true
                        enabled: libraryView.connected && !libraryView.busy
                        onClicked: libraryView.resumeSessionRequested(libraryView.suspendedSession(libraryView.selectedLab.id))
                    }
                    StudioButton {
                        objectName: "startLabButton"
                        visible: !!libraryView.selectedLab && !libraryView.runningSession(libraryView.selectedLab.id) && !libraryView.suspendedSession(libraryView.selectedLab.id)
                        iconName: "play_arrow"; text: "Bắt đầu"
                        highlighted: true
                        enabled: libraryView.connected && !libraryView.busy
                        onClicked: libraryView.startLabRequested(libraryView.selectedLab)
                    }
                    StudioIconButton {
                        iconName: "bookmark"; description: "Mở bản lưu"
                        visible: !!libraryView.selectedLab && !!libraryView.suspendedSession(libraryView.selectedLab.id)
                        enabled: !libraryView.busy
                        onClicked: libraryView.openSessionRequested(libraryView.suspendedSession(libraryView.selectedLab.id))
                    }
                    StudioButton {
                        objectName: "labQuizButton"
                        visible: libraryView.quizSupported && libraryView.hasQuiz
                        text: "Câu hỏi"
                        iconName: "help"
                        enabled: libraryView.connected && !libraryView.busy
                        onClicked: libraryView.quizRequested(libraryView.selectedLab)
                    }
                    Item { Layout.fillWidth: true }
                }
                RowLayout {
                    Layout.alignment: libraryActions.columns === 2 ? Qt.AlignRight : Qt.AlignLeft
                    spacing: Studio.Theme.space8
                    StudioButton {
                        visible: !!libraryView.selectedLab
                        iconName: "edit"; text: "Sửa"
                        flat: true
                        enabled: libraryView.connected && !libraryView.busy
                        onClicked: libraryView.editLabRequested(libraryView.selectedLab)
                    }
                    StudioIconButton {
                        visible: !!libraryView.selectedLab
                        iconName: "content_copy"; description: "Nhân bản bài lab"
                        enabled: libraryView.connected && !libraryView.busy
                        onClicked: libraryView.cloneLabRequested(libraryView.selectedLab)
                    }
                    StudioIconButton {
                        objectName: "deleteLabButton"
                        visible: !!libraryView.selectedLab
                        iconName: "delete"; description: "Xóa bài lab"
                        danger: true
                        enabled: libraryView.connected && !libraryView.busy && libraryView.deletionSupported && !libraryView.deletionBlocked
                        onClicked: libraryView.deleteLabRequested(libraryView.selectedLab)
                    }
                }
            }
            Label {
                Layout.fillWidth: true
                visible: !!libraryView.selectedLab && libraryView.connected && (!libraryView.deletionSupported || libraryView.deletionBlocked)
                text: !libraryView.deletionSupported ? "Cần cập nhật daemon để xóa bài."
                    : "Dừng mọi phiên của bài (kể cả phiên lỗi) trước khi xóa."
                wrapMode: Text.WordWrap
                font.pixelSize: Studio.Theme.bodySmall
                color: Studio.Theme.textOnSurfaceVariant
            }
        }
    }
}
