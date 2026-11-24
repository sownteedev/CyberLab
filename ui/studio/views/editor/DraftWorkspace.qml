pragma ComponentBehavior: Bound

import QtQuick
import QtQuick.Controls.Basic
import QtQuick.Layouts
import "../.." as Studio

ColumnLayout {
    id: workspace

    property bool choosingDraft: false
    readonly property bool compact: width < Studio.Theme.editorRailBreakpoint
    required property var editor
    readonly property var sections: [
        { label: qsTr("Tổng quan"), icon: "inventory_2" },
        { label: qsTr("Máy lab"), icon: "terminal" },
        { label: qsTr("Mạng"), icon: "lan" },
        { label: qsTr("File"), icon: "folder" },
        { label: qsTr("Hướng dẫn"), icon: "description" },
        { label: qsTr("Kiểm tra"), icon: "check_circle" },
        { label: qsTr("Tùy chọn"), icon: "science" }
    ]
    readonly property bool showLanding: !editor.draft || choosingDraft
    readonly property bool wide: width >= 1080
    readonly property var selectedSection: sections[editor.section] || sections[0]
    signal deleteRequested
    signal exportPackageRequested
    signal reloadRequested

    spacing: Studio.Theme.space16
    onVisibleChanged: if (!visible) reviewDrawer.close()
    onWideChanged: if (wide) reviewDrawer.close()

    Connections {
        target: workspace.editor
        function onDraftChanged() { workspace.choosingDraft = false; }
        function onSectionChanged() {
            const flick = sectionScroll.contentItem as Flickable;
            if (flick) flick.contentY = 0;
        }
    }
    Studio.DraftToolbar {
        Layout.fillWidth: true
        editor: workspace.editor
        visible: !workspace.showLanding
        onChooseRequested: {
            if (workspace.editor.dirty) chooseConfirmation.open();
            else workspace.choosingDraft = true;
        }
        onValidateRequested: {
            workspace.editor.validate();
            if (workspace.wide) workspace.editor.section = 5;
            else reviewDrawer.open();
        }
        onPublishRequested: {
            workspace.editor.section = 5;
            workspace.editor.prepareLibrarySave();
        }
        onExportRequested: workspace.exportPackageRequested()
        onReloadRequested: workspace.reloadRequested()
        onDeleteRequested: workspace.deleteRequested()
    }
    Studio.DraftLanding {
        Layout.fillHeight: true
        Layout.fillWidth: true
        editor: workspace.editor
        visible: workspace.showLanding
        onResumeRequested: {
            workspace.editor.section = 0;
            workspace.choosingDraft = false;
        }
    }
    RowLayout {
        Layout.fillHeight: true
        Layout.fillWidth: true
        spacing: workspace.compact ? Studio.Theme.space12 : Studio.Theme.space24
        visible: !workspace.showLanding

        Studio.DraftNavigation {
            Layout.fillHeight: true
            Layout.minimumWidth: implicitWidth
            Layout.maximumWidth: implicitWidth
            Layout.preferredWidth: implicitWidth
            compact: workspace.compact
            editor: workspace.editor
            sections: workspace.sections
            enabled: !!workspace.editor.document
        }
        Item {
            Layout.fillHeight: true
            Layout.fillWidth: true
            Layout.minimumWidth: 0
            objectName: "draftSectionSurface"

            ColumnLayout {
                anchors.top: parent.top
                anchors.bottom: parent.bottom
                anchors.topMargin: Studio.Theme.space8
                width: Math.max(0, parent.width - Studio.Theme.space16)
                x: (parent.width - width) / 2
                spacing: Studio.Theme.space24
                objectName: "draftSectionContent"

                ColumnLayout {
                    Layout.fillWidth: true
                    spacing: Studio.Theme.space8
                    Label {
                        Layout.fillWidth: true
                        color: Studio.Theme.textOnSurface
                        font.pixelSize: Studio.Theme.headlineMedium
                        font.weight: Font.DemiBold
                        text: workspace.selectedSection.label
                        wrapMode: Text.WordWrap
                    }
                }
                ScrollView {
                    id: sectionScroll
                    Layout.fillHeight: true
                    Layout.fillWidth: true
                    clip: true
                    contentWidth: availableWidth
                    contentHeight: formSections.implicitHeight + Studio.Theme.space24
                    objectName: "draftSectionScroll"
                    visible: workspace.editor.section !== 4
                    ScrollBar.horizontal.policy: ScrollBar.AlwaysOff

                    Studio.DraftSections {
                        id: formSections
                        viewportHeight: sectionScroll.availableHeight
                        editor: workspace.editor
                        enabled: !!editor.document && !editor.backend.busy
                        objectName: "draftSections"
                        width: sectionScroll.availableWidth
                    }
                }
                Studio.DraftDocumentation {
                    Layout.fillHeight: true
                    Layout.fillWidth: true
                    Layout.bottomMargin: Studio.Theme.space16
                    editor: workspace.editor
                    enabled: !!editor.document && !editor.backend.busy
                    visible: workspace.editor.section === 4
                }
            }
        }
    }
    readonly property Studio.ConfirmDialog chooseDialog: Studio.ConfirmDialog {
        id: chooseConfirmation
        objectName: "chooseDraftConfirmation"
        title: qsTr("Bỏ thay đổi chưa lưu?")
        message: qsTr("Bỏ phần vừa sửa để chọn bản nháp khác. Bản nháp đã lưu và bài trong thư viện vẫn được giữ nguyên.")
        confirmText: qsTr("Bỏ thay đổi và quay lại")
        confirmEnabled: !workspace.editor.backend.busy
        danger: true
        onAccepted: {
            if (workspace.editor.discardChanges()) workspace.choosingDraft = true;
        }
    }
    readonly property Studio.StudioDialog reviewDialog: Studio.StudioDialog {
        id: reviewDrawer
        parent: Overlay.overlay
        objectName: "draftReviewDrawer"
        width: Math.max(0, Math.min(640, Overlay.overlay ? Overlay.overlay.width - Studio.Theme.space32 : 640))
        height: Math.max(0, Math.min(720, Overlay.overlay ? Overlay.overlay.height - Studio.Theme.space32 : 720))
        padding: Studio.Theme.space24
        header: Studio.StudioDialogHeader {
            title: qsTr("Kiểm tra bản nháp")
            iconName: "check_circle"
            closeDescription: qsTr("Đóng kết quả kiểm tra")
            onCloseRequested: reviewDrawer.close()
        }
        contentItem: ScrollView {
            id: compactReview
            clip: true
            contentWidth: availableWidth
            Studio.DraftReview { editor: workspace.editor; width: compactReview.availableWidth }
        }
    }
}
