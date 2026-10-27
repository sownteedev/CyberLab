import QtQuick
import QtQuick.Controls.Basic
import QtQuick.Layouts
import ".."
import ".." as Studio

RowLayout {
    id: row
    required property var entry
    property bool canExport: false
    property bool showMetadata: true
    signal exportRequested(string path, bool directory)
    Layout.minimumWidth: 0
    spacing: Studio.Theme.space8
    Label {
        Layout.minimumWidth: 0
        Layout.maximumWidth: Studio.Theme.space32 * 2
        text: row.entry.branch
        elide: Text.ElideLeft
        color: Studio.Theme.textOnSurfaceVariant
        font.family: Studio.Theme.monoFamily
        font.pixelSize: Studio.Theme.bodySmall
        Layout.alignment: Qt.AlignVCenter
    }
    Icon {
        name: row.entry.isDirectory ? "folder" : "description"
        size: Studio.Theme.iconSmall
        color: row.entry.isDirectory ? Studio.Theme.primary : Studio.Theme.textOnSurfaceVariant
    }
    Label {
        Layout.fillWidth: true
        Layout.minimumWidth: 0
        text: row.entry.name
        textFormat: Text.PlainText
        color: row.entry.isDirectory ? Studio.Theme.primary : Studio.Theme.textOnSurface
        font.family: Studio.Theme.monoFamily
        font.pixelSize: Studio.Theme.bodySmall
        elide: Text.ElideMiddle
        Accessible.name: row.entry.path
        ToolTip.visible: fileHover.hovered
        ToolTip.text: row.entry.path
        HoverHandler { id: fileHover }
    }
    Label {
        Layout.minimumWidth: 0
        Layout.maximumWidth: Studio.Theme.space32 * 2
        elide: Text.ElideRight
        visible: row.showMetadata && !row.entry.isDirectory
        text: row.entry.live ? (row.entry.kind === "file" ? row.entry.size + " B" : row.entry.kind)
                            : (row.entry.isImport ? "Đã nhập" : "Ban đầu")
        color: row.entry.isImport ? Studio.Theme.success : Studio.Theme.textOnSurfaceVariant
        font.pixelSize: Studio.Theme.labelSmall
        Layout.alignment: Qt.AlignVCenter
    }
    StudioIconButton {
        objectName: "exportTreeEntry"
        Layout.minimumWidth: Studio.Theme.controlHeight
        Layout.maximumWidth: Studio.Theme.controlHeight
        visible: row.entry.live && (row.entry.kind === "file" || row.entry.kind === "directory")
        enabled: row.canExport
        iconName: "download"
        description: row.entry.isDirectory ? "Xuất thư mục thành file tar" : "Lưu file về VM"
        onClicked: row.exportRequested(row.entry.path, row.entry.isDirectory)
    }
}
