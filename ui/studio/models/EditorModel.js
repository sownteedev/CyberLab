.pragma library
.import "LabeditModel.js" as Labedit
.import "AssessmentModel.js" as Assessment

function clone(document) {
    return JSON.parse(JSON.stringify(document));
}

function identifier(value, entries, previous) {
    if (!/^[a-z][a-z0-9]*(-[a-z0-9]+)*$/.test(value) || value.length > 64)
        throw new Error("Mã chỉ gồm chữ thường, số và dấu gạch nối.");
    if (value !== previous && entries.some(entry => entry.id === value))
        throw new Error("Mã đã tồn tại: " + value);
}

function nextId(entries, prefix) {
    let number = 1;
    while (entries.some(entry => entry.id === prefix + "-" + number)) number++;
    return prefix + "-" + number;
}

function cleanDns(document) {
    document.nodes.forEach(node => {
        if (!node.dns) return;
        node.dns = node.dns.filter(address => document.nodes.some(server =>
            node.networks.some(network => server.networks.includes(network)
                && (server.addresses || {})[network] === address)));
    });
    return document;
}

function change(document, section, index, field, value) {
    const copy = clone(document);
    if (section === "metadata") {
        if (field === "id") identifier(value, [], copy.metadata.id);
        copy.metadata[field] = value;
        return copy;
    }
    const entry = copy[section][index];
    if (!entry) throw new Error("Đối tượng không còn tồn tại.");
    const previousPrompt = section === "nodes" ? (entry.user ? entry.user.name : "nobody") + "@" + (entry.hostname || entry.id) : "";
    const followsPrompt = section === "nodes" && entry.terminal_title === previousPrompt;
    if (field === "id") {
        identifier(value, copy[section], entry.id);
        const previous = entry.id;
        if (section === "nodes" && entry.hostname === previous) entry.hostname = value;
        if (section === "nodes") Labedit.renameNode(copy, previous, value);
        if (section === "nodes") copy.terminals = (copy.terminals || []).map(name => name === previous ? value : name);
        if (section === "networks") copy.nodes.forEach(node => {
            node.networks = node.networks.map(name => name === previous ? value : name);
            if (node.addresses && Object.prototype.hasOwnProperty.call(node.addresses, previous)) {
                const address = node.addresses[previous];
                delete node.addresses[previous];
                node.addresses[value] = address;
            }
        });
    }
    if (value === "" || value === null) delete entry[field];
    else entry[field] = value;
    if (followsPrompt && ["id", "hostname", "user"].includes(field))
        entry.terminal_title = (entry.user ? entry.user.name : "nobody") + "@" + (entry.hostname || entry.id);
    if (section === "networks" && field === "subnet" && !value) {
        delete entry.gateway;
        copy.nodes.forEach(node => { if (node.addresses) delete node.addresses[entry.id]; });
        cleanDns(copy);
    }
    return copy;
}

function modify(document, section, entry, index) {
    const copy = clone(document);
    if (index === undefined) {
        identifier(entry.id, copy[section]);
        if (copy[section].length >= 4) throw new Error("Tối đa 4 máy hoặc mạng.");
        copy[section].push(clone(entry));
        if (section === "nodes") copy.terminals = (copy.terminals || []).concat([entry.id]);
    } else {
        const previous = copy[section][index].id;
        if (section === "nodes") Labedit.requireUnusedNode(copy, previous);
        copy[section].splice(index, 1);
        if (section === "nodes") copy.terminals = (copy.terminals || []).filter(name => name !== previous);
        if (section === "networks") copy.nodes.forEach(node => {
            node.networks = node.networks.filter(name => name !== previous);
            if (node.addresses) delete node.addresses[previous];
        });
        cleanDns(copy);
    }
    return copy;
}

