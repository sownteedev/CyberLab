import QtQuick

QtObject {
    id: service
    required property var backend
    property bool supported: false
    property bool active: true
    property string query: ""
    property string contextKey: ""
    property var results: []
    property var sourceErrors: []
    property string state: "idle"
    property int total: 0
    property int generation: 0
    property bool inFlight: false
    property bool alive: true
    readonly property bool loading: state === "loading" || state === "waiting"
    property Timer debounce: Timer { interval: 350; onTriggered: service.fetch(false) }
    property Timer poll: Timer { interval: 1200; running: service.active && service.state === "loading"; repeat: true; onTriggered: service.fetch(false) }

    function reset() {
        ++generation;
        inFlight = false;
        results = [];
        sourceErrors = [];
        total = 0;
        state = "idle";
        debounce.stop();
        if (active && supported) {
            state = "waiting";
            debounce.restart();
        }
    }
    function fetch(refresh) {
        if (!alive || !active || !supported || inFlight) return;
        const token = generation;
        const text = query.trim();
        inFlight = true;
        const argv = ["draft", "software-search", text];
        if (refresh) argv.push("--refresh");
        backend.request(argv, (result, error) => {
            if (!service || !service.alive || service.generation !== token) return;
            service.inFlight = false;
            if (error || !result) { service.state = "error"; return; }
            service.results = result.packages || [];
            service.sourceErrors = result.source_errors || [];
            service.total = result.total || 0;
            service.state = result.state || "error";
        }, "", true);
    }
    onQueryChanged: reset()
    onContextKeyChanged: reset()
    onSupportedChanged: reset()
    onActiveChanged: reset()
    Component.onCompleted: reset()
    Component.onDestruction: alive = false
}
