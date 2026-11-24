.pragma library

function languageFor(path, text) {
    const extension = String(path).split(".").pop().toLowerCase();
    const languages = {py: "python", pyw: "python", sh: "bash", bash: "bash", zsh: "bash",
        json: "json", yaml: "yaml", yml: "yaml", js: "javascript", mjs: "javascript", cjs: "javascript",
        md: "markdown", markdown: "markdown"};
    if (Object.prototype.hasOwnProperty.call(languages, extension)) return languages[extension];
    const shebang = String(text || "").split("\n", 1)[0];
    if (/^#!.*\bpython[\d.]*\b/.test(shebang)) return "python";
    if (/^#!.*\b(?:sh|bash|zsh)\b/.test(shebang)) return "bash";
    return "";
}