function attach(document, index, network, enabled, address) {
    const copy = clone(document);
    const node = copy.nodes[index];
    if (!copy.networks.some(entry => entry.id === network)) throw new Error("Mạng không tồn tại.");
    node.networks = node.networks.filter(name => name !== network);
    node.addresses = node.addresses || {};
    delete node.addresses[network];
    if (enabled) {
        node.networks.push(network);
        if (address) node.addresses[network] = address;
    }
    return cleanDns(copy);
}

function autoOpen(document, nodeId, enabled) {
    const copy = clone(document);
    copy.terminals = (copy.terminals || []).filter(name => name !== nodeId);
    if (enabled) copy.terminals.push(nodeId);
    return copy;
}

function safePath(path) {
    return typeof path === "string" && path.length <= 200 && path.split("/").length <= 8
        && path.split("/").every(part => /^[A-Za-z0-9_][A-Za-z0-9_.-]{0,63}$/.test(part));
}

function addMapping(document, nodeId, source, target) {
    if (!source.startsWith("assets/") || !safePath(source) || (target !== "." && !safePath(target)))
        throw new Error("Nguồn phải ở assets/; đích tương đối an toàn hoặc . cho nội dung folder vào home, không dùng ..");
    const copy = clone(document);
    const node = copy.nodes.find(entry => entry.id === nodeId);
    if (!node) throw new Error("Chọn máy nhận file.");
    node.files = node.files || [];
    if (node.files.length >= 16 || node.files.some(entry => target === "." || entry.target === "." || entry.target === target
        || entry.target.startsWith(target + "/") || target.startsWith(entry.target + "/")))
        throw new Error("Đường dẫn đích trùng/chồng lấn hoặc vượt 16 ánh xạ.");
    node.files.push({source: source, target: target});
    return copy;
}

function removeAsset(document, path, assets) {
    if (document.documentation === path) throw new Error("Bỏ liên kết hướng dẫn trước khi xóa file này.");
    if (document.nodes.some(node => (node.files || []).some(entry => entry.source === path
        || (path.startsWith(entry.source + "/") && (!assets || !assets.some(asset =>
            asset.path !== path && asset.path.startsWith(entry.source + "/")))))))
        throw new Error("Bỏ ánh xạ đang sử dụng file trước khi xóa tài nguyên.");
}

function workspace(node) {
    return node && node.user ? node.user.home : "/tmp/lab";
}

function destination(node, target) {
    return workspace(node) + (target === "." ? "" : "/" + target);
}

function pathsOverlap(first, second) {
    return first === second || first.startsWith(second + "/") || second.startsWith(first + "/");
}

function draftLabel(entry) {
    const title = entry.name || entry.lab_id || "Bản nháp";
    const identity = entry.lab_id && entry.lab_id !== title ? " · " + entry.lab_id : "";
    return title + identity + " · " + entry.id.substring(0, 8);
}

function homeUpload(document, nodeId, name, folder, subfolder, assets) {
    const node = document.nodes.find(entry => entry.id === nodeId);
    if (!node) throw new Error("Chọn máy nhận file.");
    if (subfolder && !safePath(subfolder)) throw new Error("Thư mục con không hợp lệ; không dùng đường dẫn tuyệt đối hoặc ..");
    if (!folder && (!safePath(name) || name.includes("/"))) throw new Error("Tên file không hợp lệ. Đổi tên file trước khi thêm.");
    const rootMapping = (node.files || []).find(entry => entry.target === ".");
    const source = rootMapping ? rootMapping.source : "assets/" + nodeId;
    if (pathsOverlap(source, "assets/docs") || (document.documentation && pathsOverlap(source, document.documentation)))
        throw new Error("Nguồn chứa tài liệu hướng dẫn. Chọn thư mục tài nguyên riêng cho máy ở mục ánh xạ nâng cao.");
    if (document.nodes.some(other => other.id !== nodeId && (other.files || []).some(mapping => pathsOverlap(source, mapping.source))))
        throw new Error("Nguồn đang dùng chung với máy khác. Chọn thư mục tài nguyên riêng trước khi upload vào máy này.");
    if (assets && assets.some(asset => asset.kind !== "directory" && (asset.path === source || source.startsWith(asset.path + "/"))))
        throw new Error("Nguồn ánh xạ phải là thư mục, không phải file.");
    if (!rootMapping && assets && assets.some(asset => asset.path.startsWith(source + "/")))
        throw new Error("Thư mục nguồn đã có tài nguyên. Xem lại rồi gắn ánh xạ vào home ở mục nâng cao, tránh tự nhập file cũ.");
    const definition = rootMapping ? clone(document) : addMapping(document, nodeId, source, ".");
    const suffix = (subfolder ? "/" + subfolder : "") + (folder ? "" : "/" + name);
    if (!safePath(source + suffix)) throw new Error("Đường dẫn tài nguyên vượt giới hạn hoặc không hợp lệ.");
    return {document: definition, logical: source + suffix, destination: workspace(node) + suffix};
}

