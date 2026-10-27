import QtQuick

QtObject {
    id: service
    required property var api
    required property var editor
    property bool importing: false
    readonly property bool canImport: api.capabilities.includes("lab-package-import")
        && !api.busy && !importing && !editor.dirty
    signal draftOpened()

    function importPackage(path) {
        if (!canImport || !path) return;
        const nativePackage = path.toLowerCase().endsWith(".cyberlab");
        if (!nativePackage && !api.capabilities.includes("labtainer-import")) {
            api.notify("Daemon hiện tại chưa hỗ trợ nhập Labtainer.", false);
            return;
        }
        const draftId = editor.draft ? editor.draft.id : "";
        const definition = editor.definition;
        importing = true;
        const cmd = nativePackage ? "import-lab" : "import-labtainer";
        api.request([cmd, path], (result, error) => {
            service.importing = false;
            if (error || !result || !result.id) return;
            if (!editor.dirty && editor.definition === definition && (editor.draft ? editor.draft.id : "") === draftId) {
                editor.adopt(result, false);
                editor.section = 0;
                service.draftOpened();
            }
            editor.refresh();
            api.notify(result.import_report
                ? "Đã nhập bản nháp Labtainer. Chọn image, lệnh khởi động và kiểm tra tài khoản từng máy; xem labtainer-import.json trong tài nguyên."
                : "Đã nhập gói vào bản nháp. Kiểm tra trước khi xuất bản.", false);
        });
    }
    function exportPackage(target, path) {
        if (!target || !path || api.busy || !api.capabilities.includes("lab-package-export")) return;
        const args = target.kind === "draft"
            ? ["export-draft", target.id, path, "--revision", String(target.revision)]
            : ["export-lab", target.id, path];
        api.request(args, (result, error) => {
            if (!error) api.notify("Đã xuất gói bài lab. Image cần được chuẩn bị trên VM đích.", false);
        });
    }
}
