.pragma library

function copy(value) { return JSON.parse(JSON.stringify(value)); }

function profiles(policy) {
    const allowed = policy ? policy.allowed_images || [] : [];
    const known = policy ? policy.image_profiles || [] : [];
    return known.filter(profile => allowed.includes(profile.image)).concat(
        allowed.filter(image => !known.some(profile => profile.image === image))
            .map(image => ({image: image, label: image, accounts: []})));
}

function profile(policy, image) {
    return profiles(policy).find(entry => entry.image === image) || null;
}

function sameAccount(first, second) {
    return !!first && !!second && ["name", "uid", "gid", "home", "shell"].every(key => first[key] === second[key]);
}

function validUsername(value, reserved) {
    const blocked = reserved || ["root", "nobody", "daemon", "bin", "sys", "sync", "games", "man", "lp", "mail", "news", "uucp",
        "proxy", "www-data", "backup", "list", "irc", "ubuntu", "sshd", "messagebus", "polkitd",
        "systemd-network", "systemd-resolve", "systemd-timesync", "tcpdump", "uuidd", "landscape", "syslog"];
    return typeof value === "string" && /^[a-z][a-z0-9_-]{0,31}(?![\s\S])/.test(value) && !blocked.includes(value);
}

function defaultAccount(profile, username) {
    if (!profile || !profile.workstation || !profile.custom_username || !profile.accounts.length)
        return null;
    const name = validUsername(username, profile.reserved_usernames) ? username : "student";
    return Object.assign({}, profile.accounts[0], {name: name, home: "/home/" + name});
}

function accountOptions(policy, node) {
    if (!node) return [];
    const selected = profile(policy, node.image);
    const options = (selected ? selected.accounts : []).map(account => ({label: account.name, user: account}));
    if (!selected || !selected.workstation)
        options.push({label: "Tài khoản mặc định (/tmp/lab)", user: null});
    if (node.user && !options.some(option => sameAccount(option.user, node.user)))
        options.push({label: node.user.name + " (tùy chỉnh)", user: node.user});
    return options;
}

function addressNumber(value) {
    if (!/^\d{1,3}(\.\d{1,3}){3}$/.test(value || "")) return null;
    const parts = value.split(".").map(Number);
    return parts.some(part => part > 255) ? null : parts.reduce((result, part) => result * 256 + part, 0);
}

function addressText(value) {
    return [24, 16, 8, 0].map(shift => (value >>> shift) & 255).join(".");
}

function nextAddress(document, networkId) {
    const network = document.networks.find(entry => entry.id === networkId);
    if (!network || !network.subnet) return "";
    const parts = network.subnet.split("/");
    const base = addressNumber(parts[0]);
    const prefix = Number(parts[1]);
    if (parts.length !== 2 || base === null || !Number.isInteger(prefix) || prefix < 16 || prefix > 30) return "";
    const size = Math.pow(2, 32 - prefix);
    if (base % size !== 0) return "";
    const used = [];
    for (const node of document.nodes) {
        const declared = (node.addresses || {})[networkId];
        if (!declared) continue;
        const sequence = declared.endsWith("+CLONE");
        const address = addressNumber(sequence ? declared.slice(0, -6) : declared);
        if (address === null) return "";
        const count = sequence ? node.clone || 1 : 1;
        for (let index = 0; index < count; index++) used.push(address + index);
    }
    const gateway = network.gateway ? addressNumber(network.gateway) : base + 1;
    if (gateway === null) return "";
    used.push(gateway);
    for (let offset = 1; offset < size - 1; offset++) {
        if (!used.includes(base + offset)) return addressText(base + offset);
    }
    return "";
}

