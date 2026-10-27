import QtQuick

Item {
    id: service
    required property var api
    property string sessionId: ""
    property var reports: []
    property var report: null
    property string error: ""
    property int generation: 0
    property int selectionGeneration: 0
    property bool loading: false
    property bool checking: false

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
        loading = true;
        api.request(sessionId ? ["reports", sessionId] : ["reports"], (result, problem) => {
            if (current !== generation) return;
            loading = false;
            error = problem || "";
            if (problem) return;
            reports = result || [];
            if (report && reports.some(entry => entry.id === report.id)) return;
            report = null;
            if (reports.length) selectReport(reports[0].id);
        });
    }
    function selectReport(identifier) {
        const current = generation;
        const selection = ++selectionGeneration;
        loading = true;
        api.request(["report", identifier], (result, problem) => {
            if (current !== generation || selection !== selectionGeneration) return;
            loading = false;
            error = problem || "";
            if (!problem) report = result;
        });
    }
    function check() {
        if (!sessionId || checking || api.busy) return;
        const current = generation;
        selectionGeneration++;
        checking = true;
        error = "";
        api.request(["checkwork", sessionId], (result, problem) => {
            if (current !== generation) return;
            checking = false;
            error = problem || "";
            if (problem) return;
            report = result;
            refresh();
        });
    }
    function remove(identifier) {
        const current = generation;
        api.request(["delete-report", identifier, "--yes"], (result, problem) => {
            if (current !== generation) return;
            error = problem || "";
            if (!problem) refresh();
        });
    }
    function exportReport(identifier, path) {
        api.request(["export-submission", identifier, path], (result, problem) => {
            if (!problem) api.notify("Đã xuất bài nộp: " + result.destination, false);
        });
    }
}
