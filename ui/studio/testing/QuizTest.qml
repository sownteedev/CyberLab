import QtQuick
import QtQuick.Controls.Basic
import QtTest
import ".." as Studio

Item {
    id: checks
    property string screenshotFolder: ""
    readonly property var questions: [
        {id: "first", type: "choice", question: "Lệnh nào hiển thị địa chỉ mạng?", options: ["ip addr", "mkdir"], quiz_id: "network", pre_start: true},
        {id: "second", type: "choice", question: "Lệnh nào tạo thư mục?", options: ["ip addr", "mkdir"], quiz_id: "network", pre_start: true}
    ]
    QtObject {
        id: backend
        property bool busy: false
        property var requests: []
        property bool delayed: false
        property var callback: null
        function request(argv, done) {
            requests = requests.concat([argv]);
            if (delayed) { callback = done; return; }
            if (argv.length === 2) {
                done({lab_id: "fixture", lab_digest: "a".repeat(64), pre_start_required: true, questions: checks.questions}, "");
                return;
            }
            const answers = {};
            for (let index = 0; index < argv.length; index++) {
                if (argv[index] === "--answer") {
                    const parts = argv[++index].split("=");
                    answers[parts[0]] = Number(parts[1]);
                }
            }
            const correct = checks.questions.filter((question, index) => answers[question.id] === index).length;
            done({answers: answers, passed: correct === 2, correct: correct, graded: 2,
                pre_start_completed: Number.isInteger(answers.first) && Number.isInteger(answers.second),
                questions: checks.questions.map((question, index) => ({id: question.id,
                    selected: answers[question.id], status: Number.isInteger(answers[question.id]) ? (answers[question.id] === index ? "CORRECT" : "INCORRECT") : "UNANSWERED",
                    correct_answer: Number.isInteger(answers[question.id]) ? index : undefined, explanation: "Ghi nhớ lệnh để thực hành."}))}, "");
        }
    }
    ApplicationWindow {
        id: window
        width: 1100
        height: 820
        visible: true
        color: Studio.Theme.surface
        Studio.QuizDialog { id: quiz; api: backend }
        SignalSpy { id: starts; target: quiz; signalName: "startRequested" }
        TestCase {
            name: "PreparationQuiz"
            when: window.visible
            function control(name) {
                return findChild(quiz.contentItem, name) || findChild(quiz.footer, name);
            }
            function init() {
                Studio.Theme.themeMode = "dark";
                Studio.Theme.reducedMotion = true;
                backend.requests = [];
                backend.delayed = false;
                backend.callback = null;
                starts.clear();
                window.width = 1100;
                window.requestActivate();
                tryCompare(window, "active", true);
                quiz.openLab({id: "fixture", name: "Làm quen với mạng"}, true);
                tryCompare(quiz, "visible", true);
                wait(80);
            }
            function cleanup() { quiz.close(); wait(80); }
            function test_wrong_answers_reveal_review_without_starting() {
                quiz.setAnswer("first", 1);
                quiz.setAnswer("second", 0);
                quiz.submit();
                verify(quiz.service.canContinue);
                compare(starts.count, 0);
                const correct = control("quizOption-first-0");
                verify(correct !== null, "Correct answer must be displayed after submitting");
                verify(correct.visible);
                verify(correct.correctAnswer);
                compare(correct.contentItem.color, Studio.Theme.success);
                verify(!correct.contentItem.font.strikeout);
                const wrong = control("quizOption-first-1");
                verify(wrong.wrongAnswer);
                compare(wrong.contentItem.color, Studio.Theme.error);
                verify(wrong.contentItem.font.strikeout);
                compare(control("continueAfterQuizButton").text, "Vào thực hành");
                if (checks.screenshotFolder)
                    grabImage(window.contentItem).save(checks.screenshotFolder + "/quiz-review.png");
                mouseClick(control("continueAfterQuizButton"));
                compare(starts.count, 1);
                compare(starts.signalArguments[0][0].id, "fixture");
            }
            function test_no_feedback_before_submit() {
                quiz.setAnswer("first", 1);
                const option = control("quizOption-first-1");
                compare(option.wrongAnswer, false);
                compare(option.correctAnswer, false);
                verify(!option.contentItem.font.strikeout);
            }
            function test_correct_selection_is_green_not_struck() {
                quiz.setAnswer("first", 0);
                quiz.setAnswer("second", 1);
                quiz.submit();
                const correct = control("quizOption-first-0");
                verify(correct.correctAnswer);
                verify(!correct.wrongAnswer);
                compare(correct.contentItem.color, Studio.Theme.success);
                verify(!correct.contentItem.font.strikeout);
                verify(!control("quizOption-first-1").wrongAnswer);
                compare(control("quizQuestionStatus-first").text, "Đúng");
            }
            function test_same_answer_preserves_review() {
                quiz.setAnswer("first", 1);
                quiz.setAnswer("second", 0);
                quiz.submit();
                const result = quiz.quizResult;
                mouseClick(control("quizOption-first-1"));
                compare(quiz.quizResult, result);
                verify(quiz.service.canContinue);
            }
            function test_keyboard_selection() {
                const option = control("quizOption-first-1");
                option.forceActiveFocus(Qt.TabFocusReason);
                verify(option.activeFocus);
                keyClick(Qt.Key_Space);
                compare(quiz.answers.first, 1);
                verify(option.checked);
                verify(!control("quizOption-first-0").checked);
                compare(quiz.quizResult, null);
            }
            function test_ungraded_feedback_stays_neutral_data() {
                return [
                    {tag: "unanswered", status: "UNANSWERED"},
                    {tag: "unassessed", status: "UNASSESSED"},
                    {tag: "skipped", status: "SKIPPED"}
                ];
            }
            function test_ungraded_feedback_stays_neutral(data) {
                quiz.service.quizResult = {questions: [{id: "first", status: data.status}]};
                const option = control("quizOption-first-1");
                verify(!option.wrongAnswer);
                verify(!option.correctAnswer);
                verify(!option.contentItem.font.strikeout);
                compare(control("quizQuestionStatus-first").text, quiz.service.statusText(data.status));
            }
            function test_long_options_wrap() {
                window.width = 420;
                quiz.service.questions = [{id: "long", type: "choice", pre_start: true, question: "Chọn cách khôi phục dữ liệu an toàn", options: ["Giữ lại bằng chứng, kiểm tra nội dung bản sao lưu trước khi khôi phục và đối chiếu kết quả.", "x".repeat(180)]}];
                quiz.service.groupQuestions();
                waitForRendering(quiz.contentItem);
                const option = control("quizOption-long-0");
                verify(option.height > Studio.Theme.controlHeight);
                const unbroken = control("quizOption-long-1");
                verify(unbroken.contentItem.lineCount > 1);
                const bounds = option.mapToItem(null, 0, 0, option.width, option.height);
                verify(bounds.x >= 0 && bounds.x + bounds.width <= window.width);
                if (checks.screenshotFolder)
                    grabImage(window.contentItem).save(checks.screenshotFolder + "/quiz-long-options.png");
            }
            function test_loading_disables_submission() {
                backend.delayed = true;
                quiz.openLab({id: "fixture", name: "Bài đang tải"}, true);
                verify(quiz.service.loading);
                compare(control("quizAnswerProgress").text, "Đang tải câu hỏi…");
                verify(!control("submitQuizButton").enabled);
                verify(!control("continueAfterQuizButton").enabled);
            }
            function test_preface_has_no_grading() {
                quiz.service.questions = [{id: "intro", type: "preface", pre_start: true, text: "Đọc tình huống trước khi trả lời."}];
                quiz.service.groupQuestions();
                waitForRendering(quiz.contentItem);
                const card = control("quizQuestion-intro");
                verify(card.preface);
                verify(!control("quizQuestionStatus-intro").visible);
                verify(control("quizOption-intro-0") === null);
            }
            function test_light_review() {
                Studio.Theme.themeMode = "light";
                quiz.setAnswer("first", 1);
                quiz.setAnswer("second", 1);
                quiz.submit();
                waitForRendering(quiz.contentItem);
                compare(control("quizOption-first-1").contentItem.color, Studio.Theme.error);
                compare(control("quizOption-second-1").contentItem.color, Studio.Theme.success);
                if (checks.screenshotFolder)
                    grabImage(window.contentItem).save(checks.screenshotFolder + "/quiz-review-light.png");
            }
            function test_incomplete_answers_do_not_allow_start() {
                quiz.setAnswer("first", 1);
                quiz.submit();
                verify(!quiz.service.canContinue);
                verify(!control("continueAfterQuizButton").enabled);
                quiz.close();
                compare(starts.count, 0);
            }
            function test_edit_after_review_requires_resubmit() {
                quiz.setAnswer("first", 1);
                quiz.setAnswer("second", 0);
                quiz.submit();
                quiz.setAnswer("first", 0);
                verify(!quiz.service.canContinue);
                compare(quiz.quizResult, null);
            }
            function test_close_ignores_late_submission() {
                quiz.setAnswer("first", 1);
                backend.delayed = true;
                quiz.submit();
                const done = backend.callback;
                quiz.close();
                wait(80);
                done({pre_start_completed: true}, "");
                compare(quiz.quizResult, null);
                compare(starts.count, 0);
            }
            function test_narrow_review_stays_inside_dialog() {
                window.width = 420;
                quiz.setAnswer("first", 1);
                quiz.setAnswer("second", 0);
                quiz.submit();
                wait(80);
                const button = control("continueAfterQuizButton");
                const bounds = button.mapToItem(null, 0, 0, button.width, button.height);
                verify(bounds.x >= 0 && bounds.x + bounds.width <= window.width);
                if (checks.screenshotFolder)
                    grabImage(window.contentItem).save(checks.screenshotFolder + "/quiz-review-narrow.png");
            }
        }
    }
}
