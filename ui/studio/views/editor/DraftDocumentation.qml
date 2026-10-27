import QtQuick
import QtQuick.Controls.Material
import QtQuick.Layouts
import QtQuick.Dialogs
import "../../models/EditorModel.js" as Model
import "../.."
import "../.." as Studio

ColumnLayout {
    id: panel
    objectName: "draftDocumentation"
    required property var editor
    property bool preview: false
    readonly property bool wide: width >= 840
    spacing: Studio.Theme.space12
    RowLayout {
        Layout.fillWidth: true
        spacing: Studio.Theme.space8
        SectionHeader { Layout.fillWidth: true; title: "Hướng dẫn" }
        StudioButton { iconName: "upload"; text: "Nhập file .md"; onClicked: picker.open() }
        StudioIconButton {
            iconName: "delete"
            description: "Bỏ hướng dẫn"
            enabled: !!panel.editor.document && !!panel.editor.document.documentation
            onClicked: {
                const copy = Model.clone(panel.editor.document);
                delete copy.documentation;
                panel.editor.commit(copy);
                panel.editor.loadDocumentation();
            }
        }
    }
    RowLayout {
        Layout.fillWidth: true
        visible: !panel.wide
        spacing: Studio.Theme.space8
        StudioButton {
            objectName: "documentationEditTab"
            iconName: "edit"; text: "Soạn thảo"
            flat: true; selected: !panel.preview
            onClicked: panel.preview = false
        }
        StudioButton {
            objectName: "documentationPreviewTab"
            iconName: "description"; text: "Xem trước"
            flat: true; selected: panel.preview
            onClicked: panel.preview = true
        }
        Item { Layout.fillWidth: true }
    }
    SplitView {
        id: panes
        objectName: "documentationSplit"
        Layout.fillWidth: true
        Layout.fillHeight: true
        Layout.minimumHeight: 200
        handle: StudioSplitHandle { objectName: "documentationSplitHandle" }
        ColumnLayout {
            objectName: "documentationSourcePane"
            SplitView.fillWidth: !panel.wide
            SplitView.minimumWidth: panel.wide ? 360 : 0
            SplitView.preferredWidth: (panes.width - Studio.Theme.space16) / 2
            visible: panel.wide || !panel.preview
            spacing: Studio.Theme.space8
            Label {
                visible: panel.wide
                text: "Soạn thảo"
                font.pixelSize: Studio.Theme.labelLarge
                color: Studio.Theme.textOnSurfaceVariant
            }
            ScrollView {
                objectName: "documentationSourceScroll"
                Layout.fillWidth: true
                Layout.fillHeight: true
                clip: true
                contentWidth: availableWidth
                StudioTextArea {
                    objectName: "documentationSource"
                    enabled: panel.editor.documentationReady
                    text: panel.editor.documentationText
                    placeholderText: "# Mục tiêu\n\nViết hướng dẫn cho bài…"
                    Accessible.name: "Nội dung hướng dẫn Markdown"
                    wrapMode: TextEdit.Wrap
                    onTextChanged: if (activeFocus && text !== panel.editor.documentationText) {
                        panel.editor.documentationText = text;
                        panel.editor.documentationDirty = true;
                        panel.editor.report = null;
                        panel.editor.publicationReview = null;
                    }
                }
            }
        }
        ColumnLayout {
            objectName: "documentationPreviewPane"
            SplitView.fillWidth: true
            SplitView.minimumWidth: panel.wide ? 360 : 0
            visible: panel.wide || panel.preview
            spacing: Studio.Theme.space8
            Label {
                visible: panel.wide
                text: "Xem trước"
                font.pixelSize: Studio.Theme.labelLarge
                color: Studio.Theme.textOnSurfaceVariant
            }
            MarkdownView {
                objectName: "documentationPreview"
                Layout.fillWidth: true
                Layout.fillHeight: true
                markdown: panel.editor.documentationText
            }
        }
    }
    Label {
        Layout.fillWidth: true
        text: "Lưu cùng bản nháp · Markdown UTF-8, tối đa 64 KiB"
        wrapMode: Text.WordWrap
        font.pixelSize: Studio.Theme.bodySmall
        color: Studio.Theme.textOnSurfaceVariant
    }
    FileDialog {
        id: picker
        title: "Chọn hướng dẫn Markdown"
        nameFilters: ["Markdown (*.md)"]
        onAccepted: {
            const url = selectedFile.toString();
            if (!url.startsWith("file:///")) { panel.editor.localError = "Chỉ nhận file cục bộ."; return; }
            const path = "assets/docs/guide.md";
            panel.editor.upload(decodeURIComponent(url.substring(7)), path, false, () => {
                const copy = Model.clone(panel.editor.document);
                copy.documentation = path;
                panel.editor.commit(copy);
                panel.editor.loadDocumentation();
            });
        }
    }
}
