import QtQuick

Item {
    id: controller

    required property var api
    property bool connected: false
    property int importGeneration: 0
    property var labs: []
    property string manual: "Chọn một bài lab để xem hướng dẫn."
    property int manualGeneration: 0
    property string manualKey: ""
    property string notice: ""
    property int page: 0
    property var selectedLab: null
    property var selectedSession: null
    property var sessionImports: []
    property var sessions: []
    property bool smoke: false
    property var workspaceErrors: ({})
    property int workspaceGeneration: 0
    property var workspaces: ({})

    function confirmedSession(session, identifier, error, expectedState, requireCheckpoint) {
        if (session && session.id === identifier && selectedSession && selectedSession.id === identifier)
            selectedSession = session;
        if (error)
            return false;
        if (!session || session.id !== identifier || session.state !== expectedState || (requireCheckpoint && session.saved !== true)) {
            api.error = "Chưa xác nhận được trạng thái phiên thực hành. Kiểm tra lại trạng thái trước khi thử lại.";
            return false;
        }
        return true;
    }

    function deleteLab(lab) {
        if (!lab || api.busy)
            return;
        if (!api.capabilities.includes("delete-lab")) {
            api.error = "Daemon chưa hỗ trợ xóa bài. Cần cập nhật runtime trước.";
            return;
        }
        if (sessions.some(session => session.lab_id === lab.id && session.state !== "STOPPED")) {
            api.error = "Dừng tất cả phiên của bài trước khi xóa (kể cả phiên lỗi).";
            return;
        }
        const identifier = lab.id;
        const title = lab.name;
        api.error = "";
        api.request(["delete-lab", identifier, "--yes"], (result, error) => {
            if (error)
                return;
            if (result !== true) {
                api.error = "Daemon chưa xác nhận xóa bài.";
                return;
            }
            labs = labs.filter(entry => entry.id !== identifier);
            sessions = sessions.filter(session => session.lab_id !== identifier);
            if (selectedSession && selectedSession.lab_id === identifier) {
                importGeneration += 1;
                selectedSession = null;
                sessionImports = [];
            }
            if (selectedLab && selectedLab.id === identifier) {
                if (page === 0)
                    selectLab(labs[0] || null);
                else
                    selectedLab = labs[0] || null;
            }
            notice = "Đã xóa bài lab " + title + ".";
            refresh(true);
        });
    }
    function discardCheckpoint(identifier) {
        if (!identifier || api.busy || !api.capabilities.includes("discard-checkpoint"))
            return;
        api.request(["discard", identifier, "--yes"], (session, error) => {
            if (!error && session && session.id === identifier && session.saved === false) {
                if (selectedSession && selectedSession.id === identifier) {
                    selectedSession = session;
                    if (session.state !== "RUNNING") {
                        importGeneration += 1;
                        workspaceGeneration += 1;
                        sessionImports = [];
                        workspaces = ({});
                        workspaceErrors = ({});
                    }
                }
                notice = "Đã xóa bản lưu. Bài lab gốc không thay đổi.";
            }
            refreshSessions();
        });
    }
    function lifecycle(action, identifier) {
        if (!identifier || api.busy || (action === "reset" && api.starting) || !["stop", "reset"].includes(action))
            return;
        const generation = manualGeneration;
        const requestedPage = page;
        api.request([action, identifier], (session, error) => {
            const confirmed = confirmedSession(session, identifier, error, action === "reset" ? "RUNNING" : "STOPPED", false);
            const stillSelected = generation === manualGeneration && page === requestedPage && selectedSession && selectedSession.id === identifier;
            if (confirmed && stillSelected) {
                importGeneration += 1;
                sessionImports = [];
                workspaceGeneration += 1;
                workspaces = ({});
                workspaceErrors = ({});
            }
            if (confirmed && action === "reset") {
                if (!smoke)
                    api.allTerminals(session);
            }
            if (confirmed)
                notice = action === "reset" ? "Đã reset phiên thực hành." : "Đã dừng phiên thực hành.";
            refreshSessions();
            if (confirmed && stillSelected && action === "stop") {
                page = 0;
                selectLab(selectedLab);
            }
        });
    }
    function poll() {
        if (api.busy || api.inFlight)
            return;
        api.request(["info"], (info, error) => {
            const changed = updateConnection(info, error);
            if (!connected)
                return;
            if (changed)
                refreshCatalog(true);
            refreshSessions(true);
        }, "", true);
    }
    function refresh(queued) {
        if ((api.busy || api.inFlight) && !queued)
            return;
        api.request(["info"], (info, error) => {
            updateConnection(info, error);
            if (!connected)
                return;
            refreshCatalog(false);
            refreshSessions();
        });
    }
    function refreshCatalog(background) {
        api.request(["labs"], (result, error) => {
            if (error)
                return;
            if (JSON.stringify(labs) !== JSON.stringify(result))
                labs = result;
            const previous = selectedLab ? selectedLab.id : "";
            const current = labs.find(lab => lab.id === previous) || labs[0] || null;
            if (page === 0 && (!background || JSON.stringify(current) !== JSON.stringify(selectedLab)))
                selectLab(current);
            else
                selectedLab = current;
        }, "", !!background);
    }
    function refreshImports(identifier) {
        const generation = ++importGeneration;
        api.request(["imports", identifier], (result, error) => {
            if (!error && generation === importGeneration && selectedSession && selectedSession.id === identifier)
                sessionImports = result;
        }, "", true);
    }
    function refreshSessions(background) {
        api.request(["sessions"], (result, error) => {
            if (error)
                return;
            if (JSON.stringify(sessions) !== JSON.stringify(result))
                sessions = result;
            if (selectedSession) {
                let found = sessions.find(session => session.id === selectedSession.id);
                if (found) {
                    if (JSON.stringify(found) !== JSON.stringify(selectedSession))
                        selectedSession = found;
                } else {
                    if (page === 1) {
                        manualGeneration += 1;
                        manual = "Phiên không còn hoạt động.";
                    }
                    importGeneration += 1;
                    selectedSession = null;
                    sessionImports = [];
                }
            }
        }, "", !!background);
    }
    function refreshWorkspaces(nodeId) {
        const session = selectedSession;
        if (!session || session.state !== "RUNNING" || !api.capabilities || !api.capabilities.includes("workspace-files"))
            return;
        const generation = workspaceGeneration;
        const nodes = nodeId ? [nodeId] : (session.nodes || []).map(node => node[0]);
        nodes.forEach(node => api.request(["files", session.id, node], (result, error) => {
                if (generation !== workspaceGeneration || !selectedSession || selectedSession.id !== session.id)
                    return;
                const errors = Object.assign({}, workspaceErrors);
                errors[node] = error || "";
                workspaceErrors = errors;
                if (!error && result && result.source === "live") {
                    const current = Object.assign({}, workspaces);
                    current[node] = result;
                    workspaces = current;
                }
            }, "", true));
    }
    function resumeSession(session) {
        const target = session || selectedSession;
        if (!target || api.busy || api.starting)
            return;
        api.error = "";
        const generation = manualGeneration;
        const requestedPage = page;
        api.request(["resume", target.id, "--no-terminals"], (resumed, error) => {
            if (confirmedSession(resumed, target.id, error, "RUNNING", false)) {
                if (generation === manualGeneration && page === requestedPage)
                    selectSession(resumed);
                if (!smoke)
                    api.allTerminals(resumed);
            }
            refreshSessions();
        });
    }
    function saveSession(identifier) {
        if (!identifier || api.busy)
            return;
        api.request(["save", identifier], (session, error) => {
            if (confirmedSession(session, identifier, error, "RUNNING", true))
                notice = "Đã lưu tiến độ thực hành.";
            refreshSessions();
        });
    }
    function selectLab(lab) {
        const generation = ++manualGeneration;
        const key = lab ? "lab:" + lab.id : "";
        const sameDocument = manualKey === key;
        manualKey = key;
        selectedLab = lab;
        if (!lab || !lab.has_documentation)
            manual = "Bài chưa có tài liệu hướng dẫn.";
        else if (!sameDocument)
            manual = "";
        if (lab && lab.has_documentation)
            api.request(["docs", lab.id, "--json"], (result, error) => {
                if (!error && generation === manualGeneration && selectedLab && selectedLab.id === lab.id && page === 0)
                    manual = result.content;
            });
    }
    function selectSession(session) {
        const generation = ++manualGeneration;
        const key = session ? "session:" + session.id : "";
        const sameDocument = manualKey === key;
        manualKey = key;
        importGeneration += 1;
        sessionImports = [];
        selectedSession = session;
        workspaceGeneration += 1;
        workspaces = ({});
        workspaceErrors = ({});
        page = 1;
        if (!session || !session.has_documentation)
            manual = "Phiên chưa có tài liệu hướng dẫn.";
        else if (!sameDocument)
            manual = "";
        if (session && session.has_documentation)
            api.request(["docs", session.id, "--session", "--json"], (result, error) => {
                if (!error && generation === manualGeneration && selectedSession && selectedSession.id === session.id && page === 1)
                    manual = result.content;
            });
    }
    function startLab(lab, parameters) {
        let target = lab || selectedLab;
        if (!target || api.busy || api.starting)
            return;
        api.error = "";
        const generation = manualGeneration;
        const requestedPage = page;
        let command = ["start", target.id, "--no-terminals"];
        Object.keys(parameters || {}).sort().forEach(identifier => {
            command.push("--param", identifier + "=" + parameters[identifier]);
        });
        api.request(command, (session, error) => {
            if (session && session.id) {
                if (generation === manualGeneration && page === requestedPage)
                    selectSession(session);
                refreshSessions();
                if (!error && !smoke && session.state === "RUNNING")
                    api.allTerminals(session);
            }
        });
    }
    function suspendSession(identifier) {
        if (!identifier || api.busy)
            return;
        const generation = manualGeneration;
        const requestedPage = page;
        api.request(["suspend", identifier], (session, error) => {
            const confirmed = confirmedSession(session, identifier, error, "SUSPENDED", true);
            if (confirmed)
                notice = "Đã tạm dừng bài thực hành.";
            refreshSessions();
            if (confirmed && generation === manualGeneration && page === requestedPage && selectedSession && selectedSession.id === identifier) {
                importGeneration += 1;
                workspaceGeneration += 1;
                sessionImports = [];
                workspaces = ({});
                workspaceErrors = ({});
                page = 0;
                selectLab(selectedLab);
            }
        });
    }
    function updateConnection(info, error) {
        const available = !error && !!info && Array.isArray(info.capabilities);
        const capabilities = available ? info.capabilities : [];
        const changed = connected !== available || JSON.stringify(api.capabilities) !== JSON.stringify(capabilities);
        connected = available;
        if (JSON.stringify(api.capabilities) !== JSON.stringify(capabilities))
            api.capabilities = capabilities;
        return changed;
    }

    visible: false

    onNoticeChanged: if (notice.length > 0) {
        api.notify(notice, false);
        Qt.callLater(() => controller.notice = "");
    }
}