function previewFiles(node, assets) {
    const entries = [];
    (node.files || []).forEach(mapping => {
        const exact = assets.find(asset => asset.path === mapping.source);
        if (exact && exact.kind !== "directory") {
            if (mapping.target !== ".") entries.push({path: mapping.target, isImport: false, size: exact.size});
            return;
        }
        assets.filter(asset => asset.path.startsWith(mapping.source + "/")).forEach(asset => {
            const relative = asset.path.substring(mapping.source.length + 1);
            entries.push({path: (mapping.target === "." ? relative : mapping.target + "/" + relative) + (asset.kind === "directory" ? "/" : ""),
                          isImport: false, size: asset.size});
        });
    });
    return entries;
}

function removeSeedFile(document, nodeId, path, assets) {
    const copy = clone(document);
    const node = copy.nodes.find(entry => entry.id === nodeId);
    if (!node || !safePath(path)) throw new Error("File không còn tồn tại.");
    let source = "";
    (node.files || []).forEach(mapping => {
        const exact = assets.find(asset => asset.path === mapping.source && asset.kind !== "directory");
        if (exact && mapping.target === path) source = mapping.source;
        else if (!exact && (mapping.target === "." || path.startsWith(mapping.target + "/"))) {
            const relative = mapping.target === "." ? path : path.substring(mapping.target.length + 1);
            const candidate = mapping.source + "/" + relative;
            if (assets.some(asset => asset.path === candidate && asset.kind !== "directory")) source = candidate;
        }
    });
    if (!source) throw new Error("Chọn một file trong máy.");
    if (document.documentation === source || copy.nodes.some(other => other.id !== nodeId && (other.files || []).some(mapping =>
        mapping.source === source || source.startsWith(mapping.source + "/"))))
        throw new Error("File đang dùng chung. Bỏ ánh xạ riêng ở Nâng cao, không xóa tài nguyên dùng chung.");
    const remaining = assets.filter(asset => asset.path !== source);
    node.files = (node.files || []).filter(mapping =>
        !(mapping.source === source || source.startsWith(mapping.source + "/"))
        || remaining.some(asset => asset.path === mapping.source || asset.path.startsWith(mapping.source + "/")));
    return {document: copy, source: source};
}

function changePath(document, path, value) {
    if (!Array.isArray(path) || !path.length) throw new Error("Đường dẫn cấu hình không hợp lệ.");
    const copy = clone(document);
    let target = copy;
    for (let index = 0; index < path.length - 1; index++) {
        const key = path[index];
        if (!target[key] || typeof target[key] !== "object" || Array.isArray(target[key])) target[key] = {};
        target = target[key];
    }
    const key = path[path.length - 1];
    if (value === "" || value === null || value === undefined) delete target[key];
    else target[key] = value;
    return copy;
}

