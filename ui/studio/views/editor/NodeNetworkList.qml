import QtQuick
import QtQuick.Controls.Basic
import QtQuick.Layouts
import "../.." as Studio
import "../../models/NodeDefaults.js" as Defaults

ColumnLayout {
    id: panel
    required property var editor
    required property int nodeIndex
    readonly property var node: editor.document && editor.document.nodes[nodeIndex] ? editor.document.nodes[nodeIndex] : null

    Layout.fillWidth: true
    spacing: Studio.Theme.space8
    objectName: "nodeNetworkList"

    Label {
        text: qsTr("Mạng kết nối")
        color: Studio.Theme.textOnSurface
        font.weight: Font.Medium
    }
    Frame {
        Layout.fillWidth: true
        implicitWidth: 320
        padding: Studio.Theme.space4
        visible: !!panel.editor.document && panel.editor.document.networks.length > 0
        background: Rectangle {
            color: Studio.Theme.surfaceContainerLow
            radius: Studio.Theme.shapeMedium
            border.color: Studio.Theme.outlineVariant
        }
        contentItem: Column {
            spacing: Studio.Theme.space4
            Repeater {
                model: panel.editor.document ? panel.editor.document.networks : []
                Rectangle {
                    id: connection
                    required property var modelData
                    readonly property bool attached: !!panel.node && panel.node.networks.includes(modelData.id)
                    readonly property bool wide: width >= 600
                    objectName: "nodeNetworkRow-" + modelData.id
                    width: parent.width
                    implicitHeight: fields.implicitHeight + Studio.Theme.space16
                    radius: Studio.Theme.shapeSmall
                    color: attached ? Qt.alpha(Studio.Theme.primary, 0.08) : "transparent"

                    GridLayout {
                        id: fields
                        anchors.fill: parent
                        anchors.margins: Studio.Theme.space8
                        columns: connection.wide ? 2 : 1
                        columnSpacing: Studio.Theme.space16
                        rowSpacing: Studio.Theme.space8

                        CheckBox {
                            id: selected
                            Layout.fillWidth: true
                            Layout.minimumWidth: 0
                            implicitWidth: 180
                            implicitHeight: Math.max(48, labels.implicitHeight + Studio.Theme.space8)
                            leftPadding: 40
                            rightPadding: Studio.Theme.space8
                            topPadding: Studio.Theme.space4
                            bottomPadding: Studio.Theme.space4
                            objectName: "nodeNetworkToggle-" + connection.modelData.id
                            text: connection.modelData.id
                            checked: connection.attached
                            focusPolicy: Qt.StrongFocus
                            hoverEnabled: true
                            Accessible.role: Accessible.CheckBox
                            Accessible.name: qsTr("Kết nối mạng %1").arg(text)
                            onToggled: {
                                panel.editor.attach(panel.nodeIndex, connection.modelData.id, checked,
                                    checked ? Defaults.nextAddress(panel.editor.document, connection.modelData.id) : "");
                                checked = Qt.binding(() => connection.attached);
                            }
                            indicator: Rectangle {
                                x: 8
                                y: (selected.height - height) / 2
                                implicitWidth: 22
                                implicitHeight: 22
                                radius: 5
                                color: selected.checked ? Studio.Theme.primary : "transparent"
                                border.width: selected.checked ? 0 : 2
                                border.color: Studio.Theme.textOnSurfaceVariant
                                Studio.Icon {
                                    anchors.centerIn: parent
                                    name: "check"
                                    size: 16
                                    visible: selected.checked
                                    color: Studio.Theme.textOnPrimary
                                }
                            }
                            contentItem: ColumnLayout {
                                id: labels
                                spacing: 2
                                Label {
                                    Layout.fillWidth: true
                                    text: selected.text
                                    textFormat: Text.PlainText
                                    font.weight: Font.Medium
                                    color: Studio.Theme.textOnSurface
                                    elide: Text.ElideRight
                                }
                                Label {
                                    Layout.fillWidth: true
                                    objectName: "nodeNetworkAutomatic-" + connection.modelData.id
                                    text: connection.modelData.subnet || qsTr("IP tự động")
                                    textFormat: Text.PlainText
                                    color: Studio.Theme.textOnSurfaceVariant
                                    font.pixelSize: Studio.Theme.bodySmall
                                    elide: Text.ElideRight
                                }
                            }
                            background: Rectangle {
                                radius: Studio.Theme.shapeSmall
                                color: selected.hovered ? Qt.alpha(Studio.Theme.primary, 0.06) : "transparent"
                                border.width: selected.visualFocus ? Studio.Theme.focusWidth : 0
                                border.color: Studio.Theme.primary
                            }
                        }
                        GridLayout {
                            id: addressFields
                            Layout.fillWidth: true
                            Layout.preferredWidth: 300
                            Layout.maximumWidth: connection.wide ? 320 : Infinity
                            Layout.leftMargin: connection.wide ? 0 : 40
                            columns: width >= 270 ? 2 : 1
                            columnSpacing: Studio.Theme.space12
                            rowSpacing: Studio.Theme.space4
                            visible: connection.attached && !!connection.modelData.subnet
                            Label {
                                objectName: "nodeNetworkAddressLabel-" + connection.modelData.id
                                text: qsTr("IP của máy")
                                color: Studio.Theme.textOnSurfaceVariant
                                font.pixelSize: Studio.Theme.bodySmall
                            }
                            Studio.StudioTextField {
                                Layout.fillWidth: true
                                Layout.minimumWidth: 80
                                objectName: "nodeNetworkAddress-" + connection.modelData.id
                                Accessible.name: qsTr("IP của máy trên mạng %1").arg(connection.modelData.id)
                                placeholderText: qsTr("Địa chỉ IP")
                                text: panel.node ? (panel.node.addresses || {})[connection.modelData.id] || "" : ""
                                onEditingFinished: if (visible && connection.attached)
                                    panel.editor.attach(panel.nodeIndex, connection.modelData.id, true, text.trim())
                            }
                        }
                    }
                }
            }
        }
    }
}
