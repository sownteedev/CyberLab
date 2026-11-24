.pragma library

function readable(html, outline, surface) {
    let firstHeading = true;
    return html.replace(/font-size:\s*[\d.]+(?:pt|px);/g, "")
        .replace(/<p[^>]*>(<span style="[^"]*font-family:'monospace'[^"]*">[^<]*<\/span>)<\/p>/g, "<pre>$1</pre>")
        .replace(/<\/pre>\s*<pre>/g, "<br />")
        .replace(/<(h[1-6]|p|pre|li|ul|ol|table|td)(\s[^>]*)?>/g, (tag, name, attributes) => {
            let style = "";
            const cleaned = (attributes || "").replace(/\sstyle="([^"]*)"/g, (_, value) => {
                style += value;
                return "";
            });
            style = style.replace(/(?:margin-top|margin-bottom|line-height):[^;]*;/g, "");
            if (/^h[1-6]$/.test(name)) {
                style += "margin-top:" + (firstHeading ? 0 : 28) + "px;margin-bottom:12px;line-height:130%;font-size:"
                    + (name === "h1" ? 26 : name === "h2" ? 22 : 18) + "px;font-weight:700;";
                firstHeading = false;
            } else if (name === "p") {
                style += "margin-top:6px;margin-bottom:14px;line-height:120%;";
            } else if (name === "pre") {
                style += "margin-top:12px;margin-bottom:18px;line-height:110%;background-color:" + surface + ";";
            } else if (name === "li") {
                style += "margin-top:4px;margin-bottom:6px;line-height:120%;";
            } else if (name === "ul" || name === "ol") {
                style += "margin-top:8px;margin-bottom:16px;";
            } else if (name === "table") {
                style += "margin-top:12px;margin-bottom:20px;border-color:" + outline + ";";
            } else if (name === "td") {
                style += "padding:8px;border-color:" + outline + ";";
            }
            return "<" + name + cleaned.replace(/cellpadding="\d+"/, 'cellpadding="8"') + ' style="' + style + '">';
        }).replace(/<table[\s\S]*?<\/table>/g, table => table.replace(/<p style="([^"]*)"/g, (_, style) =>
            '<p style="' + style.replace(/margin-top:[^;]*;|margin-bottom:[^;]*;/g, "")
            + 'margin-top:0px;margin-bottom:0px;"'));
}

function compact(markdown) {
    let fence = "";
    let fenceLength = 0;
    let previous = "";
    return markdown.replace(/&/g, "&amp;").replace(/</g, "&lt;").replace(/>/g, "&gt;")
        .replace(/!\[/g, "\\![").split("\n").map(line => {
            const boundary = line.match(/^ {0,3}(`{3,}|~{3,})(.*)$/);
            if (boundary) {
                const marker = boundary[1];
                if (!fence) { fence = marker[0]; fenceLength = marker.length; }
                else if (marker[0] === fence && marker.length >= fenceLength && !boundary[2].trim()) fence = "";
                previous = "";
                return line;
            }
            if (fence) return line;
            const compactLine = /^ {0,3}=+\s*$/.test(line) && previous.trim() && !/^( {4}|\t)/.test(previous)
                ? line.replace(/=/g, "-") : line.replace(/^( {0,3})#(?=\s|$)/, "$1##");
            previous = line;
            return compactLine;
        }).join("\n");
}
