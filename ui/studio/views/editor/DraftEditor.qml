import QtQuick
import QtQuick.Controls.Material
import QtQuick.Layouts
import "../.."
import "../.." as Studio

Control {
    id: draftEditor
    palette.window: Studio.Theme.surface
    palette.windowText: Studio.Theme.textOnSurface
    palette.text: Studio.Theme.textOnSurface
    palette.base: Studio.Theme.surfaceContainerLowest
    palette.alternateBase: Studio.Theme.surfaceContainer
    palette.button: Studio.Theme.surfaceContainer
    palette.buttonText: Studio.Theme.textOnSurface
    palette.highlight: Studio.Theme.primary
    palette.highlightedText: Studio.Theme.textOnPrimary
    palette.placeholderText: Studio.Theme.textOnSurfaceVariant
    required property var backend
    readonly property alias service: draftService
    signal backRequested()
    signal published()
    signal exportPackageRequested(var draft)

    DraftService {
        id: draftService
        backend: draftEditor.backend
        onBackRequested: draftEditor.backRequested()
        onPublished: draftEditor.published()
        onPublicationReviewRequested: publishDialog.open()
        onUpdateReviewRequested: updateDialog.open()
        onDiscardRequested: backDialog.open()
    }

    contentItem: DraftWorkspace {
        editor: draftService
        onReloadRequested: {
            if (draftService.dirty) reloadDraftDialog.open();
            else draftService.openDraft(draftService.draft.id);
        }
        onDeleteRequested: deleteDraftDialog.open()
        onExportPackageRequested: draftEditor.exportPackageRequested(draftService.draft)
    }
    ConfirmDialog {
        id: publishDialog
        title: "Lưu bài mới vào thư viện?"
        confirmText: "Lưu vào thư viện"
        confirmEnabled: draftService.canConfirmPublication && !draftService.backend.busy
        message: draftService.publicationReview
            ? draftService.publicationReview.name + " (" + draftService.publicationReview.labId + ")\n"
                + draftService.publicationReview.nodes + " máy · " + draftService.publicationReview.networks + " mạng · "
                + draftService.publicationReview.assets + " file"
                + "\n\nKhông ghi đè bài có sẵn.\n"
                + (draftService.publicationReview.runtimeVerified ? "Đã kiểm tra môi trường chạy." : "Chưa xác minh môi trường Docker thực tế.")
            : "Cần kiểm tra lại bản nháp."
        onAccepted: draftService.confirmPublication()
        onRejected: draftService.publicationReview = null
    }
    ConfirmDialog {
        id: updateDialog
        title: "Cập nhật bài lab đã cài đặt?"
        confirmText: "Cập nhật bài"
        danger: true
        confirmEnabled: !draftService.backend.busy
        message: draftService.updateReview
            ? "Thay thế bài " + draftService.updateReview.labId + " trong thư viện bằng bản nháp này.\n"
                + "Các phiên đang chạy sẽ bị từ chối; phiên đã dừng vẫn giữ nguyên bản snapshot cũ."
            : ""
        onAccepted: draftService.confirmUpdate()
        onRejected: draftService.updateReview = null
    }
    ConfirmDialog {
        id: reloadDraftDialog
        title: "Bỏ thay đổi chưa lưu?"
        message: "Tải bản nháp mới nhất từ daemon. Thay đổi chưa lưu trong biểu mẫu và hướng dẫn sẽ bị bỏ."
        danger: true
        confirmEnabled: !draftService.backend.busy
        onAccepted: draftService.openDraft(draftService.draft.id)
    }
    ConfirmDialog {
        id: deleteDraftDialog
        title: "Xóa bản nháp?"
        message: "Xóa cả tài nguyên nháp và thay đổi chưa lưu. Bài đã xuất bản không bị xóa."
        danger: true
        confirmText: "Xóa nháp"
        confirmEnabled: !draftService.backend.busy
        onAccepted: draftService.deleteDraft()
    }
    ConfirmDialog {
        id: backDialog
        title: "Bỏ thay đổi chưa lưu?"
        message: "Thay đổi trong bản nháp và hướng dẫn sẽ bị bỏ. Bản nháp đã lưu vẫn được giữ."
        danger: true
        confirmEnabled: !draftService.backend.busy
        onAccepted: draftService.discardAndBack()
    }
}
