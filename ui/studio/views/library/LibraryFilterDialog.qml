pragma ComponentBehavior: Bound

import QtQuick
import QtQuick.Controls.Basic
import QtQuick.Layouts
import "../.." as Studio

Studio.StudioDialog {
    id: dialog

    property var topicOptions: []
    property var selectedTags: []
    property string selectedDifficulty: ""
    property var pendingTags: []
    property string pendingDifficulty: ""
    readonly property var validTags: pendingTags.filter(tag => topicOptions.some(option => option.id === tag))
    readonly property var difficulties: [
        {value: "", label: qsTr("Tất cả")},
        {value: "easy", label: qsTr("Dễ")},
        {value: "medium", label: qsTr("Trung bình")},
        {value: "hard", label: qsTr("Khó")},
        {value: "unclassified", label: qsTr("Chưa phân loại")}
    ]
    signal filtersApplied(var tags, string difficulty)

    objectName: "libraryFilterDialog"
    width: Math.min(560, parent ? parent.width - Studio.Theme.space32 : 560)
    height: Math.min(implicitHeight, parent ? parent.height - Studio.Theme.space32 : implicitHeight)
    padding: 0
    spacing: 0
    font.family: Studio.Theme.fontFamily
    closePolicy: Popup.CloseOnEscape

    onAboutToShow: {
        pendingTags = selectedTags.slice();
        pendingDifficulty = selectedDifficulty;
        scroll.contentY = 0;
    }
    onOpened: Qt.callLater(() => difficultyOptions.itemAt(0).forceActiveFocus(Qt.TabFocusReason))
    onAccepted: filtersApplied(validTags.slice(), difficulties.some(option => option.value === pendingDifficulty) ? pendingDifficulty : "")

    header: Studio.StudioDialogHeader {
        title: qsTr("Bộ lọc bài lab")
        iconName: "filter_list"
        onCloseRequested: dialog.reject()
    }

    contentItem: Flickable {
        id: scroll
        function reveal(item) {
            if (!dialog.opened || !item.activeFocus) return;
            const point = item.mapToItem(contentItem, 0, 0);
            let offset = contentY;
            if (point.y < offset) offset = point.y;
            else if (point.y + item.height > offset + height) offset = point.y + item.height - height;
            contentY = Math.max(0, Math.min(offset, contentHeight - height));
        }
        implicitHeight: contentHeight
        contentWidth: width
        contentHeight: form.implicitHeight + Studio.Theme.space16
        clip: true
        boundsBehavior: Flickable.StopAtBounds
        flickableDirection: Flickable.VerticalFlick
        interactive: contentHeight > height
        ScrollBar.vertical: ScrollBar { policy: ScrollBar.AsNeeded }

        ColumnLayout {
            id: form
            x: Studio.Theme.space24
            y: Studio.Theme.space8
            width: Math.max(0, dialog.width - Studio.Theme.space24 * 2)
            spacing: Studio.Theme.space16

            ColumnLayout {
                Layout.fillWidth: true
                spacing: Studio.Theme.space4
                Label {
                    text: qsTr("Độ khó")
                    color: Studio.Theme.textOnSurface
                    font.pixelSize: Studio.Theme.titleMedium
                    font.weight: Font.DemiBold
                }
                Flow {
                    Layout.fillWidth: true
                    spacing: Studio.Theme.space4
                    Repeater {
                        id: difficultyOptions
                        model: dialog.difficulties
                        delegate: Studio.StudioButton {
                            id: difficultyOption
                            required property var modelData
                            objectName: "difficulty-" + (modelData.value || "all")
                            text: modelData.label
                            selected: dialog.pendingDifficulty === modelData.value
                            outlined: !selected
                            flat: !selected
                            Accessible.role: Accessible.RadioButton
                            Accessible.checkable: true
                            Accessible.checked: selected
                            onClicked: dialog.pendingDifficulty = modelData.value
                            onActiveFocusChanged: if (activeFocus) Qt.callLater(() => scroll.reveal(difficultyOption))
                        }
                    }
                }
            }
            ColumnLayout {
                Layout.fillWidth: true
                spacing: Studio.Theme.space8
                Label {
                    text: qsTr("Chủ đề")
                    color: Studio.Theme.textOnSurface
                    font.pixelSize: Studio.Theme.titleMedium
                    font.weight: Font.DemiBold
                }
                Label {
                    Layout.fillWidth: true
                    visible: dialog.topicOptions.length === 0
                    text: qsTr("Chưa có chủ đề.")
                    color: Studio.Theme.textOnSurfaceVariant
                    wrapMode: Text.WordWrap
                }
                GridLayout {
                    Layout.fillWidth: true
                    columns: width >= 420 ? 2 : 1
                    rowSpacing: Studio.Theme.space4
                    columnSpacing: Studio.Theme.space8
                    Repeater {
                        model: dialog.topicOptions
                        delegate: Studio.TopicOption {
                            id: topicOption
                            required property var modelData
                            Layout.fillWidth: true
                            Layout.preferredWidth: 1
                            Layout.minimumWidth: 0
                            objectName: "topic-" + modelData.id
                            topicId: modelData.id
                            text: modelData.label
                            leading: true
                            outlined: true
                            flat: !selected
                            selected: dialog.pendingTags.includes(modelData.id)
                            Accessible.role: Accessible.CheckBox
                            Accessible.checkable: true
                            Accessible.checked: selected
                            onClicked: dialog.pendingTags = selected
                                ? dialog.pendingTags.filter(tag => tag !== modelData.id)
                                : dialog.pendingTags.concat([modelData.id])
                            onActiveFocusChanged: if (activeFocus) Qt.callLater(() => scroll.reveal(topicOption))
                        }
                    }
                }
            }
        }
    }
    footer: Control {
        implicitHeight: implicitContentHeight + topPadding + bottomPadding
        padding: Studio.Theme.space24
        topPadding: Studio.Theme.space16
        contentItem: RowLayout {
            spacing: Studio.Theme.space8
            Studio.StudioButton {
                objectName: "clearLibraryFilters"
                text: qsTr("Bỏ lọc")
                flat: true
                enabled: dialog.pendingTags.length > 0 || !!dialog.pendingDifficulty || dialog.selectedTags.length > 0 || !!dialog.selectedDifficulty
                onClicked: {
                    dialog.pendingTags = [];
                    dialog.pendingDifficulty = "";
                    dialog.accept();
                }
            }
            Item { Layout.fillWidth: true }
            Studio.StudioButton {
                text: qsTr("Hủy")
                flat: true
                onClicked: dialog.reject()
            }
            Studio.StudioButton {
                objectName: "applyLibraryFilters"
                text: qsTr("Áp dụng")
                highlighted: true
                onClicked: dialog.accept()
            }
        }
    }
}
