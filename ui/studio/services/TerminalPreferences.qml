import QtQuick

QtObject {
    id: preferences

    required property var backend
    property bool busy: false
    property string error: ""
    property bool loaded: false
    property var state: ({
            preferred: "auto",
            selected: null,
            source: "unavailable",
            options: [],
            warnings: []
        })

    function refresh() {
        request();
    }
    function request(identifier) {
        if (busy)
            return;
        busy = true;
        error = "";
        const command = identifier === undefined ? ["terminal-apps"] : ["terminal-apps", "--set", identifier];
        backend.request(command, (result, problem) => {
            busy = false;
            if (problem) {
                error = problem;
                return;
            }
            if (!result || !Array.isArray(result.options) || !Array.isArray(result.warnings)) {
                error = "CLI trả về danh sách terminal không hợp lệ.";
                return;
            }
            state = result;
            loaded = true;
        });
    }
    function select(identifier) {
        request(identifier);
    }
}
