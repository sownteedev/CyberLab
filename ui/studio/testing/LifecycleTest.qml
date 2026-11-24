import QtQuick
import QtTest
import ".." as Studio

Item {
    id: checks

    property string screenshotFolder: ""

    function session(identifier, state, saved) {
        return {id: identifier, state: state, saved: saved, lab_id: "fixture", nodes: []};
    }

    QtObject {
        id: api

        property bool busy: false
        property bool inFlight: false
        property string error: ""
        property var capabilities: ["session-persistence", "discard-checkpoint"]
        property var pending: null
        property var notices: []
        property int launches: 0
        property var requests: []

        function request(arguments, callback) {
            requests = requests.concat([arguments]);
            if (["start", "stop", "reset", "save", "suspend", "resume"].includes(arguments[0]))
                pending = callback;
        }
        function notify(message, failure) { notices = notices.concat([{message: message, failure: failure}]); }
        function allTerminals(session) { launches++; }
    }

    Studio.StudioState { id: controller; api: api }

    TestCase {
        name: "LifecycleResponses"
        when: true

        function init() {
            wait(0);
            api.busy = false;
            api.error = "";
            api.pending = null;
            api.notices = [];
            api.launches = 0;
            api.requests = [];
            api.capabilities = ["session-persistence", "discard-checkpoint", "workspace-files"];
            controller.notice = "";
            controller.page = 1;
            controller.selectedSession = checks.session("fixture-session", "RUNNING", true);
            controller.selectedLab = {id: "fixture", has_documentation: false};
            controller.sessionImports = ["kept"];
            controller.workspaces = {client: {files: ["kept.txt"]}};
        }
        function actions() {
            return [{tag: "stop", action: "stop", state: "STOPPED"},
                {tag: "reset", action: "reset", state: "RUNNING"},
                {tag: "save", action: "save", state: "RUNNING"},
                {tag: "suspend", action: "suspend", state: "SUSPENDED"},
                {tag: "resume", action: "resume", state: "RUNNING"}];
        }
        function test_start_waits_for_all_nodes_data() {
            return [{tag: "running", state: "RUNNING", error: "", launches: 1},
                {tag: "preparing", state: "PREPARING", error: "", launches: 0},
                {tag: "failed", state: "FAILED", error: "Installation failed", launches: 0},
                {tag: "stopped", state: "STOPPED", error: "", launches: 0}];
        }
        function test_start_waits_for_all_nodes(data) {
            controller.startLab(controller.selectedLab, {});
            compare(api.launches, 0);
            verify(typeof api.pending === "function");
            api.pending(checks.session("new-session", data.state, false), data.error);
            compare(api.launches, data.launches);
        }
        function test_late_start_does_not_leave_editor() {
            controller.startLab(controller.selectedLab, {});
            controller.page = 2;
            api.pending(checks.session("new-session", "RUNNING", false), "");
            compare(controller.page, 2);
            compare(api.launches, 1);
        }
        function begin(action) {
            if (action === "resume") controller.resumeSession(checks.session("fixture-session", "STOPPED", true));
            else if (action === "save") controller.saveSession("fixture-session");
            else if (action === "suspend") controller.suspendSession("fixture-session");
            else controller.lifecycle(action, "fixture-session");
            verify(typeof api.pending === "function");
        }
        function test_confirmed_response_data() { return actions(); }
        function test_confirmed_response(data) {
            begin(data.action);
            api.pending(checks.session("fixture-session", data.state, true), "");
            compare(controller.selectedSession.state, data.state);
            compare(api.error, "");
            if (data.action !== "resume") compare(api.notices.length, 1);
            compare(api.launches, ["reset", "resume"].includes(data.action) ? 1 : 0);
            verify(!api.requests.some(request => ["files", "imports"].includes(request[0])));
        }
        function test_select_session_does_not_fetch_hidden_files() {
            const session = checks.session("other-session", "RUNNING", false);
            session.nodes = [["client", ["lan"]]];
            session.has_documentation = true;
            controller.selectSession(session);
            verify(api.requests.some(request => request[0] === "docs"));
            verify(!api.requests.some(request => ["files", "imports"].includes(request[0])));
        }
        function test_unconfirmed_response_data() {
            const rows = [];
            for (const action of actions()) {
                for (const kind of ["missing", "wrong-id", "wrong-state", "transport-error"])
                    rows.push({tag: action.action + "-" + kind, action: action.action, state: action.state, kind: kind});
            }
            return rows;
        }
        function test_unconfirmed_response(data) {
            begin(data.action);
            let response = checks.session("fixture-session", data.state, true);
            if (data.kind === "missing") response = null;
            if (data.kind === "wrong-id") response.id = "other-session";
            if (data.kind === "wrong-state") response.state = "FAILED";
            const problem = data.kind === "transport-error" ? "Request failed" : "";
            api.pending(response, problem);
            compare(api.notices.length, 0);
            compare(api.launches, 0);
            compare(controller.page, 1);
            compare(controller.selectedSession.id, "fixture-session");
            compare(controller.workspaces.client.files[0], "kept.txt");
            if (!problem) verify(api.error.length > 0);
        }
        function test_save_and_suspend_require_checkpoint_data() { return [{tag: "save", action: "save", state: "RUNNING"}, {tag: "suspend", action: "suspend", state: "SUSPENDED"}]; }
        function test_save_and_suspend_require_checkpoint(data) {
            begin(data.action);
            api.pending(checks.session("fixture-session", data.state, false), "");
            compare(api.notices.length, 0);
            verify(api.error.length > 0);
            compare(controller.page, 1);
        }
        function test_delayed_result_does_not_leave_another_session_data() { return actions(); }
        function test_delayed_result_does_not_leave_another_session(data) {
            begin(data.action);
            controller.selectSession(checks.session("other-session", "RUNNING", false));
            controller.workspaces = {client: {files: ["other.txt"]}};
            api.pending(checks.session("fixture-session", data.state, true), "");
            compare(controller.selectedSession.id, "other-session");
            compare(controller.page, 1);
            compare(controller.workspaces.client.files[0], "other.txt");
        }
        function test_delayed_result_does_not_leave_editor_data() { return actions(); }
        function test_delayed_result_does_not_leave_editor(data) {
            begin(data.action);
            controller.page = 2;
            api.pending(checks.session("fixture-session", data.state, true), "");
            compare(controller.page, 2);
        }
    }
}
