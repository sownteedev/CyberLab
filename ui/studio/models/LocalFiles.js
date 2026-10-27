.pragma library

function path(url) {
    const value = String(url || "");
    if (!value.startsWith("file:///")) return "";
    try {
        const decoded = decodeURIComponent(value.substring(7));
        return /[\u0000-\u001f\u007f]/.test(decoded) ? "" : decoded;
    } catch (error) { return ""; }
}
