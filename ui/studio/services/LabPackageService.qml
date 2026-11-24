import QtQuick

QtObject {
    id: service

    required property var api
    readonly property bool canImport: api.capabilities.includes("lab-package-import") && !api.busy && !importing && !editor.dirty
    required property var editor
    property bool importing: false

    signal draftOpened
    signal libraryReloadRequested
    signal compatibilityBlocked(var report)

    function exportPackage(target, path) {
        if (!target || !path || api.busy || !api.capabilities.includes("lab-package-export"))
            return;
        const args = target.kind === "draft" ? ["export-draft", target.id, path, "--revision", String(target.revision)] : ["export-lab", target.id, path];
        api.request(args, (result, error) => {
            if (!error)
                api.notify("Đã xuất gói bài lab. Image cần được chuẩn bị trên VM đích.", false);
        });
    }
    function importPackage(path) {
        if (!canImport || !path)
            return;
        const nativePackage = path.toLowerCase().endsWith(".cyberlab");
        if (!nativePackage && !api.capabilities.includes("labtainer-import")) {
            api.notify("Daemon hiện tại chưa hỗ trợ nhập Labtainer.", false);
            return;
        }
        const draftId = editor.draft ? editor.draft.id : "";
        const definition = editor.definition;
        importing = true;
        const cmd = nativePackage ? "import-lab" : "import-labtainer";
        const performImport = () => api.request([cmd, path], (result, error) => {
            service.importing = false;
            if (!error && result && result.installed === true && result.lab_id && result.edit_protected === true) {
                service.libraryReloadRequested();
                api.notify("Đã nhập bài có khóa chỉnh sửa vào thư viện. Nhập mật khẩu khi cần chỉnh sửa.", false);
                return;
            }
            if (error || !result || !result.id)
                return;
            if (!editor.dirty && editor.definition === definition && (editor.draft ? editor.draft.id : "") === draftId) {
                editor.adopt(result, false);
                editor.section = 0;
                service.draftOpened();
            }
            editor.refresh();
            api.notify(result.import_report ? "Đã nhập bản nháp Labtainer. Chọn image, lệnh khởi động và kiểm tra tài khoản từng máy; xem labtainer-import.json trong tài nguyên." : "Đã nhập gói vào bản nháp. Kiểm tra trước khi xuất bản.", false);
        });
        if (!nativePackage && api.capabilities.includes("labtainer-inspect")) {
            api.request(["inspect-labtainer", path], (report, error) => {
                if (error || !report) {
                    service.importing = false;
                    return;
                }
                if (report.can_import !== true) {
                    service.importing = false;
                    service.compatibilityBlocked(report);
                    return;
                }
                if (editor.dirty || editor.definition !== definition || (editor.draft ? editor.draft.id : "") !== draftId) {
                    service.importing = false;
                    api.notify("Nội dung soạn thảo đã thay đổi. Lưu bản nháp rồi nhập lại gói Labtainer.", false);
                    return;
                }
                performImport();
            });
        } else {
            performImport();
        }
    }
}
