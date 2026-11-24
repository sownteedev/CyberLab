import QtQuick
import QtQuick.Controls
import QtQuick.Layouts
import "../../models/EditorModel.js" as Model
import "../.."
import "../.." as Studio

ColumnLayout {
    id: panel

    required property var editor
    required property var node

    function sources() {
        const paths = [];
        (editor.draft ? editor.draft.assets : []).forEach(asset => {
            paths.push(asset.path);
            const parts = asset.path.split("/");
            while (parts.length > 2) {
                parts.pop();
                paths.push(parts.join("/"));
            }
        });
        return paths.filter((path, index) => paths.indexOf(path) === index).sort();
    }

    spacing: Studio.Theme.space8

    Label {
        font.weight: Font.Medium
        text: "Ánh xạ của máy"
    }
    Repeater {
        model: panel.node ? panel.node.files || [] : []

        RowLayout {
            id: mappingRow

            required property int index
            required property var modelData

            Layout.fillWidth: true

            Label {
                Layout.fillWidth: true
                text: mappingRow.modelData.source + " → " + Model.destination(panel.node, mappingRow.modelData.target)
                wrapMode: Text.WrapAnywhere
            }
            StudioButton {
                flat: true
                text: "Bỏ ánh xạ"

                onClicked: panel.editor.removeMapping(panel.editor.selectedNode, mappingRow.index)
            }
        }
    }
    StudioComboBox {
        id: source

        Accessible.name: "Nguồn ánh xạ"
        Layout.fillWidth: true
        model: panel.sources()
    }
    StudioTextField {
        id: target

        Layout.fillWidth: true
        placeholderText: "Đích tương đối, hoặc . để dùng home"
    }
    StudioButton {
        enabled: !!panel.node && source.currentIndex >= 0 && !!target.text.trim()
        text: "Thêm ánh xạ"

        onClicked: panel.editor.addMapping(panel.node.id, source.currentText, target.text.trim())
    }
    Label {
        font.weight: Font.Medium
        text: "Tài nguyên trong bản nháp"
    }
    Repeater {
        model: panel.editor.draft ? panel.editor.draft.assets : []

        RowLayout {
            id: assetRow

            required property var modelData

            Layout.fillWidth: true

            Label {
                Layout.fillWidth: true
                text: assetRow.modelData.path
                wrapMode: Text.WrapAnywhere
            }
            StudioButton {
                flat: true
                text: "Xóa"

                onClicked: panel.editor.removeAsset(assetRow.modelData.path)
            }
        }
    }
}
