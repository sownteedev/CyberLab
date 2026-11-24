pragma ComponentBehavior: Bound

import QtQuick
import QtQuick.Controls.Basic
import QtQuick.Layouts
import "../.." as Studio

Studio.StudioSurface {
    id: header

    required property var lab
    property bool running: false
    property string savedState: ""
    readonly property bool saved: savedState === "SUSPENDED" || savedState === "STOPPED"
    readonly property bool wide: width >= 640

    objectName: "libraryHeader"
    color: Studio.Theme.surfaceContainer
    implicitHeight: details.implicitHeight + Studio.Theme.space32

    GridLayout {
        id: details
        anchors.fill: parent
        anchors.margins: Studio.Theme.space16
        columns: header.wide ? 2 : 1
        columnSpacing: Studio.Theme.space24
        rowSpacing: Studio.Theme.space16

        ColumnLayout {
            id: identity
            objectName: "libraryLabIdentity"
            Layout.fillWidth: true
            Layout.minimumWidth: 0
            spacing: Studio.Theme.space12

            RowLayout {
                Layout.fillWidth: true
                spacing: Studio.Theme.space12
                Rectangle {
                    Layout.preferredWidth: 44
                    Layout.preferredHeight: 44
                    radius: Studio.Theme.shapeLarge
                    color: Studio.Theme.primaryContainer
                    Studio.Icon {
                        anchors.centerIn: parent
                        name: "science"
                        color: Studio.Theme.primary
                        size: 24
                    }
                }
                ColumnLayout {
                    Layout.fillWidth: true
                    Layout.minimumWidth: 0
                    spacing: Studio.Theme.space4
                    Label {
                        Layout.fillWidth: true
                        Layout.minimumWidth: 0
                        objectName: "libraryLabTitle"
                        color: Studio.Theme.textOnSurface
                        font.family: Studio.Theme.fontFamily
                        font.pixelSize: Studio.Theme.titleLarge
                        font.weight: Font.DemiBold
                        text: header.lab ? header.lab.name : ""
                        textFormat: Text.PlainText
                        maximumLineCount: 2
                        wrapMode: Text.Wrap
                        elide: Text.ElideRight
                    }
                    Label {
                        Layout.fillWidth: true
                        Layout.minimumWidth: 0
                        color: Studio.Theme.textOnSurfaceVariant
                        font.pixelSize: Studio.Theme.bodySmall
                        text: header.lab ? header.lab.id + " · v" + header.lab.version : ""
                        textFormat: Text.PlainText
                        elide: Text.ElideMiddle
                    }
                }
            }
            Flow {
                id: topicChips
                Layout.fillWidth: true
                Layout.preferredHeight: childrenRect.height
                spacing: Studio.Theme.space8
                visible: !!header.lab
                Studio.DifficultyChip {
                    objectName: "libraryDetailDifficulty"
                    difficulty: header.lab ? header.lab.difficulty || "" : ""
                    maximumWidth: topicChips.width
                }
                Repeater {
                    model: header.lab ? header.lab.tags || [] : []
                    delegate: Studio.TopicChip {
                        required property string modelData
                        objectName: "libraryTopic-" + modelData
                        topicId: modelData
                        maximumWidth: topicChips.width
                        text: header.lab ? (header.lab.tag_labels || {})[modelData] || modelData : ""
                    }
                }
            }
        }
        ColumnLayout {
            id: summary
            objectName: "libraryLabTags"
            Layout.fillWidth: !header.wide
            Layout.alignment: header.wide ? Qt.AlignRight | Qt.AlignVCenter : Qt.AlignLeft
            Layout.maximumWidth: details.width
            spacing: Studio.Theme.space12

            Studio.StatusBadge {
                objectName: "libraryLabStatus"
                Layout.alignment: header.wide ? Qt.AlignRight : Qt.AlignLeft
                bgColor: header.running ? Studio.Theme.successContainer : header.saved ? Studio.Theme.warningContainer : Studio.Theme.surfaceContainerHigh
                dotColor: textColor
                iconName: header.running ? "terminal" : header.saved ? "bookmark" : "check_circle"
                maximumWidth: details.width
                text: header.running ? "Đang chạy" : header.savedState === "SUSPENDED" ? "Đã tạm dừng" : header.savedState === "STOPPED" ? "Đã dừng · Có bản lưu" : "Sẵn sàng"
                textColor: header.running ? Studio.Theme.textOnSuccessContainer : header.saved ? Studio.Theme.textOnWarningContainer : Studio.Theme.textOnSurfaceVariant
            }
            RowLayout {
                Layout.alignment: header.wide ? Qt.AlignRight : Qt.AlignLeft
                spacing: Studio.Theme.space8
                Studio.StatusBadge {
                    objectName: "libraryNetworkCount"
                    bgColor: Studio.Theme.transparent
                    border.width: 0
                    description: header.lab ? header.lab.networks.join(", ") : ""
                    dotColor: Studio.Theme.network
                    iconName: "lan"
                    text: header.lab ? header.lab.networks.length + " mạng" : ""
                    textColor: Studio.Theme.textOnSurfaceVariant
                    visible: !!header.lab && (header.lab.networks || []).length > 0
                }
                Rectangle {
                    Layout.preferredWidth: 1
                    Layout.preferredHeight: 16
                    color: Studio.Theme.outlineVariant
                    visible: !!header.lab && (header.lab.networks || []).length > 0
                }
                Studio.StatusBadge {
                    objectName: "libraryNodeCount"
                    bgColor: Studio.Theme.transparent
                    border.width: 0
                    description: header.lab ? (header.lab.environments || []).map(node => (node[2] ? node[2] + "@" : "") + (node[1] || node[0])).join(", ") : ""
                    dotColor: Studio.Theme.textOnSurfaceVariant
                    iconName: "terminal"
                    text: header.lab ? (header.lab.nodes || []).length + " máy" : ""
                    textColor: Studio.Theme.textOnSurfaceVariant
                }
            }
        }
    }
}
