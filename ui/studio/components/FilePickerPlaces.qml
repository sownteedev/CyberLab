pragma ComponentBehavior: Bound

import QtQuick
import QtQuick.Layouts
import QtCore
import ".." as Studio

ColumnLayout {
    id: places
    required property url currentFolder
    signal folderRequested(url folder)
    spacing: Studio.Theme.space4
    objectName: "filePickerPlaces"

    Repeater {
        model: [
            {label: "Thư mục cá nhân", icon: "folder", folder: StandardPaths.writableLocation(StandardPaths.HomeLocation)},
            {label: "Tải xuống", icon: "download", folder: StandardPaths.writableLocation(StandardPaths.DownloadLocation)},
            {label: "Tài liệu", icon: "description", folder: StandardPaths.writableLocation(StandardPaths.DocumentsLocation)},
            {label: "Hình ảnh", icon: "folder", folder: StandardPaths.writableLocation(StandardPaths.PicturesLocation)},
            {label: "Hệ thống file", icon: "desktop_windows", folder: "file:///"}
        ]
        delegate: Studio.StudioButton {
            required property var modelData
            Layout.fillWidth: true
            text: modelData.label
            iconName: modelData.icon
            leading: true
            flat: !selected
            selected: String(places.currentFolder) === String(modelData.folder)
            onClicked: places.folderRequested(modelData.folder)
        }
    }
    Item { Layout.fillHeight: true }
}
