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

    signal showPageRequested(int index)

    function startLab(lab) {
        if (api.busy || api.starting) return;
        if (lab && lab.pre_start_quiz) {
            if (!api.capabilities.includes("lab-quiz")) {
                api.error = "Daemon chưa hỗ trợ Quiz trước khi mở bài.";
                return;
            }
            preparationQuiz.openLab(lab, true);
        } else
            parameterDialog.openFor(lab);
    }

    color: Studio.Theme.surface

    Connections {
        function onImportedDraftOpened() {
            content.showPageRequested(2);
        }

        target: content.dialogs
    }
    RowLayout {
        anchors.fill: parent
        anchors.margins: Studio.Theme.contentInset
        anchors.topMargin: 0
        objectName: "studioPageLayout"
        spacing: Studio.Theme.contentGap

        ColumnLayout {
            Layout.fillHeight: true
            Layout.fillWidth: true
            spacing: Studio.Theme.contentGap

            StackLayout {
                Layout.fillHeight: true
                Layout.fillWidth: true
                currentIndex: content.controller.page

                LibraryView {
                    busy: content.api.busy
                    starting: !!content.api.starting
                    connected: content.controller.connected
                    deletionSupported: content.api.capabilities.includes("delete-lab")
                    labs: content.controller.labs
                    manual: content.controller.manual
                    objectName: "libraryView"
                    packageSupported: content.api.capabilities.includes("lab-package-export")
                    quizSupported: content.api.capabilities.includes("lab-quiz")
                    reportsSupported: content.api.capabilities.includes("checkwork")
                    reviewSupported: content.api.capabilities.includes("submission-review")
                    selectedLab: content.controller.selectedLab
                    sessions: content.controller.sessions

                    onCloneLabRequested: lab => content.editor.cloneLab(lab.id, lab.id + "-clone", lab.name + " (Bản sao)", () => content.showPageRequested(2))
                    onDeleteLabRequested: lab => content.dialogs.confirmDeleteLab(lab)
                    onEditLabRequested: lab => content.editor.editLab(lab.id, () => content.showPageRequested(2))
                    onExportPackageRequested: lab => content.dialogs.exportLabPackage(lab)
                    onImportPackageRequested: content.dialogs.importLabPackage()
                    onOpenSessionRequested: session => content.controller.selectSession(session)
                    onQuizRequested: lab => content.dialogs.showLabQuiz(lab)
                    onReportsRequested: content.dialogs.showReports(null)
                    onResumeSessionRequested: session => content.controller.resumeSession(session)
                    onReviewSubmissionsRequested: caller => content.dialogs.reviewSubmissions(caller)
                    onSelectLabRequested: lab => content.controller.selectLab(lab)
                    onStartLabRequested: lab => content.startLab(lab)
                }
                SessionView {
                    desktopSupported: content.api.capabilities.includes("seamless-apps")
                    busy: content.api.busy
                    starting: !!content.api.starting
                    checkworkSupported: content.api.capabilities.includes("checkwork")
                    discardSupported: content.api.capabilities.includes("discard-checkpoint")
                    lab: (content.controller.labs || []).find(lab => lab.id === (session ? session.lab_id : "")) || null
                    manual: content.controller.manual
                    persistenceSupported: content.api.capabilities.includes("session-persistence")
                    quizSupported: content.api.capabilities.includes("quiz")
                    session: content.controller.selectedSession
                    sessions: content.controller.sessions
                    submissionSupported: content.api.capabilities.includes("submit-and-finish")

                    onAllTerminalsRequested: session => content.api.allTerminals(session)
                    onBackRequested: content.showPageRequested(0)
                    onDiscardRequested: sessionId => content.dialogs.confirmDiscard(sessionId)
                    onQuizRequested: selected => content.dialogs.showQuiz(selected)
                    onReportsRequested: selected => content.dialogs.showReports(selected)
                    onResetRequested: sessionId => content.dialogs.confirmLifecycle("reset", sessionId)
                    onResumeRequested: session => content.controller.resumeSession(session)
                    onSaveRequested: sessionId => content.controller.saveSession(sessionId)
                    onSessionRequested: session => content.controller.selectSession(session)
                    onStopRequested: sessionId => content.dialogs.confirmLifecycle("stop", sessionId)
                    onSubmissionRequested: (selected, caller) => content.dialogs.submitSession(selected, caller)
                    onSuspendRequested: sessionId => content.controller.suspendSession(sessionId)
                    onTerminalRequested: (session, node, slot) => content.api.terminal(session, node, slot)
                    onDesktopRequested: (session, node) => content.dialogs.openDesktop(session, node)
                }
                DraftEditor {
                    id: draftEditor

                    Layout.fillHeight: true
                    Layout.fillWidth: true
                    backend: content.api

                    onBackRequested: content.showPageRequested(0)
                    onExportPackageRequested: draft => content.dialogs.exportDraftPackage(draft)
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

        api: content.api
        objectName: "preparationQuizDialog"

        onStartRequested: lab => parameterDialog.openFor(lab)
    }
    ParameterDialog {
        id: parameterDialog

        onParametersAccepted: (lab, values) => content.controller.startLab(lab, values)
    }
}