function addEntry(document, section, entry, limit) {
    const copy = clone(document);
    const list = copy[section] || [];
    if (list.length >= limit) throw new Error("Đã đạt giới hạn mục cấu hình.");
    identifier(entry.id, list, "");
    list.push(clone(entry));
    copy[section] = list;
    return copy;
}

function updateEntry(document, section, index, field, value) {
    const copy = clone(document);
    const list = copy[section] || [];
    if (!list[index]) throw new Error("Mục cấu hình không còn tồn tại.");
    if (field === "id") {
        identifier(value, list, list[index].id);
        if (section === "parameters") Labedit.rewriteTokens(copy, list[index].id, value);
    }
    if (section === "parameters" && field === "default") value = Labedit.parameterValue(list[index], value);
    if (section === "parameters" && field === "type" && value !== list[index].type) {
        delete list[index].default;
        delete list[index].choices;
    }
    if (section === "parameters" && field === "choices" && !value.includes(list[index].default)) delete list[index].default;
    if (section === "quiz" && field === "type" && value !== list[index].type) {
        const identity = list[index].id;
        if (value === "preface") list[index] = {id: identity, type: "preface", text: ""};
        else if (value === "true_false") list[index] = {id: identity, type: "true_false", question: ""};
        else list[index] = {id: identity, type: "choice", question: "", options: ["A", "B"]};
        copy[section] = list;
        return copy;
    }
    if (section === "quiz" && field === "options" && list[index].answer >= value.length) delete list[index].answer;
    if (section === "parameterizations") {
        Labedit.updateOperation(list[index], field, value);
        copy[section] = list;
        return copy;
    }
    if (value === null || value === undefined) delete list[index][field];
    else list[index][field] = value;
    copy[section] = list;
    return copy;
}

function removeEntry(document, section, index) {
    const copy = clone(document);
    const list = copy[section] || [];
    if (index < 0 || index >= list.length) throw new Error("Mục cấu hình không còn tồn tại.");
    if (section === "parameters") Labedit.requireUnusedParameter(copy, list[index].id);
    list.splice(index, 1);
    copy[section] = list;
    return copy;
}

function quizGroups(document) {
    if (Array.isArray(document.quizzes)) return document.quizzes;
    return [{id: "default", title: "", items: Array.isArray(document.quiz) ? document.quiz : []}];
}

function migrateQuizGroups(document) {
    const copy = clone(document);
    if (!Array.isArray(copy.quizzes)) {
        copy.quizzes = [{id: "default", title: "", items: Array.isArray(copy.quiz) ? copy.quiz : []}];
        delete copy.quiz;
    }
    return copy;
}

function quizEntries(document) {
    return quizGroups(document).reduce((all, group) => all.concat(group.items || []), []);
}

function addQuizGroup(document, entry, limit) {
    const copy = migrateQuizGroups(document);
    if (copy.quizzes.length >= limit) throw new Error("Đã đạt giới hạn bộ Quiz.");
    identifier(entry.id, copy.quizzes, "");
    copy.quizzes.push(clone(entry));
    return copy;
}

function updateQuizGroup(document, index, field, value) {
    const copy = migrateQuizGroups(document);
    const group = copy.quizzes[index];
    if (!group) throw new Error("Bộ Quiz không còn tồn tại.");
    if (field === "id") identifier(value, copy.quizzes, group.id);
    if (value === null || value === undefined) delete group[field];
    else group[field] = value;
    if (field === "id") {
        (group.items || []).forEach(item => {
            item.quiz_id = value;
        });
    }
    return copy;
}

function removeQuizGroup(document, index) {
    const copy = migrateQuizGroups(document);
    if (index < 0 || index >= copy.quizzes.length) throw new Error("Bộ Quiz không còn tồn tại.");
    copy.quizzes.splice(index, 1);
    return copy;
}

