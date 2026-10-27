pragma ComponentBehavior: Bound

import QtQuick
import QtQuick.Controls.Material
import QtQuick.Layouts
import "../.."
import "../.." as Studio

ColumnLayout {
    id: workspace
    required property var editor
    readonly property bool wide: width >= 1080
    readonly property bool compact: width < Studio.Theme.editorRailBreakpoint
    readonly property var sections: [
        {label: "Tổng quan", icon: "inventory_2"}, {label: "Máy lab", icon: "terminal"},
        {label: "Mạng", icon: "lan"}, {label: "File", icon: "folder"},
        {label: "Hướng dẫn", icon: "description"}, {label: "Kiểm tra", icon: "check_circle"},
        {label: "Labedit", icon: "science"}
    ]
    property bool choosingDraft: false
    readonly property bool showLanding: !editor.draft || choosingDraft
    signal reloadRequested()
    signal deleteRequested()
    signal exportPackageRequested()
    onVisibleChanged: if (!visible) reviewDrawer.close()
    onWideChanged: if (wide) reviewDrawer.close()
    spacing: Studio.Theme.space12
    Connections {
        target: workspace.editor
        function onDraftChanged() { workspace.choosingDraft = false; }
    }
    RowLayout {
        objectName: "draftEditActions"
        Layout.fillWidth: true
        Layout.maximumHeight: implicitHeight
        visible: !workspace.showLanding
        spacing: Studio.Theme.space8
        SectionHeader {
            Layout.fillWidth: true
            Layout.minimumWidth: 0
            title: workspace.editor.document ? workspace.editor.document.metadata.name : "Tạo bài lab"
            subtitle: workspace.editor.dirty ? "Thay đổi chưa lưu" : workspace.editor.draft ? "Đã lưu bản nháp" : "Bài riêng trong VM của bạn"
        }
        StudioButton { iconName: "save"; text: "Lưu"; iconOnly: workspace.compact; enabled: !!workspace.editor.draft && workspace.editor.dirty && !workspace.editor.backend.busy; onClicked: workspace.editor.save() }
        StudioButton {
            iconName: "check_circle"; text: "Kiểm tra"
            iconOnly: workspace.compact
            enabled: !!workspace.editor.document && !workspace.editor.backend.busy
            onClicked: {
                workspace.editor.validate();
                if (workspace.wide) workspace.editor.section = 5;
                else reviewDrawer.open();
            }
        }
        StudioButton {
            iconName: "check"; text: workspace.editor.isInstalledEdit ? "Cập nhật bài" : "Lưu vào thư viện"
            highlighted: true
            enabled: !!workspace.editor.document && !!workspace.editor.draft && !workspace.editor.backend.busy
            onClicked: { workspace.editor.section = 5; workspace.editor.prepareLibrarySave(); }
        }
    }
    RowLayout {
        Layout.fillWidth: true
        Layout.maximumHeight: implicitHeight
        visible: !workspace.showLanding
        spacing: Studio.Theme.space8
        StudioButton {
            objectName: "chooseDraftButton"
            iconName: "arrow_back"; text: workspace.compact ? "Bản nháp" : "Bản nháp / Tạo mới"
            flat: true
            enabled: !workspace.editor.dirty && !workspace.editor.backend.busy
            onClicked: workspace.choosingDraft = true
        }
        Item { Layout.fillWidth: true }
        StudioIconButton {
            objectName: "exportDraftPackageButton"
            iconName: "download"
            description: workspace.editor.dirty ? "Lưu nháp trước khi xuất gói" : "Xuất gói bản nháp"
            visible: workspace.editor.backend.capabilities.includes("lab-package-export")
            enabled: !!workspace.editor.document && !workspace.editor.dirty && !workspace.editor.backend.busy
            onClicked: workspace.exportPackageRequested()
        }
        StudioIconButton { iconName: "refresh"; description: "Tải lại nháp"; enabled: !!workspace.editor.draft && !workspace.editor.backend.busy; onClicked: workspace.reloadRequested() }
        StudioButton { iconName: "delete"; text: "Xóa nháp"; danger: true; iconOnly: workspace.compact; enabled: !!workspace.editor.draft && !workspace.editor.backend.busy; onClicked: workspace.deleteRequested() }
    }
    InlineError { Layout.fillWidth: true; message: workspace.editor.localError }
    DraftLanding {
        Layout.fillWidth: true
        Layout.fillHeight: true
        visible: workspace.showLanding
        editor: workspace.editor
        onResumeRequested: workspace.choosingDraft = false
    }
    StudioTabs {
        objectName: "draftSectionTabs"
        Layout.fillWidth: true
        visible: !workspace.showLanding && workspace.compact
        entries: workspace.sections
        itemPrefix: "draftSectionTab-"
        currentIndex: workspace.editor.section
        enabled: !!workspace.editor.document
        onSelected: index => workspace.editor.section = index
    }
    RowLayout {
        Layout.fillWidth: true
        Layout.fillHeight: true
        visible: !workspace.showLanding
        spacing: Studio.Theme.space16
        ScrollView {
            id: sectionNavigation
            objectName: "draftSectionNavigation"
            Layout.preferredWidth: Studio.Theme.sectionWidth
            Layout.maximumWidth: Studio.Theme.sectionWidth
            Layout.fillHeight: true
            visible: !workspace.compact
            contentWidth: availableWidth
            clip: true
            ColumnLayout {
                width: sectionNavigation.availableWidth
                spacing: Studio.Theme.space4
                Repeater {
                    model: workspace.sections
                    StudioButton {
                        required property int index
                        required property var modelData
                        objectName: "draftSection-" + index
                        Layout.fillWidth: true
                        text: modelData.label
                        iconName: modelData.icon
                        leading: true
                        flat: true
                        selected: workspace.editor.section === index
                        Accessible.role: Accessible.PageTab
                        Accessible.selected: selected
                        enabled: !!workspace.editor.document
                        onClicked: workspace.editor.section = index
                    }
                }
            }
        }
        StudioSurface {
            objectName: "draftSectionSurface"
            Layout.fillWidth: true
            Layout.fillHeight: true
            radius: Studio.Theme.shapeExtraLarge
            color: Studio.Theme.surfaceContainerLow
            ScrollView {
                id: sectionScroll
                objectName: "draftSectionScroll"
                anchors.fill: parent
                anchors.margins: Studio.Theme.space16
                visible: workspace.editor.section !== 4
                clip: true
                contentWidth: availableWidth
                DraftSections {
                    objectName: "draftSections"
                    width: sectionScroll.availableWidth
                    editor: workspace.editor
                    enabled: !!editor.document && !editor.backend.busy
                }
            }
            DraftDocumentation {
                anchors.fill: parent
                anchors.margins: Studio.Theme.space16
                editor: workspace.editor
                visible: workspace.editor.section === 4
                enabled: !!editor.document && !editor.backend.busy
            }
        }
    }
    Drawer {
        id: reviewDrawer
        objectName: "draftReviewDrawer"
        parent: Overlay.overlay
        edge: Qt.RightEdge
        width: Math.min(360, workspace.width)
        height: parent ? parent.height : workspace.height
        dragMargin: 0
        modal: true
        focus: true
        closePolicy: Popup.CloseOnEscape | Popup.CloseOnPressOutside
        padding: Studio.Theme.space16
        background: Rectangle { color: Studio.Theme.surfaceContainerHigh; radius: Studio.Theme.shapeExtraLarge }
        enter: Transition { NumberAnimation { property: "position"; to: 1; duration: Studio.Theme.enterDuration; easing.type: Easing.OutCubic } }
        exit: Transition { NumberAnimation { property: "position"; to: 0; duration: Studio.Theme.exitDuration; easing.type: Easing.InCubic } }
        ScrollView {
            id: compactReview
            anchors.fill: parent
            contentWidth: availableWidth
            clip: true
            DraftReview { width: compactReview.availableWidth; editor: workspace.editor }
        }
    }
}
