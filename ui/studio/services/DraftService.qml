import QtQuick
import ".." as Studio
import "../models/EditorModel.js" as Model
import "../models/NodeDefaults.js" as Defaults
import "../models/Messages.js" as Messages
import "../models/AccountModel.js" as Accounts

QtObject {
    id: service
    required property var backend
    readonly property bool canConfirmPublication: canPublish && !!publicationReview && publicationReview.id === draft.id && publicationReview.revision === draft.revision && publicationReview.digest === draft.digest
    readonly property bool canPublish: !!draft && !!report && report.valid && !dirty && report.revision === draft.revision && report.digest === draft.digest
    readonly property bool canUpdateInstalled: isInstalledEdit && !!report && report.valid && !dirty && report.revision === draft.revision && report.digest === draft.digest
    property string definition: ""
    property bool definitionDirty: false
    property bool dirty: definitionDirty || documentationDirty || files.dirty
    readonly property QtObject files: Studio.DraftFileService { editor: service }
    readonly property QtObject startup: Studio.DraftStartupService { editor: service }
    property var document: parse(definition)
    property int documentGeneration: 0
    property bool documentationDirty: false
    property bool documentationReady: true
    property string documentationText: ""
    property var draft: null
    property string editingDraftId: ""
    onDraftChanged: {
        const identifier = draft ? draft.id : "";
        if (editingDraftId !== identifier && backend.clearEditing)
            backend.clearEditing(null, identifier ? "draft:" + identifier : "");
        editingDraftId = identifier;
    }
    property var drafts: []
    property var editChoice: null
    property var editCallback: null
    readonly property bool isInstalledEdit: !!draft && !!draft.origin && !!document && draft.origin.lab_id === document.metadata.id
    property string localError: ""
    property var policy: null
    property var publicationReview: null
    property var report: null
    property var runtimeReport: null
    property int section: 0
    property int selectedNetwork: 0
    property int selectedNode: 0
    property bool accountPasswordPending: false
    property int accountContextGeneration: 0
    readonly property string accountContextKey: (draft ? draft.id : "") + ":" + selectedNode + ":" + (document && document.nodes[selectedNode] ? document.nodes[selectedNode].id : "")
    onAccountContextKeyChanged: accountContextGeneration++
    property bool supported: backend.capabilities.includes("authoring")
    property var updateReview: null

    onLocalErrorChanged: if (localError) Studio.StudioFeedback.report(localError)
    onReportChanged: if (report && report.valid === false) reportIssues(report)
    onRuntimeReportChanged: if (runtimeReport && !runtimeReport.ready) reportIssues(runtimeReport)

    function reportIssues(result) {
        const issues = result.issues || [];
        if (issues.length) issues.forEach(entry => Studio.StudioFeedback.report(Messages.issue(entry)));
        else if (result.error) Studio.StudioFeedback.report(result.error);
    }

    function showLocalError(message) {
        const value = String(message || "");
        if (value && localError === value) Studio.StudioFeedback.report(value);
        else localError = value;
    }

    signal backRequested
    signal discardRequested
    signal editChoiceRequested
    signal publicationReviewRequested
    signal published
    signal updateReviewRequested

    function addEntry(section, entry, limit) {
        attempt(() => commit(Model.addEntry(document, section, entry, limit)));
    }
    function addMachine() {
        attempt(() => {
            if (!Defaults.canAddMachine(document, policy))
                throw new Error("Đã hết số máy hoặc terminal được phép.");
            const copy = Model.clone(document);
            if (!copy.networks.length) {
                const network = {id: "lan"};
                if (policy && policy.network_internet) network.internet = true;
                copy.networks.push(network);
            }
            const node = Defaults.newNode(copy, policy, nextNodeId(), Studio.LabPreferences.username);
            commit(Model.modify(copy, "nodes", node));
            selectedNode = document.nodes.length - 1;
        });
    }
    function addMapping(nodeId, source, target) {
        attempt(() => commit(Model.addMapping(document, nodeId, source, target)));
    }
    function addNestedEntry(root, section, entry, limit) {
        attempt(() => commit(Model.addNestedEntry(document, root, section, entry, limit)));
    }
    function addQuizGroup(entry, limit) {
        attempt(() => commit(Model.addQuizGroup(document, entry, limit)));
    }
    function addQuizItem(groupIndex, entry, limit) {
        attempt(() => commit(Model.addQuizItem(document, groupIndex, entry, limit)));
    }
    function adopt(result, preserve, keepStartup) {
        const changed = !draft || draft.id !== result.id;
        draft = result;
        if (!preserve) {
            definition = result.definition;
            definitionDirty = false;
            if (!keepStartup) { startup.reset(); files.reset(); }
        }
        report = null;
        publicationReview = null;
        if (changed) {
            selectedNode = 0;
            selectedNetwork = 0;
            loadDocumentation();
        }
    }
    function attach(index, network, enabled, address) {
        attempt(() => commit(Model.attach(document, index, network, enabled, address)));
    }
    function attempt(callback) {
        try {
            callback();
        } catch (error) {
            showLocalError(String(error));
        }
    }
    function autoOpen(nodeId, enabled) {
        commit(Model.autoOpen(document, nodeId, enabled));
    }
    function change(group, index, field, value) {
        attempt(() => commit(Model.change(document, group, index, field, value)));
    }
    function changePath(path, value) {
        attempt(() => commit(Model.changePath(document, path, value)));
    }
    function checkRuntime(callback) {
        if (!draft || !document || backend.busy)
            return;
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
                if (callback)
                    callback();
            });
        };
        if (dirty)
            save(runCheck);
        else
            runCheck();
    }
    function cloneLab(sourceLabId, targetLabId, title, callback) {
        if (dirty) {
            showLocalError("Lưu bản nháp trước khi nhân bản bài khác.");
            return;
        }
        backend.request(["draft", "clone", sourceLabId, "--as", targetLabId, "--title", title], (result, error) => {
            if (!error) {
                adopt(result, false);
                section = 0;
                localError = "";
                if (callback)
                    callback();
                else
                    refresh();
            }
        });
    }
    function commit(value) {
        if (document && JSON.stringify(value) === JSON.stringify(document))
            return;
        definition = JSON.stringify(value, null, 2);
        definitionDirty = true;
        report = null;
        runtimeReport = null;
        publicationReview = null;
        updateReview = null;
        localError = "";
    }
    function confirmPublication() {
        const reviewed = publicationReview;
        if (!reviewed || !draft || reviewed.id !== draft.id || reviewed.revision !== draft.revision || reviewed.digest !== draft.digest || dirty) {
            showLocalError("Nháp đã thay đổi sau khi xem lại. Nhấn Lưu vào thư viện để kiểm tra lại.");
            return;
        }
        publish();
    }
    function confirmUpdate() {
        const reviewed = updateReview;
        if (!reviewed || !draft || reviewed.id !== draft.id || reviewed.revision !== draft.revision || reviewed.digest !== draft.digest || dirty) {
            showLocalError("Nháp đã thay đổi sau khi xem lại. Nhấn Cập nhật để kiểm tra lại.");
            return;
        }
        updateInstalled();
    }
    function create(identifier, title, tags, difficulty, callback) {
        if (dirty) {
            showLocalError("Lưu bản nháp trước khi tạo bài khác.");
            return;
        }
        identifier = identifier.trim();
        title = title.trim();
        const selectedTags = tags && typeof tags === "object" && Number.isInteger(tags.length) ? Array.from(tags) : [];
        if (!selectedTags.length || selectedTags.some(tag => typeof tag !== "string" || !tag.trim())) {
            showLocalError("Chọn ít nhất một chủ đề cho bài lab.");
            return;
        }
        if (!["easy", "medium", "hard"].includes(difficulty)) {
            showLocalError("Chọn độ khó cho bài lab.");
            return;
        }
        const args = ["draft", "create", identifier, "--title", title];
        for (const tag of selectedTags) args.push("--tag", tag);
        args.push("--difficulty", difficulty);
        localError = "";
        backend.request(args, (result, error) => {
            if (!error) {
                adopt(result, false);
                section = 0;
                localError = "";
                if (callback)
                    callback();
                else
                    refresh();
            }
        });
    }
    function deleteDraft() {
        backend.request(["draft", "delete", draft.id, "--revision", String(draft.revision)], (result, error) => {
            if (!error) {
                documentGeneration++;
                draft = null;
                definition = "";
                definitionDirty = false;
                files.reset();
                startup.reset();
                documentationText = "";
                documentationDirty = false;
                documentationReady = true;
                report = null;
                runtimeReport = null;
                publicationReview = null;
                updateReview = null;
                localError = "";
                refresh();
            }
        });
    }
    function discardChanges() {
        if (backend.busy)
            return false;
        definition = draft ? draft.definition : "";
        definitionDirty = false;
        documentationDirty = false;
        files.reset();
        startup.reset();
        report = null;
        runtimeReport = null;
        publicationReview = null;
        updateReview = null;
        localError = "";
        loadDocumentation();
        return true;
    }
    function discardAndBack() {
        if (discardChanges()) backRequested();
    }
    function editLab(labId, callback) {
        if (draft && draft.origin && draft.origin.lab_id === labId && document && document.metadata.id === labId) {
            section = 0;
            if (callback) callback();
            return;
        }
        if (dirty) {
            showLocalError("Lưu bản nháp trước khi sửa bài khác.");
            backend.notify(localError, true);
            return;
        }
        if (backend.busy) return;
        editCallback = callback || null;
        requestEditingDraft(labId, "", false);
    }
    function cancelEditChoice() {
        editChoice = null;
        editCallback = null;
    }
    function chooseEditingDraft(identifier, fresh) {
        if (!editChoice || dirty || backend.busy) return;
        requestEditingDraft(editChoice.lab_id, identifier, fresh);
    }
    function requestEditingDraft(labId, identifier, fresh) {
        const args = ["draft", "edit", labId];
        if (fresh) args.push("--new");
        else if (identifier) args.push("--draft", identifier);
        backend.request(args, (result, error) => {
            if (error || !result) return;
            if (dirty) {
                backend.notify("Giữ nguyên thay đổi chưa lưu. Lưu bản nháp rồi mở lại bài cần sửa.", true);
                return;
            }
            if (result.selection_required) {
                editChoice = result;
                editChoiceRequested();
                return;
            }
            const completed = editCallback;
            cancelEditChoice();
            adopt(result, false);
            section = 0;
            localError = "";
            if (completed) completed();
            else refresh();
        });
    }
    function loadDocumentation() {
        const generation = ++documentGeneration;
        documentationText = "";
        documentationDirty = false;
        documentationReady = !document || !document.documentation;
        if (documentationReady)
            return;
        backend.request(["draft", "asset", draft.id, document.documentation, "--revision", String(draft.revision), "--text"], (result, error) => {
            if (generation !== documentGeneration)
                return;
            if (!error) {
                documentationText = result.content;
                documentationReady = true;
                files.setEntry(document.documentation, {text: result.content, ready: true, dirty: false, error: ""});
            }
        });
    }
    function modify(group, entry, index) {
        attempt(() => {
            commit(Model.modify(document, group, entry, index));
            selectedNode = Math.max(0, Math.min(selectedNode, document.nodes.length - 1));
            selectedNetwork = Math.max(0, Math.min(selectedNetwork, document.networks.length - 1));
        });
    }
    function newNode(identifier) {
        return Defaults.newNode(document, policy, identifier, Studio.LabPreferences.username);
    }
    function nextNodeId() {
        if (!document.nodes.some(node => node.id === "client"))
            return "client";
        if (!document.nodes.some(node => node.id === "server"))
            return "server";
        return Model.nextId(document.nodes, "node");
    }
    function openDraft(identifier, keepSection) {
        backend.request(["draft", "show", identifier], (result, error) => {
            if (error)
                return;
            const same = draft && draft.id === result.id;
            adopt(result, false);
            if (!keepSection) section = 0;
            if (same)
                loadDocumentation();
            showLocalError(document ? "" : "Nháp này không phải JSON dùng cho biểu mẫu. Dùng CLI để xem/sửa định nghĩa; dữ liệu gốc vẫn được giữ.");
        });
    }
    function parse(text) {
        try {
            const value = JSON.parse(text);
            return value && value.metadata && Array.isArray(value.nodes) && Array.isArray(value.networks) ? value : null;
        } catch (error) {
            return null;
        }
    }
    function prepareLibrarySave() {
        if (!draft || !document || backend.busy)
            return;
        if (!Array.isArray(document.metadata.tags) || !document.metadata.tags.length) {
            section = 0;
            showLocalError("Chọn ít nhất một chủ đề trước khi lưu bài vào thư viện.");
            return;
        }
        const draftId = draft.id;
        validate(() => {
            if (!draft || draft.id !== draftId || !document || dirty || !report || !report.valid || report.revision !== draft.revision || report.digest !== draft.digest)
                return;
            const review = {
                id: draft.id,
                revision: draft.revision,
                digest: draft.digest,
                labId: document.metadata.id,
                name: document.metadata.name,
                nodes: document.nodes.length,
                networks: document.networks.length,
                assets: draft.assets.length
            };
            if (isInstalledEdit) {
                updateReview = review;
                updateReviewRequested();
            } else {
                publicationReview = review;
                publicationReviewRequested();
            }
        });
    }
    function publish(callback) {
        if (!report || !report.valid || dirty || report.revision !== draft.revision || report.digest !== draft.digest) {
            showLocalError("Cần kiểm tra đúng phiên bản trước khi lưu vào thư viện.");
            return;
        }
        backend.request(["draft", "publish", draft.id, "--revision", String(report.revision), "--digest", report.digest], (result, error) => {
            if (!error && result.published) {
                report = null;
                publicationReview = null;
                published();
                if (callback)
                    callback();
            } else if (result && result.valid === false)
                report = result;
        });
    }
    function refresh() {
        if (!supported)
            return;
        backend.request(["draft", "info"], (result, error) => {
            if (!error)
                policy = result;
        });
        backend.request(["draft", "list"], (result, error) => {
            if (!error)
                drafts = result;
        });
    }
    function removeAsset(path) {
        attempt(() => {
            Model.removeAsset(document, path, draft.assets);
            const remove = () => backend.request(["draft", "remove-asset", draft.id, path, "--revision", String(draft.revision)], (result, error) => {
                    if (!error)
                        adopt(result, true);
                });
            if (dirty)
                save(remove);
            else
                remove();
        });
    }
    function removeEntry(section, index) {
        attempt(() => commit(Model.removeEntry(document, section, index)));
    }
    function removeHomeFile(nodeId, path) {
        if (!draft || !document || backend.busy)
            return;
        attempt(() => {
            const plan = Model.removeSeedFile(document, nodeId, path, draft.assets);
            commit(plan.document);
            if (plan.source)
                removeAsset(plan.source);
            else
                save();
        });
    }
    function removeMapping(nodeIndex, index) {
        const copy = Model.clone(document);
        copy.nodes[nodeIndex].files.splice(index, 1);
        commit(copy);
    }
    function removeNestedEntry(root, section, index) {
        attempt(() => commit(Model.removeNestedEntry(document, root, section, index)));
    }
    function removeQuizGroup(index) {
        attempt(() => commit(Model.removeQuizGroup(document, index)));
    }
    function removeQuizItem(groupIndex, itemIndex) {
        attempt(() => commit(Model.removeQuizItem(document, groupIndex, itemIndex)));
    }
    function requestBack() {
        if (backend.busy)
            return;
        if (dirty)
            discardRequested();
        else
            backRequested();
    }
    function reviewPublication() {
        if (!draft || !document || backend.busy)
            return;
        validate(() => {
            publicationReview = {
                id: draft.id,
                revision: report.revision,
                digest: report.digest,
                labId: document.metadata.id,
                name: document.metadata.name,
                nodes: document.nodes.length,
                networks: document.networks.length,
                assets: draft.assets.length
            };
            publicationReviewRequested();
        });
    }
    function reviewUpdate() {
        if (!draft || !document || backend.busy)
            return;
        validate(() => {
            updateReview = {
                id: draft.id,
                revision: report.revision,
                digest: report.digest,
                labId: draft.origin.lab_id,
                name: document.metadata.name,
                nodes: document.nodes.length,
                networks: document.networks.length,
                assets: draft.assets.length
            };
            updateReviewRequested();
        });
    }
    function save(callback) {
        if (!draft || !document)
            return;
        files.save(callback);
    }
    function selectImage(index, image) {
        attempt(() => commit(Defaults.changeImage(document, index, image, policy, Studio.LabPreferences.username)));
    }
    function showMachines() {
        section = 1;
        refresh();
    }
    function updateEntry(section, index, field, value) {
        attempt(() => commit(Model.updateEntry(document, section, index, field, value)));
    }
    function updateInstalled(callback) {
        if (!report || !report.valid || dirty || report.revision !== draft.revision || report.digest !== draft.digest) {
            showLocalError("Cần kiểm tra đúng phiên bản và nội dung trước khi cập nhật bài trong thư viện.");
            return;
        }
        backend.request(["draft", "update", draft.origin.lab_id, draft.id, "--revision", String(report.revision), "--digest", report.digest, "--catalog-digest", draft.origin.digest, "--yes"], (result, error) => {
            if (!error && result && result.updated) {
                report = null;
                updateReview = null;
                published();
                if (callback)
                    callback();
            } else if (result && result.valid === false) {
                report = result;
            }
        });
    }
    function updateNestedEntry(root, section, index, field, value) {
        attempt(() => commit(Model.updateNestedEntry(document, root, section, index, field, value)));
    }
    function updateQuizGroup(index, field, value) {
        attempt(() => commit(Model.updateQuizGroup(document, index, field, value)));
    }
    function updateQuizItem(groupIndex, itemIndex, field, value) {
        attempt(() => commit(Model.updateQuizItem(document, groupIndex, itemIndex, field, value)));
    }
    function upload(source, logical, tree, callback) {
        const transfer = () => {
            const args = tree ? ["draft", "put-tree", draft.id, source, "--prefix", logical] : ["draft", "put-file", draft.id, source, logical];
            backend.request(args.concat(["--revision", String(draft.revision)]), (result, error) => {
                if (!error) {
                    adopt(result, true);
                    backend.notify("Đã thêm tài nguyên vào bản nháp.", false);
                    if (callback)
                        callback();
                }
            });
        };
        if (dirty)
            save(transfer);
        else
            transfer();
    }
    function uploadHome(source, nodeId, name, tree, subfolder) {
        attempt(() => {
            if (!policy || !policy.home_directory_target)
                throw new Error("Cần cập nhật daemon để hỗ trợ thêm nội dung folder trực tiếp vào home.");
            const plan = Model.homeUpload(document, nodeId, name, tree, subfolder, draft.assets);
            upload(source, plan.logical, tree, () => {
                attempt(() => {
                    const current = Model.homeUpload(document, nodeId, name, tree, subfolder, draft.assets, true);
                    commit(current.document);
                    save();
                });
            });
        });
    }
    function userField(index, field, value) {
        if (!document || !document.nodes[index] || !document.nodes[index].user)
            return;
        const identity = Model.clone(document.nodes[index].user);
        identity[field] = value;
        if (field === "name")
            identity.home = "/home/" + value;
        change("nodes", index, "user", identity);
    }

    function accountChange(index, operation, name, value) {
        attempt(() => {
            if (accountPasswordPending || backend.busy)
                throw new Error("Đợi thao tác hiện tại hoàn tất.");
            const node = document && document.nodes[index];
            const profile = node ? Defaults.profile(policy, node.image) : null;
            if (!profile || !profile.workstation || !profile.custom_username)
                throw new Error("Máy này không hỗ trợ cấu hình tài khoản.");
            const operations = {addUser: Accounts.addUser, addGroup: Accounts.addGroup,
                removeUser: Accounts.removeUser, removeGroup: Accounts.removeGroup,
                sudo: Accounts.setSudo, groups: Accounts.setGroups, renameMain: Accounts.renameMain,
                renameUser: Accounts.renameUser, renameGroup: Accounts.renameGroup};
            if (!operations[operation]) throw new Error("Thao tác tài khoản không hợp lệ.");
            const copy = Model.clone(document);
            copy.nodes[index] = operations[operation](node, name, value);
            commit(copy);
        });
    }

    function setAccountPassword(index, account, action, password) {
        if (!policy || !policy.machine_setup || policy.machine_setup_version !== 1) return;
        if (!draft || dirty || accountPasswordPending || backend.busy) {
            showLocalError(qsTr("Lưu thay đổi trước khi đặt hoặc khóa mật khẩu."));
            return;
        }
        const node = document && document.nodes[index];
        if (!node || index !== selectedNode || !["replace", "lock"].includes(action)) return;
        const profile = Defaults.profile(policy, node.image);
        if (!profile || !profile.machine_setup || !profile.workstation) return;
        if (action === "replace" && !Accounts.validPassword(password)) {
            showLocalError(qsTr("Mật khẩu cần 1–128 byte UTF-8, không chứa ký tự xuống dòng."));
            return;
        }
        const identifier = draft.id;
        const revision = draft.revision;
        const generation = accountContextGeneration;
        const original = definition;
        const request = {account: account, action: action};
        if (action === "replace") request.password = password;
        accountPasswordPending = true;
        backend.request(["draft", "account-password", identifier, node.id, "--revision", String(revision)], (result, error) => {
            accountPasswordPending = false;
            if (error || !result) {
                showLocalError(qsTr("Không cập nhật được mật khẩu. Tải lại bản nháp rồi thử lại."));
                return;
            }
            if (!draft || draft.id !== identifier || draft.revision !== revision || dirty || definition !== original || generation !== accountContextGeneration) {
                showLocalError(qsTr("Mật khẩu đã cập nhật. Tải lại bản nháp để nhận phiên bản mới; thay đổi đang sửa được giữ nguyên."));
                return;
            }
            adopt(result, false, true);
        }, JSON.stringify(request));
    }
    function validate(callback) {
        localError = "";
        report = null;
        publicationReview = null;
        updateReview = null;
        const check = () => backend.request(["draft", "check", draft.id, "--revision", String(draft.revision)], (result, error) => {
                if (result)
                    report = result;
                if (!error && report && report.valid && callback)
                    callback();
            });
        if (!draft)
            return;
        if (dirty)
            save(check);
        else
            check();
    }
}
