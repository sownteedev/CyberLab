pragma ComponentBehavior: Bound

import QtQuick
import QtQuick.Controls.Basic
import QtQuick.Layouts
import QtQml.Models
import ".." as Studio
import "../models/FilePickerPaths.js" as Paths

Rectangle {
    id: browser

    required property var model
    required property var selection
    required property string selectedDirectory
    required property bool loading
    required property int entryCount
    signal entryPressed(url url, bool directory, string name)
    signal entryActivated(url url, bool directory, string name)

    objectName: "filePickerList"
    implicitWidth: 440
    implicitHeight: 320
    color: Studio.Theme.surfaceContainerLow
    radius: Studio.Theme.shapeLarge

    function columns() {
        return Math.max(1, Math.floor(entries.width / 132));
    }
    function focusList() {
        entries.currentIndex = entries.count ? 0 : -1;
        entries.forceActiveFocus(Qt.TabFocusReason);
    }
    function chooseCurrent(activate) {
        if (entries.currentIndex < 0 || entries.currentIndex >= visibleEntries.items.count)
            return;
        const entry = visibleEntries.items.get(entries.currentIndex).model;
        if (activate)
            entryActivated(entry.fileUrl, entry.fileIsDir, entry.fileName);
        else
            entryPressed(entry.fileUrl, entry.fileIsDir, entry.fileName);
    }

    GridView {
        id: entries

        objectName: "filePickerEntries"
        anchors.fill: parent
        anchors.margins: Studio.Theme.space8
        clip: true
        reuseItems: true
        activeFocusOnTab: true
        boundsBehavior: Flickable.StopAtBounds
        cellWidth: width / browser.columns()
        cellHeight: 144
        keyNavigationWraps: false
        ScrollBar.vertical: ScrollBar {}

        model: DelegateModel {
            id: visibleEntries
            model: browser.model
            items.onChanged: (removed, inserted) => {
                for (let change = inserted.length - 1; change >= 0; change--) {
                    const range = inserted[change];
                    for (let offset = range.index + range.count - 1; offset >= range.index; offset--) {
                        const name = items.get(offset).model.fileName;
                        if (name === "." || name === "..")
                            items.remove(offset, 1);
                    }
                }
            }
            delegate: ItemDelegate {
                id: entry

                required property int index
                required property string fileName
                required property url fileUrl
                required property bool fileIsDir
                required property double fileSize
                readonly property int viewIndex: DelegateModel.itemsIndex
                readonly property string identity: Paths.fromPath(Paths.localPath(fileUrl))
                readonly property bool chosen: browser.selection.includes(identity) || browser.selectedDirectory === identity
                readonly property bool imageFile: !fileIsDir && Paths.isImage(fileName)

                objectName: "filePickerEntry-" + index
                width: entries.cellWidth - Studio.Theme.space8
                height: entries.cellHeight - Studio.Theme.space8
                padding: Studio.Theme.space8
                hoverEnabled: true
                focusPolicy: Qt.NoFocus
                Accessible.name: fileName
                Accessible.description: fileIsDir ? "Thư mục. Nhấn Enter hoặc nhấp đúp để mở." : "File"
                Accessible.selected: chosen

                background: Rectangle {
                    radius: Studio.Theme.shapeLarge
                    color: entry.chosen ? Studio.Theme.primaryContainer : Studio.Theme.transparent
                    border.width: entry.GridView.isCurrentItem && entries.activeFocus ? Studio.Theme.focusWidth : 0
                    border.color: Studio.Theme.primary

                    Rectangle {
                        objectName: "filePickerEntryState"
                        anchors.fill: parent
                        anchors.margins: Studio.Theme.borderWidth
                        color: Studio.Theme.textOnSurface
                        opacity: entry.down ? 0.12 : entry.hovered ? 0.08 : 0
                        radius: parent.radius - Studio.Theme.borderWidth

                        Behavior on opacity {
                            NumberAnimation {
                                duration: Studio.Theme.stateDuration
                                easing.type: Easing.OutCubic
                            }
                        }
                    }
                }
                contentItem: ColumnLayout {
                    spacing: Studio.Theme.space4

                    Item {
                        Layout.fillWidth: true
                        Layout.preferredHeight: 76

                        Item {
                            id: thumbnail

                            anchors.fill: parent

                            Image {
                                id: thumbnailImage
                                objectName: "filePickerThumbnail"

                                anchors.fill: parent
                                anchors.margins: Studio.Theme.space4
                                asynchronous: true
                                fillMode: Image.PreserveAspectFit
                                source: entry.imageFile && !entry.fileIsDir ? entry.fileUrl : ""
                                sourceSize: Qt.size(240, 152)
                                visible: status === Image.Ready
                                Accessible.ignored: true
                            }
                            Studio.Icon {
                                anchors.centerIn: parent
                                color: entry.fileIsDir ? Studio.Theme.primary : Studio.Theme.textOnSurfaceVariant
                                name: entry.fileIsDir ? "folder" : "description"
                                size: 52
                                visible: !thumbnailImage.visible
                            }
                            Studio.Icon {
                                anchors.top: parent.top
                                anchors.right: parent.right
                                name: "check_circle"
                                color: Studio.Theme.primary
                                size: Studio.Theme.iconSmall
                                visible: entry.chosen
                            }
                        }
                    }
                    Label {
                        Layout.alignment: Qt.AlignHCenter
                        Layout.fillWidth: true
                        Layout.minimumWidth: 0
                        text: entry.fileName
                        textFormat: Text.PlainText
                        elide: Text.ElideMiddle
                        horizontalAlignment: Text.AlignHCenter
                        color: entry.chosen ? Studio.Theme.textOnPrimaryContainer : Studio.Theme.textOnSurface
                        font.family: Studio.Theme.fontFamily
                        font.pixelSize: Studio.Theme.labelLarge
                        font.weight: Font.Medium
                    }
                    Label {
                        Layout.alignment: Qt.AlignHCenter
                        text: entry.fileIsDir ? "Thư mục" : Paths.sizeLabel(entry.fileSize)
                        color: entry.chosen ? Studio.Theme.textOnPrimaryContainer : Studio.Theme.textOnSurfaceVariant
                        font.pixelSize: Studio.Theme.bodySmall
                    }
                }

                onClicked: {
                    if (browser.loading || viewIndex < 0 || viewIndex >= entries.count)
                        return;
                    entries.currentIndex = viewIndex;
                    entries.forceActiveFocus(Qt.MouseFocusReason);
                    browser.entryPressed(fileUrl, fileIsDir, fileName);
                }
                onDoubleClicked: browser.entryActivated(fileUrl, fileIsDir, fileName)
            }
        }

        onCountChanged: if (currentIndex < 0 || currentIndex >= count)
            currentIndex = count ? 0 : -1
        Keys.onReturnPressed: browser.chooseCurrent(true)
        Keys.onEnterPressed: browser.chooseCurrent(true)
        Keys.onSpacePressed: browser.chooseCurrent(false)
        Keys.onDownPressed: currentIndex = count ? Math.min(count - 1, currentIndex + browser.columns()) : -1
        Keys.onUpPressed: currentIndex = count ? Math.max(0, currentIndex - browser.columns()) : -1
        Keys.onLeftPressed: currentIndex = count ? Math.max(0, currentIndex - 1) : -1
        Keys.onRightPressed: currentIndex = count ? Math.min(count - 1, currentIndex + 1) : -1
        Keys.onPressed: event => {
            if (event.key === Qt.Key_Home) {
                currentIndex = count ? 0 : -1;
                event.accepted = true;
            } else if (event.key === Qt.Key_End) {
                currentIndex = count - 1;
                event.accepted = true;
            }
        }
    }
    Label {
        anchors.centerIn: parent
        width: parent.width - Studio.Theme.space32
        visible: browser.loading || browser.entryCount === 0
        text: browser.loading ? "Đang đọc thư mục…" : "Không có mục phù hợp\nThử chọn loại file hoặc thư mục khác."
        horizontalAlignment: Text.AlignHCenter
        wrapMode: Text.WordWrap
        color: Studio.Theme.textOnSurfaceVariant
        font.pixelSize: Studio.Theme.bodyMedium
    }
}
