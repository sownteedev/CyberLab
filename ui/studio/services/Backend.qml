import QtQuick
import Quickshell
import Quickshell.Io

Item {
    id: backend
    visible: false
    property bool busy: foregroundActive || pending.some(job => job.blocking)
    readonly property bool loading: foregroundLoading || pending.some(job => !job.background)
    property bool foregroundActive: false
    property bool foregroundLoading: false
    property bool inFlight: false
    property bool demo: Quickshell.env("CYBERLAB_STUDIO_TEST_BUS") === "1"
    property var capabilities: []
    property string error: ""
    property var pending: []
    property var prefix: [Quickshell.env("CYBERLAB_STUDIO_PYTHON"), "-I", "-m", "cyberlab_cli.main"].concat(demo ? ["--test-session-bus"] : [])

    function isReadOnly(argv) {
        return ["info", "labs", "sessions", "docs", "files", "imports", "reports", "report", "quiz-result", "review-submissions"].includes(argv[0]);
    }

    function request(argv, callback, input, background) {
        if (background && pending.some(job => job.background && JSON.stringify(job.arguments) === JSON.stringify(argv))) return;
        pending = pending.concat([{
            arguments: argv,
            callback: callback,
            input: input === undefined ? "" : input,
            background: !!background,
            blocking: !background && !isReadOnly(argv)
        }]);
        pump();
    }
    function pump() {
        if (inFlight || pending.length === 0) return;
        let job = pending[0];
        inFlight = true;
        foregroundActive = job.blocking;
        foregroundLoading = !job.background;
        pending = pending.slice(1);
        let process = worker.createObject(backend, { job: job, command: prefix.concat(job.arguments) });
        process.running = true;
    }
    function finish(process, code, status) {
        if (process.finished) return;
        process.finished = true;
        let result = null;
        let problem = "";
        try { result = JSON.parse(process.output.text); }
        catch (exception) { problem = "CLI không trả về dữ liệu hợp lệ. " + process.errors.text; }
        if (code !== 0 || status !== 0) problem = process.errors.text || (result && result.error) || problem || "Thao tác không thành công.";
        if (problem && !process.job.background) { error = problem; console.warn("CyberLab CLI: " + problem); }
        try {
            if (process.job.callback) process.job.callback(result, problem);
        } finally {
            foregroundActive = false;
            foregroundLoading = false;
            inFlight = false;
            process.destroy();
            pump();
        }
    }
    function notify(message, failure) {
        if (!message || demo) return;
        let process = worker.createObject(backend, {
            command: [Quickshell.env("CYBERLAB_STUDIO_PYTHON"), "-I", "-m", "cyberlab_cli.notifications",
                      failure ? "CyberLab · Lỗi" : "CyberLab", message.substring(0, 4096)]
        });
        process.startDetached();
        process.destroy();
    }
    function terminal(session, node, slot) {
        if (!session || session.state !== "RUNNING" || !/^[a-f0-9]{32}$/.test(session.id)
                || !/^[a-z][a-z0-9]*(-[a-z0-9]+)*$/.test(node) || !Number.isInteger(slot) || slot < 0 || slot > 3) {
            error = "Terminal không hợp lệ hoặc phiên chưa chạy.";
            return;
        }
        request(["open-terminals", session.id, "--node", node, "--slot", String(slot)], null);
    }
    function allTerminals(session) {
        if (!session || session.state !== "RUNNING") return;
        request(["open-terminals", session.id], null);
    }

    Component {
        id: worker
        Process {
            id: process
            property var job: null
            property bool didStart: false
            property bool finished: false
            property alias output: output
            property alias errors: errors
            environment: ({ "LD_LIBRARY_PATH": null, "LD_PRELOAD": null, "QT_PLUGIN_PATH": null,
                              "QML_IMPORT_PATH": null, "QML2_IMPORT_PATH": null, "QT_QPA_PLATFORM": null })
            stdinEnabled: job !== null && job.input.length > 0
            stdout: StdioCollector { id: output }
            stderr: StdioCollector { id: errors }
            onStarted: {
                didStart = true;
                if (job && job.input.length > 0) {
                    write(job.input);
                    stdinEnabled = false;
                }
            }
            onExited: (code, status) => {
                if (job) Qt.callLater(() => backend.finish(process, code, status));
            }
            property Timer startupTimer: Timer {
                interval: 10000; running: process.job !== null && !process.didStart && !process.finished
                onTriggered: {
                    backend.error = "Không khởi động được CLI. Kiểm tra môi trường .venv của CyberLab.";
                    backend.finish(process, -1, 1);
                }
            }
            property Timer executionTimer: Timer {
                interval: 180000
                running: process.job !== null && process.didStart && !process.finished
                onTriggered: {
                    process.running = false;
                    backend.finish(process, -1, 1);
                }
            }
        }
    }
}
