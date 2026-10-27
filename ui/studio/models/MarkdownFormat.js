.pragma library

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
