pragma ComponentBehavior: Bound

import QtQuick
import QtQuick.Controls.Basic
import QtQuick.Layouts
import ".." as Studio

Studio.StudioButton {
    id: picker

    property var options: []
    property var selectedTags: []
    property bool requiredSelection: false
    property bool filterMode: false
    signal edited(var tags)

    readonly property string selectionText: selectedTags.map(tag => {
        const option = options.find(entry => entry.id === tag);
        return option ? option.label : tag;
    }).join(" · ")

    enabled: options.length > 0
    outlined: true
    selected: selectedTags.length > 0
    text: filterMode ? (selectedTags.length ? qsTr("Chủ đề (%1)").arg(selectedTags.length) : qsTr("Lọc chủ đề"))
        : selectionText || qsTr("Chọn chủ đề")
    onClicked: dialog.open()

    readonly property Studio.StudioDialog dialog: Studio.StudioDialog {
        id: choice
        property var pendingTags: []
        readonly property var validTags: pendingTags.filter(tag => picker.options.some(option => option.id === tag))
        objectName: picker.objectName + "Dialog"
        width: Math.max(0, Math.min(640, parent ? parent.width - Studio.Theme.space32 : 640))
        height: Math.max(0, Math.min(topicsGrid.implicitHeight + topPadding + bottomPadding + header.implicitHeight + footer.implicitHeight,
                                   parent ? parent.height - Studio.Theme.space32 : 640))
        padding: Studio.Theme.space16
        onAboutToShow: pendingTags = picker.selectedTags.slice()
        onOpened: Qt.callLater(scroll.revealFocused)
        onAccepted: if (!picker.requiredSelection || validTags.length) picker.edited(validTags.slice())
        onClosed: picker.forceActiveFocus()
        header: Studio.StudioDialogHeader {
            title: picker.filterMode ? qsTr("Lọc chủ đề") : qsTr("Chọn chủ đề")
            subtitle: picker.requiredSelection ? qsTr("Chọn ít nhất một chủ đề.") : ""
            onCloseRequested: choice.reject()
        }
        contentItem: ScrollView {
            id: scroll
            function revealFocused() {
                if (!choice.opened) return;
                for (let index = 0; index < topicItems.count; index++) {
                    const option = topicItems.itemAt(index);
                    if (option && option.activeFocus) reveal(option);
                }
            }
            onAvailableHeightChanged: Qt.callLater(revealFocused)
            onContentHeightChanged: Qt.callLater(revealFocused)
            function reveal(option) {
                if (!option.activeFocus) return;
                const flick = contentItem as Flickable;
                if (!flick) return;
                const position = option.mapToItem(flick.contentItem, 0, 0);
                let offset = flick.contentY;
                if (position.y < offset) offset = position.y;
                else if (position.y + option.height > offset + availableHeight)
                    offset = position.y + option.height - availableHeight;
                flick.contentY = Math.max(0, Math.min(offset, contentHeight - availableHeight));
            }
            clip: true
            contentWidth: availableWidth
            contentHeight: topicsGrid.implicitHeight
            GridLayout {
                id: topicsGrid
                width: scroll.availableWidth
                columns: width >= 500 ? 2 : 1
                columnSpacing: Studio.Theme.space8
                rowSpacing: Studio.Theme.space8
                Repeater {
                    id: topicItems
                    model: picker.options
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
                        selected: choice.pendingTags.includes(modelData.id)
                        Accessible.role: Accessible.CheckBox
                        Accessible.checkable: true
                        Accessible.checked: selected
                        onClicked: choice.pendingTags = selected
                            ? choice.pendingTags.filter(tag => tag !== modelData.id)
                            : choice.pendingTags.concat([modelData.id])
                        onActiveFocusChanged: if (activeFocus) Qt.callLater(() => scroll.reveal(topicOption))
                    }
                }
            }
        }
        footer: Studio.StudioDialogFooter {
            contentItem: RowLayout {
                spacing: Studio.Theme.space8
                Studio.StudioButton {
                    text: qsTr("Bỏ lọc")
                    visible: picker.filterMode
                    flat: true
                    onClicked: { choice.pendingTags = []; choice.accept(); }
                }
                Item { Layout.fillWidth: true }
                Studio.StudioButton { text: qsTr("Hủy"); visible: !picker.filterMode; flat: true; onClicked: choice.reject() }
                Studio.StudioButton {
                    objectName: "applyTopics"
                    text: qsTr("Áp dụng")
                    highlighted: true
                    enabled: !picker.requiredSelection || choice.validTags.length > 0
                    onClicked: choice.accept()
                }
            }
        }
    }
}
