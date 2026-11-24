import {engine} from "../vendor/Highlight.mjs";

export function palette(dark) {
    return dark ? {
        text: "#e6e0e9", comment: "#93a0b4", keyword: "#ffb4a9", string: "#a5d6a7",
        number: "#f5c17c", title: "#82b4ff", built_in: "#8dd9e5", attr: "#d2c0ff",
        meta: "#c4b5fd", section: "#82b4ff", variable: "#8dd9e5"
    } : {
        text: "#1d1b20", comment: "#5e6d80", keyword: "#9c2736", string: "#27623c",
        number: "#8a4b08", title: "#185ca0", built_in: "#006575", attr: "#66449a",
        meta: "#68419a", section: "#185ca0", variable: "#006575"
    };
}

export function render(text, language, dark) {
    if (!language) return "";
    const colors = palette(dark);
    try {
        const html = engine.highlight(text, {language: language, ignoreIllegals: true}).value;
        return html.split(/(<[^>]+>)/).map(part => {
            if (part.startsWith("<span")) {
                const match = part.match(/class="hljs-([a-z_]+)/);
                const role = match ? match[1] : "text";
                return '<font color="' + (colors[role] || colors.text) + '">';
            }
            if (part === "</span>") return "</font>";
            return part.replace(/ /g, "&nbsp;").replace(/\t/g, "&#9;").replace(/\n/g, "<br>");
        }).join("");
    } catch (error) {
        return "";
    }
}