function addQuizItem(document, groupIndex, entry, limit) {
    const copy = migrateQuizGroups(document);
    const group = copy.quizzes[groupIndex];
    if (!group) throw new Error("Bộ Quiz không còn tồn tại.");
    group.items = group.items || [];
    if (group.items.length >= limit) throw new Error("Đã đạt giới hạn mục trong bộ Quiz.");
    identifier(entry.id, quizEntries(copy), "");
    group.items.push(clone(entry));
    return copy;
}

function updateQuizItem(document, groupIndex, itemIndex, field, value) {
    const copy = migrateQuizGroups(document);
    const group = copy.quizzes[groupIndex];
    const item = group && group.items ? group.items[itemIndex] : null;
    if (!item) throw new Error("Mục Quiz không còn tồn tại.");
    if (field === "id") {
        identifier(value, quizEntries(copy), item.id);
        copy.quizzes.forEach(entry => (entry.items || []).forEach(candidate => {
            if (candidate.prerequisite === item.id) candidate.prerequisite = value;
        }));
    }
    if (field === "type" && value !== (item.type || "choice")) {
        const identity = item.id;
        if (value === "preface") group.items[itemIndex] = {id: identity, type: "preface", text: ""};
        else if (value === "true_false") group.items[itemIndex] = {id: identity, type: "true_false", question: ""};
        else group.items[itemIndex] = {id: identity, type: "choice", question: "", options: ["A", "B"]};
        return copy;
    }
    if (field === "options" && item.answer >= value.length) delete item.answer;
    if (value === null || value === undefined) delete item[field];
    else item[field] = value;
    return copy;
}

function removeQuizItem(document, groupIndex, itemIndex) {
    const copy = migrateQuizGroups(document);
    const group = copy.quizzes[groupIndex];
    if (!group || itemIndex < 0 || itemIndex >= (group.items || []).length)
        throw new Error("Mục Quiz không còn tồn tại.");
    const identity = group.items[itemIndex].id;
    if (copy.quizzes.some(entry => (entry.items || []).some(item => item.prerequisite === identity)))
        throw new Error("Mục Quiz đang là prerequisite của câu khác.");
    group.items.splice(itemIndex, 1);
    return copy;
}

function addNestedEntry(document, root, section, entry, limit) {
    const copy = clone(document);
    copy[root] = copy[root] || {};
    const list = copy[root][section] || [];
    if (list.length >= limit) throw new Error("Đã đạt giới hạn mục cấu hình.");
    identifier(entry.id, root === "assessment" ? Labedit.assessmentEntries(copy) : list, "");
    list.push(clone(entry));
    copy[root][section] = list;
    return copy;
}

function updateNestedEntry(document, root, section, index, field, value) {
    const copy = clone(document);
    const list = copy[root] && copy[root][section] ? copy[root][section] : [];
    if (!list[index]) throw new Error("Mục cấu hình không còn tồn tại.");
    if (field === "id") {
        identifier(value, root === "assessment" ? Labedit.assessmentEntries(copy) : list, list[index].id);
        if (root === "assessment" && section === "results") Labedit.renameResult(copy, list[index].id, value);
        if (root === "assessment" && section === "goals") Labedit.renameGoal(copy, list[index].id, value);
    }
    if (root === "assessment" && section === "results") Assessment.updateResult(list[index], field, value);
    else if (root === "assessment" && section === "goals") Assessment.updateGoal(list[index], field, value, copy[root].results || []);
    else Assessment.assign(list[index], field, value);
    copy[root][section] = list;
    return copy;
}

function removeNestedEntry(document, root, section, index) {
    const copy = clone(document);
    const list = copy[root] && copy[root][section] ? copy[root][section] : [];
    if (index < 0 || index >= list.length) throw new Error("Mục cấu hình không còn tồn tại.");
    if (root === "assessment" && section === "results") Labedit.requireUnusedResult(copy, list[index].id);
    if (root === "assessment" && section === "goals") Labedit.requireUnusedGoal(copy, list[index].id);
    list.splice(index, 1);
    copy[root][section] = list;
    return copy;
}
