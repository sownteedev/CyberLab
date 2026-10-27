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
    spacing: Studio.Theme.space16
    ColumnLayout {
        Layout.fillWidth: true
        visible: sections.editor.section === 0
        spacing: Studio.Theme.space16
        SectionHeader { title: "Tổng quan"; Layout.fillWidth: true }
        Label { text: "Mã bài" }
        StudioTextField { Layout.fillWidth: true; text: sections.editor.document ? sections.editor.document.metadata.id : ""; onEditingFinished: sections.editor.change("metadata", 0, "id", text.trim()) }
        Label { text: "Tên bài" }
        StudioTextField { Layout.fillWidth: true; text: sections.editor.document ? sections.editor.document.metadata.name : ""; onEditingFinished: sections.editor.change("metadata", 0, "name", text) }
        Label { text: "Phiên bản nội dung" }
        StudioTextField { Layout.fillWidth: true; text: sections.editor.document ? sections.editor.document.metadata.version : ""; onEditingFinished: sections.editor.change("metadata", 0, "version", text) }
        Label {
            Layout.fillWidth: true
            text: "Thêm máy, mạng, file và hướng dẫn; kiểm tra trước khi xuất bản. Bản nháp chưa chạy container và chưa trở thành bài trong thư viện."
            color: Studio.Theme.textOnSurfaceVariant
            wrapMode: Text.WordWrap
        }
    }
    ColumnLayout {
        Layout.fillWidth: true
        visible: sections.editor.section === 1
        spacing: Studio.Theme.space16
        RowLayout {
            Layout.fillWidth: true
            SectionHeader { title: "Máy lab"; Layout.fillWidth: true }
            StudioButton {
                text: "Máy"
                iconName: "add"
                enabled: Defaults.canAddMachine(sections.editor.document, sections.editor.policy)
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
                StudioButton {
                    required property var modelData
                    required property int index
                    objectName: "draftNodeCard-" + index
                    width: Math.min(implicitWidth, nodeChoices.width)
                    text: (modelData.user ? modelData.user.name + "@" : "") + (modelData.hostname || modelData.id || "Máy chưa đặt tên")
                    iconName: "terminal"
                    flat: true
                    selected: sections.editor.selectedNode === index
                    onClicked: sections.editor.selectedNode = index
                }
            }
        }
        NodeEditor { Layout.fillWidth: true; editor: sections.editor; nodeIndex: editor.selectedNode; visible: !!editor.document && editor.document.nodes.length > 0 }
    }
    ColumnLayout {
        Layout.fillWidth: true
        visible: sections.editor.section === 2
        spacing: Studio.Theme.space16
        RowLayout {
            Layout.fillWidth: true
            SectionHeader { title: "Mạng nội bộ"; Layout.fillWidth: true }
            StudioButton {
                text: "Mạng"
                iconName: "add"
                enabled: !!sections.editor.document && sections.editor.document.networks.length < 4
                onClicked: {
                    sections.editor.modify("networks", {id: Model.nextId(sections.editor.document.networks, "lan")});
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
                    required property var modelData
                    required property int index
                    objectName: "draftNetworkCard-" + index
                    width: networkChoices.width < 480 ? networkChoices.width : (networkChoices.width - networkChoices.spacing) / 2
                    title: modelData.id || "Mạng chưa đặt tên"
                    iconName: "lan"
                    subtitle: modelData.subnet || "Subnet tự động"
                    detail: (sections.editor.document ? sections.editor.document.nodes : [])
                        .filter(node => (node.networks || []).includes(modelData.id)).length
                        + " máy kết nối · Mạng nội bộ"
                    selected: sections.editor.selectedNetwork === index
                    onClicked: sections.editor.selectedNetwork = index
                }
            }
        }
        NetworkEditor { Layout.fillWidth: true; editor: sections.editor; networkIndex: editor.selectedNetwork; visible: !!editor.document && editor.document.networks.length > 0 }
    }
    DraftResources { Layout.fillWidth: true; editor: sections.editor; visible: editor.section === 3 }
    DraftReview { Layout.fillWidth: true; editor: sections.editor; visible: editor.section === 5 }
    DraftLabedit { Layout.fillWidth: true; editor: sections.editor; visible: editor.section === 6 }
}
