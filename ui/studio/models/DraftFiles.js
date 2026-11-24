.pragma library

function clone(value) { return JSON.parse(JSON.stringify(value)); }
function within(path, parent) { return path === parent || path.startsWith(parent + "/"); }
function safe(path) {
    return typeof path === "string" && path.length <= 160
        && path.split("/").every(part => /^[A-Za-z0-9_][A-Za-z0-9_.-]{0,63}$/.test(part));
}
function initial(document, assets) {
    return {document: clone(document), assets: clone(assets), pending: {}, removals: [], roots: {}, remapped: {}};
}
function mappings(node) { return (node.files || []).concat((node.setup || {}).files || []); }
function systemPath(path) { return typeof path === "string" && path.startsWith("/"); }
function branch(path) { return systemPath(path) ? "System" : "Home"; }
function project(document, assets, nodeId, area) {
    const node = document.nodes.find(item => item.id === nodeId);
    if (!node) throw new Error("Máy không còn tồn tại.");
    const entries = Object.create(null);
    function add(path, source, kind, size) {
        if (!path || path === ".") return;
        if (entries[path] && entries[path].source && source && entries[path].source !== source)
            throw new Error("Các nhóm file đang trùng đường dẫn. Kiểm tra cấu hình trước khi sửa.");
        entries[path] = {path: path, source: source || (entries[path] || {}).source || "", kind: kind, size: size || 0};
        const parts = path.split("/");
        parts.pop();
        while (parts.length && parts.join("/")) {
            const parent = parts.join("/");
            if (!entries[parent]) entries[parent] = {path: parent, source: "", kind: "directory", size: 0};
            parts.pop();
        }
    }
    (area === "System" ? (node.setup || {}).files || [] : node.files || []).forEach(mapping => {
        const matches = assets.filter(asset => within(asset.path, mapping.source));
        if (!matches.length) throw new Error("Nguồn file chưa có dữ liệu. Lưu hoặc nhập lại file trước.");
        matches.forEach(asset => {
            const relative = asset.path === mapping.source ? "" : asset.path.substring(mapping.source.length + 1);
            const path = mapping.target === "." ? relative : mapping.target + (relative ? "/" + relative : "");
            add(path, asset.path, asset.kind || "file", asset.size);
        });
    });
    return Object.keys(entries).sort().map(path => entries[path]);
}
function used(document, source) {
    return document.documentation === source || document.nodes.some(node =>
        mappings(node).some(mapping => within(source, mapping.source) || within(mapping.source, source)));
}
function drop(state, path) {
    state.assets = state.assets.filter(asset => asset.path !== path);
    if (state.pending[path]) delete state.pending[path];
    if (!state.removals.includes(path)) state.removals.push(path);
}
function put(state, path, entry, kind, size) {
    if (path.length > 200 || path.split("/").length > 8) throw new Error("Đường dẫn quá dài hoặc có quá nhiều thư mục con.");
    state.pending[path] = entry;
    state.assets = state.assets.filter(asset => asset.path !== path).concat([{path: path, kind: kind, size: size || 0}]);
}
function privateNode(value, nodeId) {
    const state = clone(value);
    state.remapped = {};
    const node = state.document.nodes.find(item => item.id === nodeId);
    const existingRoot = Object.prototype.hasOwnProperty.call(state.roots, nodeId) ? state.roots[nodeId] : "";
    const sharedRoot = existingRoot && ((state.document.documentation && within(state.document.documentation, existingRoot))
        || state.document.nodes.some(other => (other.id !== nodeId ? mappings(other) : (other.setup || {}).files || []).some(mapping =>
            within(mapping.source, existingRoot) || within(existingRoot, mapping.source))));
    if (existingRoot && !sharedRoot && (node.files || []).length === 1 && node.files[0].source === existingRoot && node.files[0].target === ".") return state;
    const rows = project(state.document, state.assets, nodeId);
    const oldSources = (node.files || []).map(mapping => mapping.source);
    let root = "";
    for (let index = 0; index < 128; index++) {
        const candidate = "assets/editor/" + nodeId + (index ? "-" + index : "");
        if (!state.assets.some(asset => within(asset.path, candidate) || within(candidate, asset.path)) && !used(state.document, candidate)) {
            root = candidate;
            break;
        }
    }
    if (!root) throw new Error("Không còn đường dẫn riêng cho máy.");
    rows.forEach(row => {
        const destination = root + "/" + row.path;
        const content = row.kind === "directory" ? {directory: true} : state.pending[row.source] || {copy: row.source};
        put(state, destination, content, row.kind, row.size);
        if (row.source) state.remapped[row.source] = destination;
    });
    put(state, root, {directory: true}, "directory");
    node.files = [{source: root, target: "."}];
    state.roots[nodeId] = root;
    state.assets.slice().forEach(asset => {
        if (oldSources.some(source => within(asset.path, source)) && !used(state.document, asset.path)) drop(state, asset.path);
    });
    return state;
}
function requirePath(state, nodeId, path, exists) {
    if (!safe(path)) throw new Error("Tên chỉ gồm chữ không dấu, số, dấu chấm, gạch ngang hoặc gạch dưới.");
    const rows = project(state.document, state.assets, nodeId);
    const found = rows.find(row => row.path === path);
    if (exists && !found) throw new Error("File không còn tồn tại.");
    if (!exists && found) throw new Error("Tên này đã tồn tại.");
    if (rows.some(row => row.kind !== "directory" && path.startsWith(row.path + "/")))
        throw new Error("Không thể tạo file bên trong một file khác.");
    return found;
}
function create(value, nodeId, path, directory) {
    if (systemPath(path)) return createSystem(value, nodeId, path, directory);
    requirePath(value, nodeId, path, false);
    const state = privateNode(value, nodeId);
    const root = state.roots[nodeId];
    const parts = path.split("/");
    parts.pop();
    while (parts.length) {
        const parent = root + "/" + parts.join("/");
        if (!state.assets.some(asset => asset.path === parent)) put(state, parent, {directory: true}, "directory");
        parts.pop();
    }
    put(state, root + "/" + path, directory ? {directory: true} : {text: ""}, directory ? "directory" : "file");
    return state;
}
function rename(value, nodeId, path, name) {
    if (systemPath(path)) return renameSystem(value, nodeId, path, name);
    requirePath(value, nodeId, path, true);
    if (!safe(name) || name.includes("/")) throw new Error("Nhập một tên, không nhập đường dẫn.");
    const parent = path.includes("/") ? path.substring(0, path.lastIndexOf("/") + 1) : "";
    const destination = parent + name;
    if (destination === path) return clone(value);
    requirePath(value, nodeId, destination, false);
    const state = privateNode(value, nodeId);
    const root = state.roots[nodeId];
    const source = root + "/" + path;
    state.assets.filter(asset => within(asset.path, source)).forEach(asset => {
        const next = root + "/" + destination + asset.path.substring(source.length);
        put(state, next, state.pending[asset.path] || (asset.kind === "directory" ? {directory: true} : {copy: asset.path}), asset.kind, asset.size);
        Object.keys(state.remapped).forEach(old => { if (state.remapped[old] === asset.path) state.remapped[old] = next; });
        state.remapped[asset.path] = next;
        drop(state, asset.path);
    });
    const node = state.document.nodes.find(item => item.id === nodeId);
    if (node.setup && node.setup.home) node.setup.home.forEach(entry => {
        if (within(entry.path, path)) entry.path = destination + entry.path.substring(path.length);
    });
    const command = node.command || [];
    if (command.length === 2 && ["sh", "bash", "/bin/sh", "/bin/bash"].includes(command[0])) {
        const target = command[1].replace(/^\.\//, "");
        if (within(target, path)) command[1] = destination + target.substring(path.length);
    }
    return state;
}
function remove(value, nodeId, path) {
    if (systemPath(path)) return removeSystem(value, nodeId, path);
    requirePath(value, nodeId, path, true);
    const node = value.document.nodes.find(item => item.id === nodeId);
    const command = node.command || [];
    if (command.length === 2 && ["sh", "bash", "/bin/sh", "/bin/bash"].includes(command[0]) && within(command[1].replace(/^\.\//, ""), path))
        throw new Error("File đang dùng để khởi động. Chọn khởi động mặc định trước khi xóa.");
    const state = privateNode(value, nodeId);
    const edited = state.document.nodes.find(item => item.id === nodeId);
    if (edited.setup && edited.setup.home) edited.setup.home = edited.setup.home.filter(entry => !within(entry.path, path));
    const source = state.roots[nodeId] + "/" + path;
    state.assets.filter(asset => within(asset.path, source)).forEach(asset => drop(state, asset.path));
    return state;
}

function importResources(value, nodeId, folder, resources) {
    if (systemPath(folder)) return importSystem(value, nodeId, folder, resources);
    if (folder && !safe(folder)) throw new Error("Thư mục đích không hợp lệ.");
    const state = privateNode(value, nodeId);
    resources.forEach(resource => {
        const path = (folder ? folder + (resource.path ? "/" : "") : "") + resource.path;
        if (!path) return;
        if (!safe(path)) throw new Error("Tên file không hợp lệ: " + path);
        const existing = project(state.document, state.assets, nodeId);
        const match = existing.find(row => row.path === path);
        if ((match && match.kind !== resource.kind) || existing.some(row => row.kind !== "directory" && path.startsWith(row.path + "/")))
            throw new Error("File và thư mục trùng tên: " + path);
        put(state, state.roots[nodeId] + "/" + path, resource.content, resource.kind, resource.size);
    });
    return state;
}

function validateSystemPath(path) {
    if (!systemPath(path) || !safe(path.substring(1)) || path.split("/").length > 8) throw new Error("Đường dẫn System không hợp lệ.");
    const roots = ["/etc", "/usr/local", "/opt", "/srv", "/var/lib", "/home", "/shared_stuff"];
    if (!roots.some(root => within(path, root)) || (roots.includes(path) && path !== "/shared_stuff"))
        throw new Error("Chọn đường dẫn con trong /etc, /usr/local, /opt, /srv, /var/lib, /home hoặc /shared_stuff.");
    const protectedPaths = ["/etc/passwd", "/etc/group", "/etc/shadow", "/etc/gshadow", "/etc/sudoers", "/etc/sudoers.d",
        "/etc/pam.d", "/etc/pam.conf", "/etc/cron.d", "/etc/crontab", "/etc/cron.daily", "/etc/cron.hourly",
        "/etc/cron.weekly", "/etc/cron.monthly", "/etc/ld.so.preload", "/etc/ld.so.conf", "/etc/ld.so.conf.d",
        "/etc/systemd", "/etc/init.d", "/etc/rc.local", "/etc/profile", "/etc/profile.d", "/etc/environment",
        "/etc/security", "/etc/login.defs", "/etc/subuid", "/etc/subgid", "/etc/nsswitch.conf", "/etc/bash.bashrc",
        "/etc/ssh", "/etc/apt", "/etc/polkit-1", "/etc/dbus-1", "/etc/ssl", "/etc/alternatives"];
    if (protectedPaths.some(root => within(path, root) || within(root, path))
        || path.split("/").some(part => /cyberlab/i.test(part)))
        throw new Error("Đường dẫn hệ thống được bảo vệ.");
}
function identities(node) {
    const users = ["root"];
    const groups = ["root"];
    if (node.user && node.user.name) { users.push(node.user.name); groups.push(node.user.name); }
    ((node.setup || {}).users || []).forEach(user => { users.push(user.name); groups.push(user.name); });
    ((node.setup || {}).groups || []).forEach(group => groups.push(group.name));
    return {owners: users.filter((name, index) => users.indexOf(name) === index),
        groups: groups.filter((name, index) => groups.indexOf(name) === index)};
}
function metadata(document, assets, nodeId, path) {
    const node = document.nodes.find(item => item.id === nodeId);
    const row = project(document, assets, nodeId, branch(path)).find(entry => entry.path === path);
    if (!row) throw new Error("File không còn tồn tại.");
    const system = systemPath(path);
    const entries = system ? (node.setup || {}).files || [] : (node.setup || {}).home || [];
    const exact = entries.find(entry => (system ? entry.target : entry.path) === path);
    const parent = system ? entries.filter(entry => within(path, entry.target)).sort((first, second) => second.target.length - first.target.length)[0] : null;
    const identity = system ? "root" : (node.user || {}).name || "";
    return Object.assign({owner: parent && parent.owner || identity, group: parent && parent.group || identity,
        mode: parent ? (row.kind === "directory" ? parent.mode : ("0000" + (parseInt(parent.mode, 8) & 438).toString(8)).slice(-4))
            : row.kind === "directory" ? "0755" : "0644"}, exact || {},
        {kind: row.kind, explicit: !!exact});
}
function validateProperties(node, row, values) {
    const choices = identities(node);
    if (!choices.owners.includes(values.owner) || !choices.groups.includes(values.group)) throw new Error("Chọn chủ sở hữu và nhóm đã khai báo.");
    if (!/^[0-3][0-7]{3}$/.test(values.mode) || (row.kind !== "directory" && values.mode[0] !== "0"))
        throw new Error("Quyền gồm 4 số octal; chỉ thư mục được dùng setgid hoặc sticky, không dùng setuid.");
}
function freeSystemSource(state, nodeId) {
    for (let index = 0; index < 4096; index++) {
        const path = "assets/system/" + nodeId + "/entry-" + index;
        if (!state.assets.some(asset => within(asset.path, path) || within(path, asset.path)) && !used(state.document, path)) return path;
    }
    throw new Error("Không còn đường dẫn riêng cho máy.");
}
function privateSystem(value, nodeId, path) {
    const state = clone(value);
    state.remapped = {};
    const node = state.document.nodes.find(item => item.id === nodeId);
    const entries = (node.setup || {}).files || [];
    const originals = clone(entries);
    originals.slice().sort((first, second) => first.source.length - second.source.length).forEach(mapping => {
        if (path && !within(path, mapping.target) && !within(mapping.target, path)) return;
        if (state.remapped[mapping.source]) return;
        function sameDestination(entry) {
            return within(entry.source, mapping.source) && entry.target === mapping.target + entry.source.substring(mapping.source.length);
        }
        const shared = state.document.documentation && within(state.document.documentation, mapping.source)
            || state.document.nodes.some(other => (other.id === nodeId ? other.files || [] : mappings(other))
                .some(entry => within(entry.source, mapping.source) || within(mapping.source, entry.source)))
            || originals.some(entry => within(entry.source, mapping.source) && !sameDestination(entry));
        if (!shared) return;
        const root = freeSystemSource(state, nodeId);
        state.assets.slice().filter(asset => within(asset.path, mapping.source)).forEach(asset => {
            const destination = root + asset.path.substring(mapping.source.length);
            put(state, destination, asset.kind === "directory" ? {directory: true} : state.pending[asset.path] || {copy: asset.path}, asset.kind, asset.size);
            state.remapped[asset.path] = destination;
        });
        if (!state.assets.some(asset => asset.path === root)) put(state, root, {directory: true}, "directory");
        originals.forEach((entry, index) => {
            if (sameDestination(entry)) entries[index].source = root + entry.source.substring(mapping.source.length);
        });
    });
    return state;
}
function flattenSystem(value, nodeId) {
    const state = clone(value);
    state.remapped = {};
    const node = state.document.nodes.find(item => item.id === nodeId);
    const old = (node.setup || {}).files || [];
    const rows = project(state.document, state.assets, nodeId, "System").filter(row => row.source);
    const entries = rows.map(row => {
        const previous = old.find(entry => entry.target === row.path) || old.find(entry => within(row.path, entry.target)) || {};
        const values = metadata(state.document, state.assets, nodeId, row.path);
        const source = freeSystemSource(state, nodeId);
        put(state, source, row.kind === "directory" ? {directory: true} : state.pending[row.source] || {copy: row.source}, row.kind, row.size);
        state.remapped[row.source] = source;
        return Object.assign({}, previous, {source: source, target: row.path, owner: values.owner, group: values.group, mode: values.mode});
    });
    node.setup = Object.assign({}, node.setup || {}, {files: entries});
    state.assets.slice().forEach(asset => {
        if (old.some(entry => within(asset.path, entry.source)) && !used(state.document, asset.path)) drop(state, asset.path);
    });
    return state;
}
function requireSystem(state, nodeId, path, exists) {
    validateSystemPath(path);
    const node = state.document.nodes.find(item => item.id === nodeId);
    const home = node.user && (node.user.home || (node.user.name ? "/home/" + node.user.name : ""));
    if (home && within(path, home)) throw new Error("Dùng Home cho file của tài khoản chính.");
    const rows = project(state.document, state.assets, nodeId, "System");
    const row = rows.find(entry => entry.path === path);
    if (exists && !row) throw new Error("File không còn tồn tại.");
    if (!exists && row) throw new Error("Tên này đã tồn tại.");
    if (rows.some(entry => entry.kind !== "directory" && path.startsWith(entry.path + "/"))) throw new Error("Không thể đặt bên trong file.");
    return row;
}
function createSystem(value, nodeId, path, directory) {
    requireSystem(value, nodeId, path, false);
    const state = clone(value);
    state.remapped = {};
    const node = state.document.nodes.find(item => item.id === nodeId);
    const source = freeSystemSource(state, nodeId);
    put(state, source, directory ? {directory: true} : {text: ""}, directory ? "directory" : "file");
    node.setup = Object.assign({}, node.setup || {}, {files: ((node.setup || {}).files || []).concat([
        {source: source, target: path, owner: "root", group: "root", mode: directory ? "0755" : "0644"}])});
    return state;
}
function properties(value, nodeId, path, values) {
    const row = project(value.document, value.assets, nodeId, branch(path)).find(entry => entry.path === path);
    if (!row) throw new Error("File không còn tồn tại.");
    const original = value.document.nodes.find(item => item.id === nodeId);
    validateProperties(original, row, values);
    const system = systemPath(path);
    if (system) requireSystem(value, nodeId, path, true);
    let state = clone(value);
    state.remapped = {};
    const node = state.document.nodes.find(item => item.id === nodeId);
    node.setup = node.setup || {};
    const key = system ? "files" : "home";
    const entries = node.setup[key] || [];
    const index = entries.findIndex(entry => (system ? entry.target : entry.path) === path);
    let entry = index >= 0 ? clone(entries[index]) : {path: path};
    if (system && index < 0) {
        const source = row.source || freeSystemSource(state, nodeId);
        if (!row.source) put(state, source, {directory: true}, "directory");
        entry = {source: source, target: path};
    }
    entry = Object.assign(entry, {owner: values.owner, group: values.group, mode: values.mode});
    if (index < 0) entries.push(entry); else entries[index] = entry;
    node.setup[key] = entries;
    return state;
}
function renameSystem(value, nodeId, path, name) {
    requireSystem(value, nodeId, path, true);
    if (!safe(name) || name.includes("/")) throw new Error("Nhập một tên, không nhập đường dẫn.");
    const destination = path.substring(0, path.lastIndexOf("/") + 1) + name;
    if (destination === path) return clone(value);
    requireSystem(value, nodeId, destination, false);
    const state = flattenSystem(value, nodeId);
    const node = state.document.nodes.find(item => item.id === nodeId);
    node.setup.files.forEach(entry => {
        if (within(entry.target, path)) {
            entry.target = destination + entry.target.substring(path.length);
            validateSystemPath(entry.target);
        }
    });
    return state;
}
function removeSystem(value, nodeId, path) {
    requireSystem(value, nodeId, path, true);
    const state = flattenSystem(value, nodeId);
    const node = state.document.nodes.find(item => item.id === nodeId);
    const removed = node.setup.files.filter(entry => within(entry.target, path));
    node.setup.files = node.setup.files.filter(entry => !within(entry.target, path));
    removed.forEach(entry => { if (!used(state.document, entry.source)) drop(state, entry.source); });
    return state;
}
function importSystem(value, nodeId, folder, resources) {
    let state = privateSystem(value, nodeId, folder);
    resources.forEach(resource => {
        const path = folder.replace(/\/$/, "") + (resource.path ? "/" + resource.path : "");
        validateSystemPath(path);
        const row = project(state.document, state.assets, nodeId, "System").find(entry => entry.path === path);
        if (row) requireSystem(state, nodeId, path, true);
        if (row && row.kind !== resource.kind) throw new Error("File và thư mục trùng tên: " + path);
        if (!row) state = createSystem(state, nodeId, path, resource.kind === "directory");
        const target = project(state.document, state.assets, nodeId, "System").find(entry => entry.path === path);
        if (target.source) put(state, target.source, resource.content, resource.kind, resource.size);
    });
    return state;
}
