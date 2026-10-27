import QtQuick

QtObject {
    id: service
    required property var api
    property var review: null
    property string error: ""
    property bool loading: false
    property int generation: 0

    function clear() {
        generation++;
        review = null;
        error = "";
        loading = false;
    }
    function load(paths) {
        if (loading || api.busy || !api.capabilities.includes("submission-review")) return;
        if (!Array.isArray(paths) || paths.length < 1 || paths.length > 32
                || paths.some(path => typeof path !== "string" || !path.startsWith("/"))) {
            error = "Chọn từ 1 đến 32 file ZIP trong VM.";
            return;
        }
        const current = ++generation;
        loading = true;
        error = "";
        review = null;
        api.request(["review-submissions"].concat(paths), (result, problem) => {
            if (current !== service.generation) return;
            service.loading = false;
            service.error = problem || "";
            if (!problem) service.review = result;
        });
    }
}
