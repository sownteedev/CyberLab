pragma ComponentBehavior: Bound

import QtQuick
import QtQuick.Controls.Basic
import QtQuick.Layouts
import "../.." as Studio

Item {
    id: toolbar

    property bool busy: false
    property bool connected: false
    property int labCount: 0
    property bool packageSupported: false
    property alias query: search.text
    property bool reportsSupported: false
    property bool reviewSupported: false
    property var topicOptions: []
    property var selectedTags: []
    property string selectedDifficulty: ""
    readonly property int activeFilterCount: selectedTags.length + (selectedDifficulty ? 1 : 0)

    signal importRequested
    signal reportsRequested
    signal reviewRequested(Item caller)

    objectName: "libraryToolbar"
    implicitHeight: controls.implicitHeight

    onVisibleChanged: {
        if (!visible) {
            toolsMenu.close();
            filters.close();
        }
    }

    ColumnLayout {
        id: controls

        anchors.fill: parent
        spacing: Studio.Theme.space8

        RowLayout {
            Layout.fillWidth: true
            Layout.minimumHeight: Studio.Theme.controlHeight
            spacing: Studio.Theme.space4

            Label {
                Layout.fillWidth: true
                Layout.minimumWidth: 0
                color: Studio.Theme.textOnSurface
                elide: Text.ElideRight
                font.family: Studio.Theme.fontFamily
                font.pixelSize: Studio.Theme.titleMedium
                font.weight: Font.DemiBold
                text: qsTr("Bài lab")
            }
            Label {
                Accessible.name: qsTr("%1 bài lab").arg(toolbar.labCount)
                color: Studio.Theme.textOnSurfaceVariant
                font.family: Studio.Theme.fontFamily
                font.pixelSize: Studio.Theme.bodySmall
                text: toolbar.labCount
            }
            Studio.StudioIconButton {
                id: importButton

                description: qsTr("Nhập gói bài lab")
                enabled: toolbar.connected && !toolbar.busy
                flat: false
                iconName: "download"
                objectName: "importLabPackageButton"
                visible: toolbar.packageSupported

                onClicked: {
                    forceActiveFocus();
                    toolbar.importRequested();
                }
            }
            Studio.StudioIconButton {
                id: toolsButton

                description: qsTr("Công cụ thư viện")
                iconName: "more_horiz"
                objectName: "libraryToolsToggle"
                selected: toolsMenu.opened
                visible: toolbar.reportsSupported || toolbar.reviewSupported

                onClicked: toolsMenu.open()
            }
        }
        RowLayout {
            Layout.fillWidth: true
            spacing: Studio.Theme.space8
            Studio.StudioSearchField {
                id: search
                Layout.fillWidth: true
                Layout.minimumWidth: 0
                objectName: "librarySearch"
                placeholderText: qsTr("Tìm bài lab...")
            }
            Studio.StudioButton {
                id: filterButton
                objectName: "libraryFilterButton"
                iconName: "filter_list"
                text: toolbar.activeFilterCount ? qsTr("Lọc (%1)").arg(toolbar.activeFilterCount) : qsTr("Bộ lọc")
                selected: toolbar.activeFilterCount > 0 || filters.opened
                Accessible.name: qsTr("Bộ lọc bài lab")
                Accessible.description: qsTr("%1 lựa chọn đang áp dụng").arg(toolbar.activeFilterCount)
                onClicked: filters.open()
            }
        }
    }
    Studio.LibraryFilterDialog {
        id: filters
        topicOptions: toolbar.topicOptions
        selectedTags: toolbar.selectedTags
        selectedDifficulty: toolbar.selectedDifficulty
        onFiltersApplied: (tags, difficulty) => {
            toolbar.selectedTags = tags;
            toolbar.selectedDifficulty = difficulty;
        }
        onClosed: if (toolbar.visible) filterButton.forceActiveFocus(Qt.TabFocusReason)
    }
    Menu {
        id: toolsMenu

        property string pendingAction: ""

        parent: toolsButton
        objectName: "libraryToolsMenu"
        popupType: Popup.Item
        modal: true
        dim: true
        padding: Studio.Theme.space8
        margins: Studio.Theme.space8
        width: Math.min(280, toolbar.width)
        x: toolsButton.width - width
        y: toolsButton.height + Studio.Theme.space4

        background: Studio.StudioPopupSurface {
            color: Studio.Theme.surface
            radius: Studio.Theme.shapeLarge
        }
        Overlay.modal: Rectangle {
            color: Studio.Theme.scrim
            Accessible.ignored: true
        }
        enter: Transition {
            NumberAnimation { property: "opacity"; from: 0; to: 1; duration: Studio.Theme.reducedMotion ? 0 : Studio.Theme.enterDuration }
        }
        exit: Transition {
            NumberAnimation { property: "opacity"; to: 0; duration: Studio.Theme.reducedMotion ? 0 : Studio.Theme.exitDuration }
        }

        onClosed: {
            const action = pendingAction;
            pendingAction = "";
            if (!toolbar.visible)
                return;
            toolsButton.forceActiveFocus(Qt.PopupFocusReason);
            if (action === "reports")
                toolbar.reportsRequested();
            else if (action === "review")
                toolbar.reviewRequested(toolsButton);
        }

        ToolsAction {
            enabled: toolbar.connected && !toolbar.busy && visible
            iconName: "description"
            objectName: "libraryReportsButton"
            text: qsTr("Kết quả đã lưu")
            visible: toolbar.reportsSupported

            onTriggered: toolsMenu.pendingAction = "reports"
        }
        ToolsAction {
            enabled: toolbar.connected && !toolbar.busy && visible
            iconName: "inventory_2"
            objectName: "reviewSubmissionsButton"
            text: qsTr("Duyệt bài nộp")
            visible: toolbar.reviewSupported

            onTriggered: toolsMenu.pendingAction = "review"
        }
    }

    component ToolsAction: MenuItem {
        id: entry

        required property string iconName

        implicitHeight: visible ? Studio.Theme.controlHeight : 0
        leftPadding: Studio.Theme.space12
        rightPadding: Studio.Theme.space12

        background: Rectangle {
            color: entry.highlighted || entry.down ? Studio.Theme.secondaryContainer : Studio.Theme.transparent
            radius: Studio.Theme.shapeSmall
            border.width: entry.visualFocus ? Studio.Theme.focusWidth : 0
            border.color: Studio.Theme.primary
        }
        contentItem: RowLayout {
            spacing: Studio.Theme.space12
            opacity: entry.enabled ? 1 : 0.38

            Studio.Icon {
                name: entry.iconName
                color: Studio.Theme.textOnSurfaceVariant
                size: Studio.Theme.iconSmall
            }
            Label {
                Layout.fillWidth: true
                color: Studio.Theme.textOnSurface
                elide: Text.ElideRight
                font.family: Studio.Theme.fontFamily
                font.pixelSize: Studio.Theme.bodyMedium
                text: entry.text
            }
        }
    }
}
