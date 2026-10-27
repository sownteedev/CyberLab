.pragma library

function workspacePath(session, nodeId) {
    if (!session) return "";
    const explicit = (session.workspaces || []).find(entry => entry[0] === nodeId);
    if (explicit) return explicit[1];
    const environment = (session.environments || []).find(entry => entry[0] === nodeId);
    return environment && environment[5] !== "/tmp" ? environment[5] + "/lab" : "/tmp/lab";
}

function hasMetadata(session, nodeId) {
    return !!session && [session.seed_files, session.files].some(entries =>
        (entries || []).some(entry => entry[0] === nodeId));
}

function filesForNode(session, imports, nodeId) {
    if (!session) return [];
    const root = workspacePath(session, nodeId);
    const relative = path => path.startsWith(root + "/") ? path.substring(root.length + 1) : path;
    const seeds = (session.seed_files || []).find(entry => entry[0] === nodeId);
    const directories = (session.seed_directories || []).find(entry => entry[0] === nodeId);
    const mappings = (session.files || []).find(entry => entry[0] === nodeId);
    let result = [];
    if (seeds) {
        result = seeds[1].map(path => ({ path: path, isImport: false, size: 0 }));
        if (directories) result = result.concat(directories[1].map(path =>
            ({ path: path + "/", isImport: false, size: 0 })));
    } else if (mappings) {
        result = mappings[1].map(path => ({ path: relative(path), isImport: false, size: 0 }));
    }
    return result.concat((imports || []).filter(record =>
        record.node === nodeId && record.state === "COMPLETE" && typeof record.path === "string"
    ).map(record => ({ path: relative(record.path), isImport: true, size: record.size })))
        .sort((first, second) => first.path.localeCompare(second.path));
}

function liveFiles(snapshot) {
    return (snapshot.entries || []).map(entry => ({
        path: entry.path + (entry.kind === "directory" ? "/" : ""),
        kind: entry.kind, size: entry.size, isImport: false, live: true
    }));
}

function treeRows(files) {
    const root = { children: [] };
    for (const file of files) {
        const parts = file.path.split("/").filter(part => part.length > 0);
        if (parts.length === 0) continue;
        if (file.path.startsWith("/")) parts.unshift("/");
        let parent = root;
        parts.forEach((name, index) => {
            const isDirectory = index < parts.length - 1 || file.path.endsWith("/");
            let entry = parent.children.find(child => child.name === name);
            if (!entry) {
                entry = { name: name, path: parts.slice(0, index + 1).join("/"), isDirectory: isDirectory, isImport: false,
                    kind: isDirectory ? "directory" : (file.kind || "file"), live: !!file.live, size: 0, children: [] };
                parent.children.push(entry);
            }
            entry.isDirectory = entry.isDirectory || isDirectory;
            if (index === parts.length - 1 && !isDirectory) {
                entry.isImport = entry.isImport || file.isImport;
                entry.size = file.size;
            }
            parent = entry;
        });
    }
    const rows = [];
    function appendChildren(parent, prefix) {
        parent.children.sort((first, second) =>
            Number(second.isDirectory) - Number(first.isDirectory) || first.name.localeCompare(second.name));
        parent.children.forEach((entry, index) => {
            const last = index === parent.children.length - 1;
            rows.push({
                name: entry.name + (entry.isDirectory && entry.name !== "/" ? "/" : ""),
                path: entry.path,
                kind: entry.kind,
                live: entry.live,
                branch: prefix + (last ? "└── " : "├── "),
                isDirectory: entry.isDirectory,
                isImport: !entry.isDirectory && entry.isImport,
                size: entry.isDirectory ? 0 : entry.size
            });
            appendChildren(entry, prefix + (last ? "    " : "│   "));
        });
    }
    appendChildren(root, "");
    return rows;
}
