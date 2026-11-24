import QtQuick

Item {
    id: service

    required property var api
    property bool checking: false
    property string error: ""
    property int generation: 0
    property bool loading: false
    property var report: null
    property var reports: []
    property int selectionGeneration: 0
    property string sessionId: ""

    function check() {
        if (!sessionId || checking || api.busy)
            return;
        const current = generation;
        selectionGeneration++;
        loading = false;
        checking = true;
        error = "";
        api.request(["checkwork", sessionId], (result, problem) => {
            if (current !== generation)
                return;
            checking = false;
            error = problem || "";
            if (problem)
                return;
            report = result;
            refresh();
        });
    }
    function exportReport(identifier, path) {
        api.request(["export-submission", identifier, path], (result, problem) => {
            if (problem)
                return;
            if (!result || typeof result.destination !== "string" || !result.destination.trim()) {
                api.notify("Chưa xác nhận được việc xuất bài nộp. Hãy kiểm tra tệp đích rồi thử lại.", true);
                return;
            }
            api.notify("Đã xuất bài nộp: " + result.destination, false);
        });
    }
    function openFor(identifier) {
        generation++;
        selectionGeneration++;
        sessionId = identifier || "";
        report = null;
        reports = [];
        error = "";
        checking = false;
        refresh();
    }
    function refresh() {
        const current = generation;
        const selection = selectionGeneration;
        loading = true;
        api.request(sessionId ? ["reports", sessionId] : ["reports"], (result, problem) => {
            if (current !== generation)
                return;
            if (selection === selectionGeneration)
                loading = false;
            error = problem || "";
            if (problem)
                return;
            reports = result || [];
            if (selection !== selectionGeneration)
                return;
            if (report && reports.some(entry => entry.id === report.id))
                return;
            report = null;
            if (reports.length)
                selectReport(reports[0].id);
        });
    }
    function remove(identifier) {
        const current = generation;
        api.request(["delete-report", identifier, "--yes"], (result, problem) => {
            if (current !== generation)
                return;
            error = problem || "";
            if (!problem)
                refresh();
        });
    }
    function selectReport(identifier) {
        const current = generation;
        const selection = ++selectionGeneration;
        loading = true;
        api.request(["report", identifier], (result, problem) => {
            if (current !== generation || selection !== selectionGeneration)
                return;
            loading = false;
            error = problem || "";
            if (!problem)
                report = result;
        });
    }
}
