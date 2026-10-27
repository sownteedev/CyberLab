import QtQuick

Item {
    id: service
    required property var api
    property var session: null
    property var lab: null
    property string labDigest: ""
    property bool beforeStart: false
    property bool preparationRequired: false
    property var questions: []
    property var groups: []
    property string activeQuizId: ""
    property var displayQuestions: []
    property var answers: ({})
    property var quizResult: null
    property string error: ""
    property bool loading: false
    property bool submitting: false
    property int generation: 0
    property int answerRevision: 0
    readonly property bool canContinue: !!lab && beforeStart && !!labDigest && !loading && !submitting
        && !error && (!preparationRequired || (!!quizResult && quizResult.pre_start_completed === true))

    function clear() {
        generation++;
        session = null;
        lab = null;
        labDigest = "";
        beforeStart = false;
        preparationRequired = false;
        questions = [];
        groups = [];
        activeQuizId = "";
        displayQuestions = [];
        answers = {};
        quizResult = null;
        error = "";
        loading = false;
        submitting = false;
        answerRevision = 0;
    }
    function openFor(selectedSession) {
        clear();
        if (!selectedSession) return;
        session = selectedSession;
        try {
            const value = selectedSession.quiz;
            questions = Array.isArray(value) ? value : JSON.parse(value || "[]");
        } catch (problem) {
            error = "Không đọc được câu hỏi của phiên thực hành.";
            return;
        }
        if (!Array.isArray(questions) || questions.length === 0) {
            questions = [];
            return;
        }
        groupQuestions();
        const current = generation;
        const revision = answerRevision;
        loading = true;
        api.request(["quiz-result", session.id], (saved, problem) => {
            if (current !== service.generation) return;
            service.loading = false;
            if (revision !== service.answerRevision) return;
            service.error = problem || "";
            if (!problem && saved && saved.answers) {
                service.answers = Object.assign({}, saved.answers);
                service.quizResult = saved;
            }
        });
    }
    function openLab(selectedLab, preparationOnly) {
        clear();
        if (!selectedLab) return;
        lab = selectedLab;
        beforeStart = !!preparationOnly;
        loading = true;
        const current = generation;
        api.request(["lab-quiz", lab.id], (value, problem) => {
            if (current !== service.generation) return;
            service.loading = false;
            service.error = problem || "";
            if (problem) return;
            if (!value || value.lab_id !== service.lab.id || !/^[0-9a-f]{64}$/.test(value.lab_digest)
                    || !Array.isArray(value.questions)) {
                service.error = "Không đọc được câu hỏi của bài lab.";
                return;
            }
            service.labDigest = value.lab_digest;
            service.preparationRequired = !!value.pre_start_required;
            service.questions = value.questions;
            service.groupQuestions();
            service.answers = Object.assign({}, value.attempt ? value.attempt.answers : {});
            service.quizResult = value.attempt || null;
        });
    }
    function groupQuestions() {
        const grouped = {};
        questions.filter(item => !beforeStart || item.pre_start).forEach(item => {
            const id = item.quiz_id || "default";
            if (!grouped[id]) grouped[id] = {id: id, title: item.quiz_title || id, items: []};
            grouped[id].items.push(item);
        });
        groups = Object.keys(grouped).map(id => grouped[id]);
        activeQuizId = groups.length ? groups[0].id : "";
        refreshDisplayQuestions();
    }
    function refreshDisplayQuestions() {
        displayQuestions = questions.filter(item => (item.quiz_id || "default") === activeQuizId);
    }
    function selectQuiz(identifier) {
        if (!groups.some(group => group.id === identifier)) return;
        activeQuizId = identifier;
        refreshDisplayQuestions();
    }
    function setAnswer(identifier, selected) {
        if (submitting) return;
        const question = questions.find(item => item.id === identifier);
        if (!question || question.type === "preface" || !Number.isInteger(selected)
                || selected < 0 || selected >= question.options.length) return;
        const updated = Object.assign({}, answers);
        updated[identifier] = selected;
        answerRevision++;
        answers = updated;
        quizResult = null;
        error = "";
    }
    function submit() {
        if ((!session && !lab) || questions.length === 0 || loading || submitting || api.busy) return;
        const current = generation;
        const revision = answerRevision;
        const argv = lab ? ["lab-quiz", lab.id, "--digest", labDigest] : ["quiz", session.id];
        questions.forEach(question => {
            if (question.type !== "preface" && Number.isInteger(answers[question.id]))
                argv.push("--answer", question.id + "=" + answers[question.id]);
        });
        submitting = true;
        error = "";
        api.request(argv, (value, problem) => {
            if (current !== service.generation) return;
            service.submitting = false;
            if (revision !== service.answerRevision) return;
            service.error = problem || "";
            if (!problem) service.quizResult = value;
        });
    }
    function forget() {
        if (!lab || loading || submitting || api.busy) return;
        const current = generation;
        submitting = true;
        api.request(["delete-lab-quiz", lab.id, "--yes"], (value, problem) => {
            if (current !== service.generation) return;
            service.submitting = false;
            service.error = problem || "";
            if (!problem) {
                service.answers = {};
                service.quizResult = null;
                service.answerRevision++;
            }
        });
    }
    function statusText(status) {
        return ({CORRECT: "Đúng", INCORRECT: "Chưa đúng", UNANSWERED: "Chưa trả lời",
            UNASSESSED: "Không chấm", SKIPPED: "Bỏ qua theo câu trước", PREFACE: "Giới thiệu"})[status] || status;
    }
}
