import QtQuick
import QtQuick.Controls.Basic
import QtQuick.Layouts
import ".."
import ".." as Studio

RowLayout {
    id: row

    property bool canExport: false
    required property var entry
    property bool showMetadata: true

    signal exportRequested(string path, bool directory)

    Layout.minimumWidth: 0
    spacing: Studio.Theme.space8

    Layout.fillWidth: true
    Layout.preferredHeight: Studio.Theme.space32

    Item {
        id: treeGuide

        readonly property int depth: row.entry && typeof row.entry.depth === "number" ? row.entry.depth : 0
        readonly property var guides: row.entry && Array.isArray(row.entry.guides) ? row.entry.guides : []
        readonly property bool isLast: row.entry && typeof row.entry.isLast === "boolean" ? row.entry.isLast : false
        readonly property real stepWidth: 16
        readonly property color lineColor: Qt.alpha(Studio.Theme.textOnSurfaceVariant, 0.35)

        Layout.alignment: Qt.AlignVCenter
        Layout.preferredWidth: Math.max(stepWidth, (depth + 1) * stepWidth)
        Layout.preferredHeight: row.Layout.preferredHeight
        Layout.fillHeight: true

        Repeater {
            model: treeGuide.guides

            Rectangle {
                required property int index
                required property bool modelData

                visible: modelData
                x: index * treeGuide.stepWidth + Math.round(treeGuide.stepWidth / 2)
                width: 1
                anchors.top: parent.top
                anchors.bottom: parent.bottom
                color: treeGuide.lineColor
            }
        }

        Item {
            x: treeGuide.depth * treeGuide.stepWidth
            width: treeGuide.stepWidth
            anchors.top: parent.top
            anchors.bottom: parent.bottom

            Rectangle {
                x: Math.round(treeGuide.stepWidth / 2)
                width: 1
                y: 0
                height: treeGuide.isLast ? Math.round(parent.height / 2) : parent.height
                color: treeGuide.lineColor
            }

            Rectangle {
                x: Math.round(treeGuide.stepWidth / 2)
                width: treeGuide.stepWidth - Math.round(treeGuide.stepWidth / 2)
                y: Math.round(parent.height / 2)
                height: 1
                color: treeGuide.lineColor
            }
        }
    }
    Icon {
        Layout.alignment: Qt.AlignVCenter
        color: row.entry.isDirectory ? Studio.Theme.primary : Studio.Theme.textOnSurfaceVariant
        name: row.entry.isDirectory ? "folder" : "description"
        size: Studio.Theme.iconSmall
    }
    Label {
        Accessible.name: row.entry.path
        Layout.fillWidth: true
        Layout.minimumWidth: 0
        ToolTip.text: row.entry.path
        ToolTip.visible: fileHover.hovered
        color: row.entry.isDirectory ? Studio.Theme.primary : Studio.Theme.textOnSurface
        elide: Text.ElideMiddle
        font.family: Studio.Theme.monoFamily
        font.pixelSize: Studio.Theme.bodySmall
        text: row.entry.name
        textFormat: Text.PlainText

        HoverHandler {
            id: fileHover
        }
    }
    Label {
        Layout.alignment: Qt.AlignVCenter
        Layout.maximumWidth: Studio.Theme.space32 * 2
        Layout.minimumWidth: 0
        color: row.entry.isImport ? Studio.Theme.success : Studio.Theme.textOnSurfaceVariant
        elide: Text.ElideRight
        font.pixelSize: Studio.Theme.labelSmall
        text: row.entry.live ? (row.entry.kind === "file" ? row.entry.size + " B" : row.entry.kind) : (row.entry.isImport ? "Đã nhập" : "Ban đầu")
        visible: row.showMetadata && !row.entry.isDirectory
    }
    StudioIconButton {
        Layout.alignment: Qt.AlignVCenter
        Layout.maximumWidth: Studio.Theme.controlHeight - Studio.Theme.space16
        Layout.minimumWidth: Studio.Theme.controlHeight - Studio.Theme.space16
        Layout.preferredHeight: Studio.Theme.controlHeight - Studio.Theme.space16
        description: row.entry.isDirectory ? "Xuất thư mục thành file tar" : "Lưu file về VM"
        enabled: row.canExport
        iconName: "download"
        objectName: "exportTreeEntry"
        visible: row.entry.live && (row.entry.kind === "file" || row.entry.kind === "directory")

        onClicked: row.exportRequested(row.entry.path, row.entry.isDirectory)
    }
}
