pragma ComponentBehavior: Bound

import QtQuick
import QtQuick.Controls.Basic
import QtQuick.Layouts
import "../.."
import "../.." as Studio

StudioSurface {
    id: header
    required property var lab
    property bool running: false
    property bool saved: false
    implicitHeight: details.implicitHeight + Studio.Theme.space32
    color: Studio.Theme.surfaceContainer
    ColumnLayout {
        id: details
        anchors.fill: parent
        anchors.margins: Studio.Theme.space16
        spacing: Studio.Theme.space8
        Label {
            objectName: "libraryLabTitle"
            Layout.fillWidth: true
            Layout.minimumWidth: 0
            text: header.lab ? header.lab.name : ""
            font.family: Studio.Theme.fontFamily
            font.pixelSize: Studio.Theme.titleLarge
            font.weight: Font.DemiBold
            color: Studio.Theme.textOnSurface
            wrapMode: Text.Wrap
            maximumLineCount: 2
            elide: Text.ElideRight
        }
        Label {
            Layout.fillWidth: true
            Layout.minimumWidth: 0
            text: header.lab ? header.lab.id + " · v" + header.lab.version : ""
            font.pixelSize: Studio.Theme.bodySmall
            color: Studio.Theme.textOnSurfaceVariant
            elide: Text.ElideMiddle
        }
        Flow {
            id: tags
            objectName: "libraryLabTags"
            Layout.fillWidth: true
            Layout.preferredHeight: implicitHeight
            spacing: Studio.Theme.space8
            StatusBadge {
                text: header.running ? "Đang chạy" : header.saved ? "Đã tạm dừng" : "Sẵn sàng"
                iconName: header.running ? "terminal" : header.saved ? "bookmark" : "check_circle"
                bgColor: header.running ? Studio.Theme.successContainer : header.saved ? Studio.Theme.warningContainer : Studio.Theme.surfaceContainerHigh
                textColor: header.running ? Studio.Theme.textOnSuccessContainer : header.saved ? Studio.Theme.textOnWarningContainer : Studio.Theme.textOnSurface
                dotColor: textColor
                maximumWidth: tags.width
            }
            StatusBadge {
                visible: !!header.lab && (header.lab.networks || []).length > 0
                text: header.lab ? header.lab.networks.length + " mạng" : ""
                description: header.lab ? header.lab.networks.join(", ") : ""
                iconName: "lan"
                maximumWidth: tags.width
                bgColor: Studio.Theme.surfaceContainerHigh
                textColor: Studio.Theme.textOnSurfaceVariant
                dotColor: Studio.Theme.network
            }
            StatusBadge {
                text: header.lab ? (header.lab.nodes || []).length + " máy" : ""
                description: header.lab ? (header.lab.environments || []).map(node =>
                    (node[2] ? node[2] + "@" : "") + (node[1] || node[0])).join(", ") : ""
                iconName: "terminal"
                maximumWidth: tags.width
                bgColor: Studio.Theme.surfaceContainerHigh
                textColor: Studio.Theme.textOnSurfaceVariant
                dotColor: Studio.Theme.textOnSurfaceVariant
            }
        }
    }
}
