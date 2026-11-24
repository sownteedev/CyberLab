import QtQuick
import "../models/StartupModel.js" as Startup

QtObject {
    id: service
    required property var editor
    readonly property var entries: editor.files.buffers
    property var previousScripts: ({})
    property var previousCommands: ({})
    property int generation: 0
    readonly property bool dirty: Object.keys(entries).some(path => entries[path].dirty)
    readonly property var assets: editor.files.assets

    function reset() {
        generation++;
        previousScripts = {};
        previousCommands = {};
    }
    function setEntry(path, entry) {
        editor.files.setEntry(path, entry);
    }
    function descriptor(node) {
        const unique = assets.filter((asset, index) => assets.findIndex(item => item.path === asset.path) === index);
        return Startup.script(node, unique);
    }
    function useDefault(node, command) {
        if (!node) return;
        const current = descriptor(node);
        if (current) previousScripts = Object.assign({}, previousScripts, {[node.id]: current});
        else if (JSON.stringify(node.command || []) !== JSON.stringify(command))
            previousCommands = Object.assign({}, previousCommands, {[node.id]: (node.command || []).slice()});
        editor.change("nodes", editor.document.nodes.findIndex(item => item.id === node.id), "command", command);
    }
    function useCustom(node) {
        if (!node) return;
        const current = descriptor(node);
        if (current) previousScripts = Object.assign({}, previousScripts, {[node.id]: current});
        editor.change("nodes", editor.document.nodes.findIndex(item => item.id === node.id), "command",
            previousCommands[node.id] || ["/bin/sh", "-c", "exec sleep infinity"]);
    }
    function useScript(node, rememberCustom) {
        if (!node) return;
        if (rememberCustom) previousCommands = Object.assign({}, previousCommands, {[node.id]: (node.command || []).slice()});
        const previous = previousScripts[node.id];
        const candidate = previous ? Object.assign({}, node, {command: [previous.shell, previous.target]}) : null;
        const current = candidate ? descriptor(candidate) : null;
        if (current && current.source === previous.source) {
            editor.change("nodes", editor.document.nodes.findIndex(item => item.id === node.id), "command", candidate.command);
            load(candidate);
        } else create(node);
    }
    function load(node) {
        const current = descriptor(node);
        if (current) editor.files.loadSource(current.source);
    }
    function retry(node) {
        const current = descriptor(node);
        if (!current || (entries[current.source] && entries[current.source].dirty)) return;
        const copy = Object.assign({}, entries);
        delete copy[current.source];
        editor.files.buffers = copy;
        load(node);
    }
    function edit(node, text) {
        const current = descriptor(node);
        if (!current || !entries[current.source] || !entries[current.source].ready || editor.backend.busy) return;
        if (Startup.shared(editor.document, node.id, current.source, current.target)) return;
        setEntry(current.source, {text: text, ready: true, dirty: true, error: ""});
        editor.report = null;
        editor.publicationReview = null;
        editor.updateReview = null;
        editor.runtimeReport = null;
    }
    function create(node, text) {
        editor.attempt(() => {
            if (!node || editor.backend.busy) return;
            const plan = Startup.create(editor.document, node.id, assets);
            if (text !== undefined && descriptor(node))
                plan.document.nodes.find(item => item.id === node.id).command[0] = descriptor(node).shell;
            editor.commit(plan.document);
            setEntry(plan.source, {text: text === undefined ? "#!/bin/sh\nset -eu\n\nexec sleep infinity\n" : text,
                ready: true, dirty: true, error: ""});
        });
    }
    function importFile(node, filename) {
        if (!node || !editor.draft || editor.backend.busy) return;
        const draftId = editor.draft.id;
        const nodeId = node.id;
        const definition = editor.definition;
        const expected = generation;
        editor.backend.request(["draft", "read-local", filename], (result, error) => {
            if (error || expected !== generation || !editor.draft || editor.draft.id !== draftId) return;
            editor.attempt(() => {
                if (editor.definition !== definition) throw new Error("Bản nháp đã thay đổi. Chọn lại script.");
                const resource = result.resources[0];
                if (!resource || resource.content.text === undefined) throw new Error("Script phải là văn bản UTF-8, tối đa 64 KiB.");
                const plan = Startup.create(editor.document, nodeId, assets);
                plan.document.nodes.find(item => item.id === nodeId).command[0] = /^#![^\n]*\bbash\b/.test(resource.content.text) ? "/bin/bash" : "/bin/sh";
                setEntry(plan.source, {text: resource.content.text, ready: true, dirty: true, error: ""});
                editor.commit(plan.document);
            });
        });
    }
}
