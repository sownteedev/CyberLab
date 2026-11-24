import QtQuick
import QtQuick.Controls.Basic
import "../.." as Studio

Rectangle {
    id: panel
    required property var entry
    required property string contextKey
    property bool readOnly: false
    signal edited(string text)
    implicitHeight: 300
    radius: Studio.Theme.shapeMedium
    color: Studio.Theme.surfaceContainer
    border.width: code.activeFocus ? Studio.Theme.focusWidth : Studio.Theme.borderWidth
    border.color: code.activeFocus ? Studio.Theme.primary : Studio.Theme.outlineVariant

    Flickable {
        id: scroll
        anchors.fill: parent
        anchors.margins: Studio.Theme.space4
        clip: true
        contentWidth: Math.max(width, measure.implicitWidth + gutter.width + 32)
        contentHeight: Math.max(height, code.implicitHeight)
        boundsBehavior: Flickable.StopAtBounds
        ScrollBar.vertical: ScrollBar {}
        ScrollBar.horizontal: ScrollBar {}
        Text { id: measure; visible: false; text: code.text; font: code.font; textFormat: Text.PlainText }
        Text {
            id: gutter
            objectName: "startupLineNumbers"
            width: Math.max(48, implicitWidth + 24)
            height: scroll.contentHeight
            topPadding: code.topPadding
            rightPadding: 12
            horizontalAlignment: Text.AlignRight
            text: Array.from({length: code.lineCount}, (_, index) => String(index + 1)).join("\n")
            font: code.font
            color: Studio.Theme.dark ? "#8491a6" : "#5f6d80"
            Accessible.ignored: true
            Rectangle { anchors.right: parent.right; width: 1; height: parent.height; color: Studio.Theme.outlineVariant }
        }
        Text {
            id: syntax
            objectName: "startupSyntax"
            x: gutter.width + code.leftPadding
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
            active: panel.visible && !!panel.entry && panel.entry.ready
            sourceComponent: Studio.CodeSyntaxWorker {
                text: code.text
                language: "bash"
                dark: Studio.Theme.dark
            }
        }
        TextArea {
            id: code
            property string editingContext: ""
            objectName: "startupScriptText"
            Accessible.name: qsTr("Nội dung script khởi động")
            x: gutter.width
            width: scroll.contentWidth - gutter.width
            height: scroll.contentHeight
            enabled: !!panel.entry && panel.entry.ready
            readOnly: panel.readOnly
            text: panel.entry ? panel.entry.text : ""
            textFormat: TextEdit.PlainText
            wrapMode: TextEdit.NoWrap
            font.family: Studio.Theme.monoFamily
            font.pixelSize: Studio.Theme.bodyLarge
            padding: Studio.Theme.space16
            color: syntax.visible ? "transparent" : Studio.Theme.textOnSurface
            selectionColor: Studio.Theme.primaryContainer
            selectedTextColor: Studio.Theme.textOnPrimaryContainer
            selectByMouse: true
            background: null
            cursorDelegate: Rectangle {
                width: 2
                height: code.cursorRectangle.height
                color: Studio.Theme.primary
                visible: code.cursorVisible
            }
            onActiveFocusChanged: if (activeFocus) editingContext = panel.contextKey
            onTextChanged: if (activeFocus && !readOnly && panel.entry && panel.entry.ready && editingContext === panel.contextKey && text !== panel.entry.text)
                panel.edited(text)
            onCursorRectangleChanged: {
                if (!activeFocus) return;
                const cursor = cursorRectangle;
                if (cursor.y < scroll.contentY) scroll.contentY = cursor.y;
                else if (cursor.y + cursor.height > scroll.contentY + scroll.height)
                    scroll.contentY = cursor.y + cursor.height - scroll.height;
                const horizontal = gutter.width + cursor.x;
                if (horizontal < scroll.contentX) scroll.contentX = horizontal;
                else if (horizontal + cursor.width > scroll.contentX + scroll.width)
                    scroll.contentX = horizontal + cursor.width - scroll.width;
            }
            Keys.onPressed: event => {
                if (!readOnly && event.key === Qt.Key_Tab) {
                    remove(selectionStart, selectionEnd);
                    insert(cursorPosition, "    ");
                    event.accepted = true;
                }
            }
        }
    }
}
