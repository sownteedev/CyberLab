import QtQuick
import ".."

Item {
    id: dialogs

    property string action: ""
    required property var api
    readonly property bool confirmationOpened: navigation.opened || closing.opened || lifecycle.opened || discard.opened || deletion.opened || submission.confirmationOpened || desktop.opened
    required property var controller
    required property var editor
    property var lab: null
    property int pendingPage: 0
    property string sessionId: ""

    signal closeConfirmed
    signal importedDraftOpened
    signal navigationConfirmed(int index)

    function openDesktop(session, node) {
        desktop.openFor(session, node);
    }
    DesktopDialog {
        id: desktop
        api: dialogs.api
    }

    function confirmClose() {
        closing.open();
    }
    function confirmDeleteLab(selectedLab) {
        lab = selectedLab;
        deletion.open();
    }
    function confirmDiscard(identifier) {
        sessionId = identifier;
        discard.open();
    }
    function confirmLifecycle(operation, identifier) {
        action = operation;
        sessionId = identifier;
        lifecycle.open();
    }
    function confirmNavigation(index) {
        pendingPage = index;
        navigation.open();
    }
    function exportDraftPackage(selectedDraft) {
        packages.exportPackage(selectedDraft, "draft");
    }
    function exportFiles(session, node, path, directory) {
        workspace.exportFiles(session, node, path, directory);
    }
    function exportLabPackage(selectedLab) {
        packages.exportPackage(selectedLab, "lab");
    }
    function importFile(session, node) {
        workspace.importFile(session, node);
    }
    function importFolder(session, node) {
        workspace.importFolder(session, node);
    }
    function importLabPackage() {
        packages.importPackage();
    }
    function reviewSubmissions(caller) {
        submissions.openFor(caller);
    }
    function showLabQuiz(selectedLab) {
        quiz.openLab(selectedLab, false);
    }
    function showQuiz(session) {
        quiz.openFor(session);
    }
    function showReports(session) {
        checkwork.openFor(session ? session.id : "");
        reportDialog.open();
    }
    function submitSession(session, caller) {
        submission.openFor(session, caller);
    }

    CheckworkService {
        id: checkwork

        api: dialogs.api
    }
    CheckworkDialog {
        id: reportDialog

        connected: dialogs.controller.connected && dialogs.api.capabilities.includes("checkwork")
        service: checkwork
        session: dialogs.controller.sessions.find(entry => entry.id === checkwork.sessionId) || null
    }
    QuizDialog {
        id: quiz

        api: dialogs.api
    }
    SubmissionReviewDialog {
        id: submissions

        api: dialogs.api
    }
    SubmissionDialog {
        id: submission

        api: dialogs.api

        onSettled: dialogs.controller.refresh(true)
    }
    LabPackageDialogs {
        id: packages

        api: dialogs.api
        editor: dialogs.editor

        onDraftOpened: dialogs.importedDraftOpened()
        onLibraryReloadRequested: dialogs.controller.refresh(true)
    }
    ConfirmDialog {
        id: navigation

        confirmEnabled: !dialogs.api.busy
        danger: true
        message: "Thay đổi trong biểu mẫu và hướng dẫn sẽ bị bỏ. Bản nháp đã lưu vẫn được giữ."
        objectName: "navigationConfirmation"
        title: "Bỏ thay đổi chưa lưu?"

        onAccepted: {
            dialogs.editor.discardAndBack();
            dialogs.navigationConfirmed(dialogs.pendingPage);
        }
    }
    ConfirmDialog {
        id: closing

        confirmText: "Đóng Studio"
        danger: true
        message: dialogs.api.starting ? "Bài đang khởi động ngầm. Đóng Studio không dừng bài, nhưng terminal sẽ không tự mở. Thay đổi chưa lưu sẽ mất." : "Thay đổi nháp chưa lưu sẽ mất. Đóng UI không tự dừng Session thật."
        objectName: "closeConfirmation"
        title: "Đóng CyberLab Studio?"

        onAccepted: dialogs.closeConfirmed()
    }
    ConfirmDialog {
        id: lifecycle

        confirmEnabled: !dialogs.api.busy
        confirmText: dialogs.action === "reset" ? qsTr("Làm lại từ đầu") : qsTr("Dừng bài")
        danger: true
        message: dialogs.action === "reset" ? "Dữ liệu hiện tại và bản lưu tiến độ sẽ bị xóa. Phiên trở về file ban đầu; bài lab gốc không thay đổi." : "Dữ liệu chưa lưu sẽ mất. Bản lưu gần nhất (nếu có) vẫn được giữ để tiếp tục. Bài lab gốc không thay đổi."
        objectName: "lifecycleConfirmation"
        title: dialogs.action === "reset" ? qsTr("Làm lại từ đầu?") : qsTr("Dừng không lưu thay đổi mới?")

        onAccepted: dialogs.controller.lifecycle(dialogs.action, dialogs.sessionId)
    }
    ConfirmDialog {
        id: discard

        confirmEnabled: !dialogs.api.busy && dialogs.controller.connected && dialogs.api.capabilities.includes("discard-checkpoint") && dialogs.controller.sessions.some(session => session.id === dialogs.sessionId && session.saved)
        confirmText: "Xóa bản lưu"
        danger: true
        message: "Tiến độ trong bản lưu sẽ bị xóa vĩnh viễn. Phiên đang chạy và bài lab gốc không bị thay đổi. Phiên đã tạm dừng sẽ không còn tiếp tục được."
        objectName: "discardConfirmation"
        title: "Xóa bản lưu thực hành?"

        onAccepted: dialogs.controller.discardCheckpoint(dialogs.sessionId)
    }
    ConfirmDialog {
        id: deletion

        confirmEnabled: !dialogs.api.busy && !!dialogs.lab && dialogs.controller.connected && dialogs.api.capabilities.includes("delete-lab") && !dialogs.controller.sessions.some(session => session.lab_id === dialogs.lab.id && session.state !== "STOPPED")
        confirmText: "Xóa bài lab"
        danger: true
        message: dialogs.lab ? "Xóa vĩnh viễn \"" + dialogs.lab.name + "\" (" + dialogs.lab.id + ").\n\nCấu hình, hướng dẫn và file ban đầu của bài cùng lịch sử phiên đã dừng sẽ bị xóa khỏi VM. Bản nháp và Docker image vẫn được giữ. Không thể hoàn tác." : "Bài lab sẽ bị xóa khỏi thư viện VM."
        objectName: "deleteLabConfirmation"
        title: "Xóa bài lab?"

        onAccepted: {
            dialogs.controller.deleteLab(dialogs.lab);
            dialogs.lab = null;
        }
        onRejected: dialogs.lab = null
    }
    WorkspaceDialogs {
        id: workspace

        api: dialogs.api
        controller: dialogs.controller
    }
}
