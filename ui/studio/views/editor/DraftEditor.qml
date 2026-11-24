import QtQuick
import QtQuick.Controls.Material
import QtQuick.Layouts
import "../.."
import "../.." as Studio

Control {
    id: draftEditor

    required property var backend
    readonly property alias service: draftService

    signal backRequested
    signal exportPackageRequested(var draft)
    signal published

    Shortcut {
        sequences: [StandardKey.Save]
        enabled: draftEditor.visible && !!draftService.draft && !draftEditor.backend.busy
        onActivated: draftService.save()
    }

    palette.alternateBase: Studio.Theme.surfaceContainer
    palette.base: Studio.Theme.surfaceContainerLowest
    palette.button: Studio.Theme.surfaceContainer
    palette.buttonText: Studio.Theme.textOnSurface
    palette.highlight: Studio.Theme.primary
    palette.highlightedText: Studio.Theme.textOnPrimary
    palette.placeholderText: Studio.Theme.textOnSurfaceVariant
    palette.text: Studio.Theme.textOnSurface
    palette.window: Studio.Theme.surface
    palette.windowText: Studio.Theme.textOnSurface

    contentItem: DraftWorkspace {
        editor: draftService

        onDeleteRequested: deleteDraftDialog.open()
        onExportPackageRequested: draftEditor.exportPackageRequested(draftService.draft)
        onReloadRequested: {
            if (draftService.dirty)
                reloadDraftDialog.open();
            else
                draftService.openDraft(draftService.draft.id, true);
        }
    }

    DraftService {
        id: draftService

        backend: draftEditor.backend

        onBackRequested: draftEditor.backRequested()
        onDiscardRequested: backDialog.open()
        onEditChoiceRequested: editingDrafts.open()
        onPublicationReviewRequested: publishDialog.open()
        onPublished: draftEditor.published()
        onUpdateReviewRequested: updateDialog.open()
    }
    EditingDraftDialog {
        id: editingDrafts
        editor: draftService
    }
    ConfirmDialog {
        id: publishDialog
        objectName: "draftPublicationDialog"

        confirmEnabled: draftService.canConfirmPublication && !draftService.backend.busy
        confirmText: "Lưu vào thư viện"
        message: draftService.publicationReview ? draftService.publicationReview.name + " (" + draftService.publicationReview.labId + ")\n" + draftService.publicationReview.nodes + " máy · " + draftService.publicationReview.networks + " mạng · " + draftService.publicationReview.assets + " file" + "\n\nKhông ghi đè bài có sẵn." : "Cần kiểm tra lại bản nháp."
        title: "Lưu bài mới vào thư viện?"

        onAccepted: draftService.confirmPublication()
        onRejected: draftService.publicationReview = null
    }
    ConfirmDialog {
        id: updateDialog
        objectName: "draftUpdateDialog"

        confirmEnabled: !draftService.backend.busy
        confirmText: "Cập nhật bài"
        danger: true
        message: draftService.updateReview ? "Thay thế bài " + draftService.updateReview.labId + " trong thư viện bằng bản nháp này.\n" + "Các phiên đang chạy sẽ bị từ chối; phiên đã dừng vẫn giữ nguyên bản snapshot cũ." : ""
        title: "Cập nhật bài lab đã cài đặt?"

        onAccepted: draftService.confirmUpdate()
        onRejected: draftService.updateReview = null
    }
    ConfirmDialog {
        id: reloadDraftDialog
        objectName: "draftReloadDialog"

        confirmEnabled: !draftService.backend.busy
        danger: true
        message: "Tải bản nháp mới nhất từ daemon. Thay đổi chưa lưu trong biểu mẫu và hướng dẫn sẽ bị bỏ."
        title: "Bỏ thay đổi chưa lưu?"

        onAccepted: draftService.openDraft(draftService.draft.id, true)
    }
    ConfirmDialog {
        id: deleteDraftDialog
        objectName: "draftDeleteDialog"

        confirmEnabled: !draftService.backend.busy
        confirmText: "Xóa nháp"
        danger: true
        message: "Xóa cả tài nguyên nháp và thay đổi chưa lưu. Bài đã xuất bản không bị xóa."
        title: "Xóa bản nháp?"

        onAccepted: draftService.deleteDraft()
    }
    ConfirmDialog {
        id: backDialog

        confirmEnabled: !draftService.backend.busy
        danger: true
        message: "Thay đổi trong bản nháp và hướng dẫn sẽ bị bỏ. Bản nháp đã lưu vẫn được giữ."
        title: "Bỏ thay đổi chưa lưu?"

        onAccepted: draftService.discardAndBack()
    }
}
