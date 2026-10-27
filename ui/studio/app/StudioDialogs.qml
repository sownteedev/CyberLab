import QtQuick
import ".."

Item {
    id: dialogs
    required property var api
    required property var controller
    required property var editor
    property string action: ""
    property string sessionId: ""
    property var lab: null
    property int pendingPage: 0
    readonly property bool confirmationOpened: navigation.opened || closing.opened || lifecycle.opened
        || discard.opened || deletion.opened || submission.confirmationOpened
    signal navigationConfirmed(int index)
    signal closeConfirmed()
    signal importedDraftOpened()

    function confirmNavigation(index) { pendingPage = index; navigation.open(); }
    function confirmClose() { closing.open(); }
    function confirmLifecycle(operation, identifier) {
        action = operation;
        sessionId = identifier;
        lifecycle.open();
    }
    function confirmDiscard(identifier) { sessionId = identifier; discard.open(); }
    function confirmDeleteLab(selectedLab) { lab = selectedLab; deletion.open(); }
    function importFile(session, node) { workspace.importFile(session, node); }
    function importFolder(session, node) { workspace.importFolder(session, node); }
    function exportFiles(session, node, path, directory) { workspace.exportFiles(session, node, path, directory); }
    function showReports(session) {
        checkwork.openFor(session ? session.id : "");
        reportDialog.open();
    }
    function showQuiz(session) {
        quiz.openFor(session);
    }
    function showLabQuiz(selectedLab) { quiz.openLab(selectedLab, false); }
    function reviewSubmissions(caller) { submissions.openFor(caller); }
    function submitSession(session, caller) { submission.openFor(session, caller); }
    function exportLabPackage(selectedLab) { packages.exportPackage(selectedLab, "lab"); }
    function exportDraftPackage(selectedDraft) { packages.exportPackage(selectedDraft, "draft"); }
    function importLabPackage() { packages.importPackage(); }

    CheckworkService { id: checkwork; api: dialogs.api }
    CheckworkDialog {
        id: reportDialog
        service: checkwork
        session: dialogs.controller.sessions.find(entry => entry.id === checkwork.sessionId) || null
        connected: dialogs.controller.connected && dialogs.api.capabilities.includes("checkwork")
    }
    QuizDialog { id: quiz; api: dialogs.api }
    SubmissionReviewDialog { id: submissions; api: dialogs.api }
    SubmissionDialog { id: submission; api: dialogs.api; onSettled: dialogs.controller.refresh(true) }

    LabPackageDialogs {
        id: packages
        api: dialogs.api
        editor: dialogs.editor
        onDraftOpened: dialogs.importedDraftOpened()
    }

    ConfirmDialog {
        id: navigation
        objectName: "navigationConfirmation"
        title: "Bỏ thay đổi chưa lưu?"
        message: "Thay đổi trong biểu mẫu và hướng dẫn sẽ bị bỏ. Bản nháp đã lưu vẫn được giữ."
        danger: true
        confirmEnabled: !dialogs.api.busy
        onAccepted: { dialogs.editor.discardAndBack(); dialogs.navigationConfirmed(dialogs.pendingPage); }
    }
    ConfirmDialog {
        id: closing
        objectName: "closeConfirmation"
        title: "Đóng CyberLab Studio?"
        message: "Thay đổi nháp chưa lưu sẽ mất. Đóng UI không tự dừng Session thật."
        danger: true
        confirmText: "Đóng Studio"
        onAccepted: dialogs.closeConfirmed()
    }
    ConfirmDialog {
        id: lifecycle
        objectName: "lifecycleConfirmation"
        title: dialogs.action === "reset" ? "Reset bài thực hành?" : "Dừng bài thực hành?"
        message: dialogs.action === "reset"
            ? "Dữ liệu hiện tại và bản lưu tiến độ sẽ bị xóa. Phiên trở về file ban đầu; bài lab gốc không thay đổi."
            : "Dữ liệu chưa lưu sẽ mất. Bản lưu gần nhất (nếu có) vẫn được giữ để tiếp tục. Bài lab gốc không thay đổi."
        danger: true
        confirmEnabled: !dialogs.api.busy
        onAccepted: dialogs.controller.lifecycle(dialogs.action, dialogs.sessionId)
    }
    ConfirmDialog {
        id: discard
        objectName: "discardConfirmation"
        title: "Xóa bản lưu thực hành?"
        message: "Tiến độ trong bản lưu sẽ bị xóa vĩnh viễn. Phiên đang chạy và bài lab gốc không bị thay đổi. Phiên đã tạm dừng sẽ không còn tiếp tục được."
        confirmText: "Xóa bản lưu"
        danger: true
        confirmEnabled: !dialogs.api.busy && dialogs.controller.connected
            && dialogs.api.capabilities.includes("discard-checkpoint")
            && dialogs.controller.sessions.some(session => session.id === dialogs.sessionId && session.saved)
        onAccepted: dialogs.controller.discardCheckpoint(dialogs.sessionId)
    }
    ConfirmDialog {
        id: deletion
        objectName: "deleteLabConfirmation"
        title: "Xóa bài lab?"
        message: dialogs.lab
            ? "Xóa vĩnh viễn \"" + dialogs.lab.name + "\" (" + dialogs.lab.id + ").\n\nCấu hình, hướng dẫn và file ban đầu của bài cùng lịch sử phiên đã dừng sẽ bị xóa khỏi VM. Bản nháp và Docker image vẫn được giữ. Không thể hoàn tác."
            : "Bài lab sẽ bị xóa khỏi thư viện VM."
        confirmText: "Xóa bài lab"
        danger: true
        confirmEnabled: !dialogs.api.busy && !!dialogs.lab && dialogs.controller.connected
            && dialogs.api.capabilities.includes("delete-lab")
            && !dialogs.controller.sessions.some(session => session.lab_id === dialogs.lab.id && session.state !== "STOPPED")
        onAccepted: { dialogs.controller.deleteLab(dialogs.lab); dialogs.lab = null; }
        onRejected: dialogs.lab = null
    }
    WorkspaceDialogs { id: workspace; api: dialogs.api; controller: dialogs.controller }
}
