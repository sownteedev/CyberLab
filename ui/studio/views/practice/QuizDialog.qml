pragma ComponentBehavior: Bound
import QtQuick
import QtQuick.Controls.Basic
import QtQuick.Layouts
import "../.."
import "../.." as Studio

Dialog {
    id: dialog
    objectName: "quizDialog"
    property var api
    property QuizService service: QuizService { api: dialog.api }
    readonly property var session: service.session
    readonly property var questions: service.questions
    readonly property var displayQuestions: service.displayQuestions
    readonly property var quizGroups: service.groups
    readonly property var answers: service.answers
    readonly property var quizResult: service.quizResult
    property Item returnFocus: null
    signal startRequested(var lab)

    function openFor(selectedSession) {
        if (!visible && parent && parent.Window.window)
            returnFocus = parent.Window.window.activeFocusItem;
        service.openFor(selectedSession);
        if (service.questions.length) open();
    }
    function setAnswer(identifier, selected) {
        service.setAnswer(identifier, selected);
    }
    function submit() {
        service.submit();
    }
    function openLab(selectedLab, beforeStart) {
        if (!visible && parent && parent.Window.window)
            returnFocus = parent.Window.window.activeFocusItem;
        service.openLab(selectedLab, beforeStart);
        if (service.lab) open();
    }

    parent: Overlay.overlay
    anchors.centerIn: parent
    width: Math.min(760, parent ? parent.width - Studio.Theme.space32 : 760)
    height: Math.min(720, parent ? parent.height - Studio.Theme.space32 : 720)
    padding: Studio.Theme.space16
    modal: true
    focus: true
    closePolicy: Popup.CloseOnEscape | Popup.CloseOnPressOutside
    onOpened: closeButton.forceActiveFocus(Qt.TabFocusReason)
    onClosed: {
        forgetConfirmation.close();
        service.clear();
        if (returnFocus) returnFocus.forceActiveFocus(Qt.TabFocusReason);
    }
    background: Rectangle { radius: Studio.Theme.shapeExtraLarge; color: Studio.Theme.surfaceContainerHigh }
    Overlay.modal: Rectangle { color: Studio.Theme.scrim }
    header: RowLayout {
        implicitHeight: Studio.Theme.appBarHeight
        Label {
            Layout.fillWidth: true
            Layout.leftMargin: Studio.Theme.space16
            text: dialog.service.beforeStart ? "Chuẩn bị trước khi mở bài" : "Câu hỏi"
            color: Studio.Theme.textOnSurface
            font.pixelSize: Studio.Theme.titleMedium
        }
        StudioIconButton {
            id: closeButton
            Layout.rightMargin: Studio.Theme.space8
            iconName: "close"
            description: "Đóng câu hỏi"
            onClicked: dialog.close()
        }
    }
    contentItem: ColumnLayout {
        spacing: Studio.Theme.space12
        Label {
            Layout.fillWidth: true
            text: dialog.service.lab ? dialog.service.lab.name
                : dialog.session ? dialog.session.lab_name + " · "
                    + dialog.questions.filter(item => item.type !== "preface").length + " câu" : ""
            textFormat: Text.PlainText
            wrapMode: Text.WordWrap
            color: Studio.Theme.textOnSurfaceVariant
        }
        Label {
            Layout.fillWidth: true
            visible: dialog.service.beforeStart
            text: "Trả lời phần chuẩn bị trước khi mở terminal. Không yêu cầu đúng tất cả."
            wrapMode: Text.WordWrap
            color: Studio.Theme.textOnSurfaceVariant
            font.pixelSize: Studio.Theme.bodySmall
        }
        StudioComboBox {
            Layout.fillWidth: true
            visible: dialog.quizGroups.length > 1
            model: dialog.quizGroups.map(group => group.title || group.id)
            currentIndex: Math.max(0, dialog.quizGroups.findIndex(group => group.id === dialog.service.activeQuizId))
            Accessible.name: "Bộ câu hỏi"
            onActivated: if (currentIndex >= 0) dialog.service.selectQuiz(dialog.quizGroups[currentIndex].id)
        }
        InlineError { Layout.fillWidth: true; message: dialog.service.error }
        ScrollView {
            id: questionsScroll
            objectName: "quizQuestionsScroll"
            Layout.fillWidth: true
            Layout.fillHeight: true
            clip: true
            contentWidth: availableWidth
            ColumnLayout {
                width: questionsScroll.availableWidth
                spacing: Studio.Theme.space12
                Repeater {
                    model: dialog.displayQuestions
                    delegate: QuizQuestionCard {
                        required property var modelData
                        Layout.fillWidth: true
                        question: modelData
                        service: dialog.service
                    }
                }
            }
        }
        Label {
            Layout.fillWidth: true
            visible: !!dialog.quizResult
            text: !dialog.quizResult ? "" : dialog.service.beforeStart
                ? (dialog.quizResult.pre_start_completed ? "Đã hoàn thành phần chuẩn bị" : "Còn câu chuẩn bị chưa trả lời")
                : dialog.quizResult.graded === 0 ? "Đã lưu câu trả lời"
                : (dialog.quizResult.passed ? "Đã đạt: " : "Kết quả: ") + dialog.quizResult.correct + "/" + dialog.quizResult.graded
            color: dialog.quizResult && dialog.quizResult.passed ? Studio.Theme.success : Studio.Theme.textOnSurfaceVariant
            font.pixelSize: Studio.Theme.titleSmall
        }
    }
    footer: RowLayout {
        spacing: Studio.Theme.space8
        StudioIconButton {
            objectName: "forgetLabQuizButton"
            Layout.leftMargin: Studio.Theme.space16
            Layout.topMargin: Studio.Theme.space8
            Layout.bottomMargin: Studio.Theme.space16
            visible: !!dialog.service.lab
            iconName: "delete"
            description: "Xóa câu trả lời của bài đã lưu"
            danger: true
            enabled: !!dialog.quizResult && !dialog.api.busy && !dialog.service.loading && !dialog.service.submitting
            onClicked: forgetConfirmation.open()
        }
        Item { Layout.fillWidth: true }
        StudioButton {
            objectName: "submitQuizButton"
            Layout.topMargin: Studio.Theme.space8
            Layout.bottomMargin: Studio.Theme.space16
            Layout.rightMargin: dialog.service.beforeStart ? 0 : Studio.Theme.space16
            text: "Nộp câu trả lời"
            iconName: "check"
            highlighted: !dialog.service.canContinue
            enabled: (!!dialog.session || !!dialog.service.lab) && dialog.questions.length > 0
                && !dialog.api.busy && !dialog.service.loading && !dialog.service.submitting
            onClicked: dialog.submit()
        }
        StudioButton {
            objectName: "continueAfterQuizButton"
            Layout.topMargin: Studio.Theme.space8
            Layout.bottomMargin: Studio.Theme.space16
            Layout.rightMargin: Studio.Theme.space16
            visible: dialog.service.beforeStart
            text: "Tiếp tục"
            iconName: "play_arrow"
            highlighted: true
            enabled: dialog.service.canContinue && !dialog.api.busy
            onClicked: {
                const selected = dialog.service.lab;
                dialog.close();
                dialog.startRequested(selected);
            }
        }
    }
    ConfirmDialog {
        id: forgetConfirmation
        title: "Xóa câu trả lời đã lưu?"
        message: "Bạn sẽ làm lại câu hỏi của bài. Câu trả lời trong phiên thực hành và báo cáo cũ không bị thay đổi."
        confirmText: "Xóa câu trả lời"
        danger: true
        confirmEnabled: !dialog.api.busy && !dialog.service.submitting
        onAccepted: dialog.service.forget()
    }
}
