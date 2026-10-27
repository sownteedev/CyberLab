import QtQuick
import QtQuick.Layouts
import ".."
import ".." as Studio

Rectangle {
    id: content
    required property var api
    required property var controller
    required property var dialogs
    readonly property var editor: draftEditor.service
    signal navigationRequested(int index)
    signal showPageRequested(int index)
    function startLab(lab) {
        if (lab && lab.pre_start_quiz) {
            if (!api.capabilities.includes("lab-quiz")) {
                api.error = "Daemon chưa hỗ trợ Quiz trước khi mở bài.";
                return;
            }
            preparationQuiz.openLab(lab, true);
        } else parameterDialog.openFor(lab);
    }
    color: Studio.Theme.surface

    Connections {
        target: content.dialogs
        function onImportedDraftOpened() {
            content.showPageRequested(2);
        }
    }

    RowLayout {
        anchors.fill: parent
        anchors.margins: Studio.Theme.contentInset
        spacing: Studio.Theme.contentGap

        StudioNavigationRail {
            currentIndex: content.controller.page
            onIndexRequested: index => content.navigationRequested(index)
        }
        ColumnLayout {
            Layout.fillWidth: true
            Layout.fillHeight: true
            spacing: Studio.Theme.contentGap
            InlineError {
                Layout.fillWidth: true
                message: content.api.error
                dismissible: true
                onDismissed: content.api.error = ""
            }
            StackLayout {
                Layout.fillWidth: true
                Layout.fillHeight: true
                currentIndex: content.controller.page

                LibraryView {
                    objectName: "libraryView"
                    labs: content.controller.labs
                    sessions: content.controller.sessions
                    selectedLab: content.controller.selectedLab
                    manual: content.controller.manual
                    connected: content.controller.connected
                    busy: content.api.busy
                    deletionSupported: content.api.capabilities.includes("delete-lab")
                    reportsSupported: content.api.capabilities.includes("checkwork")
                    packageSupported: content.api.capabilities.includes("lab-package-export")
                    reviewSupported: content.api.capabilities.includes("submission-review")
                    quizSupported: content.api.capabilities.includes("lab-quiz")
                    onQuizRequested: lab => content.dialogs.showLabQuiz(lab)
                    onReportsRequested: content.dialogs.showReports(null)
                    onReviewSubmissionsRequested: caller => content.dialogs.reviewSubmissions(caller)
                    onImportPackageRequested: content.dialogs.importLabPackage()
                    onExportPackageRequested: lab => content.dialogs.exportLabPackage(lab)
                    onSelectLabRequested: lab => content.controller.selectLab(lab)
                    onStartLabRequested: lab => content.startLab(lab)
                    onOpenSessionRequested: session => content.controller.selectSession(session)
                    onResumeSessionRequested: session => content.controller.resumeSession(session)
                    onCloneLabRequested: lab => content.editor.cloneLab(lab.id, lab.id + "-clone",
                        lab.name + " (Bản sao)", () => content.showPageRequested(2))
                    onEditLabRequested: lab => content.editor.editLab(lab.id, () => content.showPageRequested(2))
                    onDeleteLabRequested: lab => content.dialogs.confirmDeleteLab(lab)
                }
                SessionView {
                    session: content.controller.selectedSession
                    sessions: content.controller.sessions
                    lab: (content.controller.labs || []).find(lab => lab.id === (session ? session.lab_id : "")) || null
                    sessionImports: content.controller.sessionImports
                    workspaces: content.controller.workspaces
                    workspaceErrors: content.controller.workspaceErrors
                    workspaceSupported: content.api.capabilities.includes("workspace-files")
                    persistenceSupported: content.api.capabilities.includes("session-persistence")
                    discardSupported: content.api.capabilities.includes("discard-checkpoint")
                    checkworkSupported: content.api.capabilities.includes("checkwork")
                    onReportsRequested: selected => content.dialogs.showReports(selected)
                    quizSupported: content.api.capabilities.includes("quiz")
                    onQuizRequested: selected => content.dialogs.showQuiz(selected)
                    submissionSupported: content.api.capabilities.includes("submit-and-finish")
                    onSubmissionRequested: (selected, caller) => content.dialogs.submitSession(selected, caller)
                    manual: content.controller.manual
                    busy: content.api.busy
                    onSessionRequested: session => content.controller.selectSession(session)
                    onBackRequested: content.showPageRequested(0)
                    onResetRequested: sessionId => content.dialogs.confirmLifecycle("reset", sessionId)
                    onStopRequested: sessionId => content.dialogs.confirmLifecycle("stop", sessionId)
                    onSaveRequested: sessionId => content.controller.saveSession(sessionId)
                    onSuspendRequested: sessionId => content.controller.suspendSession(sessionId)
                    onResumeRequested: session => content.controller.resumeSession(session)
                    onDiscardRequested: sessionId => content.dialogs.confirmDiscard(sessionId)
                    onTerminalRequested: (session, node, slot) => content.api.terminal(session, node, slot)
                    onAllTerminalsRequested: session => content.api.allTerminals(session)
                    onImportFileRequested: (sessionId, node) => content.dialogs.importFile(sessionId, node)
                    onRefreshFilesRequested: node => content.controller.refreshWorkspaces(node)
                    onImportFolderRequested: (sessionId, node) => content.dialogs.importFolder(sessionId, node)
                    onExportRequested: (sessionId, node, path, directory) => content.dialogs.exportFiles(sessionId, node, path, directory)
                }
                DraftEditor {
                    id: draftEditor
                    Layout.fillWidth: true
                    Layout.fillHeight: true
                    backend: content.api
                    onExportPackageRequested: draft => content.dialogs.exportDraftPackage(draft)
                    onBackRequested: content.showPageRequested(0)
                    onPublished: {
                        content.controller.notice = "Đã lưu bài mới vào thư viện.";
                        content.controller.refresh(true);
                        content.controller.page = 0;
                    }
                }
            }
        }
    }
    QuizDialog {
        id: preparationQuiz
        objectName: "preparationQuizDialog"
        api: content.api
        onStartRequested: lab => parameterDialog.openFor(lab)
    }
    ParameterDialog {
        id: parameterDialog
        onParametersAccepted: (lab, values) => content.controller.startLab(lab, values)
    }
}
