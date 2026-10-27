import QtQuick
import "../models/EditorModel.js" as Model
import "../models/NodeDefaults.js" as Defaults

QtObject {
    required property var backend
    property var drafts: []
    property var draft: null
    property var policy: null
    property string definition: ""
    property var document: parse(definition)
    property bool definitionDirty: false
    property bool documentationDirty: false
    property bool dirty: definitionDirty || documentationDirty
    property string documentationText: ""
    property bool documentationReady: true
    property int documentGeneration: 0
    property var report: null
    property var runtimeReport: null
    property var publicationReview: null
    property var updateReview: null
    readonly property bool canPublish: !!draft && !!report && report.valid && !dirty
        && report.revision === draft.revision && report.digest === draft.digest
    readonly property bool canConfirmPublication: canPublish && !!publicationReview
        && publicationReview.id === draft.id && publicationReview.revision === draft.revision
        && publicationReview.digest === draft.digest
    readonly property bool isInstalledEdit: !!draft && !!draft.origin && !!document && draft.origin.lab_id === document.metadata.id
    readonly property bool canUpdateInstalled: isInstalledEdit && !!report && report.valid && !dirty
        && report.revision === draft.revision && report.digest === draft.digest
    property string localError: ""
    property int section: 0
    property int selectedNode: 0
    property int selectedNetwork: 0
    property bool supported: backend.capabilities.includes("authoring")
    signal backRequested()
    signal published()
    signal publicationReviewRequested()
    signal updateReviewRequested()
    signal discardRequested()

    function parse(text) {
        try {
            const value = JSON.parse(text);
            return value && value.metadata && Array.isArray(value.nodes) && Array.isArray(value.networks) ? value : null;
        } catch (error) { return null; }
    }
    function commit(value) {
        if (document && JSON.stringify(value) === JSON.stringify(document)) return;
        definition = JSON.stringify(value, null, 2);
        definitionDirty = true;
        report = null;
        runtimeReport = null;
        publicationReview = null;
        updateReview = null;
        localError = "";
    }
    function attempt(callback) {
        try { callback(); }
        catch (error) { localError = String(error); }
    }
    function refresh() {
        if (!supported) return;
        backend.request(["draft", "info"], (result, error) => { if (!error) policy = result; });
        backend.request(["draft", "list"], (result, error) => { if (!error) drafts = result; });
    }
    function openDraft(identifier) {
        backend.request(["draft", "show", identifier], (result, error) => {
            if (error) return;
            const same = draft && draft.id === result.id;
            adopt(result, false);
            if (same) loadDocumentation();
            localError = document ? "" : "Nháp này không phải JSON dùng cho biểu mẫu. Dùng CLI để xem/sửa định nghĩa; dữ liệu gốc vẫn được giữ.";
        });
    }
    function loadDocumentation() {
        const generation = ++documentGeneration;
        documentationText = "";
        documentationDirty = false;
        documentationReady = !document || !document.documentation;
        if (documentationReady) return;
        backend.request(["draft", "asset", draft.id, document.documentation, "--revision", String(draft.revision), "--text"], (result, error) => {
            if (generation !== documentGeneration) return;
            if (!error) { documentationText = result.content; documentationReady = true; }
        });
    }
    function adopt(result, preserve) {
        const changed = !draft || draft.id !== result.id;
        draft = result;
        if (!preserve) { definition = result.definition; definitionDirty = false; }
        report = null;
        publicationReview = null;
        if (changed) { selectedNode = 0; selectedNetwork = 0; loadDocumentation(); }
    }
    function change(group, index, field, value) {
        attempt(() => commit(Model.change(document, group, index, field, value)));
    }
    function changePath(path, value) {
        attempt(() => commit(Model.changePath(document, path, value)));
    }
    function addEntry(section, entry, limit) {
        attempt(() => commit(Model.addEntry(document, section, entry, limit)));
    }
    function updateEntry(section, index, field, value) {
        attempt(() => commit(Model.updateEntry(document, section, index, field, value)));
    }
    function removeEntry(section, index) {
        attempt(() => commit(Model.removeEntry(document, section, index)));
    }
    function addQuizGroup(entry, limit) {
        attempt(() => commit(Model.addQuizGroup(document, entry, limit)));
    }
    function updateQuizGroup(index, field, value) {
        attempt(() => commit(Model.updateQuizGroup(document, index, field, value)));
    }
    function removeQuizGroup(index) {
        attempt(() => commit(Model.removeQuizGroup(document, index)));
    }
    function addQuizItem(groupIndex, entry, limit) {
        attempt(() => commit(Model.addQuizItem(document, groupIndex, entry, limit)));
    }
    function updateQuizItem(groupIndex, itemIndex, field, value) {
        attempt(() => commit(Model.updateQuizItem(document, groupIndex, itemIndex, field, value)));
    }
    function removeQuizItem(groupIndex, itemIndex) {
        attempt(() => commit(Model.removeQuizItem(document, groupIndex, itemIndex)));
    }
    function addNestedEntry(root, section, entry, limit) {
        attempt(() => commit(Model.addNestedEntry(document, root, section, entry, limit)));
    }
    function updateNestedEntry(root, section, index, field, value) {
        attempt(() => commit(Model.updateNestedEntry(document, root, section, index, field, value)));
    }
    function removeNestedEntry(root, section, index) {
        attempt(() => commit(Model.removeNestedEntry(document, root, section, index)));
    }
    function modify(group, entry, index) {
        attempt(() => {
            commit(Model.modify(document, group, entry, index));
            selectedNode = Math.max(0, Math.min(selectedNode, document.nodes.length - 1));
            selectedNetwork = Math.max(0, Math.min(selectedNetwork, document.networks.length - 1));
        });
    }
    function attach(index, network, enabled, address) {
        attempt(() => commit(Model.attach(document, index, network, enabled, address)));
    }
    function autoOpen(nodeId, enabled) { commit(Model.autoOpen(document, nodeId, enabled)); }
    function newNode(identifier) {
        return Defaults.newNode(document, policy, identifier);
    }
    function addMachine() {
        attempt(() => {
            if (!Defaults.canAddMachine(document, policy)) throw new Error("Đã hết số máy hoặc terminal được phép.");
            const copy = Model.clone(document);
            if (!copy.networks.length) copy.networks.push({id: "lan"});
            const node = Defaults.newNode(copy, policy, nextNodeId());
            commit(Model.modify(copy, "nodes", node));
            selectedNode = document.nodes.length - 1;
        });
    }
    function selectImage(index, image) {
        attempt(() => commit(Defaults.changeImage(document, index, image, policy)));
    }
    function nextNodeId() {
        if (!document.nodes.some(node => node.id === "client")) return "client";
        if (!document.nodes.some(node => node.id === "server")) return "server";
        return Model.nextId(document.nodes, "node");
    }
    function userField(index, field, value) {
        if (!document || !document.nodes[index] || !document.nodes[index].user) return;
        const identity = Model.clone(document.nodes[index].user);
        identity[field] = value;
        if (field === "name") identity.home = "/home/" + value;
        change("nodes", index, "user", identity);
    }
    function create(identifier, title, callback) {
        if (dirty) { localError = "Lưu bản nháp trước khi tạo bài khác."; return; }
        identifier = identifier.trim();
        title = title.trim();
        backend.request(["draft", "create", identifier, "--title", title], (result, error) => {
            if (!error) { adopt(result, false); section = 0; localError = ""; if (callback) callback(); else refresh(); }
        });
    }
    function cloneLab(sourceLabId, targetLabId, title, callback) {
        if (dirty) { localError = "Lưu bản nháp trước khi nhân bản bài khác."; return; }
        backend.request(["draft", "clone", sourceLabId, "--as", targetLabId, "--title", title], (result, error) => {
            if (!error) { adopt(result, false); section = 0; localError = ""; if (callback) callback(); else refresh(); }
        });
    }
    function editLab(labId, callback) {
        if (dirty) { localError = "Lưu bản nháp trước khi sửa bài khác."; return; }
        backend.request(["draft", "edit", labId], (result, error) => {
            if (!error) { adopt(result, false); section = 0; localError = ""; if (callback) callback(); else refresh(); }
        });
    }
    function save(callback) {
        if (!draft || !document) return;
        const persist = () => backend.request(["draft", "save", draft.id, "-", "--revision", String(draft.revision)], (result, error) => {
            if (!error) {
                adopt(result, false);
                backend.request(["draft", "list"], (entries, problem) => { if (!problem) drafts = entries; });
                backend.notify("Đã lưu bản nháp.", false);
                if (callback) callback();
            }
        }, definition);
        if (!documentationDirty) { persist(); return; }
        const path = document.documentation || "assets/docs/guide.md";
        backend.request(["draft", "put-file", draft.id, "-", path, "--revision", String(draft.revision)], (result, error) => {
            if (!error) {
                adopt(result, true);
                const copy = Model.clone(document);
                copy.documentation = path;
                commit(copy);
                documentationDirty = false;
                persist();
            }
        }, documentationText);
    }
    function validate(callback) {
        localError = "";
        report = null;
        publicationReview = null;
        updateReview = null;
        const check = () => backend.request(["draft", "check", draft.id, "--revision", String(draft.revision)], (result, error) => {
            if (result) report = result;
            if (!error && report && report.valid && callback) callback();
        });
        if (!draft) return;
        if (dirty) save(check); else check();
    }
    function checkRuntime(callback) {
        if (!draft || !document || backend.busy) return;
        localError = "";
        const runCheck = () => {
            backend.request(["draft", "runtime-check", draft.id, "--revision", String(draft.revision)], (result, error) => {
                if (result) {
                    report = result;
                    runtimeReport = result;
                }
                if (!error && result && result.ready) {
                    backend.notify("Kiểm tra runtime thành công: container và tài nguyên sẵn sàng.", false);
                }
                if (callback) callback();
            });
        };
        if (dirty) save(runCheck); else runCheck();
    }
    function reviewUpdate() {
        if (!draft || !document || backend.busy) return;
        validate(() => {
            updateReview = {
                id: draft.id, revision: report.revision, digest: report.digest,
                labId: draft.origin.lab_id, name: document.metadata.name,
                nodes: document.nodes.length, networks: document.networks.length,
                assets: draft.assets.length
            };
            updateReviewRequested();
        });
    }
    function prepareLibrarySave() {
        if (!draft || !document || backend.busy) return;
        validate(() => {
            const selected = {id: draft.id, revision: draft.revision, digest: draft.digest};
            backend.request(["draft", "runtime-check", selected.id, "--revision", String(selected.revision)], (result, error) => {
                if (!draft || draft.id !== selected.id || draft.revision !== selected.revision || dirty) return;
                if (result) { report = result; runtimeReport = result; }
                if (error || !result || !result.valid || !result.ready || result.digest !== selected.digest) {
                    section = 5;
                    return;
                }
                const review = {id: selected.id, revision: selected.revision, digest: selected.digest,
                    labId: document.metadata.id, name: document.metadata.name,
                    nodes: document.nodes.length, networks: document.networks.length, assets: draft.assets.length,
                    runtimeVerified: result.runtime_verified === true};
                if (isInstalledEdit) { updateReview = review; updateReviewRequested(); }
                else { publicationReview = review; publicationReviewRequested(); }
            });
        });
    }
    function confirmUpdate() {
        const reviewed = updateReview;
        if (!reviewed || !draft || reviewed.id !== draft.id || reviewed.revision !== draft.revision
                || reviewed.digest !== draft.digest || dirty) {
            localError = "Nháp đã thay đổi sau khi xem lại. Nhấn Cập nhật để kiểm tra lại.";
            return;
        }
        updateInstalled();
    }
    function updateInstalled(callback) {
        if (!report || !report.valid || dirty || report.revision !== draft.revision || report.digest !== draft.digest) {
            localError = "Cần kiểm tra đúng revision/digest trước khi cập nhật bài đã cài đặt.";
            return;
        }
        backend.request(["draft", "update", draft.origin.lab_id, draft.id,
                         "--revision", String(report.revision),
                         "--digest", report.digest,
                         "--catalog-digest", draft.origin.digest,
                         "--yes"], (result, error) => {
            if (!error && result && result.updated) {
                report = null;
                updateReview = null;
                published();
                if (callback) callback();
            } else if (result && result.valid === false) {
                report = result;
            }
        });
    }
    function reviewPublication() {
        if (!draft || !document || backend.busy) return;
        validate(() => {
            publicationReview = {
                id: draft.id, revision: report.revision, digest: report.digest,
                labId: document.metadata.id, name: document.metadata.name,
                nodes: document.nodes.length, networks: document.networks.length,
                assets: draft.assets.length
            };
            publicationReviewRequested();
        });
    }
    function confirmPublication() {
        const reviewed = publicationReview;
        if (!reviewed || !draft || reviewed.id !== draft.id || reviewed.revision !== draft.revision
                || reviewed.digest !== draft.digest || dirty) {
            localError = "Nháp đã thay đổi sau khi xem lại. Nhấn Lưu vào thư viện để kiểm tra lại.";
            return;
        }
        publish();
    }
    function publish(callback) {
        if (!report || !report.valid || dirty || report.revision !== draft.revision || report.digest !== draft.digest) {
            localError = "Cần kiểm tra đúng revision trước khi lưu vào thư viện.";
            return;
        }
        backend.request(["draft", "publish", draft.id, "--revision", String(report.revision), "--digest", report.digest], (result, error) => {
            if (!error && result.published) { report = null; publicationReview = null; published(); if (callback) callback(); }
            else if (result && result.valid === false) report = result;
        });
    }
    function upload(source, logical, tree, callback) {
        const transfer = () => {
            const args = tree ? ["draft", "put-tree", draft.id, source, "--prefix", logical]
                              : ["draft", "put-file", draft.id, source, logical];
            backend.request(args.concat(["--revision", String(draft.revision)]), (result, error) => {
                if (!error) { adopt(result, true); backend.notify("Đã thêm tài nguyên vào bản nháp.", false); if (callback) callback(); }
            });
        };
        if (dirty) save(transfer); else transfer();
    }
    function addMapping(nodeId, source, target) {
        attempt(() => commit(Model.addMapping(document, nodeId, source, target)));
    }
    function uploadHome(source, nodeId, name, tree, subfolder) {
        attempt(() => {
            if (!policy || !policy.home_directory_target)
                throw new Error("Cần cập nhật daemon để hỗ trợ thêm nội dung folder trực tiếp vào home.");
            const plan = Model.homeUpload(document, nodeId, name, tree, subfolder, draft.assets);
            upload(source, plan.logical, tree, () => {
                attempt(() => {
                    const current = Model.homeUpload(document, nodeId, name, tree, subfolder);
                    commit(current.document);
                    save();
                });
            });
        });
    }
    function removeMapping(nodeIndex, index) {
        const copy = Model.clone(document);
        copy.nodes[nodeIndex].files.splice(index, 1);
        commit(copy);
    }
    function removeHomeFile(nodeId, path) {
        attempt(() => {
            const plan = Model.removeSeedFile(document, nodeId, path, draft.assets);
            commit(plan.document);
            removeAsset(plan.source);
        });
    }
    function removeAsset(path) {
        attempt(() => {
            Model.removeAsset(document, path, draft.assets);
            const remove = () => backend.request(["draft", "remove-asset", draft.id, path, "--revision", String(draft.revision)], (result, error) => {
                if (!error) adopt(result, true);
            });
            if (dirty) save(remove); else remove();
        });
    }
    function deleteDraft() {
        backend.request(["draft", "delete", draft.id, "--revision", String(draft.revision)], (result, error) => {
            if (!error) {
                documentGeneration++;
                draft = null; definition = ""; definitionDirty = false; documentationDirty = false;
                report = null; refresh();
            }
        });
    }
    function showMachines() { section = 1; refresh(); }
    function requestBack() {
        if (backend.busy) return;
        if (dirty) discardRequested();
        else backRequested();
    }
    function discardAndBack() {
        if (backend.busy) return;
        definition = draft ? draft.definition : "";
        definitionDirty = false;
        documentationDirty = false;
        report = null;
        publicationReview = null;
        localError = "";
        loadDocumentation();
        backRequested();
    }
}
