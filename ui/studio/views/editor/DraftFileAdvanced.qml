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
    spacing: Studio.Theme.space8
    function sources() {
        const paths = [];
        (editor.draft ? editor.draft.assets : []).forEach(asset => {
            paths.push(asset.path);
            const parts = asset.path.split("/");
            while (parts.length > 2) { parts.pop(); paths.push(parts.join("/")); }
        });
        return paths.filter((path, index) => paths.indexOf(path) === index).sort();
    }
    Label { text: "Ánh xạ của máy"; font.weight: Font.Medium }
    Repeater {
        model: panel.node ? panel.node.files || [] : []
        RowLayout {
            id: mappingRow
            required property var modelData
            required property int index
            Layout.fillWidth: true
            Label { Layout.fillWidth: true; text: mappingRow.modelData.source + " → " + Model.destination(panel.node, mappingRow.modelData.target); wrapMode: Text.WrapAnywhere }
            StudioButton { text: "Bỏ ánh xạ"; flat: true; onClicked: panel.editor.removeMapping(panel.editor.selectedNode, mappingRow.index) }
        }
    }
    StudioComboBox { id: source; Layout.fillWidth: true; model: panel.sources(); Accessible.name: "Nguồn ánh xạ" }
    StudioTextField { id: target; Layout.fillWidth: true; placeholderText: "Đích tương đối, hoặc . để dùng home" }
    StudioButton {
        text: "Thêm ánh xạ"
        enabled: !!panel.node && source.currentIndex >= 0 && !!target.text.trim()
        onClicked: panel.editor.addMapping(panel.node.id, source.currentText, target.text.trim())
    }
    Label { text: "Tài nguyên trong bản nháp"; font.weight: Font.Medium }
    Repeater {
        model: panel.editor.draft ? panel.editor.draft.assets : []
        RowLayout {
            id: assetRow
            required property var modelData
            Layout.fillWidth: true
            Label { Layout.fillWidth: true; text: assetRow.modelData.path; wrapMode: Text.WrapAnywhere }
            StudioButton { text: "Xóa"; flat: true; onClicked: panel.editor.removeAsset(assetRow.modelData.path) }
        }
    }
}
