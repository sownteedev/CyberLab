import QtQuick
import QtQuick.Controls.Basic
import QtQuick.Layouts
import QtQuick.Dialogs as Native
import "../.."
import "../.." as Studio
import "../../models/LocalFiles.js" as LocalFiles

Dialog {
    id: dialog
    objectName: "submissionReviewDialog"
    required property var api
    readonly property alias service: reviewService
    property Item returnFocus: null
    parent: Overlay.overlay
    anchors.centerIn: parent
    width: Math.min(900, parent ? parent.width - Studio.Theme.space32 : 900)
    height: Math.min(620, parent ? parent.height - Studio.Theme.space32 : 620)
    padding: Studio.Theme.space16
    modal: true
    focus: true
    closePolicy: Popup.CloseOnEscape | Popup.CloseOnPressOutside
    onOpened: chooseButton.forceActiveFocus(Qt.TabFocusReason)
    onClosed: {
        input.close();
        reviewService.clear();
        if (returnFocus) returnFocus.forceActiveFocus(Qt.TabFocusReason);
    }
    background: Rectangle { radius: Studio.Theme.shapeExtraLarge; color: Studio.Theme.surfaceContainerHigh }
    Overlay.modal: Rectangle { color: Studio.Theme.scrim }

    function openFor(caller) {
        returnFocus = caller || (parent && parent.Window.window ? parent.Window.window.activeFocusItem : null);
        if (parent && parent.Window.window) parent.Window.window.requestActivate();
        open();
    }
    SubmissionReviewService { id: reviewService; api: dialog.api }


    header: RowLayout {
        implicitHeight: Studio.Theme.appBarHeight
        Label {
            Layout.fillWidth: true
            Layout.leftMargin: Studio.Theme.space16
            text: "Duyệt bài nộp offline"
            color: Studio.Theme.textOnSurface
            font.pixelSize: Studio.Theme.titleMedium
        }
        StudioIconButton {
            id: closeButton
            objectName: "closeSubmissionReviewButton"
            Layout.rightMargin: Studio.Theme.space8
            iconName: "close"
            description: "Đóng duyệt bài nộp"
            onClicked: dialog.close()
        }
    }
    contentItem: ColumnLayout {
        spacing: Studio.Theme.space12
        InlineError { Layout.fillWidth: true; message: reviewService.error }
        Label {
            Layout.fillWidth: true
            text: "Kết quả tự kiểm tra, không phải điểm được xác thực. Gói được đối chiếu hash và nội dung báo cáo."
            wrapMode: Text.WordWrap
            color: Studio.Theme.textOnSurfaceVariant
            font.pixelSize: Studio.Theme.bodySmall
        }
        Label {
            Layout.fillWidth: true
            visible: !!reviewService.review
            text: reviewService.review ? reviewService.review.summary.submitted + " file · "
                + reviewService.review.summary.valid + " hợp lệ · " + reviewService.review.summary.invalid + " lỗi" : ""
            color: Studio.Theme.textOnSurface
            font.pixelSize: Studio.Theme.bodyMedium
        }
        ListView {
            id: results
            objectName: "submissionReviewList"
            Layout.fillWidth: true
            Layout.fillHeight: true
            clip: true
            spacing: Studio.Theme.space8
            model: reviewService.review ? reviewService.review.items : []
            ScrollBar.vertical: ScrollBar {}
            delegate: SubmissionReviewRow { width: results.width }
            EmptyState {
                anchors.centerIn: parent
                width: parent.width
                visible: results.count === 0 && !reviewService.loading
                title: "Chưa có bài nộp"
                description: "Chọn một hoặc nhiều file ZIP để bắt đầu."
            }
        }
        RowLayout {
            Layout.fillWidth: true
            spacing: Studio.Theme.space8
            StudioButton {
                id: chooseButton
                objectName: "chooseSubmissionsButton"
                iconName: "upload"
                text: "Chọn file ZIP"
                highlighted: true
                enabled: !dialog.api.busy && !reviewService.loading
                onClicked: input.open()
                onEnabledChanged: if (enabled && dialog.visible) chooseButton.forceActiveFocus(Qt.TabFocusReason)
                onActiveFocusChanged: if (!activeFocus && !enabled && dialog.visible) closeButton.forceActiveFocus(Qt.TabFocusReason)
            }
            Item { Layout.fillWidth: true }
            StudioButton { text: "Đóng"; flat: true; onClicked: dialog.close() }
        }
    }
    Native.FileDialog {
        id: input
        objectName: "submissionReviewPicker"
        title: "Chọn các bài nộp CyberLab"
        fileMode: Native.FileDialog.OpenFiles
        nameFilters: ["Bài nộp CyberLab (*.zip)"]
        onAccepted: if (dialog.visible) reviewService.load(selectedFiles.map(url => LocalFiles.path(url)))
    }
}
