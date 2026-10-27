import QtQuick
import QtQuick.Controls.Basic
import ".."
import ".." as Studio
import "../models/MarkdownFormat.js" as MarkdownFormat

ScrollView {
    id: view
    property string markdown: ""
    implicitWidth: 0
    clip: true
    background: Rectangle {
        radius: Studio.Theme.shapeLarge
        color: Studio.Theme.surfaceContainer
        border.width: Studio.Theme.borderWidth
        border.color: Studio.Theme.outlineVariant
    }
    Flickable {
        contentWidth: Math.max(width, documentText.contentWidth + documentText.leftPadding + documentText.rightPadding)
        contentHeight: documentText.implicitHeight
        boundsBehavior: Flickable.StopAtBounds
        TextArea {
            id: documentText
            objectName: "documentText"
            width: view.availableWidth
            text: MarkdownFormat.compact(view.markdown)
            readOnly: true
            textFormat: TextEdit.MarkdownText
            wrapMode: TextEdit.Wrap
            selectByMouse: true
            background: null
            color: Studio.Theme.textOnSurface
            selectionColor: Studio.Theme.primaryContainer
            selectedTextColor: Studio.Theme.textOnPrimaryContainer
            font.family: Studio.Theme.fontFamily
            font.pixelSize: Studio.Theme.bodyMedium
            padding: Studio.Theme.space16
            rightPadding: Math.max(padding, view.availableWidth - 880 - padding)
        }
    }
}
