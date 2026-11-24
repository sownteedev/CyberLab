import QtQuick
import Quickshell
import Quickshell.Io

Item {
    id: backend

    property bool busy: foregroundActive || pending.some(job => job.blocking)
    property var capabilities: []
    property bool demo: Quickshell.env("CYBERLAB_STUDIO_TEST_BUS") === "1"
    property string error: ""
    property bool foregroundActive: false
    property bool foregroundLoading: false
    property bool inFlight: false
    property bool startupActive: false
    readonly property bool starting: startupActive || pending.some(job => silentStartup(job.arguments))
    readonly property bool loading: foregroundLoading || pending.some(job => !job.background && !silentStartup(job.arguments))
    property var pending: []
    property var editGrants: ({})
    property var editWaiting: []
    property var editPrompt: null
    property int editGeneration: 0
    property var prefix: [Quickshell.env("CYBERLAB_STUDIO_PYTHON"), "-I", "-m", "cyberlab_cli.main"].concat(demo ? ["--test-session-bus"] : [])

    signal notificationRequested(string message, bool failure)
    signal editUnlockRequested(string kind, string identifier, string message)
    signal editUnlockDismissed()

    function editResource(argv) {
        if (argv[0] === "draft" && !["info", "list", "create", "software-search", "read-local"].includes(argv[1]))
            return {kind: ["edit", "clone"].includes(argv[1]) ? "lab" : "draft", id: argv[2]};
        if (["export-draft", "export-lab", "delete-lab"].includes(argv[0]))
            return {kind: argv[0] === "export-draft" ? "draft" : "lab", id: argv[1]};
        return null;
    }
    function editKey(resource) { return resource ? resource.kind + ":" + resource.id : ""; }
    function editLocked(problem) {
        const marker = "org.ptit.CyberLab1.Error.EditLocked: ";
        const position = String(problem).indexOf(marker);
        if (position < 0) return null;
        try {
            const value = JSON.parse(String(problem).substring(position + marker.length).trim());
            return ["lab", "draft"].includes(value.kind) && typeof value.id === "string" ? value : null;
        } catch (exception) { return null; }
    }
    function promptEditing() {
        if (editPrompt || !editWaiting.length) return;
        editPrompt = editWaiting[0].resource;
        editUnlockRequested(editPrompt.kind, editPrompt.id, editPrompt.message || "");
    }
    function revokeEditing(token, completed) {
        if (!token) { if (completed) completed(); return; }
        request(["edit-access", "revoke"], () => { if (completed) completed(); }, JSON.stringify({token: token}), true);
    }
    function rememberEditing(resource, token) {
        const key = editKey(resource);
        const previous = editGrants[key];
        const grants = Object.assign({}, editGrants);
        if (token) grants[key] = token;
        else delete grants[key];
        editGrants = grants;
        if (previous && previous !== token) revokeEditing(previous);
    }
    function clearEditing(completed, keepKey) {
        editGeneration++;
        const retained = keepKey && editGrants[keepKey];
        const tokens = Object.keys(editGrants).filter(key => key !== keepKey).map(key => editGrants[key]);
        editGrants = retained ? {[keepKey]: retained} : {};
        const cancelled = editWaiting.concat(pending.filter(job => !!job.resource));
        editWaiting = [];
        pending = pending.filter(job => !job.resource);
        editPrompt = null;
        editUnlockDismissed();
        cancelled.forEach(job => { if (job.callback) job.callback(null, "Đã đóng yêu cầu chỉnh sửa."); });
        let remaining = tokens.length;
        if (!remaining && completed) completed();
        tokens.forEach(token => revokeEditing(token, () => { if (--remaining === 0 && completed) completed(); }));
    }
    function cancelEditUnlock() {
        const key = editKey(editPrompt);
        const cancelled = editWaiting.filter(job => editKey(job.resource) === key);
        editWaiting = editWaiting.filter(job => editKey(job.resource) !== key);
        editPrompt = null;
        cancelled.forEach(job => { if (job.callback) job.callback(null, "Đã hủy mở khóa chỉnh sửa."); });
        Qt.callLater(promptEditing);
    }
    function unlockEditing(password, completed) {
        if (!editPrompt) return;
        const resource = editPrompt;
        const generation = editGeneration;
        request(["edit-access", "unlock"], (result, problem) => {
            if (generation !== editGeneration || editPrompt !== resource) {
                if (result && result.token) revokeEditing(result.token);
                return;
            }
            if (problem || !result || !result.token) {
                completed(null, "Không mở khóa được. Kiểm tra mật khẩu hoặc đợi rồi thử lại.");
                return;
            }
            rememberEditing(resource, result.token);
            const retry = editWaiting.filter(job => editKey(job.resource) === editKey(resource));
            editWaiting = editWaiting.filter(job => editKey(job.resource) !== editKey(resource));
            editPrompt = null;
            completed({edit_protected: result.edit_protected}, "");
            pending = retry.concat(pending);
            Qt.callLater(promptEditing);
        }, JSON.stringify({kind: resource.kind, id: resource.id, password: password}));
    }
    function setEditPassword(resource, currentPassword, newPassword, completed) {
        const generation = editGeneration;
        request(["edit-access", "protect"], (result, problem) => {
            if (generation !== editGeneration) {
                if (result && result.token) revokeEditing(result.token);
                return;
            }
            if (problem || !result) {
                completed(null, "Không đổi được mật khẩu. Kiểm tra mật khẩu hiện tại hoặc đợi rồi thử lại.");
                return;
            }
            rememberEditing(resource, result.token || "");
            completed({edit_protected: !!result.edit_protected}, "");
        }, JSON.stringify({kind: resource.kind, id: resource.id, currentPassword: currentPassword, newPassword: newPassword}));
    }

    function allTerminals(session) {
        if (!session || session.state !== "RUNNING")
            return;
        request(["open-terminals", session.id], terminalFeedback);
    }
    function finish(process, code, status) {
        if (process.finished)
            return;
        process.finished = true;
        let result = null;
        let problem = "";
        try {
            result = JSON.parse(process.output.text);
        } catch (exception) {
            problem = "CLI không trả về dữ liệu hợp lệ. " + process.errors.text;
        }
        if (code !== 0 || status !== 0)
            problem = process.errors.text || (result && result.error) || problem || "Thao tác không thành công.";
        const job = process.job;
        const stale = job.resource && job.generation !== editGeneration;
        const locked = !stale && editLocked(problem);
        if (locked) {
            job.resource = locked;
            const old = editGrants[editKey(locked)];
            const grants = Object.assign({}, editGrants);
            delete grants[editKey(locked)];
            editGrants = grants;
            if (old) revokeEditing(old);
            editWaiting = editWaiting.concat([job]);
            promptEditing();
        }
        if (result && result.edit_token) {
            const token = result.edit_token;
            delete result.edit_token;
            if (stale) revokeEditing(token);
            else rememberEditing({kind: "draft", id: result.id}, token);
        } else if (!stale && !problem && result && result.id && job.arguments[0] === "draft" && job.arguments[1] === "edit") {
            const key = editKey(job.resource);
            const token = editGrants[key];
            if (token) {
                const grants = Object.assign({}, editGrants, {["draft:" + result.id]: token});
                delete grants[key];
                editGrants = grants;
            }
        }
        if (problem && !locked && !stale && job.arguments[0] !== "edit-access" && !job.background) {
            reportError(problem);
            console.warn("CyberLab CLI: " + problem);
        }
        try {
            if (!locked && job.callback)
                job.callback(stale ? null : result, stale ? "Đã đóng yêu cầu chỉnh sửa." : problem);
        } finally {
            if (silentStartup(process.job.arguments)) {
                startupActive = false;
            } else {
                foregroundActive = false;
                foregroundLoading = false;
                inFlight = false;
            }
            process.destroy();
            pump();
        }
    }
    function isReadOnly(argv) {
        return ["info", "labs", "sessions", "docs", "files", "imports", "reports", "report", "quiz-result", "review-submissions", "terminal-apps", "inspect-labtainer"].includes(argv[0]);
    }
    function silentStartup(argv) {
        return ["start", "resume", "reset"].includes(argv[0]);
    }
    function requestTimeout(argv) {
        return silentStartup(argv) ? 7500000 : 180000;
    }
    function notify(message, failure) {
        if (!message)
            return;
        notificationRequested(String(message), !!failure);
    }
    function reportError(message) {
        const value = String(message || "");
        if (value && error === value) errorChanged();
        else error = value;
    }
    function pump() {
        const index = pending.findIndex(job => silentStartup(job.arguments) ? !startupActive : !inFlight);
        if (index < 0)
            return;
        let job = pending[index];
        if (silentStartup(job.arguments)) {
            startupActive = true;
        } else {
            inFlight = true;
            foregroundActive = job.blocking;
            foregroundLoading = !job.background;
        }
        pending = pending.filter((entry, position) => position !== index);
        const token = editGrants[editKey(job.resource)] || "";
        let process = worker.createObject(backend, {
            job: job,
            command: prefix.concat(token ? ["--edit-context"] : []).concat(job.arguments),
            payload: token ? JSON.stringify({token: token, input: job.input}) : job.input
        });
        process.running = true;
        pump();
    }
    function request(argv, callback, input, background) {
        if (background && argv[0] !== "edit-access" && pending.some(job => job.background && JSON.stringify(job.arguments) === JSON.stringify(argv)))
            return;
        pending = pending.concat([
            {
                arguments: argv,
                callback: callback,
                resource: editResource(argv),
                generation: editGeneration,
                input: input === undefined ? "" : input,
                background: !!background,
                blocking: !background && !isReadOnly(argv) && !silentStartup(argv)
            }
        ]);
        pump();
    }
    function terminal(session, node, slot) {
        if (!session || session.state !== "RUNNING" || !/^[a-f0-9]{32}$/.test(session.id) || !/^[a-z][a-z0-9]*(-[a-z0-9]+)*$/.test(node) || !Number.isInteger(slot) || slot < 0 || slot > 3) {
            reportError("Cửa sổ dòng lệnh không hợp lệ hoặc phiên chưa chạy.");
            return;
        }
        request(["open-terminals", session.id, "--node", node, "--slot", String(slot)], terminalFeedback);
    }
    function terminalFeedback(result, problem) {
        if (!problem && result && result.terminal_launch && result.terminal_launch.warnings.length)
            reportError(result.terminal_launch.warnings.join("\n"));
    }

    visible: false

    Component {
        id: worker

        Process {
            id: process

            property bool didStart: false
            property alias errors: errors
            property Timer executionTimer: Timer {
                interval: process.job ? backend.requestTimeout(process.job.arguments) : 180000
                running: process.job !== null && process.didStart && !process.finished

                onTriggered: {
                    process.running = false;
                    backend.finish(process, -1, 1);
                }
            }
            property bool finished: false
            property var job: null
            property string payload: ""
            property alias output: output
            property Timer startupTimer: Timer {
                interval: 10000
                running: process.job !== null && !process.didStart && !process.finished

                onTriggered: {
                    backend.reportError("Không khởi động được CLI. Kiểm tra môi trường .venv của CyberLab.");
                    backend.finish(process, -1, 1);
                }
            }

            environment: ({
                    "LD_LIBRARY_PATH": null,
                    "LD_PRELOAD": null,
                    "QT_PLUGIN_PATH": null,
                    "QML_IMPORT_PATH": null,
                    "QML2_IMPORT_PATH": null,
                    "QT_QPA_PLATFORM": null
                })
            stdinEnabled: payload.length > 0

            stderr: StdioCollector {
                id: errors
            }
            stdout: StdioCollector {
                id: output
            }

            onExited: (code, status) => {
                if (job)
                    Qt.callLater(() => backend.finish(process, code, status));
            }
            onStarted: {
                didStart = true;
                if (job && payload.length > 0) {
                    write(payload);
                    payload = "";
                    if (job.arguments[0] === "edit-access") job.input = "";
                    stdinEnabled = false;
                }
            }
        }
    }
}
