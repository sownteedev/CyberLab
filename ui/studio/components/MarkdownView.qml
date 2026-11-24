import QtQuick
import QtQuick.Controls.Basic
import ".."
import ".." as Studio
import "../models/MarkdownFormat.js" as MarkdownFormat

ScrollView {
    id: view

    property string markdown: ""
    property string formattedText: ""

    function render() {
        parser.text = "";
        parser.textFormat = TextEdit.MarkdownText;
        parser.text = MarkdownFormat.compact(markdown);
        parser.textFormat = TextEdit.RichText;
        formattedText = MarkdownFormat.readable(parser.getFormattedText(0, parser.length),
            String(Studio.Theme.outlineVariant), String(Studio.Theme.surfaceContainerHigh));
    }
    onMarkdownChanged: Qt.callLater(render)
    Component.onCompleted: render()
    Connections {
        target: Studio.Theme
        function onDarkChanged() { Qt.callLater(view.render); }
    }
    readonly property TextEdit parserObject: TextEdit {
        id: parser
        visible: false
        font.family: Studio.Theme.fontFamily
        font.pixelSize: 15
    }

    clip: true
    implicitWidth: 0

    background: Rectangle {
        border.color: Studio.Theme.outlineVariant
        border.width: Studio.Theme.borderWidth
        color: Studio.Theme.surfaceContainer
        radius: Studio.Theme.shapeLarge
    }

    contentItem: Flickable {
        id: scroll
        boundsBehavior: Flickable.StopAtBounds
        contentHeight: documentViewport.height
        contentWidth: documentViewport.width

        Item {
            id: documentViewport

            clip: true
            width: Math.max(scroll.width, documentText.contentWidth + documentText.leftPadding + documentText.rightPadding)
            height: documentText.implicitHeight

            TextArea {
                id: documentText

                background: null
                color: Studio.Theme.textOnSurface
                font.family: Studio.Theme.fontFamily
                font.pixelSize: 15
                objectName: "documentText"
                padding: Studio.Theme.space24
                readOnly: true
                selectByMouse: true
                selectedTextColor: Studio.Theme.textOnPrimaryContainer
                selectionColor: Studio.Theme.primaryContainer
                text: view.formattedText
                textFormat: TextEdit.RichText
                width: Math.min(scroll.width, 928)
                wrapMode: TextEdit.Wrap
            }
        }
    }
}
