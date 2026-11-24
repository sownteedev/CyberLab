.pragma library

function localPath(url) {
    const value = String(url || "");
    if (!value.startsWith("file:///")) return "";
    try {
        const decoded = decodeURIComponent(value.substring(7));
        return /[\u0000-\u001f\u007f]/.test(decoded) ? "" : decoded;
    } catch (error) { return ""; }
}

function fromPath(value, home) {
    let path = String(value || "");
    if (path === "~" || path.startsWith("~/")) path = localPath(home) + path.substring(1);
    if (!path.startsWith("/") || /[\u0000-\u001f\u007f]/.test(path)) return "";
    const parts = [];
    for (const part of path.split("/")) {
        if (part === "..") parts.pop();
        else if (part && part !== ".") parts.push(part);
    }
    return "file:///" + parts.map(part => encodeURIComponent(part)).join("/");
}

function parentFolder(url) {
    const path = localPath(url).replace(/\/$/, "");
    return fromPath(path.substring(0, path.lastIndexOf("/")) || "/");
}

function basename(url) {
    const path = localPath(url);
    return path.substring(path.lastIndexOf("/") + 1);
}

function validName(name) {
    return !!name.trim() && name !== "." && name !== ".." && !/[\/\u0000-\u001f\u007f]/.test(name);
}

function destination(folder, name, suffix) {
    if (!localPath(folder) || !validName(name)) return "";
    const extension = String(suffix || "").replace(/^\./, "");
    const filename = extension && !name.includes(".") ? name + "." + extension : name;
    return String(folder).replace(/\/$/, "") + "/" + encodeURIComponent(filename);
}

function filters(label) {
    const match = String(label || "").match(/\(([^()]*)\)\s*$/);
    return match ? match[1].trim().split(/\s+/).map(pattern => pattern === "*.*" ? "*" : pattern) : ["*"];
}

function sizeLabel(bytes) {
    if (bytes < 1024) return bytes + " B";
    if (bytes < 1024 * 1024) return (bytes / 1024).toFixed(1) + " KiB";
    return (bytes / (1024 * 1024)).toFixed(1) + " MiB";
}

function isImage(name) {
    return /\.(avif|bmp|gif|jpe?g|png|svg|webp)$/i.test(name);
}
