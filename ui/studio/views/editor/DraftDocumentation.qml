import QtQuick
import QtQuick.Controls.Basic
import QtQuick.Layouts
import "../../models/EditorModel.js" as Model
import "../.."
import "../.." as Studio

ColumnLayout {
    id: panel

    required property var editor
    property bool preview: false
    readonly property bool wide: width >= 840
    property bool syncingScroll: false
    property real scrollProgress: 0

    function syncScroll(origin, destination) {
        if (syncingScroll || !origin || !destination || !visible) return;
        syncingScroll = true;
        const range = Math.max(0, origin.contentHeight - origin.height);
        scrollProgress = range ? Math.max(0, Math.min(1, origin.contentY / range)) : 0;
        destination.contentY = scrollProgress * Math.max(0, destination.contentHeight - destination.height);
        syncingScroll = false;
    }
    Connections {
        target: sourceScroll.contentItem
        function onContentYChanged() { panel.syncScroll(sourceScroll.contentItem, previewView.contentItem); }
    }
    Connections {
        target: previewView.contentItem
        function onContentYChanged() { panel.syncScroll(previewView.contentItem, sourceScroll.contentItem); }
    }

    objectName: "draftDocumentation"
    spacing: Studio.Theme.space12

    RowLayout {
        Layout.fillWidth: true
        spacing: Studio.Theme.space8

        Label {
            Layout.fillWidth: true
            color: Studio.Theme.textOnSurfaceVariant
            text: "Markdown"
        }
        StudioButton {
            iconName: "download"
            iconOnly: panel.width < 440
            text: "Nhập file .md"

            onClicked: picker.open()
        }
        StudioIconButton {
            description: "Bỏ hướng dẫn"
            enabled: !!panel.editor.document && !!panel.editor.document.documentation
            iconName: "delete"
            objectName: "removeDocumentationButton"

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
        spacing: Studio.Theme.space8
        visible: !panel.wide

        StudioButton {
            Layout.fillWidth: panel.width < 320
            Layout.minimumWidth: 0
            flat: true
            iconName: "edit"
            objectName: "documentationEditTab"
            selected: !panel.preview
            text: "Soạn thảo"

            onClicked: panel.preview = false
        }
        StudioButton {
            Layout.fillWidth: panel.width < 320
            Layout.minimumWidth: 0
            flat: true
            iconName: "description"
            objectName: "documentationPreviewTab"
            selected: panel.preview
            text: "Xem trước"

            onClicked: panel.preview = true
        }
        Item {
            Layout.fillWidth: true
            visible: panel.width >= 320
        }
    }
    SplitView {
        id: panes

        Layout.fillHeight: true
        Layout.fillWidth: true
        Layout.minimumHeight: 200
        objectName: "documentationSplit"

        handle: StudioSplitHandle {
            objectName: "documentationSplitHandle"
        }

        ColumnLayout {
            SplitView.fillWidth: !panel.wide
            SplitView.minimumWidth: panel.wide ? 360 : 0
            SplitView.preferredWidth: (panes.width - Studio.Theme.space16) / 2
            objectName: "documentationSourcePane"
            spacing: Studio.Theme.space8
            visible: panel.wide || !panel.preview

            Label {
                color: Studio.Theme.textOnSurfaceVariant
                font.pixelSize: Studio.Theme.labelLarge
                text: "Soạn thảo"
                visible: panel.wide
            }
            ScrollView {
                id: sourceScroll
                Layout.fillHeight: true
                Layout.fillWidth: true
                clip: true
                contentWidth: availableWidth
                objectName: "documentationSourceScroll"

                StudioTextArea {
                    id: sourceText
                    Accessible.name: "Nội dung hướng dẫn Markdown"
                    enabled: panel.editor.documentationReady && !panel.editor.backend.busy
                    objectName: "documentationSource"
                    placeholderText: "# Mục tiêu\n\n# Yêu cầu\n\n# Thực hành\n\n# Kết quả cần đạt"
                    text: panel.editor.documentationText
                    font.pixelSize: 14
                    wrapMode: TextEdit.Wrap
                    background: Rectangle {
                        color: Studio.Theme.surfaceContainerLow
                        border.color: sourceText.activeFocus ? Studio.Theme.primary : Studio.Theme.outlineVariant
                        border.width: sourceText.activeFocus ? Studio.Theme.focusWidth : Studio.Theme.borderWidth
                        radius: Studio.Theme.shapeLarge
                    }

                    onTextChanged: if (activeFocus && text !== panel.editor.documentationText)
                        panel.editor.files.editDocumentation(text)
                }
            }
        }
        ColumnLayout {
            SplitView.fillWidth: true
            SplitView.minimumWidth: panel.wide ? 360 : 0
            objectName: "documentationPreviewPane"
            spacing: Studio.Theme.space8
            visible: panel.wide || panel.preview

            Label {
                color: Studio.Theme.textOnSurfaceVariant
                font.pixelSize: Studio.Theme.labelLarge
                text: "Xem trước"
                visible: panel.wide
            }
            MarkdownView {
                id: previewView
                Layout.fillHeight: true
                Layout.fillWidth: true
                markdown: panel.editor.documentationText
                objectName: "documentationPreview"
                background: Rectangle {
                    color: Studio.Theme.surfaceContainerLow
                    border.color: Studio.Theme.outlineVariant
                    border.width: Studio.Theme.borderWidth
                    radius: Studio.Theme.shapeLarge
                }
            }
        }
    }
    Label {
        Layout.fillWidth: true
        color: Studio.Theme.textOnSurfaceVariant
        font.pixelSize: Studio.Theme.bodySmall
        text: "Lưu cùng bản nháp · Markdown UTF-8, tối đa 64 KiB"
        wrapMode: Text.WordWrap
    }
    Studio.StudioFileDialog {
        id: picker

        nameFilters: ["Markdown (*.md)"]
        title: "Chọn hướng dẫn Markdown"

        onAccepted: {
            const url = selectedFile.toString();
            if (!url.startsWith("file:///")) {
                panel.editor.showLocalError("Chỉ nhận file cục bộ.");
                return;
            }
            const draftId = panel.editor.draft.id;
            panel.editor.backend.request(["draft", "read-local", decodeURIComponent(url.substring(7))], (result, error) => {
                if (error || !panel.editor.draft || panel.editor.draft.id !== draftId) return;
                const resource = result.resources[0];
                if (!resource || resource.content.text === undefined) {
                    panel.editor.showLocalError(qsTr("Hướng dẫn phải là văn bản UTF-8, tối đa 64 KiB."));
                    return;
                }
                panel.editor.files.editDocumentation(resource.content.text);
            });
        }
    }
}
