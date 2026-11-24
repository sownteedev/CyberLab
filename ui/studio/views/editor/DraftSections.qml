pragma ComponentBehavior: Bound

import QtQuick
import QtQuick.Controls.Material
import QtQuick.Layouts
import "../../models/EditorModel.js" as Model
import "../../models/NodeDefaults.js" as Defaults
import "../.."
import "../.." as Studio

ColumnLayout {
    id: sections

    required property var editor
    property int machineTab: 0
    property real viewportHeight: 0

    spacing: Studio.Theme.space24

    Studio.DraftOverview {
        Layout.fillWidth: true
        editor: sections.editor
        visible: sections.editor.section === 0
    }
    ColumnLayout {
        Layout.fillWidth: true
        spacing: Studio.Theme.space16
        visible: sections.editor.section === 1

        RowLayout {
            Layout.fillWidth: true

            Label {
                Layout.fillWidth: true
                color: Studio.Theme.textOnSurfaceVariant
                text: qsTr("%1 máy trong bài").arg(sections.editor.document ? sections.editor.document.nodes.length : 0)
            }
            StudioButton {
                enabled: Defaults.canAddMachine(sections.editor.document, sections.editor.policy)
                iconName: "add"
                highlighted: true
                objectName: "addDraftMachine"
                text: "Thêm máy"

                onClicked: sections.editor.addMachine()
            }
        }
        Flow {
            id: nodeChoices

            Layout.fillWidth: true
            Layout.preferredHeight: implicitHeight
            spacing: Studio.Theme.space8

            Repeater {
                model: sections.editor.document ? sections.editor.document.nodes : []

                DraftObjectCard {
                    required property int index
                    required property var modelData

                    iconName: "terminal"
                    detail: ""
                    subtitle: qsTr("%1 · %2 terminal").arg((Defaults.profile(sections.editor.policy, modelData.image) || {}).label || modelData.image || "").arg(modelData.terminal_count || 1)
                    objectName: "draftNodeCard-" + index
                    selected: sections.editor.selectedNode === index
                    title: (modelData.user ? modelData.user.name + "@" : "") + (modelData.hostname || modelData.id || "Máy chưa đặt tên")
                    width: nodeChoices.width < 560 ? nodeChoices.width : (nodeChoices.width - nodeChoices.spacing) / 2

                    onClicked: sections.editor.selectedNode = index
                }
            }
        }
        Studio.StudioSegmentedTabs {
            Layout.fillWidth: true
            Layout.maximumWidth: 640
            Accessible.name: qsTr("Thiết lập máy Lab")
            objectName: "machineEditorTabs"
            itemPrefix: "machineEditorTab-"
            entries: [{label: qsTr("Cấu hình"), icon: "terminal"}, {label: qsTr("Phần mềm"), icon: "inventory_2"}, {label: qsTr("Khởi động"), icon: "terminal"}]
            currentIndex: sections.machineTab
            visible: !!sections.editor.document && sections.editor.document.nodes.length > 0
            onSelected: index => sections.machineTab = index
        }
        Studio.DraftFormCard {
            Layout.fillWidth: true
            title: qsTr("Cấu hình máy")
            iconName: "terminal"
            visible: sections.machineTab === 0 && !!sections.editor.document && sections.editor.document.nodes.length > 0
            NodeEditor {
                Layout.fillWidth: true
                editor: sections.editor
                nodeIndex: editor.selectedNode
            }
        }
        Studio.EmptyState {
            Layout.fillWidth: true
            Layout.topMargin: Studio.Theme.space32
            prominent: true
            iconName: "terminal"
            title: qsTr("Chưa có máy lab")
            visible: !!sections.editor.document && sections.editor.document.nodes.length === 0
        }
        Studio.DraftFormCard {
            Layout.fillWidth: true
            title: qsTr("Phần mềm")
            enabled: !sections.editor.backend.busy
            iconName: "inventory_2"
            visible: sections.machineTab === 1 && !!sections.editor.document && sections.editor.document.nodes.length > 0
            NodeSoftwareEditor {
                editor: sections.editor
                nodeIndex: sections.editor.selectedNode
            }
        }
        Studio.DraftFormCard {
            Layout.fillWidth: true
            title: qsTr("Khởi động")
            iconName: "terminal"
            visible: sections.machineTab === 2 && !!sections.editor.document && sections.editor.document.nodes.length > 0
            Studio.NodeStartupEditor {
                Layout.fillWidth: true
                editor: sections.editor
                nodeIndex: sections.editor.selectedNode
            }
        }
    }
    ColumnLayout {
        Layout.fillWidth: true
        spacing: Studio.Theme.space16
        visible: sections.editor.section === 2

        RowLayout {
            Layout.fillWidth: true

            Label {
                Layout.fillWidth: true
                color: Studio.Theme.textOnSurfaceVariant
                text: qsTr("%1 mạng trong bài").arg(sections.editor.document ? sections.editor.document.networks.length : 0)
            }
            StudioButton {
                enabled: !!sections.editor.document && sections.editor.document.networks.length < 4
                iconName: "add"
                highlighted: true
                objectName: "addDraftNetwork"
                text: "Thêm mạng"

                onClicked: {
                    const network = {id: Model.nextId(sections.editor.document.networks, "lan")};
                    if (sections.editor.policy && sections.editor.policy.network_internet) network.internet = true;
                    sections.editor.modify("networks", network);
                    sections.editor.selectedNetwork = sections.editor.document.networks.length - 1;
                }
            }
        }
        Flow {
            id: networkChoices

            Layout.fillWidth: true
            Layout.preferredHeight: implicitHeight
            spacing: Studio.Theme.space8

            Repeater {
                model: sections.editor.document ? sections.editor.document.networks : []

                DraftObjectCard {
                    required property int index
                    required property var modelData

                    detail: (sections.editor.document ? sections.editor.document.nodes : []).filter(node => (node.networks || []).includes(modelData.id)).length + " máy kết nối · " + (Model.networkInternet(sections.editor.document, modelData) ? "Có Internet" : "Nội bộ")
                    iconName: "lan"
                    objectName: "draftNetworkCard-" + index
                    selected: sections.editor.selectedNetwork === index
                    subtitle: modelData.subnet || "Subnet tự động"
                    title: modelData.id || "Mạng chưa đặt tên"
                    width: networkChoices.width < 480 ? networkChoices.width : (networkChoices.width - networkChoices.spacing) / 2

                    onClicked: sections.editor.selectedNetwork = index
                }
            }
        }
        Studio.DraftFormCard {
            Layout.fillWidth: true
            title: qsTr("Cấu hình mạng")
            iconName: "lan"
            visible: !!sections.editor.document && sections.editor.document.networks.length > 0
            NetworkEditor {
                Layout.fillWidth: true
                editor: sections.editor
                networkIndex: editor.selectedNetwork
            }
        }
        Studio.EmptyState {
            Layout.fillWidth: true
            Layout.topMargin: Studio.Theme.space32
            prominent: true
            iconName: "lan"
            title: qsTr("Chưa có mạng nội bộ")
            visible: !!sections.editor.document && sections.editor.document.networks.length === 0
        }
    }
    DraftResources {
        Layout.fillWidth: true
        Layout.preferredHeight: Math.max(implicitHeight, sections.viewportHeight - Studio.Theme.space24)
        editor: sections.editor
        visible: editor.section === 3
    }
    DraftReview {
        Layout.fillWidth: true
        editor: sections.editor
        visible: editor.section === 5
    }
    DraftLabedit {
        Layout.fillWidth: true
        editor: sections.editor
        visible: editor.section === 6
    }
}
