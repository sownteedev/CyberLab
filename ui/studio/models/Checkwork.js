.pragma library

function statusText(status) {
    return ({PASS: "Đạt", FAIL: "Chưa đạt", ERROR: "Lỗi kiểm tra", NO_CRITERIA: "Chưa có tiêu chí",
             CORRECT: "Đúng", INCORRECT: "Chưa đúng", UNANSWERED: "Chưa trả lời", UNASSESSED: "Không chấm",
             COLLECTED: "Đã thu thập", MISSING: "Thiếu file", OPTIONAL_MISSING: "Không bắt buộc"})[status] || status;
}

function statusIcon(status) {
    return status === "PASS" || status === "COLLECTED" ? "check_circle"
        : status === "ERROR" ? "error" : "description";
}

function historyLabel(report) {
    const date = new Date(report.created_at);
    const time = isNaN(date.getTime()) ? report.created_at : date.toLocaleString(Qt.locale("vi_VN"), "dd/MM hh:mm:ss");
    return time + " · " + statusText(report.status) + " · " + (report.lab_name || report.lab_id);
}
