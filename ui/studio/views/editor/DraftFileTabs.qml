pragma ComponentBehavior: Bound
import QtQuick
import QtQuick.Controls.Basic
import "../.." as Studio

ScrollView {
    id: tabs
    required property var files
    objectName: "fileTabs"
    implicitHeight: 56
    clip: true
    contentWidth: tabRow.width
    contentHeight: 56
    ScrollBar.vertical.policy: ScrollBar.AlwaysOff
    ScrollBar.horizontal.policy: ScrollBar.AsNeeded

    function revealActive() {
        const index = files.tabs.findIndex(tab => tab.key === files.activeKey);
        reveal(tabRepeater.itemAt(index));
    }
    function reveal(item) {
        if (!item || !contentItem) return;
        const left = contentItem.contentX;
        if (item.x < left) contentItem.contentX = item.x;
        else if (item.x + item.width > left + width)
            contentItem.contentX = Math.max(0, item.x + item.width - width);
    }
    onWidthChanged: Qt.callLater(revealActive)
    Connections {
        target: tabs.files
        function onActiveKeyChanged() { Qt.callLater(tabs.revealActive); }
        function onTabsChanged() { Qt.callLater(tabs.revealActive); }
    }
    Row {
        id: tabRow
        height: 56
        Repeater {
            id: tabRepeater
            model: tabs.files.tabs
            delegate: Item {
                id: fileTab
                required property var modelData
                readonly property var buffer: tabs.files.buffers[tabs.files.source(modelData.nodeId, modelData.path)]
                readonly property bool selected: modelData.key === tabs.files.activeKey
                readonly property string filename: modelData.path.split("/").pop()
                readonly property string title: {
                    const matches = tabs.files.tabs.filter(tab => tab.path.split("/").pop() === filename);
                    if (matches.length < 2) return filename;
                    const sameMachine = matches.filter(tab => tab.nodeId === modelData.nodeId).length > 1;
                    const areas = matches.some(tab => tab.path.startsWith("/")) && matches.some(tab => !tab.path.startsWith("/"));
                    return modelData.nodeId + " / " + (areas ? (modelData.path.startsWith("/") ? "System" : "Home / ") : "") + (sameMachine ? modelData.path : filename);
                }
                objectName: "fileTab-" + modelData.key
                width: Math.min(Math.max(160, titleMetrics.advanceWidth + 108), Math.max(160, Math.min(360, tabs.width)))
                height: 56
                TextMetrics { id: titleMetrics; text: fileTab.title; font: tabLabel.font }
                Rectangle {
                    anchors.fill: parent
                    anchors.margins: 4
                    radius: Studio.Theme.shapeMedium
                    color: fileTab.selected ? Studio.Theme.surfaceContainerHigh
                        : activate.hovered || close.hovered ? Studio.Theme.surfaceContainer : "transparent"
                    border.width: activate.visualFocus ? 2 : 0
                    border.color: Studio.Theme.primary
                    Behavior on color { ColorAnimation { duration: Studio.Theme.stateDuration } }
                }
                Button {
                    id: activate
                    objectName: "fileTabSelect-" + fileTab.modelData.key
                    anchors.left: parent.left
                    anchors.right: close.left
                    height: parent.height
                    padding: 0
                    Accessible.name: fileTab.modelData.nodeId + " / " + fileTab.modelData.path
                    Accessible.role: Accessible.PageTab
                    Accessible.selected: fileTab.selected
                    background: null
                    contentItem: Item {
                        Studio.Icon {
                            anchors.left: parent.left
                            anchors.leftMargin: 16
                            anchors.verticalCenter: parent.verticalCenter
                            name: fileTab.buffer && fileTab.buffer.dirty ? "edit" : "description"
                            size: 20
                            color: fileTab.selected ? Studio.Theme.primary : Studio.Theme.textOnSurfaceVariant
                        }
                        Label {
                            id: tabLabel
                            objectName: "fileTabLabel-" + fileTab.modelData.key
                            anchors.left: parent.left
                            anchors.leftMargin: 44
                            anchors.right: parent.right
                            anchors.rightMargin: 8
                            anchors.verticalCenter: parent.verticalCenter
                            text: fileTab.title
                            textFormat: Text.PlainText
                            font.family: Studio.Theme.fontFamily
                            font.pixelSize: Studio.Theme.labelLarge
                            font.weight: Font.Medium
                            elide: Text.ElideMiddle
                            color: fileTab.selected ? Studio.Theme.textOnSurface : Studio.Theme.textOnSurfaceVariant
                        }
                    }
                    onClicked: tabs.files.activeKey = fileTab.modelData.key
                    onActiveFocusChanged: if (activeFocus) tabs.reveal(fileTab)
                }
                Studio.StudioIconButton {
                    id: close
                    objectName: "fileTabClose-" + fileTab.modelData.key
                    anchors.right: parent.right
                    anchors.rightMargin: 4
                    anchors.verticalCenter: parent.verticalCenter
                    width: 48
                    height: 48
                    iconName: "close"
                    iconSize: 20
                    description: qsTr("Đóng %1").arg(fileTab.filename)
                    onClicked: tabs.files.close(fileTab.modelData.key)
                    onActiveFocusChanged: if (activeFocus) tabs.reveal(fileTab)
                }
                Rectangle {
                    anchors.bottom: parent.bottom
                    anchors.horizontalCenter: parent.horizontalCenter
                    width: parent.width - 32
                    height: 3
                    radius: 2
                    color: Studio.Theme.primary
                    visible: fileTab.selected
                }
            }
        }
    }
}
