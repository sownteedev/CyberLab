import QtQuick

Item {
    id: service
    required property var api
    property bool submitting: false
    readonly property bool supported: api.capabilities.includes("submit-and-finish")
    signal settled()

    function submit(session, path) {
        if (!supported || submitting || api.busy || !session || session.state !== "RUNNING" || !path) return;
        const identifier = session.id;
        submitting = true;
        api.request(["submit", identifier, path], (result, problem) => {
            submitting = false;
            if (!problem) {
                if (result && result.id === identifier && result.state === "STOPPED"
                        && result.submission && result.submission.destination) {
                    api.notify("Đã lưu bài nộp và kết thúc phiên: " + result.submission.destination, false);
                } else {
                    api.notify("Chưa xác nhận được kết thúc phiên. Kiểm tra bài nộp và trạng thái phiên trước khi thử lại.", true);
                }
            }
            service.settled();
        });
    }
}
