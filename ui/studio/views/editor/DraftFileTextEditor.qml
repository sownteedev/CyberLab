pragma ComponentBehavior: Bound
import QtQuick
import QtQuick.Controls.Basic
import QtQuick.Layouts
import "../../models/CodeLanguage.js" as Syntax
import "../.." as Studio
import "../../models/Messages.js" as Messages

ColumnLayout {
    id: panel
    required property var files
    required property var tab
    readonly property string source: files.source(tab.nodeId, tab.path)
    readonly property var entry: files.buffers[source] || ({text: "", ready: false, error: ""})
    property bool searching: false
    spacing: 0

    function findNext() {
        if (!search.text) return;
        let index = code.text.toLowerCase().indexOf(search.text.toLowerCase(), code.selectionEnd);
        if (index < 0) index = code.text.toLowerCase().indexOf(search.text.toLowerCase());
        if (index >= 0) { code.select(index, index + search.text.length); code.forceActiveFocus(); }
    }
    RowLayout {
        Layout.fillWidth: true
        Layout.leftMargin: 16
        Layout.rightMargin: 4
        Layout.topMargin: 4
        Layout.bottomMargin: 4
        spacing: 8
        Studio.Icon { name: "terminal"; size: 20; color: Studio.Theme.textOnSurfaceVariant }
        Label {
            Layout.fillWidth: true
            elide: Text.ElideMiddle
            text: panel.tab.nodeId + " / " + (panel.tab.path.startsWith("/") ? "System" : "Home / ") + panel.tab.path
            color: Studio.Theme.textOnSurfaceVariant
            font.pixelSize: Studio.Theme.bodySmall
        }
        Studio.StudioIconButton {
            iconName: "search"
            description: qsTr("Tìm trong file")
            enabled: panel.entry.ready
            onClicked: { panel.searching = !panel.searching; if (panel.searching) search.forceActiveFocus(); }
        }
    }
    Rectangle { Layout.fillWidth: true; implicitHeight: 1; color: Studio.Theme.outlineVariant; opacity: 0.5 }
    RowLayout {
        Layout.fillWidth: true
        Layout.leftMargin: 12
        Layout.rightMargin: 12
        visible: panel.searching
        Studio.StudioTextField {
            id: search
            Layout.fillWidth: true
            placeholderText: qsTr("Tìm trong file")
            onAccepted: panel.findNext()
            Keys.onEscapePressed: { panel.searching = false; code.forceActiveFocus(); }
        }
        Studio.StudioIconButton { iconName: "chevron_right"; description: qsTr("Kết quả tiếp theo"); onClicked: panel.findNext() }
        Studio.StudioIconButton { iconName: "close"; description: qsTr("Đóng tìm kiếm"); onClicked: panel.searching = false }
    }
    Flickable {
        id: scroll
        Layout.fillWidth: true
        Layout.fillHeight: true
        visible: panel.entry.ready
        clip: true
        contentWidth: Math.max(width, measure.implicitWidth + gutter.width + 24)
        contentHeight: Math.max(height, measure.implicitHeight + 32)
        boundsBehavior: Flickable.StopAtBounds
        ScrollBar.vertical: ScrollBar {}
        ScrollBar.horizontal: ScrollBar {}
        Text { id: measure; visible: false; text: code.text; font: code.font; textFormat: Text.PlainText }
        Row {
            width: scroll.contentWidth
            height: scroll.contentHeight
            Text {
                id: gutter
                objectName: "fileLines-" + panel.tab.key
                width: Math.max(48, implicitWidth + 24)
                height: scroll.contentHeight
                topPadding: 16
                rightPadding: 16
                horizontalAlignment: Text.AlignRight
                font.family: Studio.Theme.monoFamily
                font.pixelSize: Studio.Theme.bodyMedium
                color: Studio.Theme.dark ? "#8491a6" : "#5f6d80"
                text: Array.from({length: code.lineCount}, (_, index) => String(index + 1)).join("\n")
                Rectangle { anchors.right: parent.right; height: parent.height; width: 1; color: Studio.Theme.outlineVariant; opacity: 0.5 }
            }
            Item {
                width: parent.width - gutter.width
                height: scroll.contentHeight
            Text {
                id: syntax
                objectName: "fileSyntax-" + panel.tab.key
                readonly property string language: Syntax.languageFor(panel.tab.path, code.text)
                x: code.leftPadding
                y: code.topPadding
                font: code.font
                textFormat: Text.StyledText
                wrapMode: Text.NoWrap
                color: Studio.Theme.textOnSurface
                text: highlighter.item ? highlighter.item.markup : ""
                visible: text.length > 0 && !code.inputMethodComposing
                Accessible.ignored: true
            }
            Loader {
                id: highlighter
                active: panel.visible && panel.entry.ready && syntax.language.length > 0
                sourceComponent: Studio.CodeSyntaxWorker {
                    text: code.text
                    language: syntax.language
                    dark: Studio.Theme.dark
                }
            }
            TextArea {
                id: code
                objectName: "fileText-" + panel.tab.key
                Accessible.name: panel.tab.nodeId + " / " + panel.tab.path
                width: parent.width
                height: scroll.contentHeight
                padding: 16
                leftPadding: 12
                color: syntax.visible ? "transparent" : Studio.Theme.textOnSurface
                cursorDelegate: Rectangle {
                    width: 2
                    height: code.cursorRectangle.height
                    color: Studio.Theme.primary
                    visible: code.cursorVisible
                }
                selectionColor: Studio.Theme.primaryContainer
                selectedTextColor: Studio.Theme.textOnPrimaryContainer
                font.family: Studio.Theme.monoFamily
                font.pixelSize: Studio.Theme.bodyMedium
                selectByMouse: true
                readOnly: panel.tab.path.startsWith("/") && !panel.files.setupSupported
                wrapMode: TextEdit.NoWrap
                textFormat: TextEdit.PlainText
                text: panel.entry.text || ""
                background: null
                PointHandler {
                    id: selectionPointer
                    acceptedButtons: Qt.LeftButton
                    acceptedDevices: PointerDevice.Mouse | PointerDevice.TouchPad
                    target: null
                    property int anchor: 0
                    onActiveChanged: if (active) {
                        anchor = point.modifiers & Qt.ShiftModifier
                            ? (code.cursorPosition === code.selectionStart ? code.selectionEnd : code.selectionStart)
                            : code.positionAt(point.position.x, point.position.y);
                    }
                }
                Timer {
                    interval: 16
                    repeat: true
                    running: selectionPointer.active && panel.visible && panel.entry.ready && code.activeFocus
                        && Math.abs(selectionPointer.point.scenePosition.x - selectionPointer.point.scenePressPosition.x) > 4
                    onTriggered: {
                        const pointer = scroll.mapFromItem(null, selectionPointer.point.scenePosition.x, selectionPointer.point.scenePosition.y);
                        const edge = 24;
                        const distance = pointer.x < edge ? pointer.x - edge
                            : pointer.x > scroll.width - edge ? pointer.x - (scroll.width - edge) : 0;
                        if (!distance) return;
                        const step = Math.sign(distance) * Math.min(18, Math.max(2, Math.abs(distance) / 2));
                        const next = Math.max(0, Math.min(scroll.contentWidth - scroll.width, scroll.contentX + step));
                        if (next === scroll.contentX) return;
                        scroll.contentX = next;
                        const position = code.mapFromItem(scroll, Math.max(0, Math.min(scroll.width, pointer.x)),
                            Math.max(0, Math.min(scroll.height, pointer.y)));
                        code.select(selectionPointer.anchor, code.positionAt(position.x, position.y));
                    }
                }
                onTextChanged: if (activeFocus && panel.entry.ready && text !== panel.entry.text)
                    panel.files.edit(panel.tab.nodeId, panel.tab.path, text)
                Keys.onPressed: event => {
                    if (code.readOnly) return;
                    if (event.key === Qt.Key_Tab) {
                        code.remove(code.selectionStart, code.selectionEnd);
                        code.insert(code.cursorPosition, "    ");
                        event.accepted = true;
                    } else if (event.key === Qt.Key_Backtab) {
                        const start = code.text.lastIndexOf("\n", Math.max(0, code.cursorPosition - 1)) + 1;
                        const indentation = code.text.substring(start).match(/^( {1,4}|\t)/);
                        if (indentation) code.remove(start, start + indentation[0].length);
                        event.accepted = true;
                    } else if (event.key === Qt.Key_F && (event.modifiers & Qt.ControlModifier)) {
                        panel.searching = true;
                        search.forceActiveFocus();
                        event.accepted = true;
                    }
                }
                onCursorRectangleChanged: {
                    const flick = scroll;
                    if (!activeFocus || !flick) return;
                    if (cursorRectangle.y < flick.contentY) flick.contentY = cursorRectangle.y;
                    else if (cursorRectangle.y + cursorRectangle.height > flick.contentY + flick.height)
                        flick.contentY = cursorRectangle.y + cursorRectangle.height - flick.height;
                }
            }
            }
        }
    }
    Item {
        Layout.fillWidth: true
        Layout.fillHeight: true
        visible: !panel.entry.ready
        ColumnLayout {
            anchors.centerIn: parent
            width: Math.max(0, parent.width - 32)
            Label {
                Layout.fillWidth: true
                horizontalAlignment: Text.AlignHCenter
                wrapMode: Text.Wrap
                color: Studio.Theme.textOnSurfaceVariant
                text: panel.entry.binary ? qsTr("File nhị phân hoặc lớn hơn 64 KiB — không sửa tại đây.")
                    : Messages.text(panel.entry.error) || qsTr("Đang mở file…")
                textFormat: Text.PlainText
                Studio.ErrorNotifier { message: panel.entry.error || "" }
            }
            Studio.StudioButton {
                Layout.alignment: Qt.AlignHCenter
                visible: !!panel.entry.error
                text: qsTr("Thử lại")
                onClicked: panel.files.loadSource(panel.source)
            }
        }
    }
}