function enableGui(node, policy) {
    if (node.image !== "cyberlab/ubuntu:24.04-1" || !policy || !policy.software_preparation) return;
    const previous = node.software || {};
    node.software = Object.assign({}, previous, {gui: true, apps: previous.apps || [], packages: previous.packages || []});
    if (!previous.gui) delete node.software.environment;
    const resources = policy.software_catalog && policy.software_catalog.resources;
    if (resources) {
        node.resources = Object.assign({}, node.resources || {});
        for (const name of Object.keys(resources))
            node.resources[name] = Math.max(node.resources[name] || 0, resources[name]);
    }
}

function newNode(document, policy, identifier, username) {
    const options = profiles(policy);
    if (!options.length) throw new Error("Chưa có môi trường được phép. Làm mới kết nối trước khi thêm máy.");
    const selected = options[0];
    const node = {id: identifier, image: selected.image, command: copy(selected.command || []), networks: [], terminal_count: 1};
    if (selected.resources) node.resources = copy(selected.resources);
    const usedAccounts = document.nodes.filter(entry => entry.image === selected.image && entry.user).map(entry => entry.user.name);
    const account = defaultAccount(selected, username) || selected.accounts.find(entry => !usedAccounts.includes(entry.name)) || selected.accounts[0];
    if (account) node.user = copy(account);
    if (document.networks.length) {
        const network = document.networks[0];
        node.networks = [network.id];
        const address = nextAddress(document, network.id);
        if (address) node.addresses = {[network.id]: address};
    }
    enableGui(node, policy);
    return node;
}

function terminalCapacity(document, index, policy) {
    if (!document || !document.nodes[index]) return 1;
    const budget = policy && policy.max_terminal_slots_per_lab || 8;
    const perNode = policy && policy.max_terminal_slots_per_node || 4;
    const used = document.nodes.reduce((total, node, position) => total
        + (position === index ? 0 : (node.terminal_count || 1) * (node.clone || 1)), 0);
    return Math.max(0, Math.min(perNode, Math.floor((budget - used) / (document.nodes[index].clone || 1))));
}

function canAddMachine(document, policy) {
    if (!document || !profiles(policy).length) return false;
    const machines = document.nodes.reduce((total, node) => total + (node.clone || 1), 0);
    const terminals = document.nodes.reduce((total, node) => total + (node.terminal_count || 1) * (node.clone || 1), 0);
    return machines < (policy && policy.max_nodes || 4) && terminals < (policy && policy.max_terminal_slots_per_lab || 8);
}

function changeImage(document, index, image, policy, username) {
    const selected = profile(policy, image);
    if (!selected) throw new Error("Môi trường không được daemon cho phép.");
    const result = copy(document);
    const node = result.nodes[index];
    if (!node) throw new Error("Máy không còn tồn tại.");
    if (node.image === image) return result;
    if (node.software && ((node.software.apps || []).length || (node.software.packages || []).length))
        throw new Error("Bỏ các phần mềm đã chọn trước khi đổi môi trường. Cấu hình hiện tại vẫn được giữ nguyên.");
    delete node.software;
    const followsPrompt = node.terminal_title === (node.user ? node.user.name : "nobody") + "@" + (node.hostname || node.id);
    const previous = profile(policy, node.image);
    const defaultCommand = previous && JSON.stringify(node.command) === JSON.stringify(previous.command);
    const legacyCommand = JSON.stringify(node.command) === JSON.stringify(["sleep", "3600"]);
    if ((!node.command || !node.command.length || defaultCommand || legacyCommand) && selected.command)
        node.command = copy(selected.command);
    const matching = defaultAccount(selected, username) || selected.accounts.find(account => sameAccount(account, node.user));
    if (matching) node.user = copy(matching);
    else if (selected.accounts.length) node.user = copy(selected.accounts[0]);
    else delete node.user;
    if (followsPrompt) node.terminal_title = (node.user ? node.user.name : "nobody") + "@" + (node.hostname || node.id);
    node.image = image;
    if (selected.resources) node.resources = copy(selected.resources);
    else if (!selected.workstation && previous && previous.workstation) delete node.resources;
    enableGui(node, policy);
    return result;
}
