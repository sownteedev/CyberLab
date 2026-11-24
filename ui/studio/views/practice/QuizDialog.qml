pragma ComponentBehavior: Bound
import QtQuick
import QtQuick.Controls.Basic
import QtQuick.Layouts
import "../.."
import "../.." as Studio

Studio.StudioDialog {
    id: dialog

    readonly property var answers: service.answers
    property var api
    readonly property var displayQuestions: service.displayQuestions
    readonly property var questions: service.questions
    readonly property var quizGroups: service.groups
    readonly property var quizResult: service.quizResult
    property Item returnFocus: null
    property QuizService service: QuizService {
        api: dialog.api
    }
    readonly property var session: service.session

    signal startRequested(var lab)

    function openFor(selectedSession) {
        if (!visible && parent && parent.Window.window)
            returnFocus = parent.Window.window.activeFocusItem;
        service.openFor(selectedSession);
        if (service.questions.length)
            open();
    }
    function openLab(selectedLab, beforeStart) {
        if (!visible && parent && parent.Window.window)
            returnFocus = parent.Window.window.activeFocusItem;
        service.openLab(selectedLab, beforeStart);
        if (service.lab)
            open();
    }
    function setAnswer(identifier, selected) {
        service.setAnswer(identifier, selected);
    }
    function submit() {
        service.submit();
    }

    anchors.centerIn: parent
    closePolicy: Popup.CloseOnEscape | Popup.CloseOnPressOutside
    focus: true
    height: Math.min(720, parent ? parent.height - Studio.Theme.space32 : 720)
    modal: true
    objectName: "quizDialog"
    padding: Studio.Theme.space24
    topPadding: Studio.Theme.space8
    parent: Overlay.overlay
    width: Math.min(760, parent ? parent.width - Studio.Theme.space32 : 760)

    contentItem: ColumnLayout {
        spacing: Studio.Theme.space12

        Label {
            Layout.fillWidth: true
            color: Studio.Theme.textOnSurfaceVariant
            text: dialog.service.lab ? dialog.service.lab.name : dialog.session ? dialog.session.lab_name + " · " + dialog.questions.filter(item => item.type !== "preface").length + " câu" : ""
            textFormat: Text.PlainText
            wrapMode: Text.WordWrap
        }
        Label {
            Layout.fillWidth: true
            color: Studio.Theme.textOnSurfaceVariant
            font.pixelSize: Studio.Theme.bodySmall
            text: "Trả lời đủ để vào thực hành, không cần đúng hết."
            visible: dialog.service.beforeStart
            wrapMode: Text.WordWrap
        }
        StudioComboBox {
            Accessible.name: "Bộ câu hỏi"
            Layout.fillWidth: true
            currentIndex: Math.max(0, dialog.quizGroups.findIndex(group => group.id === dialog.service.activeQuizId))
            model: dialog.quizGroups.map(group => group.title || group.id)
            visible: dialog.quizGroups.length > 1

            onActivated: if (currentIndex >= 0)
                dialog.service.selectQuiz(dialog.quizGroups[currentIndex].id)
        }
        InlineError {
            Layout.fillWidth: true
            message: dialog.service.error
        }
        Label {
            Layout.fillWidth: true
            color: Studio.Theme.textOnSurfaceVariant
            font.pixelSize: Studio.Theme.bodySmall
            objectName: "quizAnswerProgress"
            text: dialog.service.loading ? "Đang tải câu hỏi…" : "Đã trả lời "
                + dialog.questions.filter(item => item.type !== "preface" && Number.isInteger(dialog.answers[item.id])).length
                + "/" + dialog.questions.filter(item => item.type !== "preface").length + " câu"
        }
        LoadingState {
            Layout.fillWidth: true
            busy: dialog.service.loading || dialog.service.submitting
            visible: busy
        }
        ScrollView {
            id: questionsScroll

            Layout.fillHeight: true
            Layout.fillWidth: true
            clip: true
            contentWidth: availableWidth
            objectName: "quizQuestionsScroll"

            ColumnLayout {
                spacing: Studio.Theme.space12
                width: questionsScroll.availableWidth

                Repeater {
                    model: dialog.displayQuestions

                    delegate: QuizQuestionCard {
                        required property int index
                        required property var modelData

                        Layout.fillWidth: true
                        question: modelData
                        number: dialog.displayQuestions.slice(0, index + 1).filter(item => item.type !== "preface").length
                        service: dialog.service
                    }
                }
            }
        }
        Label {
            Layout.fillWidth: true
            color: dialog.quizResult && dialog.quizResult.passed ? Studio.Theme.success : Studio.Theme.textOnSurfaceVariant
            font.pixelSize: Studio.Theme.titleSmall
            text: !dialog.quizResult ? "" : dialog.service.beforeStart ? (dialog.quizResult.pre_start_completed ? "Đã hoàn thành phần chuẩn bị" : "Còn câu chuẩn bị chưa trả lời") : dialog.quizResult.graded === 0 ? "Đã lưu câu trả lời" : (dialog.quizResult.passed ? "Đã đạt: " : "Kết quả: ") + dialog.quizResult.correct + "/" + dialog.quizResult.graded
            visible: !!dialog.quizResult
            wrapMode: Text.WordWrap
        }
    }
    footer: Studio.StudioDialogFooter {
        contentItem: GridLayout {
            columns: dialog.service.beforeStart ? (width < 460 ? 2 : 3) : (dialog.service.lab ? 2 : 1)
            columnSpacing: Studio.Theme.space8
            rowSpacing: Studio.Theme.space8

            StudioIconButton {
                danger: true
                description: "Xóa câu trả lời của bài đã lưu"
                enabled: !!dialog.quizResult && !dialog.api.busy && !dialog.service.loading && !dialog.service.submitting
                iconName: "delete"
                objectName: "forgetLabQuizButton"
                visible: !!dialog.service.lab

                onClicked: forgetConfirmation.open()
            }
            StudioButton {
                Layout.fillWidth: true
                enabled: (!!dialog.session || !!dialog.service.lab) && dialog.questions.length > 0 && !dialog.quizResult && !dialog.api.busy && !dialog.service.loading && !dialog.service.submitting
                highlighted: !dialog.service.canContinue
                iconName: "check"
                objectName: "submitQuizButton"
                text: dialog.service.submitting ? "Đang lưu…" : dialog.quizResult ? "Đã xem đáp án" : "Xem đáp án"

                onClicked: dialog.submit()
            }
            StudioButton {
                Layout.fillWidth: true
                Layout.columnSpan: parent.columns === 2 ? 2 : 1
                enabled: dialog.service.canContinue && !dialog.api.busy
                highlighted: true
                iconName: "play_arrow"
                objectName: "continueAfterQuizButton"
                text: "Vào thực hành"
                visible: dialog.service.beforeStart

                onClicked: {
                    const selected = dialog.service.lab;
                    dialog.close();
                    dialog.startRequested(selected);
                }
            }
        }
    }
    header: Studio.StudioDialogHeader {
        id: dialogHeader
        title: dialog.service.beforeStart ? "Quiz trước thực hành" : "Quiz"
        iconName: "help"
        closeDescription: "Đóng câu hỏi"
        onCloseRequested: dialog.close()
    }

    onAboutToHide: {
        forgetConfirmation.close();
        service.clear();
    }
    onClosed: {
        if (returnFocus)
            returnFocus.forceActiveFocus(Qt.TabFocusReason);
    }
    onOpened: dialogHeader.closeButton.forceActiveFocus(Qt.TabFocusReason)

    ConfirmDialog {
        id: forgetConfirmation

        confirmEnabled: !dialog.api.busy && !dialog.service.submitting
        confirmText: "Xóa câu trả lời"
        danger: true
        message: "Bạn sẽ làm lại câu hỏi của bài. Câu trả lời trong phiên thực hành và báo cáo cũ không bị thay đổi."
        title: "Xóa câu trả lời đã lưu?"

        onAccepted: dialog.service.forget()
    }
}
