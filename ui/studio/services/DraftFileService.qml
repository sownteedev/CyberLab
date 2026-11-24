import QtQuick
import "../models/DraftFiles.js" as Files

QtObject {
    id: service
    required property var editor
    property var buffers: ({})
    property var pending: ({})
    property var removals: []
    property var roots: ({})
    property var tabs: []
    property string activeKey: ""
    property int generation: 0
    property bool saving: false
    readonly property bool setupSupported: (editor.backend.capabilities || []).includes("machine-setup-v1")
    readonly property bool dirty: Object.keys(pending).length > 0 || removals.length > 0 || Object.keys(buffers).some(path => buffers[path].dirty)
    readonly property var assets: {
        const result = (editor.draft ? editor.draft.assets || [] : []).filter(asset => !removals.includes(asset.path));
        Object.keys(pending).concat(Object.keys(buffers).filter(path => buffers[path].dirty)).forEach(path => {
            const index = result.findIndex(asset => asset.path === path);
            const entry = {path: path, kind: pending[path] && pending[path].directory ? "directory" : "file", size: 0};
            if (index < 0) result.push(entry);
            else result[index] = entry;
        });
        return result;
    }
    readonly property var activeTab: tabs.find(tab => tab.key === activeKey) || null

    function reset() {
        generation++;
        buffers = {};
        pending = {};
        removals = [];
        roots = {};
        tabs = [];
        activeKey = "";
        saving = false;
    }
    function setEntry(path, entry) {
        buffers = Object.assign({}, buffers, {[path]: entry});
    }
    function editDocumentation(text) {
        if (!editor.document) return;
        editor.attempt(() => {
            const document = Files.clone(editor.document);
            let path = document.documentation;
            const shared = path && document.nodes.some(node => Files.mappings(node).some(mapping => Files.within(path, mapping.source)));
            if (!path || shared) {
                path = "";
                for (let index = 0; index < 128; index++) {
                    const candidate = "assets/docs/guide" + (index ? "-" + index : "") + ".md";
                    if (!assets.some(asset => Files.within(asset.path, candidate) || Files.within(candidate, asset.path)) && !Files.used(document, candidate)) {
                        path = candidate;
                        break;
                    }
                }
                if (!path) throw new Error("Không còn tên trống cho hướng dẫn.");
                document.documentation = path;
                editor.commit(document);
            }
            setEntry(path, {text: text, ready: true, dirty: true, error: ""});
            editor.documentationText = text;
            editor.documentationReady = true;
            editor.documentationDirty = true;
            editor.report = null;
            editor.publicationReview = null;
        });
    }
    function state() {
        const value = Files.initial(editor.document, assets);
        value.pending = Files.clone(pending);
        Object.keys(buffers).filter(path => buffers[path].dirty).forEach(path => value.pending[path] = {text: buffers[path].text});
        value.removals = removals.slice();
        value.roots = Files.clone(roots);
        return value;
    }
    function rows(nodeId, area) {
        try { return Files.project(editor.document, assets, nodeId, area); }
        catch (error) { return []; }
    }
    function requireSetup(path, metadata) {
        if (!setupSupported && (metadata || Files.systemPath(path)))
            throw new Error("Backend chưa hỗ trợ thiết lập máy. Các khai báo được giữ nguyên.");
    }
    function metadata(nodeId, path) { return Files.metadata(editor.document, assets, nodeId, path); }
    function properties(nodeId, path, values) {
        editor.attempt(() => {
            requireSetup(path, true);
            apply(Files.properties(state(), nodeId, path, values));
        });
    }
    function source(nodeId, path) {
        const row = rows(nodeId, Files.branch(path)).find(entry => entry.path === path);
        return row ? row.source : "";
    }
    function apply(value) {
        const next = Object.assign({}, buffers);
        Object.keys(value.remapped).forEach(old => {
            if (next[old] && next[old].ready) next[value.remapped[old]] = Object.assign({}, next[old]);
        });
        Object.keys(value.pending).forEach(path => {
            if (value.pending[path].text !== undefined && !next[path])
                next[path] = {text: value.pending[path].text, ready: true, dirty: true, error: ""};
        });
        Object.keys(next).forEach(path => {
            if (!value.assets.some(asset => asset.path === path)) delete next[path];
        });
        pending = value.pending;
        removals = value.removals;
        roots = value.roots;
        buffers = next;
        editor.commit(value.document);
    }
    function open(nodeId, path) {
        const key = nodeId + ":" + path;
        if (!tabs.some(tab => tab.key === key)) tabs = tabs.concat([{key: key, nodeId: nodeId, path: path}]);
        activeKey = key;
        loadSource(source(nodeId, path));
    }
    function close(key) {
        tabs = tabs.filter(tab => tab.key !== key);
        if (activeKey === key) activeKey = tabs.length ? tabs[tabs.length - 1].key : "";
    }
    function loadSource(path, callback) {
        if (!path) return;
        if (buffers[path] && buffers[path].ready) { if (callback) callback(buffers[path]); return; }
        if (buffers[path] && buffers[path].loading) return;
        if (pending[path] && pending[path].text !== undefined) {
            const entry = {text: pending[path].text, ready: true, dirty: true, error: ""};
            setEntry(path, entry);
            if (callback) callback(entry);
            return;
        }
        if (pending[path] && pending[path].bytes !== undefined) {
            setEntry(path, {text: "", ready: false, dirty: false, binary: true, error: ""});
            return;
        }
        if (!editor.draft || editor.backend.busy) return;
        const expected = generation;
        const draftId = editor.draft.id;
        const revision = editor.draft.revision;
        const origin = pending[path] && pending[path].copy ? pending[path].copy : path;
        setEntry(path, {text: "", ready: false, dirty: false, loading: true, error: ""});
        editor.backend.request(["draft", "asset", draftId, origin, "--revision", String(revision), "--preview"], (result, error) => {
            if (expected !== generation || !editor.draft || editor.draft.id !== draftId || (buffers[path] && buffers[path].dirty)) return;
            const problem = error || (editor.draft.revision !== revision ? "Bản nháp đã thay đổi. Mở lại file." : "");
            const entry = {text: problem ? "" : result.content || "", ready: !problem && result.editable !== false,
                dirty: false, loading: false, binary: !problem && result.editable === false, error: problem};
            setEntry(path, entry);
            if (callback) callback(entry);
        });
    }
    function edit(nodeId, path, text) {
        editor.attempt(() => {
            requireSetup(path, false);
            const original = source(nodeId, path);
            if (!buffers[original] || !buffers[original].ready || editor.backend.busy || buffers[original].text === text) return;
            apply(Files.systemPath(path) ? Files.privateSystem(state(), nodeId, path) : Files.privateNode(state(), nodeId));
            setEntry(source(nodeId, path), {text: text, ready: true, dirty: true, error: ""});
            editor.report = null;
        });
    }
    function create(nodeId, path, directory) {
        editor.attempt(() => {
            requireSetup(path, false);
            apply(Files.create(state(), nodeId, path, directory));
            if (!directory) open(nodeId, path);
        });
    }
    function rename(nodeId, path, name) {
        editor.attempt(() => {
            requireSetup(path, false);
            const next = (path.includes("/") ? path.substring(0, path.lastIndexOf("/") + 1) : "") + name;
            apply(Files.rename(state(), nodeId, path, name));
            const selected = activeKey;
            tabs = tabs.map(tab => {
                if (tab.nodeId !== nodeId || !Files.within(tab.path, path)) return tab;
                const target = next + tab.path.substring(path.length);
                const entry = {nodeId: nodeId, path: target, key: nodeId + ":" + target};
                if (tab.key === selected) activeKey = entry.key;
                return entry;
            });
        });
    }
    function remove(nodeId, path) {
        editor.attempt(() => {
            requireSetup(path, false);
            apply(Files.remove(state(), nodeId, path));
            tabs = tabs.filter(tab => tab.nodeId !== nodeId || !Files.within(tab.path, path));
            if (!tabs.some(tab => tab.key === activeKey)) activeKey = tabs.length ? tabs[0].key : "";
        });
    }
    function save(callback) {
        if (!editor.draft || !editor.document || saving) return;
        if (!setupSupported && editor.document.nodes.some(node => node.setup !== undefined)) {
            editor.showLocalError("Backend chưa hỗ trợ thiết lập máy. Các khai báo được giữ nguyên.");
            return;
        }
        if (editor.documentationDirty) {
            const path = editor.document.documentation || "assets/docs/guide.md";
            const document = Files.clone(editor.document);
            document.documentation = path;
            editor.commit(document);
            setEntry(path, {text: editor.documentationText, dirty: true, ready: true, error: ""});
        }
        const writes = Files.clone(pending);
        Object.keys(buffers).filter(path => buffers[path].dirty).forEach(path => writes[path] = {text: buffers[path].text});
        const definition = editor.definition;
        const draftId = editor.draft.id;
        const expected = generation;
        const payload = {definition: definition, entries: writes,
            removals: removals.filter(path => (editor.draft.assets || []).some(asset => asset.path === path))};
        saving = true;
        editor.backend.request(["draft", "save-workspace", draftId, "-", "--revision", String(editor.draft.revision)], (result, error) => {
            if (generation !== expected || !editor.draft || editor.draft.id !== draftId) return;
            saving = false;
            if (error) { editor.showLocalError(error); return; }
            pending = {};
            removals = [];
            const next = Object.assign({}, buffers);
            Object.keys(writes).forEach(path => {
                if (next[path] && writes[path].text === next[path].text) next[path] = Object.assign({}, next[path], {dirty: false});
            });
            buffers = next;
            editor.adopt(result, true);
            if (editor.definition === definition) editor.definitionDirty = false;
            editor.documentationDirty = false;
            editor.localError = "";
            editor.backend.notify("Đã lưu bản nháp.", false);
            if (callback) callback();
        }, JSON.stringify(payload));
    }
    function importLocal(filename, nodeId, folder, directory) {
        if (!setupSupported && Files.systemPath(folder)) {
            editor.showLocalError("Backend chưa hỗ trợ thiết lập máy. Các khai báo được giữ nguyên.");
            return;
        }
        const draftId = editor.draft.id;
        const definition = editor.definition;
        const expected = generation;
        editor.backend.request(["draft", "read-local", filename].concat(directory ? ["--folder"] : []), (result, error) => {
            if (error || expected !== generation || !editor.draft || editor.draft.id !== draftId) return;
            editor.attempt(() => {
                requireSetup(folder, false);
                if (editor.definition !== definition) throw new Error("Bản nháp đã thay đổi. Chọn lại file.");
                const value = Files.importResources(state(), nodeId, folder, result.resources);
                apply(value);
                const next = Object.assign({}, buffers);
                result.resources.forEach(resource => {
                    const target = folder.replace(/\/$/, "") + (folder && resource.path ? "/" : "") + resource.path;
                    const path = source(nodeId, target);
                    if (resource.kind !== "file") return;
                    next[path] = {text: resource.content.text || "", ready: resource.content.text !== undefined,
                        dirty: resource.content.text !== undefined, binary: resource.content.bytes !== undefined, error: ""};
                });
                buffers = next;
            });
        });
    }
}
