import QtQuick
import QtQuick.Controls.Basic
import QtQuick.Layouts
import "../.."
import "../.." as Studio
import "../../models/LocalFiles.js" as LocalFiles

Studio.StudioDialog {
    id: dialog

    required property var api
    property Item returnFocus: null
    readonly property alias service: reviewService

    function openFor(caller) {
        returnFocus = caller || (parent && parent.Window.window ? parent.Window.window.activeFocusItem : null);
        if (parent && parent.Window.window)
            parent.Window.window.requestActivate();
        open();
    }

    anchors.centerIn: parent
    closePolicy: Popup.CloseOnEscape | Popup.CloseOnPressOutside
    focus: true
    height: Math.min(620, parent ? parent.height - Studio.Theme.space32 : 620)
    modal: true
    objectName: "submissionReviewDialog"
    padding: Studio.Theme.space24
    topPadding: Studio.Theme.space8
    bottomPadding: Studio.Theme.space16
    parent: Overlay.overlay
    title: qsTr("Duyệt bài nộp")
    width: Math.min(900, parent ? parent.width - Studio.Theme.space32 : 900)

    contentItem: ColumnLayout {
        spacing: Studio.Theme.space12

        InlineError {
            Layout.fillWidth: true
            message: reviewService.error
        }
        Label {
            Layout.fillWidth: true
            color: Studio.Theme.textOnSurface
            font.pixelSize: Studio.Theme.bodyMedium
            text: reviewService.review ? reviewService.review.summary.submitted + " file · " + reviewService.review.summary.valid + " hợp lệ · " + reviewService.review.summary.invalid + " lỗi" : ""
            visible: !!reviewService.review
        }
        ListView {
            id: results

            Layout.fillHeight: true
            Layout.fillWidth: true
            clip: true
            model: reviewService.review ? reviewService.review.items : []
            objectName: "submissionReviewList"
            spacing: Studio.Theme.space8

            ScrollBar.vertical: ScrollBar {
            }
            delegate: SubmissionReviewRow {
                width: results.width
            }

            EmptyState {
                anchors.centerIn: parent
                compact: parent.height < 120
                iconName: reviewService.loading ? "refresh" : "inventory_2"
                objectName: "submissionReviewEmptyState"
                prominent: parent.height >= 200
                title: reviewService.loading ? qsTr("Đang đối chiếu bài nộp") : qsTr("Chưa có bài nộp")
                visible: results.count === 0
                width: parent.width
            }
            LoadingState {
                anchors.left: parent.left
                anchors.right: parent.right
                anchors.top: parent.top
                busy: reviewService.loading
            }
        }
        Label {
            Layout.fillWidth: true
            color: Studio.Theme.textOnSurfaceVariant
            font.pixelSize: Studio.Theme.bodySmall
            text: qsTr("Gói được đối chiếu hash và nội dung báo cáo. Kết quả tự kiểm tra không phải điểm thi được xác thực.")
            wrapMode: Text.WordWrap
        }
    }
    footer: Studio.StudioDialogFooter {
        contentItem: RowLayout {
            spacing: Studio.Theme.space8

            Label {
                color: Studio.Theme.textOnSurfaceVariant
                font.pixelSize: Studio.Theme.bodySmall
                text: qsTr("Tối đa 32 gói ZIP mỗi lần")
                visible: dialog.width >= 600
            }
            Item {
                Layout.fillWidth: true
            }
            StudioButton {
                flat: true
                objectName: "closeSubmissionReviewAction"
                text: "Đóng"

                onClicked: dialog.close()
            }
            StudioButton {
                id: chooseButton

                enabled: !dialog.api.busy && !reviewService.loading
                highlighted: true
                iconName: "download"
                objectName: "chooseSubmissionsButton"
                text: "Chọn file ZIP"

                onActiveFocusChanged: if (!activeFocus && !enabled && dialog.visible)
                    dialogHeader.closeButton.forceActiveFocus(Qt.TabFocusReason)
                onClicked: input.open()
                onEnabledChanged: if (enabled && dialog.visible)
                    chooseButton.forceActiveFocus(Qt.TabFocusReason)
            }
        }
    }
    header: Studio.StudioDialogHeader {
        id: dialogHeader

        title: dialog.title
        iconName: "inventory_2"
        closeDescription: qsTr("Đóng duyệt bài nộp")
        closeObjectName: "closeSubmissionReviewButton"
        onCloseRequested: dialog.close()
    }

    onClosed: {
        input.close();
        reviewService.clear();
        if (returnFocus)
            returnFocus.forceActiveFocus(Qt.TabFocusReason);
    }
    onOpened: chooseButton.forceActiveFocus(Qt.TabFocusReason)

    SubmissionReviewService {
        id: reviewService

        api: dialog.api
    }
    Studio.StudioFileDialog {
        id: input

        fileMode: "openMany"
        nameFilters: ["Bài nộp CyberLab (*.zip)"]
        objectName: "submissionReviewPicker"
        title: "Chọn các bài nộp CyberLab"

        onAccepted: if (dialog.visible)
            reviewService.load(selectedFiles.map(url => LocalFiles.path(url)))
    }
}
