import QtQuick
import QtQuick.Controls.Basic
import QtQuick.Layouts
import ".." as Studio
import "../models/FilePickerPaths.js" as Paths

Rectangle {
    id: preview

    property bool directory: false
    property real fileSize: 0
    property string fileName: ""
    property url fileUrl: ""
    property var modified: null
    readonly property bool imageFile: !directory && Paths.isImage(fileName)

    color: Studio.Theme.surfaceContainerHigh
    radius: Studio.Theme.shapeLarge
    implicitWidth: 256
    implicitHeight: 320
    objectName: "filePickerPreview"

    ColumnLayout {
        anchors.fill: parent
        anchors.margins: Studio.Theme.space12
        spacing: Studio.Theme.space12

        Label {
            Layout.fillWidth: true
            color: Studio.Theme.textOnSurface
            font.pixelSize: Studio.Theme.titleSmall
            font.weight: Font.DemiBold
            text: "Xem trước"
        }
        Item {
            Layout.fillWidth: true
            Layout.fillHeight: true
            Layout.minimumHeight: 72
            Layout.preferredHeight: 220

            Item {
                anchors.fill: parent

                Image {
                    id: previewImage
                    objectName: "filePickerPreviewImage"

                    anchors.fill: parent
                    anchors.margins: Studio.Theme.space8
                    asynchronous: true
                    fillMode: Image.PreserveAspectFit
                    source: preview.imageFile ? preview.fileUrl : ""
                    sourceSize: Qt.size(560, 400)
                    visible: status === Image.Ready
                    Accessible.ignored: true
                }
                Studio.Icon {
                    anchors.centerIn: parent
                    color: preview.directory ? Studio.Theme.primary : Studio.Theme.textOnSurfaceVariant
                    name: preview.directory ? "folder" : "description"
                    size: 64
                    visible: !previewImage.visible
                }
            }
        }
        Label {
            Layout.fillWidth: true
            color: Studio.Theme.textOnSurface
            elide: Text.ElideMiddle
            font.pixelSize: Studio.Theme.titleSmall
            font.weight: Font.DemiBold
            text: preview.fileName || "Chưa chọn mục"
            textFormat: Text.PlainText
            horizontalAlignment: Text.AlignHCenter
        }
        ColumnLayout {
            Layout.fillWidth: true
            spacing: Studio.Theme.space4
            visible: preview.fileName.length > 0

            Label {
                color: Studio.Theme.textOnSurfaceVariant
                font.pixelSize: Studio.Theme.bodySmall
                text: preview.directory ? "Thư mục" : preview.imageFile ? "Hình ảnh" : "File"
            }
            Label {
                visible: preview.modified !== null
                Layout.fillWidth: true
                color: Studio.Theme.textOnSurfaceVariant
                elide: Text.ElideRight
                font.pixelSize: Studio.Theme.bodySmall
                text: preview.modified ? "Sửa: " + Qt.formatDateTime(preview.modified, "dd/MM/yyyy HH:mm") : ""
            }
            Label {
                Layout.fillWidth: true
                color: Studio.Theme.textOnSurfaceVariant
                elide: Text.ElideMiddle
                font.pixelSize: Studio.Theme.bodySmall
                text: preview.directory ? "Có thể mở để xem nội dung" : Paths.sizeLabel(preview.fileSize)
            }
            Label {
                Layout.fillWidth: true
                color: Studio.Theme.textOnSurfaceVariant
                elide: Text.ElideMiddle
                font.pixelSize: Studio.Theme.bodySmall
                text: Paths.localPath(preview.fileUrl)
                textFormat: Text.PlainText
            }
        }
    }
}
