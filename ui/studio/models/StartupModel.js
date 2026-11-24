.pragma library

function script(node, assets) {
    const command = node ? node.command || [] : [];
    if (command.length !== 2 || !["/bin/sh", "/bin/bash", "sh", "bash"].includes(command[0])) return null;
    const target = command[1].replace(/^\.\//, "");
    if (!safePath(target)) return null;
    const matches = [];
    (node.files || []).forEach(mapping => {
        let source = "";
        if (mapping.target === target) source = mapping.source;
        else if (mapping.target === ".") source = mapping.source + "/" + target;
        else if (target.startsWith(mapping.target + "/")) source = mapping.source + target.substring(mapping.target.length);
        if (source && assets.some(asset => asset.path === source && asset.kind !== "directory"))
            matches.push({source: source, target: target, shell: command[0]});
    });
    return matches.length === 1 ? matches[0] : null;
}

function safePath(path) {
    return typeof path === "string" && path.length <= 200 && path.split("/").every(part => /^[A-Za-z0-9_][A-Za-z0-9_.-]{0,63}$/.test(part));
}

function overlaps(first, second) {
    return first === second || first.startsWith(second + "/") || second.startsWith(first + "/");
}

function shared(document, nodeId, source, target) {
    return document.documentation === source || document.nodes.some(node => (node.files || []).some(mapping => {
        if (mapping.source !== source && !source.startsWith(mapping.source + "/")) return false;
        const relative = source === mapping.source ? "" : source.substring(mapping.source.length + 1);
        const destination = mapping.target === "." ? relative : mapping.target + (relative ? "/" + relative : "");
        return node.id !== nodeId || destination !== target;
    }));
}

function create(document, nodeId, assets) {
    const copy = JSON.parse(JSON.stringify(document));
    const node = copy.nodes.find(entry => entry.id === nodeId);
    if (!node || !safePath(nodeId) || nodeId.includes("/")) throw new Error("Chọn máy có tên hợp lệ.");
    node.files = (node.files || []).reduce((mappings, mapping) => {
        if (mapping.target !== ".") return mappings.concat([mapping]);
        const children = [];
        assets.filter(asset => asset.path.startsWith(mapping.source + "/")).forEach(asset => {
            const child = asset.path.substring(mapping.source.length + 1).split("/")[0];
            if (!children.includes(child)) children.push(child);
        });
        if (!children.length && !assets.some(asset => asset.path === mapping.source && asset.kind === "directory"))
            throw new Error("Chưa có danh sách file của máy. Lưu và tải lại bản nháp.");
        return mappings.concat(children.map(child => ({source: mapping.source + "/" + child, target: child})));
    }, []);
    if (node.files.length >= 16) throw new Error("Máy đã đủ 16 nhóm file.");
    const sources = assets.filter(asset => asset.kind !== "directory").map(asset => asset.path).concat(copy.nodes.reduce((entries, item) =>
        entries.concat((item.files || []).map(mapping => mapping.source)), []));
    if (copy.documentation) sources.push(copy.documentation);
    let source = "";
    for (let index = 0; index < 128; index++) {
        const candidate = "assets/startup/" + nodeId + "/start" + (index ? "-" + index : "") + ".sh";
        if (!sources.some(path => overlaps(path, candidate)) && !assets.some(asset => asset.path === candidate)) { source = candidate; break; }
    }
    if (!source) throw new Error("Thư mục assets/startup đang được dùng chung. Đổi nguồn file trước khi tạo script.");
    const targets = [];
    (node.files || []).forEach(mapping => {
        if (mapping.target !== ".") targets.push(mapping.target);
        assets.filter(asset => asset.path.startsWith(mapping.source + "/")).forEach(asset => {
            const relative = asset.path.substring(mapping.source.length + 1);
            targets.push(mapping.target === "." ? relative : mapping.target + "/" + relative);
        });
    });
    let target = "";
    for (let index = 0; index < 128; index++) {
        const candidate = "start" + (index ? "-" + index : "") + ".sh";
        if (!targets.some(path => overlaps(path, candidate))) { target = candidate; break; }
    }
    if (!target) throw new Error("Không còn tên script trống trong máy.");
    node.files = (node.files || []).concat([{source: source, target: target}]);
    node.command = ["/bin/sh", target];
    return {document: copy, source: source, target: target};
}
