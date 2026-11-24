.pragma library

function copy(value) { return JSON.parse(JSON.stringify(value)); }
function validPassword(value) {
    if (typeof value !== "string" || !value || /[\x00\r\n]/.test(value)) return false;
    try { return encodeURIComponent(value).replace(/%[A-F\d]{2}/g, "x").length <= 128; }
    catch (error) { return false; }
}
function setup(node) { return node.setup || {}; }
function users(node) { return setup(node).users || []; }
function groups(node) { return setup(node).groups || []; }
function groupNames(node) { return groups(node).map(group => group.name).concat(users(node).map(user => user.name)); }

function checkName(node, name) {
    const reserved = ["root", "student", "nobody", "daemon", "bin", "sys", "sync", "games", "man", "lp", "mail", "news", "uucp",
        "proxy", "www-data", "backup", "list", "irc", "ubuntu", "sshd", "messagebus", "polkitd", "sudo", "wheel", "adm", "docker",
        "systemd-network", "systemd-resolve", "systemd-timesync", "tcpdump", "uuidd", "landscape", "syslog"];
    if (typeof name !== "string" || !/^[a-z][a-z0-9_-]{0,31}(?![\s\S])/.test(name) || reserved.includes(name))
        throw new Error("Tên không hợp lệ hoặc dành cho hệ thống.");
    if (name === node.user.name || groupNames(node).includes(name))
        throw new Error("Tên tài khoản hoặc nhóm đã tồn tại.");
}

function nextId(node) {
    const used = [2000].concat(users(node).map(user => user.uid), users(node).map(user => user.gid), groups(node).map(group => group.gid));
    for (let value = 3000; value <= 59999; value++)
        if (!used.includes(value)) return value;
    throw new Error("Không còn UID/GID trống.");
}

function withSetup(node) {
    if (!node || !node.user || node.user.uid !== 2000 || node.user.gid !== 2000)
        throw new Error("Chỉ cấu hình tài khoản trên máy Ubuntu.");
    const result = copy(node);
    if (!result.setup) result.setup = {};
    return result;
}

function addUser(node, name) {
    const result = withSetup(node);
    checkName(result, name);
    if (users(result).length >= 32) throw new Error("Tối đa 32 tài khoản phụ.");
    const identifier = nextId(result);
    result.setup.users = users(result).concat([{name: name, uid: identifier, gid: identifier, groups: [], sudo: "disabled", password_hash: "!"}]);
    return result;
}

function addGroup(node, name) {
    const result = withSetup(node);
    checkName(result, name);
    if (groups(result).length >= 32) throw new Error("Tối đa 32 nhóm bổ sung.");
    result.setup.groups = groups(result).concat([{name: name, gid: nextId(result)}]);
    return result;
}

function checkReferences(node, name, owner, identifier) {
    const entries = (setup(node).files || []).concat(setup(node).home || []);
    if (entries.some(entry => entry.group === name || entry.group === identifier || (owner && (entry.owner === name || entry.owner === identifier)))
            || users(node).some(user => user.name !== name && (user.groups || []).includes(name)))
        throw new Error("Tài khoản/nhóm đang được sử dụng. Hãy đổi chủ sở hữu hoặc nhóm trước.");
}

function removeUser(node, name) {
    const result = withSetup(node);
    const user = users(result).find(entry => entry.name === name);
    if (!user || name === result.user.name) throw new Error("Không thể xóa tài khoản chính.");
    checkReferences(result, name, true, user.uid);
    if (user.gid !== user.uid) checkReferences(result, name, false, user.gid);
    result.setup.users = users(result).filter(entry => entry.name !== name);
    return result;
}

function removeGroup(node, name) {
    const result = withSetup(node);
    const group = groups(result).find(entry => entry.name === name);
    if (!group) throw new Error("Không thể xóa nhóm riêng của tài khoản.");
    checkReferences(result, name, false, group.gid);
    result.setup.groups = groups(result).filter(entry => entry.name !== name);
    return result;
}

function setSudo(node, name, value) {
    const result = withSetup(node);
    if (!["disabled", "password", "passwordless"].includes(value)) throw new Error("Quyền sudo không hợp lệ.");
    const target = name === result.user.name ? result.setup : users(result).find(user => user.name === name);
    if (!target) throw new Error("Tài khoản không còn tồn tại.");
    target.sudo = value;
    return result;
}

function setGroups(node, name, values) {
    const result = withSetup(node);
    const user = users(result).find(entry => entry.name === name);
    if (!user || !Array.isArray(values) || values.length > 32 || values.some((value, index) => !groupNames(result).includes(value) || values.indexOf(value) !== index))
        throw new Error("Nhóm không hợp lệ hoặc vượt giới hạn 32 nhóm.");
    user.groups = values.slice();
    return result;
}

function renameMain(node, name) {
    if (name === node.user.name) return copy(node);
    const result = withSetup(node);
    if (name !== "student") checkName(result, name);
    else if (groupNames(result).includes(name)) throw new Error("Tên đã tồn tại.");
    checkReferences(result, result.user.name, true, result.user.uid);
    result.user.name = name;
    result.user.home = "/home/" + name;
    return result;
}

function renameUser(node, name, replacement) {
    const result = withSetup(node);
    if (name === replacement) return result;
    checkName(result, replacement);
    const user = users(result).find(entry => entry.name === name);
    if (!user) throw new Error("Tài khoản không còn tồn tại.");
    checkReferences(result, name, true, user.uid);
    if ((user.groups || []).includes(name)) throw new Error("Hãy bỏ nhóm riêng khỏi nhóm bổ sung trước khi đổi tên.");
    user.name = replacement;
    return result;
}

function renameGroup(node, name, replacement) {
    const result = withSetup(node);
    if (name === replacement) return result;
    checkName(result, replacement);
    const group = groups(result).find(entry => entry.name === name);
    if (!group) throw new Error("Nhóm không còn tồn tại.");
    checkReferences(result, name, false, group.gid);
    group.name = replacement;
    return result;
}
