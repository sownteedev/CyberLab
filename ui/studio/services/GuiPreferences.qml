import QtQuick

QtObject {
    id: preferences

    required property var backend
    property bool busy: false
    property string error: ""
    property var state: ({ preferred: "auto", host: {}, warning: "" })

    function refresh() { request(); }
    function select(identifier) { request(identifier); }
    function request(identifier) {
        if (busy)
            return;
        busy = true;
        backend.request(identifier === undefined ? ["gui-preferences"] : ["gui-preferences", "--set", identifier], (result, problem) => {
            busy = false;
            error = problem || "";
            if (!problem && result)
                state = result;
        });
    }
}
